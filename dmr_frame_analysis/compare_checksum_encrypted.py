#!/usr/bin/env python3
"""Compare checksum bytes between encrypted and cleartext AMBE"""

import sqlite3
import numpy as np

# First analyze the encrypted frames from our database
db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_101926_361605.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get encrypted AMBE frames
cur.execute("""
    SELECT ambe 
    FROM Frames 
    WHERE frame_type = 'DMR_DATA_VOICE_SYNC' 
    ORDER BY id
    LIMIT 100
""")

encrypted_frames = []
for row in cur:
    if row[0]:
        ambe_bytes = bytes.fromhex(row[0])
        encrypted_frames.append(ambe_bytes)

print(f"Found {len(encrypted_frames)} encrypted frames")

# Analyze encrypted frames
print("\nEncrypted frame analysis:")
encrypted_checksums = []
for i, frame in enumerate(encrypted_frames[:10]):
    if len(frame) >= 8:
        last_byte = frame[7]
        encrypted_checksums.append(last_byte)
        print(f"Frame {i}:")
        print(f"  Data: {' '.join(f'{b:02X}' for b in frame[:7])}")
        print(f"  Last byte: {last_byte:02X}")

# Now let's also check the md380 format file
print("\n\nAnalyzing MD380 format AMBE:")
with open("ambe_md380_format.bin", "rb") as f:
    data = f.read()

md380_frames = []
for i in range(0, len(data), 7):  # MD380 uses 7 bytes
    if i + 7 <= len(data):
        frame = data[i:i+7]
        md380_frames.append(frame)

print(f"Total MD380 frames: {len(md380_frames)}")

for i, frame in enumerate(md380_frames[:10]):
    print(f"MD380 Frame {i}: {' '.join(f'{b:02X}' for b in frame)}")

# Compare bit patterns in the last byte
print("\n\nBit analysis of encrypted checksums:")
if encrypted_checksums:
    bit_counts = [0] * 8
    for checksum in encrypted_checksums:
        for bit in range(8):
            if checksum & (1 << bit):
                bit_counts[bit] += 1
    
    for bit in range(8):
        print(f"Bit {bit}: Set in {bit_counts[bit]}/{len(encrypted_checksums)} frames ({100*bit_counts[bit]/len(encrypted_checksums):.1f}%)")

# Load cleartext for comparison  
with open("cleartext_ambe.bin", "rb") as f:
    cleartext_data = f.read()

cleartext_checksums = []
for i in range(0, min(800, len(cleartext_data)), 8):  # First 100 frames
    if i + 8 <= len(cleartext_data):
        cleartext_checksums.append(cleartext_data[i+7])

print(f"\n\nCleartext checksums: {set(cleartext_checksums)}")
print(f"Encrypted checksums: {set(encrypted_checksums) if encrypted_checksums else 'None'}")

conn.close()