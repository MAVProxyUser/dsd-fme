#!/usr/bin/env python3

import sqlite3
import pandas as pd
from datetime import datetime
from collections import Counter

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm (32 steps)"""
    lfsr = current_mi
    
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

def analyze_capture(db_path):
    print(f"Analyzing: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get correlations table
    try:
        correlations = pd.read_sql_query("""
            SELECT * FROM dmr_correlations 
            ORDER BY timestamp
        """, conn)
        
        if not correlations.empty:
            print(f"\n=== CORRELATIONS ===")
            print(f"Total H-MI/C-MI pairs: {len(correlations)}")
            
            # Get unique H-MI values
            h_mi_values = correlations['header_mi'].unique()
            print(f"Unique H-MI values: {len(h_mi_values)}")
            for h_mi in h_mi_values:
                print(f"  H-MI: 0x{h_mi:08X}")
    except:
        print("No correlations table found")
    
    # Get all C_* tables for complete analysis
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
        ORDER BY name
    """, conn)
    
    total_frames = 0
    all_timestamps = []
    c_mi_list = []
    
    print(f"\n=== C-MI ANALYSIS ===")
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
        
        print(f"\n=== CAPTURE STATISTICS ===")
        print(f"Capture duration: {duration:.1f} seconds")
        print(f"C-MI capture rate: {len(c_mi_list)/duration:.2f} per second")
        print(f"Frame capture rate: {total_frames/duration:.2f} per second")
    
    # Sort C-MI values to analyze progression
    sorted_c_mi = sorted(c_mi_list)
    
    # Analyze LFSR jumps
    print(f"\n=== LFSR JUMP ANALYSIS ===")
    jumps = []
    
    for i in range(1, len(sorted_c_mi)):
        # Simple difference (may need LFSR position calculation)
        jump = sorted_c_mi[i] - sorted_c_mi[i-1]
        jumps.append(jump)
    
    if jumps:
        jump_counter = Counter(jumps)
        total_jumps = len(jumps)
        
        for jump, count in jump_counter.most_common(10):
            percentage = (count / total_jumps) * 100
            print(f"Jump {jump:+d}: {count} occurrences ({percentage:.1f}%)")
    
    # Check first few C-MI values
    print(f"\n=== C-MI SEQUENCE (first 20) ===")
    for i, c_mi in enumerate(sorted_c_mi[:20]):
        print(f"#{i+1}: 0x{c_mi:08X}")
    
    # Check superframes for H-MI
    try:
        superframes = pd.read_sql_query("SELECT DISTINCT h_mi FROM superframes WHERE h_mi IS NOT NULL", conn)
        if not superframes.empty:
            print(f"\n=== H-MI FROM SUPERFRAMES ===")
            for h_mi in superframes['h_mi'].unique():
                if h_mi and h_mi > 0:
                    print(f"H-MI: 0x{h_mi:08X}")
    except:
        pass
    
    conn.close()

if __name__ == "__main__":
    # Find latest database
    import glob
    import os
    
    db_files = glob.glob("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_*.db")
    if db_files:
        latest_db = max(db_files, key=os.path.getctime)
        analyze_capture(latest_db)