#!/usr/bin/env python3
import sqlite3
import numpy as np
from collections import Counter

def analyze_30sec_test():
    conn = sqlite3.connect('dsd_fme.db')
    cursor = conn.cursor()
    
    print("30-Second Silence Analysis")
    print("=" * 40)
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    c_tables = [row[0] for row in cursor.fetchall()]
    
    print(f"C- tables found: {len(c_tables)}")
    
    # Collect all AMBE frames
    all_frames = []
    frame_count_by_table = {}
    
    for table in c_tables:
        cursor.execute(f"SELECT ambe_hex, timestamp FROM {table} ORDER BY id")
        frames = cursor.fetchall()
        all_frames.extend(frames)
        frame_count_by_table[table] = len(frames)
    
    total_frames = len(all_frames)
    print(f"Total AMBE frames collected: {total_frames}")
    print(f"Average frames per MI: {total_frames/len(c_tables):.1f}")
    
    # Expected vs actual
    expected_frames = 1500  # 30 seconds worth
    print(f"Expected frames (30s): ~{expected_frames}")
    print(f"Collection efficiency: {total_frames/expected_frames*100:.1f}%")
    
    # Analyze bit patterns
    print("\nBit Pattern Analysis:")
    
    # Convert hex to binary
    bit_patterns = []
    for frame, _ in all_frames:
        try:
            # Handle 64-bit hex strings
            binary = bin(int(frame, 16))[2:].zfill(64)[:49]  # AMBE is 49 bits
            bit_patterns.append(binary)
        except:
            continue
    
    if bit_patterns:
        # Bit frequency analysis
        bit_counts = np.zeros(49)
        for pattern in bit_patterns[:1000]:  # Sample first 1000 to avoid memory issues
            for i, bit in enumerate(pattern[:49]):
                bit_counts[i] += int(bit)
        
        bit_freq = bit_counts / min(len(bit_patterns), 1000)
        
        print(f"Bit position bias (should be ~0.5 for true random):")
        biased_positions = []
        extreme_biases = []
        for i, freq in enumerate(bit_freq):
            if freq < 0.45 or freq > 0.55:
                biased_positions.append((i, freq))
                if freq < 0.35 or freq > 0.65:
                    extreme_biases.append((i, freq))
        
        print(f"  Biased positions (outside 0.45-0.55): {len(biased_positions)}/49")
        print(f"  Extreme biases (outside 0.35-0.65): {len(extreme_biases)}/49")
        
        if extreme_biases:
            print("  Extreme bias examples:")
            for pos, freq in extreme_biases[:5]:
                print(f"    Position {pos:2d}: {freq:.3f}")
    
    # Look for repeated frames
    frame_counter = Counter([f[0] for f in all_frames])
    repeated = [(frame, count) for frame, count in frame_counter.items() if count > 1]
    
    print(f"\nRepeated frames: {len(repeated)}")
    if repeated:
        repeated.sort(key=lambda x: x[1], reverse=True)
        print("  Most repeated:")
        for frame, count in repeated[:5]:
            print(f"    {frame}: {count} times")
    
    # MI analysis
    print("\nMI Analysis:")
    mi_values = []
    for table in c_tables:
        mi_hex = table.split('_')[1]
        mi_values.append(int(mi_hex, 16))
    
    print(f"  Total unique MIs: {len(mi_values)}")
    print(f"  MI value range: {min(mi_values):08X} - {max(mi_values):08X}")
    
    # Check for patterns in MI sequence
    mi_diffs = []
    for i in range(len(mi_values)-1):
        diff = (mi_values[i+1] - mi_values[i]) & 0xFFFFFFFF
        mi_diffs.append(diff)
    
    if mi_diffs:
        print(f"  Average MI step: {np.mean(mi_diffs):.0f}")
        print(f"  MI step variance: {np.std(mi_diffs):.0f}")
    
    # Look for low-energy frames (potential silence)
    print("\nPotential silence patterns:")
    low_energy = []
    high_zero = []
    
    for frame, _ in all_frames[:1000]:  # Sample
        zero_count = frame.count('0')
        if zero_count > 32:  # More than half zeros
            high_zero.append((frame, zero_count))
        if frame[:8] == '00000000':  # First 32 bits all zero
            low_energy.append(frame)
    
    print(f"  Frames with >50% zeros: {len(high_zero)}")
    print(f"  Frames starting with 00000000: {len(low_energy)}")
    
    if high_zero:
        high_zero.sort(key=lambda x: x[1], reverse=True)
        print("  Highest zero count frames:")
        for frame, zeros in high_zero[:3]:
            print(f"    {frame}: {zeros} zeros")
    
    conn.close()
    
    return {
        'total_frames': total_frames,
        'unique_mis': len(c_tables),
        'repeated_frames': len(repeated),
        'high_zero_frames': len(high_zero)
    }

if __name__ == "__main__":
    results = analyze_30sec_test()
    
    print("\nSummary:")
    print(f"  Captured {results['total_frames']} frames across {results['unique_mis']} MIs")
    print(f"  Found {results['repeated_frames']} repeated AMBE patterns")
    print(f"  Found {results['high_zero_frames']} potential silence frames")
    
    print("\nRC4 Attack Feasibility:")
    if results['repeated_frames'] > 10:
        print("  ✓ Some repeated patterns found - potential for correlation")
    else:
        print("  ✗ Few repeated patterns - limited correlation opportunity")
    
    if results['high_zero_frames'] > 50:
        print("  ✓ Many low-energy frames - potential silence signatures")
    else:
        print("  ✗ Few low-energy frames - silence not distinctive")
    
    print(f"\nNext steps:")
    print("  1. Collect more samples (need ~100k+ frames)")
    print("  2. Test with known patterns (roger beep)")
    print("  3. Analyze MI evolution predictability")
    print("  4. Correlate with RF timing patterns")