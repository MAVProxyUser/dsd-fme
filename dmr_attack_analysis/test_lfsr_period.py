#!/usr/bin/env python3
"""
Test the LFSR period claim - is it really 2^15-1 instead of 2^32-1?
"""

def dmr_lfsr_next(lfsr):
    """DMR LFSR: x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def test_lfsr_period():
    """Test if LFSR period is 2^15-1 as claimed"""
    print("=== Testing DMR LFSR Period ===\n")
    
    # Start with the known initial value
    initial = 0x6C8AB637
    current = initial
    
    # Track all values seen
    seen_values = {initial: 0}
    
    # Generate values and look for cycle
    print("Generating LFSR sequence...")
    
    # Test for 2^15 iterations as claimed
    max_iterations = 2**15
    
    for i in range(1, max_iterations + 1):
        current = dmr_lfsr_next(current)
        
        if current in seen_values:
            print(f"\nCYCLE DETECTED at iteration {i}!")
            print(f"Value 0x{current:08X} was previously seen at iteration {seen_values[current]}")
            print(f"Cycle length: {i - seen_values[current]}")
            
            if current == initial:
                print(f"Returned to initial value - full cycle length: {i}")
            
            # Verify it's actually repeating
            test_next = current
            print("\nVerifying cycle by generating next 5 values:")
            for j in range(5):
                test_next = dmr_lfsr_next(test_next)
                original_pos = seen_values.get(test_next, -1)
                print(f"  0x{test_next:08X} - originally at position {original_pos}")
            
            return i
        
        seen_values[current] = i
        
        # Progress indicator
        if i % 1000 == 0:
            print(f"  Iteration {i}: 0x{current:08X}")
    
    print(f"\nNo cycle detected within {max_iterations} iterations")
    print(f"Unique values generated: {len(seen_values)}")
    
    # Let's continue a bit more to see if cycle happens after 2^15
    print("\nContinuing past 2^15...")
    for i in range(max_iterations + 1, max_iterations + 1000):
        current = dmr_lfsr_next(current)
        
        if current in seen_values:
            print(f"\nCYCLE DETECTED at iteration {i}!")
            print(f"Value 0x{current:08X} was previously seen at iteration {seen_values[current]}")
            print(f"Cycle length: {i - seen_values[current]}")
            
            if current == initial:
                print(f"Returned to initial value - full cycle length: {i}")
            
            return i
        
        seen_values[current] = i
    
    return None

def test_polynomial_primitivity():
    """Test if the polynomial is primitive"""
    print("\n=== Testing Polynomial Primitivity ===\n")
    
    # The polynomial x^32 + x^4 + x^2 + 1
    # For an LFSR to have maximal period 2^n-1, the polynomial must be primitive
    
    print("Polynomial: x^32 + x^4 + x^2 + 1")
    print("Binary representation: 10000000000000000000000000010101")
    print()
    
    # Test different starting values to see if they produce different cycle lengths
    test_values = [
        0x6C8AB637,  # Our known DMR value
        0x00000001,  # Minimal non-zero
        0xFFFFFFFF,  # All ones
        0x12345678,  # Random
        0xAAAAAAAA,  # Alternating bits
    ]
    
    cycle_lengths = {}
    
    for start_val in test_values:
        print(f"Testing with start value 0x{start_val:08X}...")
        current = start_val
        seen = {start_val: 0}
        
        for i in range(1, 2**16):  # Test up to 2^16
            current = dmr_lfsr_next(current)
            
            if current in seen:
                cycle_len = i - seen[current]
                cycle_lengths[start_val] = cycle_len
                print(f"  Cycle length: {cycle_len}")
                break
                
            seen[current] = i
            
            if i % 5000 == 0:
                print(f"    Still searching... iteration {i}")
    
    print("\nCycle lengths for different starting values:")
    for val, length in cycle_lengths.items():
        print(f"  0x{val:08X}: {length}")
    
    # Check if all non-zero values have the same cycle length
    unique_lengths = set(cycle_lengths.values())
    if len(unique_lengths) == 1:
        print(f"\nAll starting values produce the same cycle length: {unique_lengths.pop()}")
        print("This suggests a single large cycle (characteristic of primitive polynomial)")
    else:
        print(f"\nDifferent cycle lengths found: {unique_lengths}")
        print("This confirms the polynomial is NOT primitive!")

def analyze_captured_mi_sequences():
    """Analyze actual captured MI sequences"""
    print("\n=== Analyzing Captured MI Sequences ===\n")
    
    # Known sequences from our captures
    captured_sequences = [
        [0x6C8AB637, 0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B],
        [0x6C8AB637, 0x4F36EE3A, 0xE8083B57],  # Different order
    ]
    
    print("Testing if captured sequences follow our LFSR...")
    
    for seq_num, sequence in enumerate(captured_sequences):
        print(f"\nSequence {seq_num + 1}:")
        
        current = sequence[0]
        matches = True
        
        for i in range(1, len(sequence)):
            next_predicted = dmr_lfsr_next(current)
            actual = sequence[i]
            
            print(f"  Step {i}: 0x{current:08X} -> 0x{next_predicted:08X} (actual: 0x{actual:08X})")
            
            if next_predicted != actual:
                print(f"    MISMATCH! This sequence doesn't follow our LFSR")
                matches = False
                break
            
            current = actual
        
        if matches:
            print("  ✓ Sequence matches LFSR progression")
        else:
            print("  ✗ Sequence deviates from LFSR")

def main():
    print("DMR LFSR Period Analysis")
    print("========================\n")
    
    # Test the main claim about 2^15-1 period
    actual_period = test_lfsr_period()
    
    # Test polynomial primitivity
    test_polynomial_primitivity()
    
    # Analyze captured sequences
    analyze_captured_mi_sequences()
    
    print("\n=== CONCLUSIONS ===")
    
    if actual_period and actual_period == 2**15 - 1:
        print(f"✓ CONFIRMED: LFSR period is {actual_period} (2^15-1)")
        print("  This is much shorter than 2^32-1!")
        print("  The polynomial is NOT primitive")
        print("  This could indeed be a deliberate weakness")
    elif actual_period:
        print(f"✗ Period is {actual_period}, not 2^15-1 as claimed")
    else:
        print("✗ Could not determine period within tested range")
    
    print("\nIMPLICATIONS:")
    print("- Shorter period = fewer unique MI values")
    print("- More keystream reuse opportunities") 
    print("- Easier cryptanalysis")
    print("- Possible intentional weakness")

if __name__ == "__main__":
    main()