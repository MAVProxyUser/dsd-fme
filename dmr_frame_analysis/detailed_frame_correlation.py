#!/usr/bin/env python3

import sqlite3
import glob
from datetime import datetime
from collections import defaultdict

# Get the latest two databases
databases = sorted(glob.glob("dmr_capture_*.db"))[-2:]

print(f"Analyzing frame-level correlation between:")
print(f"  DB1: {databases[0]}")
print(f"  DB2: {databases[1]}")

# Get detailed frame data from each database
def get_detailed_frames(db_file):
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    
    # Get radio ID
    cursor.execute("SELECT DISTINCT source_id FROM superframes WHERE source_id IS NOT NULL")
    source_id = cursor.fetchone()
    source_id = source_id[0] if source_id else "Unknown"
    
    # Get all AMBE frames with timestamps
    all_frames = []
    
    # Get from all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S0'")
    tables = cursor.fetchall()
    
    for table_name in tables:
        table = table_name[0]
        # Get frame data with superframe timestamp
        cursor.execute(f"""
            SELECT a.timestamp, a.superframe_id, s.start_timestamp, 
                   a.ambe_hex, a.mi_full, '{table}' as table_name
            FROM {table} a
            LEFT JOIN superframes s ON a.superframe_id = s.id
            ORDER BY a.timestamp
        """)
        frames = cursor.fetchall()
        all_frames.extend(frames)
    
    db.close()
    
    # Sort by timestamp
    all_frames.sort(key=lambda x: x[0])
    
    return {
        'source_id': source_id,
        'frames': all_frames
    }

data1 = get_detailed_frames(databases[0])
data2 = get_detailed_frames(databases[1])

print(f"\nRadio {data1['source_id']}: {len(data1['frames'])} total AMBE frames")
print(f"Radio {data2['source_id']}: {len(data2['frames'])} total AMBE frames")

# Find exact timestamp matches
exact_matches = []
close_matches = []

# Create a timestamp index for faster lookup
timestamp_index2 = defaultdict(list)
for i, frame2 in enumerate(data2['frames']):
    timestamp_index2[frame2[0]].append(i)

# Look for matches
for i, frame1 in enumerate(data1['frames']):
    timestamp1 = frame1[0]
    
    # Check for exact matches
    if timestamp1 in timestamp_index2:
        for j in timestamp_index2[timestamp1]:
            frame2 = data2['frames'][j]
            exact_matches.append((frame1, frame2))
    
    # Check for close matches (within 1 second)
    try:
        dt1 = datetime.strptime(timestamp1, '%Y-%m-%d %H:%M:%S')
        
        for dt_str in timestamp_index2.keys():
            dt2 = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            diff = abs((dt1 - dt2).total_seconds())
            
            if diff < 1.0 and diff > 0:
                for j in timestamp_index2[dt_str]:
                    frame2 = data2['frames'][j]
                    close_matches.append((frame1, frame2, diff))
    except:
        pass

print(f"\nFound {len(exact_matches)} exact timestamp matches")
print(f"Found {len(close_matches)} close matches (within 1 second)")

# Analyze exact matches
if exact_matches:
    print("\nExact Timestamp Matches (first 20):")
    print("Timestamp           | Radio 1 Table    | Radio 2 Table    | R1 MI      | R2 MI")
    print("-" * 80)
    
    for frame1, frame2 in exact_matches[:20]:
        print(f"{frame1[0]} | {frame1[5]:16s} | {frame2[5]:16s} | "
              f"{frame1[4] or 0:10d} | {frame2[4] or 0:10d}")

# Frame length analysis
print("\nFrame Pattern Analysis:")

# Group frames by superframe
sf_frames1 = defaultdict(list)
sf_frames2 = defaultdict(list)

for frame in data1['frames']:
    if frame[1]:  # Has superframe_id
        sf_frames1[frame[1]].append(frame)

for frame in data2['frames']:
    if frame[1]:  # Has superframe_id
        sf_frames2[frame[1]].append(frame)

# Compare superframe sizes
size_comparison = []
for sf_id1, frames1 in sf_frames1.items():
    for sf_id2, frames2 in sf_frames2.items():
        # Check if they're close in time
        if frames1 and frames2:
            try:
                dt1 = datetime.strptime(frames1[0][2], '%Y-%m-%d %H:%M:%S')
                dt2 = datetime.strptime(frames2[0][2], '%Y-%m-%d %H:%M:%S')
                
                if abs((dt1 - dt2).total_seconds()) < 1.0:
                    size_comparison.append({
                        'time1': dt1,
                        'time2': dt2,
                        'size1': len(frames1),
                        'size2': len(frames2),
                        'encrypted1': 'C_' in frames1[0][5] or 'H_' in frames1[0][5],
                        'encrypted2': 'C_' in frames2[0][5] or 'H_' in frames2[0][5]
                    })
            except:
                pass

print(f"\nFound {len(size_comparison)} matching superframes")

if size_comparison:
    # Separate by encryption status
    both_encrypted = [s for s in size_comparison if s['encrypted1'] and s['encrypted2']]
    both_unencrypted = [s for s in size_comparison if not s['encrypted1'] and not s['encrypted2']]
    mixed = [s for s in size_comparison if s['encrypted1'] != s['encrypted2']]
    
    print(f"  Both encrypted: {len(both_encrypted)}")
    print(f"  Both unencrypted: {len(both_unencrypted)}")
    print(f"  Mixed (one encrypted): {len(mixed)}")
    
    # Size correlation
    if both_unencrypted:
        print("\nUnencrypted frame count correlation:")
        sizes1 = [s['size1'] for s in both_unencrypted]
        sizes2 = [s['size2'] for s in both_unencrypted]
        
        # Check if sizes match
        exact_size_matches = sum(1 for s in both_unencrypted if s['size1'] == s['size2'])
        print(f"  Exact size matches: {exact_size_matches}/{len(both_unencrypted)}")
        print(f"  Average size Radio 1: {sum(sizes1)/len(sizes1):.1f}")
        print(f"  Average size Radio 2: {sum(sizes2)/len(sizes2):.1f}")
    
    if both_encrypted:
        print("\nEncrypted frame count correlation:")
        sizes1 = [s['size1'] for s in both_encrypted]
        sizes2 = [s['size2'] for s in both_encrypted]
        
        # Check if sizes match
        exact_size_matches = sum(1 for s in both_encrypted if s['size1'] == s['size2'])
        print(f"  Exact size matches: {exact_size_matches}/{len(both_encrypted)}")
        print(f"  Average size Radio 1: {sum(sizes1)/len(sizes1):.1f}")
        print(f"  Average size Radio 2: {sum(sizes2)/len(sizes2):.1f}")