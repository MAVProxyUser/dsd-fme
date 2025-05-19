#!/usr/bin/env python3
"""
Check for all call ID 16777215 in captures
"""
import sqlite3
import glob

def check_for_all_call(db_path):
    """Look for all call ID 16777215"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check superframes table
    cur.execute("""
        SELECT id, source_id, target_id, group_call, timestamp
        FROM superframes
        WHERE source_id = 16777215 OR target_id = 16777215
    """)
    
    results = cur.fetchall()
    if results:
        print(f"\nFound {len(results)} 'All Call' transmissions (ID: 16777215):")
        for row in results:
            id_, src, tgt, group, ts = row
            print(f"  ID: {id_}, Source: {src}, Target: {tgt}, Group: {group}, Time: {ts}")
    
    # Check for any radio IDs
    cur.execute("""
        SELECT DISTINCT source_id, target_id, group_call
        FROM superframes
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