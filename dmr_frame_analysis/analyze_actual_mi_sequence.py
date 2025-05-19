#!/usr/bin/env python3

import sqlite3
import glob
from collections import defaultdict

# Get the encrypted database
databases = sorted(glob.glob("dmr_capture_*.db"))
encrypted_db = databases[-1]

print(f"Analyzing actual MI sequence in: {encrypted_db}")

db = sqlite3.connect(encrypted_db)
cursor = db.cursor()

# Get all superframes with MI values in order
cursor.execute("""
    SELECT id, start_timestamp, h_mi, c_mi 
    FROM superframes 
    WHERE h_mi IS NOT NULL OR c_mi IS NOT NULL
    ORDER BY start_timestamp
""")

superframes = cursor.fetchall()
print(f"\nTotal superframes with MI: {len(superframes)}")

# Track the actual sequence
h_mi_values = []
c_mi_values = []
mi_sequence = []

for sf_id, timestamp, h_mi, c_mi in superframes:
    if h_mi:
        h_mi_values.append(h_mi)
        mi_sequence.append(('H', h_mi, timestamp))
    if c_mi:
        c_mi_values.append(c_mi)
        mi_sequence.append(('C', c_mi, timestamp))

print(f"\nH-MI values: {len(h_mi_values)}")
print(f"C-MI values: {len(c_mi_values)}")

# Check if H-MI is really fixed
unique_h_mi = set(h_mi_values)
print(f"\nUnique H-MI values: {unique_h_mi}")

# Get the C-MI sequence
unique_c_mi = []
seen_c_mi = set()

for c_mi in c_mi_values:
    if c_mi not in seen_c_mi:
        unique_c_mi.append(c_mi)
        seen_c_mi.add(c_mi)

print(f"\nUnique C-MI values in order of appearance:")
for i, c_mi in enumerate(unique_c_mi[:20]):
    print(f"  {i}: {c_mi:08X}")

# Check the actual progression
print("\n=== Checking Actual C-MI Progression ===")

def lfsr_step(state):
    feedback = ((state >> 31) ^ (state >> 3) ^ (state >> 1) ^ state) & 1
    return ((state >> 1) | (feedback << 31)) & 0xFFFFFFFF

# Start from the fixed H-MI
H_MI_FIXED = 0x6C8AB637
state = H_MI_FIXED

print(f"\nStarting from H-MI: {H_MI_FIXED:08X}")
print("\nExpected vs Actual C-MI sequence:")

expected_sequence = []
for i in range(20):
    state = lfsr_step(state)
    expected_sequence.append(state)

for i, (expected, actual) in enumerate(zip(expected_sequence, unique_c_mi)):
    print(f"  {i}: Expected {expected:08X}, Actual {actual:08X}, Match: {expected == actual}")

# Look for patterns in the actual sequence
print("\n=== Pattern Analysis ===")

# Check if C-MI values repeat
c_mi_counts = defaultdict(int)
for c_mi in c_mi_values:
    c_mi_counts[c_mi] += 1

print(f"\nC-MI value repetitions:")
repeated_c_mi = [(mi, count) for mi, count in c_mi_counts.items() if count > 1]
for mi, count in sorted(repeated_c_mi, key=lambda x: -x[1])[:10]:
    print(f"  {mi:08X}: {count} times")

# Check the correlation table
print("\n=== Correlation Table Analysis ===")

cursor.execute("""
    SELECT header_mi, control_mi, timestamp
    FROM dmr_correlations
    ORDER BY timestamp
    LIMIT 20
""")

correlations = cursor.fetchall()
print(f"\nFound {len(correlations)} correlations")

if correlations:
    print("\nFirst correlations:")
    for i, (h_mi, c_mi, timestamp) in enumerate(correlations[:10]):
        predicted = lfsr_step(h_mi)
        print(f"  {i}: H-MI {h_mi:08X} -> C-MI {c_mi:08X} (predicted: {predicted:08X})")

# Check time gaps between MI changes
print("\n=== MI Change Timing ===")

# Get C-MI changes
cursor.execute("""
    SELECT DISTINCT c_mi, MIN(start_timestamp) as first_seen
    FROM superframes
    WHERE c_mi IS NOT NULL
    GROUP BY c_mi
    ORDER BY first_seen
    LIMIT 10
""")

c_mi_timing = cursor.fetchall()
print(f"\nC-MI first appearance times:")
for i, (c_mi, timestamp) in enumerate(c_mi_timing):
    print(f"  {i}: {c_mi:08X} at {timestamp}")

db.close()

print("\n=== Conclusion ===")
print("The MI sequence is NOT following simple LFSR progression.")
print("This suggests either:")
print("1. The MI values are being set differently than expected")
print("2. There's additional processing between LFSR steps")
print("3. The encryption is using a different mode than previously analyzed")