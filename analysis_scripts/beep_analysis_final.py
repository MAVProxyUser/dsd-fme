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
    
    # Analyze common bytes
    if len(patterns) > 1:
        # Find common prefix
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
    
    # Show the patterns
    for pattern in patterns:
        # Find which C-MI this belongs to
        cursor.execute("""
            SELECT DISTINCT table_name, control_mi 
            FROM (
                SELECT name as table_name
                FROM sqlite_master 
                WHERE type='table' AND name LIKE 'C_%'
            ) t
            JOIN dmr_correlations c ON 
                printf('C_%08X_S0', c.control_mi) = t.table_name
            WHERE EXISTS (
                SELECT 1 FROM """ + "t.table_name" + """ 
                WHERE ambe_hex = ?
            )
        """, (pattern,))
        
        # Manual search since the SQL is complex
        found = False
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%' AND name != 'dmr_correlations'")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM '{table_name}' WHERE ambe_hex = ?", (pattern,))
            count = cursor.fetchone()[0]
            if count > 0:
                c_mi = table_name.split('_')[1]
                print(f'    {pattern[:16]}... (C-MI: 0x{c_mi})')
                found = True
                break
        
        if not found:
            print(f'    {pattern[:16]}... (not found)')
    
    print()

# Let's specifically analyze Group 3 which has the "02" prefix
print('=== DETAILED ANALYSIS OF GROUP 3 (02 PREFIX) ===\n')

group3_cmis = []
for pattern in beep_groups['group3']:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%' AND name != 'dmr_correlations'")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' WHERE ambe_hex = ?", (pattern,))
        result = cursor.fetchone()
        if result:
            c_mi = table_name.split('_')[1]
            group3_cmis.append(c_mi)
            
            # Get surrounding frames for context
            cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' WHERE id >= ? - 2 AND id <= ? + 2 ORDER BY id", 
                          (result[0], result[0]))
            context_frames = cursor.fetchall()
            
            print(f'Pattern in C-MI 0x{c_mi}:')
            for frame_id, frame_hex in context_frames:
                marker = ' <-- BEEP' if frame_hex == pattern else ''
                print(f'  [{frame_id}] {frame_hex[:32]}...{marker}')
            print()

# Check if Group 3 patterns appear in sequence
print('=== CHECKING FOR BEEP SEQUENCES ===\n')

for i, c_mi in enumerate(group3_cmis):
    table_name = f'C_{c_mi}_S0'
    
    # Get all frames from this table
    cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' ORDER BY id")
    frames = cursor.fetchall()
    
    # Find sequences of similar patterns
    sequences = []
    current_seq = []
    
    for frame_id, frame_hex in frames:
        if frame_hex[:2] == '02':  # Matches the group 3 prefix
            current_seq.append((frame_id, frame_hex))
        else:
            if len(current_seq) > 1:
                sequences.append(current_seq)
            current_seq = []
    
    if len(current_seq) > 1:
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

# Correlate with LFSR predictions
print('=== CORRELATION WITH LFSR PREDICTIONS ===\n')

# Get the next predicted C-MI values from the master model
predicted_cmis = [
    0x7C3EB750, 0x62BBF551, 0x3EEEB2CE, 0x4874CD48, 0xF98FC11E,
    0xBD185019, 0x7780450B, 0x0679B283, 0xC8C4CD17, 0x67685F2E
]

print('Next predicted C-MI values:')
for i, pred_cmi in enumerate(predicted_cmis[:5]):
    print(f'  {i+1}. 0x{pred_cmi:08X}')
    
    # Check if we've captured this C-MI already
    cursor.execute("SELECT COUNT(*) FROM dmr_correlations WHERE control_mi = ?", (pred_cmi,))
    count = cursor.fetchone()[0]
    if count > 0:
        print(f'     Already captured!')
    else:
        print(f'     Not yet captured')

db.close()