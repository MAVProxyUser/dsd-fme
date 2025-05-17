#!/usr/bin/env python3
"""
Find and analyze beep patterns in the latest capture
"""
import sqlite3
import glob
import binascii
from collections import defaultdict
from datetime import datetime
import json

def find_beep_patterns():
    """Find repeating patterns that could be beeps"""
    
    print("Beep Pattern Finder")
    print("==================\n")
    
    # Get latest database
    db_files = sorted(glob.glob("dmr_capture_*.db"))
    latest_db = db_files[-1]
    
    print(f"Analyzing latest capture: {latest_db}")
    
    conn = sqlite3.connect(latest_db)
    cursor = conn.cursor()
    
    # Get all C-MI values with timestamps
    cursor.execute("""
        SELECT control_mi, timestamp 
        FROM dmr_correlations 
        ORDER BY timestamp
    """)
    correlations = cursor.fetchall()
    
    print(f"Total correlations: {len(correlations)}")
    
    # Analyze AMBE patterns at end of each C-MI sequence
    pattern_locations = defaultdict(list)
    end_patterns = defaultdict(list)
    
    for c_mi, timestamp in correlations:
        table_name = f"C_{c_mi:08X}_S0"
        
        try:
            # Get the last few AMBE frames
            cursor.execute(f"""
                SELECT ambe_hex, timestamp, id
                FROM {table_name}
                ORDER BY id DESC
                LIMIT 5
            """)
            frames = cursor.fetchall()
            
            if frames:
                # Look at the very last frame (most likely to be beep)
                last_frame = frames[0]
                ambe_hex, frame_time, frame_id = last_frame
                ambe_bytes = binascii.unhexlify(ambe_hex.replace('0x', ''))
                
                # Record this pattern
                pattern_locations[ambe_bytes].append({
                    'c_mi': c_mi,
                    'table': table_name,
                    'timestamp': frame_time,
                    'frame_id': frame_id,
                    'position': 'last'
                })
                
                # Also check penultimate frame
                if len(frames) > 1:
                    penult_hex = frames[1][0]
                    penult_bytes = binascii.unhexlify(penult_hex.replace('0x', ''))
                    end_patterns[penult_bytes].append({
                        'c_mi': c_mi,
                        'position': 'second_last'
                    })
        
        except sqlite3.OperationalError:
            continue
    
    # Find patterns that appear multiple times
    print("\n=== REPEATED PATTERNS ===")
    repeated_patterns = {k: v for k, v in pattern_locations.items() if len(v) > 1}
    
    if repeated_patterns:
        print(f"Found {len(repeated_patterns)} repeated patterns")
        
        for pattern, locations in sorted(repeated_patterns.items(), 
                                       key=lambda x: len(x[1]), 
                                       reverse=True)[:10]:
            print(f"\nPattern: {binascii.hexlify(pattern).decode()[:32]}...")
            print(f"Appears {len(locations)} times")
            print("Locations:")
            for loc in locations[:5]:
                print(f"  C-MI: 0x{loc['c_mi']:08X}, Time: {loc['timestamp']}")
    else:
        print("No exact repeated patterns found")
    
    # Look for similar patterns (hamming distance)
    print("\n=== SIMILAR PATTERNS ===")
    all_patterns = list(pattern_locations.keys())
    
    similar_groups = defaultdict(list)
    for i, pattern1 in enumerate(all_patterns):
        for j, pattern2 in enumerate(all_patterns[i+1:], i+1):
            if len(pattern1) == len(pattern2):
                # Calculate hamming distance
                distance = sum(b1 != b2 for b1, b2 in zip(pattern1, pattern2))
                if distance <= 3:  # Very similar
                    similar_groups[pattern1].append((pattern2, distance))
    
    if similar_groups:
        print(f"Found {len(similar_groups)} groups of similar patterns")
        for pattern, similar in list(similar_groups.items())[:3]:
            print(f"\nBase: {binascii.hexlify(pattern).decode()[:32]}...")
            print("Similar patterns:")
            for sim_pattern, dist in similar:
                print(f"  Distance {dist}: {binascii.hexlify(sim_pattern).decode()[:32]}...")
    
    # Analyze timing gaps to find beep boundaries
    print("\n=== TIMING ANALYSIS ===")
    time_gaps = []
    
    for i in range(1, len(correlations)):
        t1 = datetime.strptime(correlations[i-1][1], '%Y-%m-%d %H:%M:%S')
        t2 = datetime.strptime(correlations[i][1], '%Y-%m-%d %H:%M:%S')
        gap = (t2 - t1).seconds
        
        if gap > 0:
            time_gaps.append((i, gap, correlations[i][0]))
    
    if time_gaps:
        print("Significant time gaps (potential beep boundaries):")
        for idx, gap, c_mi in sorted(time_gaps, key=lambda x: x[1], reverse=True)[:10]:
            print(f"  Position {idx}: {gap}s gap before C-MI 0x{c_mi:08X}")
    
    # Pattern frequency analysis
    print("\n=== PATTERN FREQUENCY ===")
    pattern_lengths = defaultdict(int)
    for pattern in all_patterns:
        pattern_lengths[len(pattern)] += 1
    
    print("Pattern lengths:")
    for length, count in sorted(pattern_lengths.items()):
        print(f"  {length} bytes: {count} patterns")
    
    conn.close()
    
    # Save analysis results
    results = {
        'database': latest_db,
        'total_patterns': len(all_patterns),
        'repeated_patterns': len(repeated_patterns),
        'similar_groups': len(similar_groups),
        'analysis_time': datetime.now().isoformat()
    }
    
    with open('beep_analysis_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to beep_analysis_results.json")
    
    return repeated_patterns

def correlate_with_predictions():
    """Correlate found patterns with LFSR predictions"""
    
    print("\n=== PREDICTION CORRELATION ===")
    
    # Load pattern model
    try:
        with open('dmr_master_pattern.json', 'r') as f:
            model = json.load(f)
        
        # Get latest predictions
        h_mi = 0x6C8AB637
        last_c_mi = 0x34F2F1F1  # From the output above
        
        predicted = [
            0x7C3EB750, 0x62BBF551, 0x3EEEB2CE, 0x4874CD48,
            0xF98FC11E, 0xBD185019, 0x7780450B, 0x0679B283,
            0xC8C4CD17, 0x67685F2E
        ]
        
        print(f"Next predicted C-MI values:")
        for i, pred in enumerate(predicted):
            print(f"  {i+1}: 0x{pred:08X}")
        
        print("\nTo verify:")
        print("1. Capture more data with beeps")
        print("2. Check if these C-MI values appear")
        print("3. Analyze AMBE patterns at these positions")
        
    except FileNotFoundError:
        print("Pattern model not found")

if __name__ == "__main__":
    # Find beep patterns
    beep_patterns = find_beep_patterns()
    
    # Correlate with predictions
    correlate_with_predictions()
    
    print("\n=== RECOMMENDATIONS ===")
    print("1. Look for patterns that appear at regular intervals")
    print("2. Check patterns that appear after time gaps")
    print("3. Compare similar patterns for beep variations")
    print("4. Correlate with predicted C-MI values")