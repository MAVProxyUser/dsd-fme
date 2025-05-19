#!/usr/bin/env python3
"""Compare old and new MI sequences"""

old_sequence = [
    0xE8083B57,
    0x4F36EE3A,
    0x752FEA1C,
    0x9A0C201B,
    0xD3C028BF,
    0xD851670C,
    0x1E3DC9E8,
    0xBB5FC480
]

import sqlite3
conn = sqlite3.connect('dmr_capture_20250518_020534_898339.db')
cursor = conn.cursor()
cursor.execute('SELECT DISTINCT c_mi FROM superframes WHERE c_mi != 0 ORDER BY id LIMIT 8')
new_values = [row[0] for row in cursor.fetchall()]

print('Old sequence:')
for i, val in enumerate(old_sequence):
    print(f'{i}: 0x{val:08X}')
    
print('\nNew captured values:')
for i, val in enumerate(new_values):
    print(f'{i}: 0x{val:08X}')
    
print('\nMatches:')
for i in range(min(len(old_sequence), len(new_values))):
    match = old_sequence[i] == new_values[i]
    status = 'MATCH' if match else 'DIFFERENT'
    print(f'{i}: Old 0x{old_sequence[i]:08X} vs New 0x{new_values[i]:08X} {status}')
    
if new_values == old_sequence[:len(new_values)]:
    print("\n✓ SAME SEQUENCE - MI values match!")
else:
    print("\n✗ DIFFERENT SEQUENCE - MI values don't match!")
    
conn.close()