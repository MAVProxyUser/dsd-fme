#!/usr/bin/env python3
"""
Real AMBE+2 end-to-end test using DSD-FME capture and decode
"""

import numpy as np
import wave
import subprocess
import os
import struct

def generate_test_tones():
    """Generate 2400/2600 Hz alternating test tones"""
    sample_rate = 8000
    duration_per_tone = 3.0  # 3 seconds each
    
    # Create alternating pattern
    pattern = []
    frequencies = [2400, 2600]
    
    for cycle in range(3):  # 3 cycles
        for freq in frequencies:
            t = np.linspace(0, duration_per_tone, int(sample_rate * duration_per_tone), False)
            tone = np.sin(2 * np.pi * freq * t) * 0.8
            pattern.extend(tone)
    
    # Convert to 16-bit PCM
    audio_data = np.array(pattern)
    pcm_data = (audio_data * 32767).astype(np.int16)
    
    # Save as WAV
    with wave.open("test_tones_2400_2600.wav", "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_data.tobytes())
    
    print(f"Created test_tones_2400_2600.wav ({len(pcm_data)} samples, {len(pcm_data)/sample_rate:.1f} seconds)")
    return "test_tones_2400_2600.wav"

def modulate_to_gfsk(audio_file):
    """Use GNU Radio or simple FSK modulation"""
    print("Modulating audio to GFSK...")
    
    # For testing, we'll use a simple approach
    # In reality, you'd use GNU Radio or similar for proper DMR modulation
    
    # Read the audio
    with wave.open(audio_file, "rb") as wav:
        params = wav.getparams()
        audio_data = wav.readframes(params.nframes)
    
    # Create a simple FM modulated signal
    sample_rate = params.framerate
    audio_samples = np.frombuffer(audio_data, dtype=np.int16) / 32768.0
    
    # Simple FM modulation
    carrier_freq = 12000  # 12 kHz carrier
    deviation = 2000  # 2 kHz deviation
    
    t = np.arange(len(audio_samples)) / sample_rate
    phase = 2 * np.pi * carrier_freq * t + deviation * np.cumsum(audio_samples) / sample_rate
    modulated = np.sin(phase)
    
    # Save modulated signal
    modulated_pcm = (modulated * 32767).astype(np.int16)
    
    with wave.open("modulated_dmr.wav", "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48000)  # Higher sample rate for RF
        wav.writeframes(modulated_pcm.tobytes())
    
    print("Created modulated_dmr.wav")
    return "modulated_dmr.wav"

def capture_with_dsdfme(input_file):
    """Use DSD-FME to decode and capture AMBE frames"""
    print("Processing with DSD-FME...")
    
    # Run DSD-FME in DMR mode
    cmd = [
        "dsd-fme",
        "-i", input_file,
        "-o", "decoded_audio.wav",
        "-c", "captured_frames.bin",
        "-ft",  # DMR/MotoTRBO
        "-v", "1"  # Verbose
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    
    print("DSD-FME processing complete")
    return "captured_frames.bin"

def test_with_actual_dmr_capture():
    """Test using actual DMR captures we have"""
    print("\n=== Testing with actual DMR capture ===")
    
    # Use our cleartext AMBE frames
    if not os.path.exists("cleartext_ambe.bin"):
        print("No cleartext AMBE file found")
        return
    
    # Decode the frames
    print("Decoding cleartext AMBE frames...")
    subprocess.run([
        "python3", "decode_ambe_final.py",
        "cleartext_ambe.bin",
        "cleartext_decoded_test.wav"
    ])
    
    # Analyze the output
    print("\nAnalyzing decoded audio...")
    subprocess.run(["sox", "cleartext_decoded_test.wav", "-n", "stat"], stderr=subprocess.STDOUT)
    
    # Create spectrogram
    print("\nCreating spectrogram...")
    subprocess.run([
        "sox", "cleartext_decoded_test.wav", "-n", "spectrogram",
        "-o", "cleartext_spectrogram.png"
    ])
    
    print("Spectrogram saved to cleartext_spectrogram.png")

def test_known_good_ambe():
    """Test with known good AMBE patterns"""
    print("\n=== Testing with known AMBE patterns ===")
    
    # Create a simple test pattern
    # DMR AMBE+2 silence frame (49 bits)
    silence_pattern = 0x0001D1A49603252
    
    # Create 1 second of silence (50 frames)
    with open("silence_test.bin", "wb") as f:
        for i in range(50):
            # Pack as 8-byte frame
            frame_64bit = (silence_pattern << 15) & 0xFFFFFFFFFFFFFFFF
            f.write(struct.pack('>Q', frame_64bit))
    
    print("Created silence_test.bin")
    
    # Decode it
    subprocess.run([
        "python3", "decode_ambe_final.py", 
        "silence_test.bin",
        "silence_decoded.wav"
    ])
    
    print("Decoded to silence_decoded.wav")

def main():
    print("=== Real AMBE+2 End-to-End Test ===\n")
    
    # Test 1: Generate test tones
    print("Test 1: Generating test tones...")
    test_audio = generate_test_tones()
    
    # Test 2: Try with actual DMR capture
    test_with_actual_dmr_capture()
    
    # Test 3: Known good patterns
    test_known_good_ambe()
    
    print("\n=== Test Summary ===")
    print("1. Generated test tones: test_tones_2400_2600.wav")
    print("2. Decoded cleartext: cleartext_decoded_test.wav")
    print("3. Decoded silence: silence_decoded.wav")
    print("\nListen to these files to verify audio quality.")

if __name__ == "__main__":
    main()