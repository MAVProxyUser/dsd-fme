#!/usr/bin/env python3

import sqlite3
import pandas as pd
from collections import defaultdict, Counter
import numpy as np

def analyze_ambe_patterns_complete(db_path):
    """Complete analysis of AMBE patterns with statistical proof"""
    print(f"Analyzing AMBE patterns in: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get all C_* tables
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
    """, conn)
    
    # Collect ALL AMBE frames
    all_frames = []
    frame_by_prefix = defaultdict(list)
    frame_sequences = []  # To track sequences
    
    print(f"\n=== COLLECTING ALL AMBE FRAMES ===")
    
    for idx, table_name in enumerate(c_tables['name']):
        c_mi = int(table_name.split('_')[1], 16)
        
        # Get frames from this table
        frames = pd.read_sql_query(f"""
            SELECT ambe_hex, timestamp
            FROM '{table_name}'
            ORDER BY timestamp
        """, conn)
        
        for frame_idx, row in frames.iterrows():
            if row['ambe_hex']:
                hex_data = row['ambe_hex']
                all_frames.append(hex_data)
                
                # Track sequences
                frame_sequences.append({
                    'ambe_hex': hex_data,
                    'c_mi': c_mi,
                    'table_idx': idx,
                    'frame_idx': frame_idx,
                    'timestamp': row['timestamp']
                })
                
                # Analyze by prefix
                prefix = hex_data[:2]
                frame_by_prefix[prefix].append({
                    'full_frame': hex_data,
                    'c_mi': c_mi,
                    'position': len(all_frames) - 1
                })
    
    print(f"Total AMBE frames collected: {len(all_frames)}")
    
    # Analyze patterns
    print(f"\n=== PATTERN ANALYSIS ===")
    
    # Most common prefixes
    prefix_counts = Counter([f[:2] for f in all_frames])
    print("\nTop 10 most common prefixes:")
    for prefix, count in prefix_counts.most_common(10):
        percentage = (count / len(all_frames)) * 100
        print(f"  0x{prefix}: {count} frames ({percentage:.2f}%)")
    
    # Test specific claims about 0x00 and 0x02
    print(f"\n=== TESTING SPECIFIC PREFIX CLAIMS ===")
    
    # Analyze 0x02 prefix (claimed beeps)
    print("\n1. Testing 0x02 prefix (claimed beeps):")
    beep_data = frame_by_prefix.get('02', [])
    if beep_data:
        beep_frames = [d['full_frame'] for d in beep_data]
        unique_beeps = Counter(beep_frames)
        print(f"   Total 0x02 frames: {len(beep_frames)}")
        print(f"   Unique patterns: {len(unique_beeps)}")
        print("   Most common patterns:")
        for pattern, count in unique_beeps.most_common(5):
            print(f"     {pattern}: {count} times ({count/len(beep_frames)*100:.1f}%)")
        
        # Check if they cluster at end of transmissions
        positions = [d['position'] for d in beep_data]
        avg_position = np.mean(positions)
        total_frames = len(all_frames)
        print(f"   Average position: {avg_position:.0f}/{total_frames} ({avg_position/total_frames*100:.1f}%)")
    
    # Analyze 0x00 prefix (claimed silence)
    print("\n2. Testing 0x00 prefix (claimed silence):")
    silence_data = frame_by_prefix.get('00', [])
    if silence_data:
        silence_frames = [d['full_frame'] for d in silence_data]
        unique_silence = Counter(silence_frames)
        print(f"   Total 0x00 frames: {len(silence_frames)}")
        print(f"   Unique patterns: {len(unique_silence)}")
        print("   Most common patterns:")
        for pattern, count in unique_silence.most_common(5):
            print(f"     {pattern}: {count} times ({count/len(silence_frames)*100:.1f}%)")
    
    # Test if prefix alone is sufficient
    print("\n3. Testing if prefix alone is sufficient for frame type:")
    
    # Calculate entropy for each prefix
    prefix_reliability = {}
    
    for prefix, data_list in frame_by_prefix.items():
        if len(data_list) < 5:  # Skip rare prefixes
            continue
        
        frames = [d['full_frame'] for d in data_list]
        unique_frames = len(set(frames))
        
        # Calculate how much the rest of the frame varies
        suffixes = [f[2:] for f in frames]
        unique_suffixes = len(set(suffixes))
        
        reliability = 1.0 - (unique_suffixes / len(suffixes))
        
        prefix_reliability[prefix] = {
            'count': len(frames),
            'unique_full': unique_frames,
            'unique_suffix': unique_suffixes,
            'reliability': reliability
        }
    
    print("\nPrefix reliability scores (1.0 = perfectly reliable):")
    sorted_reliability = sorted(prefix_reliability.items(), 
                               key=lambda x: x[1]['reliability'], 
                               reverse=True)
    
    for prefix, stats in sorted_reliability[:10]:
        print(f"   0x{prefix}: reliability={stats['reliability']:.3f}, "
              f"count={stats['count']}, unique_suffixes={stats['unique_suffix']}")
    
    # Simulate AMBE decoder validation
    print("\n=== SIMULATED AMBE DECODER VALIDATION ===")
    
    valid_frames = 0
    invalid_frames = 0
    decode_stats = defaultdict(int)
    
    # Test first 1000 frames
    test_frames = all_frames[:1000] if len(all_frames) > 1000 else all_frames
    
    for frame_hex in test_frames:
        # Basic AMBE frame validation
        if len(frame_hex) == 16:  # 8 bytes
            # Convert to binary for analysis
            try:
                frame_int = int(frame_hex, 16)
                bit_count = bin(frame_int).count('1')
                
                # AMBE frames typically have balanced bit distribution
                if 10 <= bit_count <= 54:  # Reasonable range for 64 bits
                    
                    # Additional validation based on prefix
                    prefix = frame_hex[:2]
                    
                    if prefix == '00':
                        # Silence frames should have low bit density
                        if bit_count < 20:
                            decode_stats['valid_silence'] += 1
                            valid_frames += 1
                        else:
                            decode_stats['invalid_silence'] += 1
                            invalid_frames += 1
                            
                    elif prefix == '02':
                        # Beep frames have specific patterns
                        decode_stats['potential_beep'] += 1
                        valid_frames += 1
                        
                    else:
                        # General speech frame
                        decode_stats['valid_speech'] += 1
                        valid_frames += 1
                else:
                    decode_stats['invalid_bit_distribution'] += 1
                    invalid_frames += 1
                    
            except ValueError:
                decode_stats['parse_error'] += 1
                invalid_frames += 1
        else:
            decode_stats['invalid_length'] += 1
            invalid_frames += 1
    
    total_tested = valid_frames + invalid_frames
    print(f"\nTested {total_tested} frames:")
    print(f"Valid frames: {valid_frames} ({valid_frames/total_tested*100:.1f}%)")
    print(f"Invalid frames: {invalid_frames} ({invalid_frames/total_tested*100:.1f}%)")
    
    print("\nDetailed validation breakdown:")
    for category, count in decode_stats.items():
        print(f"   {category}: {count}")
    
    # Look for repeated patterns (call end beeps)
    print("\n=== REPEATED PATTERN ANALYSIS ===")
    
    # Find consecutive repeated frames
    consecutive_repeats = defaultdict(int)
    repeat_sequences = []
    
    i = 0
    while i < len(all_frames) - 2:
        if all_frames[i] == all_frames[i+1]:
            # Found a repeat, see how long it continues
            repeat_frame = all_frames[i]
            repeat_count = 2
            
            j = i + 2
            while j < len(all_frames) and all_frames[j] == repeat_frame:
                repeat_count += 1
                j += 1
            
            if repeat_count >= 3:
                consecutive_repeats[repeat_frame] += 1
                repeat_sequences.append({
                    'frame': repeat_frame,
                    'count': repeat_count,
                    'start_position': i,
                    'end_position': j-1
                })
            
            i = j
        else:
            i += 1
    
    print("\nFrames repeated 3+ times consecutively:")
    sorted_repeats = sorted(consecutive_repeats.items(), 
                           key=lambda x: x[1], 
                           reverse=True)
    
    for frame, occurrences in sorted_repeats[:5]:
        print(f"   {frame}: {occurrences} sequences")
        # Show where these occur
        positions = [s['start_position'] for s in repeat_sequences 
                    if s['frame'] == frame]
        if positions:
            avg_pos = np.mean(positions)
            print(f"     Average position: {avg_pos:.0f}/{len(all_frames)} "
                  f"({avg_pos/len(all_frames)*100:.1f}%)")
    
    conn.close()
    
    return frame_by_prefix, prefix_reliability

# Statistical proof with confidence intervals
def calculate_statistical_confidence(frame_by_prefix):
    """Calculate statistical confidence for prefix-based frame type identification"""
    print("\n=== STATISTICAL CONFIDENCE ANALYSIS ===")
    
    # Focus on claimed patterns
    for prefix in ['00', '02']:
        if prefix not in frame_by_prefix:
            print(f"\nNo data for prefix 0x{prefix}")
            continue
        
        data = frame_by_prefix[prefix]
        frames = [d['full_frame'] for d in data]
        
        print(f"\nStatistical analysis for prefix 0x{prefix}:")
        print(f"Sample size: {len(frames)}")
        
        # Pattern consistency
        pattern_counts = Counter(frames)
        most_common = pattern_counts.most_common(1)[0]
        consistency = most_common[1] / len(frames)
        
        print(f"Most common full pattern: {most_common[0]}")
        print(f"Occurrences: {most_common[1]}/{len(frames)} ({consistency:.1%})")
        
        # Calculate 95% confidence interval
        import scipy.stats as stats
        n = len(frames)
        if n > 0:
            # Wilson score interval for better small sample performance
            z = 1.96  # 95% confidence
            p_hat = consistency
            
            denominator = 1 + z**2/n
            center = (p_hat + z**2/(2*n)) / denominator
            margin = z * np.sqrt((p_hat*(1-p_hat)/n + z**2/(4*n**2))) / denominator
            
            lower = center - margin
            upper = center + margin
            
            print(f"95% Confidence Interval: [{lower:.1%}, {upper:.1%}]")
            
            # Statistical verdict
            if lower > 0.7:
                print("VERDICT: STRONG EVIDENCE - Prefix is highly predictive")
            elif lower > 0.5:
                print("VERDICT: MODERATE EVIDENCE - Prefix is somewhat predictive")
            else:
                print("VERDICT: WEAK EVIDENCE - Prefix alone is not sufficient")
        
        # Analyze suffix variability
        suffixes = [f[2:] for f in frames]
        unique_suffixes = len(set(suffixes))
        suffix_entropy = unique_suffixes / len(suffixes)
        
        print(f"Suffix entropy: {suffix_entropy:.3f} "
              f"({unique_suffixes} unique suffixes)")

# Main execution
db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_025824.db"
frame_by_prefix, prefix_reliability = analyze_ambe_patterns_complete(db_path)
calculate_statistical_confidence(frame_by_prefix)