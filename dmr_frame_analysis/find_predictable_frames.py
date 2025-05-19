#!/usr/bin/env python3
"""Find predictable frame patterns for XOR attack"""

import sqlite3
from collections import defaultdict, Counter

# Database files
encrypted_db = "dmr_capture_20250518_112024_998484.db"
cleartext_db = "dmr_capture_20250518_112958_062803.db"

def analyze_predictable_patterns():
    # Common predictable AMBE patterns
    known_patterns = {
        'silence': ['0000000000000000', 'FFFFFFFFFFFFFFFF'],
        'dtmf': [],  # DTMF tones have specific patterns
        'comfort_noise': [],
        'end_of_transmission': []
    }
    
    # Analyze cleartext for common patterns
    conn_clr = sqlite3.connect(cleartext_db)
    cursor_clr = conn_clr.cursor()
    
    print("=== CLEARTEXT PATTERN ANALYSIS ===")
    
    # Get all cleartext AMBE frames
    cursor_clr.execute("SELECT ambe_hex FROM U_00000000_S0")
    clr_frames = [row[0] for row in cursor_clr.fetchall()]
    
    # Count frame patterns
    pattern_counts = Counter(clr_frames)
    
    print(f"\nTotal cleartext frames: {len(clr_frames)}")
    print(f"Unique patterns: {len(pattern_counts)}")
    
    print("\nMost common cleartext patterns:")
    for pattern, count in pattern_counts.most_common(20):
        percentage = count / len(clr_frames) * 100
        print(f"  {pattern}: {count} times ({percentage:.1f}%)")
    
    # Analyze encrypted for same patterns
    conn_enc = sqlite3.connect(encrypted_db)
    cursor_enc = conn_enc.cursor()
    
    print("\n=== ENCRYPTED PATTERN ANALYSIS ===")
    
    # Get all encrypted AMBE frames with MI values
    cursor_enc.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%_S0'
    """)
    
    encrypted_patterns = defaultdict(list)
    mi_to_frames = defaultdict(list)
    
    for table in cursor_enc.fetchall():
        table_name = table[0]
        mi_value = table_name.split('_')[1]
        
        cursor_enc.execute(f"SELECT ambe_hex FROM '{table_name}'")
        frames = [row[0] for row in cursor_enc.fetchall()]
        
        for frame in frames:
            encrypted_patterns[frame].append(mi_value)
            mi_to_frames[mi_value].append(frame)
    
    # Find frames that appear with multiple MIs (potential pattern)
    print("\nFrames appearing with multiple MI values:")
    multi_mi_frames = [(frame, mis) for frame, mis in encrypted_patterns.items() if len(set(mis)) > 1]
    
    for frame, mis in sorted(multi_mi_frames, key=lambda x: len(set(x[1])), reverse=True)[:10]:
        unique_mis = len(set(mis))
        print(f"  {frame}: appears with {unique_mis} different MIs")
    
    # Check for silence/empty frames
    print("\n=== LOOKING FOR SILENCE/EMPTY FRAMES ===")
    
    # Common silence patterns in AMBE
    silence_patterns = [
        '0000000000000000',
        'FFFFFFFFFFFFFFFF',
        '0000000000000080',  # Some codecs use bit flags
        '8000000000000000'
    ]
    
    # Check cleartext for silence
    clr_silence_candidates = []
    for pattern in silence_patterns:
        if pattern in pattern_counts:
            clr_silence_candidates.append((pattern, pattern_counts[pattern]))
    
    if clr_silence_candidates:
        print("\nPotential silence in cleartext:")
        for pattern, count in clr_silence_candidates:
            print(f"  {pattern}: {count} times")
    
    # Look for frames at start/end of transmission
    print("\n=== START/END OF TRANSMISSION PATTERNS ===")
    
    # Get first and last frames from each superframe
    cursor_clr.execute("""
        SELECT superframe_id, MIN(id), MAX(id) 
        FROM U_00000000_S0 
        GROUP BY superframe_id
    """)
    
    start_frames = []
    end_frames = []
    
    for sf_id, min_id, max_id in cursor_clr.fetchall():
        cursor_clr.execute("SELECT ambe_hex FROM U_00000000_S0 WHERE id = ?", (min_id,))
        start = cursor_clr.fetchone()
        if start:
            start_frames.append(start[0])
            
        cursor_clr.execute("SELECT ambe_hex FROM U_00000000_S0 WHERE id = ?", (max_id,))
        end = cursor_clr.fetchone()
        if end:
            end_frames.append(end[0])
    
    start_counter = Counter(start_frames)
    end_counter = Counter(end_frames)
    
    print("\nMost common start-of-transmission frames:")
    for pattern, count in start_counter.most_common(5):
        print(f"  {pattern}: {count} times")
    
    print("\nMost common end-of-transmission frames:")
    for pattern, count in end_counter.most_common(5):
        print(f"  {pattern}: {count} times")
    
    # XOR analysis for predictable patterns
    print("\n=== XOR ANALYSIS FOR PREDICTABLE PATTERNS ===")
    
    # If we find common patterns in both, XOR them
    if mi_to_frames:
        # Take a common cleartext pattern
        most_common_clr = pattern_counts.most_common(1)[0][0]
        print(f"\nMost common cleartext pattern: {most_common_clr}")
        
        # Find encrypted frames that might be the same content
        # Look specifically at frames with matching positions
        cursor_clr.execute("""
            SELECT id, ambe_hex, superframe_id 
            FROM U_00000000_S0 
            WHERE ambe_hex = ? 
            LIMIT 5
        """, (most_common_clr,))
        
        for clr_id, clr_hex, clr_sf in cursor_clr.fetchall():
            print(f"\nCleartext frame {clr_id} (SF {clr_sf}): {clr_hex}")
            
            # Try to XOR with various encrypted frames
            for mi, enc_frames in list(mi_to_frames.items())[:3]:
                if enc_frames:
                    enc_hex = enc_frames[0]
                    print(f"  Encrypted (MI {mi}): {enc_hex}")
                    
                    # XOR the frames
                    clr_int = int(clr_hex, 16)
                    enc_int = int(enc_hex, 16)
                    xor_result = clr_int ^ enc_int
                    
                    print(f"  XOR result: {xor_result:016X}")
                    
                    # Check if XOR result looks like a keystream
                    # (should have good randomness)
                    bit_count = bin(xor_result).count('1')
                    print(f"  Bit balance: {bit_count}/64 bits set")
    
    conn_clr.close()
    conn_enc.close()
    
    print("\n=== CONCLUSIONS ===")
    print("1. Some cleartext patterns repeat frequently")
    print("2. These might be silence, comfort noise, or protocol frames")
    print("3. If we can identify the same pattern encrypted, we can recover keystream")
    print("4. End-of-transmission frames are good candidates")

if __name__ == "__main__":
    analyze_predictable_patterns()