#!/usr/bin/env python3
"""Analyze if the 8th byte in AMBE frames is a checksum"""

import numpy as np

# First, let's analyze the cleartext AMBE frames to see if the 8th byte is a checksum
with open("cleartext_ambe.bin", "rb") as f:
    data = f.read()

frames = []
for i in range(0, len(data), 8):
    if i + 8 <= len(data):
        frame = data[i:i+8]
        frames.append(frame)

print(f"Total frames: {len(frames)}")

# Analyze patterns in the 8th byte
checksums = []
for i, frame in enumerate(frames[:100]):  # First 100 frames
    last_byte = frame[7]
    checksums.append(last_byte)
    
    # Calculate various checksums to see if any match
    sum_mod256 = sum(frame[:7]) % 256
    xor_all = 0
    for b in frame[:7]:
        xor_all ^= b
    
    # CRC-8 calculation (simple version)
    crc = 0
    for b in frame[:7]:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07  # CRC-8 polynomial
            else:
                crc <<= 1
        crc &= 0xFF
    
    if i < 10:
        print(f"Frame {i}:")
        print(f"  Data: {' '.join(f'{b:02X}' for b in frame[:7])}")
        print(f"  Last byte: {last_byte:02X}")
        print(f"  Sum mod 256: {sum_mod256:02X}")
        print(f"  XOR all: {xor_all:02X}")
        print(f"  CRC-8: {crc:02X}")
        print()

# Check for patterns in adjacent frames
print("\nChecking if same data produces same checksum:")
seen_data = {}
for i, frame in enumerate(frames):
    data_part = bytes(frame[:7])
    checksum = frame[7]
    
    if data_part in seen_data:
        if seen_data[data_part] != checksum:
            print(f"MISMATCH: Same data, different checksums at frames {seen_data[data_part][1]} and {i}")
        else:
            print(f"MATCH: Same data, same checksum at frames {seen_data[data_part][1]} and {i}")
    else:
        seen_data[data_part] = (checksum, i)

# Look for frames with all zeros in data portion
print("\nFrames with zero data:")
for i, frame in enumerate(frames):
    if all(b == 0 for b in frame[:7]):
        print(f"Frame {i}: All zeros, checksum = {frame[7]:02X}")

# Check if certain bits are always set/unset
print("\nBit analysis of checksums:")
bit_counts = [0] * 8
for checksum in checksums:
    for bit in range(8):
        if checksum & (1 << bit):
            bit_counts[bit] += 1

for bit in range(8):
    print(f"Bit {bit}: Set in {bit_counts[bit]}/{len(checksums)} frames ({100*bit_counts[bit]/len(checksums):.1f}%)")