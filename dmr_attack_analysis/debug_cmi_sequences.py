#!/usr/bin/env python3
"""
Debug C-MI sequences to understand the data
"""

import sqlite3
from glob import glob

# Check actual C-MI sequences
db_file = "dmr_capture_20250517_021613.db"
conn = sqlite3.connect(db_file)

# Get first 20 C-MI values for our H-MI
query = """
SELECT control_mi, timestamp
FROM dmr_correlations  
WHERE header_mi = 1821029943
ORDER BY timestamp
LIMIT 20
"""

results = conn.execute(query).fetchall()

print(f"C-MI sequence from {db_file}:")
print("Index  C-MI (hex)    C-MI (decimal)    Timestamp")

for i, (c_mi, ts) in enumerate(results):
    print(f"{i:5d}  0x{c_mi:08X}  {c_mi:12d}  {ts}")
    
    if i > 0:
        prev_c_mi = results[i-1][0]
        
        # Try simple LFSR calculation
        state = prev_c_mi
        for step in range(1, 6):
            bit = ((state >> 31) ^ (state >> 3) ^ (state >> 1)) & 0x1
            state = ((state << 1) | bit) & 0xFFFFFFFF
            
            if state == c_mi:
                print(f"       Jump: +{step}")
                break
        else:
            # Try calculating the numerical difference
            diff = c_mi - prev_c_mi
            print(f"       Numerical diff: {diff}")

conn.close()

# Also check the master pattern data
import json

with open('dmr_master_pattern.json', 'r') as f:
    pattern_data = json.load(f)

print("\n\nMaster pattern jump distribution:")
jumps = pattern_data['h_mi_patterns']['0x6C8AB637']['jump_distribution']
for jump, count in sorted(jumps.items(), key=lambda x: int(x[0]))[:10]:
    print(f"  Jump {jump:>3s}: {count:4d} times")