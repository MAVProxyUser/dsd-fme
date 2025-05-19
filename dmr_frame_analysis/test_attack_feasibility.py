#!/usr/bin/env python3
"""Test attack feasibility on short capture"""
import sqlite3

# Connect to database
conn = sqlite3.connect('dmr_capture_20250517_205116.db')
cursor = conn.cursor()

# Get encrypted frames
cursor.execute("""
    SELECT table_name, COUNT(*) as frame_count
    FROM sqlite_master, (
        SELECT name as table_name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'H_%' OR name LIKE 'C_%'
    )
    JOIN (SELECT name FROM sqlite_master WHERE type='table') t
    ON table_name = t.name
    WHERE table_name NOT IN ('dmr_correlations', 'dmr_metadata', 'superframes')
    GROUP BY table_name
""")

# Simpler query
cursor.execute("""
    SELECT COUNT(*) FROM H_6C8AB637_S0
""")
h_frames = cursor.fetchone()[0]

# Count C-MI tables
cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name LIKE 'C_%'
""")
c_tables = cursor.fetchall()

print("=== Attack Feasibility Analysis ===")
print(f"Fixed H-MI frames: {h_frames}")
print(f"Unique C-MI tables: {len(c_tables)}")
print("\nC-MI Tables:")
for table in c_tables:
    table_name = table[0]
    mi_value = table_name.split('_')[1]
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  {table_name}: {count} frames (MI: 0x{mi_value})")

# Total encrypted frames
cursor.execute("""
    SELECT COUNT(*) FROM dmr_correlations WHERE header_mi = 1821029943
""")
correlations = cursor.fetchone()[0]

print(f"\nTotal correlations: {correlations}")
print(f"Attack feasibility: {'HIGH' if correlations > 5 else 'MODERATE'}")
print("\nWith known plaintext (beeps) at transmission boundaries,")
print("we can recover keystreams for each MI position and decrypt all traffic.")

conn.close()