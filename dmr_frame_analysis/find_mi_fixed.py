#!/usr/bin/env python3
"""
Find MI in LFSR cycle - fixed version
"""

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def find_position_in_cycle(target_mi, start_mi):
    """Find position of target MI starting from start MI"""
    mi = start_mi
    
    for step in range(32767):  # Full cycle
        mi = dmr_lfsr_next(mi)
        if mi == target_mi:
            return step + 1
    
    return None

def print_lfsr_sequence(start_mi, count):
    """Print LFSR sequence"""
    mi = start_mi
    print(f"Starting from 0x{start_mi:08x}:")
    
    for i in range(count):
        mi = dmr_lfsr_next(mi)
        print(f"  Step {i+1}: 0x{mi:08x}")

if __name__ == "__main__":
    h_mi = 0x6C8AB637
    
    # Show the first 20 steps
    print("LFSR sequence from H_MI:")
    print_lfsr_sequence(h_mi, 20)
    
    # Now find our C_MI values
    print("\nFinding our C_MI values:")
    c_mis = [0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0xC4856E39]
    
    for c_mi in c_mis:
        position = find_position_in_cycle(c_mi, h_mi)
        if position:
            print(f"  0x{c_mi:08x} - Found at step {position}")
        else:
            print(f"  0x{c_mi:08x} - NOT FOUND")
    
    # Double check by generating exact positions
    print("\nVerifying by direct calculation:")
    mi = h_mi
    for i in range(20):
        mi = dmr_lfsr_next(mi)
        if mi in c_mis:
            print(f"  Step {i+1}: 0x{mi:08x} ✓")