#!/usr/bin/env python3
"""
Fixed AMBE end-to-end test with proper error handling
"""

import struct
import numpy as np
import wave
import subprocess

def analyze_cleartext_frames():
    """Safely analyze cleartext frames"""
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    frames = []
    bit_counts = []
    
    # Extract all frames
    for i in range(0, len(data), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            ambe_49bit = frame_64bit >> 15
            
            # Count bits
            bit_count = bin(ambe_49bit).count('1')
            
            frames.append(frame)
            bit_counts.append(bit_count)
    
    print(f"Analyzed {len(frames)} frames")
    print(f"Bit count range: {min(bit_counts)} to {max(bit_counts)}")
    
    # Sort frames by bit count
    sorted_indices = sorted(range(len(frames)), key=lambda i: bit_counts[i])
    
    # Get frames at different percentiles
    low_idx = sorted_indices[len(sorted_indices) // 10]  # 10th percentile
    high_idx = sorted_indices[9 * len(sorted_indices) // 10]  # 90th percentile
    
    return frames, low_idx, high_idx

def create_safe_test_pattern():
    """Create test pattern with error handling"""
    frames, low_idx, high_idx = analyze_cleartext_frames()
    
    # Create alternating pattern
    with open("safe_test_pattern.bin", "wb") as f:
        # Pattern: 3s low freq, 3s high freq, repeated
        pattern_sequence = [
            (low_idx, 150),   # 3 seconds at low
            (high_idx, 150),  # 3 seconds at high
            (low_idx, 150),   # 3 seconds at low
            (high_idx, 150),  # 3 seconds at high
            (low_idx, 150),   # 3 seconds at low
            (high_idx, 150),  # 3 seconds at high
        ]
        
        frame_count = 0
        for frame_idx, duration in pattern_sequence:
            for _ in range(duration):
                f.write(frames[frame_idx])
                frame_count += 1
    
    print(f"Created safe_test_pattern.bin with {frame_count} frames")
    print(f"Using frames {low_idx} (low) and {high_idx} (high)")
    
    # Also create a reference
    create_reference_audio()

def create_reference_audio():
    """Create 2400/2600 Hz reference"""
    sample_rate = 8000
    duration = 3.0
    
    # Generate tones
    audio_data = []
    frequencies = [2400, 2600, 2400, 2600, 2400, 2600]
    
    for freq in frequencies:
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = 0.8 * np.sin(2 * np.pi * freq * t)
        audio_data.extend(tone)
    
    # Save as WAV
    pcm_data = (np.array(audio_data) * 32767).astype(np.int16)
    
    with wave.open("reference_tones.wav", "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_data.tobytes())
    
    print(f"Created reference_tones.wav")

def decode_pattern(input_file, output_file):
    """Decode using our Python decoder"""
    subprocess.run([
        "python3", "decode_ambe_final.py",
        input_file, output_file
    ])
    print(f"Decoded to {output_file}")

def create_spectrograms():
    """Create spectrograms for comparison"""
    files = ["reference_tones.wav", "safe_decoded.wav"]
    
    for audio_file in files:
        spec_file = audio_file.replace(".wav", "_spectrogram.png")
        subprocess.run([
            "sox", audio_file, "-n", "spectrogram",
            "-o", spec_file,
            "-x", "800", "-y", "400"
        ])
        print(f"Created {spec_file}")

def main():
    print("=== Fixed AMBE End-to-End Test ===\n")
    
    # Create test pattern safely
    create_safe_test_pattern()
    
    # Decode it
    decode_pattern("safe_test_pattern.bin", "safe_decoded.wav")
    
    # Create spectrograms
    create_spectrograms()
    
    print("\n=== Test Complete ===")
    print("Check the spectrograms:")
    print("1. reference_tones_spectrogram.png - Should show clear 2400/2600 Hz lines")
    print("2. safe_decoded_spectrogram.png - Should show some pattern if decoding works")

if __name__ == "__main__":
    main()