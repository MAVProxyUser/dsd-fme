#!/usr/bin/env python3

import sqlite3
import pandas as pd
from collections import Counter, defaultdict
import numpy as np

def analyze_unencrypted_superframes(db_path):
    """Analyze unencrypted capture from superframes table"""
    print(f"Analyzing unencrypted capture: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get the schema
    schema = pd.read_sql_query("""
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='superframes'
    """, conn)
    print(f"\nSuperframes schema:\n{schema['sql'].iloc[0]}")
    
    # Get all data from superframes
    frames = pd.read_sql_query("""
        SELECT * FROM superframes
        ORDER BY start_timestamp
    """, conn)
    
    print(f"\nTotal superframes: {len(frames)}")
    print(f"Columns: {frames.columns.tolist()}")
    
    # Show sample data
    print("\nSample data:")
    print(frames.head())
    
    # The AMBE data is likely embedded in the frames themselves
    # Let's check what's available
    non_null_counts = {}
    for col in frames.columns:
        non_null = frames[col].notna().sum()
        if non_null > 0:
            non_null_counts[col] = non_null
    
    print("\nNon-null column counts:")
    for col, count in non_null_counts.items():
        print(f"  {col}: {count}")
    
    # For unencrypted DMR, we need to look at the raw frame data
    # Let's see if there's frame data stored
    
    conn.close()

# Check if we need to parse the raw capture differently
def check_capture_output():
    """Check the actual capture output for AMBE frames"""
    print("\n=== PARSING CAPTURE OUTPUT ===")
    
    # The AMBE frames were displayed in the terminal output
    # Pattern: AMBE D82C261ECD2200 err = [0] [0]
    
    print("AMBE frames are displayed in terminal output during capture")
    print("Pattern: AMBE [16 hex chars] err = [x] [y]")
    print("\nTo properly analyze beep patterns:")
    print("1. Capture output to a file: ./dsd-fme -i rtl:0:145.125M:40 -fs -Z > capture.log")
    print("2. Parse the log file for AMBE frames")
    print("3. Identify patterns at transmission ends")

# Run the analysis
db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_032539.db"
analyze_unencrypted_superframes(db_path)
check_capture_output()