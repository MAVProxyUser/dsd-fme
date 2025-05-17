#!/usr/bin/env python3
import sqlite3
import collections

# Connect to database  
db = sqlite3.connect('dmr_capture_20250517_010359.db')
cursor = db.cursor()

# Get all C_ tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%' AND name != 'dmr_correlations'")
tables = cursor.fetchall()

print(f'Found {len(tables)} C_ tables')

# Collect end patterns
end_patterns = collections.defaultdict(list)
last_frame_patterns = collections.defaultdict(list)

for table in tables:
    table_name = table[0]
    cursor.execute(f"SELECT ambe_hex FROM {table_name} ORDER BY id")
    frames = cursor.fetchall()
    
    if len(frames) > 0:
        # Check the last frame
        last_frame = frames[-1][0]
        last_frame_patterns[last_frame].append(table_name)
        
        # Check the last 2 frames concatenated
        if len(frames) >= 2:
            last_pattern = frames[-2][0] + frames[-1][0]
            end_patterns[last_pattern].append(table_name)

# Report repeated last frames
print('\n=== REPEATED LAST FRAMES ===')
count = 0
for pattern, tables in last_frame_patterns.items():
    if len(tables) > 1:
        count += 1
        print(f'Pattern {count}: {pattern[:32]}...')
        print(f'  Appears as last frame in {len(tables)} tables:')
        for t in tables:
            c_mi = t.split('_')[1]
            print(f'    {t} (C-MI: 0x{c_mi})')

if count == 0:
    print('  No repeated last frames found')

# Check for similar patterns (first 8 bytes)
prefix_groups = collections.defaultdict(list)
for pattern, tables in last_frame_patterns.items():
    prefix = pattern[:16]  # First 8 bytes in hex = 8 bytes
    prefix_groups[prefix].extend([(t, pattern) for t in tables])

print('\n=== SIMILAR LAST FRAMES (same first 8 bytes) ===')
count = 0
for prefix, group in prefix_groups.items():
    if len(group) > 1:
        count += 1
        print(f'\nPrefix {count}: {prefix}')
        for table, full_pattern in group:
            c_mi = table.split('_')[1]
            print(f'  {table} (0x{c_mi}): {full_pattern[:32]}...')

if count == 0:
    print('  No similar patterns found')

# Also check all individual frames
all_frame_patterns = collections.defaultdict(set)
for table in tables:
    table_name = table[0]
    cursor.execute(f"SELECT ambe_hex FROM {table_name}")
    frames = cursor.fetchall()
    for frame in frames:
        all_frame_patterns[frame[0]].add(table_name)

print('\n=== MOST COMMON INDIVIDUAL FRAMES ===')
common_frames = sorted(all_frame_patterns.items(), key=lambda x: len(x[1]), reverse=True)[:10]
for i, (frame, tables_set) in enumerate(common_frames):
    print(f'{i+1}. {frame[:32]}... appears in {len(tables_set)} tables')

# Check for timing gaps that might indicate beeps
print('\n=== TIMING ANALYSIS ===')
cursor.execute("""
    SELECT c1.c_mi, c1.timestamp, c2.c_mi, c2.timestamp,
           (julianday(c2.timestamp) - julianday(c1.timestamp)) * 86400 as gap_seconds
    FROM dmr_correlations c1
    JOIN dmr_correlations c2 ON c1.id + 1 = c2.id
    WHERE gap_seconds > 0.5
    ORDER BY gap_seconds DESC
    LIMIT 10
""")

gaps = cursor.fetchall()
print('Significant time gaps:')
for gap in gaps:
    print(f'  {gap[4]:.1f}s gap between 0x{gap[0]:08X} and 0x{gap[2]:08X}')

db.close()