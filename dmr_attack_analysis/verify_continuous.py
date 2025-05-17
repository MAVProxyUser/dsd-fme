#!/usr/bin/env python3
"""
Verify the continuous capture LFSR progression
"""
import sqlite3

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

print("Verifying LFSR Progression in Continuous Capture")
print("==============================================\n")

# Connect to database
conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Get ALL C-MI values in order
cursor.execute("""
    SELECT control_mi, timestamp 
    FROM dmr_correlations 
    WHERE header_mi = 1821029943
    ORDER BY timestamp
""")
all_records = cursor.fetchall()
conn.close()

print(f"Total C-MI values: {len(all_records)}")

# Extract just the C-MI values
c_mi_values = [r[0] for r in all_records]

# Check if each value follows LFSR from previous
print("\nChecking LFSR progression:")
print("Index | Current C-MI   | Next C-MI      | LFSR Predicted | Match")
print("------|----------------|----------------|----------------|------")

correct = 0
total = len(c_mi_values) - 1

for i in range(min(20, total)):  # Show first 20
    current = c_mi_values[i]
    actual_next = c_mi_values[i + 1]
    predicted_next = lfsr_next(current)
    
    match = "YES" if predicted_next == actual_next else "NO"
    if predicted_next == actual_next:
        correct += 1
    
    print(f"{i:5} | 0x{current:08X} | 0x{actual_next:08X} | 0x{predicted_next:08X} | {match}")

# Check all values
all_correct = 0
for i in range(total):
    current = c_mi_values[i]
    actual_next = c_mi_values[i + 1]
    predicted_next = lfsr_next(current)
    
    if predicted_next == actual_next:
        all_correct += 1

print(f"\n...")
print(f"Total checked: {total}")
print(f"Correct predictions: {all_correct}")
print(f"Accuracy: {all_correct/total*100:.2f}%")

# Now check if values appear in sequence
print("\nChecking if values follow LFSR sequence from H-MI:")
h_mi = 0x6C8AB637
current = h_mi

# Generate enough LFSR values
lfsr_sequence = []
for _ in range(2000):
    current = lfsr_next(current)
    lfsr_sequence.append(current)

# Find where our C-MI values appear
print("\nFirst 10 C-MI positions in LFSR sequence:")
for i in range(min(10, len(c_mi_values))):
    c_mi = c_mi_values[i]
    try:
        pos = lfsr_sequence.index(c_mi)
        print(f"C-MI[{i}] = 0x{c_mi:08X} found at LFSR position {pos}")
    except ValueError:
        print(f"C-MI[{i}] = 0x{c_mi:08X} NOT FOUND")

# Check gaps between positions
positions = []
for c_mi in c_mi_values:
    try:
        pos = lfsr_sequence.index(c_mi)
        positions.append(pos)
    except ValueError:
        positions.append(-1)

# Calculate jumps
jumps = []
for i in range(len(positions) - 1):
    if positions[i] != -1 and positions[i+1] != -1:
        jump = positions[i+1] - positions[i]
        jumps.append(jump)

from collections import Counter
jump_counts = Counter(jumps)

print(f"\nJump distribution:")
for jump, count in jump_counts.most_common():
    print(f"  Jump {jump}: {count} times ({count/len(jumps)*100:.2f}%)")