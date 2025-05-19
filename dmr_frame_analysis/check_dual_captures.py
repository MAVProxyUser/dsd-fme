#!/usr/bin/env python3
"""
Check dual capture databases for radio IDs
"""
import sqlite3
import glob

def check_capture(db_path):
    """Analyze capture database"""
    print(f"\n=== {db_path} ===")
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Check superframes with radio IDs
        cur.execute("""
            SELECT id, source_id, target_id, encrypted, h_mi, c_mi, start_timestamp
            FROM superframes
            WHERE source_id IS NOT NULL OR target_id IS NOT NULL
            LIMIT 10
        """)
        
        results = cur.fetchall()
        if results:
            print(f"Found {len(results)} transmissions with IDs:")
            for row in results:
                id_, src, tgt, enc, h_mi, c_mi, ts = row
                enc_status = "Encrypted" if enc else "Unencrypted"
                print(f"  ID {id_}: {src} → {tgt} ({enc_status}) H_MI: {h_mi:08x}, C_MI: {c_mi:08x}, Time: {ts}")
                
                # Identify radios
                if src == 6969:
                    print("    ^^ Radio 6969 (unencrypted)")
                elif src == 1234:
                    print("    ^^ Radio 1234 (encrypted)")
                    
                if tgt == 16777215:
                    print("    ^^ All Call (broadcast)")
        else:
            print("No transmissions with radio IDs found")
            
            # Check if any data exists
            cur.execute("SELECT COUNT(*) FROM superframes")
            count = cur.fetchone()[0]
            print(f"Total superframes: {count}")
        
        # Check AMBE tables
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%' OR name LIKE 'U_%')
        """)
        
        tables = cur.fetchall()
        if tables:
            print(f"\nAMBE tables ({len(tables)}):")
            for table in tables:
                table_name = table[0]
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]
                print(f"  {table_name}: {count} frames")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Find all databases
    db_files = sorted(glob.glob("/home/ubuntu/dsd-fme_sqlite/build/*.db"))
    
    print(f"Found {len(db_files)} database files")
    
    for db in db_files:
        check_capture(db)