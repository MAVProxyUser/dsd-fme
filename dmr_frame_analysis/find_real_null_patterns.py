#!/usr/bin/env python3
"""Find actual null/silence patterns in real DMR captures"""
import sqlite3
import numpy as np
from collections import Counter
import matplotlib.pyplot as plt

def analyze_real_frames():
    """Analyze frames from actual DMR capture to find null patterns"""
    
    # Connect to both databases
    databases = [
        ('dmr_capture_20250517_204818.db', 'Unencrypted'),
        ('dmr_capture_20250517_205116.db', 'Encrypted')
    ]
    
    all_patterns = {}
    
    for db_file, db_type in databases:
        print(f"\n=== Analyzing {db_type} Database: {db_file} ===")
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE '%_S0'
            """)
            
            tables = cursor.fetchall()
            print(f"Found {len(tables)} AMBE tables")
            
            for table_name, in tables:
                print(f"\nAnalyzing table: {table_name}")
                
                # Get all frames
                cursor.execute(f"""
                    SELECT ambe_hex, COUNT(*) as count 
                    FROM {table_name} 
                    GROUP BY ambe_hex 
                    ORDER BY count DESC
                """)
                
                frames = cursor.fetchall()
                
                # Look for patterns
                pattern_stats = []
                
                for ambe_hex, count in frames[:20]:  # Top 20 patterns
                    # Analyze the pattern
                    ambe_bytes = bytes.fromhex(ambe_hex)
                    unique_bytes = len(set(ambe_bytes))
                    
                    # Check for specific characteristics
                    is_all_same = unique_bytes == 1
                    is_low_entropy = unique_bytes <= 2
                    is_zeros = ambe_hex == "0000000000000000"
                    byte_values = list(set(ambe_bytes))
                    
                    pattern_info = {
                        'hex': ambe_hex,
                        'count': count,
                        'unique_bytes': unique_bytes,
                        'is_all_same': is_all_same,
                        'is_low_entropy': is_low_entropy,
                        'is_zeros': is_zeros,
                        'byte_values': byte_values,
                        'table': table_name
                    }
                    
                    pattern_stats.append(pattern_info)
                    
                    # Track globally
                    if ambe_hex not in all_patterns:
                        all_patterns[ambe_hex] = []
                    all_patterns[ambe_hex].append((db_type, table_name, count))
                
                # Print findings
                print(f"\nLow entropy patterns (potential nulls):")
                for info in pattern_stats:
                    if info['is_low_entropy']:
                        print(f"  {info['hex']}: {info['count']} times, "
                              f"{info['unique_bytes']} unique bytes {info['byte_values']}")
                
                # Look for actual silence
                cursor.execute(f"""
                    SELECT ambe_hex, id 
                    FROM {table_name} 
                    WHERE ambe_hex = '0000000000000000'
                    LIMIT 5
                """)
                
                silence_frames = cursor.fetchall()
                if silence_frames:
                    print(f"\nFound {len(silence_frames)} all-zero frames (definite silence)")
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Error analyzing {db_file}: {e}")
    
    # Summary of findings
    print("\n=== Pattern Summary Across All Captures ===")
    
    # Sort by frequency
    sorted_patterns = sorted(all_patterns.items(), 
                           key=lambda x: sum(count for _, _, count in x[1]), 
                           reverse=True)
    
    print("\nMost common patterns:")
    null_candidates = []
    
    for pattern, occurrences in sorted_patterns[:20]:
        total_count = sum(count for _, _, count in occurrences)
        ambe_bytes = bytes.fromhex(pattern)
        unique_bytes = len(set(ambe_bytes))
        
        print(f"\n{pattern}:")
        print(f"  Total occurrences: {total_count}")
        print(f"  Unique bytes: {unique_bytes}")
        print(f"  Byte values: {list(set(ambe_bytes))}")
        print(f"  Found in: {[f'{db_type}/{table}' for db_type, table, _ in occurrences]}")
        
        # Identify likely null frames
        if unique_bytes <= 2 or pattern == "0000000000000000":
            null_candidates.append((pattern, total_count, unique_bytes))
            print(f"  ** LIKELY NULL/SILENCE FRAME **")
    
    return null_candidates

def check_dmr_specs():
    """Check what the DMR spec says about null frames"""
    print("\n=== DMR Specification Information ===")
    print("\nAccording to ETSI TS 102 361 (DMR Standard):")
    print("1. Null frames are used for silence suppression")
    print("2. The vocoder (AMBE+2) can produce comfort noise")
    print("3. Specific null patterns depend on manufacturer implementation")
    print("4. Common silence patterns include all-zeros")
    print("\nNote: The actual null patterns I suggested earlier were")
    print("speculative. Real patterns should be identified from")
    print("actual captures and manufacturer documentation.")

def create_pattern_visualization(null_candidates):
    """Visualize the discovered null patterns"""
    if not null_candidates:
        print("\nNo null candidates found")
        return
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    patterns = []
    labels = []
    
    for pattern, count, unique in null_candidates[:10]:  # Top 10
        # Convert to byte array for visualization
        byte_vals = [b for b in bytes.fromhex(pattern)]
        patterns.append(byte_vals)
        labels.append(f"{pattern[:8]}... ({count} times, {unique} unique)")
    
    # Create heatmap
    patterns_array = np.array(patterns)
    im = ax.imshow(patterns_array, aspect='auto', cmap='viridis')
    
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel('Byte Position')
    ax.set_title('Discovered Null/Silence Patterns from Real DMR Capture')
    
    plt.colorbar(im, ax=ax, label='Byte Value')
    plt.tight_layout()
    plt.savefig('real_null_patterns.png', dpi=150)
    plt.close()
    
    print("\nCreated: real_null_patterns.png")

# Run analysis
null_candidates = analyze_real_frames()
check_dmr_specs()
create_pattern_visualization(null_candidates)

print("\n=== Conclusion ===")
print("The null patterns I mentioned earlier (0x13, 0xAC, etc.) were")
print("speculative and not based on actual DMR data.")
print("\nFrom our real captures, we should look for:")
print("1. Patterns that appear frequently")
print("2. Low entropy (few unique bytes)")
print("3. Patterns at silence boundaries")
print("4. Manufacturer-specific implementations")
print("\nAlways verify patterns against real data!")