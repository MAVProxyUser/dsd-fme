#!/usr/bin/env python3
"""Analyze cleartext capture to understand why no AMBE was found"""

import sqlite3

db_file = "dmr_capture_20250518_112958_062803.db"

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print("=== CLEARTEXT CAPTURE ANALYSIS ===")

# Check superframes
cursor.execute("SELECT COUNT(*), sync_type FROM superframes GROUP BY sync_type")
print("\nSuperframe types:")
for row in cursor.fetchall():
    print(f"  {row[1]}: {row[0]}")

# Check for any MI values
cursor.execute("SELECT COUNT(*), h_mi, c_mi FROM superframes WHERE h_mi IS NOT NULL OR c_mi IS NOT NULL")
result = cursor.fetchone()
print(f"\nFrames with MI values: {result[0]}")

# Check encryption flag
cursor.execute("SELECT COUNT(*) FROM superframes WHERE encrypted = 1")
print(f"Encrypted frames: {cursor.fetchone()[0]}")

# Look for FLCO/FID info
cursor.execute("SELECT DISTINCT flco, fid, source_id, target_id FROM superframes WHERE source_id IS NOT NULL LIMIT 5")
print("\nFLCO/FID/ID info:")
for row in cursor.fetchall():
    print(f"  FLCO: {row[0]}, FID: {row[1]}, Src: {row[2]}, Tgt: {row[3]}")

# Check all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
all_tables = [row[0] for row in cursor.fetchall()]
print(f"\nAll tables in database:")
for table in all_tables:
    print(f"  {table}")

# Check dmr_frames for voice data
if 'dmr_frames' in all_tables:
    cursor.execute("SELECT COUNT(*), frame_type FROM dmr_frames GROUP BY frame_type")
    print("\nDMR frame types:")
    for row in cursor.fetchall():
        print(f"  {row[1]}: {row[0]}")

conn.close()

print("\n=== KEY UNDERSTANDING ===")
print("1. Cleartext DMR doesn't use MI values - that's encryption-specific")
print("2. AMBE data in cleartext should be stored differently")
print("3. Need to check how dsd-fme logs cleartext AMBE vs encrypted")