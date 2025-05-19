#!/usr/bin/env python3
"""Correct AMBE frame handling based on dsd-fme source code"""

import struct
import numpy as np

def debug_ambe_format():
    """Debug the AMBE format from our captures"""
    
    # Read first few AMBE frames from cleartext
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read(80)  # First 10 frames
    
    print("=== Cleartext AMBE Frame Analysis ===\n")
    
    for i in range(10):
        frame_8byte = data[i*8:(i+1)*8]
        frame_64bit = struct.unpack('>Q', frame_8byte)[0]
        
        # The actual AMBE data is in bits 63-15 (49 bits total)
        # The lower 15 bits are padding/status
        ambe_49bit = frame_64bit >> 15
        status_bits = frame_64bit & 0x7FFF
        
        print(f"Frame {i+1}:")
        print(f"  Raw 8-byte: {frame_8byte.hex()}")
        print(f"  64-bit:     0x{frame_64bit:016X}")
        print(f"  AMBE 49bit: 0x{ambe_49bit:013X}")
        print(f"  Status:     0x{status_bits:04X}")
        print(f"  Binary:     {bin(ambe_49bit)[2:].zfill(49)}")
        print()
    
    # Now let's see how dsd-fme would unpack this
    print("=== DSD-FME Style Unpacking ===\n")
    
    frame_8byte = data[0:8]
    frame_64bit = struct.unpack('>Q', frame_8byte)[0]
    
    # Method 1: Direct bit extraction (what we should use)
    ambe_bits = []
    for i in range(64, 15, -1):  # Bits 63 down to 16
        bit = (frame_64bit >> (i-1)) & 1
        ambe_bits.append(bit)
    
    print(f"Direct extraction (49 bits): {ambe_bits[:10]}...")
    
    # Method 2: Byte-wise extraction matching dsd-fme pack_ambe
    bytes_7 = []
    bit_array = []
    
    # Extract bits MSB first for the upper 49 bits
    for i in range(63, 14, -1):  # 49 bits from position 63 to 15
        bit = (frame_64bit >> i) & 1
        bit_array.append(bit)
    
    # Pack into 7 bytes
    for i in range(6):  # First 6 bytes get 8 bits each
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bit_array[i*8 + j]
        bytes_7.append(byte_val)
    
    # 7th byte gets the 49th bit in MSB
    bytes_7.append(bit_array[48] << 7)
    
    print(f"Packed 7-byte: {bytes(bytes_7).hex()}")
    
    # Let's verify this matches our original conversion
    with open("cleartext_ambe_7byte_fixed.bin", "rb") as f:
        fixed_7byte = f.read(7)
    
    print(f"Our fixed:     {fixed_7byte.hex()}")
    print(f"Match: {bytes(bytes_7) == fixed_7byte}")

def create_correct_decoder():
    """Create a decoder that properly handles AMBE frames"""
    decoder_code = '''#!/usr/bin/env python3
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
    
    print(f"\\nConverted {frame_count} frames to 7-byte format")
    
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
'''
    
    with open("decode_ambe_final.py", "w") as f:
        f.write(decoder_code)
    
    print("Created decode_ambe_final.py")

if __name__ == "__main__":
    debug_ambe_format()
    create_correct_decoder()