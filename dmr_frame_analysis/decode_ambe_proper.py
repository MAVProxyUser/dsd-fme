#!/usr/bin/env python3
"""Decode AMBE frames using the proper pack_ambe format from dsd-fme"""

import struct

# Using the unpack_ambe logic from dsd_file.c
def convert_64bit_to_7byte(ambe_64bit):
    """Convert 64-bit AMBE to 7-byte format for decoder"""
    # Extract the 7-byte (49-bit AMBE + padding)
    bytes_7 = []
    
    # Process first 6 bytes (48 bits)
    for i in range(6):
        shift = 56 - (i * 8)
        byte_val = (ambe_64bit >> shift) & 0xFF
        bytes_7.append(byte_val)
    
    # Process last byte (1 bit + 7 bits padding)
    last_bit = (ambe_64bit >> 8) & 0x01
    bytes_7.append(last_bit << 7)  # Put the 49th bit in MSB position
    
    return bytes(bytes_7)

def main():
    # Process cleartext AMBE file
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Output file for 7-byte AMBE frames
    with open("cleartext_ambe_7byte.bin", "wb") as out:
        frame_count = 0
        for i in range(0, len(data), 8):
            if i + 8 <= len(data):
                # Read 8-byte frame
                frame_8 = data[i:i+8]
                ambe_64bit = struct.unpack('>Q', frame_8)[0]  # Big-endian 64-bit
                
                # Convert to 7-byte format
                frame_7 = convert_64bit_to_7byte(ambe_64bit)
                out.write(frame_7)
                
                frame_count += 1
                
                # Debug first few frames
                if frame_count <= 5:
                    print(f"Frame {frame_count}:")
                    print(f"  8-byte: {' '.join(f'{b:02X}' for b in frame_8)}")
                    print(f"  64-bit: {ambe_64bit:016X}")
                    print(f"  7-byte: {' '.join(f'{b:02X}' for b in frame_7)}")
                    print()
    
    print(f"Converted {frame_count} frames to 7-byte format")
    print("Output: cleartext_ambe_7byte.bin")

if __name__ == "__main__":
    main()