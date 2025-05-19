#!/usr/bin/env python3
"""Verify C-MI progression follows LFSR sequence"""

import sqlite3
import sys

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def verify_capture(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get distinct C-MI values in order
    cursor.execute('''
        SELECT DISTINCT c_mi 
        FROM superframes 
        WHERE c_mi != 0 
        ORDER BY id
    ''')
    
    c_mi_values = [row[0] for row in cursor.fetchall()]
    
    print(f"Database: {db_file}")
    print(f"Found {len(c_mi_values)} unique C-MI values")
    print("\nVerifying C-MI to C-MI progression:")
    
    matches = 0
    total = len(c_mi_values) - 1  # Number of transitions
    
    for i in range(total):
        current = c_mi_values[i]
        actual_next = c_mi_values[i + 1]
        predicted_next = dmr_lfsr_next(current)
        
        match = predicted_next == actual_next
        if match:
            matches += 1
            
        status = '✓' if match else '✗'
        print(f"{i}: 0x{current:08X} -> Predicted: 0x{predicted_next:08X}, Actual: 0x{actual_next:08X} {status}")
        
        if i >= 10:  # Show first 10 for brevity
            print("...")
            break
    
    # Check overall accuracy
    accuracy = (matches / total) * 100 if total > 0 else 0
    
    # Also check for full accuracy
    full_matches = 0
    for i in range(len(c_mi_values) - 1):
        current = c_mi_values[i]
        actual_next = c_mi_values[i + 1]
        predicted_next = dmr_lfsr_next(current)
        if predicted_next == actual_next:
            full_matches += 1
    
    full_accuracy = (full_matches / (len(c_mi_values) - 1)) * 100 if len(c_mi_values) > 1 else 0
    print(f"\nFull sequence accuracy: {full_matches}/{len(c_mi_values)-1} = {full_accuracy:.1f}%")
    
    # Also verify the H-MI is the fixed value
    cursor.execute('SELECT DISTINCT h_mi FROM superframes WHERE h_mi != 0')
    h_mi_values = [row[0] for row in cursor.fetchall()]
    
    print(f"\nH-MI values: {len(h_mi_values)} unique")
    for h_mi in h_mi_values[:5]:
        print(f"  0x{h_mi:08X}")
    
    if h_mi_values and h_mi_values[0] == 0x6C8AB637:
        print("✓ H-MI is the expected fixed value")
    else:
        print("✗ H-MI is not the expected fixed value")
    
    conn.close()
    return accuracy

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Test with recent capture
        db_file = "dmr_capture_20250518_020534_898339.db"
    else:
        db_file = sys.argv[1]
    
    verify_capture(db_file)