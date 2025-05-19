#!/usr/bin/env python3
"""
Test AMBE decoding by creating proper DMR frames for DSD-FME
"""

import struct
import numpy as np
import wave
import subprocess
import os

def create_dmr_frame_stream():
    """Create a DMR frame stream that DSD-FME can decode"""
    
    # Read our cleartext AMBE frames
    with open("cleartext_ambe.bin", "rb") as f:
        ambe_data = f.read()
    
    # Create a simple DMR frame structure
    # DMR frame = sync pattern + slot data + AMBE frames
    
    # DMR sync patterns
    DMR_DATA_SYNC = bytes.fromhex("D5D7F77FD757")  # DMR data sync
    DMR_VOICE_SYNC = bytes.fromhex("755FD7DF75F7")  # DMR voice sync
    
    with open("dmr_test_stream.bin", "wb") as out:
        frame_count = 0
        
        # Process AMBE frames in groups of 3 (one DMR slot)
        for i in range(0, len(ambe_data), 24):  # 3 frames * 8 bytes
            if i + 24 > len(ambe_data):
                break
            
            # Get 3 AMBE frames
            ambe1 = ambe_data[i:i+8]
            ambe2 = ambe_data[i+8:i+16]
            ambe3 = ambe_data[i+16:i+24]
            
            # Write sync pattern
            if frame_count % 6 == 0:
                out.write(DMR_DATA_SYNC)
            else:
                out.write(DMR_VOICE_SYNC)
            
            # Write AMBE frames
            out.write(ambe1)
            out.write(ambe2)
            out.write(ambe3)
            
            frame_count += 1
    
    print(f"Created dmr_test_stream.bin with {frame_count} DMR frames")
    return "dmr_test_stream.bin"

def test_dsd_fme_decode(input_file):
    """Test decoding with DSD-FME"""
    
    print(f"\nTesting DSD-FME decode of {input_file}...")
    
    # Run DSD-FME
    cmd = [
        "dsd-fme",
        "-i", input_file,
        "-o", "dsd_decoded.wav",
        "-ft",  # DMR/MotoTRBO
        "-v", "1"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("DSD-FME decode successful")
        if os.path.exists("dsd_decoded.wav"):
            # Analyze output
            result = subprocess.run(["sox", "dsd_decoded.wav", "-n", "stat"], 
                                  capture_output=True, text=True, stderr=subprocess.STDOUT)
            print("\nDecoded audio stats:")
            print(result.stdout)
    else:
        print(f"DSD-FME error: {result.stderr}")

def create_test_with_sox():
    """Create test tones using SoX"""
    
    print("\nCreating test tones with SoX...")
    
    # Create 2400 Hz tone
    subprocess.run([
        "sox", "-n", "tone_2400.wav",
        "synth", "3", "sine", "2400",
        "trim", "0", "3"
    ])
    
    # Create 2600 Hz tone
    subprocess.run([
        "sox", "-n", "tone_2600.wav",
        "synth", "3", "sine", "2600",
        "trim", "0", "3"
    ])
    
    # Concatenate tones
    subprocess.run([
        "sox", "tone_2400.wav", "tone_2600.wav",
        "tone_2400.wav", "tone_2600.wav",
        "test_tones_sox.wav"
    ])
    
    print("Created test_tones_sox.wav")
    return "test_tones_sox.wav"

def extract_ambe_from_dsd_log():
    """Extract AMBE frames from DSD-FME log output"""
    
    print("\nExtracting AMBE from DSD-FME log...")
    
    # Run DSD-FME with verbose output to capture AMBE frames
    subprocess.run([
        "dsd-fme",
        "-i", "cleartext_ambe.bin",
        "-v", "4",  # Maximum verbosity
        "-ft"       # DMR mode
    ], stdout=open("dsd_verbose.log", "w"), stderr=subprocess.STDOUT)
    
    # Parse log for AMBE data
    with open("dsd_verbose.log", "r") as f:
        log_data = f.read()
    
    # Look for AMBE frame patterns in log
    print("Checking DSD-FME log for AMBE patterns...")

def test_codec2_alternative():
    """Test with Codec2 as alternative vocoder"""
    
    print("\nTesting Codec2 vocoder...")
    
    # Check if codec2 is available
    result = subprocess.run(["which", "c2enc"], capture_output=True)
    if result.returncode != 0:
        print("Codec2 not found. Install with: apt-get install codec2")
        return
    
    # Create test audio
    test_audio = create_test_with_sox()
    
    # Encode with Codec2 450 mode (similar to AMBE+2)
    subprocess.run([
        "c2enc", "450", test_audio, "test_codec2.c2"
    ])
    
    # Decode back
    subprocess.run([
        "c2dec", "450", "test_codec2.c2", "test_codec2_decoded.wav"
    ])
    
    print("Created test_codec2_decoded.wav")
    
    # Compare spectrograms
    for wav in [test_audio, "test_codec2_decoded.wav"]:
        spec_file = wav.replace(".wav", "_spec.png")
        subprocess.run([
            "sox", wav, "-n", "spectrogram",
            "-o", spec_file
        ])
        print(f"Spectrogram: {spec_file}")

def main():
    print("=== DMR/AMBE Test Suite ===\n")
    
    # Test 1: Create DMR frame stream
    dmr_stream = create_dmr_frame_stream()
    
    # Test 2: Try decoding with DSD-FME
    test_dsd_fme_decode(dmr_stream)
    
    # Test 3: Create known test tones
    test_tones = create_test_with_sox()
    
    # Test 4: Extract AMBE from verbose log
    extract_ambe_from_dsd_log()
    
    # Test 5: Try alternative vocoder
    test_codec2_alternative()
    
    print("\n=== Test Complete ===")
    print("Check the following files:")
    print("1. dmr_test_stream.bin - DMR frame stream")
    print("2. dsd_decoded.wav - DSD-FME decoded audio (if successful)")
    print("3. test_tones_sox.wav - Reference test tones")
    print("4. test_codec2_decoded.wav - Codec2 test (if available)")

if __name__ == "__main__":
    main()