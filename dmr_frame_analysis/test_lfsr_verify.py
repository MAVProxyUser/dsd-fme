#!/usr/bin/env python3
"""Test LFSR predictions on short capture data"""

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

# Data from our short capture
h_mi = 1821029943  # 0x6C8AB637 - the fixed value
c_mi_values = [
    3892853591,  # 0xE8083B57
    1328999994,  # 0x4F36EE3A  
    1966074396,  # 0x752FEA1C
    2584485915,  # 0x9A0C201B
    3552585919,  # 0xD3C028BF
    3629213452,  # 0xD851670C
    507365864,   # 0x1E3DC9E8
    3143615616   # 0xBB5FC480
]

print("Testing LFSR predictions on short capture data:")
print(f"Fixed H-MI: 0x{h_mi:08X}")
print("\nC-MI Sequence:")

current = h_mi
matches = 0
total = len(c_mi_values)

for i, actual_c_mi in enumerate(c_mi_values):
    predicted = dmr_lfsr_next(current)
    match = predicted == actual_c_mi
    if match:
        matches += 1
    
    print(f"{i}: Current: 0x{current:08X} -> Predicted: 0x{predicted:08X}, Actual: 0x{actual_c_mi:08X} {'✓' if match else '✗'}")
    
    # Use actual value for next prediction to stay in sync
    current = actual_c_mi

print(f"\nAccuracy: {matches}/{total} = {(matches/total)*100:.1f}%")

# Let's also test if we can find these values in the expected LFSR sequence
print("\n--- Checking if values appear in LFSR sequence ---")
current = h_mi
seen_values = set()
max_iterations = 35000  # Slightly more than LFSR period

for i in range(max_iterations):
    seen_values.add(current)
    current = dmr_lfsr_next(current)
    
    # Check if we've completed a cycle
    if current == h_mi:
        print(f"LFSR cycle completed at iteration {i+1}")
        break

print(f"\nTotal unique values in LFSR cycle: {len(seen_values)}")

# Check which C-MI values are in the LFSR sequence
print("\nC-MI values in LFSR sequence:")
for c_mi in c_mi_values:
    if c_mi in seen_values:
        print(f"0x{c_mi:08X} ✓ Found in sequence")
    else:
        print(f"0x{c_mi:08X} ✗ NOT in sequence")