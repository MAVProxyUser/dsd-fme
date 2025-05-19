#!/usr/bin/env python3
"""
Check where algorithm ID is stored and why it's not propagating
"""
import sqlite3

def check_algid_storage(db_path):
    """Check where AlgID is stored in the database"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print("Checking AlgID storage:")
    print("=" * 50)
    
    # Check correlations table
    print("\n1. Correlations table:")
    cur.execute("""
        SELECT header_mi, control_mi, slot, algid
        FROM dmr_correlations
    """)
    
    for row in cur.fetchall():
        h_mi, c_mi, slot, algid = row
        print(f"  H_MI: 0x{h_mi:08x}, C_MI: 0x{c_mi:08x}, Slot: {slot}, AlgID: {algid}")
    
    # Check AMBE tables for AlgID
    print("\n2. AMBE tables:")
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')
        ORDER BY name
    """)
    
    for table in cur.fetchall():
        table_name = table[0]
        cur.execute(f"SELECT DISTINCT algid FROM {table_name}")
        algids = [row[0] for row in cur.fetchall()]
        print(f"  {table_name}: AlgIDs = {algids}")
    
    # Check superframes - this is where the issue is
    print("\n3. Superframes table:")
    cur.execute("""
        SELECT id, encrypted, privacy_algid, h_mi, c_mi
        FROM superframes
        WHERE c_mi != 0
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        sf_id, enc, algid, h_mi, c_mi = row
        print(f"  SF {sf_id}: encrypted={enc}, privacy_algid={algid}, H_MI=0x{h_mi:08x}, C_MI=0x{c_mi:08x}")
    
    # Check db_logger source code issue
    print("\n4. Source code issue:")
    print("  dmr_flco.c line 72: is_encrypted = (state->payload_algid != 0)")
    print("  But state->payload_algid is only set when PI header is received")
    print("  LFSR encryption might not always send PI headers")
    
    # Verify encryption by checking table prefixes
    print("\n5. Actual encryption status (based on table prefixes):")
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE '__%_S0' ESCAPE '_'
    """)
    
    encrypted_count = 0
    unencrypted_count = 0
    
    for table in cur.fetchall():
        table_name = table[0]
        if table_name.startswith('U_'):
            unencrypted_count += 1
        elif table_name.startswith('C_') or table_name.startswith('H_'):
            encrypted_count += 1
    
    print(f"  Encrypted tables (C_ or H_): {encrypted_count}")
    print(f"  Unencrypted tables (U_): {unencrypted_count}")
    print(f"  => Encryption is {'ACTIVE' if encrypted_count > 0 else 'INACTIVE'}")
    
    conn.close()

def suggest_fix():
    """Suggest how to fix the issue"""
    print("\n\nSuggested Fix:")
    print("=" * 50)
    print("The issue is in dmr_flco.c:")
    print("1. Line 72 checks state->payload_algid to determine encryption")
    print("2. But payload_algid is only set when PI headers are received")
    print("3. LFSR encryption may not always include PI headers")
    print()
    print("Fix options:")
    print("A. Also check for presence of H_ and C_ tables")
    print("B. Set algid when creating encrypted AMBE tables")
    print("C. Use the AlgID from dmr_correlations table")
    print()
    print("The encrypted flag should be set if:")
    print("- state->payload_algid != 0 OR")
    print("- H_MI != 0 OR")
    print("- C_MI != 0 (and not 0x00000000)")

if __name__ == "__main__":
    print("=== Radio 1234 (Encrypted) ===")
    check_algid_storage("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234505.db")
    suggest_fix()