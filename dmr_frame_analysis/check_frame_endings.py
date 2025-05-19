#!/usr/bin/env python3
"""
Check frame endings for patterns
"""
import sqlite3
from collections import Counter

def analyze_frame_endings(db_path):
    """Check last bytes of frames for patterns"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all table names that contain AMBE data
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'H_%' OR name LIKE 'C_%' OR name LIKE 'U_%'
    """)
    
    ending_patterns = Counter()
    frames_with_zeros = []
    
    for table_row in cur.fetchall():
        table_name = table_row[0]
        
        cur.execute(f"SELECT ambe_hex FROM {table_name} WHERE ambe_hex IS NOT NULL")
        
        for row in cur.fetchall():
            ambe_hex = row[0].lower()
            
            # Check last 2 bytes
            last_bytes = ambe_hex[-4:]
            ending_patterns[last_bytes] += 1
            
            # Check for frames ending in 00
            if ambe_hex.endswith('00'):
                frames_with_zeros.append(ambe_hex)
    
    conn.close()
    
    print("Most common frame endings:")
    for ending, count in ending_patterns.most_common(20):
        print(f"  ...{ending}: {count} occurrences")
        if ending == '0000':
            print("    ^^ Double zero ending!")
    
    print(f"\nFrames ending with 00: {len(frames_with_zeros)}")
    if frames_with_zeros:
        print("Examples:")
        for frame in frames_with_zeros[:5]:
            print(f"  {frame}")
            
            # Check how many trailing zeros
            zero_count = 0
            for i in range(len(frame)-1, -1, -2):
                if frame[i-1:i+1] == '00':
                    zero_count += 1
                else:
                    break
            if zero_count > 1:
                print(f"    {zero_count} trailing zero bytes")

def check_specific_patterns(db_path):
    """Look for specific byte patterns that might indicate silence"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all table names that contain AMBE data
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'H_%' OR name LIKE 'C_%' OR name LIKE 'U_%'
    """)
    
    pattern_counts = {
        'contains_0000': 0,
        'contains_ffff': 0,
        'contains_aaaa': 0,
        'contains_5555': 0,
        'multiple_zeros': 0,
        'low_bits_set': 0
    }
    
    for table_row in cur.fetchall():
        table_name = table_row[0]
        
        cur.execute(f"SELECT ambe_hex FROM {table_name} WHERE ambe_hex IS NOT NULL")
        
        for row in cur.fetchall():
            ambe_hex = row[0].lower()
            
            # Check for specific patterns
            if '0000' in ambe_hex:
                pattern_counts['contains_0000'] += 1
            if 'ffff' in ambe_hex:
                pattern_counts['contains_ffff'] += 1
            if 'aaaa' in ambe_hex:
                pattern_counts['contains_aaaa'] += 1
            if '5555' in ambe_hex:
                pattern_counts['contains_5555'] += 1
            
            # Count zero bytes
            zero_bytes = ambe_hex.count('00') // 2
            if zero_bytes >= 3:
                pattern_counts['multiple_zeros'] += 1
            
            # Check for low bit density
            bytes_data = bytes.fromhex(ambe_hex)
            bit_count = sum(bin(b).count('1') for b in bytes_data)
            if bit_count < 18:  # Less than 25% bits set
                pattern_counts['low_bits_set'] += 1
    
    conn.close()
    
    print("\nPattern analysis:")
    for pattern, count in pattern_counts.items():
        print(f"  {pattern}: {count} frames")

if __name__ == "__main__":
    databases = [
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_205116.db",
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_204818.db"
    ]
    
    for db in databases:
        print(f"\n=== Analyzing {db} ===")
        analyze_frame_endings(db)
        check_specific_patterns(db)