#!/usr/bin/env python3
"""
Check actual table names in database
"""
import sqlite3

def check_tables(db_path):
    """Check table structure"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    print(f"Tables in {db_path}:")
    for table in tables:
        print(f"  - {table}")
        
        # Get columns for each table
        cur.execute(f"PRAGMA table_info({table})")
        columns = cur.fetchall()
        print("    Columns:")
        for col in columns:
            print(f"      {col[1]} ({col[2]})")
        
        # Count records
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"    Records: {count}")
        print()
    
    conn.close()

if __name__ == "__main__":
    databases = [
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_205116.db",
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_204818.db"
    ]
    
    for db in databases:
        print(f"\n=== {db} ===")
        check_tables(db)