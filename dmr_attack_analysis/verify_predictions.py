#!/usr/bin/env python3
"""
Verify LFSR predictions against actual captured data
"""

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    # Iterate 32 times as per the C implementation
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

# Read captured C- MI values
with open('c_mi_sequence.txt', 'r') as f:
    captured_values = [int(line.strip()) for line in f if line.strip()]

print(f"Total captured C- MI values: {len(captured_values)}")
print()

# Convert to hex for display
print("First 20 captured C- MI values:")
for i in range(min(20, len(captured_values))):
    print(f"{i+1:3d}: 0x{captured_values[i]:08X}")

# The discovered interleaving pattern
JUMP_PATTERN = [1,1,1,3,-2,1,3,1,-2,4,-1,2,3,-2,1,4,-2,1,4]

# Generate raw LFSR sequence from H- MI
h_mi = 0x6C8AB637  # Same as before
raw_sequence = []
current = h_mi
for _ in range(200):  # Generate plenty of values
    current = lfsr_next(current)
    raw_sequence.append(current)

# Now let's predict based on our pattern
# First, find where we are in the sequence
first_captured = captured_values[0]
print(f"\nFirst captured: 0x{first_captured:08X}")

# Find this in our raw sequence
try:
    first_pos = raw_sequence.index(first_captured)
    print(f"Found at raw position: {first_pos}")
except ValueError:
    print("Not found in raw sequence!")
    exit(1)

# Now predict and verify
print("\nVerifying predictions:")
print("Index | Predicted      | Actual         | Match | Jump")
print("------|----------------|----------------|-------|-----")

matches = 0
current_pos = first_pos
pattern_index = 0

for i in range(min(50, len(captured_values))):
    predicted = raw_sequence[current_pos]
    actual = captured_values[i]
    match = "YES" if predicted == actual else "NO"
    
    if predicted == actual:
        matches += 1
    
    # For next iteration
    if i < len(captured_values) - 1:
        jump = JUMP_PATTERN[pattern_index % len(JUMP_PATTERN)]
        print(f"{i:5d} | 0x{predicted:08X} | 0x{actual:08X} | {match:3s} | {jump:4d}")
        current_pos += jump
        pattern_index += 1
    else:
        print(f"{i:5d} | 0x{predicted:08X} | 0x{actual:08X} | {match:3s} |    -")

accuracy = (matches / min(50, len(captured_values))) * 100
print(f"\nAccuracy: {matches}/{min(50, len(captured_values))} = {accuracy:.1f}%")

# Look for gaps in the sequence (where transmissions stopped/started)
print("\nChecking for sequence gaps:")
for i in range(1, min(50, len(captured_values))):
    actual_current = captured_values[i]
    actual_prev = captured_values[i-1]
    
    # Find positions in raw sequence
    try:
        pos_current = raw_sequence.index(actual_current)
        pos_prev = raw_sequence.index(actual_prev)
        raw_gap = pos_current - pos_prev
        
        # Expected gap based on pattern
        pattern_idx = (i-1) % len(JUMP_PATTERN)
        expected_gap = JUMP_PATTERN[pattern_idx]
        
        if raw_gap != expected_gap:
            print(f"Gap at {i}: Expected {expected_gap}, Actual {raw_gap} (TX may have stopped/started)")
    except ValueError:
        print(f"Could not find position for value at index {i}")