#!/usr/bin/env python3
"""Find the actual cycle length of the C-MI sequence"""

import sqlite3

db_file = "dmr_capture_20250518_024416_423288.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get all distinct C-MI values in order
cursor.execute('''
    SELECT DISTINCT c_mi 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id
''')

unique_cmi = [row[0] for row in cursor.fetchall()]
print(f"Total unique C-MI values in this transmission: {len(unique_cmi)}")

# Expected full sequence based on LFSR
expected_full_sequence = [
    0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0xD3C028BF,
    0xD851670C, 0x1E3DC9E8, 0xBB5FC480, 0x97D76800, 0xB0E136DB,
    0xF3152FD2, 0x46CB4902, 0xDC09BDB4, 0xB9EC6354, 0xC4856E39,
    0x11E3BB5A, 0x3D6EEE34, 0x63BBBB54, 0x2BFABF7C, 0xD24D2433,
    0x2A77B3F0, 0x206BF0CF, 0x14218AD7, 0x8F15BE98, 0x0CE35C4F,
    0x3317D40C, 0xCCE1A791, 0xB93D3A9F, 0xA9D520BA, 0xA9047971,
    0xC45437F2
]

print(f"Expected sequence length: {len(expected_full_sequence)}")

# Check how many match
matches = 0
for i in range(min(len(unique_cmi), len(expected_full_sequence))):
    if unique_cmi[i] == expected_full_sequence[i]:
        matches += 1
    else:
        print(f"First mismatch at position {i}:")
        print(f"  Expected: 0x{expected_full_sequence[i]:08X}")
        print(f"  Actual: 0x{unique_cmi[i]:08X}")
        break

print(f"\nMatches: {matches}/{min(len(unique_cmi), len(expected_full_sequence))}")

# Now check for repetition pattern
print("\nLooking for cycle pattern...")
cycle_found = False
for cycle_len in range(1, min(50, len(unique_cmi)//2)):
    is_cyclic = True
    for i in range(cycle_len, min(100, len(unique_cmi))):
        if unique_cmi[i] != unique_cmi[i % cycle_len]:
            is_cyclic = False
            break
    
    if is_cyclic:
        print(f"Found cycle of length {cycle_len}!")
        print("Cycle values:")
        for i in range(cycle_len):
            print(f"  {i}: 0x{unique_cmi[i]:08X}")
        cycle_found = True
        break

if not cycle_found:
    print("No short cycle found - checking if it matches full LFSR sequence")
    
# Print the actual unique sequence
print("\nActual unique C-MI sequence (first 31):")
for i in range(min(31, len(unique_cmi))):
    expected = expected_full_sequence[i] if i < len(expected_full_sequence) else None
    match = unique_cmi[i] == expected if expected else False
    status = '✓' if match else '✗' if expected else '?'
    print(f"{i:2d}: 0x{unique_cmi[i]:08X} {status}")

conn.close()