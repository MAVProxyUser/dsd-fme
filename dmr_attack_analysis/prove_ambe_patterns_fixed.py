#!/usr/bin/env python3

import sqlite3
import pandas as pd
from collections import defaultdict, Counter
import numpy as np

def analyze_ambe_patterns_thoroughly(db_path):
    """Deep analysis of AMBE patterns to prove/disprove claims"""
    print(f"Analyzing AMBE patterns in: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get all C_* tables
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
    """, conn)
    
    # Collect ALL AMBE frames with context
    all_frames_with_context = []
    frame_by_prefix = defaultdict(list)
    prefix_patterns = Counter()
    
    print(f"\n=== COLLECTING ALL AMBE FRAMES WITH CONTEXT ===")
    
    for table_name in c_tables['name']:
        c_mi = int(table_name.split('_')[1], 16)
        
        frames = pd.read_sql_query(f"""
            SELECT ambe_hex, timestamp, superframe_id
            FROM '{table_name}'
            ORDER BY timestamp
        """, conn)
        
        for idx, row in frames.iterrows():
            if row['ambe_hex']:
                hex_data = row['ambe_hex']
                all_frames_with_context.append({
                    'ambe_hex': hex_data,
                    'c_mi': c_mi,
                    'timestamp': row['timestamp'],
                    'superframe_id': row['superframe_id'],
                    'position': idx
                })
                
                # Analyze by prefix (first byte)
                prefix = hex_data[:2]
                frame_by_prefix[prefix].append(hex_data)
                prefix_patterns[prefix] += 1
    
    print(f"Total AMBE frames collected: {len(all_frames_with_context)}")
    
    # Test specific claims
    print(f"\n=== TESTING SPECIFIC CLAIMS ===")
    
    # CLAIM 1: 0x02 prefix indicates beeps
    print("\nCLAIM 1: 0x02 prefix indicates beeps")
    beep_frames = frame_by_prefix.get('02', [])
    print(f"Found {len(beep_frames)} frames with 0x02 prefix")
    if beep_frames:
        # Analyze bit patterns
        unique_beeps = Counter(beep_frames)
        print(f"Unique 0x02 patterns: {len(unique_beeps)}")
        print("Most common 0x02 patterns:")
        for pattern, count in unique_beeps.most_common(5):
            print(f"  {pattern}: {count} times")
        
        # Check if they appear at end of calls
        beep_positions = [f['position'] for f in all_frames_with_context 
                         if f['ambe_hex'].startswith('02')]
        print(f"Average position of 0x02 frames: {np.mean(beep_positions):.1f}")
    
    # CLAIM 2: 0x00 prefix indicates silence
    print("\nCLAIM 2: 0x00 prefix indicates silence")
    silence_frames = frame_by_prefix.get('00', [])
    print(f"Found {len(silence_frames)} frames with 0x00 prefix")
    if silence_frames:
        unique_silence = Counter(silence_frames)
        print(f"Unique 0x00 patterns: {len(unique_silence)}")
        print("Most common 0x00 patterns:")
        for pattern, count in unique_silence.most_common(5):
            print(f"  {pattern}: {count} times")
    
    # CLAIM 3: Prefix is sufficient for frame type
    print("\nCLAIM 3: Prefix is sufficient for frame type identification")
    
    # For each prefix, calculate entropy of remaining bytes
    prefix_entropy = {}
    for prefix, frames in frame_by_prefix.items():
        if len(frames) < 5:  # Skip rare prefixes
            continue
        
        # Get remaining bytes after prefix
        remaining_parts = [f[2:] for f in frames]
        unique_remaining = len(set(remaining_parts))
        
        # Calculate entropy
        entropy = unique_remaining / len(frames)
        prefix_entropy[prefix] = {
            'total_frames': len(frames),
            'unique_patterns': unique_remaining,
            'entropy': entropy
        }
    
    print("\nPrefix reliability analysis (lower entropy = more reliable):")
    sorted_prefixes = sorted(prefix_entropy.items(), 
                           key=lambda x: x[1]['entropy'])
    
    for prefix, stats in sorted_prefixes[:10]:
        print(f"  0x{prefix}: {stats['total_frames']} frames, "
              f"{stats['unique_patterns']} unique, "
              f"entropy: {stats['entropy']:.3f}")
    
    # CLAIM 4: AMBE decoder validation
    print("\n=== AMBE DECODER VALIDATION SIMULATION ===")
    
    # Simulate decoder validation based on known AMBE properties
    valid_count = 0
    invalid_count = 0
    validation_results = defaultdict(int)
    
    for frame_data in all_frames_with_context[:500]:  # Test 500 frames
        frame_hex = frame_data['ambe_hex']
        
        # AMBE+2 frames should be 49 bits (rounded to 8 bytes)
        if len(frame_hex) == 16:  # 8 bytes in hex
            frame_bytes = bytes.fromhex(frame_hex)
            
            # Check for known patterns
            if frame_hex.startswith('00'):
                validation_results['silence_candidate'] += 1
                # Silence frames often have low bit density
                bit_count = bin(int(frame_hex, 16)).count('1')
                if bit_count < 20:
                    validation_results['validated_silence'] += 1
                    valid_count += 1
                else:
                    invalid_count += 1
                    
            elif frame_hex.startswith('02'):
                validation_results['beep_candidate'] += 1
                # Beep frames often have specific patterns
                if frame_hex[2:4] in ['5A', 'BC', '8A', 'E0', 'FE', '46', '9C']:
                    validation_results['validated_beep'] += 1
                    valid_count += 1
                else:
                    invalid_count += 1
                    
            else:
                # General AMBE frame validation
                # Check for reasonable bit distribution (not all 0s or 1s)
                bit_count = bin(int(frame_hex, 16)).count('1')
                if 15 <= bit_count <= 49:  # Reasonable range
                    validation_results['validated_speech'] += 1
                    valid_count += 1
                else:
                    validation_results['invalid_pattern'] += 1
                    invalid_count += 1
        else:
            validation_results['invalid_length'] += 1
            invalid_count += 1
    
    print(f"Validation results on 500 frames:")
    print(f"Valid frames: {valid_count} ({valid_count/500*100:.1f}%)")
    print(f"Invalid frames: {invalid_count} ({invalid_count/500*100:.1f}%)")
    
    print("\nDetailed validation breakdown:")
    for result_type, count in validation_results.items():
        print(f"  {result_type}: {count}")
    
    # Pattern repetition analysis for call end detection
    print("\n=== PATTERN REPETITION ANALYSIS ===")
    
    # Look for consecutive repeated frames
    consecutive_repeats = defaultdict(int)
    
    for i in range(len(all_frames_with_context) - 2):
        frame1 = all_frames_with_context[i]['ambe_hex']
        frame2 = all_frames_with_context[i + 1]['ambe_hex']
        frame3 = all_frames_with_context[i + 2]['ambe_hex']
        
        if frame1 == frame2 == frame3:
            consecutive_repeats[frame1] += 1
    
    print("Frames repeated 3+ times consecutively:")
    for frame, count in sorted(consecutive_repeats.items(), 
                              key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {frame}: {count} occurrences")
    
    conn.close()
    
    return all_frames_with_context, frame_by_prefix, prefix_entropy

# Statistical proof of claims
def statistical_proof_analysis(frame_by_prefix, prefix_entropy):
    """Provide statistical proof/disproof of claims"""
    print("\n=== STATISTICAL PROOF ANALYSIS ===")
    
    # For claimed patterns (0x00, 0x02), calculate confidence intervals
    for prefix in ['00', '02']:
        if prefix not in frame_by_prefix:
            print(f"\nNo frames found with prefix 0x{prefix}")
            continue
            
        frames = frame_by_prefix[prefix]
        print(f"\nStatistical analysis for prefix 0x{prefix}:")
        print(f"Sample size: {len(frames)}")
        
        # Calculate pattern consistency
        pattern_counts = Counter(frames)
        most_common = pattern_counts.most_common(1)[0]
        
        consistency = most_common[1] / len(frames)
        print(f"Most common pattern: {most_common[0]}")
        print(f"Consistency: {consistency:.1%}")
        
        # Calculate confidence interval
        import scipy.stats as stats
        confidence_level = 0.95
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        margin_error = z_score * np.sqrt((consistency * (1 - consistency)) / len(frames))
        
        print(f"{confidence_level*100}% Confidence Interval: "
              f"[{consistency - margin_error:.1%}, {consistency + margin_error:.1%}]")
        
        # Verdict
        if consistency > 0.7:
            print(f"VERDICT: Strong evidence that 0x{prefix} indicates specific frame type")
        elif consistency > 0.5:
            print(f"VERDICT: Moderate evidence that 0x{prefix} indicates specific frame type")
        else:
            print(f"VERDICT: Weak evidence that 0x{prefix} indicates specific frame type")

# Main execution
db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_025824.db"
frames, frame_by_prefix, prefix_entropy = analyze_ambe_patterns_thoroughly(db_path)
statistical_proof_analysis(frame_by_prefix, prefix_entropy)