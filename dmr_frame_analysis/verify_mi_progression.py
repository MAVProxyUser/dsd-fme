#!/usr/bin/env python3

import sqlite3
import glob
from datetime import datetime

# LFSR parameters
LFSR_POLYNOMIAL = 0x10000015  # x^32 + x^4 + x^2 + 1
H_MI_FIXED = 0x6C8AB637

def lfsr_step(state):
    """Single step of the LFSR"""
    feedback = ((state >> 31) ^ (state >> 3) ^ (state >> 1) ^ state) & 1
    return ((state >> 1) | (feedback << 31)) & 0xFFFFFFFF

def lfsr_steps(state, n):
    """Multiple LFSR steps"""
    for _ in range(n):
        state = lfsr_step(state)
    return state

# Get the encrypted database (Radio 1234)
databases = sorted(glob.glob("dmr_capture_*.db"))
encrypted_db = databases[-1]  # The one with microseconds

print(f"Analyzing MI progression in: {encrypted_db}")

db = sqlite3.connect(encrypted_db)
cursor = db.cursor()

# Get all MI values in order
cursor.execute("""
    SELECT DISTINCT h_mi, c_mi, start_timestamp
    FROM superframes
    WHERE h_mi IS NOT NULL OR c_mi IS NOT NULL
    ORDER BY start_timestamp
""")

mi_sequence = []
for row in cursor.fetchall():
    h_mi, c_mi, timestamp = row
    if h_mi:
        mi_sequence.append(('H', h_mi, timestamp))
    if c_mi:
        mi_sequence.append(('C', c_mi, timestamp))

print(f"\nFound {len(mi_sequence)} MI values")

# Check H-MI to C-MI progression
print("\n=== H-MI to C-MI Progression ===")

h_to_c_transitions = []
for i in range(len(mi_sequence) - 1):
    if mi_sequence[i][0] == 'H' and mi_sequence[i+1][0] == 'C':
        h_mi = mi_sequence[i][1]
        c_mi = mi_sequence[i+1][1]
        h_to_c_transitions.append((h_mi, c_mi))

print(f"\nFound {len(h_to_c_transitions)} H->C transitions")

if h_to_c_transitions:
    print("\nChecking if C-MI can be predicted from H-MI:")
    
    correct_predictions = 0
    for i, (h_mi, actual_c_mi) in enumerate(h_to_c_transitions[:10]):
        # Predict C-MI: step LFSR once from H-MI
        predicted_c_mi = lfsr_step(h_mi)
        
        match = predicted_c_mi == actual_c_mi
        if match:
            correct_predictions += 1
        
        print(f"\nTransition {i}:")
        print(f"  H-MI:          {h_mi:08X}")
        print(f"  Actual C-MI:   {actual_c_mi:08X}")
        print(f"  Predicted:     {predicted_c_mi:08X}")
        print(f"  Match:         {match}")
    
    print(f"\nPrediction accuracy: {correct_predictions}/{min(10, len(h_to_c_transitions))}")

# Check C-MI to C-MI progression
print("\n=== C-MI to C-MI Progression ===")

c_to_c_transitions = []
for i in range(len(mi_sequence) - 1):
    if mi_sequence[i][0] == 'C' and mi_sequence[i+1][0] == 'C':
        c_mi1 = mi_sequence[i][1]
        c_mi2 = mi_sequence[i+1][1]
        c_to_c_transitions.append((c_mi1, c_mi2))

print(f"\nFound {len(c_to_c_transitions)} C->C transitions")

if c_to_c_transitions:
    print("\nChecking if next C-MI can be predicted from current C-MI:")
    
    correct_predictions = 0
    for i, (c_mi1, actual_c_mi2) in enumerate(c_to_c_transitions[:10]):
        # Predict next C-MI: step LFSR once
        predicted_c_mi2 = lfsr_step(c_mi1)
        
        match = predicted_c_mi2 == actual_c_mi2
        if match:
            correct_predictions += 1
        
        print(f"\nTransition {i}:")
        print(f"  Current C-MI:  {c_mi1:08X}")
        print(f"  Actual next:   {actual_c_mi2:08X}")
        print(f"  Predicted:     {predicted_c_mi2:08X}")
        print(f"  Match:         {match}")
    
    print(f"\nPrediction accuracy: {correct_predictions}/{min(10, len(c_to_c_transitions))}")

# Verify the fixed H-MI value
print("\n=== Fixed H-MI Verification ===")

cursor.execute("SELECT COUNT(*) FROM superframes WHERE h_mi = ?", (H_MI_FIXED,))
h_mi_count = cursor.fetchone()[0]

print(f"\nFixed H-MI {H_MI_FIXED:08X} appears {h_mi_count} times")

# Track the full sequence from fixed H-MI
if h_mi_count > 0:
    print("\nTracing LFSR sequence from fixed H-MI:")
    
    # Generate expected sequence
    state = H_MI_FIXED
    expected_sequence = [state]
    for _ in range(10):
        state = lfsr_step(state)
        expected_sequence.append(state)
    
    print(f"Expected: {[f'{x:08X}' for x in expected_sequence[:5]]}")
    
    # Find actual sequence in database
    cursor.execute("""
        SELECT h_mi, c_mi, start_timestamp
        FROM superframes
        WHERE h_mi = ? OR c_mi IN ({})
        ORDER BY start_timestamp
        LIMIT 10
    """.format(','.join('?' * 10)), [H_MI_FIXED] + expected_sequence[1:])
    
    actual_sequence = []
    for row in cursor.fetchall():
        h_mi, c_mi, _ = row
        if h_mi == H_MI_FIXED:
            actual_sequence.append(h_mi)
        if c_mi in expected_sequence:
            actual_sequence.append(c_mi)
    
    print(f"Actual:   {[f'{x:08X}' for x in actual_sequence[:5]]}")
    
    # Check if the sequence matches
    matches = sum(1 for a, e in zip(actual_sequence, expected_sequence) if a == e)
    print(f"\nSequence matches: {matches}/{min(len(actual_sequence), len(expected_sequence))}")

# Check correlation between different tables
print("\n=== Table Correlation Check ===")

# Get the first few C_MI tables
cursor.execute("""
    SELECT name 
    FROM sqlite_master 
    WHERE type='table' AND name LIKE 'C_%' 
    ORDER BY name 
    LIMIT 5
""")

c_tables = [row[0] for row in cursor.fetchall()]

if c_tables:
    print(f"\nChecking progression between tables:")
    
    for i in range(len(c_tables) - 1):
        table1 = c_tables[i]
        table2 = c_tables[i + 1]
        
        # Extract MI values from table names
        mi1 = int(table1.split('_')[1], 16)
        mi2 = int(table2.split('_')[1], 16)
        
        # Predict
        predicted_mi2 = lfsr_step(mi1)
        
        print(f"\n{table1} -> {table2}")
        print(f"  MI1:      {mi1:08X}")
        print(f"  MI2:      {mi2:08X}")
        print(f"  Predicted: {predicted_mi2:08X}")
        print(f"  Match:    {mi2 == predicted_mi2}")

db.close()

print("\n=== Summary ===")
print("The LFSR progression can be used to:")
print("1. Predict the first C-MI from the H-MI")
print("2. Predict subsequent C-MI values") 
print("3. Track the complete LFSR sequence through a transmission")