#!/usr/bin/env python3
"""Analyze 5-minute capture for IV reuse vulnerability"""

import sqlite3
from collections import defaultdict

db_file = "dmr_capture_20250518_112024_998484.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print("=== 5-MINUTE CAPTURE ANALYSIS ===\n")

# Get all IVs
cursor.execute('''
    SELECT h_mi, c_mi, id, start_timestamp
    FROM superframes
    ORDER BY id
''')

rows = cursor.fetchall()
print(f"Total superframes: {len(rows)}")

# Track IV usage
h_mi_usage = defaultdict(int)
c_mi_usage = defaultdict(int)

for h_mi, c_mi, _, _ in rows:
    if h_mi != 0:
        h_mi_usage[h_mi] += 1
    if c_mi != 0:
        c_mi_usage[c_mi] += 1

print(f"\nH-MI Analysis:")
for h_mi, count in h_mi_usage.items():
    print(f"  0x{h_mi:08X}: used {count} times")

print(f"\nC-MI Analysis:")
print(f"  Total unique C-MI values: {len(c_mi_usage)}")
print(f"  C-MI values used more than once: {sum(1 for count in c_mi_usage.values() if count > 1)}")

# Show most reused C-MI values
print("\nMost reused C-MI values:")
sorted_cmi = sorted(c_mi_usage.items(), key=lambda x: x[1], reverse=True)
for c_mi, count in sorted_cmi[:20]:
    if count > 1:
        print(f"  0x{c_mi:08X}: used {count} times")

# Calculate impact
total_h_mi_reuse = sum(count - 1 for count in h_mi_usage.values())
total_c_mi_reuse = sum(count - 1 for count in c_mi_usage.values() if count > 1)

print(f"\nIV REUSE STATISTICS:")
print(f"  H-MI total reuses: {total_h_mi_reuse}")
print(f"  C-MI total reuses: {total_c_mi_reuse}")
print(f"  Total IV reuses: {total_h_mi_reuse + total_c_mi_reuse}")

# Check if C-MI follows expected pattern
cursor.execute('''
    SELECT DISTINCT c_mi 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id
    LIMIT 20
''')

first_20_cmi = [row[0] for row in cursor.fetchall()]
expected_start = [0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0xD3C028BF]

print("\nPattern verification (first 5 C-MI values):")
for i in range(min(5, len(first_20_cmi))):
    expected = expected_start[i] if i < len(expected_start) else None
    actual = first_20_cmi[i]
    match = actual == expected
    print(f"  Position {i}: 0x{actual:08X} {'✓' if match else '✗'}")

print("\n=== VULNERABILITY IMPACT ===")
print("With RC4 stream cipher:")
print(f"- {total_h_mi_reuse + total_c_mi_reuse} times the same keystream is generated")
print("- XOR attacks can recover plaintext without the key")
print("- The person's statement 'As long as IVs are only used once' is violated")
print(f"- In just 5 minutes, IVs were reused {total_h_mi_reuse + total_c_mi_reuse} times!")

# Demonstrate potential attack
print("\nATTACK SCENARIO:")
print("If we capture two messages with same IV:")
print("  Message 1: C1 = P1 XOR Keystream")
print("  Message 2: C2 = P2 XOR Keystream")
print("  Therefore: C1 XOR C2 = P1 XOR P2")
print("  If we know P1 (silence, header, etc), we get P2!")

conn.close()