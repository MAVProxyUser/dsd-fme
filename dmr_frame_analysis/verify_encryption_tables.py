#!/usr/bin/env python3
"""
Verify encryption by checking AMBE table contents
"""
import sqlite3

def check_encryption_evidence(db_path, radio_name):
    """Check for evidence of encryption in AMBE tables"""
    print(f"\n=== {radio_name} - {db_path} ===")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all table names
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%' OR name LIKE 'U_%')
        ORDER BY name
    """)
    
    tables = cur.fetchall()
    
    for table in tables:
        table_name = table[0]
        print(f"\n{table_name}:")
        
        # Parse table name
        parts = table_name.split('_')
        if parts[0] == 'U':
            print("  Type: Unencrypted")
        elif parts[0] == 'H':
            print("  Type: Header MI")
        elif parts[0] == 'C':
            print("  Type: Control MI")
        
        print(f"  MI Value: {parts[1]}")
        
        # Get sample frames
        cur.execute(f"""
            SELECT id, ambe_hex, mi_full, algid 
            FROM {table_name} 
            LIMIT 3
        """)
        
        for row in cur.fetchall():
            id_, ambe, mi, algid = row
            print(f"  Frame {id_}: AMBE={ambe}, MI={mi:08x}, AlgID={algid}")
    
    # Check correlations table
    print("\nCorrelations:")
    cur.execute("""
        SELECT header_mi, control_mi, slot, algid
        FROM dmr_correlations
    """)
    
    for row in cur.fetchall():
        h_mi, c_mi, slot, algid = row
        print(f"  H_MI: {h_mi:08x}, C_MI: {c_mi:08x}, Slot: {slot}, AlgID: {algid}")
    
    conn.close()

if __name__ == "__main__":
    check_encryption_evidence(
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234505.db",
        "Radio 1234 (Encrypted)"
    )
    
    check_encryption_evidence(
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234506.db",
        "Radio 6969 (Unencrypted)"
    )