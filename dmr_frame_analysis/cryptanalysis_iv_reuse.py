#!/usr/bin/env python3
"""
DMR cryptanalysis exploiting IV reuse across 3 AMBE frames per burst
"""

import sqlite3
import sys
from collections import defaultdict, Counter
import struct

def hamming_weight(x):
    """Count number of 1 bits"""
    return bin(x).count('1')

def find_patterns(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all C-MI tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    cmi_tables = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(cmi_tables)} C-MI tables")
    
    # Collect all bursts grouped by C-MI
    all_bursts = defaultdict(list)
    
    for table in cmi_tables:
        cmi = table.replace('C_', '').replace('_S0', '')
        cursor.execute(f"SELECT id, ambe_hex FROM {table} ORDER BY id")
        frames = cursor.fetchall()
        
        # Group into bursts of 3
        for i in range(0, len(frames) - 2, 3):
            burst = []
            for j in range(3):
                hex_val = frames[i+j][1]
                # Convert to integer
                val = int(hex_val, 16)
                burst.append(val)
            all_bursts[cmi].append(burst)
    
    print(f"\nAnalyzing {sum(len(b) for b in all_bursts.values())} total bursts")
    
    # Key insight: All 3 frames in a burst use the same IV
    # So if we XOR any two frames, we get the XOR of their plaintexts
    
    # Look for similar plaintexts across bursts
    similar_plains = []
    for cmi, bursts in all_bursts.items():
        for i, burst1 in enumerate(bursts):
            for j, burst2 in enumerate(bursts[i+1:], i+1):
                # XOR corresponding frames between bursts
                for frame_idx in range(3):
                    xor = burst1[frame_idx] ^ burst2[frame_idx]
                    hw = hamming_weight(xor)
                    if hw <= 10:  # Similar plaintexts
                        similar_plains.append({
                            'cmi': cmi,
                            'burst1': i,
                            'burst2': j,
                            'frame': frame_idx,
                            'xor': xor,
                            'bits': hw
                        })
    
    print(f"\nFound {len(similar_plains)} frame pairs with ≤10 bit differences")
    
    # Analyze intra-burst patterns (same IV, different plaintexts)
    intra_patterns = Counter()
    for cmi, bursts in all_bursts.items():
        for burst in bursts:
            # XOR each pair within the burst
            xor01 = burst[0] ^ burst[1]
            xor02 = burst[0] ^ burst[2]
            xor12 = burst[1] ^ burst[2]
            
            # Look for patterns in XOR relationships
            pattern = (hamming_weight(xor01), hamming_weight(xor02), hamming_weight(xor12))
            intra_patterns[pattern] += 1
    
    print("\n=== Intra-burst XOR patterns (hamming weights) ===")
    for pattern, count in intra_patterns.most_common(10):
        print(f"  {pattern}: {count} times")
    
    # Look for keystream reuse across different C-MIs
    keystream_candidates = defaultdict(list)
    
    # If two C-MIs encrypt similar plaintext, their XOR reveals keystream difference
    cmis = list(all_bursts.keys())
    for i, cmi1 in enumerate(cmis):
        for cmi2 in cmis[i+1:]:
            bursts1 = all_bursts[cmi1]
            bursts2 = all_bursts[cmi2]
            
            min_len = min(len(bursts1), len(bursts2))
            for burst_idx in range(min_len):
                for frame_idx in range(3):
                    xor = bursts1[burst_idx][frame_idx] ^ bursts2[burst_idx][frame_idx]
                    hw = hamming_weight(xor)
                    
                    if hw <= 20:  # Potential keystream relationship
                        keystream_candidates[xor].append({
                            'cmi1': cmi1,
                            'cmi2': cmi2,
                            'burst': burst_idx,
                            'frame': frame_idx
                        })
    
    print(f"\n=== Potential keystream relationships ===")
    print(f"Found {len(keystream_candidates)} unique XOR values")
    
    # Show most common patterns
    sorted_candidates = sorted(keystream_candidates.items(), 
                              key=lambda x: len(x[1]), 
                              reverse=True)[:10]
    
    for xor_val, occurrences in sorted_candidates:
        print(f"\nXOR: 0x{xor_val:013X} (bits: {hamming_weight(xor_val)})")
        print(f"Seen {len(occurrences)} times:")
        for occ in occurrences[:3]:  # Show first 3
            print(f"  {occ['cmi1'][:8]} ⊕ {occ['cmi2'][:8]} burst {occ['burst']} frame {occ['frame']}")
    
    # CRITICAL INSIGHT: Since all 3 frames in a burst use the same IV,
    # we can correlate patterns across frames within each burst
    
    print("\n=== Exploiting triple frame IV reuse ===")
    
    # If plaintext has patterns, we'll see correlated XORs
    correlated_bursts = []
    for cmi, bursts in all_bursts.items():
        for burst_idx, burst in enumerate(bursts):
            xor01 = burst[0] ^ burst[1]
            xor02 = burst[0] ^ burst[2]
            xor12 = burst[1] ^ burst[2]
            
            # Check for mathematical relationships
            if xor01 ^ xor02 == xor12:  # This should always be true
                # Look for special patterns
                if hamming_weight(xor01) < 15 and hamming_weight(xor02) < 15:
                    correlated_bursts.append({
                        'cmi': cmi,
                        'burst': burst_idx,
                        'xor01': xor01,
                        'xor02': xor02,
                        'xor12': xor12
                    })
    
    print(f"Found {len(correlated_bursts)} bursts with low-weight correlations")
    for cb in correlated_bursts[:5]:
        print(f"\nC-MI {cb['cmi'][:8]} burst {cb['burst']}:")
        print(f"  F0⊕F1: 0x{cb['xor01']:013X} ({hamming_weight(cb['xor01'])} bits)")
        print(f"  F0⊕F2: 0x{cb['xor02']:013X} ({hamming_weight(cb['xor02'])} bits)")
        print(f"  F1⊕F2: 0x{cb['xor12']:013X} ({hamming_weight(cb['xor12'])} bits)")
    
    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    find_patterns(db_path)