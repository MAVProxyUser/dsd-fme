#!/usr/bin/env python3
"""
DMR LFSR Final Analysis - Understanding the exact pattern
"""

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    # Iterate 32 times as per the C implementation
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

# Captured sequence
captured = [
    0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0x1E3DC9E8, 0xD3C028BF,
    0xD851670C, 0x97D76800, 0xB0E136DB, 0xBB5FC480, 0x46CB4902, 0xF3152FD2,
    0xDC09BDB4, 0x11E3BB5A, 0xB9EC6354, 0xC4856E39, 0x2BFABF7C, 0x3D6EEE34,
    0x63BBBB54, 0x206BF0CF
]

# Generate expected raw sequence
h_mi = 0x6C8AB637
raw = []
current = h_mi
for _ in range(30):
    current = lfsr_next(current)
    raw.append(current)

print("Mapping captured to raw sequence positions:")
print("Captured Pos | Raw Pos | Value")
print("-------------|---------|----------")

# Map captured positions to raw positions
mapping = []
for i, val in enumerate(captured):
    if val in raw:
        raw_pos = raw.index(val)
        mapping.append((i, raw_pos))
        print(f"{i:12d} | {raw_pos:7d} | 0x{val:08X}")

# Analyze the pattern
print("\nPattern analysis:")
print("Captured group | Raw positions")
print("---------------|---------------")

# Group by 3s to see pattern
for i in range(0, len(mapping), 3):
    group = mapping[i:i+3]
    captured_pos = [x[0] for x in group]
    raw_pos = [x[1] for x in group]
    print(f"{captured_pos} | {raw_pos}")

# Look for the mathematical relationship
print("\nIdentifying the transformation pattern:")
for i in range(1, len(mapping)):
    c_diff = mapping[i][0] - mapping[i-1][0]  # Always 1
    r_diff = mapping[i][1] - mapping[i-1][1]
    print(f"C[{mapping[i-1][0]}]->C[{mapping[i][0]}] (diff:{c_diff}) maps to R[{mapping[i-1][1]}]->R[{mapping[i][1]}] (diff:{r_diff})")

# Based on analysis, the pattern seems to be:
# Groups of 6: positions [0,1,2,3,4,5] in raw become [0,1,2,5,3,4] in captured
# But with position 4 and 5 swapped, then 3 shifted

print("\nPredicting next values based on pattern:")
last_captured_val = captured[-1]
last_raw_pos = raw.index(last_captured_val)

print(f"Last captured: 0x{last_captured_val:08X} at raw position {last_raw_pos}")
print()

# The pattern shows jumps of: +1,+1,+1,+3,-2,+1,+3,+1,-2,+4,-1,+2,+3,-2,+1,+4,-2,+1,+4
# This suggests a complex but deterministic interleaving

# Continue the pattern
jump_pattern = [1,1,1,3,-2,1,3,1,-2,4,-1,2,3,-2,1,4,-2,1,4]
current_pos = last_raw_pos

print("Predicted next 10 C- MI values:")
print("Index | Raw Pos | Predicted C- MI")
print("------|---------|----------------")

for i in range(10):
    # Use the jump pattern cyclically
    jump = jump_pattern[len(captured) % len(jump_pattern)]
    current_pos += jump
    
    if current_pos < len(raw):
        predicted = raw[current_pos]
    else:
        # Generate new values if needed
        while len(raw) <= current_pos:
            current = raw[-1]
            current = lfsr_next(current)
            raw.append(current)
        predicted = raw[current_pos]
    
    print(f"{i+1:5d} | {current_pos:7d} | 0x{predicted:08X}")
    
    # Add to pattern for next iteration
    captured.append(predicted)