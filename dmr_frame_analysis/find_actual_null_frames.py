#!/usr/bin/env python3
"""
Find actual null/silence frames in our captures by analyzing patterns
"""
import sqlite3
import numpy as np
from collections import Counter

def analyze_frame_entropy(ambe_hex):
    """Calculate entropy and pattern metrics for a frame"""
    # Convert hex to bytes
    try:
        ambe_bytes = bytes.fromhex(ambe_hex)
    except:
        return None
    
    # Calculate byte frequency
    byte_counts = Counter(ambe_bytes)
    unique_bytes = len(byte_counts)
    
    # Calculate entropy
    total_bytes = len(ambe_bytes)
    entropy = 0
    for count in byte_counts.values():
        p = count / total_bytes
        if p > 0:
            entropy -= p * np.log2(p)
    
    # Check for repeated patterns
    repeated_patterns = []
    for i in range(1, len(ambe_bytes) // 2):
        pattern = ambe_bytes[:i]
        if ambe_bytes == pattern * (len(ambe_bytes) // i):
            repeated_patterns.append(pattern.hex())
    
    return {
        'entropy': entropy,
        'unique_bytes': unique_bytes,
        'most_common': byte_counts.most_common(3),
        'repeated_patterns': repeated_patterns
    }

def find_null_frames(db_path):
    """Find frames that might be null/silence frames"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all AMBE frames
    cur.execute("""
        SELECT DISTINCT ambe_hex_frame1, ambe_hex_frame2, ambe_hex_frame3
        FROM dmr_frames
        WHERE ambe_hex_frame1 IS NOT NULL
    """)
    
    null_candidates = []
    frame_count = 0
    
    for row in cur.fetchall():
        for i, ambe_hex in enumerate(row):
            if ambe_hex:
                frame_count += 1
                metrics = analyze_frame_entropy(ambe_hex)
                
                if metrics:
                    # Look for low entropy or repeated patterns
                    if metrics['entropy'] < 2.0 or metrics['unique_bytes'] < 4 or metrics['repeated_patterns']:
                        null_candidates.append({
                            'frame': ambe_hex,
                            'position': i + 1,
                            'metrics': metrics
                        })
    
    conn.close()
    
    print(f"Analyzed {frame_count} AMBE frames")
    print(f"Found {len(null_candidates)} potential null/silence frames")
    
    # Group by pattern
    patterns = {}
    for candidate in null_candidates:
        frame = candidate['frame']
        if frame not in patterns:
            patterns[frame] = []
        patterns[frame].append(candidate)
    
    print(f"\nUnique patterns: {len(patterns)}")
    
    # Show most common patterns
    sorted_patterns = sorted(patterns.items(), key=lambda x: len(x[1]), reverse=True)
    
    for i, (pattern, instances) in enumerate(sorted_patterns[:10]):
        print(f"\nPattern {i+1}: {pattern}")
        print(f"Occurrences: {len(instances)}")
        print(f"Metrics: {instances[0]['metrics']}")
        
        # Convert to binary for analysis
        try:
            bytes_data = bytes.fromhex(pattern)
            bin_str = ''.join(format(b, '08b') for b in bytes_data)
            print(f"Binary: {bin_str[:32]}... (first 32 bits)")
        except:
            pass

if __name__ == "__main__":
    import glob
    
    # Check all databases
    db_files = glob.glob("/home/ubuntu/dsd-fme_sqlite/dmr_attack_analysis/*.db")
    
    for db_file in db_files:
        print(f"\n=== Analyzing {db_file} ===")
        find_null_frames(db_file)