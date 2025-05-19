#!/usr/bin/env python3
"""
Attempt to recover RC4 keystream using IV reuse vulnerability
"""

import sqlite3
import sys
from collections import defaultdict
import numpy as np

def recover_keystream(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all C-MI tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    cmi_tables = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(cmi_tables)} C-MI tables")
    
    # Collect bursts by C-MI
    bursts_by_cmi = defaultdict(list)
    
    for table in cmi_tables:
        # Extract C-MI hex value from table name (e.g., C_752FEA1C_S0)
        parts = table.split('_')
        if len(parts) >= 2:
            cmi_str = parts[1]
            cmi = int(cmi_str, 16)
        else:
            continue
        cursor.execute(f"SELECT id, ambe_hex FROM {table} ORDER BY id")
        frames = cursor.fetchall()
        
        # Group into bursts of 3
        for i in range(0, len(frames) - 2, 3):
            burst = []
            for j in range(3):
                hex_val = frames[i+j][1]
                val = int(hex_val, 16)
                burst.append(val)
            bursts_by_cmi[cmi].append(burst)
    
    # Strategy: Since all 3 frames in a burst use the same keystream,
    # we can use differential analysis
    
    print("\n=== Keystream Recovery Analysis ===")
    
    # Look for bursts where frames are very similar (common in voice)
    keystream_estimates = defaultdict(list)
    
    for cmi, bursts in bursts_by_cmi.items():
        for burst_idx, burst in enumerate(bursts):
            # If two frames have similar plaintext, their XOR approximates
            # the plaintext difference
            f0, f1, f2 = burst
            
            # Calculate XORs
            xor01 = f0 ^ f1
            xor02 = f0 ^ f2
            xor12 = f1 ^ f2
            
            # Low hamming weight suggests similar plaintexts
            hw01 = bin(xor01).count('1')
            hw02 = bin(xor02).count('1')
            hw12 = bin(xor12).count('1')
            
            if hw01 < 15:  # Similar frames
                # The keystream is the same for both
                # C0 = P0 ⊕ K
                # C1 = P1 ⊕ K
                # C0 ⊕ C1 = P0 ⊕ P1
                
                keystream_estimates[cmi].append({
                    'burst': burst_idx,
                    'frames': (0, 1),
                    'xor': xor01,
                    'weight': hw01
                })
    
    # Find C-MIs with consistent patterns (likely same key)
    print(f"\nFound {len(keystream_estimates)} C-MIs with potential patterns")
    
    # Look for C-MIs that might share keystream segments
    cmi_correlations = defaultdict(list)
    
    cmis = list(bursts_by_cmi.keys())
    for i, cmi1 in enumerate(cmis):
        for cmi2 in cmis[i+1:]:
            bursts1 = bursts_by_cmi[cmi1]
            bursts2 = bursts_by_cmi[cmi2]
            
            if not bursts1 or not bursts2:
                continue
                
            # Compare first burst of each
            b1 = bursts1[0]
            b2 = bursts2[0]
            
            # If they share keystream, C1 ⊕ C2 = P1 ⊕ P2
            for frame_idx in range(3):
                xor = b1[frame_idx] ^ b2[frame_idx]
                hw = bin(xor).count('1')
                
                if hw < 25:  # Potentially related
                    cmi_correlations[(cmi1, cmi2)].append({
                        'frame': frame_idx,
                        'xor': xor,
                        'weight': hw
                    })
    
    print(f"\nFound {len(cmi_correlations)} C-MI pairs with correlations")
    
    # Show most promising correlations
    sorted_correlations = sorted(cmi_correlations.items(), 
                                key=lambda x: len(x[1]), 
                                reverse=True)[:10]
    
    for (cmi1, cmi2), corrs in sorted_correlations:
        print(f"\nC-MI 0x{cmi1:08X} ⟷ 0x{cmi2:08X}:")
        for corr in corrs[:3]:
            print(f"  Frame {corr['frame']}: 0x{corr['xor']:013X} ({corr['weight']} bits)")
    
    # CRITICAL: Exploit the fact that voice often has silence or repeated patterns
    print("\n=== Searching for repeated plaintext patterns ===")
    
    # Look for bursts that might contain silence (low variation)
    silence_candidates = []
    
    for cmi, bursts in bursts_by_cmi.items():
        for burst_idx, burst in enumerate(bursts):
            # Check if all frames are similar (suggesting repeated plaintext)
            xor01 = burst[0] ^ burst[1]
            xor02 = burst[0] ^ burst[2]
            
            if bin(xor01).count('1') < 8 and bin(xor02).count('1') < 8:
                silence_candidates.append({
                    'cmi': cmi,
                    'burst': burst_idx,
                    'frames': burst,
                    'xor01': xor01,
                    'xor02': xor02
                })
    
    print(f"\nFound {len(silence_candidates)} potential silence/repeated patterns")
    
    for candidate in silence_candidates[:5]:
        print(f"\nC-MI 0x{candidate['cmi']:08X} burst {candidate['burst']}:")
        for i, frame in enumerate(candidate['frames']):
            print(f"  Frame {i}: 0x{frame:013X}")
        print(f"  F0⊕F1: 0x{candidate['xor01']:013X} ({bin(candidate['xor01']).count('1')} bits)")
        print(f"  F0⊕F2: 0x{candidate['xor02']:013X} ({bin(candidate['xor02']).count('1')} bits)")
    
    # Final attack: Use knowledge that AMBE silence is often 0x00 or specific pattern
    print("\n=== Testing known plaintext patterns ===")
    
    # Common AMBE silence patterns (49 bits)
    silence_patterns = [
        0x0000000000000,  # All zeros
        0x1555555555555,  # Alternating pattern
    ]
    
    # Try to recover keystream by assuming known plaintext
    recovered_keystreams = []
    
    for cmi, bursts in bursts_by_cmi.items():
        for burst_idx, burst in enumerate(bursts):
            for pattern in silence_patterns:
                # If plaintext is known, keystream = ciphertext ⊕ plaintext
                potential_keystreams = []
                for frame in burst:
                    ks = frame ^ pattern
                    potential_keystreams.append(ks)
                
                # Check if keystreams are identical (they should be for same IV)
                if potential_keystreams[0] == potential_keystreams[1] == potential_keystreams[2]:
                    recovered_keystreams.append({
                        'cmi': cmi,
                        'burst': burst_idx,
                        'keystream': potential_keystreams[0],
                        'pattern': pattern
                    })
    
    print(f"\nRecovered {len(recovered_keystreams)} potential keystreams")
    
    for ks in recovered_keystreams[:5]:
        print(f"\nC-MI 0x{ks['cmi']:08X} burst {ks['burst']}:")
        print(f"  Assumed plaintext: 0x{ks['pattern']:013X}")
        print(f"  Recovered keystream: 0x{ks['keystream']:013X}")
    
    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    recover_keystream(db_path)