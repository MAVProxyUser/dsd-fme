#!/usr/bin/env python3
"""Find exactly where MI progression fails"""

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

# Get ALL distinct C-MI values in order
cursor.execute('''
    SELECT DISTINCT c_mi 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id
''')

c_mi_values = [row[0] for row in cursor.fetchall()]
print(f"Total unique C-MI values: {len(c_mi_values)}")

# Check all transitions
matches = 0
first_failure_pos = None

for i in range(len(c_mi_values) - 1):
    current = c_mi_values[i]
    actual_next = c_mi_values[i + 1]
    predicted_next = dmr_lfsr_next(current)
    
    if predicted_next == actual_next:
        matches += 1
    else:
        if first_failure_pos is None:
            first_failure_pos = i
            print(f"\nFirst failure at position {i}:")
            print(f"Current: 0x{current:08X}")
            print(f"Predicted next: 0x{predicted_next:08X}")
            print(f"Actual next: 0x{actual_next:08X}")
            
            # Check if we can find the actual value in LFSR sequence
            test = current
            steps_found = None
            for step in range(1000):
                test = dmr_lfsr_next(test)
                if test == actual_next:
                    steps_found = step + 1
                    break
            
            if steps_found:
                print(f"Actual value found {steps_found} LFSR steps from current")
            else:
                print("Actual value NOT found in next 1000 LFSR steps")
            
            # Look at surrounding values
            print("\nSurrounding values:")
            for j in range(max(0, i-2), min(len(c_mi_values), i+3)):
                print(f"  {j}: 0x{c_mi_values[j]:08X}")

print(f"\nTotal matches: {matches}/{len(c_mi_values)-1} = {(matches/(len(c_mi_values)-1)*100):.1f}%")

if first_failure_pos is None:
    print("✓ Perfect LFSR progression for all values!")
else:
    # Check if there are any patterns - maybe it restarts?
    print(f"\nFailure occurs after {first_failure_pos} successful predictions")
    
    # Check if the sequence restarts
    if c_mi_values[first_failure_pos + 1] == c_mi_values[0]:
        print("✓ Sequence appears to restart from beginning")
    else:
        print("✗ Sequence does not restart from beginning")

conn.close()