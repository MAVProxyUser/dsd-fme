#!/usr/bin/env python3
"""
Simple test to verify database creation works
"""
import sqlite3
import time
from datetime import datetime

# Create timestamp database name
now = datetime.now()
db_name = f"test_dmr_capture_{now.strftime('%Y%m%d_%H%M%S')}.db"

print(f"Creating test database: {db_name}")

# Create database and basic tables
conn = sqlite3.connect(db_name)
conn.execute("PRAGMA foreign_keys = ON")

# Create superframes table
conn.execute("""
CREATE TABLE IF NOT EXISTS superframes (
    id INTEGER PRIMARY KEY,
    start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    slot INTEGER,
    color_code INTEGER,
    sync_type TEXT,
    h_mi INTEGER,
    c_mi INTEGER,
    frame_count INTEGER DEFAULT 0,
    source_id INTEGER DEFAULT 0,
    target_id INTEGER DEFAULT 0
)
""")

# Create a test AMBE table
conn.execute("""
CREATE TABLE IF NOT EXISTS H_12345678_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    mi_full INTEGER,
    algid INTEGER,
    slot INTEGER,
    source_id INTEGER,
    target_id INTEGER,
    superframe_id INTEGER DEFAULT NULL
)
""")

# Insert test data
conn.execute("""
INSERT INTO superframes (slot, color_code, sync_type, h_mi, c_mi, source_id, target_id)
VALUES (0, 0, 'MS_VOICE', 305419896, 0, 1234, 16777215)
""")

# Insert test AMBE frame
conn.execute("""
INSERT INTO H_12345678_S0 (ambe_hex, mi_full, algid, slot, source_id, target_id, superframe_id)
VALUES ('3D11B2190B3380', 305419896, 33, 0, 1234, 16777215, 1)
""")

conn.commit()
conn.close()

print(f"Database created successfully: {db_name}")
print("Test data inserted")