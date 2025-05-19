#!/usr/bin/env python3
"""
Detailed analysis of cleartext AMBE frames to understand patterns
"""

import sqlite3
import sys
from collections import defaultdict, Counter
import numpy as np

def analyze_cleartext_details(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"=== Detailed Cleartext Analysis: {db_path} ===")
    
    # Get cleartext table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'U_%'")
    cleartext_tables = [row[0] for row in cursor.fetchall()]
    
    if not cleartext_tables:
        print("No cleartext tables found")
        return
    
    table = cleartext_tables[0]
    print(f"Analyzing table: {table}")
    
    # Get all frames with full details
    cursor.execute(f"SELECT * FROM {table} ORDER BY id LIMIT 50")
    frames = cursor.fetchall()
    
    print(f"\nFirst 10 frames:")
    for i, frame in enumerate(frames[:10]):
        print(f"Frame {i}: {frame}")
    
    # Check schema
    cursor.execute(f"PRAGMA table_info({table})")
    schema = cursor.fetchall()
    print(f"\nTable schema:")
    for col in schema:
        print(f"  {col}")
    
    # Analyze ambe_hex values
    cursor.execute(f"SELECT id, ambe_hex FROM {table} ORDER BY id")
    all_frames = cursor.fetchall()
    
    # Convert to integers and analyze
    frame_values = []
    for id, hex_str in all_frames:
        val = int(hex_str, 16)
        frame_values.append(val)
    
    # Check if this is actual silence or test pattern
    print(f"\n=== Frame Analysis ===")
    print(f"Total frames: {len(frame_values)}")
    
    # Extract just the gain bits (first 7 bits)
    gains = [f & 0x7F for f in frame_values]
    print(f"Unique gain values: {set(gains)}")
    
    # Check if the rest of the bits are random or patterned
    non_gain_bits = [f >> 7 for f in frame_values]
    unique_non_gain = len(set(non_gain_bits))
    print(f"Unique non-gain patterns: {unique_non_gain}")
    
    # Look for repeating patterns
    pattern_counter = Counter(frame_values)
    repeated_frames = [f for f, count in pattern_counter.items() if count > 1]
    print(f"Repeated frame values: {len(repeated_frames)}")
    
    # Analyze bursts
    print(f"\n=== Burst Analysis (groups of 3) ===")
    for i in range(0, min(15, len(frame_values)-2), 3):
        burst = frame_values[i:i+3]
        print(f"Burst {i//3}:")
        for j, frame in enumerate(burst):
            print(f"  Frame {j}: 0x{frame:013X} (gain: {frame & 0x7F})")
        
        # Check XOR relationships
        if len(burst) == 3:
            xor01 = burst[0] ^ burst[1]
            xor02 = burst[0] ^ burst[2]
            xor12 = burst[1] ^ burst[2]
            print(f"  XOR patterns:")
            print(f"    F0⊕F1: 0x{xor01:013X} ({bin(xor01).count('1')} bits)")
            print(f"    F0⊕F2: 0x{xor02:013X} ({bin(xor02).count('1')} bits)")
            print(f"    F1⊕F2: 0x{xor12:013X} ({bin(xor12).count('1')} bits)")
    
    # Check if this is the simulated test audio
    test_pattern_file = "/home/ubuntu/dsd-fme_sqlite/dmr_attack_analysis/simulated_dmr_30min.wav"
    print(f"\n=== Checking for Test Patterns ===")
    print(f"Test audio file exists: {os.path.exists(test_pattern_file)}")
    
    # Statistical analysis
    print(f"\n=== Statistical Analysis ===")
    avg_bits_set = np.mean([bin(f).count('1') for f in frame_values])
    print(f"Average bits set per frame: {avg_bits_set:.1f}")
    
    # Check entropy
    from math import log2
    unique_frames = len(set(frame_values))
    total_frames = len(frame_values)
    if unique_frames > 0:
        entropy = -sum((pattern_counter[v]/total_frames) * log2(pattern_counter[v]/total_frames) 
                      for v in pattern_counter if pattern_counter[v] > 0)
        print(f"Frame entropy: {entropy:.3f} bits")
        print(f"Max possible entropy: {log2(total_frames):.3f} bits")
    
    conn.close()

if __name__ == "__main__":
    db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_112958_062803.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    import os
    analyze_cleartext_details(db_path)