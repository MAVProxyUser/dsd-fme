#!/usr/bin/env python3
"""
DMR LFSR Predictor - Predict next C- MI values
"""

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    # Iterate 32 times as per the C implementation
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

# The discovered interleaving pattern
JUMP_PATTERN = [1,1,1,3,-2,1,3,1,-2,4,-1,2,3,-2,1,4,-2,1,4]

# Generate raw LFSR sequence from H- MI
h_mi = 0x6C8AB637
raw_sequence = []
current = h_mi
for _ in range(50):  # Generate enough values
    current = lfsr_next(current)
    raw_sequence.append(current)

# Last captured value and its position
last_captured = 0x206BF0CF
last_raw_pos = 21  # From our analysis

print("DMR LFSR C- MI Prediction")
print("=========================")
print(f"H- MI (static): 0x{h_mi:08X}")
print(f"Last captured C- MI: 0x{last_captured:08X}")
print(f"Last raw position: {last_raw_pos}")
print()

print("Next 20 predicted C- MI values:")
print("Count | Pattern Jump | Raw Pos | C- MI Value")
print("------|--------------|---------|------------")

current_pos = last_raw_pos
pattern_index = 19 % len(JUMP_PATTERN)  # We had 20 captured values (0-19)

for i in range(20):
    pattern_index = (pattern_index + 1) % len(JUMP_PATTERN)
    jump = JUMP_PATTERN[pattern_index]
    current_pos += jump
    
    # Ensure we have enough raw values
    while current_pos >= len(raw_sequence):
        current = raw_sequence[-1]
        current = lfsr_next(current)
        raw_sequence.append(current)
    
    predicted = raw_sequence[current_pos]
    print(f"{i+1:5d} | {jump:12d} | {current_pos:7d} | 0x{predicted:08X}")

print()
print("Summary:")
print("========")
print("The LFSR uses polynomial: x^32 + x^4 + x^2 + 1")
print("The interleaving pattern is: " + str(JUMP_PATTERN))
print("This pattern repeats every 19 values")
print()
print("With this knowledge, we can predict all future C- MI values!")
print("The combination of:")
print("  1. Fixed H- MI (seed)")
print("  2. Known LFSR polynomial")
print("  3. Discovered interleaving pattern")
print("Makes the encryption completely predictable.")