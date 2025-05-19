#!/usr/bin/env python3
"""Create known AMBE test patterns based on DMR standards"""

import struct
import numpy as np

# Known AMBE+2 patterns from DMR standard (49-bit values)
AMBE_SILENCE = 0x0001D1A49603252  # Standard silence frame (49 bits)
AMBE_TONE_1K = 0x014899908C416B4  # Approximation for 1kHz tone (49 bits)
AMBE_DTMF_1 = 0x02694B916838FC4  # DTMF digit 1 pattern (49 bits)

def create_test_pattern():
    """Create test AMBE pattern file"""
    
    # Create pattern: silence, tone, DTMF, silence
    pattern = [
        AMBE_SILENCE,  # 100 frames of silence
        AMBE_TONE_1K,  # 100 frames of 1kHz tone  
        AMBE_DTMF_1,   # 100 frames of DTMF
        AMBE_SILENCE   # 100 frames of silence
    ]
    
    with open("test_pattern_ambe.bin", "wb") as f:
        for i, ambe_49bit in enumerate(pattern):
            # Repeat each pattern 100 times
            for j in range(100):
                # Pack into 8-byte format (49 bits in upper, 0 in lower)
                frame_64bit = (ambe_49bit << 15) & 0xFFFFFFFFFFFFFFFF
                f.write(struct.pack('>Q', frame_64bit))
    
    print("Created test_pattern_ambe.bin with known AMBE patterns")
    
    # Also create the 7-byte version directly
    with open("test_pattern_ambe_7byte.bin", "wb") as f:
        for i, ambe_49bit in enumerate(pattern):
            for j in range(100):
                # Pack 49 bits into 7 bytes
                bytes_7 = []
                
                # Extract bits MSB first
                for k in range(6):
                    shift = 41 - (k * 8)
                    byte_val = (ambe_49bit >> shift) & 0xFF
                    bytes_7.append(byte_val)
                
                # 7th byte gets bit 49 in MSB
                bytes_7.append((ambe_49bit & 0x01) << 7)
                
                f.write(bytes(bytes_7))
    
    print("Created test_pattern_ambe_7byte.bin")
    
    # Create a test with real AMBE frames from our cleartext
    print("\nExtracting real AMBE patterns from cleartext...")
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Find frames with different energy levels
    frames_by_energy = []
    
    for i in range(0, min(1000, len(data)), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            
            # Estimate "energy" from bit pattern
            ones = bin(frame_64bit).count('1')
            frames_by_energy.append((ones, frame))
    
    # Sort by energy
    frames_by_energy.sort(key=lambda x: x[0])
    
    # Create pattern with low, medium, high energy frames
    with open("real_pattern_ambe.bin", "wb") as f:
        # Low energy (quiet)
        for _ in range(50):
            f.write(frames_by_energy[10][1])
        
        # Medium energy
        for _ in range(50):
            f.write(frames_by_energy[len(frames_by_energy)//2][1])
        
        # High energy
        for _ in range(50):
            f.write(frames_by_energy[-10][1])
        
        # Back to low
        for _ in range(50):
            f.write(frames_by_energy[10][1])
    
    print("Created real_pattern_ambe.bin from actual cleartext frames")

if __name__ == "__main__":
    create_test_pattern()