#!/usr/bin/env python3
"""
DMR IV Reuse Attack
Exploit the fact that all 3 AMBE frames in a burst use the same IV
"""

import sqlite3
import sys
from collections import defaultdict, Counter
import numpy as np

def extract_vocoder_bits(ambe_hex):
    """Extract the 49 vocoder bits from the 64-bit logged value"""
    # Convert hex to binary
    value = int(ambe_hex, 16)
    # We have 64 bits, vocoder uses first 49
    vocoder_mask = (1 << 49) - 1
    return value & vocoder_mask

def analyze_iv_reuse(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== DMR IV Reuse Attack ===")
    print(f"Database: {db_path}\n")
    
    # Get all C_MI tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    cmi_tables = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(cmi_tables)} C-MI tables")
    
    # Collect bursts
    all_bursts = []
    burst_by_cmi = defaultdict(list)
    
    for table in cmi_tables[:50]:  # Analyze first 50 tables
        cmi = table.split('_')[1]
        
        cursor.execute(f"""
            SELECT id, ambe_hex, superframe_id 
            FROM {table} 
            ORDER BY id
        """)
        frames = cursor.fetchall()
        
        # Group frames into bursts (3 frames each)
        for i in range(0, len(frames) - 2, 3):
            burst = []
            for j in range(3):
                frame_id, ambe_hex, sf_id = frames[i + j]
                vocoder_bits = extract_vocoder_bits(ambe_hex)
                burst.append({
                    'id': frame_id,
                    'full_hex': ambe_hex,
                    'vocoder': vocoder_bits,
                    'superframe': sf_id
                })
            
            burst_data = {
                'cmi': cmi,
                'frames': burst,
                'superframe': burst[0]['superframe']
            }
            all_bursts.append(burst_data)
            burst_by_cmi[cmi].append(burst_data)
    
    print(f"\nAnalyzed {len(all_bursts)} complete bursts")
    
    # IV Reuse Analysis
    print("\n=== IV Reuse Within Bursts ===")
    print("All 3 frames in each burst use the SAME keystream")
    print("This means: C1 ⊕ C2 = P1 ⊕ P2 (plaintext difference)")
    
    # Look for similar plaintexts within bursts
    low_hamming_pairs = []
    
    for burst in all_bursts:
        frames = burst['frames']
        # Compare all pairs within the burst
        for i in range(3):
            for j in range(i+1, 3):
                xor = frames[i]['vocoder'] ^ frames[j]['vocoder']
                hamming = bin(xor).count('1')
                
                if hamming <= 10:  # Similar plaintexts
                    low_hamming_pairs.append({
                        'cmi': burst['cmi'],
                        'frame_i': i,
                        'frame_j': j,
                        'xor': xor,
                        'hamming': hamming
                    })
    
    print(f"\nFound {len(low_hamming_pairs)} frame pairs with ≤10 bit differences")
    print("(These likely have similar plaintext)")
    
    # Pattern Analysis
    print("\n=== Plaintext Pattern Analysis ===")
    xor_patterns = defaultdict(int)
    
    for burst in all_bursts:
        frames = burst['frames']
        # XOR pattern for the burst
        xor01 = frames[0]['vocoder'] ^ frames[1]['vocoder']
        xor02 = frames[0]['vocoder'] ^ frames[2]['vocoder']
        xor12 = frames[1]['vocoder'] ^ frames[2]['vocoder']
        
        # Look for patterns
        pattern = (
            bin(xor01).count('1') // 5,
            bin(xor02).count('1') // 5,
            bin(xor12).count('1') // 5
        )
        xor_patterns[pattern] += 1
    
    print("XOR patterns (hamming weight grouped by 5):")
    for pattern, count in sorted(xor_patterns.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {pattern}: {count} bursts")
    
    # Cross-CMI Analysis
    print("\n=== Cross-CMI Analysis ===")
    print("If two CMIs encrypt the same plaintext with different keys:")
    print("CMI1 ⊕ CMI2 = Keystream1 ⊕ Keystream2")
    
    cmi_pairs = []
    cmis = list(burst_by_cmi.keys())
    
    for i, cmi1 in enumerate(cmis):
        for cmi2 in cmis[i+1:]:
            bursts1 = burst_by_cmi[cmi1]
            bursts2 = burst_by_cmi[cmi2]
            
            # Compare first burst of each CMI
            if bursts1 and bursts2:
                b1 = bursts1[0]['frames']
                b2 = bursts2[0]['frames']
                
                # Compare each frame position
                similarities = []
                for frame_idx in range(3):
                    xor = b1[frame_idx]['vocoder'] ^ b2[frame_idx]['vocoder']
                    hamming = bin(xor).count('1')
                    similarities.append(hamming)
                
                avg_hamming = np.mean(similarities)
                if avg_hamming < 25:  # Potentially related
                    cmi_pairs.append({
                        'cmi1': cmi1,
                        'cmi2': cmi2,
                        'avg_hamming': avg_hamming,
                        'frame_hammings': similarities
                    })
    
    print(f"\nFound {len(cmi_pairs)} CMI pairs with similar patterns")
    for pair in sorted(cmi_pairs, key=lambda x: x['avg_hamming'])[:5]:
        print(f"  {pair['cmi1']} ⟷ {pair['cmi2']}: avg {pair['avg_hamming']:.1f} bits")
        print(f"    Frame differences: {pair['frame_hammings']}")
    
    # Silence Detection
    print("\n=== Silence/Repeated Pattern Detection ===")
    potential_silence = []
    
    for burst in all_bursts:
        frames = burst['frames']
        
        # Check if frames are very similar (repeated pattern)
        xor01 = frames[0]['vocoder'] ^ frames[1]['vocoder']
        xor02 = frames[0]['vocoder'] ^ frames[2]['vocoder']
        
        if bin(xor01).count('1') < 5 and bin(xor02).count('1') < 5:
            potential_silence.append(burst)
    
    print(f"\nFound {len(potential_silence)} bursts with potential silence/repeated patterns")
    
    # Statistical Analysis
    print("\n=== Statistical Analysis ===")
    all_vocoder_values = []
    for burst in all_bursts:
        for frame in burst['frames']:
            all_vocoder_values.append(frame['vocoder'])
    
    # Bit bias analysis
    bit_biases = []
    for bit_pos in range(49):
        ones = sum(1 for v in all_vocoder_values if v & (1 << bit_pos))
        prob = ones / len(all_vocoder_values)
        bias = abs(prob - 0.5)
        bit_biases.append((bit_pos, prob, bias))
    
    print("Most biased bit positions:")
    for pos, prob, bias in sorted(bit_biases, key=lambda x: x[2], reverse=True)[:10]:
        print(f"  Bit {pos}: {prob:.3f} (bias: {bias:.3f})")
    
    # Attack Summary
    print("\n=== Attack Summary ===")
    print(f"1. Analyzed {len(all_bursts)} bursts ({len(all_bursts)*3} frames)")
    print(f"2. Found {len(low_hamming_pairs)} similar frame pairs (potential known plaintext)")
    print(f"3. Identified {len(potential_silence)} silence candidates")
    print(f"4. Cross-CMI analysis reveals {len(cmi_pairs)} related key pairs")
    print("\n5. CRITICAL: Each burst provides 3 encryptions with same IV")
    print("   This triples our attack surface compared to single-frame analysis!")
    
    conn.close()

if __name__ == "__main__":
    db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    analyze_iv_reuse(db_path)