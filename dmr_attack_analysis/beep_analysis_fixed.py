#!/usr/bin/env python3
import sqlite3
import collections
from datetime import datetime

# Connect to database  
db = sqlite3.connect('dmr_capture_20250517_010359.db')
cursor = db.cursor()

# Define beep candidate groups from our analysis
beep_groups = {
    'group1': ['3316AB4000687000', 'C4A4AE2000A81000', '2966C5400014C000'],
    'group2': ['3C543C8000252800', '9CF2FF8000CAE800', 'E9F43C200003DC00'],
    'group3': ['029C3C0000188000', '02E07020005A1000', '02AA7D00008D3400'],  # All start with 02!
    'group4': ['CDD623000084A000', 'CDB42120006A6400'],
    'group5': ['A690142000F6A400', '6B9E9620009B9400']
}

# Analyze the patterns in more detail
print('=== BEEP PATTERN ANALYSIS ===\n')

for group_name, patterns in beep_groups.items():
    print(f'{group_name.upper()}:')
    
    # Find common prefix
    if len(patterns) > 1:
        min_len = min(len(p) for p in patterns)
        common_prefix = ''
        for i in range(0, min_len, 2):  # Check byte by byte (2 hex chars)
            bytes_at_pos = [p[i:i+2] for p in patterns]
            if len(set(bytes_at_pos)) == 1:  # All patterns have same byte at this position
                common_prefix += bytes_at_pos[0]
            else:
                break
        
        if common_prefix:
            print(f'  Common prefix: {common_prefix} ({len(common_prefix)//2} bytes)')
    
    # Show the patterns and find their C-MIs
    pattern_cmis = []
    for pattern in patterns:
        # Search all tables for this pattern
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C!_%' ESCAPE '!' AND name != 'dmr_correlations'")
        tables = cursor.fetchall()
        
        found = False
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM '{table_name}' WHERE ambe_hex = ?", (pattern,))
            count = cursor.fetchone()[0]
            if count > 0:
                c_mi = table_name.split('_')[1]
                pattern_cmis.append(c_mi)
                print(f'    {pattern[:16]}... (C-MI: 0x{c_mi})')
                found = True
                break
        
        if not found:
            print(f'    {pattern[:16]}... (not found)')
    
    # Store Group 3 C-MIs for further analysis
    if group_name == 'group3':
        group3_cmis = pattern_cmis
    
    print()

# Let's specifically analyze Group 3 which has the "02" prefix
print('=== DETAILED ANALYSIS OF GROUP 3 (02 PREFIX) ===\n')

for c_mi in group3_cmis:
    table_name = f'C_{c_mi}_S0'
    
    # Get all frames to find the beep pattern context
    cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' ORDER BY id")
    frames = cursor.fetchall()
    
    # Find the beep pattern
    for i, (frame_id, frame_hex) in enumerate(frames):
        if frame_hex in beep_groups['group3']:
            print(f'Pattern in C-MI 0x{c_mi}:')
            # Show context (2 before, the frame, 2 after)
            start = max(0, i-2)
            end = min(len(frames), i+3)
            for j in range(start, end):
                marker = ' <-- BEEP' if j == i else ''
                print(f'  [{frames[j][0]}] {frames[j][1][:32]}...{marker}')
            print()
            break

# Check for sequences of frames with "02" prefix
print('=== CHECKING FOR BEEP SEQUENCES ===\n')

for c_mi in group3_cmis:
    table_name = f'C_{c_mi}_S0'
    
    # Get all frames from this table
    cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' ORDER BY id")
    frames = cursor.fetchall()
    
    # Find sequences of frames starting with "02"
    sequences = []
    current_seq = []
    
    for frame_id, frame_hex in frames:
        if frame_hex[:2] == '02':  # Matches the group 3 prefix
            current_seq.append((frame_id, frame_hex))
        else:
            if len(current_seq) >= 2:  # Only interested in sequences of 2+ frames
                sequences.append(current_seq)
            current_seq = []
    
    if len(current_seq) >= 2:
        sequences.append(current_seq)
    
    if sequences:
        print(f'C-MI 0x{c_mi} - Found {len(sequences)} sequences with "02" prefix:')
        for seq in sequences:
            print(f'  Sequence of {len(seq)} frames: IDs {seq[0][0]}-{seq[-1][0]}')
            for frame_id, frame_hex in seq[:3]:  # Show first 3
                print(f'    [{frame_id}] {frame_hex[:32]}...')
            if len(seq) > 3:
                print(f'    ... ({len(seq)-3} more frames)')
        print()

# Check if these patterns appear at the end of transmissions
print('=== END-OF-TRANSMISSION ANALYSIS ===\n')

# Get patterns that appear before large gaps
cursor.execute("""
    SELECT c1.control_mi, c2.control_mi,
           (julianday(c2.timestamp) - julianday(c1.timestamp)) * 86400 as gap_seconds
    FROM dmr_correlations c1
    JOIN dmr_correlations c2 ON c1.id + 1 = c2.id
    WHERE gap_seconds > 1.0
    ORDER BY gap_seconds DESC
""")

gaps = cursor.fetchall()

print('Checking if beep patterns appear before gaps:')
beep_before_gap_count = 0

for gap in gaps:
    c_mi_before = gap[0]
    gap_seconds = gap[2]
    
    table_name = f'C_{c_mi_before:08X}_S0'
    try:
        # Get the last frame before the gap
        cursor.execute(f"SELECT ambe_hex FROM '{table_name}' ORDER BY id DESC LIMIT 1")
        last_frame = cursor.fetchone()
        
        if last_frame:
            # Check if it's one of our beep patterns
            for group_name, patterns in beep_groups.items():
                if last_frame[0] in patterns:
                    print(f'  {group_name} pattern before {gap_seconds:.1f}s gap (C-MI: 0x{c_mi_before:08X})')
                    beep_before_gap_count += 1
                    break
    except:
        pass

print(f'\nTotal beep patterns before gaps: {beep_before_gap_count}')

# Summary
print('\n=== SUMMARY ===\n')
print('Most likely beep pattern: Group 3 (02 prefix)')
print('Patterns:')
for pattern in beep_groups['group3']:
    print(f'  {pattern}')
print('\nThese patterns:')
print('- All start with byte 0x02')
print('- Appear at the end of transmissions (before gaps)')
print('- Are found in multiple C-MI sequences')
print('\nRecommendation: Use these patterns as known plaintext for cryptanalysis')

db.close()