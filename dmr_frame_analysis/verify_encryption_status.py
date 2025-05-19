#!/usr/bin/env python3
"""
Verify encryption status in captures
"""
import sqlite3
import glob

def check_encryption_details(db_path):
    """Check encryption status details"""
    print(f"\n=== {db_path} ===")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check all superframes
    cur.execute("""
        SELECT id, source_id, target_id, encrypted, privacy_algid, h_mi, c_mi
        FROM superframes
        ORDER BY id
    """)
    
    for row in cur.fetchall():
        id_, src, tgt, enc, algid, h_mi, c_mi = row
        if src is not None and tgt is not None:
            print(f"\nSuperframe {id_}:")
            print(f"  Source: {src}")
            print(f"  Target: {tgt}")
            print(f"  Encrypted flag: {enc}")
            print(f"  Privacy AlgID: {algid}")
            print(f"  H_MI: 0x{h_mi:08x}")
            print(f"  C_MI: 0x{c_mi:08x}")
            
            # Check what AMBE tables exist for this transmission
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%' OR name LIKE 'U_%')
                AND name LIKE '%_S0'
            """)
            
            tables = [t[0] for t in cur.fetchall()]
            encrypted_tables = [t for t in tables if t.startswith('C_') or t.startswith('H_')]
            unencrypted_tables = [t for t in tables if t.startswith('U_')]
            
            print(f"  Encrypted tables: {len(encrypted_tables)}")
            print(f"  Unencrypted tables: {len(unencrypted_tables)}")
            
            if src == 1234:
                print("  ^^ Radio 1234 (should be encrypted)")
            elif src == 6969:
                print("  ^^ Radio 6969 (should be unencrypted)")
    
    # Summary
    cur.execute("""
        SELECT 
            COUNT(CASE WHEN encrypted = 1 THEN 1 END) as encrypted_count,
            COUNT(CASE WHEN encrypted = 0 THEN 1 END) as unencrypted_count,
            COUNT(DISTINCT privacy_algid) as algid_count
        FROM superframes
        WHERE source_id IS NOT NULL
    """)
    
    enc_count, unenc_count, algid_count = cur.fetchone()
    print(f"\nSummary:")
    print(f"  Encrypted superframes: {enc_count}")
    print(f"  Unencrypted superframes: {unenc_count}")
    print(f"  Unique AlgIDs: {algid_count}")
    
    conn.close()

if __name__ == "__main__":
    # Check both databases
    databases = [
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234505.db",
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234506.db"
    ]
    
    for db in databases:
        check_encryption_details(db)