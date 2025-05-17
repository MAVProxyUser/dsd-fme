#!/usr/bin/env python3
"""
Analysis of continuous 3+ minute DMR capture
"""
import sqlite3
import numpy as np
from datetime import datetime
from collections import Counter

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

print("Continuous DMR Capture Analysis")
print("===============================\n")

# Connect to database
conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Get basic statistics
cursor.execute("SELECT COUNT(*) FROM dmr_correlations")
total_correlations = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM superframes")
total_superframes = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(DISTINCT header_mi) FROM dmr_correlations")
unique_h_mi = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(DISTINCT control_mi) FROM dmr_correlations")
unique_c_mi = cursor.fetchone()[0]

print(f"Total correlations: {total_correlations}")
print(f"Total superframes: {total_superframes}")
print(f"Unique H-MI values: {unique_h_mi}")
print(f"Unique C-MI values: {unique_c_mi}")

# Get the H-MI value
cursor.execute("SELECT DISTINCT header_mi FROM dmr_correlations")
h_mi = cursor.fetchone()[0]
print(f"\nH-MI value: 0x{h_mi:08X}")

# Get all correlations in order
cursor.execute("""
    SELECT control_mi, timestamp 
    FROM dmr_correlations 
    WHERE header_mi = ?
    ORDER BY timestamp
""", (h_mi,))
correlations = cursor.fetchall()

# Calculate time span
timestamps = [datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S') for r in correlations]
duration = (timestamps[-1] - timestamps[0]).seconds
print(f"Capture duration: {duration} seconds")
print(f"Average frame rate: {len(correlations)/duration:.1f} frames/second")

# Analyze LFSR progression
c_mi_values = [r[0] for r in correlations]

# Generate LFSR sequence
lfsr_sequence = []
current = h_mi
for _ in range(len(c_mi_values) + 100):
    current = lfsr_next(current)
    lfsr_sequence.append(current)

# Find positions in LFSR sequence
lfsr_lookup = {val: idx for idx, val in enumerate(lfsr_sequence)}
positions = [lfsr_lookup.get(c_mi, -1) for c_mi in c_mi_values]

# Calculate jumps
jumps = []
perfect_count = 0
for i in range(len(positions) - 1):
    if positions[i] != -1 and positions[i+1] != -1:
        jump = positions[i+1] - positions[i]
        jumps.append(jump)
        if jump == 1:
            perfect_count += 1

# Jump statistics
jump_counter = Counter(jumps)
total_jumps = len(jumps)

print(f"\nLFSR Jump Analysis:")
print(f"Total valid jumps: {total_jumps}")
print(f"Perfect progressions (jump=1): {perfect_count} ({perfect_count/total_jumps*100:.2f}%)")
print(f"\nJump distribution:")
for jump, count in jump_counter.most_common():
    print(f"  Jump {jump:3d}: {count:4d} times ({count/total_jumps*100:5.2f}%)")

# Find longest continuous sequence
longest_run = 0
current_run = 0
for jump in jumps:
    if jump == 1:
        current_run += 1
        longest_run = max(longest_run, current_run)
    else:
        current_run = 0

print(f"\nLongest continuous LFSR sequence: {longest_run} frames")

# Test prediction accuracy
print(f"\nPrediction Test:")
test_size = min(100, len(c_mi_values) - 1)
correct_predictions = 0

for i in range(test_size):
    current_val = c_mi_values[i]
    actual_next = c_mi_values[i + 1]
    predicted_next = lfsr_next(current_val)
    
    if predicted_next == actual_next:
        correct_predictions += 1

print(f"Direct prediction accuracy: {correct_predictions}/{test_size} ({correct_predictions/test_size*100:.1f}%)")

# Analyze any anomalies
anomalies = []
for i, jump in enumerate(jumps):
    if jump != 1:
        anomalies.append((i, jump))

print(f"\nAnomalies (non-1 jumps): {len(anomalies)}")
if anomalies:
    print("First 10 anomalies:")
    for idx, (pos, jump) in enumerate(anomalies[:10]):
        print(f"  Position {pos}: jump={jump}")

# Final assessment
print(f"\n=== CRYPTANALYSIS ASSESSMENT ===")
print(f"Total frames captured: {len(c_mi_values)}")
print(f"LFSR predictability: {perfect_count/total_jumps*100:.2f}%")
print(f"Frames needed for attack: ~{int(1000 * (total_jumps/perfect_count))} (accounting for anomalies)")

if perfect_count/total_jumps > 0.95:
    print("\nVULNERABILITY: CRITICAL")
    print("The LFSR is highly predictable. An attacker can:")
    print("1. Predict future IVs with high accuracy")
    print("2. Reduce RC4 keyspace significantly")
    print("3. Potentially recover plaintext with sufficient data")
else:
    print("\nVULNERABILITY: MODERATE")
    print("Some unpredictability exists, but the fixed H-MI still poses risk")

conn.close()