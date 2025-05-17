#!/usr/bin/env python3
"""
Analyze LFSR patterns within individual transmission bursts
"""
import datetime

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    # Iterate 32 times as per the C implementation
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

# Get C- MI values with timestamps to identify bursts
import sqlite3
conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Get all C- MI values with timestamps
query = """
SELECT control_mi, timestamp 
FROM dmr_correlations 
WHERE header_mi = 1821029943 
ORDER BY timestamp
"""
cursor.execute(query)
results = cursor.fetchall()
conn.close()

print(f"Total correlations: {len(results)}")

# Group into bursts based on time gaps
bursts = []
current_burst = []
last_time = None

for mi, timestamp in results:
    current_time = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    
    if last_time and (current_time - last_time).seconds > 5:  # 5 second gap = new burst
        if current_burst:
            bursts.append(current_burst)
        current_burst = [(mi, timestamp)]
    else:
        current_burst.append((mi, timestamp))
    
    last_time = current_time

if current_burst:
    bursts.append(current_burst)

print(f"Found {len(bursts)} transmission bursts")
print()

# Analyze each burst
h_mi = 0x6C8AB637
raw_sequence = []
current = h_mi
for _ in range(200):
    current = lfsr_next(current)
    raw_sequence.append(current)

# The pattern we discovered
JUMP_PATTERN = [1,1,1,3,-2,1,3,1,-2,4,-1,2,3,-2,1,4,-2,1,4]

for burst_num, burst in enumerate(bursts[:5]):  # Analyze first 5 bursts
    print(f"Burst {burst_num + 1}: {len(burst)} frames")
    print(f"Time: {burst[0][1]} to {burst[-1][1]}")
    print()
    
    # Check if the burst follows our pattern
    print("Position | C- MI          | Raw Pos | Jump | Pattern Match")
    print("---------|----------------|---------|------|-------------")
    
    matches = 0
    for i in range(min(10, len(burst))):  # Check first 10 values
        mi_value = burst[i][0]
        
        # Find in raw sequence
        try:
            raw_pos = raw_sequence.index(mi_value)
            
            if i == 0:
                print(f"{i:8d} | 0x{mi_value:08X} | {raw_pos:7d} |    - | (start)")
                start_pos = raw_pos
            else:
                prev_mi = burst[i-1][0]
                prev_pos = raw_sequence.index(prev_mi)
                actual_jump = raw_pos - prev_pos
                
                # Expected jump from pattern
                pattern_idx = (i-1) % len(JUMP_PATTERN)
                expected_jump = JUMP_PATTERN[pattern_idx]
                
                match = "YES" if actual_jump == expected_jump else "NO"
                if actual_jump == expected_jump:
                    matches += 1
                
                print(f"{i:8d} | 0x{mi_value:08X} | {raw_pos:7d} | {actual_jump:4d} | {match} (exp: {expected_jump})")
                
        except ValueError:
            print(f"{i:8d} | 0x{mi_value:08X} | NOT FOUND")
    
    accuracy = (matches / (min(10, len(burst)) - 1)) * 100 if len(burst) > 1 else 0
    print(f"\nPattern accuracy: {matches}/{min(10, len(burst)) - 1} = {accuracy:.1f}%")
    print("-" * 60)
    print()

# Check if bursts always start at specific pattern positions
print("Burst starting positions in raw sequence:")
for burst_num, burst in enumerate(bursts[:8]):
    mi_value = burst[0][0]
    try:
        raw_pos = raw_sequence.index(mi_value)
        print(f"Burst {burst_num + 1}: Raw position {raw_pos} (0x{mi_value:08X})")
    except ValueError:
        print(f"Burst {burst_num + 1}: Not found (0x{mi_value:08X})")