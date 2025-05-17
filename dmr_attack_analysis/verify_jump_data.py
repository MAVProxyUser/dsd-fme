#!/usr/bin/env python3
"""
Verify jump patterns in the actual data
"""

import sqlite3
import json
from glob import glob

# Load the master pattern to see actual jumps
with open('dmr_master_pattern.json', 'r') as f:
    pattern_data = json.load(f)

print("Jump distribution from master analysis:")
jump_dist = pattern_data['h_mi_patterns']['0x6C8AB637']['jump_distribution']
for jump, count in sorted(jump_dist.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  Jump {jump:>3s}: {count:4d} occurrences")

# Let's check a sample database to see actual C-MI progressions
db_file = "dmr_capture_20250517_021613.db"
conn = sqlite3.connect(db_file)

# Get some actual C-MI sequences
query = """
SELECT header_mi, control_mi, timestamp
FROM dmr_correlations
WHERE header_mi = 1819898423  -- 0x6C8AB637
ORDER BY timestamp
LIMIT 20
"""

results = conn.execute(query).fetchall()

print(f"\nActual C-MI progression from {db_file}:")
print("H-MI        C-MI        Timestamp")
for i, row in enumerate(results):
    h_mi, c_mi, ts = row
    print(f"0x{h_mi:08X}  0x{c_mi:08X}  {ts}")
    
    if i > 0:
        # Calculate the jump from previous
        prev_c_mi = results[i-1][1]
        # This would be the actual LFSR calculation
        print(f"            Jump from 0x{prev_c_mi:08X} to 0x{c_mi:08X}")

conn.close()

# Now let's analyze calls with time gaps
print("\n=== ANALYZING CALL SESSIONS ===")

db_files = sorted(glob("dmr_capture_*.db"))

for db_file in db_files[:2]:  # Just check first two
    print(f"\n{db_file}:")
    conn = sqlite3.connect(db_file)
    
    # Get correlations with time gaps
    query = """
    SELECT header_mi, control_mi, timestamp,
           CAST((julianday(timestamp) - 
                 julianday(LAG(timestamp) OVER (PARTITION BY header_mi ORDER BY timestamp))) * 86400 
                AS INTEGER) as gap_seconds
    FROM dmr_correlations
    WHERE header_mi = 1819898423
    ORDER BY timestamp
    LIMIT 30
    """
    
    results = conn.execute(query).fetchall()
    
    current_call = []
    call_num = 1
    
    for row in results:
        h_mi, c_mi, ts, gap = row
        
        if gap is None:
            gap = 0
            
        if gap > 5:  # New call
            if current_call:
                print(f"  Call {call_num}: {len(current_call)} frames, "
                      f"C-MI range: 0x{current_call[0]:08X} to 0x{current_call[-1]:08X}")
                call_num += 1
            current_call = [c_mi]
        else:
            current_call.append(c_mi)
    
    if current_call:
        print(f"  Call {call_num}: {len(current_call)} frames, "
              f"C-MI range: 0x{current_call[0]:08X} to 0x{current_call[-1]:08X}")
    
    conn.close()