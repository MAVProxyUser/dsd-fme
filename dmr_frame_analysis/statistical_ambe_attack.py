#!/usr/bin/env python3
"""Use statistical analysis of AMBE patterns to break encryption"""

import sqlite3
import numpy as np
from collections import defaultdict, Counter
import struct

def analyze_ambe_statistics():
    """Analyze statistical properties of AMBE frames"""
    
    # First, analyze cleartext AMBE to understand patterns
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn_clear = sqlite3.connect(cleartext_db)
    cursor_clear = conn_clear.cursor()
    
    print("=== CLEARTEXT AMBE ANALYSIS ===")
    
    # Get cleartext AMBE frames
    cursor_clear.execute("SELECT ambe_hex FROM U_00000000_S0 LIMIT 1000")
    cleartext_frames = [row[0] for row in cursor_clear.fetchall()]
    
    print(f"Analyzing {len(cleartext_frames)} cleartext AMBE frames")
    
    # Analyze bit patterns in cleartext
    cleartext_patterns = analyze_bit_patterns(cleartext_frames)
    
    print("\nCleartext AMBE characteristics:")
    print(f"  Average hamming weight: {cleartext_patterns['avg_hamming']:.1f}/64")
    print(f"  Bit position bias: {cleartext_patterns['bit_bias'][:10]}")
    print(f"  Common byte patterns: {cleartext_patterns['common_bytes'][:5]}")
    
    conn_clear.close()
    
    # Now analyze encrypted frames
    encrypted_db = "dmr_capture_20250518_112024_998484.db"
    conn_enc = sqlite3.connect(encrypted_db)
    cursor_enc = conn_enc.cursor()
    
    print("\n=== ENCRYPTED FRAME ANALYSIS ===")
    
    # Get frames with same MI (IV reuse)
    cursor_enc.execute("""
        SELECT c_mi, COUNT(*) as count
        FROM superframes
        WHERE c_mi IS NOT NULL AND c_mi != 0
        GROUP BY c_mi
        HAVING COUNT(*) >= 4
        ORDER BY count DESC
        LIMIT 1
    """)
    
    target_mi, count = cursor_enc.fetchone()
    table_name = f"C_{target_mi:08X}_S0"
    
    print(f"\nAnalyzing MI {target_mi:08X} with {count} uses")
    
    # Get frames grouped by superframe
    cursor_enc.execute(f"""
        SELECT superframe_id, ambe_hex 
        FROM '{table_name}'
        ORDER BY superframe_id, id
    """)
    
    frames_by_sf = defaultdict(list)
    for sf_id, ambe_hex in cursor_enc.fetchall():
        frames_by_sf[sf_id].append(ambe_hex)
    
    # XOR frames from different superframes (same position)
    print("\n=== DIFFERENTIAL CRYPTANALYSIS ===")
    
    sf_ids = list(frames_by_sf.keys())
    if len(sf_ids) >= 2:
        sf1_frames = frames_by_sf[sf_ids[0]]
        sf2_frames = frames_by_sf[sf_ids[1]]
        
        min_len = min(len(sf1_frames), len(sf2_frames))
        
        print(f"Comparing {min_len} frame positions between superframes")
        
        xor_diffs = []
        for pos in range(min_len):
            frame1 = int(sf1_frames[pos], 16)
            frame2 = int(sf2_frames[pos], 16)
            xor_diff = frame1 ^ frame2
            
            xor_diffs.append({
                'position': pos,
                'xor': xor_diff,
                'hamming': bin(xor_diff).count('1'),
                'hex': f"{xor_diff:016X}"
            })
        
        # Find positions with consistent patterns
        print("\nPositions with low XOR differences:")
        sorted_diffs = sorted(xor_diffs, key=lambda x: x['hamming'])
        
        for diff in sorted_diffs[:5]:
            print(f"  Position {diff['position']}: {diff['hex']} ({diff['hamming']} bits)")
    
    # Statistical attack based on AMBE structure
    print("\n=== AMBE STRUCTURE-BASED ATTACK ===")
    
    # AMBE frames have specific structure:
    # - Bits 0-5: Fundamental frequency (should be 10-50 for voice)
    # - Bits 6-14: First spectral magnitude
    # - Bits 15-48: Additional spectral information
    # - Bit 49: Voicing decision
    
    # Test keystreams that produce valid AMBE structure
    test_frame = frames_by_sf[sf_ids[0]][0]  # First frame
    
    print(f"\nTesting frame: {test_frame}")
    
    best_candidates = []
    
    # Generate keystream candidates based on AMBE constraints
    for fundamental in range(10, 51, 5):  # Valid voice fundamentals
        for voicing in [0, 1]:  # Voiced/unvoiced
            
            # Construct a plausible AMBE frame
            plausible_ambe = 0
            
            # Set fundamental frequency
            plausible_ambe |= (fundamental << 58)
            
            # Set voicing bit
            plausible_ambe |= (voicing << 49)
            
            # Calculate keystream
            encrypted_int = int(test_frame, 16)
            keystream = encrypted_int ^ plausible_ambe
            
            # Test this keystream on other frames
            score = test_keystream_validity(keystream, frames_by_sf[sf_ids[0]])
            
            if score > 50:  # Threshold for likely valid
                best_candidates.append({
                    'keystream': keystream,
                    'fundamental': fundamental,
                    'voicing': voicing,
                    'score': score
                })
    
    # Sort by score
    best_candidates.sort(key=lambda x: x['score'], reverse=True)
    
    print("\nBest keystream candidates:")
    for i, candidate in enumerate(best_candidates[:5]):
        print(f"{i+1}. Score: {candidate['score']}")
        print(f"   Keystream: {candidate['keystream']:016X}")
        print(f"   Fundamental: {candidate['fundamental']} Hz")
        print(f"   Voicing: {candidate['voicing']}")
    
    conn_enc.close()
    
    print("\n=== FINAL ATTACK STRATEGY ===")
    print("1. Use AMBE structure constraints to limit keystream space")
    print("2. Test candidates against known audio characteristics")
    print("3. Validate using spectral analysis of decoded audio")
    print("4. With enough frames, statistical convergence reveals key")

def analyze_bit_patterns(frames):
    """Analyze statistical properties of AMBE frames"""
    
    hamming_weights = []
    bit_counts = [0] * 64
    byte_counter = Counter()
    
    for frame_hex in frames:
        frame_int = int(frame_hex, 16)
        
        # Hamming weight
        hamming = bin(frame_int).count('1')
        hamming_weights.append(hamming)
        
        # Bit position counts
        for bit_pos in range(64):
            if frame_int & (1 << bit_pos):
                bit_counts[bit_pos] += 1
        
        # Byte patterns
        for i in range(0, 16, 2):
            byte = frame_hex[i:i+2]
            byte_counter[byte] += 1
    
    # Calculate bit bias
    bit_bias = [(count / len(frames)) for count in bit_counts]
    
    return {
        'avg_hamming': np.mean(hamming_weights),
        'bit_bias': bit_bias,
        'common_bytes': byte_counter.most_common(10)
    }

def test_keystream_validity(keystream, frames):
    """Test if keystream produces valid AMBE frames"""
    
    score = 0
    
    for frame_hex in frames[:20]:  # Test on subset
        encrypted_int = int(frame_hex, 16)
        decrypted = encrypted_int ^ keystream
        
        # Extract AMBE fields
        fundamental = (decrypted >> 58) & 0x3F
        voicing = (decrypted >> 49) & 0x1FF
        
        # Check validity
        if 8 < fundamental < 50:  # Valid voice range
            score += 5
            
        # Check spectral magnitudes are reasonable
        for i in range(8):
            magnitude = (decrypted >> (i * 6)) & 0x3F
            if 0 < magnitude < 60:  # Reasonable range
                score += 1
    
    return score

if __name__ == "__main__":
    analyze_ambe_statistics()