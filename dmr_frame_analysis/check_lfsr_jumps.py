#!/usr/bin/env python3

import sqlite3
import glob

# LFSR parameters
H_MI_FIXED = 0x6C8AB637
LFSR_PERIOD = 32767

def lfsr_step(state):
    feedback = ((state >> 31) ^ (state >> 3) ^ (state >> 1) ^ state) & 1
    return ((state >> 1) | (feedback << 31)) & 0xFFFFFFFF

def find_lfsr_distance(start, target, max_steps=LFSR_PERIOD):
    """Find how many LFSR steps from start to reach target"""
    state = start
    for steps in range(max_steps):
        if state == target:
            return steps
        state = lfsr_step(state)
    return None

# Get the encrypted database
databases = sorted(glob.glob("dmr_capture_*.db"))
encrypted_db = databases[-1]

print(f"Checking LFSR jumps in: {encrypted_db}")

db = sqlite3.connect(encrypted_db)
cursor = db.cursor()

# Get unique C-MI values in order
cursor.execute("""
    SELECT DISTINCT c_mi, MIN(start_timestamp) as first_seen
    FROM superframes
    WHERE c_mi IS NOT NULL
    GROUP BY c_mi
    ORDER BY first_seen
""")

c_mi_sequence = [row[0] for row in cursor.fetchall()]

print(f"\nUnique C-MI values: {len(c_mi_sequence)}")

# Check jumps from H-MI to each C-MI
print("\n=== LFSR Jumps from H-MI ===")
print(f"Starting from H-MI: {H_MI_FIXED:08X}")

for i, c_mi in enumerate(c_mi_sequence[:10]):
    steps = find_lfsr_distance(H_MI_FIXED, c_mi)
    if steps is not None:
        print(f"\nC-MI {i}: {c_mi:08X}")
        print(f"  Steps from H-MI: {steps}")
        print(f"  Jump size: {steps} ({steps/LFSR_PERIOD:.2%} of period)")
    else:
        print(f"\nC-MI {i}: {c_mi:08X} - NOT FOUND in LFSR sequence!")

# Check jumps between consecutive C-MI values
print("\n\n=== LFSR Jumps Between C-MI Values ===")

for i in range(len(c_mi_sequence) - 1):
    c_mi1 = c_mi_sequence[i]
    c_mi2 = c_mi_sequence[i + 1]
    
    steps = find_lfsr_distance(c_mi1, c_mi2)
    if steps is not None:
        print(f"\n{c_mi1:08X} -> {c_mi2:08X}")
        print(f"  Steps: {steps}")
        print(f"  Jump: {steps} ({steps/LFSR_PERIOD:.2%} of period)")
    else:
        # Try reverse - maybe we went backwards?
        reverse_steps = find_lfsr_distance(c_mi2, c_mi1)
        if reverse_steps is not None:
            print(f"\n{c_mi1:08X} -> {c_mi2:08X}")
            print(f"  REVERSE! Steps backward: {LFSR_PERIOD - reverse_steps}")
        else:
            print(f"\n{c_mi1:08X} -> {c_mi2:08X} - NO LFSR PATH FOUND!")
    
    if i >= 9:  # Just check first 10
        break

# Let's also check if these C-MI values exist in the LFSR sequence at all
print("\n\n=== C-MI Values in LFSR Sequence ===")

# Generate full LFSR sequence
lfsr_sequence = set()
state = H_MI_FIXED
for _ in range(LFSR_PERIOD):
    lfsr_sequence.add(state)
    state = lfsr_step(state)

print(f"\nGenerated full LFSR sequence ({len(lfsr_sequence)} values)")

# Check which C-MI values are in the sequence
found_in_lfsr = 0
not_in_lfsr = []

for c_mi in c_mi_sequence[:20]:
    if c_mi in lfsr_sequence:
        found_in_lfsr += 1
    else:
        not_in_lfsr.append(c_mi)

print(f"\nC-MI values in LFSR sequence: {found_in_lfsr}/{len(c_mi_sequence[:20])}")

if not_in_lfsr:
    print("\nC-MI values NOT in LFSR sequence:")
    for c_mi in not_in_lfsr[:5]:
        print(f"  {c_mi:08X}")

# Check for algorithmic relationship
print("\n\n=== Checking for Other Relationships ===")

# Check if C-MI might be derived from H-MI with different operations
for i, c_mi in enumerate(c_mi_sequence[:5]):
    print(f"\nC-MI {i}: {c_mi:08X}")
    
    # Try XOR
    xor_result = H_MI_FIXED ^ c_mi
    print(f"  H-MI XOR C-MI: {xor_result:08X}")
    
    # Try addition/subtraction
    add_result = (H_MI_FIXED + c_mi) & 0xFFFFFFFF
    sub_result = (c_mi - H_MI_FIXED) & 0xFFFFFFFF
    print(f"  H-MI + C-MI: {add_result:08X}")
    print(f"  C-MI - H-MI: {sub_result:08X}")

db.close()

print("\n=== Conclusion ===")
print("The C-MI values do not follow simple LFSR progression.")
print("They may be:")
print("1. Generated using a different algorithm")
print("2. Using LFSR with large jumps (call length based?)")
print("3. Derived from other values (maybe frame counters?)")