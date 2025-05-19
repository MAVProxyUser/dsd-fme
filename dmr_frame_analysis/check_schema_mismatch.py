#!/usr/bin/env python3
"""
Check database schema mismatch issue
"""
import sqlite3

def check_schema(db_path):
    """Check database schema"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    
    print(f"Tables in {db_path}:")
    for table in tables:
        print(f"\n{table}:")
        
        # Get table schema
        cur.execute(f"PRAGMA table_info({table})")
        columns = cur.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
    
    # Check if superframes table exists
    if 'superframes' not in tables:
        print("\nERROR: 'superframes' table is missing!")
        print("This explains the error: 'no such table: main.superframes'")
    
    # Check AMBE table for superframe_id column
    ambe_tables = [t for t in tables if t.startswith(('U_', 'H_', 'C_'))]
    if ambe_tables:
        print("\nChecking AMBE table columns:")
        for table in ambe_tables[:1]:  # Check just one
            cur.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cur.fetchall()]
            print(f"{table} columns: {columns}")
            
            if 'superframe_id' not in columns:
                print(f"ERROR: '{table}' is missing 'superframe_id' column!")
                print("This explains the error: 'table U_00000000_S0 has no column named superframe_id'")
    
    conn.close()

if __name__ == "__main__":
    db_file = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_003136.db"
    check_schema(db_file)