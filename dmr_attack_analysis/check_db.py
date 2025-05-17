#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Check H_ table
cursor.execute('SELECT * FROM H_6C8AB637_S0 LIMIT 5')
print("H_ table sample:")
for row in cursor.fetchall():
    print(row)

# Check correlations
cursor.execute('SELECT * FROM dmr_correlations LIMIT 5')
print("\nCorrelations:")
for row in cursor.fetchall():
    print(row)

# Check table schema
cursor.execute("PRAGMA table_info(H_6C8AB637_S0)")
print("\nH_ table schema:")
for row in cursor.fetchall():
    print(row)

conn.close()