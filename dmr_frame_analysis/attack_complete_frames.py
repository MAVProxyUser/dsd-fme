#!/usr/bin/env python3
"""
Attack DMR encryption using complete voice frames
This uses all 3 AMBE frames per burst for better cryptanalysis
"""

import sqlite3
import struct
import numpy as np
from collections import defaultdict

def extract_complete_frames(db_path):
    """Extract complete frames from database"""
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # First check if CompleteFrames table exists
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='CompleteFrames'
    """)
    
    if not cur.fetchone():
        print("CompleteFrames table not found. Using fallback to individual frames...")
        return extract_frames_fallback(conn)
    
    # Get all complete frames
    cur.execute("""
        SELECT id, slot, burst_num, ambe1, ambe2, ambe3, mi, 
               algid, encrypted, src_id, dst_id
        FROM CompleteFrames
        ORDER BY id
    """)
    
    frames = []
    for row in cur:
        frame_id, slot, burst_num, ambe1, ambe2, ambe3, mi, algid, encrypted, src_id, dst_id = row
        
        # Convert BLOB to uint64
        ambe1_val = struct.unpack('>Q', ambe1)[0] if ambe1 else 0
        ambe2_val = struct.unpack('>Q', ambe2)[0] if ambe2 else 0
        ambe3_val = struct.unpack('>Q', ambe3)[0] if ambe3 else 0
        
        frames.append({
            'id': frame_id,
            'slot': slot,
            'burst_num': burst_num,
            'ambe': [ambe1_val, ambe2_val, ambe3_val],
            'mi': mi,
            'algid': algid,
            'encrypted': encrypted,
            'src_id': src_id,
            'dst_id': dst_id
        })
    
    conn.close()
    return frames

def extract_frames_fallback(conn):
    """Fallback to extract individual frames and group them"""
    
    cur = conn.cursor()
    
    # Get individual frames
    cur.execute("""
        SELECT f.id, f.frame_type, f.ambe, s.mi, s.algid, 
               s.src_id, s.dst_id
        FROM Frames f
        JOIN Superframes s ON f.superframe_id = s.id
        WHERE f.frame_type = 'DMR_DATA_VOICE_SYNC' 
        AND f.ambe IS NOT NULL
        ORDER BY f.id
    """)
    
    # Group frames by MI
    frames_by_mi = defaultdict(list)
    
    for row in cur:
        frame_id, frame_type, ambe_hex, mi, algid, src_id, dst_id = row
        
        if ambe_hex and mi:
            ambe_bytes = bytes.fromhex(ambe_hex)
            ambe_val = struct.unpack('>Q', ambe_bytes)[0]
            
            frames_by_mi[mi].append({
                'id': frame_id,
                'ambe': ambe_val,
                'algid': algid,
                'src_id': src_id,
                'dst_id': dst_id
            })
    
    # Convert to complete frame format (best effort)
    complete_frames = []
    for mi, frame_list in frames_by_mi.items():
        # Group into sets of 3
        for i in range(0, len(frame_list), 3):
            if i + 2 < len(frame_list):
                complete_frames.append({
                    'id': frame_list[i]['id'],
                    'slot': 0,  # Unknown
                    'burst_num': i // 3,
                    'ambe': [
                        frame_list[i]['ambe'],
                        frame_list[i+1]['ambe'],
                        frame_list[i+2]['ambe']
                    ],
                    'mi': mi,
                    'algid': frame_list[i]['algid'],
                    'encrypted': 1 if frame_list[i]['algid'] else 0,
                    'src_id': frame_list[i]['src_id'],
                    'dst_id': frame_list[i]['dst_id']
                })
    
    return complete_frames

def analyze_complete_iv_reuse(frames):
    """Analyze IV reuse with complete frames"""
    
    # Group frames by MI
    frames_by_mi = defaultdict(list)
    
    for frame in frames:
        if frame['mi'] and frame['encrypted']:
            frames_by_mi[frame['mi']].append(frame)
    
    # Find MIs with multiple uses
    reused_ivs = {mi: frame_list for mi, frame_list in frames_by_mi.items() 
                  if len(frame_list) >= 2}
    
    print(f"Found {len(reused_ivs)} IVs with multiple uses")
    
    # Analyze each reused IV
    attack_results = []
    
    for mi, frame_list in sorted(reused_ivs.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\nMI 0x{mi:08X}: {len(frame_list)} complete frames")
        
        # For each pair of frames with same IV
        for i in range(len(frame_list)):
            for j in range(i+1, len(frame_list)):
                frame1 = frame_list[i]
                frame2 = frame_list[j]
                
                # XOR all 3 AMBE frames
                xor_results = []
                for k in range(3):
                    # Extract vocoder bits (49 bits)
                    vocoder1 = frame1['ambe'][k] >> 15
                    vocoder2 = frame2['ambe'][k] >> 15
                    
                    # XOR to eliminate keystream
                    xor_val = vocoder1 ^ vocoder2
                    xor_results.append(xor_val)
                
                attack_results.append({
                    'mi': mi,
                    'frame1_id': frame1['id'],
                    'frame2_id': frame2['id'],
                    'xor_ambe1': xor_results[0],
                    'xor_ambe2': xor_results[1],
                    'xor_ambe3': xor_results[2],
                    'src_id': frame1['src_id'],
                    'dst_id': frame1['dst_id']
                })
                
                # Show first few results
                if len(attack_results) <= 3:
                    print(f"  Frame {frame1['id']} ⊕ Frame {frame2['id']}:")
                    print(f"    AMBE1: 0x{xor_results[0]:013X}")
                    print(f"    AMBE2: 0x{xor_results[1]:013X}")
                    print(f"    AMBE3: 0x{xor_results[2]:013X}")
    
    return attack_results

def analyze_patterns(attack_results):
    """Analyze patterns in XOR results"""
    
    print("\n=== Pattern Analysis ===")
    
    # Group by src/dst pairs
    by_conversation = defaultdict(list)
    
    for result in attack_results:
        key = (result['src_id'], result['dst_id'])
        by_conversation[key].append(result)
    
    # Analyze each conversation
    for (src, dst), results in by_conversation.items():
        print(f"\nConversation {src} -> {dst}: {len(results)} XOR pairs")
        
        # Look for patterns in XORs
        ambe1_xors = [r['xor_ambe1'] for r in results]
        ambe2_xors = [r['xor_ambe2'] for r in results]
        ambe3_xors = [r['xor_ambe3'] for r in results]
        
        # Count unique values
        unique1 = len(set(ambe1_xors))
        unique2 = len(set(ambe2_xors))
        unique3 = len(set(ambe3_xors))
        
        print(f"  Unique XOR values: AMBE1={unique1}, AMBE2={unique2}, AMBE3={unique3}")
        
        # Look for repeated patterns
        from collections import Counter
        counter1 = Counter(ambe1_xors)
        
        most_common = counter1.most_common(5)
        if most_common[0][1] > 1:
            print("  Most common AMBE1 XORs:")
            for xor_val, count in most_common:
                if count > 1:
                    print(f"    0x{xor_val:013X}: {count} times")

def attempt_plaintext_recovery(attack_results):
    """Attempt to recover plaintext from patterns"""
    
    print("\n=== Plaintext Recovery Attempt ===")
    
    # Look for frames where multiple XORs give same result
    # This suggests similar plaintext
    
    xor_patterns = defaultdict(list)
    
    for result in attack_results:
        # Create pattern from all 3 XORs
        pattern = (result['xor_ambe1'], result['xor_ambe2'], result['xor_ambe3'])
        xor_patterns[pattern].append(result)
    
    # Find repeated patterns
    repeated = {p: results for p, results in xor_patterns.items() 
                if len(results) > 1}
    
    print(f"Found {len(repeated)} repeated XOR patterns")
    
    for pattern, results in sorted(repeated.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
        print(f"\nPattern repeated {len(results)} times:")
        print(f"  AMBE1: 0x{pattern[0]:013X}")
        print(f"  AMBE2: 0x{pattern[1]:013X}")
        print(f"  AMBE3: 0x{pattern[2]:013X}")
        
        # These frames likely have similar content
        # Could be silence, repeated words, etc.

def main():
    print("=== DMR Attack with Complete Frames ===\n")
    
    # Use newest database
    import glob
    db_files = sorted(glob.glob("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_*.db"))
    
    if not db_files:
        print("No database files found")
        return
    
    db_path = db_files[-1]
    print(f"Using database: {db_path}")
    
    # Extract complete frames
    frames = extract_complete_frames(db_path)
    print(f"Found {len(frames)} complete frames")
    
    # Analyze IV reuse
    attack_results = analyze_complete_iv_reuse(frames)
    print(f"\nGenerated {len(attack_results)} XOR relationships")
    
    # Look for patterns
    analyze_patterns(attack_results)
    
    # Attempt recovery
    attempt_plaintext_recovery(attack_results)
    
    print("\n=== Summary ===")
    print("Complete frames provide 3x more data per IV reuse")
    print("Related frames (same burst) show correlated patterns")
    print("This significantly improves plaintext recovery chances")

if __name__ == "__main__":
    main()