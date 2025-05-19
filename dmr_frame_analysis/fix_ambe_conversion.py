#!/usr/bin/env python3
"""Fix AMBE 8-byte to 7-byte conversion with correct bit mapping"""

import struct

def debug_frame_conversion():
    """Debug the bit mapping between 8-byte and 7-byte formats"""
    
    # Test with known cleartext frame
    test_frame_8byte = bytes.fromhex("1A4C0F6000AF9000")
    frame_64bit = struct.unpack('>Q', test_frame_8byte)[0]
    
    print(f"8-byte frame: {test_frame_8byte.hex()}")
    print(f"64-bit value: 0x{frame_64bit:016X}")
    print(f"Binary: {bin(frame_64bit)[2:].zfill(64)}")
    
    # Extract AMBE bits (bits 63-15, total 49 bits)
    ambe_49bit = frame_64bit >> 15
    print(f"\n49-bit AMBE: 0x{ambe_49bit:013X}")
    print(f"Binary: {bin(ambe_49bit)[2:].zfill(49)}")
    
    # Method 1: Direct 7-byte packing
    bytes_7_v1 = []
    for i in range(7):
        if i < 6:
            # First 6 bytes get 8 bits each
            shift = 41 - (i * 8)  # 41 = 49 - 8
            byte_val = (ambe_49bit >> shift) & 0xFF
        else:
            # 7th byte gets remaining bit in MSB
            byte_val = (ambe_49bit & 0x01) << 7
        bytes_7_v1.append(byte_val)
    
    print(f"\nMethod 1 (direct): {bytes(bytes_7_v1).hex()}")
    
    # Method 2: Following dsd-fme unpack_ambe logic
    bytes_7_v2 = []
    bit_array = []
    
    # Convert to bit array (MSB first)
    for i in range(49):
        bit = (ambe_49bit >> (48 - i)) & 0x01
        bit_array.append(bit)
    
    # Pack into bytes
    for i in range(6):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bit_array[i*8 + j]
        bytes_7_v2.append(byte_val)
    
    # Last byte gets bit 48 in MSB
    bytes_7_v2.append(bit_array[48] << 7)
    
    print(f"Method 2 (bit array): {bytes(bytes_7_v2).hex()}")
    
    # Test reverse conversion
    print("\nReverse conversion test:")
    reverse_bits = []
    for i in range(6):
        byte_val = bytes_7_v2[i]
        for j in range(8):
            bit = (byte_val >> (7-j)) & 0x01
            reverse_bits.append(bit)
    
    # Add 49th bit
    reverse_bits.append((bytes_7_v2[6] >> 7) & 0x01)
    
    # Convert back to integer
    reverse_49bit = 0
    for i, bit in enumerate(reverse_bits):
        reverse_49bit = (reverse_49bit << 1) | bit
    
    print(f"Reversed 49-bit: 0x{reverse_49bit:013X}")
    print(f"Match: {reverse_49bit == ambe_49bit}")

def convert_cleartext_correct():
    """Convert cleartext AMBE with correct bit mapping"""
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    with open("cleartext_ambe_7byte_fixed.bin", "wb") as out:
        frame_count = 0
        
        for i in range(0, len(data), 8):
            if i + 8 <= len(data):
                # Read 8-byte frame
                frame_8 = data[i:i+8]
                frame_64bit = struct.unpack('>Q', frame_8)[0]
                
                # Extract 49-bit AMBE (bits 63-15)
                ambe_49bit = frame_64bit >> 15
                
                # Convert to bit array
                bit_array = []
                for j in range(49):
                    bit = (ambe_49bit >> (48 - j)) & 0x01
                    bit_array.append(bit)
                
                # Pack into 7 bytes
                bytes_7 = []
                
                # First 6 bytes (48 bits)
                for j in range(6):
                    byte_val = 0
                    for k in range(8):
                        byte_val = (byte_val << 1) | bit_array[j*8 + k]
                    bytes_7.append(byte_val)
                
                # 7th byte (49th bit in MSB)
                bytes_7.append(bit_array[48] << 7)
                
                out.write(bytes(bytes_7))
                frame_count += 1
                
                # Debug first few frames
                if frame_count <= 3:
                    print(f"\nFrame {frame_count}:")
                    print(f"  8-byte: {frame_8.hex()}")
                    print(f"  49-bit: 0x{ambe_49bit:013X}")
                    print(f"  7-byte: {bytes(bytes_7).hex()}")
        
        print(f"\nConverted {frame_count} frames to cleartext_ambe_7byte_fixed.bin")

if __name__ == "__main__":
    print("Debugging AMBE frame conversion...")
    debug_frame_conversion()
    
    print("\n" + "="*50)
    print("Converting cleartext with fixed bit mapping...")
    convert_cleartext_correct()