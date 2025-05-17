#!/usr/bin/env python3
"""
Analyze continuous sequences within bursts
"""
def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    # Iterate 32 times as per the C implementation
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

# Generate raw LFSR sequence
h_mi = 0x6C8AB637
raw_sequence = []
current = h_mi
for _ in range(300):
    current = lfsr_next(current)
    raw_sequence.append(current)

# Read the captured sequence
with open('c_mi_sequence.txt', 'r') as f:
    captured_values = [int(line.strip()) for line in f if line.strip()]

# Look for continuous sequences where LFSR advances by 1
print("Looking for continuous LFSR sequences:")
print("Start | Length | First Value    | Last Value")
print("------|--------|----------------|----------------")

in_sequence = False
sequence_start = 0
sequence_values = []

for i in range(len(captured_values) - 1):
    current_val = captured_values[i]
    next_val = captured_values[i + 1]
    
    # Find positions in raw sequence
    try:
        current_pos = raw_sequence.index(current_val)
        next_pos = raw_sequence.index(next_val)
        
        if next_pos == current_pos + 1:  # Continuous sequence
            if not in_sequence:
                in_sequence = True
                sequence_start = i
                sequence_values = [current_val]
            sequence_values.append(next_val)
        else:
            if in_sequence:
                # End of sequence
                print(f"{sequence_start:5d} | {len(sequence_values):6d} | 0x{sequence_values[0]:08X} | 0x{sequence_values[-1]:08X}")
                in_sequence = False
    except ValueError:
        if in_sequence:
            print(f"{sequence_start:5d} | {len(sequence_values):6d} | 0x{sequence_values[0]:08X} | 0x{sequence_values[-1]:08X}")
            in_sequence = False

# Final sequence if still in progress
if in_sequence:
    print(f"{sequence_start:5d} | {len(sequence_values):6d} | 0x{sequence_values[0]:08X} | 0x{sequence_values[-1]:08X}")

# Check if there's any consistent pattern
print("\nAnalyzing jump patterns between consecutive values:")
jumps = []
for i in range(len(captured_values) - 1):
    try:
        pos1 = raw_sequence.index(captured_values[i])
        pos2 = raw_sequence.index(captured_values[i + 1])
        jump = pos2 - pos1
        jumps.append(jump)
    except ValueError:
        jumps.append(None)

# Count jump frequencies
from collections import Counter
jump_counts = Counter(j for j in jumps if j is not None)
print("\nMost common jumps:")
for jump, count in jump_counts.most_common(10):
    print(f"Jump {jump:3d}: {count:3d} times")

# Look for repeating patterns in jumps
print("\nLooking for repeating jump patterns:")
pattern_lengths = [3, 4, 5, 6, 7, 8, 9, 10]
for length in pattern_lengths:
    patterns = {}
    for i in range(len(jumps) - length):
        pattern = tuple(jumps[i:i+length])
        if None not in pattern:
            patterns[pattern] = patterns.get(pattern, 0) + 1
    
    # Find most common patterns
    if patterns:
        most_common = max(patterns.items(), key=lambda x: x[1])
        if most_common[1] > 2:  # At least 3 occurrences
            print(f"Length {length}: {most_common[0]} occurs {most_common[1]} times")