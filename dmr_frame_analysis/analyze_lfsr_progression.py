#!/usr/bin/env python3
"""
Analyze LFSR progression through transmission gaps
"""
import sqlite3
from datetime import datetime

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def find_lfsr_position(target, start):
    """Find position of target MI in LFSR sequence from start"""
    mi = start
    for step in range(32767):
        mi = dmr_lfsr_next(mi)
        if mi == target:
            return step + 1
    return None

def analyze_lfsr_progression(db_path):
    """Analyze how LFSR progresses through transmissions"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get superframes with MI values
    cur.execute("""
        SELECT id, start_timestamp, h_mi, c_mi, source_id, target_id
        FROM superframes
        WHERE c_mi != 0
        ORDER BY start_timestamp, id
    """)
    
    superframes = cur.fetchall()
    
    print("LFSR Progression Analysis:")
    print("=" * 60)
    
    h_mi = 0x6C8AB637
    transmissions = []
    current_transmission = None
    prev_timestamp = None
    
    for sf_id, timestamp, h_mi_val, c_mi_val, src, tgt in superframes:
        ts = datetime.fromisoformat(timestamp)
        
        # Check for transmission gap (more than 0.5 seconds)
        if prev_timestamp and (ts - prev_timestamp).total_seconds() > 0.5:
            # Save current transmission and start new one
            if current_transmission:
                transmissions.append(current_transmission)
            current_transmission = {
                'start_time': ts,
                'c_mi_values': []
            }
        elif not current_transmission:
            current_transmission = {
                'start_time': ts,
                'c_mi_values': []
            }
        
        # Add C_MI to current transmission
        current_transmission['c_mi_values'].append({
            'sf_id': sf_id,
            'timestamp': ts,
            'h_mi': h_mi_val,
            'c_mi': c_mi_val,
            'source': src,
            'target': tgt
        })
        
        prev_timestamp = ts
    
    # Add last transmission
    if current_transmission:
        transmissions.append(current_transmission)
    
    # Analyze each transmission
    print(f"Found {len(transmissions)} separate transmissions:\n")
    
    for i, trans in enumerate(transmissions):
        start_time = trans['start_time']
        c_mi_values = trans['c_mi_values']
        
        print(f"Transmission {i+1}:")
        print(f"  Start: {start_time}")
        print(f"  Duration: {(c_mi_values[-1]['timestamp'] - start_time).total_seconds():.1f} seconds")
        print(f"  Frames: {len(c_mi_values)}")
        
        # Analyze LFSR sequence
        first_c_mi = c_mi_values[0]['c_mi']
        position = find_lfsr_position(first_c_mi, h_mi)
        
        print(f"  First C_MI: 0x{first_c_mi:08x} (position {position} from H_MI)")
        
        # Check if sequence is continuous
        continuous = True
        expected = first_c_mi
        
        for j, frame in enumerate(c_mi_values[1:], 1):
            expected = dmr_lfsr_next(expected)
            if frame['c_mi'] == expected:
                print(f"    Frame {j+1}: 0x{frame['c_mi']:08x} ✓")
            else:
                # Find actual position
                actual_pos = find_lfsr_position(frame['c_mi'], h_mi)
                print(f"    Frame {j+1}: 0x{frame['c_mi']:08x} - Jump to position {actual_pos}")
                continuous = False
                expected = frame['c_mi']  # Reset expected for next iteration
        
        print(f"  Continuous: {'Yes' if continuous else 'No'}")
        print()
    
    # Show complete LFSR sequence found
    print("\nComplete LFSR Sequence:")
    all_c_mi = set()
    for trans in transmissions:
        for frame in trans['c_mi_values']:
            if frame['h_mi'] == h_mi:  # Only encrypted frames
                all_c_mi.add(frame['c_mi'])
    
    # Sort by position in LFSR
    sorted_c_mi = []
    for c_mi in all_c_mi:
        pos = find_lfsr_position(c_mi, h_mi)
        if pos:
            sorted_c_mi.append((pos, c_mi))
    
    sorted_c_mi.sort()
    
    print(f"Found {len(sorted_c_mi)} unique C_MI values:")
    for pos, c_mi in sorted_c_mi:
        print(f"  Position {pos:3d}: 0x{c_mi:08x}")
    
    # Check for gaps in sequence
    if sorted_c_mi:
        print("\nGaps in LFSR sequence:")
        prev_pos = 0
        for pos, c_mi in sorted_c_mi:
            if pos - prev_pos > 1 and prev_pos > 0:
                print(f"  Gap: positions {prev_pos+1} to {pos-1} ({pos-prev_pos-1} values)")
            prev_pos = pos
    
    conn.close()

if __name__ == "__main__":
    # Analyze Radio 1234 (encrypted)
    print("=== Radio 1234 (Encrypted) ===")
    analyze_lfsr_progression("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234505.db")