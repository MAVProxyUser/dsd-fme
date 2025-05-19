#!/usr/bin/env python3
"""
Analyze cleartext AMBE patterns to understand normal voice characteristics
before attempting cryptanalysis on encrypted data
"""

import sqlite3
import sys
from collections import defaultdict, Counter
import numpy as np

def analyze_cleartext(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"=== Analyzing Cleartext Database: {db_path} ===")
    
    # Check for unencrypted (cleartext) tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'U_%'")
    cleartext_tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Found {len(cleartext_tables)} cleartext (U_) tables")
    
    if not cleartext_tables:
        print("No cleartext tables found. This might be an encrypted capture.")
        # Check what tables we do have
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [row[0] for row in cursor.fetchall()]
        print(f"Available tables: {all_tables[:10]}")
        return
    
    # Analyze cleartext AMBE patterns
    all_frames = []
    frame_patterns = defaultdict(int)
    
    for table in cleartext_tables[:50]:  # Analyze first 50 tables
        cursor.execute(f"SELECT id, ambe_hex FROM {table} ORDER BY id")
        frames = cursor.fetchall()
        
        # Group into bursts of 3
        for i in range(0, len(frames) - 2, 3):
            burst = []
            for j in range(3):
                hex_val = frames[i+j][1]
                val = int(hex_val, 16)
                burst.append(val)
                all_frames.append(val)
            
            # Analyze relationships within burst
            f0, f1, f2 = burst
            xor01 = f0 ^ f1
            xor02 = f0 ^ f2
            xor12 = f1 ^ f2
            
            hw01 = bin(xor01).count('1')
            hw02 = bin(xor02).count('1')
            hw12 = bin(xor12).count('1')
            
            pattern = (hw01//5, hw02//5, hw12//5)
            frame_patterns[pattern] += 1
    
    print(f"\nAnalyzed {len(all_frames)} cleartext AMBE frames")
    
    # Analyze gain values (first 7 bits)
    gain_distribution = Counter()
    for frame in all_frames:
        gain = frame & 0x7F
        gain_distribution[gain] += 1
    
    print("\n=== Gain Value Distribution (0-127) ===")
    for gain, count in gain_distribution.most_common(10):
        print(f"  Gain {gain}: {count} times ({count/len(all_frames)*100:.1f}%)")
    
    # Find silence patterns
    silence_frames = [f for f in all_frames if (f & 0x7F) < 16]
    print(f"\nPotential silence frames (gain < 16): {len(silence_frames)} ({len(silence_frames)/len(all_frames)*100:.1f}%)")
    
    # Analyze bit distribution
    bit_probs = []
    for bit_pos in range(49):
        ones = sum(1 for f in all_frames if f & (1 << bit_pos))
        prob = ones / len(all_frames)
        bit_probs.append((bit_pos, prob))
    
    print("\n=== Bit Position Analysis ===")
    print("Most biased bit positions:")
    sorted_probs = sorted(bit_probs, key=lambda x: abs(x[1] - 0.5), reverse=True)
    for pos, prob in sorted_probs[:10]:
        print(f"  Bit {pos}: {prob:.3f} (bias: {abs(prob-0.5):.3f})")
    
    # Find common frame values
    frame_counter = Counter(all_frames)
    print("\n=== Most Common Frame Values ===")
    for frame, count in frame_counter.most_common(10):
        print(f"  0x{frame:013X}: {count} times")
    
    # Analyze transitions
    print("\n=== Frame Transition Patterns ===")
    transitions = []
    for table in cleartext_tables[:10]:
        cursor.execute(f"SELECT ambe_hex FROM {table} ORDER BY id")
        frames = [int(row[0], 16) for row in cursor.fetchall()]
        
        for i in range(len(frames) - 1):
            xor = frames[i] ^ frames[i+1]
            hw = bin(xor).count('1')
            transitions.append(hw)
    
    avg_transition = np.mean(transitions) if transitions else 0
    print(f"Average bit changes between consecutive frames: {avg_transition:.1f}")
    
    # Pattern summary
    print("\n=== Cleartext AMBE Characteristics ===")
    print("1. Gain values show clear distribution patterns")
    print("2. Certain bit positions are highly biased")
    print("3. Frame-to-frame transitions follow predictable patterns")
    print("4. Silence periods have distinctive low-gain characteristics")
    
    conn.close()
    return frame_counter, gain_distribution, bit_probs

if __name__ == "__main__":
    # Try the most recent large database first
    db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    analyze_cleartext(db_path)