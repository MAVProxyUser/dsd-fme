#!/usr/bin/env python3
"""Verify IV predictions against captured data"""

import sqlite3
import sys

if len(sys.argv) < 2:
    print("Usage: python3 verify_iv_predictions.py <database_file>")
    sys.exit(1)

db_file = sys.argv[1]
print(f"\nVerifying predictions against: {db_file}")

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get the first few C-MI values
cursor.execute('''
    SELECT DISTINCT c_mi 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id
    LIMIT 10
''')

captured_values = [row[0] for row in cursor.fetchall()]

# Expected values from our predictions
expected = [
    0xB3DA646D,
    0x2B82F6AC,
    0xD22AE085,
    0xF165CF9A,
    0xE6A624EF,
    0xE08D9BBA,
    0xF3637096,
    0x17E43C42,
    0x987CC053,
    0x73AD4552
]

print('\nVerification Results:')
print('=' * 50)
print('Pos | Predicted    | Captured     | Match')
print('-' * 50)

matches = 0
total_checked = min(len(expected), len(captured_values))

for i in range(total_checked):
    match = expected[i] == captured_values[i]
    if match:
        matches += 1
    status = '✓' if match else '✗'
    print(f'{i:3d} | 0x{expected[i]:08X} | 0x{captured_values[i]:08X} | {status}')

accuracy = (matches / total_checked) * 100 if total_checked > 0 else 0
print(f'\nAccuracy: {matches}/{total_checked} = {accuracy:.1f}%')

if accuracy == 100:
    print('\n✓ PERFECT PREDICTION! All captured IVs matched!')
else:
    print('\n✗ Some predictions did not match')
    
print(f'\nCaptured {len(captured_values)} unique C-MI values total')

# Also check H-MI is still fixed
cursor.execute('SELECT DISTINCT h_mi FROM superframes WHERE h_mi != 0')
h_mi_values = [row[0] for row in cursor.fetchall()]

if h_mi_values and h_mi_values[0] == 0x6C8AB637:
    print("✓ H-MI remains fixed at 0x6C8AB637")
else:
    print(f"✗ H-MI changed to: 0x{h_mi_values[0]:08X}")

conn.close()