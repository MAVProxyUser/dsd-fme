#!/usr/bin/env python3

import sqlite3
import pandas as pd
from datetime import datetime

def analyze_capture(db_path):
    print(f"Analyzing: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get correlations
    correlations = pd.read_sql_query("""
        SELECT * FROM dmr_correlations 
        ORDER BY timestamp
    """, conn)
    
    # Get total capture duration
    if not correlations.empty:
        correlations['timestamp'] = pd.to_datetime(correlations['timestamp'])
        duration = (correlations['timestamp'].max() - correlations['timestamp'].min()).total_seconds()
        
        print(f"\nCapture Statistics:")
        print(f"Total correlations: {len(correlations)}")
        print(f"Capture duration: {duration:.1f} seconds")
        print(f"Correlation rate: {len(correlations)/duration:.2f} per second")
        
        # Check LFSR jumps
        correlations = correlations.sort_values('timestamp')
        jumps = []
        
        for i in range(1, len(correlations)):
            prev_mi = correlations.iloc[i-1]['control_mi']
            curr_mi = correlations.iloc[i]['control_mi']
            
            # Calculate jump (simplified)
            jump = curr_mi - prev_mi
            jumps.append(jump)
        
        # Analyze jump patterns
        if jumps:
            from collections import Counter
            jump_counter = Counter(jumps)
            total_jumps = len(jumps)
            
            print("\nLFSR Jump Pattern Analysis:")
            for jump, count in jump_counter.most_common(10):
                percentage = (count / total_jumps) * 100
                print(f"Jump {jump:+d}: {count} occurrences ({percentage:.1f}%)")
    
    # Check for fixed H-MI
    unique_h_mi = correlations['header_mi'].unique()
    print(f"\nUnique H-MI values: {len(unique_h_mi)}")
    for h_mi in unique_h_mi:
        print(f"H-MI: 0x{h_mi:08X}")
    
    conn.close()

if __name__ == "__main__":
    # Analyze the 30-second capture
    analyze_capture("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_025428.db")