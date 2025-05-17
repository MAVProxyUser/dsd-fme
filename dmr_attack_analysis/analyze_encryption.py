#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Get all correlations to see the MI progression
cursor.execute("""
    SELECT header_mi, control_mi 
    FROM dmr_correlations 
    ORDER BY id
""")
correlations = cursor.fetchall()

print("MI Evolution Pattern:")
print("H-MI (static)  ->  C-MI (evolving)")
print("-" * 40)
for i, (h_mi, c_mi) in enumerate(correlations[:10]):
    print(f"{h_mi:08X}  ->  {c_mi:08X}")

# Check AMBE frame counts
cursor.execute("SELECT COUNT(*) FROM H_6C8AB637_S0")
h_frames = cursor.fetchone()[0]

total_c_frames = 0
for c in correlations:
    c_mi = c[1]
    cursor.execute(f"SELECT COUNT(*) FROM C_{c_mi:08X}_S0")
    count = cursor.fetchone()[0]
    total_c_frames += count

print(f"\nAMBE Frame Distribution:")
print(f"H- table frames: {h_frames}")
print(f"C- table frames: {total_c_frames}")
print(f"Total frames: {h_frames + total_c_frames}")

# Check timing between transmissions
print("\nTransmission Pattern:")
cursor.execute("""
    SELECT DISTINCT timestamp 
    FROM dmr_correlations 
    ORDER BY timestamp
""")
timestamps = [row[0] for row in cursor.fetchall()]
for i, ts in enumerate(timestamps[:5]):
    print(f"Transmission {i+1}: {ts}")

conn.close()