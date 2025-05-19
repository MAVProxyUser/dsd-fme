#!/usr/bin/env python3

import sqlite3
import glob
import sys

# Get the latest databases
databases = sorted(glob.glob("dmr_capture_*.db"))[-2:]

for db_file in databases:
    try:
        print(f"\n=== Checking {db_file} ===")
        db = sqlite3.connect(db_file)
        cursor = db.cursor()
        
        # Get superframe data
        cursor.execute("SELECT slot, source_id, target_id, encrypted, h_mi, c_mi FROM superframes")
        superframes = cursor.fetchall()
        
        print(f"Superframes: {len(superframes)}")
        
        # Count encrypted vs unencrypted
        encrypted_count = sum(1 for s in superframes if s[3] > 0)
        unencrypted_count = sum(1 for s in superframes if s[3] == 0)
        
        print(f"Encrypted: {encrypted_count}")
        print(f"Unencrypted: {unencrypted_count}")
        
        # Show unique radio IDs
        sources = set(s[1] for s in superframes if s[1] is not None)
        targets = set(s[2] for s in superframes if s[2] is not None)
        
        print(f"Source IDs: {sources}")
        print(f"Target IDs: {targets}")
        
        # Show MI values
        h_mi_set = set(s[4] for s in superframes if s[4] is not None and s[4] != 0)
        c_mi_set = set(s[5] for s in superframes if s[5] is not None and s[5] != 0)
        
        print(f"H-MI values: {list(h_mi_set)[:5]}{'...' if len(h_mi_set) > 5 else ''}")
        print(f"C-MI values: {list(c_mi_set)[:5]}{'...' if len(c_mi_set) > 5 else ''}")
        
        # Check AMBE tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S%'")
        ambe_tables = cursor.fetchall()
        
        print(f"\nAMBE tables: {len(ambe_tables)}")
        for table_name in ambe_tables:
            table = table_name[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} frames")
            
        db.close()
        
    except Exception as e:
        print(f"ERROR checking {db_file}: {e}")