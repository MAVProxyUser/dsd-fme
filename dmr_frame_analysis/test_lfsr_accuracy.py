#!/usr/bin/env python3
"""Test LFSR prediction accuracy on all captures"""

import sqlite3
import glob

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def analyze_capture(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get C-MI values in order of appearance
    cursor.execute('''
        SELECT c_mi 
        FROM superframes 
        WHERE c_mi IS NOT NULL AND c_mi != 0 
        ORDER BY id
    ''')
    
    c_mi_sequence = [row[0] for row in cursor.fetchall()]
    
    if len(c_mi_sequence) < 2:
        return None
    
    # Test consecutive transitions
    correct = 0
    total = 0
    
    for i in range(len(c_mi_sequence) - 1):
        current = c_mi_sequence[i]
        actual_next = c_mi_sequence[i + 1]
        predicted_next = dmr_lfsr_next(current)
        
        if predicted_next == actual_next:
            correct += 1
        total += 1
    
    conn.close()
    
    return correct / total if total > 0 else 0

# Test all captures
db_files = glob.glob("dmr_capture_*.db")
db_files.extend(glob.glob("/home/ubuntu/DMR_Captures/dmr_capture_*.db"))

print("LFSR Prediction Accuracy by Capture:")
print("=" * 50)

overall_correct = 0
overall_total = 0

for db_file in sorted(set(db_files)):
    accuracy = analyze_capture(db_file)
    if accuracy is not None:
        print(f"{db_file}: {accuracy*100:.1f}%")
        
        # Get total transitions for weighting
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM superframes WHERE c_mi IS NOT NULL AND c_mi != 0")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 1:
            overall_correct += accuracy * (count - 1)
            overall_total += (count - 1)

if overall_total > 0:
    overall_accuracy = overall_correct / overall_total
    print(f"\nOverall Weighted Accuracy: {overall_accuracy*100:.1f}%")
else:
    print("\nNo valid data for analysis")