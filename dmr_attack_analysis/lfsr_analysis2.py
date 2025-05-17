#!/usr/bin/env python3
"""
DMR LFSR Analysis - Check for pattern in mismatches
"""

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    # Iterate 32 times as per the C implementation
    for _ in range(32):
        # Calculate feedback bit using taps at positions 32, 4, and 2
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        # Shift left and add the new bit
        lfsr = (lfsr << 1) | bit
    
    # Mask to 32 bits
    return lfsr & 0xFFFFFFFF

# Captured C- MI values from the database
captured_values = [
    0xE8083B57,  # First C- MI
    0x4F36EE3A,
    0x752FEA1C,
    0x9A0C201B,
    0x1E3DC9E8,
    0xD3C028BF,
    0xD851670C,
    0x97D76800,
    0xB0E136DB,
    0xBB5FC480,
    0x46CB4902,
    0xF3152FD2,
    0xDC09BDB4,
    0x11E3BB5A,
    0xB9EC6354,
    0xC4856E39,
    0x2BFABF7C,
    0x3D6EEE34,
    0x63BBBB54,
    0x206BF0CF
]

# Generate expected sequence from H- MI
h_mi = 0x6C8AB637
expected = []
current = h_mi
for _ in range(25):
    current = lfsr_next(current)
    expected.append(current)

print("DMR LFSR Pattern Analysis")
print("========================")
print()

# Check if captured values are in the expected sequence
print("Checking if captured values appear in expected sequence:")
captured_found = {}
for i, val in enumerate(captured_values):
    if val in expected:
        idx = expected.index(val)
        captured_found[i] = idx
        print(f"Captured[{i:2d}] = 0x{val:08X} found at Expected[{idx:2d}]")
    else:
        print(f"Captured[{i:2d}] = 0x{val:08X} NOT FOUND in expected")

print("\nPattern analysis:")
# Look for patterns
for i in range(1, len(captured_values)):
    if i in captured_found and i-1 in captured_found:
        diff = captured_found[i] - captured_found[i-1]
        print(f"Jump from position {i-1} to {i}: {diff}")

# Check for pairs/swaps
print("\nChecking for swapped pairs:")
for i in range(0, len(captured_values)-1, 2):
    val1 = captured_values[i]
    val2 = captured_values[i+1]
    
    # Check if val2 appears before val1 in expected
    if val1 in expected and val2 in expected:
        idx1 = expected.index(val1)
        idx2 = expected.index(val2)
        if idx2 < idx1:
            print(f"Swapped pair at {i},{i+1}: 0x{val1:08X} and 0x{val2:08X}")

# Try reverse order for some values
print("\nChecking if values appear in blocks out of order:")
# Group captured values into blocks
block_size = 3
for start in range(0, len(captured_values), block_size):
    block = captured_values[start:start+block_size]
    print(f"\nBlock {start//block_size}: {[f'0x{v:08X}' for v in block]}")
    
    # Check if this block appears reversed in expected
    reversed_block = list(reversed(block))
    for i in range(len(expected) - len(reversed_block) + 1):
        if expected[i:i+len(reversed_block)] == reversed_block:
            print(f"  Found reversed at position {i}")
    
    # Check if block appears in any order
    for i in range(len(expected) - len(block) + 1):
        expected_block = expected[i:i+len(block)]
        if sorted(block) == sorted(expected_block):
            print(f"  Found same values (possibly reordered) at position {i}")
            print(f"    Expected: {[f'0x{v:08X}' for v in expected_block]}")
            print(f"    Captured: {[f'0x{v:08X}' for v in block]}")