#!/usr/bin/env python3
"""
Check if encryption flag is now being set correctly
"""
import sqlite3

def check_encryption_fix(db_path):
    """Check if the encryption flag fix is working"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check superframes with encryption data
    print("Checking superframes for encryption flag:")
    print("=" * 60)
    
    cur.execute("""
        SELECT id, source_id, target_id, encrypted, privacy_algid, h_mi, c_mi
        FROM superframes
        WHERE source_id IS NOT NULL
        ORDER BY id
    """)
    
    for row in cur.fetchall():
        sf_id, src, tgt, enc, algid, h_mi, c_mi = row
        
        print(f"\nSuperframe {sf_id}:")
        print(f"  Source: {src}, Target: {tgt}")
        print(f"  Encrypted flag: {enc}")
        print(f"  Privacy AlgID: {algid}")
        print(f"  H_MI: 0x{h_mi:08x}")
        print(f"  C_MI: 0x{c_mi:08x}")
        
        # Check if encryption should be detected
        should_be_encrypted = (h_mi != 0 or c_mi != 0)
        
        if should_be_encrypted and enc == 1:
            print("  ✓ Encryption correctly detected!")
        elif should_be_encrypted and enc == 0:
            print("  ✗ ERROR: Encryption NOT detected (should be encrypted)")
        elif not should_be_encrypted and enc == 0:
            print("  ✓ Correctly identified as unencrypted")
        else:
            print("  ? Unexpected state")
            
        # Check for our log message
        if src == 1234:
            print("  ^^ Radio 1234 (should be encrypted)")
        elif src == 6969:
            print("  ^^ Radio 6969 (should be unencrypted)")
    
    # Check AMBE tables to confirm encryption
    print("\n\nVerifying with AMBE tables:")
    print("=" * 60)
    
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%' OR name LIKE 'U_%')
        ORDER BY name
    """)
    
    encrypted_tables = 0
    unencrypted_tables = 0
    
    for row in cur.fetchall():
        table_name = row[0]
        if table_name.startswith('U_'):
            unencrypted_tables += 1
        else:
            encrypted_tables += 1
    
    print(f"Encrypted tables (H_ or C_): {encrypted_tables}")
    print(f"Unencrypted tables (U_): {unencrypted_tables}")
    
    # Check for our debug messages in the logs
    print("\n\nChecking logs for debug messages:")
    print("=" * 60)
    
    try:
        with open("logs/radio_1234.log", "r") as f:
            content = f.read()
            if "Encryption detected via MI value" in content:
                print("✓ Found encryption detection message in Radio 1234 log")
            else:
                print("✗ No encryption detection message in Radio 1234 log")
    except:
        print("Could not read Radio 1234 log")
    
    try:
        with open("logs/radio_6969.log", "r") as f:
            content = f.read()
            if "Encryption detected via MI value" in content:
                print("✓ Found encryption detection message in Radio 6969 log")
            else:
                print("✗ No encryption detection message in Radio 6969 log")
    except:
        print("Could not read Radio 6969 log")
    
    conn.close()

if __name__ == "__main__":
    db_file = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_001756.db"
    print(f"Checking {db_file}")
    check_encryption_fix(db_file)