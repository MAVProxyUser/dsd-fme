#!/usr/bin/env python3

import sqlite3
import glob
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Get the latest two databases
databases = sorted(glob.glob("dmr_capture_*.db"))[-2:]

print(f"Visualizing superframe synchronization between:")
print(f"  DB1: {databases[0]}")
print(f"  DB2: {databases[1]}")

def get_superframe_data(db_file):
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    
    # Get radio ID
    cursor.execute("SELECT DISTINCT source_id FROM superframes WHERE source_id IS NOT NULL")
    source_id = cursor.fetchone()
    source_id = source_id[0] if source_id else "Unknown"
    
    # Get superframe data with AMBE counts
    cursor.execute("""
        SELECT 
            s.id,
            s.start_timestamp,
            s.h_mi,
            s.c_mi,
            s.source_id,
            s.target_id
        FROM superframes s
        ORDER BY s.start_timestamp
    """)
    
    superframes = []
    for row in cursor.fetchall():
        sf_id, timestamp, h_mi, c_mi, src, tgt = row
        
        # Count AMBE frames for this superframe
        total_frames = 0
        encrypted_frames = 0
        
        # Check all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S0'")
        tables = cursor.fetchall()
        
        for table_name in tables:
            table = table_name[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE superframe_id = ?", (sf_id,))
            count = cursor.fetchone()[0]
            total_frames += count
            
            if not table.startswith('U_'):
                encrypted_frames += count
        
        superframes.append({
            'id': sf_id,
            'timestamp': datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S'),
            'h_mi': h_mi,
            'c_mi': c_mi,
            'source': src,
            'target': tgt,
            'total_frames': total_frames,
            'encrypted_frames': encrypted_frames,
            'radio': source_id
        })
    
    db.close()
    return superframes

# Get data from both databases
data1 = get_superframe_data(databases[0])
data2 = get_superframe_data(databases[1])

# Create visualization
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# Plot Radio 1
times1 = [sf['timestamp'] for sf in data1]
frames1 = [sf['total_frames'] for sf in data1]
colors1 = ['blue' if sf['encrypted_frames'] == 0 else 'red' for sf in data1]

ax1.bar(times1, frames1, width=0.0001, color=colors1, alpha=0.7)
ax1.set_ylabel('Frames per Superframe')
ax1.set_title(f'Radio {data1[0]["radio"]} - {"Unencrypted" if data1[0]["encrypted_frames"] == 0 else "Encrypted"}')
ax1.grid(True, alpha=0.3)

# Plot Radio 2
times2 = [sf['timestamp'] for sf in data2]
frames2 = [sf['total_frames'] for sf in data2]
colors2 = ['blue' if sf['encrypted_frames'] == 0 else 'red' for sf in data2]

ax2.bar(times2, frames2, width=0.0001, color=colors2, alpha=0.7)
ax2.set_ylabel('Frames per Superframe')
ax2.set_title(f'Radio {data2[0]["radio"]} - {"Unencrypted" if data2[0]["radio"] == "6969" else "Encrypted"}')
ax2.grid(True, alpha=0.3)

# Plot time correlation
correlation_matches = []
for sf1 in data1:
    for sf2 in data2:
        time_diff = abs((sf1['timestamp'] - sf2['timestamp']).total_seconds())
        if time_diff < 0.1:  # Within 100ms
            correlation_matches.append({
                'time': sf1['timestamp'],
                'frames1': sf1['total_frames'],
                'frames2': sf2['total_frames'],
                'match': sf1['total_frames'] == sf2['total_frames'] and sf1['total_frames'] > 0
            })

if correlation_matches:
    match_times = [m['time'] for m in correlation_matches]
    match_values = [1 if m['match'] else 0.5 for m in correlation_matches]
    match_colors = ['green' if m['match'] else 'orange' for m in correlation_matches]
    
    ax3.scatter(match_times, match_values, c=match_colors, s=50, alpha=0.7)
    ax3.set_ylabel('Correlation')
    ax3.set_title('Frame Count Matches (Green = Perfect Match, Orange = Different)')
    ax3.set_ylim(0, 1.5)
    ax3.grid(True, alpha=0.3)

# Format x-axis
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
plt.xticks(rotation=45)
plt.xlabel('Time')

plt.tight_layout()
plt.savefig('superframe_sync_timeline.png', dpi=150, bbox_inches='tight')
print("Saved visualization to superframe_sync_timeline.png")

# Create a detailed correlation analysis
plt.figure(figsize=(10, 6))

# Find exact time matches
exact_matches = []
for sf1 in data1:
    for sf2 in data2:
        if sf1['timestamp'] == sf2['timestamp'] and sf1['total_frames'] > 0 and sf2['total_frames'] > 0:
            exact_matches.append((sf1['total_frames'], sf2['total_frames']))

if exact_matches:
    x_vals = [m[0] for m in exact_matches]
    y_vals = [m[1] for m in exact_matches]
    
    plt.scatter(x_vals, y_vals, alpha=0.6, s=50)
    plt.xlabel(f'Radio {data1[0]["radio"]} Frame Count')
    plt.ylabel(f'Radio {data2[0]["radio"]} Frame Count')
    plt.title('Frame Count Correlation at Matching Timestamps')
    
    # Add diagonal line for perfect correlation
    max_val = max(max(x_vals), max(y_vals))
    plt.plot([0, max_val], [0, max_val], 'r--', alpha=0.5, label='Perfect correlation')
    
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig('frame_count_correlation.png', dpi=150)
    print("Saved correlation plot to frame_count_correlation.png")
    
    # Calculate correlation statistics
    if len(exact_matches) > 1:
        import numpy as np
        correlation = np.corrcoef(x_vals, y_vals)[0, 1]
        print(f"\nFrame count correlation coefficient: {correlation:.3f}")
        print(f"Number of matching timestamps with data: {len(exact_matches)}")
        
        # Count perfect matches
        perfect_matches = sum(1 for x, y in exact_matches if x == y)
        print(f"Perfect frame count matches: {perfect_matches}/{len(exact_matches)}")

print(f"\nTotal superframes analyzed:")
print(f"  Radio {data1[0]['radio']}: {len(data1)}")
print(f"  Radio {data2[0]['radio']}: {len(data2)}")

# Count superframes with data
sf_with_data1 = sum(1 for sf in data1 if sf['total_frames'] > 0)
sf_with_data2 = sum(1 for sf in data2 if sf['total_frames'] > 0)

print(f"Superframes with AMBE data:")
print(f"  Radio {data1[0]['radio']}: {sf_with_data1}")
print(f"  Radio {data2[0]['radio']}: {sf_with_data2}")