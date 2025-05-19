#!/usr/bin/env python3
"""Comprehensive analysis of DMR Call Tone and Call End Tone patterns"""
import sqlite3
import sys
from collections import Counter

if len(sys.argv) < 2:
    print("Using default database...")
    db_file = 'dmr_capture_20250517_204818.db'
else:
    db_file = sys.argv[1]

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print(f"=== Analyzing Call Tones in {db_file} ===\n")

# Check for cleartext frames
cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name = 'U_00000000_S0'
""")

if not cursor.fetchone():
    print("No unencrypted frames found.\n")
    
    # Show encrypted pattern instead
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
        ORDER BY name
    """)
    
    enc_tables = cursor.fetchall()
    print(f"Encrypted tables: {len(enc_tables)}")
    
    for table_name, in enc_tables[:3]:
        cursor.execute(f"""
            SELECT ambe_hex, id FROM {table_name}
            ORDER BY id LIMIT 3
        """)
        
        frames = cursor.fetchall()
        print(f"\n{table_name} (first frames - Call Tone location):")
        for ambe_hex, frame_id in frames:
            print(f"  Frame {frame_id}: {ambe_hex}")
else:
    # Analyze cleartext frames
    cursor.execute("""
        SELECT u.id, u.ambe_hex, u.superframe_id, s.frame_count
        FROM U_00000000_S0 u
        LEFT JOIN superframes s ON u.superframe_id = s.id
        ORDER BY u.id
    """)
    
    all_frames = cursor.fetchall()
    print(f"Total cleartext frames: {len(all_frames)}")
    
    # Group by superframe
    superframes = {}
    for frame_id, ambe_hex, sf_id, frame_count in all_frames:
        if sf_id not in superframes:
            superframes[sf_id] = []
        superframes[sf_id].append((frame_id, ambe_hex))
    
    print(f"Superframes: {len(superframes)}\n")
    
    # Find repeated patterns (tones)
    pattern_counts = Counter([f[1] for f in all_frames])
    repeated = [(p, c) for p, c in pattern_counts.items() if c >= 3]
    
    print("1. Repeated Patterns (Call Tones repeat):")
    tone_patterns = []
    for pattern, count in sorted(repeated, key=lambda x: x[1], reverse=True)[:10]:
        print(f"   {pattern}: {count} times")
        
        # Check characteristics
        hex_bytes = bytes.fromhex(pattern)
        unique_bytes = len(set(hex_bytes))
        zeros = sum(1 for b in hex_bytes if b == 0)
        
        if pattern == "0000000000000000":
            print("      ** SILENCE **")
        elif unique_bytes <= 4:
            print(f"      ** DEFINITE TONE - only {unique_bytes} unique bytes **")
            tone_patterns.append(pattern)
        elif unique_bytes <= 6 and count >= 5:
            print(f"      ** LIKELY TONE - {unique_bytes} unique bytes, high repetition **")
            tone_patterns.append(pattern)
    
    # Analyze transmission boundaries
    print("\n2. Transmission Boundary Analysis:")
    
    call_tone_found = False
    call_end_tone_found = False
    
    for sf_id, frames in superframes.items():
        if len(frames) < 5:
            continue
            
        print(f"\n   Superframe {sf_id} ({len(frames)} frames):")
        
        # Check start (Call Tone)
        print("   Start (Call Tone location):")
        start_tone_count = 0
        for i in range(min(3, len(frames))):
            frame_id, ambe_hex = frames[i]
            print(f"      Frame {frame_id}: {ambe_hex}")
            
            # Check if it's a tone pattern
            if ambe_hex in tone_patterns:
                start_tone_count += 1
                print(f"         ** CALL TONE DETECTED **")
                call_tone_found = True
            else:
                # Check entropy
                unique_bytes = len(set(bytes.fromhex(ambe_hex)))
                if unique_bytes <= 5:
                    print(f"         ** Possible tone - {unique_bytes} unique bytes **")
        
        # Check end (Call End Tone - 3 beeps)
        print("   End (Call End Tone location):")
        end_tone_count = 0
        end_frames = frames[-5:] if len(frames) >= 5 else frames
        
        for frame_id, ambe_hex in end_frames:
            print(f"      Frame {frame_id}: {ambe_hex}")
            
            # Check if it's a tone pattern
            if ambe_hex in tone_patterns:
                end_tone_count += 1
                print(f"         ** CALL END TONE {end_tone_count} DETECTED **")
                call_end_tone_found = True
            else:
                # Check entropy
                unique_bytes = len(set(bytes.fromhex(ambe_hex)))
                if unique_bytes <= 5:
                    print(f"         ** Possible tone - {unique_bytes} unique bytes **")
        
        if end_tone_count >= 3:
            print("      *** FULL CALL END TONE SEQUENCE (3 beeps) ***")
    
    # Look for tone sequences
    print("\n3. Tone Sequence Detection:")
    
    sequences = []
    current_pattern = None
    sequence_start = None
    sequence_frames = []
    
    for frame_id, ambe_hex, _, _ in all_frames:
        if ambe_hex in tone_patterns:
            if current_pattern == ambe_hex:
                sequence_frames.append(frame_id)
            else:
                # New pattern or end of sequence
                if len(sequence_frames) >= 3:
                    sequences.append((current_pattern, sequence_frames))
                current_pattern = ambe_hex
                sequence_start = frame_id
                sequence_frames = [frame_id]
        else:
            # Not a tone - end current sequence
            if len(sequence_frames) >= 3:
                sequences.append((current_pattern, sequence_frames))
            current_pattern = None
            sequence_frames = []
    
    # Check last sequence
    if len(sequence_frames) >= 3:
        sequences.append((current_pattern, sequence_frames))
    
    print(f"\nFound {len(sequences)} tone sequences:")
    for pattern, frames in sequences[:10]:
        duration_ms = len(frames) * 20  # 20ms per AMBE frame
        print(f"   Pattern {pattern}:")
        print(f"     Frames: {frames[0]}-{frames[-1]} ({len(frames)} frames, {duration_ms}ms)")
        
        if duration_ms >= 180 and duration_ms <= 320:
            print("     ** MATCHES CALL TONE DURATION (200-300ms) **")
        elif len(frames) == 3 and duration_ms == 60:
            print("     ** POSSIBLE SINGLE BEEP IN CALL END TONE **")

conn.close()

print("\n=== Summary ===")
if tone_patterns:
    print(f"Found {len(tone_patterns)} distinct tone patterns")
    print("Call Tone:", "DETECTED" if call_tone_found else "Not clearly detected")
    print("Call End Tone:", "DETECTED" if call_end_tone_found else "Not clearly detected")
else:
    print("No clear tone patterns detected")
    
print("\nDMR Call Tone Characteristics:")
print("- Single beep at transmission start")
print("- ~200-300ms duration (10-15 AMBE frames)")
print("- Low entropy pattern (few unique bytes)")
print("\nDMR Call End Tone Characteristics:")
print("- Three beeps at transmission end")
print("- Each beep ~200ms")
print("- Same pattern as Call Tone, repeated 3 times")
print("- May have brief silence between beeps")