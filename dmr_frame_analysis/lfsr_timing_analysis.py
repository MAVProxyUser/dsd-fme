#!/usr/bin/env python3
import sqlite3
import sys
from datetime import datetime

def lfsr32(state, steps):
    """LFSR with polynomial x^32 + x^4 + x^2 + 1"""
    # Polynomial: x^32 + x^4 + x^2 + 1 = 0x15 (positions 4, 2, 0)
    for i in range(steps):
        feedback = ((state >> 31) ^ (state >> 3) ^ (state >> 1) ^ state) & 1
        state = ((state << 1) | feedback) & 0xFFFFFFFF
    return state

db_file = sys.argv[1]
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get H-MI and C-MI values ordered by timestamp
cursor.execute('''
    SELECT id, h_mi, c_mi, start_timestamp 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id
''')

rows = list(cursor.fetchall())
print(f"Found {len(rows)} non-zero C-MI values")

# Fixed H-MI from Motorola
fixed_h_mi = 0x6C8AB637

# Analyze progression
print("\nC-MI Progression Analysis:")
print("ID  C-MI        Time                      Steps from H-MI?")
print("=" * 60)

for i, row in enumerate(rows[:20]):  # First 20 entries
    id_val, h_mi, c_mi, timestamp = row
    
    # Try to find how many LFSR steps from H-MI to this C-MI
    test_state = fixed_h_mi
    steps_found = None
    
    # Test up to 10000 steps
    for steps in range(10000):
        if test_state == c_mi:
            steps_found = steps
            break
        test_state = lfsr32(test_state, 1)
    
    print(f"{id_val:3d} 0x{c_mi:08X} {timestamp} {steps_found if steps_found else 'Not found'}")
    
    if i > 0:
        # Calculate time difference
        prev_row = rows[i-1]
        prev_time = datetime.fromisoformat(prev_row[3])
        curr_time = datetime.fromisoformat(timestamp)
        time_diff = (curr_time - prev_time).total_seconds()
        
        # Calculate LFSR steps between C-MI values
        prev_c_mi = prev_row[2]
        test_state = prev_c_mi
        steps_between = None
        
        for steps in range(1000):
            test_state = lfsr32(test_state, 1)
            if test_state == c_mi:
                steps_between = steps + 1
                break
        
        print(f"    -> Time diff: {time_diff:.3f}s, LFSR steps: {steps_between if steps_between else 'Not found'}")

conn.close()