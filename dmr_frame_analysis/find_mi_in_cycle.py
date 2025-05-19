#!/usr/bin/env python3
"""
Find where C4856E39 appears in the LFSR cycle
"""

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def find_mi_in_cycle(target_mi):
    """Find where a specific MI appears in the LFSR cycle"""
    h_mi = 0x6C8AB637
    mi = h_mi
    
    print(f"Searching for 0x{target_mi:08x} in LFSR cycle...")
    print(f"Starting from H_MI: 0x{h_mi:08x}")
    
    for step in range(32767):  # Full cycle
        mi = dmr_lfsr_next(mi)
        if mi == target_mi:
            print(f"\nFound at step {step+1}!")
            
            # Show surrounding values
            print("\nContext (±3 steps):")
            context_mi = h_mi
            for i in range(max(0, step-2), min(32767, step+4)):
                for _ in range(i):
                    context_mi = dmr_lfsr_next(context_mi)
                marker = " <-- HERE" if i == step else ""
                print(f"  Step {i+1}: 0x{context_mi:08x}{marker}")
                context_mi = h_mi  # Reset for next iteration
            
            return step + 1
    
    print(f"Not found in LFSR cycle!")
    return None

if __name__ == "__main__":
    # The mystery MI
    mystery_mi = 0xC4856E39
    position = find_mi_in_cycle(mystery_mi)
    
    if position:
        print(f"\n0xC4856E39 is at position {position} in the LFSR sequence")
        
        # Now check our actual sequence
        print("\nOur actual C_MI sequence:")
        c_mis = [0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0xC4856E39]
        
        h_mi = 0x6C8AB637
        for i, c_mi in enumerate(c_mis):
            # Find position
            mi = h_mi
            for step in range(32767):
                mi = dmr_lfsr_next(mi)
                if mi == c_mi:
                    print(f"  {i+1}. 0x{c_mi:08x} - Step {step+1}")
                    break