#!/usr/bin/env python3
"""Find actual call tones by analyzing AMBE frame characteristics"""
import sqlite3
import numpy as np
from collections import Counter

db_file = 'dmr_capture_20250517_204818.db'
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print("=== Analyzing AMBE Frames for Call Tone Patterns ===\n")

# Get all frames with superframe info
cursor.execute("""
    SELECT u.id, u.ambe_hex, u.superframe_id, s.source_id, s.target_id, s.sync_type
    FROM U_00000000_S0 u
    LEFT JOIN superframes s ON u.superframe_id = s.id
    ORDER BY u.id
""")

frames = cursor.fetchall()
print(f"Total frames: {len(frames)}")

# Group frames by superframe
superframe_data = {}
for frame_id, ambe_hex, sf_id, src, tgt, sync_type in frames:
    if sf_id not in superframe_data:
        superframe_data[sf_id] = []
    superframe_data[sf_id].append((frame_id, ambe_hex))

print(f"Superframes: {len(superframe_data)}\n")

# Analyze each superframe for tone patterns
tone_candidates = []

for sf_id, sf_frames in superframe_data.items():
    print(f"Superframe {sf_id}: {len(sf_frames)} frames")
    
    # Check first 3 frames (Call Tone location)
    print("  Start frames (Call Tone location):")
    for i in range(min(3, len(sf_frames))):
        frame_id, ambe_hex = sf_frames[i]
        
        # Analyze byte patterns
        ambe_bytes = bytes.fromhex(ambe_hex)
        byte_entropy = len(set(ambe_bytes))
        
        # Look for characteristics of tones
        # Tones have lower entropy than voice
        if byte_entropy <= 6:  # Lower threshold
            print(f"    Frame {frame_id}: {ambe_hex}")
            print(f"      Low entropy ({byte_entropy} unique bytes) - TONE CANDIDATE")
            tone_candidates.append(('start', sf_id, frame_id, ambe_hex))
    
    # Check last 5 frames (Call End Tone location)
    print("  End frames (Call End Tone location):")
    if len(sf_frames) >= 5:
        for i in range(len(sf_frames)-5, len(sf_frames)):
            frame_id, ambe_hex = sf_frames[i]
            
            # Analyze byte patterns
            ambe_bytes = bytes.fromhex(ambe_hex)
            byte_entropy = len(set(ambe_bytes))
            
            if byte_entropy <= 6:  # Lower threshold for tones
                print(f"    Frame {frame_id}: {ambe_hex}")
                print(f"      Low entropy ({byte_entropy} unique bytes) - TONE CANDIDATE")
                tone_candidates.append(('end', sf_id, frame_id, ambe_hex))
    
    print()

# Analyze tone candidates for patterns
print("\n=== Tone Candidate Analysis ===")

if tone_candidates:
    print(f"Found {len(tone_candidates)} potential tone frames\n")
    
    # Group by location
    start_tones = [t for t in tone_candidates if t[0] == 'start']
    end_tones = [t for t in tone_candidates if t[0] == 'end']
    
    print(f"Start tones: {len(start_tones)}")
    print(f"End tones: {len(end_tones)}")
    
    # Look for similar patterns
    pattern_groups = Counter([t[3] for t in tone_candidates])
    
    print("\nRepeated patterns:")
    for pattern, count in pattern_groups.most_common():
        if count > 1:
            print(f"  {pattern}: {count} occurrences")
            locations = [t[0] for t in tone_candidates if t[3] == pattern]
            print(f"    Locations: {locations}")
else:
    print("No clear tone candidates found")

# Check for actual DMR tone characteristics
print("\n=== DMR Call Tone Characteristics ===")
print("Expected patterns:")
print("1. Call Tone: Single tone at start, ~200-300ms")
print("2. Call End Tone: 3 beeps at end, ~200ms each")
print("3. Frequency: 2400Hz or 2600Hz")
print("4. AMBE encoding: Lower entropy than voice")

# Let's try a different approach - look for frames that are different from neighbors
print("\n=== Detecting Tones by Context ===")

for sf_id, sf_frames in superframe_data.items():
    if len(sf_frames) < 5:
        continue
    
    # Check if first frame is different from subsequent (potential start tone)
    first_frame = sf_frames[0][1]
    second_frame = sf_frames[1][1] if len(sf_frames) > 1 else None
    
    if first_frame != second_frame:
        # Calculate entropy difference
        first_entropy = len(set(bytes.fromhex(first_frame)))
        second_entropy = len(set(bytes.fromhex(second_frame))) if second_frame else 0
        
        if first_entropy < second_entropy - 2:  # First frame has lower entropy
            print(f"\nSuperframe {sf_id}: Potential Call Tone")
            print(f"  First frame: {first_frame} (entropy: {first_entropy})")
            print(f"  Second frame: {second_frame} (entropy: {second_entropy})")
    
    # Check last frames for pattern changes (potential end tones)
    if len(sf_frames) >= 5:
        last_5 = sf_frames[-5:]
        entropy_values = [len(set(bytes.fromhex(f[1]))) for f in last_5]
        
        # Look for entropy drops (tones have lower entropy)
        entropy_drops = []
        for i in range(1, len(entropy_values)):
            if entropy_values[i] < entropy_values[i-1] - 2:
                entropy_drops.append(i)
        
        if entropy_drops:
            print(f"\nSuperframe {sf_id}: Potential Call End Tones")
            print(f"  Entropy pattern: {entropy_values}")
            print(f"  Drops at positions: {entropy_drops}")

conn.close()

print("\n=== Summary ===")
print("Call tones in AMBE have:")
print("1. Lower byte entropy than voice")
print("2. Different pattern from surrounding frames")
print("3. Specific duration (10-15 frames for single tone)")
print("4. Predictable location (start/end of transmission)")
print("\nThe cleartext capture may contain voice data without")
print("clear transmission boundaries, or the tones may be")
print("encoded in a way that's not immediately obvious in the hex.")