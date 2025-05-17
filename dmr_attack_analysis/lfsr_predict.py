#!/usr/bin/env python3
"""
DMR LFSR Prediction with interleaving pattern
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

def apply_dmr_interleaving(sequence):
    """Apply the DMR interleaving pattern discovered from captured data"""
    # Pattern observed: every 3rd and 4th values are swapped in groups of 6
    result = []
    i = 0
    while i < len(sequence):
        # Groups of 6: [0,1,2,3,4,5] -> [0,1,2,5,3,4]
        if i + 5 < len(sequence):
            result.extend([sequence[i], sequence[i+1], sequence[i+2]])
            result.extend([sequence[i+5], sequence[i+3], sequence[i+4]])
            i += 6
        else:
            # Handle remaining values
            result.extend(sequence[i:])
            break
    return result

# Generate expected sequence from H- MI
h_mi = 0x6C8AB637
print(f"H- MI (seed): 0x{h_mi:08X}")
print()

# Generate the raw LFSR sequence
raw_sequence = []
current = h_mi
for _ in range(30):  # Generate more than we need
    current = lfsr_next(current)
    raw_sequence.append(current)

# Apply interleaving pattern
interleaved = apply_dmr_interleaving(raw_sequence)

# Show the prediction for the next values
last_captured = 0x206BF0CF
print("Last captured value: 0x{:08X}".format(last_captured))
print()

# Find where we are in the sequence
try:
    idx = interleaved.index(last_captured)
    print(f"Found last captured value at position {idx}")
    print()
    
    print("Predicted next 10 C- MI values:")
    print("Index | Predicted C- MI")
    print("------|----------------")
    
    for i in range(1, 11):
        if idx + i < len(interleaved):
            predicted = interleaved[idx + i]
            print(f"{i:5d} | 0x{predicted:08X}")
    
    # Also show what they would be without interleaving
    print("\nRaw LFSR sequence (without interleaving):")
    current = last_captured
    # Need to find the raw position
    raw_idx = raw_sequence.index(last_captured) if last_captured in raw_sequence else -1
    
    if raw_idx >= 0:
        print("Index | Raw LFSR")
        print("------|-------------")
        for i in range(1, 11):
            if raw_idx + i < len(raw_sequence):
                print(f"{i:5d} | 0x{raw_sequence[raw_idx + i]:08X}")
    else:
        # Generate from last captured
        print("Generating from last captured value...")
        current = last_captured
        for i in range(1, 11):
            current = lfsr_next(current)
            print(f"{i:5d} | 0x{current:08X}")
            
except ValueError:
    print("Last captured value not found in sequence, generating from it directly...")
    current = last_captured
    print("\nPredicted next values (without pattern adjustment):")
    for i in range(1, 11):
        current = lfsr_next(current)
        print(f"{i:5d} | 0x{current:08X}")

# Verify our pattern understanding
print("\nPattern verification with captured data:")
captured_values = [
    0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0x1E3DC9E8, 0xD3C028BF,
    0xD851670C, 0x97D76800, 0xB0E136DB, 0xBB5FC480, 0x46CB4902, 0xF3152FD2,
    0xDC09BDB4, 0x11E3BB5A, 0xB9EC6354, 0xC4856E39, 0x2BFABF7C, 0x3D6EEE34,
    0x63BBBB54, 0x206BF0CF
]

matches = 0
for i, captured in enumerate(captured_values):
    if i < len(interleaved) and captured == interleaved[i]:
        matches += 1

print(f"Matches with interleaving pattern: {matches}/{len(captured_values)}")