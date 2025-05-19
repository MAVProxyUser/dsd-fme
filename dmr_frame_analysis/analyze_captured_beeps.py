#!/usr/bin/env python3
"""Analyze captured DMR frames to find beep patterns"""
import sqlite3
import sys
from collections import Counter

if len(sys.argv) < 2:
    print("Usage: python3 analyze_captured_beeps.py <database_file>")
    sys.exit(1)

db_file = sys.argv[1]
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print(f"=== Analyzing {db_file} for Beep Patterns ===\n")

# Check for unencrypted frames
cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name = 'U_00000000_S0'
""")

if not cursor.fetchone():
    print("No unencrypted frames found. Looking for encrypted patterns instead...")
    
    # Analyze encrypted frames
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')
        ORDER BY name
    """)
    
    tables = cursor.fetchall()
    print(f"Found {len(tables)} encrypted tables\n")
    
    for table_name, in tables[:5]:  # First 5 tables
        cursor.execute(f"""
            SELECT ambe_hex, id FROM {table_name}
            ORDER BY id LIMIT 3
        """)
        
        frames = cursor.fetchall()
        print(f"{table_name}:")
        for ambe_hex, frame_id in frames:
            print(f"  Frame {frame_id}: {ambe_hex}")
        print()
    
else:
    # Analyze unencrypted frames
    cursor.execute("SELECT COUNT(*) FROM U_00000000_S0")
    total_frames = cursor.fetchone()[0]
    print(f"Total unencrypted frames: {total_frames}")
    
    # Find common patterns
    cursor.execute("""
        SELECT ambe_hex, COUNT(*) as count 
        FROM U_00000000_S0 
        GROUP BY ambe_hex 
        ORDER BY count DESC 
        LIMIT 20
    """)
    
    patterns = cursor.fetchall()
    print("\n1. Most Common Patterns (beeps/silence will repeat):")
    
    beep_candidates = []
    for pattern, count in patterns:
        percentage = (count / total_frames) * 100
        print(f"   {pattern}: {count} times ({percentage:.1f}%)")
        
        # Analyze pattern characteristics
        hex_bytes = bytes.fromhex(pattern)
        unique_bytes = len(set(hex_bytes))
        zero_count = sum(1 for b in hex_bytes if b == 0)
        
        # Look for beep characteristics
        if pattern == "0000000000000000":
            print(f"      ** SILENCE **")
        elif count >= 5 and unique_bytes <= 4:
            print(f"      ** LIKELY BEEP - repeats {count} times, {unique_bytes} unique bytes")
            beep_candidates.append((pattern, count))
        elif count >= 3 and zero_count >= 6:
            print(f"      ** POSSIBLE BEEP/SILENCE - {zero_count} zeros")
            beep_candidates.append((pattern, count))
    
    # Look at transmission boundaries
    print("\n2. Transmission Boundary Analysis:")
    
    # Get superframe boundaries
    cursor.execute("""
        SELECT DISTINCT superframe_id 
        FROM U_00000000_S0 
        WHERE superframe_id IS NOT NULL 
        ORDER BY superframe_id
    """)
    
    superframes = cursor.fetchall()
    
    for sf_id, in superframes[:5]:  # Analyze first 5 superframes
        # Get first and last frames
        cursor.execute("""
            SELECT ambe_hex, id 
            FROM U_00000000_S0 
            WHERE superframe_id = ? 
            ORDER BY id 
            LIMIT 5
        """, (sf_id,))
        start_frames = cursor.fetchall()
        
        cursor.execute("""
            SELECT ambe_hex, id 
            FROM U_00000000_S0 
            WHERE superframe_id = ? 
            ORDER BY id DESC 
            LIMIT 5
        """, (sf_id,))
        end_frames = cursor.fetchall()
        
        print(f"\n   Superframe {sf_id}:")
        print("   Start (looking for 1 beep):")
        for ambe_hex, frame_id in start_frames:
            print(f"      Frame {frame_id}: {ambe_hex}")
            if ambe_hex in [p[0] for p in beep_candidates]:
                print(f"         ** MATCHES BEEP CANDIDATE **")
        
        print("   End (looking for 3 beeps):")
        beep_count = 0
        for ambe_hex, frame_id in reversed(end_frames):
            print(f"      Frame {frame_id}: {ambe_hex}")
            if ambe_hex in [p[0] for p in beep_candidates]:
                beep_count += 1
                print(f"         ** BEEP {beep_count} **")
    
    # Look for specific sequences
    print("\n3. Beep Sequence Detection:")
    
    # Find consecutive repeated patterns
    cursor.execute("""
        SELECT ambe_hex, id 
        FROM U_00000000_S0 
        ORDER BY id
    """)
    
    all_frames = cursor.fetchall()
    sequences = []
    current_pattern = None
    current_count = 0
    start_id = None
    
    for ambe_hex, frame_id in all_frames:
        if ambe_hex == current_pattern:
            current_count += 1
        else:
            if current_count >= 3:  # Found a sequence
                sequences.append((current_pattern, current_count, start_id))
            current_pattern = ambe_hex
            current_count = 1
            start_id = frame_id
    
    # Check last sequence
    if current_count >= 3:
        sequences.append((current_pattern, current_count, start_id))
    
    print(f"\n   Found {len(sequences)} repeated sequences:")
    for pattern, count, start_id in sequences[:10]:
        print(f"   Pattern {pattern} repeated {count} times starting at frame {start_id}")
        if pattern in [p[0] for p in beep_candidates]:
            print(f"      ** CONFIRMED BEEP SEQUENCE **")

conn.close()

print("\n=== Summary ===")
print("DMR beep patterns identified by:")
print("1. High repetition count (same tone = same AMBE)")
print("2. Limited byte diversity")
print("3. Appearance at transmission boundaries")
print("4. Sequences of 1 (start) or 3 (end) beeps")
print(f"\nBeep candidates found: {len(beep_candidates)}")