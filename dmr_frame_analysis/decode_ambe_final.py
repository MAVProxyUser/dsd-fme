#!/usr/bin/env python3
"""Decode AMBE frames using correct bit extraction"""

import struct
import subprocess
import numpy as np

def extract_ambe_49bit(frame_8byte):
    """Extract 49-bit AMBE from 8-byte frame"""
    frame_64bit = struct.unpack('>Q', frame_8byte)[0]
    # AMBE is in bits 63-15
    ambe_49bit = frame_64bit >> 15
    return ambe_49bit

def pack_ambe_7byte(ambe_49bit):
    """Pack 49-bit AMBE into 7 bytes for mbelib"""
    bytes_7 = []
    
    # Extract bits MSB first
    bit_array = []
    for i in range(48, -1, -1):
        bit = (ambe_49bit >> i) & 1
        bit_array.append(bit)
    
    # Pack first 6 bytes
    for i in range(6):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bit_array[i*8 + j]
        bytes_7.append(byte_val)
    
    # 7th byte gets bit 49 in MSB
    bytes_7.append(bit_array[48] << 7)
    
    return bytes(bytes_7)

def decode_ambe_file(input_file, output_file):
    """Decode AMBE file to audio"""
    
    # First convert 8-byte to 7-byte format
    temp_7byte = input_file + ".7byte"
    
    with open(input_file, "rb") as f_in:
        with open(temp_7byte, "wb") as f_out:
            frame_count = 0
            while True:
                frame_8byte = f_in.read(8)
                if len(frame_8byte) < 8:
                    break
                
                ambe_49bit = extract_ambe_49bit(frame_8byte)
                frame_7byte = pack_ambe_7byte(ambe_49bit)
                f_out.write(frame_7byte)
                frame_count += 1
                
                if frame_count <= 3:
                    print(f"Frame {frame_count}:")
                    print(f"  8-byte: {frame_8byte.hex()}")
                    print(f"  49-bit: 0x{ambe_49bit:013X}")
                    print(f"  7-byte: {frame_7byte.hex()}")
    
    print(f"\nConverted {frame_count} frames to 7-byte format")
    
    # Now decode with mbelib
    print(f"Decoding with mbelib...")
    subprocess.run([
        "./decode_mbelib_correct",
        temp_7byte,
        output_file
    ])
    
    print(f"Decoded audio saved to {output_file}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.bin output.wav")
        sys.exit(1)
    
    decode_ambe_file(sys.argv[1], sys.argv[2])
