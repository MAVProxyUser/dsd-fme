#!/usr/bin/env python3
"""
Find actual null frames in the new database structure
"""
import sqlite3
from collections import Counter
import numpy as np

def analyze_ambe_table(conn, table_name):
    """Analyze AMBE frames in a specific table"""
    cur = conn.cursor()
    
    # Get all AMBE frames
    cur.execute(f"""
        SELECT ambe_hex FROM {table_name}
        WHERE ambe_hex IS NOT NULL
    """)
    
    frames = []
    for row in cur.fetchall():
        ambe_hex = row[0].lower()
        frames.append(ambe_hex)
    
    return frames

def find_null_frames(db_path):
    """Find null/silence frames in database"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all table names that contain AMBE data
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'H_%' OR name LIKE 'C_%' OR name LIKE 'U_%'
    """)
    
    all_frames = []
    
    for table_row in cur.fetchall():
        table_name = table_row[0]
        frames = analyze_ambe_table(conn, table_name)
        all_frames.extend(frames)
        print(f"Table {table_name}: {len(frames)} frames")
    
    conn.close()
    
    print(f"\nTotal frames analyzed: {len(all_frames)}")
    
    # Find patterns
    frame_counter = Counter(all_frames)
    
    print("\nMost common frames:")
    for frame, count in frame_counter.most_common(15):
        print(f"{frame}: {count} occurrences")
        
        # Analyze pattern
        unique_chars = len(set(frame))
        if unique_chars <= 4:
            print(f"  ^^ Low entropy (only {unique_chars} unique hex chars)")
            
            # Convert to bytes
            try:
                bytes_data = bytes.fromhex(frame)
                unique_bytes = len(set(bytes_data))
                print(f"  {unique_bytes} unique bytes: {list(set(bytes_data))}")
                
                # Check for repeated patterns
                for pattern_len in [1, 2, 3]:
                    if len(bytes_data) % pattern_len == 0:
                        chunks = [bytes_data[i:i+pattern_len] for i in range(0, len(bytes_data), pattern_len)]
                        if len(set(chunks)) == 1:
                            print(f"  Repeating {pattern_len}-byte pattern: {chunks[0].hex()}")
            except:
                pass
        
    # Look for specific null patterns
    print("\nChecking for known null patterns:")
    null_patterns = [
        "000000000000000000",  # All zeros
        "ffffffffffffffff",    # All ones
        "131313131313131313",  # Repeated 0x13
        "acacacacacacacacac",  # Repeated 0xAC
    ]
    
    for pattern in null_patterns:
        if pattern in frame_counter:
            print(f"  {pattern}: {frame_counter[pattern]} occurrences")
        else:
            print(f"  {pattern}: Not found")
    
    # Find frames with minimal variation
    print("\nFrames with minimal byte variation:")
    low_variation = []
    
    for frame in set(all_frames):
        try:
            bytes_data = bytes.fromhex(frame)
            unique_bytes = len(set(bytes_data))
            
            if unique_bytes <= 2:  # Very low variation
                byte_counts = Counter(bytes_data)
                entropy = -sum((count/len(bytes_data)) * np.log2(count/len(bytes_data)) 
                              for count in byte_counts.values() if count > 0)
                
                low_variation.append({
                    'frame': frame,
                    'unique_bytes': unique_bytes,
                    'entropy': entropy,
                    'byte_dist': dict(byte_counts)
                })
        except:
            pass
    
    # Sort by entropy
    low_variation.sort(key=lambda x: x['entropy'])
    
    for item in low_variation[:10]:
        print(f"\n{item['frame']}")
        print(f"  Unique bytes: {item['unique_bytes']}")
        print(f"  Entropy: {item['entropy']:.3f}")
        print(f"  Byte distribution: {item['byte_dist']}")

if __name__ == "__main__":
    databases = [
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_205116.db",
        "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_204818.db"
    ]
    
    for db in databases:
        print(f"\n=== Analyzing {db} ===")
        find_null_frames(db)