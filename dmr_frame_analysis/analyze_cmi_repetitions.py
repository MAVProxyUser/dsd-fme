#!/usr/bin/env python3
"""Analyze C-MI repetition patterns in captures"""

import sqlite3

def analyze_repetitions(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get all C-MI values in order
    cursor.execute('''
        SELECT c_mi 
        FROM superframes 
        WHERE c_mi IS NOT NULL AND c_mi != 0 
        ORDER BY id
    ''')
    
    c_mi_sequence = [row[0] for row in cursor.fetchall()]
    
    print(f"\nAnalyzing {db_file}:")
    print(f"Total C-MI values: {len(c_mi_sequence)}")
    print(f"Unique C-MI values: {len(set(c_mi_sequence))}")
    
    # Count consecutive repetitions
    repetitions = 0
    max_repeat = 1
    current_repeat = 1
    
    for i in range(1, len(c_mi_sequence)):
        if c_mi_sequence[i] == c_mi_sequence[i-1]:
            repetitions += 1
            current_repeat += 1
            max_repeat = max(max_repeat, current_repeat)
        else:
            current_repeat = 1
    
    # Analyze patterns
    repeat_pattern = {}
    i = 0
    while i < len(c_mi_sequence):
        count = 1
        while i + count < len(c_mi_sequence) and c_mi_sequence[i] == c_mi_sequence[i + count]:
            count += 1
        
        if count not in repeat_pattern:
            repeat_pattern[count] = 0
        repeat_pattern[count] += 1
        i += count
    
    print(f"Consecutive repetitions: {repetitions}")
    print(f"Max consecutive repeats: {max_repeat}")
    print(f"Repetition percentage: {repetitions/(len(c_mi_sequence)-1)*100:.1f}%")
    
    print("\nRepetition pattern distribution:")
    for length, count in sorted(repeat_pattern.items()):
        print(f"  {length}x repeat: {count} occurrences")
    
    # Sample some sequences
    print("\nSample sequences:")
    for i in range(0, min(50, len(c_mi_sequence)), 5):
        values = c_mi_sequence[i:i+5]
        hex_values = [f"0x{v:08X}" for v in values]
        print(f"  {i}: {' -> '.join(hex_values)}")
    
    conn.close()

# Test the encrypted capture
analyze_repetitions("dmr_capture_20250518_112024_998484.db")