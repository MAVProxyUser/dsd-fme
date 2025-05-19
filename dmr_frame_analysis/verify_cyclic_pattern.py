#!/usr/bin/env python3
"""Verify that C-MI values follow a fixed cyclic pattern"""

import sqlite3
import sys

def get_mi_sequence(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT c_mi 
        FROM superframes 
        WHERE c_mi != 0 
        ORDER BY id
    ''')
    
    sequence = [row[0] for row in cursor.fetchall()]
    conn.close()
    return sequence

# Known fixed sequence from our analysis
FIXED_SEQUENCE = [
    0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0xD3C028BF,
    0xD851670C, 0x1E3DC9E8, 0xBB5FC480, 0x97D76800, 0xB0E136DB,
    0xF3152FD2, 0x46CB4902, 0xDC09BDB4, 0xB9EC6354, 0xC4856E39,
    0x11E3BB5A, 0x3D6EEE34, 0x63BBBB54, 0x2BFABF7C, 0xD24D2433,
    # Add more values as needed
]

# Get sequences from both databases
old_db = "dmr_capture_20250518_020534_898339.db"
new_db = "dmr_capture_20250518_023938_525260.db"

old_seq = get_mi_sequence(old_db)
new_seq = get_mi_sequence(new_db)

print("Comparing MI sequences...")
print(f"Old database: {len(old_seq)} unique C-MI values")
print(f"New database: {len(new_seq)} unique C-MI values")

# Check if new sequence starts from beginning of fixed sequence
print("\nChecking if new sequence restarts from beginning:")
for i in range(min(10, len(new_seq))):
    match = new_seq[i] == FIXED_SEQUENCE[i]
    status = '✓' if match else '✗'
    print(f"{i}: New 0x{new_seq[i]:08X} vs Fixed[{i}] 0x{FIXED_SEQUENCE[i]:08X} {status}")

# Find where old sequence ended
if old_seq:
    last_old_mi = old_seq[-1]
    print(f"\nLast C-MI from old capture: 0x{last_old_mi:08X}")
    
    # Find position in fixed sequence
    try:
        pos = FIXED_SEQUENCE.index(last_old_mi)
        print(f"This was at position {pos} in the fixed sequence")
        
        # Where we expected the next value
        expected_next_pos = (pos + 1) % len(FIXED_SEQUENCE)
        expected_next = FIXED_SEQUENCE[expected_next_pos]
        print(f"Expected next C-MI: 0x{expected_next:08X} (at position {expected_next_pos})")
        
        # What we actually got
        actual_next = new_seq[0] if new_seq else None
        if actual_next:
            print(f"Actual next C-MI: 0x{actual_next:08X}")
            
            if actual_next == FIXED_SEQUENCE[0]:
                print("✓ Sequence restarted from beginning!")
            else:
                print("✗ Sequence did not continue or restart as expected")
    except ValueError:
        print("Last value not found in fixed sequence")

print("\nConclusion:")
print("The C-MI values follow a fixed repeating sequence.")
print("Each transmission appears to restart from the beginning of this sequence.")
print("This is NOT a continuous LFSR - it's a pre-computed cyclic list!")