#!/usr/bin/env python3
"""
Check what frame data we actually have
"""
import sqlite3
import glob
import os

def check_database(db_path):
    """Check database contents"""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check if table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    print(f"Tables: {tables}")
    
    if 'dmr_frames' not in tables:
        print("No dmr_frames table")
        conn.close()
        return
    
    # Count records
    cur.execute("SELECT COUNT(*) FROM dmr_frames")
    count = cur.fetchone()[0]
    print(f"Total records: {count}")
    
    # Check for AMBE data
    cur.execute("SELECT COUNT(*) FROM dmr_frames WHERE ambe_hex_frame1 IS NOT NULL")
    ambe_count = cur.fetchone()[0]
    print(f"Records with AMBE data: {ambe_count}")
    
    if ambe_count > 0:
        # Get sample frames
        cur.execute("""
            SELECT ambe_hex_frame1, ambe_hex_frame2, ambe_hex_frame3
            FROM dmr_frames
            WHERE ambe_hex_frame1 IS NOT NULL
            LIMIT 5
        """)
        
        print("\nSample AMBE frames:")
        for i, row in enumerate(cur.fetchall()):
            print(f"Record {i+1}:")
            for j, frame in enumerate(row):
                if frame:
                    print(f"  Frame {j+1}: {frame}")
                    
                    # Look for patterns
                    if frame == "000000000000000000":
                        print("    -> ALL ZEROS!")
                    elif len(set(frame.lower())) <= 2:
                        print("    -> Simple pattern!")
    
    conn.close()

if __name__ == "__main__":
    # List databases
    db_pattern = "/home/ubuntu/dsd-fme_sqlite/dmr_attack_analysis/*.db"
    db_files = glob.glob(db_pattern)
    
    print(f"Looking for databases matching: {db_pattern}")
    print(f"Found {len(db_files)} databases")
    
    for db_file in db_files:
        print(f"\n=== {os.path.basename(db_file)} ===")
        check_database(db_file)