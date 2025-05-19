#!/usr/bin/env python3
"""Analyze multiple keyed transmissions to verify pattern"""

import sqlite3
import sys
from datetime import datetime

if len(sys.argv) < 2:
    print("Usage: python3 analyze_keyed_transmissions.py <database_file>")
    sys.exit(1)

db_file = sys.argv[1]
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print(f"\nAnalyzing transmissions in: {db_file}")
print("=" * 50)

# Get all C-MI values with timestamps
cursor.execute('''
    SELECT id, h_mi, c_mi, start_timestamp 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id
''')

rows = cursor.fetchall()
if not rows:
    print("No transmissions captured yet")
    sys.exit(1)

# Detect transmission boundaries (gaps > 2 seconds)
transmissions = []
current_tx = []
last_time = None

for row in rows:
    id_val, h_mi, c_mi, timestamp = row
    curr_time = datetime.fromisoformat(timestamp)
    
    if last_time and (curr_time - last_time).total_seconds() > 2:
        # New transmission detected
        if current_tx:
            transmissions.append(current_tx)
        current_tx = []
    
    current_tx.append((id_val, h_mi, c_mi, timestamp))
    last_time = curr_time

# Don't forget the last transmission
if current_tx:
    transmissions.append(current_tx)

print(f"Found {len(transmissions)} separate transmissions")

# Analyze each transmission
for tx_num, tx_data in enumerate(transmissions, 1):
    print(f"\nTransmission #{tx_num}:")
    print(f"  Start time: {tx_data[0][3]}")
    print(f"  Duration: {(datetime.fromisoformat(tx_data[-1][3]) - datetime.fromisoformat(tx_data[0][3])).total_seconds():.1f} seconds")
    print(f"  Superframes: {len(tx_data)}")
    
    # Check H-MI
    h_mi_values = set(row[1] for row in tx_data)
    print(f"  H-MI values: {len(h_mi_values)} unique")
    for h_mi in h_mi_values:
        print(f"    0x{h_mi:08X}")
    
    # Check C-MI sequence
    print(f"  C-MI sequence (first 10):")
    for i, (_, _, c_mi, _) in enumerate(tx_data[:10]):
        print(f"    {i}: 0x{c_mi:08X}")
    
    # Check if it starts with expected sequence
    expected_start = [0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0xD3C028BF]
    matches = 0
    for i in range(min(len(expected_start), len(tx_data))):
        if tx_data[i][2] == expected_start[i]:
            matches += 1
    
    if matches == min(len(expected_start), len(tx_data)):
        print("  ✓ C-MI sequence starts from beginning as expected!")
    else:
        print(f"  ✗ C-MI sequence doesn't match expected pattern ({matches}/{min(len(expected_start), len(tx_data))} matches)")

conn.close()

print("\nConclusion:")
print("Each transmission should start with the same C-MI sequence")
print("H-MI should always be 0x6C8AB637")