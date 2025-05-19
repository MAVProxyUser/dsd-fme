#!/usr/bin/env python3
"""Find structural patterns in DMR frames - headers, sync, embedded signaling"""

import sqlite3
from collections import defaultdict, Counter

def analyze_dmr_structure():
    print("=== DMR FRAME STRUCTURE ANALYSIS ===")
    
    # DMR Frame structure reminders:
    # - Slot 0/1 structure is predictable
    # - EMB (Embedded signaling) has known patterns
    # - PI header is partially predictable
    # - SYNC patterns are fixed
    
    encrypted_db = "dmr_capture_20250518_112024_998484.db"
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    
    print("\n=== LOOKING FOR DMR STRUCTURAL PATTERNS ===")
    
    # In DMR, certain parts are predictable:
    # 1. SYNC patterns (fixed values)
    # 2. CACH (Access Header) - partially predictable
    # 3. EMB (Embedded Signaling) - follows patterns
    # 4. Slot timing indicators
    
    # Check superframe metadata
    for db_file, label in [(encrypted_db, "ENCRYPTED"), (cleartext_db, "CLEARTEXT")]:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        print(f"\n{label} Structural Analysis:")
        
        # Check PI/LC data patterns
        cursor.execute("""
            SELECT sync_type, slot, flco, fid, COUNT(*) 
            FROM superframes 
            GROUP BY sync_type, slot, flco, fid
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)
        
        print("\nCommon frame structures:")
        for row in cursor.fetchall():
            print(f"  Type: {row[0]}, Slot: {row[1]}, FLCO: {row[2]}, FID: {row[3]}, Count: {row[4]}")
        
        # Check for repeating metadata patterns
        cursor.execute("""
            SELECT source_id, target_id, color_code, COUNT(*)
            FROM superframes
            GROUP BY source_id, target_id, color_code
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """)
        
        print("\nCommon metadata combinations:")
        for row in cursor.fetchall():
            print(f"  Src: {row[0]}, Tgt: {row[1]}, CC: {row[2]}, Count: {row[3]}")
        
        # IMPORTANT: Check first and last frames of transmissions
        # These often have predictable patterns
        cursor.execute("""
            SELECT id, h_mi, c_mi, frame_count
            FROM superframes
            WHERE frame_count = 1 OR frame_count = 15
            LIMIT 10
        """)
        
        print("\nFrames with specific counts (potential start/end):")
        for row in cursor.fetchall():
            print(f"  ID: {row[0]}, H-MI: {row[1]}, C-MI: {row[2]}, Count: {row[3]}")
        
        conn.close()
    
    # The key insight: In encrypted DMR, certain frames are NOT encrypted:
    # 1. SYNC patterns
    # 2. Some control messages
    # 3. Frame headers
    
    print("\n=== ATTACK VECTOR: RC4 KEY REUSE ===")
    
    conn = sqlite3.connect(encrypted_db)
    cursor = conn.cursor()
    
    # Find C-MI values that appear multiple times
    cursor.execute("""
        SELECT c_mi, COUNT(*) as count
        FROM superframes
        WHERE c_mi IS NOT NULL AND c_mi != 0
        GROUP BY c_mi
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        LIMIT 10
    """)
    
    print("\nC-MI values with multiple uses (RC4 IV reuse!):")
    reused_mis = []
    for mi, count in cursor.fetchall():
        print(f"  MI {mi:08X}: used {count} times")
        reused_mis.append(mi)
    
    # For each reused MI, get the AMBE frames
    if reused_mis:
        mi = reused_mis[0]  # Take most reused
        table_name = f"C_{mi:08X}_S0"
        
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        frame_count = cursor.fetchone()[0]
        
        print(f"\nAnalyzing MI {mi:08X} with {frame_count} frames:")
        
        cursor.execute(f"SELECT ambe_hex FROM '{table_name}' LIMIT 10")
        frames = [row[0] for row in cursor.fetchall()]
        
        # XOR frames encrypted with same IV!
        if len(frames) >= 2:
            print("\nXORing frames with same IV:")
            for i in range(min(5, len(frames)-1)):
                frame1 = int(frames[i], 16)
                frame2 = int(frames[i+1], 16)
                xor_result = frame1 ^ frame2
                
                print(f"  Frame {i} XOR Frame {i+1}: {xor_result:016X}")
                
                # This gives us: plaintext1 XOR plaintext2
                # If we can guess one plaintext, we get the other!
    
    conn.close()
    
    print("\n=== KEY FINDINGS ===")
    print("1. Each C-MI appears exactly 2 times (confirmed earlier)")
    print("2. This means each IV is reused once")
    print("3. XORing two frames with same IV eliminates the keystream")
    print("4. Result is plaintext1 XOR plaintext2")
    print("5. If we can guess one frame (silence, end marker), we get the other")
    
    print("\n=== IMMEDIATE ATTACK ===")
    print("1. Find frames encrypted with same C-MI")
    print("2. XOR them together (eliminates keystream)")
    print("3. Look for patterns in XOR result")
    print("4. Common patterns: silence, DTMF, end-of-transmission")
    print("5. With enough samples, statistical analysis reveals content")

if __name__ == "__main__":
    analyze_dmr_structure()