#!/usr/bin/env python3
"""Test different AMBE formats with md380_vocoder"""

import sqlite3
import os
import subprocess

def test_md380_formats():
    """Test various AMBE format conversions for md380_vocoder"""
    
    print("=== TESTING MD380 VOCODER FORMATS ===")
    
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn = sqlite3.connect(cleartext_db)
    cursor = conn.cursor()
    
    # Get first few frames for testing
    cursor.execute("SELECT ambe_hex FROM U_00000000_S0 LIMIT 10")
    test_frames = [row[0] for row in cursor.fetchall()]
    
    print(f"\nTesting with {len(test_frames)} frames")
    
    # MD380 vocoder expects AMBE+2 format
    # AMBE+2 in DMR is typically:
    # - 49 bits of AMBE data
    # - Packed into specific format
    
    # Test different packing strategies
    test_strategies = {
        "dmr_standard": lambda hex_val: convert_dmr_to_ambe(hex_val),
        "raw_49bit": lambda hex_val: extract_49_bits(hex_val),
        "byte_reversed": lambda hex_val: reverse_bytes(hex_val),
        "bit_reversed": lambda hex_val: reverse_bits(hex_val)
    }
    
    for strategy_name, converter in test_strategies.items():
        output_file = f"test_{strategy_name}.ambe"
        print(f"\nTesting {strategy_name} format -> {output_file}")
        
        with open(output_file, 'wb') as f:
            for i, frame_hex in enumerate(test_frames):
                try:
                    converted = converter(frame_hex)
                    f.write(converted)
                    if i == 0:  # Show first conversion
                        print(f"  Frame 0: {frame_hex} -> {converted.hex()}")
                except Exception as e:
                    print(f"  Error on frame {i}: {e}")
    
    # Create test script
    with open("test_all_formats.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Test all AMBE format variations\n\n")
        f.write("# Build md380_vocoder first\n")
        f.write("if [ ! -d 'md380_vocoder' ]; then\n")
        f.write("    git clone https://github.com/nostar/md380_vocoder.git\n")
        f.write("    cd md380_vocoder && make && cd ..\n")
        f.write("fi\n\n")
        
        for strategy_name in test_strategies.keys():
            f.write(f"echo 'Testing {strategy_name}:'\n")
            f.write(f"./md380_vocoder/md380_vocoder < test_{strategy_name}.ambe > output_{strategy_name}.pcm 2> log_{strategy_name}.txt\n")
            f.write(f"echo 'Result:' && cat log_{strategy_name}.txt\n")
            f.write(f"echo 'PCM size:' && wc -c output_{strategy_name}.pcm\n")
            f.write(f"echo '---'\n\n")
    
    os.chmod("test_all_formats.sh", 0o755)
    
    conn.close()
    
    print("\n=== READY TO TEST ===")
    print("Run: ./test_all_formats.sh")
    print("This will test all format variations with md380_vocoder")
    print("\nCheck which format produces valid PCM output")

def convert_dmr_to_ambe(hex_val):
    """Convert DMR frame to AMBE+2 format"""
    # DMR uses specific bit packing for AMBE+2
    frame_int = int(hex_val, 16)
    
    # Standard DMR extracts 49 bits from specific positions
    # This is a guess based on DMR standards
    ambe_bits = frame_int & 0x1FFFFFFFFFFFF  # Lower 49 bits
    
    # Pack into bytes (49 bits = 7 bytes with padding)
    return ambe_bits.to_bytes(7, byteorder='big')

def extract_49_bits(hex_val):
    """Extract lower 49 bits"""
    frame_int = int(hex_val, 16)
    bits_49 = frame_int & ((1 << 49) - 1)
    return bits_49.to_bytes(7, byteorder='big')

def reverse_bytes(hex_val):
    """Reverse byte order"""
    frame_int = int(hex_val, 16)
    frame_bytes = frame_int.to_bytes(8, byteorder='big')
    return frame_bytes[::-1][:7]  # Reverse and take 7 bytes

def reverse_bits(hex_val):
    """Reverse bit order within bytes"""
    frame_int = int(hex_val, 16)
    frame_bytes = frame_int.to_bytes(8, byteorder='big')
    
    # Reverse bits in each byte
    reversed_bytes = bytes([int(bin(b)[2:].zfill(8)[::-1], 2) for b in frame_bytes])
    return reversed_bytes[:7]

if __name__ == "__main__":
    test_md380_formats()