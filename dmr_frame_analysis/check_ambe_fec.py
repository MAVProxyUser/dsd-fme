#!/usr/bin/env python3
"""
Check if AMBE frames need FEC processing before decoding
"""

import struct
import numpy as np

def analyze_ambe_structure():
    """Analyze the structure of AMBE frames from cleartext"""
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read(800)  # First 100 frames
    
    print("=== AMBE Frame Structure Analysis ===\n")
    
    for i in range(10):
        frame = data[i*8:(i+1)*8]
        frame_64bit = struct.unpack('>Q', frame)[0]
        
        # Break down the frame structure
        # DMR AMBE+2: 49 bits of vocoder data + 23 bits FEC = 72 bits total
        # But we only have 49 bits in our frames
        
        print(f"Frame {i+1}:")
        print(f"  Raw: {frame.hex()}")
        print(f"  64-bit: 0x{frame_64bit:016X}")
        
        # Extract different bit ranges
        upper_49 = frame_64bit >> 15
        lower_15 = frame_64bit & 0x7FFF
        
        print(f"  Upper 49 bits: 0x{upper_49:013X}")
        print(f"  Lower 15 bits: 0x{lower_15:04X}")
        
        # Check for patterns in lower bits
        print(f"  Binary lower: {bin(lower_15)[2:].zfill(15)}")
        print()
    
    # Check if lower bits have consistent patterns
    lower_bits_list = []
    for i in range(0, len(data), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            lower_15 = frame_64bit & 0x7FFF
            lower_bits_list.append(lower_15)
    
    # Analyze patterns
    unique_lower = set(lower_bits_list)
    print(f"Unique lower 15-bit patterns: {len(unique_lower)}")
    print(f"Most common values: {sorted(unique_lower)[:10]}")
    
    # Check if these might be sync/status bits
    bit_frequency = [0] * 15
    for value in lower_bits_list:
        for bit in range(15):
            if value & (1 << bit):
                bit_frequency[bit] += 1
    
    print("\nBit frequency in lower 15 bits:")
    for bit in range(15):
        freq = bit_frequency[bit] / len(lower_bits_list) * 100
        print(f"  Bit {bit:2d}: {freq:5.1f}%")

def check_hamming_fec():
    """Check if frames use Hamming FEC"""
    
    # DMR uses (10,6,3) Hamming code for FEC
    # Let's see if our frames show Hamming patterns
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read(80)  # First 10 frames
    
    print("\n=== Hamming FEC Check ===\n")
    
    for i in range(10):
        frame = data[i*8:(i+1)*8]
        frame_64bit = struct.unpack('>Q', frame)[0]
        
        # Extract 49-bit AMBE
        ambe_49bit = frame_64bit >> 15
        
        # DMR AMBE+2 structure (72 bits total):
        # - 49 bits vocoder data
        # - 23 bits FEC
        
        # Check if our 49 bits already include FEC
        print(f"Frame {i+1} AMBE bits:")
        print(f"  Hex: 0x{ambe_49bit:013X}")
        print(f"  Binary: {bin(ambe_49bit)[2:].zfill(49)}")
        
        # Look for Hamming patterns in last bits
        last_10_bits = ambe_49bit & 0x3FF
        print(f"  Last 10 bits: {bin(last_10_bits)[2:].zfill(10)}")
        print()

def test_dmr_frame_alignment():
    """Test if frames are properly aligned for DMR"""
    
    print("\n=== DMR Frame Alignment Test ===\n")
    
    # DMR frame timing:
    # - 30ms per slot (2 slots = 60ms frame)
    # - 3 AMBE frames per slot
    # - Each AMBE frame = 20ms of audio
    
    frames_per_second = 50  # 50 frames/sec = 20ms each
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    num_frames = len(data) // 8
    duration_seconds = num_frames / frames_per_second
    
    print(f"Total frames: {num_frames}")
    print(f"Duration: {duration_seconds:.1f} seconds")
    print(f"Frame rate: {frames_per_second} fps (20ms per frame)")
    
    # Check for superframe patterns (every 6 frames)
    print("\nSuperframe patterns (every 6 frames):")
    
    for i in range(0, min(60, num_frames), 6):
        print(f"\nSuperframe starting at frame {i}:")
        for j in range(6):
            if (i + j) * 8 < len(data):
                frame = data[(i+j)*8:(i+j+1)*8]
                frame_64bit = struct.unpack('>Q', frame)[0]
                lower_15 = frame_64bit & 0x7FFF
                print(f"  Frame {j}: lower bits = 0x{lower_15:04X}")

def main():
    print("=== AMBE Frame Analysis ===\n")
    
    # Analyze frame structure
    analyze_ambe_structure()
    
    # Check for Hamming FEC
    check_hamming_fec()
    
    # Test DMR alignment
    test_dmr_frame_alignment()
    
    print("\n=== Conclusion ===")
    print("Based on analysis, determine if frames need FEC processing")

if __name__ == "__main__":
    main()