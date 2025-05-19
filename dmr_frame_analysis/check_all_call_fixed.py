#!/usr/bin/env python3
"""
Check for all call ID 16777215 in captures - fixed version
"""
import sqlite3
import glob

def check_for_all_call(db_path):
    """Look for all call ID 16777215"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # First check what columns exist
    cur.execute("PRAGMA table_info(superframes)")
    columns = [col[1] for col in cur.fetchall()]
    print(f"Superframes columns: {columns}")
    
    # Check superframes table
    cur.execute("""
        SELECT id, source_id, target_id, group_call, start_timestamp
        FROM superframes
        WHERE source_id = 16777215 OR target_id = 16777215
    """)
    
    results = cur.fetchall()
    if results:
        print(f"\nFound {len(results)} 'All Call' transmissions (ID: 16777215):")
        for row in results:
            id_, src, tgt, group, ts = row
            print(f"  ID: {id_}, Source: {src}, Target: {tgt}, Group: {group}, Time: {ts}")
    else:
        print("\nNo 'All Call' transmissions found with ID 16777215")
    
    # Check for any radio IDs
    cur.execute("""
        SELECT DISTINCT source_id, target_id, group_call
        FROM superframes
        WHERE source_id IS NOT NULL AND target_id IS NOT NULL
        ORDER BY source_id, target_id
    """)
    
    print("\nAll Radio IDs found:")
    for row in cur.fetchall():
        src, tgt, group = row
        call_type = "Group" if group else "Private"
        print(f"  Source: {src}, Target: {tgt} ({call_type})")
        
        # Note special IDs
        if src == 16777215:
            print(f"    ^^ Source is 'All Call' (broadcast)")
        if tgt == 16777215:
            print(f"    ^^ Target is 'All Call' (broadcast)")
        if src == 6969:
            print(f"    ^^ Radio 6969 (no encryption)")
        if src == 1234:
            print(f"    ^^ Radio 1234 (encrypted)")
    
    # Check which tables have AMBE data
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%' OR name LIKE 'U_%')
    """)
    
    print("\nAMBE data tables:")
    for row in cur.fetchall():
        table_name = row[0]
        # Count frames
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        print(f"  {table_name}: {count} frames")
        
        # Parse table name
        parts = table_name.split('_')
        if len(parts) >= 2:
            enc_type = parts[0]
            mi_value = parts[1]
            slot = parts[2] if len(parts) > 2 else "?"
            
            if enc_type == 'U':
                print(f"    Unencrypted (MI: {mi_value})")
            elif enc_type == 'H':
                print(f"    Header MI: {mi_value}")
            elif enc_type == 'C':
                print(f"    Control MI: {mi_value}")
    
    # Check for 16777215 in hex (0xFFFFFF)
    print("\nChecking if 16777215 appears as target in other forms...")
    print(f"16777215 in hex: 0x{16777215:X}")
    print(f"16777215 in binary: 0b{16777215:b}")
    print("This is the maximum 24-bit value (all 1s), commonly used for broadcast/all call")
    
    conn.close()

if __name__ == "__main__":
    # Check latest database
    db_files = sorted(glob.glob("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_*.db"))
    
    if db_files:
        latest_db = db_files[-1]
        print(f"Analyzing {latest_db}")
        check_for_all_call(latest_db)
    else:
        print("No database files found")