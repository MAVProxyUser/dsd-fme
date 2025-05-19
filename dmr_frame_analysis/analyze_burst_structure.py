#!/usr/bin/env python3
"""Analyze burst structure and patterns in DMR capture"""

import sqlite3
import sys
from collections import defaultdict, Counter

def analyze_burst_structure(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all C-MI tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    cmi_tables = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(cmi_tables)} C-MI tables")
    
    # Analyze frame counts and burst patterns
    frame_count_dist = Counter()
    complete_bursts = 0
    partial_bursts = 0
    all_xors = []
    
    for table in cmi_tables[:50]:  # Sample first 50 for speed
        cursor.execute(f"SELECT id, ambe_hex FROM {table} ORDER BY id")
        frames = cursor.fetchall()
        
        frame_count = len(frames)
        frame_count_dist[frame_count] += 1
        
        complete = frame_count // 3
        partial = frame_count % 3
        
        if partial > 0:
            partial_bursts += 1
        else:
            complete_bursts += complete
        
        # Analyze XOR patterns within bursts
        for i in range(0, frame_count - 3, 3):
            burst = frames[i:i+3]
            if len(burst) == 3:
                # XOR first frame with second and third
                v1 = int(burst[0][1], 16)
                v2 = int(burst[1][1], 16)
                v3 = int(burst[2][1], 16)
                
                xor12 = v1 ^ v2
                xor13 = v1 ^ v3
                xor23 = v2 ^ v3
                
                all_xors.extend([xor12, xor13, xor23])
    
    print("\n=== Frame Count Distribution ===")
    for count, tables in sorted(frame_count_dist.items()):
        print(f"{count} frames: {tables} tables")
    
    print(f"\n=== Burst Analysis ===")
    print(f"Complete bursts: {complete_bursts}")
    print(f"Tables with partial bursts: {partial_bursts}")
    
    # Look for patterns in XORs
    xor_counter = Counter(all_xors)
    print(f"\n=== XOR Pattern Analysis ===")
    print(f"Total XOR values: {len(all_xors)}")
    print(f"Unique XOR values: {len(xor_counter)}")
    
    # Find most common XOR values
    print("\nMost common XOR values:")
    for xor_val, count in xor_counter.most_common(10):
        print(f"  0x{xor_val:013X}: {count} times")
    
    # Check for small Hamming distances
    small_hamming = [x for x in all_xors if bin(x).count('1') <= 10]
    print(f"\nXORs with ≤10 bits set: {len(small_hamming)} ({len(small_hamming)/len(all_xors)*100:.1f}%)")
    
    # Analyze consecutive frame differences
    print("\n=== Consecutive Frame Analysis ===")
    for table in cmi_tables[:5]:
        print(f"\n{table}:")
        cursor.execute(f"SELECT id, ambe_hex FROM {table} ORDER BY id LIMIT 9")
        frames = cursor.fetchall()
        
        for i in range(0, len(frames)-1, 3):
            burst = frames[i:i+3]
            if len(burst) == 3:
                print(f"  Burst {i//3}:")
                for j in range(3):
                    print(f"    Frame {j}: {burst[j][1]}")
                
                # Show intra-burst XORs
                v1 = int(burst[0][1], 16)
                v2 = int(burst[1][1], 16)
                v3 = int(burst[2][1], 16)
                
                print(f"    F0⊕F1: 0x{v1^v2:013X} (bits: {bin(v1^v2).count('1')})")
                print(f"    F0⊕F2: 0x{v1^v3:013X} (bits: {bin(v1^v3).count('1')})")
                print(f"    F1⊕F2: 0x{v2^v3:013X} (bits: {bin(v2^v3).count('1')})")
    
    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    analyze_burst_structure(db_path)