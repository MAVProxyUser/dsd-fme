#!/usr/bin/env python3
"""Predict the next IVs for 150.125 MHz transmission"""

import sqlite3

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

# Get the last C-MI value from our most recent capture
db_file = "dmr_capture_20250518_020534_898339.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get the last unique C-MI value
cursor.execute('''
    SELECT DISTINCT c_mi 
    FROM superframes 
    WHERE c_mi != 0 
    ORDER BY id DESC
    LIMIT 1
''')

last_c_mi = cursor.fetchone()[0]
print(f"Last captured C-MI: 0x{last_c_mi:08X}")

# Predict the next 10 C-MI values
print("\nPredicted next C-MI values for 150.125 MHz:")
print("=" * 40)

current = last_c_mi
predictions = []

for i in range(10):
    next_mi = dmr_lfsr_next(current)
    predictions.append(next_mi)
    print(f"{i+1}: 0x{next_mi:08X}")
    current = next_mi

print("\nThe fixed H-MI will remain: 0x6C8AB637")
print("\nNext transmission will use:")
print(f"  H-MI: 0x6C8AB637")
print(f"  C-MI: 0x{predictions[0]:08X}")

# Also show the sequence of values we expect
print("\nExpected sequence of C-MI values:")
for i, mi in enumerate(predictions[:5]):
    print(f"  Superframe {i}: 0x{mi:08X}")

conn.close()

# Save these predictions to a file for later verification
with open('predicted_ivs.txt', 'w') as f:
    f.write(f"Predictions made at: {db_file}\n")
    f.write(f"Last C-MI: 0x{last_c_mi:08X}\n")
    f.write("Predicted next C-MI values:\n")
    for i, mi in enumerate(predictions):
        f.write(f"{i+1}: 0x{mi:08X}\n")
    
print("\nPredictions saved to predicted_ivs.txt")