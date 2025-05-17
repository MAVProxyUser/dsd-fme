#!/usr/bin/env python3

import sqlite3
import pandas as pd
from datetime import datetime
from collections import Counter

def analyze_capture(db_path):
    print(f"Analyzing: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get all C_* tables
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
        ORDER BY name
    """, conn)
    
    total_frames = 0
    all_timestamps = []
    c_mi_list = []
    
    print(f"Found {len(c_tables)} C-MI tables")
    
    for table_name in c_tables['name']:
        # Extract C-MI value from table name
        c_mi = int(table_name.split('_')[1], 16)
        c_mi_list.append(c_mi)
        
        # Count frames in table
        frame_count = pd.read_sql_query(f"SELECT COUNT(*) as count FROM '{table_name}'", conn)
        frames_in_table = frame_count['count'].iloc[0]
        total_frames += frames_in_table
        
        # Get timestamps
        if frames_in_table > 0:
            timestamps = pd.read_sql_query(f"SELECT timestamp FROM '{table_name}'", conn)
            all_timestamps.extend(pd.to_datetime(timestamps['timestamp']))
    
    print(f"Total AMBE frames: {total_frames}")
    print(f"Unique C-MI values: {len(c_mi_list)}")
    
    # Calculate capture duration
    if all_timestamps:
        min_time = min(all_timestamps)
        max_time = max(all_timestamps)
        duration = (max_time - min_time).total_seconds()
        
        print(f"\nCapture Statistics:")
        print(f"Capture duration: {duration:.1f} seconds")
        print(f"C-MI capture rate: {len(c_mi_list)/duration:.2f} per second")
        print(f"Frame capture rate: {total_frames/duration:.2f} per second")
    
    # Analyze C-MI progression
    print("\nC-MI Values (first 10):")
    for i, c_mi in enumerate(sorted(c_mi_list)[:10]):
        print(f"C-MI #{i+1}: 0x{c_mi:08X}")
    
    # Check for H-MI in superframes table
    try:
        superframes = pd.read_sql_query("SELECT DISTINCT h_mi FROM superframes", conn)
        if not superframes.empty:
            print(f"\nH-MI values from superframes:")
            for h_mi in superframes['h_mi'].unique():
                if h_mi is not None:
                    print(f"H-MI: 0x{h_mi:08X}")
    except:
        pass
    
    conn.close()

if __name__ == "__main__":
    # Analyze the 30-second capture
    analyze_capture("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_025428.db")