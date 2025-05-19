#!/usr/bin/env python3

import sqlite3
import glob
from datetime import datetime
import matplotlib.pyplot as plt
from collections import defaultdict

# Get the latest two databases
databases = sorted(glob.glob("dmr_capture_*.db"))
if len(databases) < 2:
    print("Need at least 2 databases to correlate")
    exit(1)

# Use the most recent two
db1_file = databases[-2]
db2_file = databases[-1]

print(f"Correlating transmissions between:")
print(f"  DB1: {db1_file}")
print(f"  DB2: {db2_file}")

# Function to get transmission data
def get_transmission_data(db_file):
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    
    # Get source radio ID
    cursor.execute("SELECT DISTINCT source_id FROM superframes WHERE source_id IS NOT NULL")
    source_id = cursor.fetchone()
    source_id = source_id[0] if source_id else "Unknown"
    
    # Get superframe timings
    cursor.execute("""
        SELECT id, start_timestamp, slot, h_mi, c_mi, frame_count
        FROM superframes
        ORDER BY start_timestamp
    """)
    superframes = cursor.fetchall()
    
    # Get AMBE frame counts per superframe
    ambe_counts = {}
    
    # Check encrypted tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')")
    encrypted_tables = cursor.fetchall()
    
    for table_name in encrypted_tables:
        table = table_name[0]
        cursor.execute(f"""
            SELECT superframe_id, COUNT(*) 
            FROM {table} 
            WHERE superframe_id IS NOT NULL
            GROUP BY superframe_id
        """)
        for sf_id, count in cursor.fetchall():
            ambe_counts[sf_id] = ambe_counts.get(sf_id, 0) + count
    
    # Check unencrypted tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'U_%'")
    unencrypted_tables = cursor.fetchall()
    
    for table_name in unencrypted_tables:
        table = table_name[0]
        cursor.execute(f"""
            SELECT superframe_id, COUNT(*) 
            FROM {table}
            WHERE superframe_id IS NOT NULL
            GROUP BY superframe_id
        """)
        for sf_id, count in cursor.fetchall():
            ambe_counts[sf_id] = ambe_counts.get(sf_id, 0) + count
    
    db.close()
    
    return {
        'source_id': source_id,
        'superframes': superframes,
        'ambe_counts': ambe_counts
    }

# Get data from both databases
data1 = get_transmission_data(db1_file)
data2 = get_transmission_data(db2_file)

print(f"\nRadio {data1['source_id']}: {len(data1['superframes'])} superframes")
print(f"Radio {data2['source_id']}: {len(data2['superframes'])} superframes")

# Convert timestamps and find overlaps
overlaps = []

for i, sf1 in enumerate(data1['superframes']):
    sf1_id, sf1_time, sf1_slot, sf1_h_mi, sf1_c_mi, sf1_frames = sf1
    sf1_timestamp = datetime.strptime(sf1_time, '%Y-%m-%d %H:%M:%S')
    sf1_ambe = data1['ambe_counts'].get(sf1_id, 0)
    
    for j, sf2 in enumerate(data2['superframes']):
        sf2_id, sf2_time, sf2_slot, sf2_h_mi, sf2_c_mi, sf2_frames = sf2
        sf2_timestamp = datetime.strptime(sf2_time, '%Y-%m-%d %H:%M:%S')
        sf2_ambe = data2['ambe_counts'].get(sf2_id, 0)
        
        # Check if timestamps are within 1 second of each other
        time_diff = abs((sf1_timestamp - sf2_timestamp).total_seconds())
        
        if time_diff < 1.0:
            overlaps.append({
                'radio1': data1['source_id'],
                'radio2': data2['source_id'],
                'time1': sf1_timestamp,
                'time2': sf2_timestamp,
                'time_diff': time_diff,
                'ambe1': sf1_ambe,
                'ambe2': sf2_ambe,
                'frame_diff': abs(sf1_ambe - sf2_ambe)
            })

print(f"\nFound {len(overlaps)} overlapping transmissions")

# Analyze patterns
if overlaps:
    print("\nCorrelations (within 1 second):")
    print("Time1                | Time2                | Diff(s) | Radio1 AMBE | Radio2 AMBE | Frame Diff")
    print("-" * 90)
    
    for overlap in overlaps[:20]:  # Show first 20
        print(f"{overlap['time1']} | {overlap['time2']} | {overlap['time_diff']:.3f}   | "
              f"{overlap['ambe1']:11d} | {overlap['ambe2']:11d} | {overlap['frame_diff']:10d}")
    
    # Statistical analysis
    frame_diffs = [o['frame_diff'] for o in overlaps]
    avg_diff = sum(frame_diffs) / len(frame_diffs) if frame_diffs else 0
    
    print(f"\nAverage frame count difference: {avg_diff:.1f}")
    print(f"Min frame difference: {min(frame_diffs) if frame_diffs else 0}")
    print(f"Max frame difference: {max(frame_diffs) if frame_diffs else 0}")
    
    # Plot timeline
    plt.figure(figsize=(12, 6))
    
    # Plot Radio 1
    times1 = [datetime.strptime(sf[1], '%Y-%m-%d %H:%M:%S') for sf in data1['superframes']]
    frames1 = [data1['ambe_counts'].get(sf[0], 0) for sf in data1['superframes']]
    plt.scatter(times1, [1]*len(times1), c=frames1, cmap='Blues', s=50, label=f'Radio {data1["source_id"]}')
    
    # Plot Radio 2
    times2 = [datetime.strptime(sf[1], '%Y-%m-%d %H:%M:%S') for sf in data2['superframes']]
    frames2 = [data2['ambe_counts'].get(sf[0], 0) for sf in data2['superframes']]
    plt.scatter(times2, [2]*len(times2), c=frames2, cmap='Reds', s=50, label=f'Radio {data2["source_id"]}')
    
    # Mark overlaps
    overlap_times = [(o['time1'], o['time2']) for o in overlaps]
    for t1, t2 in overlap_times:
        plt.plot([t1, t2], [1, 2], 'g-', alpha=0.3, linewidth=1)
    
    plt.ylim(0.5, 2.5)
    plt.yticks([1, 2], [f'Radio {data1["source_id"]}', f'Radio {data2["source_id"]}'])
    plt.xlabel('Time')
    plt.title('Transmission Timeline Correlation')
    plt.legend()
    plt.tight_layout()
    plt.savefig('dual_transmission_correlation.png', dpi=150)
    print("\nSaved correlation plot to dual_transmission_correlation.png")