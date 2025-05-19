#!/usr/bin/env python3
"""
Find frames with all zeros or simple patterns
"""
import sqlite3
import glob

def check_simple_patterns(ambe_hex):
    """Check if frame matches known simple patterns"""
    patterns = {
        'all_zeros': '000000000000000000',
        'all_ones': 'ffffffffffffffff',
        'alternating_01': '00ff00ff00ff00ff00',
        'alternating_10': 'ff00ff00ff00ff00ff',
        'all_aa': 'aaaaaaaaaaaaaaaaaa',
        'all_55': '5555555555555555',
        'all_cc': 'cccccccccccccccc',
        'all_33': '3333333333333333',
    }
    
    # Normalize to lowercase
    ambe_hex = ambe_hex.lower()
    
    for name, pattern in patterns.items():
        if ambe_hex == pattern:
            return name
    
    # Check for single byte repeated
    if len(ambe_hex) == 18:  # 9 bytes in hex
        first_byte = ambe_hex[:2]
        if ambe_hex == first_byte * 9:
            return f'repeated_{first_byte}'
    
    return None

def find_simple_frames(db_path):
    """Find frames with simple patterns"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all AMBE frames
    cur.execute("""
        SELECT id, ambe_hex_frame1, ambe_hex_frame2, ambe_hex_frame3,
               call_duration_ms, src_radio_id, dst_radio_id
        FROM dmr_frames
        WHERE ambe_hex_frame1 IS NOT NULL
        ORDER BY id
    """)
    
    simple_frames = []
    
    for row in cur.fetchall():
        id_, f1, f2, f3, duration, src, dst = row
        
        for i, frame in enumerate([f1, f2, f3]):
            if frame:
                pattern = check_simple_patterns(frame)
                if pattern:
                    simple_frames.append({
                        'id': id_,
                        'frame_pos': i + 1,
                        'pattern': pattern,
                        'hex': frame,
                        'duration': duration,
                        'src': src,
                        'dst': dst
                    })
    
    conn.close()
    
    if simple_frames:
        print(f"Found {len(simple_frames)} simple pattern frames:")
        
        # Group by pattern
        patterns = {}
        for frame in simple_frames:
            pattern = frame['pattern']
            if pattern not in patterns:
                patterns[pattern] = []
            patterns[pattern].append(frame)
        
        for pattern, frames in patterns.items():
            print(f"\n{pattern}: {len(frames)} occurrences")
            # Show first example
            example = frames[0]
            print(f"  Example: {example['hex']}")
            print(f"  Call duration: {example['duration']}ms")
            print(f"  Frame position: {example['frame_pos']}")
    else:
        print("No simple pattern frames found")
    
    return simple_frames

# Check for frames at start/end of calls
def find_edge_frames(db_path):
    """Find frames at the very start or end of calls"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Find first and last frames of each call
    cur.execute("""
        WITH call_edges AS (
            SELECT src_radio_id, dst_radio_id, 
                   MIN(id) as first_id, MAX(id) as last_id
            FROM dmr_frames
            WHERE ambe_hex_frame1 IS NOT NULL
            GROUP BY src_radio_id, dst_radio_id
        )
        SELECT f.id, f.ambe_hex_frame1, f.ambe_hex_frame2, f.ambe_hex_frame3,
               CASE WHEN f.id = ce.first_id THEN 'first'
                    WHEN f.id = ce.last_id THEN 'last'
               END as position
        FROM dmr_frames f
        JOIN call_edges ce ON f.src_radio_id = ce.src_radio_id 
                          AND f.dst_radio_id = ce.dst_radio_id
        WHERE f.id IN (ce.first_id, ce.last_id)
    """)
    
    edge_frames = []
    for row in cur.fetchall():
        id_, f1, f2, f3, position = row
        for i, frame in enumerate([f1, f2, f3]):
            if frame:
                edge_frames.append({
                    'id': id_,
                    'frame': frame,
                    'frame_pos': i + 1,
                    'call_position': position
                })
    
    conn.close()
    
    print(f"\nFound {len(edge_frames)} edge frames")
    
    # Look for patterns in edge frames
    edge_patterns = {}
    for ef in edge_frames:
        pattern = check_simple_patterns(ef['frame'])
        if pattern:
            key = f"{ef['call_position']}_{pattern}"
            if key not in edge_patterns:
                edge_patterns[key] = []
            edge_patterns[key].append(ef)
    
    if edge_patterns:
        print("\nEdge frame patterns:")
        for pattern, frames in edge_patterns.items():
            print(f"  {pattern}: {len(frames)} occurrences")

if __name__ == "__main__":
    # Check all databases
    db_files = glob.glob("/home/ubuntu/dsd-fme_sqlite/dmr_attack_analysis/*.db")
    
    for db_file in db_files:
        print(f"\n=== Analyzing {db_file} ===")
        find_simple_frames(db_file)
        find_edge_frames(db_file)