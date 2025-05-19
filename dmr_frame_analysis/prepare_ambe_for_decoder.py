#!/usr/bin/env python3
"""Prepare AMBE frames for decoding with md380_vocoder"""

import sqlite3
import struct
import subprocess
import os

def prepare_ambe_frames():
    """Extract and prepare AMBE frames for the md380_vocoder decoder"""
    
    print("=== PREPARING AMBE FRAMES FOR MD380 VOCODER ===")
    
    # The md380_vocoder expects AMBE frames in specific format
    # According to the repo, it handles AMBE+2 frames from MD380/DMR
    
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn = sqlite3.connect(cleartext_db)
    cursor = conn.cursor()
    
    # Get cleartext AMBE frames
    cursor.execute("SELECT ambe_hex FROM U_00000000_S0 ORDER BY id")
    ambe_frames = [row[0] for row in cursor.fetchall()]
    
    print(f"\nFound {len(ambe_frames)} cleartext AMBE frames")
    
    # MD380 vocoder expects binary format
    # Each AMBE frame is 49 bits, but stored as 64-bit (8 bytes)
    
    # Create binary file for vocoder
    ambe_binary_file = "cleartext_ambe.bin"
    pcm_output_file = "decoded_audio.raw"
    
    print(f"\nWriting AMBE frames to {ambe_binary_file}")
    
    with open(ambe_binary_file, 'wb') as f:
        for frame_hex in ambe_frames:
            # Convert hex to binary
            # MD380 format might expect specific byte ordering
            frame_int = int(frame_hex, 16)
            
            # Try different byte arrangements for MD380
            # Option 1: Big-endian 8 bytes
            frame_bytes = frame_int.to_bytes(8, byteorder='big')
            f.write(frame_bytes)
    
    print(f"Wrote {len(ambe_frames)} frames ({len(ambe_frames) * 8} bytes)")
    
    # Also create a format with just 49 bits (7 bytes) per frame
    ambe_49bit_file = "cleartext_ambe_49bit.bin"
    
    with open(ambe_49bit_file, 'wb') as f:
        for frame_hex in ambe_frames:
            frame_int = int(frame_hex, 16)
            # Take only 49 bits (7 bytes)
            frame_bytes = frame_int.to_bytes(7, byteorder='big')
            f.write(frame_bytes)
    
    print(f"Also created 49-bit format: {ambe_49bit_file}")
    
    # Create frame-by-frame files for testing
    test_dir = "ambe_test_frames"
    os.makedirs(test_dir, exist_ok=True)
    
    print(f"\nCreating individual test frames in {test_dir}/")
    
    for i, frame_hex in enumerate(ambe_frames[:10]):  # First 10 for testing
        frame_file = f"{test_dir}/frame_{i:04d}.bin"
        with open(frame_file, 'wb') as f:
            frame_int = int(frame_hex, 16)
            frame_bytes = frame_int.to_bytes(8, byteorder='big')
            f.write(frame_bytes)
    
    # Create C header format for md380_vocoder
    print("\nCreating C array format for md380_vocoder testing")
    
    with open("ambe_frames.h", 'w') as f:
        f.write("// AMBE frames from cleartext capture\n")
        f.write(f"// Total frames: {len(ambe_frames)}\n\n")
        f.write("const unsigned char ambe_frames[] = {\n")
        
        for i, frame_hex in enumerate(ambe_frames[:100]):  # First 100
            frame_int = int(frame_hex, 16)
            frame_bytes = frame_int.to_bytes(8, byteorder='big')
            
            hex_str = ', '.join(f'0x{b:02x}' for b in frame_bytes)
            f.write(f"    {hex_str},  // Frame {i}\n")
        
        f.write("};\n")
        f.write(f"\nconst int num_frames = {min(100, len(ambe_frames))};\n")
    
    # Analyze frame structure for MD380 compatibility
    print("\n=== MD380 COMPATIBILITY ANALYSIS ===")
    
    # Check if frames match MD380 expectations
    print("\nFirst 5 frames (hex and binary):")
    for i, frame_hex in enumerate(ambe_frames[:5]):
        frame_int = int(frame_hex, 16)
        frame_bin = bin(frame_int)[2:].zfill(64)
        
        print(f"\nFrame {i}: {frame_hex}")
        print(f"  Binary: {frame_bin}")
        print(f"  Bits 0-48 (AMBE data): {frame_bin[:49]}")
        print(f"  Bits 49-63 (padding): {frame_bin[49:]}")
    
    # Create a script to build and run md380_vocoder
    print("\nCreating build script for md380_vocoder")
    
    with open("decode_with_md380.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Script to decode AMBE using md380_vocoder\n\n")
        f.write("# Clone md380_vocoder if not present\n")
        f.write("if [ ! -d 'md380_vocoder' ]; then\n")
        f.write("    git clone https://github.com/nostar/md380_vocoder.git\n")
        f.write("fi\n\n")
        f.write("# Build the vocoder\n")
        f.write("cd md380_vocoder\n")
        f.write("make\n\n")
        f.write("# Run decoder on our AMBE frames\n")
        f.write("# Note: May need to adjust parameters based on md380_vocoder usage\n")
        f.write("./md380_vocoder < ../cleartext_ambe.bin > ../decoded_audio.raw\n")
        f.write("\n# Convert raw PCM to WAV\n")
        f.write("sox -r 8000 -e signed -b 16 -c 1 ../decoded_audio.raw ../decoded_audio.wav\n")
    
    os.chmod("decode_with_md380.sh", 0o755)
    
    conn.close()
    
    print("\n=== NEXT STEPS ===")
    print("1. Run: ./decode_with_md380.sh")
    print("2. This will:")
    print("   - Clone md380_vocoder")
    print("   - Build the decoder")
    print("   - Decode AMBE frames to raw PCM")
    print("   - Convert to WAV for playback")
    print("\n3. Files created:")
    print(f"   - {ambe_binary_file} (8 bytes/frame)")
    print(f"   - {ambe_49bit_file} (7 bytes/frame)")
    print(f"   - {test_dir}/ (individual frames)")
    print(f"   - ambe_frames.h (C header format)")
    print(f"   - decode_with_md380.sh (build/run script)")
    
    print("\n4. If decoding succeeds with cleartext,")
    print("   we can use the same process on decrypted frames!")

if __name__ == "__main__":
    prepare_ambe_frames()