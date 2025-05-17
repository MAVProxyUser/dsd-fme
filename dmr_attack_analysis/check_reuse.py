#!/usr/bin/env python3
import sqlite3
from collections import Counter

conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Check for reused MIs in correlations
cursor.execute("SELECT header_mi, control_mi FROM dmr_correlations")
correlations = cursor.fetchall()

header_mis = [c[0] for c in correlations]
control_mis = [c[1] for c in correlations]

print("Header MI reuse:")
header_counter = Counter(header_mis)
for mi, count in header_counter.items():
    if count > 1:
        print(f"  MI {mi:08X} used {count} times")
if not any(count > 1 for count in header_counter.values()):
    print("  No reuse detected")

print("\nControl MI reuse:")
control_counter = Counter(control_mis)
for mi, count in control_counter.items():
    if count > 1:
        print(f"  MI {mi:08X} used {count} times")
if not any(count > 1 for count in control_counter.values()):
    print("  No reuse detected")

# Check for patterns in C- tables
print("\nChecking for MI patterns in C- tables:")
cursor.execute("SELECT control_mi FROM dmr_correlations ORDER BY id")
control_sequence = [row[0] for row in cursor.fetchall()]

print("Control MI sequence (first 10):")
for i, mi in enumerate(control_sequence[:10]):
    print(f"  {i}: {mi:08X}")

# Check AMBE reuse in H- table
print("\nChecking for AMBE frame reuse in H- table:")
cursor.execute("SELECT ambe_hex, COUNT(*) as count FROM H_6C8AB637_S0 GROUP BY ambe_hex HAVING count > 1")
reused_ambe = cursor.fetchall()
if reused_ambe:
    print(f"Found {len(reused_ambe)} reused AMBE frames")
    for ambe, count in reused_ambe[:5]:
        print(f"  {ambe}: {count} times")
else:
    print("  No AMBE frame reuse detected")

conn.close()