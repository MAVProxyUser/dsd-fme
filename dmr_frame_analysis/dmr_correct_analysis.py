#!/usr/bin/env python3
"""
Corrected DMR analysis with proper vocoder bit extraction
"""

import sqlite3
import sys
from collections import defaultdict, Counter

def analyze_vocoder_bits(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== Corrected DMR Vocoder Analysis ===")
    
    # Get a sample table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%' LIMIT 1")
    table = cursor.fetchone()[0]
    
    # Get some frames
    cursor.execute(f"SELECT ambe_hex FROM {table} LIMIT 10")
    frames = cursor.fetchall()
    
    print(f"\nAnalyzing frames from {table}:")
    for i, (ambe_hex,) in enumerate(frames):
        # Convert hex to integer
        value = int(ambe_hex, 16)
        
        # Extract different bit ranges
        first_7_bits = value & 0x7F  # Gain
        first_49_bits = value & ((1 << 49) - 1)  # Vocoder
        
        print(f"\nFrame {i}: {ambe_hex}")
        print(f"  Full value: 0x{value:016X}")
        print(f"  Binary: {bin(value)[2:].zfill(64)}")
        print(f"  First 7 bits (gain): {first_7_bits} (0x{first_7_bits:02X})")
        print(f"  First 49 bits: 0x{first_49_bits:013X}")
        print(f"  Bit 48-63: 0x{(value >> 48) & 0xFFFF:04X}")
    
    # Analyze bit distribution across all frames
    print("\n=== Bit Distribution Analysis ===")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    tables = [row[0] for row in cursor.fetchall()]
    
    all_values = []
    for table in tables[:20]:  # Sample first 20 tables
        cursor.execute(f"SELECT ambe_hex FROM {table}")
        for (ambe_hex,) in cursor.fetchall():
            value = int(ambe_hex, 16)
            all_values.append(value)
    
    print(f"\nAnalyzing {len(all_values)} frames")
    
    # Bit position analysis
    bit_counts = [0] * 64
    for value in all_values:
        for bit_pos in range(64):
            if value & (1 << bit_pos):
                bit_counts[bit_pos] += 1
    
    print("\nBit position probabilities:")
    for pos in range(0, 64, 8):
        probs = []
        for i in range(8):
            if pos + i < 64:
                prob = bit_counts[pos + i] / len(all_values)
                probs.append(f"{prob:.3f}")
        print(f"  Bits {pos:2d}-{pos+7:2d}: {' '.join(probs)}")
    
    # Check gain distribution
    gain_dist = Counter()
    for value in all_values:
        gain = (value >> 57) & 0x7F  # Gain is in the MSB area
        gain_dist[gain] += 1
    
    print("\n=== Gain Distribution (top bits) ===")
    for gain, count in gain_dist.most_common(10):
        print(f"  Gain {gain}: {count} times ({count/len(all_values)*100:.1f}%)")
    
    conn.close()

if __name__ == "__main__":
    db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    analyze_vocoder_bits(db_path)