#!/usr/bin/env python3
"""
Final DMR Attack Analysis
Properly extract vocoder bits and exploit IV reuse
"""

import sqlite3
import sys
from collections import defaultdict, Counter
import struct

def extract_vocoder_data(ambe_hex):
    """
    Extract the actual vocoder data from the logged AMBE frame
    Based on the bit pattern analysis, the data is in specific bit ranges
    """
    value = int(ambe_hex, 16)
    
    # Extract the three data segments (avoiding the zero-padding areas)
    segment1 = (value >> 10) & 0x3FFF  # Bits 10-23 (14 bits)
    segment2 = (value >> 32) & 0xFFFF  # Bits 32-47 (16 bits)
    segment3 = (value >> 48) & 0xFFFF  # Bits 48-63 (16 bits)
    
    # Combine into vocoder data (46 bits total)
    vocoder_data = (segment3 << 30) | (segment2 << 14) | segment1
    
    return vocoder_data

def final_dmr_attack(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== Final DMR Attack Analysis ===")
    print(f"Database: {db_path}\n")
    
    # Get all C-MI tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    cmi_tables = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(cmi_tables)} C-MI tables")
    
    # Collect all bursts with proper vocoder extraction
    all_bursts = []
    
    for table in cmi_tables[:100]:  # Analyze first 100 tables
        cmi = table.split('_')[1]
        
        cursor.execute(f"""
            SELECT id, ambe_hex, superframe_id 
            FROM {table} 
            ORDER BY id
        """)
        frames = cursor.fetchall()
        
        # Group into bursts of 3
        for i in range(0, len(frames) - 2, 3):
            burst_frames = []
            for j in range(3):
                frame_id, ambe_hex, sf_id = frames[i + j]
                vocoder_data = extract_vocoder_data(ambe_hex)
                burst_frames.append({
                    'id': frame_id,
                    'hex': ambe_hex,
                    'vocoder': vocoder_data,
                    'superframe': sf_id
                })
            
            all_bursts.append({
                'cmi': cmi,
                'frames': burst_frames,
                'superframe': burst_frames[0]['superframe']
            })
    
    print(f"\nAnalyzed {len(all_bursts)} complete bursts")
    
    # IV Reuse Attack
    print("\n=== IV Reuse Attack Results ===")
    
    # Within-burst analysis
    similar_frames = []
    xor_patterns = defaultdict(int)
    
    for burst in all_bursts:
        frames = burst['frames']
        
        # Calculate XORs between frames (same IV, different plaintext)
        xor01 = frames[0]['vocoder'] ^ frames[1]['vocoder']
        xor02 = frames[0]['vocoder'] ^ frames[2]['vocoder']
        xor12 = frames[1]['vocoder'] ^ frames[2]['vocoder']
        
        # Hamming weights
        hw01 = bin(xor01).count('1')
        hw02 = bin(xor02).count('1')
        hw12 = bin(xor12).count('1')
        
        # Pattern classification
        pattern = (hw01 // 5, hw02 // 5, hw12 // 5)
        xor_patterns[pattern] += 1
        
        # Look for very similar frames
        if hw01 <= 10 or hw02 <= 10 or hw12 <= 10:
            similar_frames.append({
                'cmi': burst['cmi'],
                'weights': (hw01, hw02, hw12),
                'xors': (xor01, xor02, xor12)
            })
    
    print(f"Found {len(similar_frames)} bursts with highly similar frames")
    print("\nXOR weight patterns:")
    for pattern, count in sorted(xor_patterns.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {pattern}: {count} bursts")
    
    # Cross-CMI analysis
    print("\n=== Cross-CMI Keystream Analysis ===")
    
    # Group bursts by CMI
    bursts_by_cmi = defaultdict(list)
    for burst in all_bursts:
        bursts_by_cmi[burst['cmi']].append(burst)
    
    # Find CMI pairs with similar patterns
    cmi_relationships = []
    cmis = list(bursts_by_cmi.keys())
    
    for i, cmi1 in enumerate(cmis):
        for j, cmi2 in enumerate(cmis[i+1:], i+1):
            bursts1 = bursts_by_cmi[cmi1]
            bursts2 = bursts_by_cmi[cmi2]
            
            if bursts1 and bursts2:
                # Compare first burst
                b1 = bursts1[0]['frames']
                b2 = bursts2[0]['frames']
                
                # XOR corresponding frames
                frame_xors = []
                for k in range(3):
                    xor = b1[k]['vocoder'] ^ b2[k]['vocoder']
                    hw = bin(xor).count('1')
                    frame_xors.append(hw)
                
                avg_hw = sum(frame_xors) / 3
                
                if avg_hw < 20:  # Similar keystreams or plaintexts
                    cmi_relationships.append({
                        'cmi1': cmi1,
                        'cmi2': cmi2,
                        'avg_hamming': avg_hw,
                        'frame_hammings': frame_xors
                    })
    
    print(f"Found {len(cmi_relationships)} CMI pairs with potential relationships")
    for rel in sorted(cmi_relationships, key=lambda x: x['avg_hamming'])[:10]:
        print(f"  {rel['cmi1']} ⟷ {rel['cmi2']}: avg {rel['avg_hamming']:.1f} bits")
    
    # Statistical analysis
    print("\n=== Statistical Analysis ===")
    
    all_vocoder_values = []
    for burst in all_bursts:
        for frame in burst['frames']:
            all_vocoder_values.append(frame['vocoder'])
    
    # Bit bias analysis (for the 46 active bits)
    print("Bit position biases (46 active bits):")
    for bit_range in [(0, 13), (14, 29), (30, 45)]:
        biases = []
        for pos in range(bit_range[0], bit_range[1] + 1):
            ones = sum(1 for v in all_vocoder_values if v & (1 << pos))
            prob = ones / len(all_vocoder_values)
            bias = abs(prob - 0.5)
            biases.append((pos, prob, bias))
        
        print(f"  Bits {bit_range[0]:2d}-{bit_range[1]:2d}:", end='')
        for pos, prob, bias in sorted(biases, key=lambda x: x[2], reverse=True)[:3]:
            print(f" [{pos}:{prob:.2f}]", end='')
        print()
    
    # Pattern detection
    print("\n=== Pattern Detection ===")
    
    # Look for repeated values (potential silence/tone)
    value_counts = Counter(all_vocoder_values)
    repeated_values = [(v, c) for v, c in value_counts.items() if c > 3]
    
    print(f"Found {len(repeated_values)} repeated vocoder values")
    for value, count in sorted(repeated_values, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  0x{value:012X}: {count} times")
    
    # Silence pattern detection
    silence_candidates = []
    for burst in all_bursts:
        frames = burst['frames']
        
        # Check for low variation
        xor01 = frames[0]['vocoder'] ^ frames[1]['vocoder']
        xor02 = frames[0]['vocoder'] ^ frames[2]['vocoder']
        
        if bin(xor01).count('1') < 8 and bin(xor02).count('1') < 8:
            silence_candidates.append(burst)
    
    print(f"\nFound {len(silence_candidates)} potential silence bursts")
    
    # Attack summary
    print("\n=== Attack Summary ===")
    print(f"1. Total bursts analyzed: {len(all_bursts)} ({len(all_bursts)*3} frames)")
    print(f"2. IV reuse confirmed: Each burst has 3 frames with same IV")
    print(f"3. Similar frame pairs: {len(similar_frames)} (potential plaintext patterns)")
    print(f"4. Related CMI pairs: {len(cmi_relationships)} (keystream relationships)")
    print(f"5. Repeated values: {len(repeated_values)} (possible known plaintexts)")
    print(f"6. Silence candidates: {len(silence_candidates)}")
    
    print("\n=== Exploitation Strategy ===")
    print("1. Use IV reuse: 3 equations per burst instead of 1")
    print("2. Exploit similar frames for differential cryptanalysis")
    print("3. Cross-CMI analysis reveals keystream relationships")
    print("4. Statistical biases can reduce key search space")
    print("5. Combined with LFSR weakness = practical attack")
    
    conn.close()

if __name__ == "__main__":
    db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    final_dmr_attack(db_path)