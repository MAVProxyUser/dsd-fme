#!/usr/bin/env python3

import sqlite3
import glob
import sys

# Get the latest databases
databases = sorted(glob.glob("dmr_capture_*.db"))

for db_file in databases:
    try:
        print(f"\n=== Analyzing {db_file} ===")
        db = sqlite3.connect(db_file)
        cursor = db.cursor()
        
        # Get superframe data
        cursor.execute("SELECT slot, source_id, target_id, h_mi, c_mi FROM superframes")
        superframes = cursor.fetchall()
        
        print(f"Total superframes: {len(superframes)}")
        
        # Count encrypted superframes based on MI values
        encrypted_count = sum(1 for s in superframes if (s[3] is not None and s[3] != 0) or (s[4] is not None and s[4] != 0))
        unencrypted_count = len(superframes) - encrypted_count
        
        print(f"Encrypted (has MI values): {encrypted_count}")
        print(f"Unencrypted (no MI values): {unencrypted_count}")
        
        # Show unique radio IDs
        sources = set(s[1] for s in superframes if s[1] is not None)
        targets = set(s[2] for s in superframes if s[2] is not None)
        
        print(f"Source IDs: {sources}")
        print(f"Target IDs: {targets}")
        
        # Check for encrypted AMBE tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')")
        encrypted_tables = cursor.fetchall()
        
        print(f"\nEncrypted AMBE tables: {len(encrypted_tables)}")
        
        # Count frames in encrypted tables
        total_encrypted_frames = 0
        for table_name in encrypted_tables:
            table = table_name[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            if count > 0:
                total_encrypted_frames += count
                print(f"  {table}: {count} frames")
        
        print(f"\nTotal encrypted AMBE frames: {total_encrypted_frames}")
        
        # Check unencrypted table
        unencrypted_frames = 0
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'U_%'")
        unencrypted_tables = cursor.fetchall()
        
        for table_name in unencrypted_tables:
            table = table_name[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            unencrypted_frames += count
        
        print(f"Unencrypted AMBE frames: {unencrypted_frames}")
        
        # Determine overall encryption status
        print(f"\n** Transmission is {'ENCRYPTED' if total_encrypted_frames > 0 else 'UNENCRYPTED'} **")
        
        db.close()
        
    except Exception as e:
        print(f"ERROR analyzing {db_file}: {e}")