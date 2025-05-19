#!/usr/bin/env python3

import sqlite3
import glob
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

# Get the latest two databases
databases = sorted(glob.glob("dmr_capture_*.db"))[-2:]

print(f"Visualizing frame synchronization between:")
print(f"  DB1: {databases[0]}")
print(f"  DB2: {databases[1]}")

# Get frame timing data
def get_frame_timings(db_file):
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    
    # Get radio ID
    cursor.execute("SELECT DISTINCT source_id FROM superframes WHERE source_id IS NOT NULL")
    source_id = cursor.fetchone()
    source_id = source_id[0] if source_id else "Unknown"
    
    # Get superframe data with frame counts
    # Removed this complex query as it's not needed
    
    # This query is complex, let's simplify
    frames_by_time = []
    
    # Get all AMBE tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S0'")
    tables = cursor.fetchall()
    
    for table_name in tables:
        table = table_name[0]
        cursor.execute(f"""
            SELECT s.start_timestamp, COUNT(*) as frame_count,
                   CASE 
                       WHEN '{table}' LIKE 'U_%' THEN 'Unencrypted'
                       WHEN '{table}' LIKE 'H_%' THEN 'Header MI'
                       WHEN '{table}' LIKE 'C_%' THEN 'Control MI'
                   END as encryption_type,
                   s.id
            FROM {table} a
            JOIN superframes s ON a.superframe_id = s.id
            WHERE a.superframe_id IS NOT NULL
            GROUP BY s.start_timestamp, s.id
            ORDER BY s.start_timestamp
        """)
        
        for row in cursor.fetchall():
            timestamp, count, enc_type, sf_id = row
            frames_by_time.append({
                'timestamp': datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S'),
                'count': count,
                'type': enc_type,
                'radio': source_id,
                'superframe_id': sf_id
            })
    
    db.close()
    return frames_by_time

# Get data from both radios
radio1_frames = get_frame_timings(databases[0])
radio2_frames = get_frame_timings(databases[1])

# Create timeline visualization
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

# Plot Radio 1 (unencrypted)
r1_times = [f['timestamp'] for f in radio1_frames]
r1_counts = [f['count'] for f in radio1_frames]
r1_colors = ['blue' if f['type'] == 'Unencrypted' else 'red' for f in radio1_frames]

ax1.scatter(r1_times, r1_counts, c=r1_colors, alpha=0.6, s=50)
ax1.set_ylabel('Frames per Superframe')
ax1.set_title(f'Radio {radio1_frames[0]["radio"]} (Unencrypted)')
ax1.grid(True, alpha=0.3)

# Plot Radio 2 (encrypted)
r2_times = [f['timestamp'] for f in radio2_frames]
r2_counts = [f['count'] for f in radio2_frames]
r2_colors = ['green' if f['type'] == 'Header MI' else 'orange' for f in radio2_frames]

ax2.scatter(r2_times, r2_counts, c=r2_colors, alpha=0.6, s=50)
ax2.set_ylabel('Frames per Superframe')
ax2.set_title(f'Radio {radio2_frames[0]["radio"]} (Encrypted)')
ax2.grid(True, alpha=0.3)

# Format x-axis
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
plt.xticks(rotation=45)
plt.xlabel('Time')

plt.tight_layout()
plt.savefig('frame_sync_timeline.png', dpi=150, bbox_inches='tight')
print("Saved timeline to frame_sync_timeline.png")

# Create a direct comparison plot
plt.figure(figsize=(12, 8))

# Aggregate by second for clearer visualization
df1 = pd.DataFrame(radio1_frames)
df2 = pd.DataFrame(radio2_frames)

if not df1.empty and not df2.empty:
    # Round to nearest second
    df1['second'] = df1['timestamp'].dt.floor('S')
    df2['second'] = df2['timestamp'].dt.floor('S')
    
    # Sum frames per second
    r1_by_sec = df1.groupby('second')['count'].sum()
    r2_by_sec = df2.groupby('second')['count'].sum()
    
    # Merge for comparison
    comparison = pd.DataFrame({
        'Radio_6969': r1_by_sec,
        'Radio_1234': r2_by_sec
    }).fillna(0)
    
    # Plot
    comparison.plot(kind='line', figsize=(12, 6), marker='o', markersize=4)
    plt.title('Frame Count Comparison by Second')
    plt.xlabel('Time')
    plt.ylabel('Total Frames')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('frame_count_comparison.png', dpi=150, bbox_inches='tight')
    print("Saved comparison to frame_count_comparison.png")
    
    # Calculate correlation
    if len(comparison) > 1:
        correlation = comparison['Radio_6969'].corr(comparison['Radio_1234'])
        print(f"\nFrame count correlation coefficient: {correlation:.3f}")
    
    # Show simultaneous transmissions
    simultaneous = comparison[(comparison['Radio_6969'] > 0) & (comparison['Radio_1234'] > 0)]
    print(f"Seconds with simultaneous transmission: {len(simultaneous)}/{len(comparison)}")