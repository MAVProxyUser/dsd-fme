#!/usr/bin/env python3
"""
DMR LFSR Analysis - Verify and predict C- MI evolution
Polynomial: C(x) = x^32 + x^4 + x^2 + 1
"""

def lfsr_next(current_mi):
    """
    Calculate the next MI value using the LFSR algorithm
    Polynomial: x^32 + x^4 + x^2 + 1
    """
    lfsr = current_mi
    
    # Iterate 32 times as per the C implementation
    for _ in range(32):
        # Calculate feedback bit using taps at positions 32, 4, and 2
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        # Shift left and add the new bit
        lfsr = (lfsr << 1) | bit
    
    # Mask to 32 bits
    return lfsr & 0xFFFFFFFF

def lfsr_sequence(seed, count):
    """Generate a sequence of LFSR values starting from seed"""
    values = [seed]
    current = seed
    
    for _ in range(count):
        current = lfsr_next(current)
        values.append(current)
    
    return values

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

# H- MI (seed) value
h_mi = 0x6C8AB637

print("DMR LFSR Analysis")
print("=================")
print(f"H- MI (seed): 0x{h_mi:08X}")
print()

# Verify the LFSR evolution
print("Verifying LFSR evolution:")
print("Index | Captured      | Calculated    | Match")
print("------|---------------|---------------|------")

current = h_mi
matches = 0
for i, captured in enumerate(captured_values):
    # Calculate next value
    current = lfsr_next(current)
    match = "YES" if current == captured else "NO"
    if current == captured:
        matches += 1
    print(f"{i:5d} | 0x{captured:08X} | 0x{current:08X} | {match}")

print(f"\nMatches: {matches}/{len(captured_values)}")

# If we have good matches, predict next values
if matches > len(captured_values) * 0.9:  # If >90% match
    print("\nPredicting next 10 values:")
    print("Index | Predicted")
    print("------|-------------")
    
    # Start from the last captured value
    current = captured_values[-1]
    for i in range(10):
        current = lfsr_next(current)
        print(f"{i:5d} | 0x{current:08X}")
else:
    print("\nNot enough matches to reliably predict future values")
    print("The LFSR may not be starting directly from the H- MI")
    
    # Try to find the sequence starting point
    print("\nSearching for sequence starting point...")
    # Generate more values from the seed
    extended_sequence = lfsr_sequence(h_mi, 100)
    
    # Look for the first captured value in the sequence
    for offset, value in enumerate(extended_sequence):
        if value == captured_values[0]:
            print(f"Found sequence starting at offset {offset} from H- MI")
            print("Verifying with this offset...")
            
            # Verify from this offset
            matches = 0
            for i, captured in enumerate(captured_values):
                if i + offset < len(extended_sequence):
                    calculated = extended_sequence[i + offset]
                    match = "YES" if calculated == captured else "NO"
                    if calculated == captured:
                        matches += 1
                    print(f"Value {i}: 0x{captured:08X} vs 0x{calculated:08X} {match}")
            
            print(f"Matches with offset {offset}: {matches}/{len(captured_values)}")
            break