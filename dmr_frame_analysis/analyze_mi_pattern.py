#!/usr/bin/env python3
import sqlite3
import sys

if len(sys.argv) != 2:
    print("Usage: python3 analyze_mi_pattern.py <database_file>")
    sys.exit(1)

db_file = sys.argv[1]
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

cursor.execute('SELECT c_mi FROM superframes ORDER BY id')
c_mi_values = [row[0] for row in cursor.fetchall()]

# Remove duplicates to see unique sequence
unique_sequence = []
for mi in c_mi_values:
    if mi not in unique_sequence:
        unique_sequence.append(mi)

print(f'Total unique C-MI values: {len(unique_sequence)}')
print(f'Total C-MI values: {len(c_mi_values)}')

# Check if any value repeats in the unique sequence
if len(unique_sequence) != len(set(unique_sequence)):
    print('WARNING: Found repeated values in unique sequence!')
else:
    print('No repeated values found in unique sequence')

# Look for zeros
zeros = sum(1 for mi in c_mi_values if mi == 0)
print(f'Number of zero C-MI values: {zeros}')

# Check pairs (original values occur in pairs)
print('\nPair analysis:')
consecutive_same = 0
for i in range(1, len(c_mi_values)):
    if c_mi_values[i] == c_mi_values[i-1]:
        consecutive_same += 1
print(f'Consecutive same values: {consecutive_same}')

# Analyze the unique progression
print('\nFirst 10 unique C-MI values:')
for i, mi in enumerate(unique_sequence[:10]):
    print(f'{i}: 0x{mi:08X}')

conn.close()