#!/usr/bin/env python3

import sqlite3
import pandas as pd
from collections import defaultdict
import numpy as np

def analyze_transmission_patterns(db_path):
    """Analyze transmission patterns to find call boundaries and beeps"""
    print(f"Analyzing transmission patterns in: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get all frames with timestamps
    all_frame_data = []
    
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
        ORDER BY name
    """, conn)
    
    print(f"\nCollecting frames from {len(c_tables)} C-MI tables...")
    
    for table_name in c_tables['name']:
        c_mi = int(table_name.split('_')[1], 16)
        
        frames = pd.read_sql_query(f"""
            SELECT ambe_hex, timestamp, mi_full
            FROM '{table_name}'
            ORDER BY timestamp
        """, conn)
        
        for _, row in frames.iterrows():
            all_frame_data.append({
                'ambe_hex': row['ambe_hex'],
                'timestamp': pd.to_datetime(row['timestamp']),
                'c_mi': c_mi,
                'mi_full': row['mi_full']
            })
    
    # Sort by timestamp
    all_frame_data.sort(key=lambda x: x['timestamp'])
    
    print(f"Total frames: {len(all_frame_data)}")
    
    # Analyze timing gaps to find transmission boundaries
    print("\n=== TRANSMISSION BOUNDARY ANALYSIS ===")
    
    gaps = []
    for i in range(1, len(all_frame_data)):
        time_diff = (all_frame_data[i]['timestamp'] - 
                    all_frame_data[i-1]['timestamp']).total_seconds()
        
        if time_diff > 0.5:  # Gap > 500ms suggests new transmission
            gaps.append({
                'index': i,
                'gap': time_diff,
                'before_frame': all_frame_data[i-1],
                'after_frame': all_frame_data[i]
            })
    
    print(f"Found {len(gaps)} potential transmission boundaries")
    
    # Look at frames before gaps (potential call end beeps)
    print("\n=== FRAMES BEFORE TRANSMISSION GAPS ===")
    
    end_frames = defaultdict(int)
    for gap in gaps[:10]:  # First 10 gaps
        # Look at last 5 frames before gap
        start_idx = max(0, gap['index'] - 5)
        end_idx = gap['index']
        
        print(f"\nGap at index {gap['index']} ({gap['gap']:.1f}s):")
        for i in range(start_idx, end_idx):
            frame = all_frame_data[i]
            print(f"  {i}: {frame['ambe_hex']} (C-MI: 0x{frame['c_mi']:08X})")
            end_frames[frame['ambe_hex']] += 1
    
    # Check for patterns within transmissions
    print("\n=== CONSECUTIVE FRAME ANALYSIS ===")
    
    consecutive_patterns = defaultdict(list)
    
    for i in range(len(all_frame_data) - 1):
        if all_frame_data[i]['ambe_hex'] == all_frame_data[i+1]['ambe_hex']:
            pattern = all_frame_data[i]['ambe_hex']
            consecutive_patterns[pattern].append(i)
    
    print(f"Found {len(consecutive_patterns)} frames that repeat consecutively")
    
    if consecutive_patterns:
        print("\nMost repeated consecutive frames:")
        sorted_patterns = sorted(consecutive_patterns.items(), 
                               key=lambda x: len(x[1]), 
                               reverse=True)[:10]
        
        for pattern, indices in sorted_patterns:
            print(f"  {pattern}: {len(indices)} times")
            print(f"    At indices: {indices[:5]}...")  # Show first 5
    
    # Check if encryption is changing the beep pattern
    print("\n=== ENCRYPTION PATTERN ANALYSIS ===")
    
    # Group frames by C-MI and check if patterns vary
    frames_by_cmi = defaultdict(list)
    for frame in all_frame_data:
        frames_by_cmi[frame['c_mi']].append(frame['ambe_hex'])
    
    # Look for C-MI values with repeated frames
    for c_mi, frames in frames_by_cmi.items():
        if len(frames) > 10:
            unique_frames = len(set(frames))
            if unique_frames < len(frames):
                print(f"\nC-MI 0x{c_mi:08X}: {len(frames)} frames, {unique_frames} unique")
                
                # Count occurrences
                frame_counts = defaultdict(int)
                for frame in frames:
                    frame_counts[frame] += 1
                
                # Show repeated frames
                repeated = [(f, c) for f, c in frame_counts.items() if c > 1]
                if repeated:
                    print("  Repeated frames:")
                    for frame, count in sorted(repeated, 
                                             key=lambda x: x[1], 
                                             reverse=True)[:3]:
                        print(f"    {frame}: {count} times")
    
    conn.close()

# Run the analysis
db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_025824.db"
analyze_transmission_patterns(db_path)