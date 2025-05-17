#!/usr/bin/env python3
import sqlite3
import collections
from datetime import datetime

# Connect to database  
db = sqlite3.connect('dmr_capture_20250517_010359.db')
cursor = db.cursor()

# Get all beep candidates (last frames before gaps)
cursor.execute("""
    SELECT c1.control_mi as c_mi_before, c2.control_mi as c_mi_after,
           (julianday(c2.timestamp) - julianday(c1.timestamp)) * 86400 as gap_seconds
    FROM dmr_correlations c1
    JOIN dmr_correlations c2 ON c1.id + 1 = c2.id
    WHERE gap_seconds > 0.5
    ORDER BY gap_seconds DESC
""")

gaps = cursor.fetchall()
print(f'Found {len(gaps)} gaps > 0.5s')

# Collect all the last frames before gaps
last_frames_before_gaps = []

for gap in gaps:
    c_mi_before = gap[0]
    gap_seconds = gap[2]
    
    # Get the last few frames from this C-MI
    table_name = f'C_{c_mi_before:08X}_S0'
    try:
        cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' ORDER BY id DESC LIMIT 5")
        frames = cursor.fetchall()
        
        if frames:
            # Reverse to get chronological order
            frames = frames[::-1]
            last_frames_before_gaps.append({
                'c_mi': c_mi_before,
                'gap_seconds': gap_seconds,
                'frames': frames,
                'table': table_name
            })
    except Exception as e:
        print(f"Error accessing {table_name}: {e}")

# Analyze the patterns
print('\n=== PATTERN ANALYSIS ===')

# Look for exact matches in the last frames
last_frame_patterns = collections.defaultdict(list)
for entry in last_frames_before_gaps:
    if entry['frames']:
        last_frame = entry['frames'][-1][1]  # Get the hex of the last frame
        last_frame_patterns[last_frame].append(entry)

# Report repeated patterns
repeated_patterns = [(pattern, entries) for pattern, entries in last_frame_patterns.items() if len(entries) > 1]

if repeated_patterns:
    print('EXACT REPEATED PATTERNS (last frame before gap):')
    for pattern, entries in repeated_patterns:
        print(f'\nPattern: {pattern[:32]}...')
        print(f'Appears {len(entries)} times:')
        for entry in entries:
            print(f'  C-MI 0x{entry["c_mi"]:08X} (gap: {entry["gap_seconds"]:.1f}s)')
else:
    print('No exact repeated patterns in last frames')

# Look for similar patterns (hamming distance)
def hamming_distance(s1, s2):
    if len(s1) != len(s2):
        return float('inf')
    return sum(c1 != c2 for c1, c2 in zip(s1, s2))

print('\n=== SIMILAR PATTERNS ===')
# Calculate similarity between all last frames
similarity_threshold = 8  # Allow up to 8 bit differences

similar_groups = []
processed = set()

for i, entry1 in enumerate(last_frames_before_gaps):
    if i in processed or not entry1['frames']:
        continue
        
    last_frame1 = entry1['frames'][-1][1]
    group = [entry1]
    processed.add(i)
    
    for j, entry2 in enumerate(last_frames_before_gaps[i+1:], i+1):
        if j in processed or not entry2['frames']:
            continue
            
        last_frame2 = entry2['frames'][-1][1]
        distance = hamming_distance(last_frame1, last_frame2)
        
        if distance <= similarity_threshold:
            group.append(entry2)
            processed.add(j)
    
    if len(group) > 1:
        similar_groups.append(group)

if similar_groups:
    print(f'Found {len(similar_groups)} groups of similar patterns:')
    for i, group in enumerate(similar_groups):
        print(f'\nGroup {i+1} ({len(group)} patterns):')
        for entry in group:
            last_frame = entry['frames'][-1][1]
            print(f'  C-MI 0x{entry["c_mi"]:08X}: {last_frame[:32]}... (gap: {entry["gap_seconds"]:.1f}s)')
else:
    print('No similar patterns found')

# Look for patterns across multiple frames (not just the last one)
print('\n=== MULTI-FRAME PATTERNS ===')

# Check if the last 2-3 frames form a repeated pattern
multi_frame_patterns = collections.defaultdict(list)

for entry in last_frames_before_gaps:
    if len(entry['frames']) >= 2:
        # Get the last 2 frames concatenated
        last_two = entry['frames'][-2][1] + entry['frames'][-1][1]
        multi_frame_patterns[last_two].append(entry)

repeated_multi = [(pattern, entries) for pattern, entries in multi_frame_patterns.items() if len(entries) > 1]

if repeated_multi:
    print('REPEATED MULTI-FRAME PATTERNS (last 2 frames):')
    for pattern, entries in repeated_multi:
        print(f'\nPattern: {pattern[:48]}...')
        print(f'Appears {len(entries)} times:')
        for entry in entries:
            print(f'  C-MI 0x{entry["c_mi"]:08X} (gap: {entry["gap_seconds"]:.1f}s)')
else:
    print('No repeated multi-frame patterns')

# Save detailed results
print('\n=== SAVING RESULTS ===')
with open('beep_candidates.txt', 'w') as f:
    f.write('BEEP CANDIDATES - Last frames before gaps\n')
    f.write('=========================================\n\n')
    
    for entry in last_frames_before_gaps:
        f.write(f'C-MI: 0x{entry["c_mi"]:08X} (gap: {entry["gap_seconds"]:.1f}s)\n')
        f.write(f'Table: {entry["table"]}\n')
        f.write('Last frames:\n')
        for i, (frame_id, frame_hex) in enumerate(entry['frames']):
            f.write(f'  [{frame_id}] {frame_hex}\n')
        f.write('\n')

print('Results saved to beep_candidates.txt')

db.close()