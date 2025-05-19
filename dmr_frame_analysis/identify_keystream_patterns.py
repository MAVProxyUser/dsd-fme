#!/usr/bin/env python3
"""Identify potential silence and predictable patterns to recover keystream"""

import sqlite3
from collections import defaultdict, Counter

def identify_keystream_patterns():
    encrypted_db = "dmr_capture_20250518_112024_998484.db"
    conn = sqlite3.connect(encrypted_db)
    cursor = conn.cursor()
    
    print("=== IDENTIFYING PREDICTABLE FRAMES FOR KEYSTREAM RECOVERY ===")
    
    # Get C-MI with most frames
    cursor.execute("""
        SELECT c_mi, COUNT(*) as count
        FROM superframes
        WHERE c_mi IS NOT NULL AND c_mi != 0
        GROUP BY c_mi
        ORDER BY count DESC
        LIMIT 1
    """)
    
    target_mi, count = cursor.fetchone()
    table_name = f"C_{target_mi:08X}_S0"
    
    print(f"\nAnalyzing MI {target_mi:08X} with {count} transmissions")
    
    # Get all frames for this MI
    cursor.execute(f"SELECT id, ambe_hex, superframe_id FROM '{table_name}' ORDER BY id")
    frames = cursor.fetchall()
    
    print(f"Total AMBE frames: {len(frames)}")
    
    # Group frames by position within superframe
    frames_by_position = defaultdict(list)
    
    for frame_id, ambe_hex, sf_id in frames:
        # Get position within superframe
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM '{table_name}' 
            WHERE superframe_id = ? AND id < ?
        """, (sf_id, frame_id))
        position = cursor.fetchone()[0]
        frames_by_position[position].append((frame_id, ambe_hex, sf_id))
    
    print(f"\nFrames grouped by position:")
    for pos in sorted(frames_by_position.keys())[:5]:
        print(f"  Position {pos}: {len(frames_by_position[pos])} frames")
    
    # Analyze frames at each position
    print("\n=== ANALYZING FRAME PATTERNS BY POSITION ===")
    
    potential_silence = []
    
    for position in sorted(frames_by_position.keys())[:3]:  # First 3 positions
        frames_at_pos = frames_by_position[position]
        
        if len(frames_at_pos) < 2:
            continue
            
        print(f"\nPosition {position} ({len(frames_at_pos)} frames):")
        
        # XOR all pairs at this position
        xor_results = []
        
        for i in range(len(frames_at_pos)-1):
            for j in range(i+1, min(i+5, len(frames_at_pos))):
                frame1 = int(frames_at_pos[i][1], 16)
                frame2 = int(frames_at_pos[j][1], 16)
                xor_result = frame1 ^ frame2
                
                bit_diff = bin(xor_result).count('1')
                xor_results.append({
                    'i': i,
                    'j': j,
                    'xor': xor_result,
                    'bit_diff': bit_diff,
                    'hex': f"{xor_result:016X}"
                })
        
        # Statistics
        bit_diffs = [r['bit_diff'] for r in xor_results]
        avg_diff = sum(bit_diffs) / len(bit_diffs) if bit_diffs else 0
        min_diff = min(bit_diffs) if bit_diffs else 0
        
        print(f"  Average bit difference: {avg_diff:.1f}")
        print(f"  Minimum bit difference: {min_diff}")
        
        # Show examples
        if xor_results:
            sorted_results = sorted(xor_results, key=lambda x: x['bit_diff'])
            print(f"  Most similar pairs:")
            for r in sorted_results[:3]:
                print(f"    Frames {r['i']},{r['j']}: {r['hex']} ({r['bit_diff']} bits)")
        
        # If very low bit differences, might be silence or pattern
        if min_diff < 10:
            potential_silence.append({
                'position': position,
                'min_diff': min_diff,
                'examples': frames_at_pos[:3]
            })
    
    # Check for AMBE silence patterns
    print("\n=== POTENTIAL SILENCE/PATTERN FRAMES ===")
    
    if potential_silence:
        for item in potential_silence:
            print(f"\nPosition {item['position']} (min diff: {item['min_diff']}):")
            for i, (fid, hex_val, sfid) in enumerate(item['examples'][:3]):
                print(f"  Example {i}: {hex_val}")
    
    # Common AMBE silence patterns
    silence_candidates = [
        '0000000000000000',  # Complete silence
        '0000000000000080',  # Silence with flag
        '8000000000000000',  # Alternative silence
    ]
    
    # Try known patterns against encrypted frames
    print("\n=== ATTEMPTING KNOWN PLAINTEXT ATTACK ===")
    
    # Take first frame from each position
    for position in sorted(frames_by_position.keys())[:3]:
        if not frames_by_position[position]:
            continue
            
        encrypted_hex = frames_by_position[position][0][1]
        encrypted = int(encrypted_hex, 16)
        
        print(f"\nPosition {position} frame: {encrypted_hex}")
        
        for silence_pattern in silence_candidates:
            plaintext = int(silence_pattern, 16)
            keystream = encrypted ^ plaintext
            
            print(f"  If plaintext is {silence_pattern}:")
            print(f"    Keystream would be: {keystream:016X}")
            
            # Test this keystream on other frames at same position
            if len(frames_by_position[position]) > 1:
                next_encrypted = int(frames_by_position[position][1][1], 16)
                predicted_plain = next_encrypted ^ keystream
                print(f"    Next frame would decrypt to: {predicted_plain:016X}")
    
    # Statistical analysis of byte patterns
    print("\n=== BYTE FREQUENCY ANALYSIS ===")
    
    byte_freq = Counter()
    
    for _, hex_val, _ in frames[:100]:  # Sample first 100
        for i in range(0, 16, 2):
            byte = hex_val[i:i+2]
            byte_freq[byte] += 1
    
    print("Most common encrypted bytes:")
    for byte, count in byte_freq.most_common(10):
        print(f"  0x{byte}: {count} times ({count/len(frames)*100:.1f}%)")
    
    conn.close()
    
    print("\n=== ATTACK SUMMARY ===")
    print("1. Frames at same position likely have similar content")
    print("2. Low bit differences suggest predictable patterns")
    print("3. First/last frames in transmission are best targets")
    print("4. With keystream from one frame, can decrypt all with same IV")
    print("5. Statistical analysis can reveal patterns over time")

if __name__ == "__main__":
    identify_keystream_patterns()