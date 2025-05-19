#!/usr/bin/env python3
"""
Check all databases for radio IDs
"""
import sqlite3
import glob
import os

def check_db_for_ids(db_path):
    """Check if database contains radio IDs"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check superframes
    cur.execute("""
        SELECT id, source_id, target_id, h_mi, c_mi, encrypted
        FROM superframes
        WHERE source_id IS NOT NULL OR target_id IS NOT NULL
        LIMIT 10
    """)
    
    results = cur.fetchall()
    if results:
        print(f"Found {len(results)} superframes with IDs:")
        for row in results:
            print(f"  ID: {row[0]}, Source: {row[1]}, Target: {row[2]}, H_MI: {row[3]:08x}, C_MI: {row[4]:08x}, Enc: {row[5]}")
    else:
        # Check if ANY superframes exist
        cur.execute("SELECT COUNT(*) FROM superframes")
        count = cur.fetchone()[0]
        print(f"No IDs found. Total superframes: {count}")
        
        # Show sample of what we do have
        cur.execute("SELECT * FROM superframes LIMIT 2")
        samples = cur.fetchall()
        if samples:
            print("Sample superframe data:")
            for s in samples:
                print(f"  {s}")
    
    conn.close()

def examine_db_logger_code():
    """Check the db_logger code to see why IDs might not be saved"""
    print("\nChecking db_logger.c for ID handling...")
    
    try:
        with open("/home/ubuntu/dsd-fme_sqlite/src/db_logger.c", "r") as f:
            content = f.read()
            
            # Look for superframe INSERT statements
            if "INSERT INTO superframes" in content:
                start = content.find("INSERT INTO superframes")
                end = content.find(";", start)
                insert_stmt = content[start:end+1]
                print("Found INSERT statement:")
                print(insert_stmt[:200] + "...")
                
            # Look for source_id and target_id handling
            if "source_id" in content and "target_id" in content:
                print("\nFound ID handling in db_logger.c")
                
                # Find relevant sections
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'source_id' in line or 'target_id' in line:
                        # Show context
                        context_start = max(0, i-2)
                        context_end = min(len(lines), i+3)
                        print(f"\nLine {i}:")
                        for j in range(context_start, context_end):
                            print(f"  {j}: {lines[j]}")
    except FileNotFoundError:
        print("db_logger.c not found")

if __name__ == "__main__":
    db_files = sorted(glob.glob("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_*.db"))
    
    print("Checking all database files for radio IDs...")
    print("=" * 50)
    
    for db_file in db_files:
        print(f"\n{os.path.basename(db_file)}:")
        print("-" * 30)
        check_db_for_ids(db_file)
    
    # Check the source code
    examine_db_logger_code()