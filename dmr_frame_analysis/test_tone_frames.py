#!/usr/bin/env python3
"""
Test specific frames that should contain tones
"""

import struct
import subprocess
import numpy as np

def test_high_pitch_frames():
    """Test frames with maximum pitch value"""
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Find frames with pitch=255 (maximum)
    max_pitch_frames = []
    
    for i in range(0, len(data), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            ambe_49bit = frame_64bit >> 15
            
            pitch = ambe_49bit & 0xFF
            
            if pitch == 255:
                max_pitch_frames.append((i//8, frame))
    
    print(f"Found {len(max_pitch_frames)} frames with max pitch (255)")
    
    # Create test file with these frames
    with open("max_pitch_test.bin", "wb") as f:
        # Use first max pitch frame repeated
        if max_pitch_frames:
            frame_idx, frame_data = max_pitch_frames[0]
            print(f"Using frame {frame_idx} for test")
            
            # 3 seconds of this frame
            for _ in range(150):
                f.write(frame_data)
    
    # Decode it
    print("\nDecoding max pitch frame...")
    subprocess.run([
        "python3", "decode_ambe_final.py",
        "max_pitch_test.bin", "max_pitch_decoded.wav"
    ])
    
    # Analyze
    print("\nAnalyzing decoded audio...")
    result = subprocess.run([
        "sox", "max_pitch_decoded.wav", "-n", "stats"
    ], capture_output=True, text=True, stderr=subprocess.STDOUT)
    
    # Extract key info
    for line in result.stdout.split('\n'):
        if 'frequency' in line.lower() or 'peak' in line.lower():
            print(line)

def test_frame_patterns():
    """Test different frame patterns"""
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Categorize frames by characteristics
    frame_types = {
        'silence': [],
        'low_energy': [],
        'high_energy': [],
        'steady_tone': []
    }
    
    for i in range(0, min(5000, len(data)), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            ambe_49bit = frame_64bit >> 15
            
            # Analyze characteristics
            pitch = ambe_49bit & 0xFF
            gain = (ambe_49bit >> 8) & 0xF
            voicing = (ambe_49bit >> 12) & 0xF
            spectral = (ambe_49bit >> 16) & 0x1FFFFFFFF
            
            # Categorize
            if pitch == 0 and gain == 0:
                frame_types['silence'].append((i//8, frame))
            elif gain < 5:
                frame_types['low_energy'].append((i//8, frame))
            elif gain > 10:
                frame_types['high_energy'].append((i//8, frame))
            
            # Look for steady tone characteristics
            # In AMBE, tones might have:
            # - Consistent non-zero pitch
            # - Moderate gain
            # - Specific spectral pattern
            if 50 < pitch < 200 and 5 < gain < 12:
                frame_types['steady_tone'].append((i//8, frame))
    
    print("\nFrame categorization:")
    for ftype, frames in frame_types.items():
        print(f"{ftype}: {len(frames)} frames")
    
    # Test steady tone candidates
    if frame_types['steady_tone']:
        with open("steady_tone_test.bin", "wb") as f:
            # Use several different steady tone frames
            for idx, (frame_idx, frame_data) in enumerate(frame_types['steady_tone'][:3]):
                print(f"\nSteady tone frame {idx} (index {frame_idx})")
                # 1 second of each
                for _ in range(50):
                    f.write(frame_data)
        
        # Decode
        subprocess.run([
            "python3", "decode_ambe_final.py",
            "steady_tone_test.bin", "steady_tone_decoded.wav"
        ])
        
        # Frequency analysis
        print("\nFrequency analysis of steady tone frames:")
        subprocess.run([
            "python3", "analyze_tone_frequencies.py"
        ])

def compare_with_reference():
    """Compare with known good AMBE decoding"""
    
    print("\n=== Comparing with reference implementation ===")
    
    # If DSD-FME can decode our cleartext properly, let's use it
    print("Testing cleartext with DSD-FME directly...")
    
    # Create a simple test
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read(800)  # First 100 frames
    
    with open("test_100_frames.bin", "wb") as f:
        f.write(data)
    
    # Try different decoders
    print("\n1. Testing with our decoder:")
    subprocess.run([
        "python3", "decode_ambe_final.py",
        "test_100_frames.bin", "our_decode.wav"
    ])
    
    print("\n2. Creating spectrogram:")
    subprocess.run([
        "sox", "our_decode.wav", "-n", "spectrogram",
        "-o", "our_decode_spec.png"
    ])

def main():
    print("=== Testing Tone Frames in AMBE ===\n")
    
    # Test frames with maximum pitch
    test_high_pitch_frames()
    
    # Test different frame patterns
    test_frame_patterns()
    
    # Compare with reference
    compare_with_reference()
    
    print("\n=== Test Complete ===")
    print("Check spectrograms to see if any frames produce clear tones")

if __name__ == "__main__":
    main()