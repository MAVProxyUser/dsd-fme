#!/usr/bin/env python3
import sqlite3
import numpy as np
from collections import Counter

def analyze_30sec_test():
    conn = sqlite3.connect('dsd_fme.db')
    cursor = conn.cursor()
    
    print("30-Second Silence Analysis")
    print("=" * 40)
    
    # Get all AMBE frames from the test
    cursor.execute("""
        SELECT ambe_hex, timestamp 
        FROM H_6C8AB637_S0 
        ORDER BY id
    """)
    h_frames = cursor.fetchall()
    
    # Get all C- frames
    cursor.execute("SELECT DISTINCT control_mi FROM dmr_correlations ORDER BY id")
    c_mis = [row[0] for row in cursor.fetchall()]
    
    all_frames = []
    for mi in c_mis:
        cursor.execute(f"""
            SELECT ambe_hex, timestamp 
            FROM C_{mi:08X}_S0 
            ORDER BY id
        """)
        all_frames.extend(cursor.fetchall())
    
    print(f"Total frames collected: {len(h_frames) + len(all_frames)}")
    print(f"H- frames: {len(h_frames)}")
    print(f"C- frames: {len(all_frames)}")
    print(f"Unique C- MIs: {len(c_mis)}")
    
    # Analyze bit patterns
    print("\nBit Pattern Analysis:")
    
    # Convert hex to binary for analysis
    bit_patterns = []
    for frame, _ in (h_frames + all_frames):
        binary = bin(int(frame, 16))[2:].zfill(64)[:49]  # AMBE is 49 bits
        bit_patterns.append(binary)
    
    # Bit frequency analysis
    bit_counts = np.zeros(49)
    for pattern in bit_patterns:
        for i, bit in enumerate(pattern[:49]):
            bit_counts[i] += int(bit)
    
    bit_freq = bit_counts / len(bit_patterns)
    
    print(f"Bit position bias (should be ~0.5 for random):")
    biased_positions = []
    for i, freq in enumerate(bit_freq):
        if freq < 0.45 or freq > 0.55:
            biased_positions.append((i, freq))
            print(f"  Position {i:2d}: {freq:.3f} {'(LOW)' if freq < 0.5 else '(HIGH)'}")
    
    # Look for repeated frames
    frame_counter = Counter([f[0] for f in (h_frames + all_frames)])
    repeated = [(frame, count) for frame, count in frame_counter.items() if count > 1]
    
    print(f"\nRepeated frames: {len(repeated)}")
    for frame, count in repeated[:5]:
        print(f"  {frame}: {count} times")
    
    # Hamming distance analysis
    print("\nFrame similarity analysis:")
    distances = []
    for i in range(min(100, len(bit_patterns)-1)):
        dist = sum(a != b for a, b in zip(bit_patterns[i], bit_patterns[i+1]))
        distances.append(dist)
    
    avg_distance = np.mean(distances) if distances else 0
    print(f"Average Hamming distance: {avg_distance:.1f}/49 bits")
    print(f"Min distance: {min(distances) if distances else 0}")
    print(f"Max distance: {max(distances) if distances else 0}")
    
    # Look for patterns in quiet frames
    print("\nPotential silence signatures:")
    
    # Check for frames with many zeros (typical of silence)
    low_energy_frames = []
    for frame, _ in (h_frames + all_frames):
        if frame.count('0') > 40:  # More than 40 zeros in hex
            low_energy_frames.append(frame)
    
    print(f"Low energy frames: {len(low_energy_frames)}")
    if low_energy_frames:
        print(f"Example: {low_energy_frames[0]}")
    
    conn.close()
    
    return {
        'total_frames': len(h_frames) + len(all_frames),
        'biased_positions': biased_positions,
        'repeated_frames': len(repeated),
        'avg_hamming': avg_distance,
        'low_energy_frames': len(low_energy_frames)
    }

if __name__ == "__main__":
    analyze_30sec_test()