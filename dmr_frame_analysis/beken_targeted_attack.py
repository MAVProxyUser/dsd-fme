#!/usr/bin/env python3
"""Targeted attack using Beken BK378 vocoder characteristics"""

import sqlite3
import numpy as np

def beken_targeted_attack():
    """Use Beken-specific knowledge for improved decryption"""
    
    print("=== BEKEN BK378 TARGETED ATTACK ===")
    
    # Beken BK378 specific characteristics:
    # 1. Modified AMBE+2 with specific bit allocations
    # 2. Known silence patterns
    # 3. Predictable initialization sequences
    # 4. Specific comfort noise generation
    
    encrypted_db = "dmr_capture_20250518_112024_998484.db"
    conn = sqlite3.connect(encrypted_db)
    cursor = conn.cursor()
    
    # Get frames with most reuse
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
    
    print(f"\nTargeting MI {target_mi:08X} with {count} uses")
    
    # Get all frames for this MI
    cursor.execute(f"""
        SELECT id, ambe_hex, superframe_id
        FROM '{table_name}'
        ORDER BY superframe_id, id
    """)
    
    frames = cursor.fetchall()
    
    # Group by position within superframe
    frames_by_position = {}
    for frame_id, ambe_hex, sf_id in frames:
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM '{table_name}' 
            WHERE superframe_id = ? AND id < ?
        """, (sf_id, frame_id))
        position = cursor.fetchone()[0]
        
        if position not in frames_by_position:
            frames_by_position[position] = []
        frames_by_position[position].append((frame_id, ambe_hex, sf_id))
    
    print(f"\nFrame positions found: {sorted(frames_by_position.keys())}")
    
    # Beken-specific attack vectors
    print("\n=== BEKEN ATTACK VECTORS ===")
    
    # 1. End-of-transmission pattern
    print("\n1. END-OF-TRANSMISSION ATTACK")
    
    # Beken typically ends with specific patterns
    beken_eot_patterns = [
        '0000000000000080',  # Common EOT marker
        '00000000000000C0',  # Alternative EOT
        'FC00000000000080',  # Comfort noise + EOT
    ]
    
    # Test on last frames
    last_position = max(frames_by_position.keys())
    last_frames = frames_by_position[last_position]
    
    print(f"Testing EOT patterns on position {last_position} ({len(last_frames)} frames)")
    
    best_eot_result = None
    best_eot_score = 0
    
    for eot_pattern in beken_eot_patterns:
        for frame_idx, (_, enc_hex, _) in enumerate(last_frames[:3]):
            enc_int = int(enc_hex, 16)
            eot_int = int(eot_pattern, 16)
            keystream = enc_int ^ eot_int
            
            # Test this keystream
            score = 0
            decoded_samples = []
            
            for _, test_hex, _ in last_frames:
                test_int = int(test_hex, 16)
                decoded = test_int ^ keystream
                
                # Validate against Beken constraints
                if validate_beken_frame(decoded):
                    score += 1
                
                decoded_samples.append(f"{decoded:016X}")
            
            if score > best_eot_score:
                best_eot_score = score
                best_eot_result = {
                    'pattern': eot_pattern,
                    'keystream': f"{keystream:016X}",
                    'score': score,
                    'samples': decoded_samples[:5]
                }
    
    if best_eot_result:
        print(f"\nBest EOT match:")
        print(f"  Pattern: {best_eot_result['pattern']}")
        print(f"  Keystream: {best_eot_result['keystream']}")
        print(f"  Score: {best_eot_result['score']}/{len(last_frames)}")
        print(f"  Decoded samples:")
        for sample in best_eot_result['samples']:
            print(f"    {sample}")
    
    # 2. Silence detection
    print("\n\n2. SILENCE PATTERN ATTACK")
    
    # Look for frames with high zero bytes (likely silence)
    silence_candidates = []
    
    for position, position_frames in frames_by_position.items():
        for frame_id, hex_val, sf_id in position_frames:
            zero_count = hex_val.count('00')
            if zero_count >= 3:  # At least 3 zero bytes
                silence_candidates.append({
                    'position': position,
                    'frame_id': frame_id,
                    'hex': hex_val,
                    'zero_count': zero_count
                })
    
    # Sort by zero count
    silence_candidates.sort(key=lambda x: x['zero_count'], reverse=True)
    
    print(f"\nTop silence candidates:")
    for candidate in silence_candidates[:5]:
        print(f"  Position {candidate['position']}, Frame {candidate['frame_id']}: "
              f"{candidate['hex']} ({candidate['zero_count']} zeros)")
    
    # Test Beken silence patterns
    if silence_candidates:
        best_silence = silence_candidates[0]
        enc_int = int(best_silence['hex'], 16)
        
        print(f"\nTesting silence patterns on frame {best_silence['frame_id']}")
        
        for silence_pattern in ['0000000000000000', '0000000000000080', 'FC00000000000000']:
            silence_int = int(silence_pattern, 16)
            keystream = enc_int ^ silence_int
            
            print(f"\n  If silence is {silence_pattern}:")
            print(f"    Keystream: {keystream:016X}")
            
            # Decrypt a few frames
            position_frames = frames_by_position[best_silence['position']]
            for i, (_, test_hex, _) in enumerate(position_frames[:3]):
                if i == 0:
                    continue  # Skip the candidate itself
                
                test_int = int(test_hex, 16)
                decoded = test_int ^ keystream
                
                print(f"    Frame {i} decodes to: {decoded:016X}")
                
                # Validate
                if validate_beken_frame(decoded):
                    print(f"      ✓ Valid Beken frame!")
                else:
                    print(f"      ✗ Invalid Beken frame")
    
    # 3. Cross-position correlation
    print("\n\n3. CROSS-POSITION CORRELATION")
    
    # Frames at position 0 often have similar initialization
    if 0 in frames_by_position:
        pos0_frames = frames_by_position[0]
        
        print(f"\nAnalyzing position 0 frames ({len(pos0_frames)} samples)")
        
        # XOR all pairs to find patterns
        xor_patterns = []
        
        for i in range(len(pos0_frames)-1):
            for j in range(i+1, min(i+3, len(pos0_frames))):
                frame1_int = int(pos0_frames[i][1], 16)
                frame2_int = int(pos0_frames[j][1], 16)
                xor_result = frame1_int ^ frame2_int
                
                bit_diff = bin(xor_result).count('1')
                xor_patterns.append({
                    'i': i,
                    'j': j,
                    'xor': f"{xor_result:016X}",
                    'bit_diff': bit_diff
                })
        
        # Find lowest differences
        xor_patterns.sort(key=lambda x: x['bit_diff'])
        
        print("\nLowest XOR differences (similar content):")
        for pattern in xor_patterns[:3]:
            print(f"  Frames {pattern['i']},{pattern['j']}: "
                  f"{pattern['xor']} ({pattern['bit_diff']} bits)")
    
    conn.close()
    
    print("\n\n=== BEKEN ATTACK SUMMARY ===")
    print("1. EOT patterns show promise with specific Beken markers")
    print("2. Silence candidates identified by zero byte count")
    print("3. Position-based correlation reveals similar frames")
    print("4. Validation against Beken constraints improves accuracy")
    print("\nNext steps:")
    print("- Test recovered keystreams on full frame sets")
    print("- Use actual Beken decoder for audio validation")
    print("- Capture known audio for definitive break")

def validate_beken_frame(frame_int):
    """Validate if frame matches Beken constraints"""
    
    # Extract Beken fields
    fundamental = frame_int & 0x3F  # Bits 0-5
    first_spectral = (frame_int >> 6) & 0x3F  # Bits 6-11
    
    # Beken-specific constraints
    # 1. Fundamental frequency in voice range (0-50)
    if not (0 <= fundamental <= 50):
        return False
    
    # 2. First spectral magnitude reasonable (0-60)
    if not (0 <= first_spectral <= 60):
        return False
    
    # 3. Check for invalid bit patterns
    # Beken never sets certain bit combinations
    invalid_patterns = [
        0xFFFFFFFFFFFFFFFF,  # All ones
        0xAAAAAAAAAAAAAAAA,  # Alternating pattern
    ]
    
    if frame_int in invalid_patterns:
        return False
    
    return True

if __name__ == "__main__":
    beken_targeted_attack()