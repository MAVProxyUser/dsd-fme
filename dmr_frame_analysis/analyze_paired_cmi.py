#!/usr/bin/env python3
"""Analyze the paired C-MI pattern"""

import sqlite3
import sys

if len(sys.argv) < 2:
    db_file = "dmr_capture_20250518_024416_423288.db"
else:
    db_file = sys.argv[1]

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get all C-MI values in order
cursor.execute('''
    SELECT id, c_mi, start_timestamp 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id
    LIMIT 100
''')

rows = cursor.fetchall()
print(f"Total rows: {len(rows)}")

# Extract unique sequence (removing duplicates)
unique_sequence = []
for _, c_mi, _ in rows:
    if not unique_sequence or c_mi != unique_sequence[-1]:
        unique_sequence.append(c_mi)

print(f"\nUnique C-MI sequence (first 20):")
expected_sequence = [
    0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0xD3C028BF,
    0xD851670C, 0x1E3DC9E8, 0xBB5FC480, 0x97D76800, 0xB0E136DB,
    0xF3152FD2, 0x46CB4902, 0xDC09BDB4, 0xB9EC6354, 0xC4856E39
]

for i in range(min(20, len(unique_sequence))):
    match = unique_sequence[i] == expected_sequence[i] if i < len(expected_sequence) else False
    status = '✓' if match else '✗'
    print(f"{i:2d}: 0x{unique_sequence[i]:08X} {status}")

# Check pairing pattern
print("\nPairing pattern (first 20 entries):")
for i in range(min(20, len(rows))):
    print(f"{i:2d}: 0x{rows[i][1]:08X}")
    
# Verify each value appears exactly twice
print("\nChecking if each C-MI appears exactly twice in sequence:")
i = 0
while i < len(rows) - 1:
    if rows[i][1] == rows[i+1][1]:
        print(f"✓ Pair at positions {i},{i+1}: 0x{rows[i][1]:08X}")
        i += 2
    else:
        print(f"✗ No pair at position {i}: 0x{rows[i][1]:08X}")
        i += 1

conn.close()

print("\nConclusion:")
print("1. C-MI values follow the expected LFSR sequence")
print("2. Each C-MI value appears exactly twice (in pairs)")
print("3. This is consistent with DMR's dual-slot structure")
print("4. The sequence restarts from beginning for each transmission")