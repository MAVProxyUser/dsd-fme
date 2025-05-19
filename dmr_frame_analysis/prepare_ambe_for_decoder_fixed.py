#!/usr/bin/env python3
"""Prepare AMBE frames for decoding with md380_vocoder - FIXED"""

import sqlite3
import struct
import subprocess
import os

def prepare_ambe_frames():
    """Extract and prepare AMBE frames for the md380_vocoder decoder"""
    
    print("=== PREPARING AMBE FRAMES FOR MD380 VOCODER ===")
    
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn = sqlite3.connect(cleartext_db)
    cursor = conn.cursor()
    
    # Get cleartext AMBE frames
    cursor.execute("SELECT ambe_hex FROM U_00000000_S0 ORDER BY id")
    ambe_frames = [row[0] for row in cursor.fetchall()]
    
    print(f"\nFound {len(ambe_frames)} cleartext AMBE frames")
    
    # First, let's check the actual size of our frames
    print("\nChecking frame sizes:")
    for i, frame_hex in enumerate(ambe_frames[:5]):
        frame_int = int(frame_hex, 16)
        bit_length = frame_int.bit_length()
        print(f"Frame {i}: {frame_hex} = {bit_length} bits")
    
    # Create binary file for vocoder
    ambe_binary_file = "cleartext_ambe.bin"
    
    print(f"\nWriting AMBE frames to {ambe_binary_file}")
    
    with open(ambe_binary_file, 'wb') as f:
        for frame_hex in ambe_frames:
            # Convert hex to binary - handle as 8 bytes
            frame_int = int(frame_hex, 16)
            frame_bytes = frame_int.to_bytes(8, byteorder='big')
            f.write(frame_bytes)
    
    print(f"Wrote {len(ambe_frames)} frames ({len(ambe_frames) * 8} bytes)")
    
    # For 49-bit format, we need to handle the overflow properly
    ambe_49bit_file = "cleartext_ambe_49bit.bin"
    
    print(f"\nCreating 49-bit format: {ambe_49bit_file}")
    
    with open(ambe_49bit_file, 'wb') as f:
        for frame_hex in ambe_frames:
            frame_int = int(frame_hex, 16)
            
            # Extract only the lower 49 bits
            frame_49bit = frame_int & ((1 << 49) - 1)  # Mask to 49 bits
            
            # Now we can safely convert to 7 bytes
            if frame_49bit.bit_length() <= 56:  # 7 bytes = 56 bits
                frame_bytes = frame_49bit.to_bytes(7, byteorder='big')
                f.write(frame_bytes)
            else:
                print(f"Warning: Frame still too large after masking: {frame_49bit:x}")
    
    # MD380 expects specific format - let's check
    print("\n=== MD380 FORMAT ANALYSIS ===")
    
    # According to MD380, AMBE+2 frames are 49 bits
    # But our frames are 64 bits - let's see the structure
    
    print("\nAnalyzing frame structure:")
    for i, frame_hex in enumerate(ambe_frames[:3]):
        frame_int = int(frame_hex, 16)
        frame_bin = bin(frame_int)[2:].zfill(64)
        
        print(f"\nFrame {i}: {frame_hex}")
        print(f"  Binary (64-bit): {frame_bin}")
        print(f"  Upper 15 bits:   {frame_bin[:15]}")
        print(f"  Lower 49 bits:   {frame_bin[15:]}")
        
        # Check which bits are typically set
        upper_bits = (frame_int >> 49) & 0x7FFF  # Upper 15 bits
        lower_bits = frame_int & ((1 << 49) - 1)  # Lower 49 bits
        
        print(f"  Upper value: 0x{upper_bits:04X}")
        print(f"  Lower value: 0x{lower_bits:013X}")
    
    # Create test files with different bit arrangements
    test_formats = [
        ("format_64bit.bin", 8, lambda x: x),  # Original 64-bit
        ("format_49bit_lower.bin", 7, lambda x: x & ((1 << 49) - 1)),  # Lower 49 bits
        ("format_49bit_shifted.bin", 7, lambda x: (x >> 15) & ((1 << 49) - 1)),  # Shifted
    ]
    
    for filename, byte_size, transform in test_formats:
        print(f"\nCreating {filename}")
        try:
            with open(filename, 'wb') as f:
                for frame_hex in ambe_frames[:100]:  # First 100 for testing
                    frame_int = int(frame_hex, 16)
                    transformed = transform(frame_int)
                    
                    if transformed.bit_length() <= byte_size * 8:
                        frame_bytes = transformed.to_bytes(byte_size, byteorder='big')
                        f.write(frame_bytes)
                    else:
                        print(f"  Skipping frame - too large: {transformed:x}")
        except Exception as e:
            print(f"  Error: {e}")
    
    # Create build script
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
        f.write("# Test different formats\n")
        f.write("echo 'Testing 64-bit format:'\n")
        f.write("./md380_vocoder < ../format_64bit.bin > ../decoded_64bit.raw\n")
        f.write("echo 'Testing 49-bit lower format:'\n")
        f.write("./md380_vocoder < ../format_49bit_lower.bin > ../decoded_49bit.raw\n")
        f.write("\n# Convert to WAV\n")
        f.write("for file in ../*.raw; do\n")
        f.write("    sox -r 8000 -e signed -b 16 -c 1 \"$file\" \"${file%.raw}.wav\"\n")
        f.write("done\n")
    
    os.chmod("decode_with_md380.sh", 0o755)
    
    conn.close()
    
    print("\n=== SUMMARY ===")
    print("Fixed the overflow error!")
    print("Created multiple format options to test with md380_vocoder")
    print("\nRun: ./decode_with_md380.sh")
    print("This will test different bit arrangements to find the correct format")

if __name__ == "__main__":
    prepare_ambe_frames()