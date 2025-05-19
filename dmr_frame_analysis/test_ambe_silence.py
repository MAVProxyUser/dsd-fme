#!/usr/bin/env python3
"""Test AMBE decoding with known silence frames"""

import struct

# DMR silence frame pattern (from Motorola spec)
# This is the standard AMBE+2 silence frame
SILENCE_FRAME_49BIT = 0x00E8D24B019291  # 49-bit silence pattern

def create_silence_frames():
    """Create AMBE silence frames in both 8-byte and 7-byte formats"""
    
    # Create 100 silence frames (2 seconds)
    num_frames = 100
    
    # 8-byte format (as stored in cleartext database)
    with open("silence_8byte.bin", "wb") as f:
        for i in range(num_frames):
            # Pack as 64-bit with silence pattern in upper 49 bits
            frame_64bit = SILENCE_FRAME_49BIT << 15
            f.write(struct.pack('>Q', frame_64bit))
    
    # 7-byte format for decoder
    with open("silence_7byte.bin", "wb") as f:
        for i in range(num_frames):
            # Pack 49 bits into 7 bytes
            bytes_7 = []
            
            # First 48 bits
            for j in range(6):
                shift = 48 - 8 - (j * 8)
                byte_val = (SILENCE_FRAME_49BIT >> shift) & 0xFF
                bytes_7.append(byte_val)
            
            # 49th bit in MSB of 7th byte
            bit_49 = (SILENCE_FRAME_49BIT >> 0) & 0x01
            bytes_7.append(bit_49 << 7)
            
            f.write(bytes(bytes_7))
    
    print(f"Created {num_frames} silence frames")
    print("Files: silence_8byte.bin, silence_7byte.bin")
    
    # Also create frames using actual cleartext pattern
    # Take the quietest frame from cleartext as reference
    quiet_frame = 0x001063D94023F000  # A low-energy frame from cleartext
    
    with open("quiet_7byte.bin", "wb") as f:
        for i in range(num_frames):
            # Convert to 7-byte format
            bytes_7 = []
            for j in range(6):
                shift = 56 - (j * 8)
                byte_val = (quiet_frame >> shift) & 0xFF
                bytes_7.append(byte_val)
            
            # Get bit 49 (actually bit 15 from right in 64-bit)
            bit_49 = (quiet_frame >> 15) & 0x01
            bytes_7.append(bit_49 << 7)
            
            f.write(bytes(bytes_7))
    
    print("Created quiet_7byte.bin with low-energy cleartext pattern")

if __name__ == "__main__":
    create_silence_frames()