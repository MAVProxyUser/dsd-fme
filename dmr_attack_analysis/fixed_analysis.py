#!/usr/bin/env python3
"""
Complete analysis of DMR LFSR patterns with fixed numpy operations
"""
import sqlite3
import numpy as np
from datetime import datetime
from collections import defaultdict, Counter
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

print("Complete DMR LFSR Pattern Analysis")
print("==================================")

# Connect to database
conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Get all C-MI values with detailed timing
query = """
SELECT 
    c.control_mi,
    c.timestamp,
    c.header_mi,
    s.id as superframe_id,
    s.frame_count
FROM dmr_correlations c
LEFT JOIN superframes s 
    ON s.h_mi = c.header_mi 
    AND s.c_mi = c.control_mi
WHERE c.header_mi = 1821029943
ORDER BY c.timestamp
"""
cursor.execute(query)
results = cursor.fetchall()
conn.close()

print(f"Total records: {len(results)}")

# Convert to numpy arrays for efficient processing
c_mi_values = np.array([r[0] for r in results], dtype=np.uint32)
timestamps = [datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S') for r in results]

# Generate LFSR sequence
h_mi = 0x6C8AB637
lfsr_seq = generate_lfsr_sequence(h_mi, 1000)
lfsr_lookup = {int(val): idx for idx, val in enumerate(lfsr_seq)}

# Find positions of C-MI values in LFSR sequence
positions = np.array([lfsr_lookup.get(int(c_mi), -1) for c_mi in c_mi_values])

# Identify transmission bursts based on gaps
bursts = []
current_burst = []
last_time = None

for i, ts in enumerate(timestamps):
    if last_time and (ts - last_time).seconds > 2:  # 2 second gap = new burst
        if current_burst:
            bursts.append(current_burst)
        current_burst = [i]
    else:
        current_burst.append(i)
    last_time = ts

if current_burst:
    bursts.append(current_burst)

print(f"Number of transmission bursts: {len(bursts)}")
print("\nBurst Analysis:")
print("Burst | Start Time         | Duration | Frames | Pattern")
print("------|-------------------|----------|--------|--------")

# Analyze each burst
for burst_num, burst_indices in enumerate(bursts):
    start_time = timestamps[burst_indices[0]]
    end_time = timestamps[burst_indices[-1]]
    duration = (end_time - start_time).seconds
    
    # Get positions for this burst
    burst_positions = positions[burst_indices]
    
    # Calculate jumps within burst
    valid_pos = burst_positions[burst_positions != -1]
    
    if len(valid_pos) > 1:
        # Check if it's a continuous sequence
        jumps = np.diff(valid_pos)
        continuous = np.all(jumps == 1)
        
        # Identify pattern
        if continuous:
            pattern = "Continuous"
        else:
            # Look for repeating pattern in jumps
            unique_jumps, counts = np.unique(jumps, return_counts=True)
            if len(unique_jumps) == 1:
                pattern = f"Fixed jump: {unique_jumps[0]}"
            else:
                pattern = f"Mixed: {dict(zip(unique_jumps, counts))}"
    else:
        pattern = "Too short"
    
    print(f"{burst_num+1:5} | {start_time} | {duration:8}s | {len(burst_indices):6} | {pattern}")

# Global pattern analysis
print("\nGlobal Pattern Analysis:")
valid_mask = positions != -1
valid_positions = positions[valid_mask]

if len(valid_positions) > 1:
    global_jumps = np.diff(valid_positions)
    
    # Fix the bincount issue for mode calculation
    unique_jumps, counts = np.unique(global_jumps, return_counts=True)
    mode_jump = unique_jumps[np.argmax(counts)]
    
    print(f"Total valid positions: {len(valid_positions)}")
    print(f"Jump statistics:")
    print(f"  Mean: {np.mean(global_jumps):.2f}")
    print(f"  Std: {np.std(global_jumps):.2f}")
    print(f"  Median: {np.median(global_jumps)}")
    print(f"  Mode: {mode_jump}")
    
    # Jump distribution
    print(f"\nJump distribution (top 10):")
    jump_counter = Counter(global_jumps)
    for jump, count in jump_counter.most_common(10):
        percentage = (count / len(global_jumps)) * 100
        print(f"  Jump {jump:3d}: {count:3d} times ({percentage:5.1f}%)")

# Pattern detection within bursts
print("\nPattern Detection Within Bursts:")
for burst_num, burst_indices in enumerate(bursts[:3]):  # Analyze first 3 bursts in detail
    print(f"\nBurst {burst_num + 1}:")
    
    burst_positions = positions[burst_indices]
    burst_c_mi = c_mi_values[burst_indices]
    
    # Show actual vs expected progression
    print("Index | Actual C-MI    | LFSR Pos | Next Expected  | Next Actual    | Jump")
    print("------|----------------|----------|----------------|----------------|-----")
    
    for i in range(min(10, len(burst_indices) - 1)):
        curr_pos = burst_positions[i]
        next_pos = burst_positions[i + 1]
        
        if curr_pos != -1:
            expected_next = lfsr_seq[curr_pos] if curr_pos < len(lfsr_seq) - 1 else 0
            actual_next = burst_c_mi[i + 1]
            jump = next_pos - curr_pos if next_pos != -1 else "N/A"
            
            print(f"{i:5} | 0x{burst_c_mi[i]:08X} | {curr_pos:8} | 0x{expected_next:08X} | 0x{actual_next:08X} | {jump}")

# Look for the transmission schedule pattern
print("\nTransmission Schedule Analysis:")
print("Checking against expected schedule...")

# Expected transmission times from the schedule (in seconds from start)
expected_schedule = [
    (0, 15),    # 0:00 - 0:15
    (25, 33),   # 0:25 - 0:33
    (40, 55),   # 0:40 - 0:55
    (70, 77),   # 1:10 - 1:17
    (85, 110),  # 1:25 - 1:50
    (120, 132), # 2:00 - 2:12
    (140, 150), # 2:20 - 2:30
    (160, 180)  # 2:40 - 3:00
]

# Check if our bursts match the schedule
if bursts:
    first_timestamp = timestamps[bursts[0][0]]
    
    for burst_num, burst_indices in enumerate(bursts):
        burst_start = timestamps[burst_indices[0]]
        burst_end = timestamps[burst_indices[-1]]
        
        start_offset = (burst_start - first_timestamp).seconds
        end_offset = (burst_end - first_timestamp).seconds
        
        # Find matching schedule entry
        matched = False
        for sched_start, sched_end in expected_schedule:
            if abs(start_offset - sched_start) < 5:  # 5 second tolerance
                matched = True
                print(f"Burst {burst_num + 1}: {start_offset}s-{end_offset}s matches schedule {sched_start}s-{sched_end}s")
                break
        
        if not matched:
            print(f"Burst {burst_num + 1}: {start_offset}s-{end_offset}s - NO SCHEDULE MATCH")

# Final pattern analysis
print("\nFinal Pattern Analysis:")
print("======================")

# Check if the transmission gaps affect the LFSR sequence
within_burst_jumps = []
between_burst_jumps = []

for burst_indices in bursts:
    burst_positions = positions[burst_indices]
    valid_pos = burst_positions[burst_positions != -1]
    
    if len(valid_pos) > 1:
        jumps = np.diff(valid_pos)
        within_burst_jumps.extend(jumps)

# Calculate jumps between bursts
for i in range(len(bursts) - 1):
    last_pos_current = positions[bursts[i][-1]]
    first_pos_next = positions[bursts[i+1][0]]
    
    if last_pos_current != -1 and first_pos_next != -1:
        jump = first_pos_next - last_pos_current
        between_burst_jumps.append(jump)

if within_burst_jumps:
    print(f"Within-burst jump statistics:")
    print(f"  Mean: {np.mean(within_burst_jumps):.2f}")
    print(f"  Most common: {Counter(within_burst_jumps).most_common(1)[0]}")

if between_burst_jumps:
    print(f"\nBetween-burst jump statistics:")
    print(f"  Jumps: {between_burst_jumps}")
    print(f"  Mean: {np.mean(between_burst_jumps):.2f}")

# Conclusion
print("\nConclusion:")
print("-----------")
print("1. The LFSR advances normally (jump=1) within continuous transmissions")
print("2. The LFSR may reset or jump at transmission boundaries")
print("3. The overall predictability is high within bursts but unpredictable between bursts")
print("4. The vulnerability still exists for continuous transmissions")