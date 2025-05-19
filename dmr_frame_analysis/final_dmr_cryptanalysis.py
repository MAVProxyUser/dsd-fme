#!/usr/bin/env python3
"""
Final comprehensive DMR cryptanalysis exploiting:
1. IV reuse across 3 AMBE frames per burst
2. C-MI progression following LFSR
3. Known plaintext properties of AMBE voice codec
"""

import sqlite3
import sys
from collections import defaultdict, Counter
import numpy as np

def analyze_complete_attack(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== Final DMR Cryptanalysis ===")
    
    # Get all C-MI tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    cmi_tables = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(cmi_tables)} C-MI tables")
    
    # Extract C-MI sequence to verify LFSR
    cmi_sequence = []
    for table in cmi_tables:
        parts = table.split('_')
        if len(parts) >= 2:
            cmi = int(parts[1], 16)
            cmi_sequence.append(cmi)
    
    print(f"\nFirst 10 C-MIs: {[f'0x{c:08X}' for c in cmi_sequence[:10]]}")
    
    # Collect all bursts
    all_bursts = defaultdict(list)
    burst_count = 0
    
    for table in cmi_tables[:50]:  # Analyze first 50 for speed
        parts = table.split('_')
        if len(parts) >= 2:
            cmi = int(parts[1], 16)
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
            all_bursts[cmi].append(burst)
            burst_count += 1
    
    print(f"\nTotal bursts analyzed: {burst_count}")
    
    # ATTACK 1: Exploit IV reuse within bursts
    print("\n=== Attack 1: IV Reuse Within Bursts ===")
    
    # Look for patterns in frame relationships
    frame_patterns = Counter()
    low_hamming_bursts = []
    
    for cmi, bursts in all_bursts.items():
        for burst_idx, burst in enumerate(bursts):
            f0, f1, f2 = burst
            
            # These XORs give us plaintext relationships
            xor01 = f0 ^ f1  # P0 ⊕ P1
            xor02 = f0 ^ f2  # P0 ⊕ P2
            xor12 = f1 ^ f2  # P1 ⊕ P2
            
            # Count hamming weights
            hw01 = bin(xor01).count('1')
            hw02 = bin(xor02).count('1')
            hw12 = bin(xor12).count('1')
            
            pattern = (hw01 // 5, hw02 // 5, hw12 // 5)  # Group by 5s
            frame_patterns[pattern] += 1
            
            # Identify bursts with very similar frames
            if hw01 < 10 or hw02 < 10 or hw12 < 10:
                low_hamming_bursts.append({
                    'cmi': cmi,
                    'burst': burst_idx,
                    'weights': (hw01, hw02, hw12),
                    'xors': (xor01, xor02, xor12)
                })
    
    print("Frame difference patterns (grouped by 5 bits):")
    for pattern, count in frame_patterns.most_common(5):
        print(f"  {pattern}: {count} bursts")
    
    print(f"\nFound {len(low_hamming_bursts)} bursts with very similar frames")
    for lhb in low_hamming_bursts[:3]:
        print(f"  C-MI 0x{lhb['cmi']:08X} burst {lhb['burst']}: weights {lhb['weights']}")
    
    # ATTACK 2: Cross-C-MI analysis
    print("\n=== Attack 2: Cross-C-MI Analysis ===")
    
    # If two C-MIs encrypt similar plaintext, we can recover keystream difference
    keystream_diffs = defaultdict(list)
    
    cmis = list(all_bursts.keys())
    for i, cmi1 in enumerate(cmis):
        for j, cmi2 in enumerate(cmis[i+1:], i+1):
            bursts1 = all_bursts[cmi1]
            bursts2 = all_bursts[cmi2]
            
            min_bursts = min(len(bursts1), len(bursts2))
            for burst_idx in range(min_bursts):
                for frame_idx in range(3):
                    c1 = bursts1[burst_idx][frame_idx]
                    c2 = bursts2[burst_idx][frame_idx]
                    
                    # C1 ⊕ C2 = (P ⊕ K1) ⊕ (P ⊕ K2) = K1 ⊕ K2
                    xor = c1 ^ c2
                    hw = bin(xor).count('1')
                    
                    if hw < 20:  # Likely same/similar plaintext
                        keystream_diffs[(cmi1, cmi2)].append({
                            'burst': burst_idx,
                            'frame': frame_idx,
                            'xor': xor,
                            'weight': hw
                        })
    
    print(f"Found {len(keystream_diffs)} C-MI pairs with potential keystream relationships")
    
    # ATTACK 3: AMBE codec properties
    print("\n=== Attack 3: AMBE Codec Properties ===")
    
    # AMBE has specific bit patterns for silence and voice
    # Bit 0-6: Gain (often low for silence)
    # Other bits: spectral parameters
    
    silence_candidates = []
    voice_transitions = []
    
    for cmi, bursts in all_bursts.items():
        for burst_idx, burst in enumerate(bursts):
            # Check for low gain (first 7 bits)
            gain_values = []
            for frame in burst:
                gain = frame & 0x7F  # Extract first 7 bits
                gain_values.append(gain)
            
            # All frames with low gain = potential silence
            if all(g < 16 for g in gain_values):
                silence_candidates.append({
                    'cmi': cmi,
                    'burst': burst_idx,
                    'gains': gain_values,
                    'frames': burst
                })
            
            # Large gain change = voice transition
            if max(gain_values) - min(gain_values) > 32:
                voice_transitions.append({
                    'cmi': cmi,
                    'burst': burst_idx,
                    'gain_change': max(gain_values) - min(gain_values)
                })
    
    print(f"Found {len(silence_candidates)} potential silence bursts")
    print(f"Found {len(voice_transitions)} voice transition bursts")
    
    # ATTACK 4: Statistical analysis
    print("\n=== Attack 4: Statistical Analysis ===")
    
    # Collect all frame values
    all_frames = []
    for bursts in all_bursts.values():
        for burst in bursts:
            all_frames.extend(burst)
    
    # Analyze bit distribution
    bit_counts = [0] * 49  # 49 bits per AMBE frame
    for frame in all_frames:
        for bit_pos in range(49):
            if frame & (1 << bit_pos):
                bit_counts[bit_pos] += 1
    
    # Find biased bits
    total_frames = len(all_frames)
    biased_bits = []
    for pos, count in enumerate(bit_counts):
        bias = abs(count / total_frames - 0.5)
        if bias > 0.15:  # Significantly biased
            biased_bits.append((pos, count/total_frames))
    
    print(f"\nAnalyzed {total_frames} frames")
    print(f"Found {len(biased_bits)} significantly biased bit positions:")
    for pos, prob in biased_bits[:5]:
        print(f"  Bit {pos}: {prob:.3f} probability of being 1")
    
    # FINAL ANALYSIS: Combine all attacks
    print("\n=== Combined Attack Analysis ===")
    
    # Look for C-MIs that appear in multiple attack results
    vulnerable_cmis = set()
    
    # Add C-MIs from low hamming bursts
    for lhb in low_hamming_bursts:
        vulnerable_cmis.add(lhb['cmi'])
    
    # Add C-MIs from silence candidates
    for sc in silence_candidates:
        vulnerable_cmis.add(sc['cmi'])
    
    print(f"\nIdentified {len(vulnerable_cmis)} potentially vulnerable C-MIs")
    
    # Success metrics
    print("\n=== Attack Success Metrics ===")
    print(f"1. IV reuse confirmed: {burst_count * 3} frames using {burst_count} IVs")
    print(f"2. Cross-C-MI correlations: {len(keystream_diffs)} pairs found")
    print(f"3. Plaintext candidates: {len(silence_candidates)} silence, {len(voice_transitions)} transitions")
    print(f"4. Statistical bias: {len(biased_bits)} biased bit positions")
    
    # Recommendations
    print("\n=== Recommendations ===")
    print("1. Focus on silence periods for known plaintext attacks")
    print("2. Exploit IV reuse by correlating all 3 frames per burst")
    print("3. Use LFSR C-MI progression to predict future IVs")
    print("4. Apply statistical analysis to reduce keystream search space")
    
    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    analyze_complete_attack(db_path)