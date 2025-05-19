#!/usr/bin/env python3
"""
Direct search for null-like patterns in AMBE frames
"""
import sqlite3
import glob
from collections import Counter

def analyze_all_frames(db_path):
    """Analyze all AMBE frames to find patterns"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get sample of frames
    cur.execute("""
        SELECT ambe_hex_frame1, ambe_hex_frame2, ambe_hex_frame3
        FROM dmr_frames
        WHERE ambe_hex_frame1 IS NOT NULL
        LIMIT 100
    """)
    
    all_frames = []
    for row in cur.fetchall():
        for frame in row:
            if frame:
                all_frames.append(frame.lower())
    
    print(f"Sample of {len(all_frames)} frames:")
    
    # Check for common patterns
    frame_counter = Counter(all_frames)
    
    print("\nMost common frames:")
    for frame, count in frame_counter.most_common(10):
        print(f"  {frame}: {count} times")
        
        # Check if it's a simple pattern
        if len(set(frame)) <= 3:  # Only a few unique characters
            print(f"    Low complexity frame!")
    
    # Look for frames with minimal variation
    print("\nFrames with low byte variation:")
    for frame in set(all_frames):
        bytes_data = bytes.fromhex(frame)
        unique_bytes = len(set(bytes_data))
        if unique_bytes <= 3:
            print(f"  {frame}")
            print(f"    Unique bytes: {unique_bytes}")
            print(f"    Byte values: {list(set(bytes_data))}")
    
    conn.close()

if __name__ == "__main__":
    db_files = glob.glob("/home/ubuntu/dsd-fme_sqlite/dmr_attack_analysis/*.db")
    
    for db_file in db_files:
        print(f"\n=== {db_file} ===")
        analyze_all_frames(db_file)