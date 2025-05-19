#!/usr/bin/env python3
"""Debug MI progression to see where it fails"""

import sqlite3

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

db_file = "dmr_capture_20250518_020534_898339.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get distinct C-MI values in order
cursor.execute('''
    SELECT DISTINCT c_mi 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id
    LIMIT 50
''')

c_mi_values = [row[0] for row in cursor.fetchall()]

print("Checking where C-MI progression diverges from LFSR...")
print("Pos | Current C-MI | Predicted Next | Actual Next | Match")
print("-" * 60)

matches = 0
for i in range(len(c_mi_values) - 1):
    current = c_mi_values[i]
    actual_next = c_mi_values[i + 1]
    predicted_next = dmr_lfsr_next(current)
    
    match = predicted_next == actual_next
    if match:
        matches += 1
    
    status = '✓' if match else '✗'
    print(f"{i:3d} | 0x{current:08X} | 0x{predicted_next:08X} | 0x{actual_next:08X} | {status}")
    
print(f"\nTotal matches: {matches}/{len(c_mi_values)-1}")

# Let's also check if there's a pattern in where it fails
if matches < len(c_mi_values) - 1:
    print("\nChecking if there's a pattern in the failures...")
    
    # Get all C-MI values with timestamps
    cursor.execute('''
        SELECT id, c_mi, start_timestamp 
        FROM superframes 
        WHERE c_mi != 0 
        ORDER BY id
        LIMIT 50
    ''')
    
    rows = cursor.fetchall()
    print("\nID | C-MI | Timestamp")
    print("-" * 40)
    for i, (id_val, c_mi, timestamp) in enumerate(rows[:20]):
        print(f"{id_val:3d} | 0x{c_mi:08X} | {timestamp}")

conn.close()