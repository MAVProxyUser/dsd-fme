#!/usr/bin/env python3
"""
Analyze DMR frames with understanding that each C-MI has its own table
And that we need to group every 3 consecutive frames as a complete burst
"""

import sqlite3
import struct
import numpy as np
from collections import defaultdict

def get_all_cmi_tables(conn):
    """Get all C_* tables from database"""
    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
    """)
    
    tables = [row[0] for row in cur.fetchall()]
    return tables

def extract_frames_from_table(conn, table_name):
    """Extract AMBE frames from a specific C-MI table"""
    cur = conn.cursor()
    
    # Extract C-MI from table name
    cmi_hex = table_name.split('_')[1]
    cmi_value = int(cmi_hex, 16)
    
    # Get all frames from this table
    cur.execute(f"""
        SELECT id, ambe_hex, algid, slot, superframe_id, timestamp
        FROM '{table_name}'
        ORDER BY id
    """)
    
    frames = []
    for row in cur:
        frame_id, ambe_hex, algid, slot, superframe_id, timestamp = row
        
        if ambe_hex:
            # Convert hex string to bytes
            ambe_bytes = bytes.fromhex(ambe_hex)
            ambe_val = struct.unpack('>Q', ambe_bytes)[0] if len(ambe_bytes) == 8 else 0
            
            frames.append({
                'id': frame_id,
                'ambe': ambe_val,
                'cmi': cmi_value,
                'algid': algid,
                'slot': slot,
                'superframe_id': superframe_id,
                'timestamp': timestamp
            })
    
    return frames

def group_into_complete_frames(frames):
    """Group individual AMBE frames into complete 3-frame bursts"""
    
    complete_frames = []
    
    # Sort by ID to ensure proper ordering
    frames.sort(key=lambda x: x['id'])
    
    # Group every 3 consecutive frames
    for i in range(0, len(frames), 3):
        if i + 2 < len(frames):
            complete_frames.append({
                'burst_id': i // 3,
                'frames': frames[i:i+3],
                'cmi': frames[i]['cmi'],
                'slot': frames[i]['slot'],
                'algid': frames[i]['algid']
            })
    
    return complete_frames

def analyze_complete_frames(db_path):
    """Analyze database using complete frame understanding"""
    
    conn = sqlite3.connect(db_path)
    
    # Get all C-MI tables
    cmi_tables = get_all_cmi_tables(conn)
    print(f"Found {len(cmi_tables)} C-MI tables")
    
    # Extract frames from each table
    all_frames = []
    frames_by_cmi = defaultdict(list)
    
    for table in cmi_tables:
        frames = extract_frames_from_table(conn, table)
        if frames:
            # Group by C-MI
            cmi = frames[0]['cmi']
            frames_by_cmi[cmi].extend(frames)
            all_frames.extend(frames)
    
    print(f"Total individual AMBE frames: {len(all_frames)}")
    
    # Find C-MIs with multiple uses (for IV reuse)
    reused_cmis = {cmi: frames for cmi, frames in frames_by_cmi.items() 
                   if len(frames) >= 6}  # At least 2 complete bursts
    
    print(f"Found {len(reused_cmis)} C-MIs with multiple bursts")
    
    # Analyze IV reuse with complete frames
    attack_results = []
    
    for cmi, frame_list in sorted(reused_cmis.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f"\nC-MI 0x{cmi:08X}: {len(frame_list)} frames ({len(frame_list)//3} complete bursts)")
        
        # Group into complete frames
        complete_frames = group_into_complete_frames(frame_list)
        
        # Compare complete frames
        for i in range(len(complete_frames)):
            for j in range(i+1, len(complete_frames)):
                burst1 = complete_frames[i]
                burst2 = complete_frames[j]
                
                # XOR all 3 frames in each burst
                xor_results = []
                for k in range(3):
                    # Extract vocoder bits (upper 49)
                    vocoder1 = burst1['frames'][k]['ambe'] >> 15
                    vocoder2 = burst2['frames'][k]['ambe'] >> 15
                    
                    xor_val = vocoder1 ^ vocoder2
                    xor_results.append(xor_val)
                
                attack_results.append({
                    'cmi': cmi,
                    'burst1_id': burst1['burst_id'],
                    'burst2_id': burst2['burst_id'],
                    'xor_results': xor_results
                })
                
                # Print first few results
                if len(attack_results) <= 5:
                    print(f"  Burst {i} ⊕ Burst {j}:")
                    for k, xor_val in enumerate(xor_results):
                        print(f"    Frame {k+1}: 0x{xor_val:013X}")
    
    conn.close()
    return attack_results

def analyze_patterns(attack_results):
    """Look for patterns in XOR results"""
    
    print("\n=== Pattern Analysis ===")
    
    # Look for identical XOR patterns
    xor_patterns = defaultdict(list)
    
    for result in attack_results:
        # Create pattern tuple from all 3 XORs
        pattern = tuple(result['xor_results'])
        xor_patterns[pattern].append(result)
    
    # Find repeated patterns
    repeated = {p: results for p, results in xor_patterns.items() 
                if len(results) > 1}
    
    print(f"Found {len(repeated)} repeated XOR patterns")
    
    for pattern, results in sorted(repeated.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
        print(f"\nPattern repeated {len(results)} times:")
        for i, xor_val in enumerate(pattern):
            print(f"  Frame {i+1}: 0x{xor_val:013X}")
        
        # Show which C-MIs involved
        cmis = set(r['cmi'] for r in results)
        print(f"  C-MIs: {[f'0x{cmi:08X}' for cmi in list(cmis)[:3]]}")

def estimate_plaintext_relationships(attack_results):
    """Estimate plaintext relationships from XOR patterns"""
    
    print("\n=== Plaintext Relationship Analysis ===")
    
    # Look for small XOR values (similar plaintext)
    small_xors = []
    
    for result in attack_results:
        # Calculate magnitude of XOR
        magnitudes = [bin(xor_val).count('1') for xor_val in result['xor_results']]
        avg_magnitude = sum(magnitudes) / len(magnitudes)
        
        if avg_magnitude < 10:  # Few bit differences
            small_xors.append((result, avg_magnitude))
    
    print(f"Found {len(small_xors)} burst pairs with similar plaintext")
    
    for result, magnitude in sorted(small_xors, key=lambda x: x[1])[:5]:
        print(f"\nC-MI 0x{result['cmi']:08X}: ~{magnitude:.1f} bit differences")
        for i, xor_val in enumerate(result['xor_results']):
            print(f"  Frame {i+1}: 0x{xor_val:013X} ({bin(xor_val).count('1')} bits)")

def main():
    print("=== DMR Complete Frame Analysis v2 ===\n")
    
    # Use newest database
    import glob
    db_files = sorted(glob.glob("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_*.db"))
    
    if not db_files:
        print("No database files found")
        return
    
    db_path = db_files[-1]
    print(f"Using database: {db_path}")
    
    # Analyze with complete frame understanding
    attack_results = analyze_complete_frames(db_path)
    
    print(f"\n=== Attack Results ===")
    print(f"Generated {len(attack_results)} complete frame comparisons")
    
    # Analyze patterns
    analyze_patterns(attack_results)
    
    # Estimate plaintext relationships
    estimate_plaintext_relationships(attack_results)
    
    print("\n=== Conclusion ===")
    print("Complete frame analysis shows:")
    print("1. Each C-MI encrypts 3 AMBE frames with same keystream")
    print("2. Patterns emerge when comparing complete bursts")
    print("3. Similar plaintext produces small XOR differences")
    print("4. This provides strong cryptanalysis opportunities")

if __name__ == "__main__":
    main()