#!/usr/bin/env python3
import sqlite3
import collections
from datetime import datetime

# Connect to database  
db = sqlite3.connect('dmr_capture_20250517_010359.db')
cursor = db.cursor()

# Get all C_ tables excluding the correlations table
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C!_%' ESCAPE '!' AND name != 'dmr_correlations'")
tables = cursor.fetchall()

print(f'Found {len(tables)} C_ tables')

# Collect all last frames
last_frames = {}
all_frames = collections.defaultdict(list)

for table in tables:
    table_name = table[0]
    # Extract C-MI from table name
    parts = table_name.split('_')
    if len(parts) >= 2:
        c_mi = parts[1]
        
        # Get all frames from this table
        cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' ORDER BY id")
        frames = cursor.fetchall()
        
        if frames:
            # Store the last frame
            last_frames[c_mi] = frames[-1][1]
            
            # Store all frames
            for frame_id, frame_hex in frames:
                all_frames[frame_hex].append((c_mi, frame_id))

# Find repeated last frames
print('\n=== REPEATED LAST FRAMES ===')
last_frame_counts = collections.Counter(last_frames.values())
repeated_last_frames = [(frame, count) for frame, count in last_frame_counts.items() if count > 1]

if repeated_last_frames:
    for frame, count in repeated_last_frames:
        print(f'Frame {frame[:32]}... appears {count} times as last frame')
        # Find which C-MIs have this last frame
        c_mis = [c_mi for c_mi, last_frame in last_frames.items() if last_frame == frame]
        print(f'  In C-MIs: {", ".join(["0x" + c_mi for c_mi in c_mis[:5]])}')
else:
    print('  No repeated last frames found')

# Find most common frames overall
print('\n=== MOST COMMON FRAMES ===')
frame_counts = [(frame, len(occurrences)) for frame, occurrences in all_frames.items()]
frame_counts.sort(key=lambda x: x[1], reverse=True)

for i, (frame, count) in enumerate(frame_counts[:10]):
    print(f'{i+1}. {frame[:32]}... appears {count} times')

# Look for silence or near-silence patterns
print('\n=== SILENCE PATTERNS ===')
silence_count = 0
near_silence_count = 0

for frame, occurrences in all_frames.items():
    # Count zeros in the frame
    zero_count = frame.count('0')
    if zero_count > len(frame) * 0.9:  # More than 90% zeros
        silence_count += len(occurrences)
    elif zero_count > len(frame) * 0.7:  # More than 70% zeros
        near_silence_count += len(occurrences)

print(f'Silence patterns (>90% zeros): {silence_count} frames')
print(f'Near-silence patterns (>70% zeros): {near_silence_count} frames')

# Check timing gaps to identify potential beep boundaries
print('\n=== TIMING ANALYSIS ===')
cursor.execute("""
    SELECT c1.control_mi as c_mi_before, c1.timestamp as time_before,
           c2.control_mi as c_mi_after, c2.timestamp as time_after,
           (julianday(c2.timestamp) - julianday(c1.timestamp)) * 86400 as gap_seconds
    FROM dmr_correlations c1
    JOIN dmr_correlations c2 ON c1.id + 1 = c2.id
    WHERE gap_seconds > 0.5
    ORDER BY gap_seconds DESC
    LIMIT 10
""")

gaps = cursor.fetchall()
print('Significant time gaps (potential call boundaries):')
for gap in gaps:
    print(f'  {gap[4]:.1f}s gap: 0x{gap[0]:08X} -> 0x{gap[2]:08X}')
    
    # Check what was the last frame before the gap
    table_before = f'C_{gap[0]:08X}_S0'
    try:
        cursor.execute(f"SELECT ambe_hex FROM '{table_before}' ORDER BY id DESC LIMIT 3")
        last_frames_before = cursor.fetchall()
        if last_frames_before:
            print(f'    Last frames before gap:')
            for i, frame in enumerate(last_frames_before):
                print(f'      -{i}: {frame[0][:32]}...')
    except:
        pass

# Look for patterns that might be beeps based on characteristics
print('\n=== POTENTIAL BEEP PATTERNS ===')
beep_candidates = []

for c_mi, last_frame in last_frames.items():
    # Check if this C-MI appears before a gap
    cursor.execute("""
        SELECT c1.control_mi, c2.control_mi,
               (julianday(c2.timestamp) - julianday(c1.timestamp)) * 86400 as gap_seconds
        FROM dmr_correlations c1
        JOIN dmr_correlations c2 ON c1.id + 1 = c2.id
        WHERE c1.control_mi = ? AND gap_seconds > 0.5
    """, (int(c_mi, 16),))
    
    gap_after = cursor.fetchone()
    if gap_after:
        beep_candidates.append((c_mi, last_frame, gap_after[2]))

if beep_candidates:
    print(f'Found {len(beep_candidates)} potential beep patterns (last frames before gaps):')
    for c_mi, frame, gap in beep_candidates[:5]:
        print(f'  C-MI 0x{c_mi}: {frame[:32]}... (gap: {gap:.1f}s)')
else:
    print('  No clear beep candidates found')

db.close()