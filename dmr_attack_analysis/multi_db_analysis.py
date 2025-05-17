#!/usr/bin/env python3
"""
Analysis script that works with multiple timestamped databases
"""
import sqlite3
import glob
import os
from datetime import datetime
from collections import defaultdict
import numpy as np

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

print("Multi-Database DMR Analysis")
print("===========================\n")

# Find all DMR capture databases
db_files = glob.glob("dmr_capture_*.db")
db_files.extend(glob.glob("dsd_fme.db"))  # Include current capture

if not db_files:
    print("No capture databases found!")
    exit(1)

print(f"Found {len(db_files)} database(s):")
for db in sorted(db_files):
    size = os.path.getsize(db) / 1024 / 1024  # MB
    print(f"  {db} ({size:.1f} MB)")

# Combine data from all databases
all_correlations = []
all_ambe_frames = defaultdict(list)

for db_file in sorted(db_files):
    print(f"\nProcessing {db_file}...")
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get correlations
    cursor.execute("""
        SELECT header_mi, control_mi, timestamp, slot, algid 
        FROM dmr_correlations 
        ORDER BY timestamp
    """)
    correlations = cursor.fetchall()
    all_correlations.extend(correlations)
    print(f"  Found {len(correlations)} correlations")
    
    # Get AMBE frames from all tables
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')
    """)
    tables = cursor.fetchall()
    
    for table_name in tables:
        table = table_name[0]
        cursor.execute(f"SELECT * FROM {table}")
        frames = cursor.fetchall()
        all_ambe_frames[table].extend(frames)
    
    conn.close()

print(f"\nCombined totals:")
print(f"  Correlations: {len(all_correlations)}")
print(f"  AMBE tables: {len(all_ambe_frames)}")
total_ambe = sum(len(frames) for frames in all_ambe_frames.values())
print(f"  AMBE frames: {total_ambe}")

# Group by H-MI for analysis
h_mi_groups = defaultdict(list)
for h_mi, c_mi, timestamp, slot, algid in all_correlations:
    h_mi_groups[h_mi].append((c_mi, timestamp, slot, algid))

# Analyze each H-MI (radio)
for h_mi, records in h_mi_groups.items():
    print(f"\n=== H-MI: 0x{h_mi:08X} ===")
    print(f"Records: {len(records)}")
    
    # Sort by timestamp
    records.sort(key=lambda x: x[1])
    
    # Extract C-MI sequence
    c_mi_values = [r[0] for r in records]
    
    # Generate LFSR sequence
    lfsr_sequence = []
    current = h_mi
    for _ in range(5000):  # Generate plenty
        current = lfsr_next(current)
        lfsr_sequence.append(current)
    
    # Create position lookup
    lfsr_lookup = {val: idx for idx, val in enumerate(lfsr_sequence)}
    
    # Build complete pattern model
    positions = []
    for c_mi in c_mi_values:
        if c_mi in lfsr_lookup:
            positions.append(lfsr_lookup[c_mi])
    
    # Calculate jumps
    jumps = []
    for i in range(len(positions) - 1):
        jump = positions[i+1] - positions[i]
        jumps.append(jump)
    
    # Analyze pattern
    from collections import Counter
    jump_counter = Counter(jumps)
    
    print(f"\nJump distribution:")
    for jump, count in jump_counter.most_common(10):
        print(f"  Jump {jump:3d}: {count:4d} times ({count/len(jumps)*100:5.1f}%)")
    
    # Find radio ID if available
    radio_ids = set()
    for _, _, slot, _ in records:
        # In real implementation, extract radio ID from frames
        radio_ids.add(slot)  # Placeholder
    
    print(f"Slots/Radio IDs seen: {radio_ids}")

# Pattern learning
print("\n=== PATTERN LEARNING ===")
all_jumps = []
for h_mi, records in h_mi_groups.items():
    records.sort(key=lambda x: x[1])
    c_mi_values = [r[0] for r in records]
    
    # Convert to positions
    positions = []
    for c_mi in c_mi_values:
        if c_mi in lfsr_lookup:
            positions.append(lfsr_lookup[c_mi])
    
    # Calculate jumps
    for i in range(len(positions) - 1):
        jump = positions[i+1] - positions[i]
        all_jumps.append(jump)

# Build pattern model
jump_sequence = []
for i in range(0, len(all_jumps) - 20, 20):  # Sample every 20 jumps
    pattern = all_jumps[i:i+20]
    jump_sequence.append(pattern)

print(f"Collected {len(jump_sequence)} pattern samples")

# Save pattern model
import json
pattern_model = {
    'jump_distribution': dict(Counter(all_jumps).most_common()),
    'pattern_samples': jump_sequence,
    'total_frames': len(all_correlations)
}

with open('dmr_pattern_model.json', 'w') as f:
    json.dump(pattern_model, f, indent=2)

print("Pattern model saved to: dmr_pattern_model.json")