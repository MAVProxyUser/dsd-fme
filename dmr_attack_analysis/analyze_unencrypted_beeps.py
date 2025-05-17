#!/usr/bin/env python3

import sqlite3
import pandas as pd
from collections import Counter, defaultdict
import numpy as np

def analyze_unencrypted_capture(db_path):
    """Analyze unencrypted capture to find beep patterns"""
    print(f"Analyzing unencrypted capture: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get all C_* tables (no C-MI in unencrypted, but same structure)
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
    """, conn)
    
    print(f"\nFound {len(c_tables)} tables")
    
    all_frames = []
    frames_by_position = defaultdict(list)
    
    # Collect all frames with timing info
    for table_name in c_tables['name']:
        frames = pd.read_sql_query(f"""
            SELECT ambe_hex, timestamp
            FROM '{table_name}'
            ORDER BY timestamp
        """, conn)
        
        for idx, row in frames.iterrows():
            frame_data = {
                'ambe_hex': row['ambe_hex'],
                'timestamp': pd.to_datetime(row['timestamp']),
                'table': table_name,
                'position': idx
            }
            all_frames.append(frame_data)
    
    # Sort by timestamp
    all_frames.sort(key=lambda x: x['timestamp'])
    
    print(f"Total frames: {len(all_frames)}")
    
    # Find transmission boundaries
    print("\n=== TRANSMISSION BOUNDARY ANALYSIS ===")
    
    transmissions = []
    current_transmission = []
    
    for i in range(len(all_frames)):
        if i == 0:
            current_transmission.append(all_frames[i])
        else:
            time_diff = (all_frames[i]['timestamp'] - 
                        all_frames[i-1]['timestamp']).total_seconds()
            
            if time_diff > 0.5:  # New transmission
                transmissions.append(current_transmission)
                current_transmission = [all_frames[i]]
            else:
                current_transmission.append(all_frames[i])
    
    # Don't forget the last transmission
    if current_transmission:
        transmissions.append(current_transmission)
    
    print(f"Found {len(transmissions)} transmissions")
    
    # Analyze end frames of each transmission
    print("\n=== END-OF-TRANSMISSION PATTERNS ===")
    
    end_patterns = Counter()
    beep_candidates = []
    
    for trans_idx, transmission in enumerate(transmissions):
        if len(transmission) < 5:
            continue
            
        print(f"\nTransmission {trans_idx + 1} ({len(transmission)} frames):")
        
        # Look at last 10 frames
        end_frames = transmission[-10:]
        
        print("Last 10 frames:")
        for idx, frame in enumerate(end_frames):
            print(f"  -{10-idx}: {frame['ambe_hex']}")
            
            # Count patterns in last 5 frames
            if idx >= 5:
                end_patterns[frame['ambe_hex']] += 1
                beep_candidates.append(frame)
    
    # Find repeated patterns at transmission ends
    print("\n=== MOST COMMON END PATTERNS ===")
    
    for pattern, count in end_patterns.most_common(10):
        print(f"{pattern}: {count} occurrences")
    
    # Look for consecutive repeated frames (strong beep indicator)
    print("\n=== CONSECUTIVE REPEATED FRAMES ===")
    
    repeated_sequences = defaultdict(list)
    
    for trans_idx, transmission in enumerate(transmissions):
        for i in range(len(transmission) - 2):
            if (transmission[i]['ambe_hex'] == 
                transmission[i+1]['ambe_hex'] == 
                transmission[i+2]['ambe_hex']):
                
                pattern = transmission[i]['ambe_hex']
                count = 3
                
                # Count how many times it continues
                j = i + 3
                while (j < len(transmission) and 
                       transmission[j]['ambe_hex'] == pattern):
                    count += 1
                    j += 1
                
                repeated_sequences[pattern].append({
                    'trans_idx': trans_idx,
                    'position': i,
                    'count': count,
                    'at_end': (i + count >= len(transmission) - 3)
                })
    
    print(f"Found {len(repeated_sequences)} unique repeated patterns")
    
    # Show patterns that repeat at transmission ends
    end_repeats = {}
    for pattern, occurrences in repeated_sequences.items():
        end_count = sum(1 for occ in occurrences if occ['at_end'])
        if end_count > 0:
            end_repeats[pattern] = end_count
    
    print("\nPatterns that repeat at transmission ends:")
    for pattern, count in sorted(end_repeats.items(), 
                               key=lambda x: x[1], 
                               reverse=True):
        print(f"  {pattern}: {count} transmissions")
    
    # Analyze bit patterns of potential beeps
    print("\n=== BIT PATTERN ANALYSIS ===")
    
    if end_repeats:
        # Take the most common end repeat pattern
        beep_pattern = max(end_repeats.items(), key=lambda x: x[1])[0]
        print(f"\nAnalyzing potential beep pattern: {beep_pattern}")
        
        # Convert to binary
        beep_int = int(beep_pattern, 16)
        beep_bits = bin(beep_int)[2:].zfill(64)
        
        print(f"Binary: {beep_bits}")
        print(f"Bit count: {beep_bits.count('1')}/64")
        
        # Check byte structure
        print("\nByte breakdown:")
        for i in range(0, 64, 8):
            byte_bits = beep_bits[i:i+8]
            byte_val = int(byte_bits, 2)
            print(f"  Byte {i//8}: {byte_bits} (0x{byte_val:02X})")
    
    conn.close()
    
    return end_patterns, repeated_sequences

# Run the analysis
db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_032539.db"
end_patterns, repeated_sequences = analyze_unencrypted_capture(db_path)