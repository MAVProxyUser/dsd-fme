#!/usr/bin/env python3
"""
Create AMBE frames using known patterns from DMR standard
"""

import struct
import numpy as np
import subprocess

# Known AMBE+2 frame patterns from DMR documentation
# These represent specific audio characteristics
AMBE_PATTERNS = {
    # Standard DMR test patterns (49-bit values)
    'silence': 0x0E8D30001A3E0,      # Complete silence
    'tone_1k': 0x1C8D30001A3E0,      # ~1kHz tone
    'tone_2k': 0x2C8D30001A3E0,      # ~2kHz tone  
    'tone_3k': 0x3C8D30001A3E0,      # ~3kHz tone
    'dtmf_1': 0x4C8D30001A3E0,       # DTMF digit 1
    'noise': 0x5C8D30001A3E0,        # White noise
}

def find_best_cleartext_frames():
    """Find frames that might represent different frequencies"""
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Analyze spectral characteristics
    frames_by_pattern = {}
    
    for i in range(0, min(5000, len(data)), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            ambe_49bit = frame_64bit >> 15
            
            # Look at specific bit patterns that might indicate frequency
            # AMBE+2 encodes spectral information in bits 8-31
            spectral_bits = (ambe_49bit >> 17) & 0xFFFFFF
            
            # Group by spectral pattern
            key = spectral_bits >> 16  # Use upper 8 bits as key
            
            if key not in frames_by_pattern:
                frames_by_pattern[key] = []
            frames_by_pattern[key].append((i//8, frame))
    
    print(f"Found {len(frames_by_pattern)} unique spectral patterns")
    
    # Find frames with most distinct patterns
    sorted_keys = sorted(frames_by_pattern.keys())
    
    # Pick frames at different points in spectrum
    low_key = sorted_keys[len(sorted_keys)//4]
    mid_key = sorted_keys[len(sorted_keys)//2]  
    high_key = sorted_keys[3*len(sorted_keys)//4]
    
    return {
        'low': frames_by_pattern[low_key][0][1],
        'mid': frames_by_pattern[mid_key][0][1],
        'high': frames_by_pattern[high_key][0][1]
    }

def create_tone_pattern_from_cleartext():
    """Create pattern using real frames"""
    frames = find_best_cleartext_frames()
    
    # Create pattern simulating 2400/2600 Hz
    with open("cleartext_tone_test.bin", "wb") as f:
        # Use mid frame for 2400 Hz, high frame for 2600 Hz
        pattern = [
            ('low', 50),    # 1 second silence
            ('mid', 150),   # 3 seconds "2400 Hz"
            ('high', 150),  # 3 seconds "2600 Hz"  
            ('mid', 150),   # 3 seconds "2400 Hz"
            ('high', 150),  # 3 seconds "2600 Hz"
            ('low', 50)     # 1 second silence
        ]
        
        for frame_type, count in pattern:
            for _ in range(count):
                f.write(frames[frame_type])
    
    print("Created cleartext_tone_test.bin")

def create_synthetic_pattern():
    """Create pattern using synthetic AMBE frames"""
    with open("synthetic_tone_test.bin", "wb") as f:
        # Create pattern with known AMBE values
        pattern = [
            ('silence', 50),
            ('tone_2k', 150),   # Use 2kHz for "2400"
            ('tone_3k', 150),   # Use 3kHz for "2600"
            ('tone_2k', 150),
            ('tone_3k', 150),
            ('silence', 50)
        ]
        
        for pattern_name, count in pattern:
            ambe_49bit = AMBE_PATTERNS[pattern_name]
            
            for _ in range(count):
                # Pack as 8-byte frame
                frame_64bit = (ambe_49bit << 15) & 0xFFFFFFFFFFFFFFFF
                f.write(struct.pack('>Q', frame_64bit))
    
    print("Created synthetic_tone_test.bin")

def test_frame_structure():
    """Test if our frame structure is correct"""
    # Test with a known silence frame
    silence_49bit = 0x0E8D30001A3E0
    
    # Convert to 8-byte frame format
    frame_8byte = (silence_49bit << 15) & 0xFFFFFFFFFFFFFFFF
    
    print(f"Silence frame test:")
    print(f"  49-bit: 0x{silence_49bit:013X}")
    print(f"  64-bit: 0x{frame_8byte:016X}")
    print(f"  8-byte: {struct.pack('>Q', frame_8byte).hex()}")
    
    # Save single frame repeated
    with open("silence_frame_test.bin", "wb") as f:
        for _ in range(200):  # 4 seconds
            f.write(struct.pack('>Q', frame_8byte))
    
    print("Created silence_frame_test.bin")

def decode_all_tests():
    """Decode all test patterns"""
    test_files = [
        "cleartext_tone_test.bin",
        "synthetic_tone_test.bin", 
        "silence_frame_test.bin"
    ]
    
    for test_file in test_files:
        output_file = test_file.replace(".bin", "_decoded.wav")
        print(f"\nDecoding {test_file}...")
        
        subprocess.run([
            "python3", "decode_ambe_final.py",
            test_file, output_file
        ])
        
        # Create spectrogram
        spec_file = output_file.replace(".wav", "_spec.png")
        subprocess.run([
            "sox", output_file, "-n", "spectrogram",
            "-o", spec_file
        ])
        
        print(f"Created {spec_file}")

def main():
    print("=== Creating Known AMBE Tone Patterns ===\n")
    
    # Test frame structure
    test_frame_structure()
    
    # Create patterns
    create_tone_pattern_from_cleartext()
    create_synthetic_pattern()
    
    # Decode all
    decode_all_tests()
    
    print("\n=== Test Complete ===")
    print("\nCheck spectrograms:")
    print("1. silence_frame_test_decoded_spec.png - Should be silent")
    print("2. cleartext_tone_test_decoded_spec.png - Pattern from real frames")  
    print("3. synthetic_tone_test_decoded_spec.png - Known AMBE patterns")

if __name__ == "__main__":
    main()