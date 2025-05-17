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
    try:
        cursor.execute(f"SELECT ambe_hex FROM '{table_name}' ORDER BY id")
        frames = cursor.fetchall()
        
        if len(frames) > 0:
            # Check the last frame
            last_frame = frames[-1][0]
            last_frame_patterns[last_frame].append(table_name)
            
            # Check the last 2 frames concatenated
            if len(frames) >= 2:
                last_pattern = frames[-2][0] + frames[-1][0]
                end_patterns[last_pattern].append(table_name)
    except sqlite3.OperationalError as e:
        print(f"Error with table {table_name}: {e}")

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
    prefix = pattern[:16]  # First 8 bytes in hex = 16 hex chars
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
    try:
        cursor.execute(f"SELECT ambe_hex FROM '{table_name}'")
        frames = cursor.fetchall()
        for frame in frames:
            all_frame_patterns[frame[0]].add(table_name)
    except sqlite3.OperationalError as e:
        print(f"Error with table {table_name}: {e}")

print('\n=== MOST COMMON INDIVIDUAL FRAMES ===')
common_frames = sorted(all_frame_patterns.items(), key=lambda x: len(x[1]), reverse=True)[:10]
for i, (frame, tables_set) in enumerate(common_frames):
    print(f'{i+1}. {frame[:32]}... appears in {len(tables_set)} tables')
    if i < 3:  # Show details for top 3
        print('   Tables:', ', '.join(sorted(list(tables_set))[:5]))

# Check specific beep patterns (common in DMR)
print('\n=== CHECKING COMMON BEEP PATTERNS ===')
# Common DMR beep patterns (these are examples, actual patterns may vary)
beep_patterns = [
    'E99FE996E996E996',  # Common beep start
    '0000000000000000',  # Silence
    'FFFFFFFFFFFFFFFF',  # Full scale
]

for pattern in beep_patterns:
    count = 0
    for frame, tables_set in all_frame_patterns.items():
        if pattern in frame:
            count += len(tables_set)
    print(f'Pattern {pattern}: found in {count} frames')

# Look for patterns that appear at the very end of transmissions
print('\n=== END-OF-TRANSMISSION PATTERNS ===')
# Get the superframe data
cursor.execute("""
    SELECT sf.id, sf.slot, sf.start_time, sf.end_time,
           (julianday(sf.end_time) - julianday(sf.start_time)) * 86400 as duration
    FROM superframes sf
    WHERE sf.end_time IS NOT NULL
    ORDER BY sf.id
""")
superframes = cursor.fetchall()
print(f'Found {len(superframes)} complete superframes')

# Check for patterns that appear right before long gaps
cursor.execute("""
    SELECT c1.c_mi, c1.timestamp, c2.c_mi, c2.timestamp,
           (julianday(c2.timestamp) - julianday(c1.timestamp)) * 86400 as gap_seconds
    FROM dmr_correlations c1
    JOIN dmr_correlations c2 ON c1.id + 1 = c2.id
    WHERE gap_seconds > 1.0
    ORDER BY gap_seconds DESC
    LIMIT 10
""")

gaps = cursor.fetchall()
print('\nSignificant time gaps (potential transmission ends):')
for gap in gaps:
    print(f'  {gap[4]:.1f}s gap after C-MI 0x{gap[0]:08X}')
    # Check what pattern was at the end of this C-MI
    table_name = f'C_{gap[0]:08X}_S0'
    try:
        cursor.execute(f"SELECT ambe_hex FROM '{table_name}' ORDER BY id DESC LIMIT 1")
        last_frame = cursor.fetchone()
        if last_frame:
            print(f'    Last frame: {last_frame[0][:32]}...')
    except:
        pass

db.close()