#!/usr/bin/env python3
"""
Analyze actual database files for null frames
"""
import sqlite3
from collections import Counter

def find_null_patterns(db_path):
    """Find null or silence patterns in actual captures"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all AMBE frames
    cur.execute("""
        SELECT ambe_hex_frame1, ambe_hex_frame2, ambe_hex_frame3,
               call_duration_ms
        FROM dmr_frames
        WHERE ambe_hex_frame1 IS NOT NULL
    """)
    
    frame_patterns = Counter()
    low_entropy_frames = []
    
    for row in cur.fetchall():
        duration = row[3]
        for i, frame in enumerate(row[:3]):
            if frame:
                frame_lower = frame.lower()
                frame_patterns[frame_lower] += 1
                
                # Check for simple patterns
                unique_chars = len(set(frame_lower))
                if unique_chars <= 4:  # Low variety
                    low_entropy_frames.append({
                        'frame': frame_lower,
                        'unique_chars': unique_chars,
                        'duration': duration
                    })
    
    conn.close()
    
    print(f"Total unique patterns: {len(frame_patterns)}")
    print("\nMost common patterns:")
    for pattern, count in frame_patterns.most_common(20):
        print(f"{pattern}: {count} occurrences")
        
        # Check if it's a simple pattern
        if len(set(pattern)) <= 4:
            print(f"  ^^ Low entropy pattern!")
            
    print(f"\nLow entropy frames: {len(low_entropy_frames)}")
    if low_entropy_frames:
        # Show unique low entropy patterns
        unique_low = {}
        for frame in low_entropy_frames:
            pattern = frame['frame']
            if pattern not in unique_low:
                unique_low[pattern] = frame
        
        print("Unique low entropy patterns:")
        for pattern, info in list(unique_low.items())[:10]:
            print(f"  {pattern}")
            print(f"    Unique chars: {info['unique_chars']}")
            
            # Convert to bytes for analysis
            try:
                bytes_data = bytes.fromhex(pattern)
                byte_counts = Counter(bytes_data)
                print(f"    Byte distribution: {dict(byte_counts)}")
                
                # Check for repeated bytes
                if len(byte_counts) == 1:
                    byte_val = list(byte_counts.keys())[0]
                    print(f"    ALL SAME BYTE: 0x{byte_val:02x}")
            except:
                pass

if __name__ == "__main__":
    databases = [
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_205116.db",
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_204818.db"
    ]
    
    for db in databases:
        print(f"\n=== Analyzing {db} ===")
        find_null_patterns(db)