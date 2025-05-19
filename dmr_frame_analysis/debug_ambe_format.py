#!/usr/bin/env python3
"""
Debug AMBE format to understand why tones aren't working
"""

import struct
import subprocess

def examine_mbelib_source():
    """Check mbelib source for AMBE frame format"""
    
    # Let's examine actual AMBE+2 bit allocation from documentation
    print("=== AMBE+2 Frame Structure (49 bits) ===")
    print("Based on DVSI AMBE+2 vocoder specification:")
    print("Bits 0-7:   Reserved/Error control")  
    print("Bits 8-11:  Voicing metrics")
    print("Bits 12-19: Fundamental frequency (pitch)")
    print("Bits 20-32: HOC (Higher Order Coefficients) magnitudes")
    print("Bits 33-48: Additional spectral/error info")
    print()

def check_dmr_spec():
    """Check DMR specification for AMBE usage"""
    
    print("=== DMR AMBE Usage ===")
    print("DMR uses AMBE+2 at 3600 bps (49 bits every 20ms)")
    print("Frame structure in DMR:")
    print("- 216 bit burst = 108 bit payload") 
    print("- 108 bits = 3 x 36 bits")
    print("- Each 36 bits = 49 bit AMBE + 7 bit FEC")
    print()

def analyze_bit_patterns():
    """Analyze bit patterns in our frames"""
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read(80)  # First 10 frames
    
    print("=== Bit Pattern Analysis ===")
    
    for i in range(10):
        frame = data[i*8:(i+1)*8]
        frame_64bit = struct.unpack('>Q', frame)[0]
        
        # Extract in different ways to check
        method1 = frame_64bit >> 15  # Our current method
        method2 = frame_64bit & 0x1FFFFFFFFFFFF000  # Top 49 bits
        method3 = frame_64bit >> 15  # Same as method1
        
        print(f"\nFrame {i+1}:")
        print(f"  Raw hex: {frame.hex()}")
        print(f"  Method1 (>>15):      0x{method1:013X}")
        print(f"  Method2 (mask):      0x{method2:016X}")
        
        # Extract specific fields based on AMBE spec
        # This is speculative - actual bit positions may differ
        ambe_49 = method1
        
        # Try different field extractions
        field1 = ambe_49 & 0xFF  # Lower 8 bits
        field2 = (ambe_49 >> 8) & 0xFF  # Next 8 bits
        field3 = (ambe_49 >> 16) & 0xFF  # Next 8 bits
        field4 = (ambe_49 >> 24) & 0xFF  # Next 8 bits
        field5 = (ambe_49 >> 32) & 0x1FFFF  # Upper 17 bits
        
        print(f"  Fields: {field1:02X} {field2:02X} {field3:02X} {field4:02X} {field5:05X}")

def create_test_with_known_pattern():
    """Create test using frames that should be tones"""
    
    # Let's find frames that have patterns suggesting tones
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Look for patterns that might indicate stable frequencies
    tone_candidates = []
    
    for i in range(0, min(5000, len(data)), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            ambe_49bit = frame_64bit >> 15
            
            # Look for specific patterns that might indicate tones
            # Tones should have stable parameters unlike speech
            
            # Check if middle bits are stable (potential frequency info)
            mid_bits = (ambe_49bit >> 16) & 0xFFFF
            
            # Tones might have repeating patterns
            if mid_bits in [0x8D30, 0x8D24, 0x8D3C]:  # Patterns seen in test data
                tone_candidates.append((i//8, frame, mid_bits))
    
    print(f"\nFound {len(tone_candidates)} potential tone frames")
    
    if tone_candidates:
        # Group by pattern
        patterns = {}
        for idx, frame, pattern in tone_candidates:
            if pattern not in patterns:
                patterns[pattern] = []
            patterns[pattern].append((idx, frame))
        
        print("\nPatterns found:")
        for pattern, frames in patterns.items():
            print(f"  Pattern 0x{pattern:04X}: {len(frames)} frames")
        
        # Create test with different patterns
        with open("pattern_test.bin", "wb") as f:
            for pattern, frames in sorted(patterns.items()):
                if frames:
                    # Use first frame of this pattern
                    _, frame_data = frames[0]
                    # 2 seconds of this pattern
                    for _ in range(100):
                        f.write(frame_data)
        
        print("Created pattern_test.bin")
        
        # Decode and analyze
        subprocess.run([
            "python3", "decode_ambe_final.py",
            "pattern_test.bin", "pattern_decoded.wav"
        ])

def test_different_decoders():
    """Try different AMBE decoders to see if issue is with mbelib"""
    
    print("\n=== Testing Different Decoders ===")
    
    # Create a short test file
    with open("cleartext_ambe.bin", "rb") as f:
        test_data = f.read(400)  # 50 frames
    
    with open("test_50frames.bin", "wb") as f:
        f.write(test_data)
    
    # Test 1: Our current decoder
    print("1. Our mbelib decoder:")
    subprocess.run([
        "./decode_mbelib_correct", 
        "cleartext_ambe_7byte_fixed.bin",
        "mbelib_output.wav"
    ])
    
    # Check output
    if subprocess.run(["ls", "mbelib_output.wav"], capture_output=True).returncode == 0:
        result = subprocess.run(["sox", "mbelib_output.wav", "-n", "stats"], 
                              capture_output=True, text=True, stderr=subprocess.STDOUT)
        print(result.stdout)

def main():
    print("=== Debugging AMBE Format ===\n")
    
    # Understand AMBE structure
    examine_mbelib_source()
    check_dmr_spec()
    
    # Analyze our frames
    analyze_bit_patterns()
    
    # Create targeted tests
    create_test_with_known_pattern()
    
    # Try different approaches
    test_different_decoders()
    
    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    main()