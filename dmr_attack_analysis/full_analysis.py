#!/usr/bin/env python3
"""
Complete analysis of DMR LFSR patterns accounting for transmission gaps
Uses numpy for efficient computation
"""
import sqlite3
import numpy as np
from datetime import datetime
from collections import defaultdict
import sys

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    # Iterate 32 times as per the C implementation
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

def generate_lfsr_sequence(seed, length):
    """Generate LFSR sequence of given length"""
    sequence = []
    current = seed
    for _ in range(length):
        current = lfsr_next(current)
        sequence.append(current)
    return np.array(sequence, dtype=np.uint32)

print("Full DMR LFSR Analysis")
print("======================")

# Connect to database and get ALL data
conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Get all correlations with timestamps
query = """
SELECT 
    c.header_mi,
    c.control_mi,
    c.timestamp,
    s.id as superframe_id,
    s.sync_type
FROM dmr_correlations c
LEFT JOIN superframes s ON s.h_mi = c.header_mi AND s.c_mi = c.control_mi
ORDER BY c.timestamp
"""
cursor.execute(query)
results = cursor.fetchall()

print(f"Total correlations in database: {len(results)}")

# Group by header MI
h_mi_groups = defaultdict(list)
for h_mi, c_mi, timestamp, sf_id, sync_type in results:
    h_mi_groups[h_mi].append({
        'c_mi': c_mi,
        'timestamp': datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S'),
        'superframe_id': sf_id,
        'sync_type': sync_type
    })

# Analyze each H-MI group
for h_mi, records in h_mi_groups.items():
    print(f"\nAnalyzing H-MI: 0x{h_mi:08X}")
    print(f"Total records: {len(records)}")
    
    # Sort by timestamp
    records.sort(key=lambda x: x['timestamp'])
    
    # Identify transmission bursts based on time gaps
    bursts = []
    current_burst = []
    last_time = None
    
    for record in records:
        if last_time and (record['timestamp'] - last_time).seconds > 3:
            if current_burst:
                bursts.append(current_burst)
            current_burst = [record]
        else:
            current_burst.append(record)
        last_time = record['timestamp']
    
    if current_burst:
        bursts.append(current_burst)
    
    print(f"Number of transmission bursts: {len(bursts)}")
    
    # Generate LFSR sequence for comparison
    lfsr_sequence = generate_lfsr_sequence(h_mi, 500)
    
    # Create lookup dictionary for fast searching
    lfsr_lookup = {int(val): idx for idx, val in enumerate(lfsr_sequence)}
    
    # Analyze each burst
    for burst_num, burst in enumerate(bursts):
        print(f"\nBurst {burst_num + 1}: {len(burst)} frames")
        print(f"Time: {burst[0]['timestamp']} to {burst[-1]['timestamp']}")
        
        # Get C-MI values for this burst
        c_mi_values = [record['c_mi'] for record in burst]
        
        # Find positions in LFSR sequence
        positions = []
        for c_mi in c_mi_values:
            if c_mi in lfsr_lookup:
                positions.append(lfsr_lookup[c_mi])
            else:
                positions.append(-1)
        
        # Analyze the pattern within this burst
        if len(positions) > 1:
            jumps = []
            for i in range(1, len(positions)):
                if positions[i-1] != -1 and positions[i] != -1:
                    jump = positions[i] - positions[i-1]
                    jumps.append(jump)
            
            # Look for patterns in jumps
            jumps_array = np.array(jumps)
            unique_jumps, counts = np.unique(jumps_array, return_counts=True)
            
            print("Jump distribution:")
            for jump, count in zip(unique_jumps, counts):
                print(f"  Jump {jump:3d}: {count:3d} times ({count/len(jumps)*100:.1f}%)")
            
            # Check for continuous sequences
            continuous_count = np.sum(jumps_array == 1)
            print(f"Continuous sequences (jump=1): {continuous_count}/{len(jumps)} ({continuous_count/len(jumps)*100:.1f}%)")
    
    # Overall pattern analysis across all bursts
    print(f"\nOverall pattern analysis for H-MI 0x{h_mi:08X}:")
    
    all_c_mi = [record['c_mi'] for record in records]
    all_positions = []
    for c_mi in all_c_mi:
        if c_mi in lfsr_lookup:
            all_positions.append(lfsr_lookup[c_mi])
        else:
            all_positions.append(-1)
    
    # Remove -1 values
    valid_positions = [p for p in all_positions if p != -1]
    
    if len(valid_positions) > 1:
        all_jumps = []
        for i in range(1, len(all_positions)):
            if all_positions[i-1] != -1 and all_positions[i] != -1:
                jump = all_positions[i] - all_positions[i-1]
                all_jumps.append(jump)
        
        jumps_array = np.array(all_jumps)
        unique_jumps, counts = np.unique(jumps_array, return_counts=True)
        
        print("\nGlobal jump distribution:")
        # Sort by frequency
        sorted_indices = np.argsort(-counts)
        for idx in sorted_indices[:10]:  # Top 10 most common jumps
            jump = unique_jumps[idx]
            count = counts[idx]
            print(f"  Jump {jump:3d}: {count:3d} times ({count/len(all_jumps)*100:.1f}%)")
    
    # Look for the interleaving pattern
    print("\nSearching for interleaving pattern...")
    
    # Try different pattern lengths
    pattern_found = False
    for pattern_length in range(3, 25):
        if len(all_jumps) < pattern_length * 3:  # Need at least 3 repetitions
            continue
            
        # Check if a pattern repeats
        pattern_matches = 0
        for start in range(len(all_jumps) - pattern_length * 2):
            pattern = all_jumps[start:start + pattern_length]
            next_pattern = all_jumps[start + pattern_length:start + pattern_length * 2]
            
            if pattern == next_pattern:
                pattern_matches += 1
        
        if pattern_matches > 0:
            print(f"Pattern length {pattern_length}: {pattern_matches} matches found")
            if pattern_matches > 5:  # Significant pattern
                # Extract the most common pattern
                patterns = []
                for start in range(0, len(all_jumps) - pattern_length + 1, pattern_length):
                    pattern = tuple(all_jumps[start:start + pattern_length])
                    patterns.append(pattern)
                
                from collections import Counter
                pattern_counts = Counter(patterns)
                most_common_pattern = pattern_counts.most_common(1)[0]
                
                print(f"Most common pattern: {most_common_pattern[0]}")
                print(f"Occurs {most_common_pattern[1]} times")
                pattern_found = True
                break
    
    if not pattern_found:
        print("No consistent repeating pattern found")

# Close database
conn.close()

# Advanced analysis using numpy
print("\n\nAdvanced Pattern Analysis")
print("========================")

# Reopen connection for numpy analysis
conn = sqlite3.connect('dsd_fme.db')

# Get all C-MI values in order
query = """
SELECT control_mi, timestamp 
FROM dmr_correlations 
WHERE header_mi = 1821029943
ORDER BY timestamp
"""
df = np.array(conn.execute(query).fetchall())
conn.close()

c_mi_values = df[:, 0].astype(np.uint32)
timestamps = df[:, 1]

print(f"Total C-MI values: {len(c_mi_values)}")

# Generate large LFSR sequence
h_mi = 0x6C8AB637
lfsr_seq = generate_lfsr_sequence(h_mi, 1000)

# Find all C-MI values in the LFSR sequence
positions = np.array([np.where(lfsr_seq == c_mi)[0][0] if np.any(lfsr_seq == c_mi) else -1 
                     for c_mi in c_mi_values])

# Calculate jumps
valid_mask = (positions[:-1] != -1) & (positions[1:] != -1)
jumps = np.diff(positions)[valid_mask]

print(f"Valid jumps: {len(jumps)}")

# Statistical analysis
print(f"Jump statistics:")
print(f"  Mean: {np.mean(jumps):.2f}")
print(f"  Std: {np.std(jumps):.2f}")
print(f"  Median: {np.median(jumps)}")
print(f"  Mode: {np.bincount(jumps + 10).argmax() - 10}")  # Offset for negative values

# Plot jump distribution if matplotlib is available
try:
    import matplotlib.pyplot as plt
    plt.figure(figsize=(10, 6))
    plt.hist(jumps, bins=50, edgecolor='black')
    plt.xlabel('Jump Size')
    plt.ylabel('Frequency')
    plt.title('DMR LFSR Jump Distribution')
    plt.savefig('jump_distribution.png')
    print("\nJump distribution plot saved as 'jump_distribution.png'")
except ImportError:
    print("\nMatplotlib not available, skipping plot generation")

# Check for cyclic patterns using autocorrelation
print("\nAutocorrelation analysis...")
max_lag = min(100, len(jumps) // 2)
autocorr = np.correlate(jumps - np.mean(jumps), jumps - np.mean(jumps), mode='full')
autocorr = autocorr[len(autocorr)//2:len(autocorr)//2 + max_lag]
autocorr /= autocorr[0]  # Normalize

# Find peaks in autocorrelation
peaks = []
for i in range(1, len(autocorr) - 1):
    if autocorr[i] > autocorr[i-1] and autocorr[i] > autocorr[i+1] and autocorr[i] > 0.3:
        peaks.append(i)

if peaks:
    print(f"Potential pattern periods: {peaks[:5]}")
else:
    print("No significant periodic patterns detected")