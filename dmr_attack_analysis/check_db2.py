#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print(f"Total tables: {len(tables)}")
print("Tables:", [t[0] for t in tables])

# Count rows in each table
print("\nRow counts:")
for table in tables:
    table_name = table[0]
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"{table_name}: {count} rows")

# Check H_ table
print("\nSample from H_ table:")
cursor.execute("SELECT * FROM H_6C8AB637_S0 LIMIT 3")
for row in cursor.fetchall():
    print(row)

# Check a C_ table
print("\nSample from C_ table:")
cursor.execute("SELECT * FROM C_E8083B57_S0 LIMIT 3")
for row in cursor.fetchall():
    print(row)

# Check correlations
print("\nSample correlations:")
cursor.execute("SELECT * FROM dmr_correlations LIMIT 5")
for row in cursor.fetchall():
    print(row)

conn.close()