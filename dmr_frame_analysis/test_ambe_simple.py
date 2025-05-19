#!/usr/bin/env python3
"""
Simple AMBE test using known working patterns
"""

import struct
import numpy as np
import wave
import subprocess

# Known AMBE patterns from DSD-FME source comments
AMBE_PATTERNS = {
    'silence': 0x00E8D30001A3E0,  # Standard DMR silence
    'tone_low': 0x06C8D30001A3E0,  # Low frequency tone approximation  
    'tone_high': 0x1AD8D30001A3E0, # High frequency tone approximation
}

def create_simple_test():
    """Create simple AMBE test pattern"""
    
    # Pattern: silence, low tone, high tone, silence
    pattern_sequence = ['silence'] * 50 + ['tone_low'] * 100 + ['tone_high'] * 100 + ['silence'] * 50
    
    with open("simple_test_ambe.bin", "wb") as f:
        for pattern_name in pattern_sequence:
            ambe_49bit = AMBE_PATTERNS[pattern_name]
            
            # Pack as 8-byte frame (49 bits in upper positions)
            frame_64bit = (ambe_49bit << 15) & 0xFFFFFFFFFFFFFFFF
            f.write(struct.pack('>Q', frame_64bit))
    
    print(f"Created simple_test_ambe.bin with {len(pattern_sequence)} frames")
    
    # Also try with actual frames from our cleartext capture
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Extract frames with specific patterns
    frames_by_pattern = {}
    
    for i in range(0, min(1000, len(data)), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            
            # Look for specific bit patterns
            bits_15_20 = (frame_64bit >> 43) & 0x3F  # Extract 6 bits
            
            if bits_15_20 not in frames_by_pattern:
                frames_by_pattern[bits_15_20] = []
            frames_by_pattern[bits_15_20].append(frame)
    
    # Create pattern using real frames
    with open("real_pattern_test.bin", "wb") as f:
        # Find frames with different characteristics
        sorted_patterns = sorted(frames_by_pattern.keys())
        
        # Use frames with low, medium, high bit patterns
        low_pattern = sorted_patterns[len(sorted_patterns)//4]
        high_pattern = sorted_patterns[3*len(sorted_patterns)//4]
        
        # Write pattern
        for _ in range(50):
            f.write(frames_by_pattern[low_pattern][0])
        for _ in range(100):
            f.write(frames_by_pattern[high_pattern][0])
        for _ in range(50):
            f.write(frames_by_pattern[low_pattern][0])
    
    print("Created real_pattern_test.bin from actual cleartext frames")

def decode_and_verify(ambe_file, output_wav):
    """Decode AMBE file and create spectrogram"""
    
    print(f"\nDecoding {ambe_file}...")
    
    # Use our decoder
    subprocess.run([
        "python3", "decode_ambe_final.py",
        ambe_file, output_wav
    ])
    
    print(f"Creating spectrogram for {output_wav}...")
    
    # Create spectrogram
    spectrogram_file = output_wav.replace('.wav', '_spectrogram.png')
    subprocess.run([
        "sox", output_wav, "-n", "spectrogram",
        "-o", spectrogram_file,
        "-x", "800", "-y", "400",
        "-z", "100"
    ])
    
    print(f"Spectrogram saved to {spectrogram_file}")
    
    # Get audio statistics
    result = subprocess.run([
        "sox", output_wav, "-n", "stat"
    ], capture_output=True, text=True, stderr=subprocess.STDOUT)
    
    print("\nAudio statistics:")
    print(result.stdout)

def test_individual_frame():
    """Test decoding a single frame"""
    
    # Use first frame from cleartext
    with open("cleartext_ambe.bin", "rb") as f:
        single_frame = f.read(8)
    
    with open("single_frame_test.bin", "wb") as f:
        # Write the same frame 100 times
        for _ in range(100):
            f.write(single_frame)
    
    print("Created single_frame_test.bin")
    decode_and_verify("single_frame_test.bin", "single_frame_decoded.wav")

def main():
    print("=== Simple AMBE Test ===\n")
    
    # Create test patterns
    create_simple_test()
    
    # Decode simple pattern
    decode_and_verify("simple_test_ambe.bin", "simple_test_decoded.wav")
    
    # Decode real pattern
    decode_and_verify("real_pattern_test.bin", "real_pattern_decoded.wav")
    
    # Test single frame
    test_individual_frame()
    
    print("\n=== Summary ===")
    print("Check the following files:")
    print("1. simple_test_decoded.wav - Should have distinct pattern")
    print("2. real_pattern_decoded.wav - From actual cleartext")
    print("3. single_frame_decoded.wav - Single frame repeated")
    print("\nSpectrograms created for visual verification")

if __name__ == "__main__":
    main()