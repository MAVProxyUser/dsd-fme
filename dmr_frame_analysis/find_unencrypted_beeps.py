#!/usr/bin/env python3
"""Find actual beep patterns in unencrypted DMR frames"""
import sqlite3
from collections import Counter

# Connect to database with unencrypted frames
conn = sqlite3.connect('dmr_capture_20250517_204818.db')
cursor = conn.cursor()

print("=== Searching for Beep Patterns in Unencrypted DMR ===\n")

# Get all unencrypted frames ordered by time
cursor.execute("""
    SELECT id, ambe_hex, superframe_id 
    FROM U_00000000_S0 
    ORDER BY id
""")

frames = cursor.fetchall()
print(f"Total unencrypted frames: {len(frames)}")

# Analyze frame patterns
frame_patterns = Counter()
for _, ambe_hex, _ in frames:
    frame_patterns[ambe_hex] += 1

# Find most common patterns (likely silence or beeps)
print("\n1. Most Common Patterns (likely silence or beeps):")
for pattern, count in frame_patterns.most_common(10):
    print(f"   {pattern}: {count} occurrences")
    # Check if it's all zeros (silence)
    if pattern == "0000000000000000":
        print(f"      ** SILENCE **")
    # Check for patterns with limited byte values (could be tones)
    hex_bytes = bytes.fromhex(pattern)
    unique_bytes = len(set(hex_bytes))
    if unique_bytes <= 3:
        print(f"      ** Possible tone - only {unique_bytes} unique bytes")

# Look at transmission boundaries
print("\n2. First 5 frames (transmission start):")
for i in range(min(5, len(frames))):
    frame_id, ambe_hex, sf_id = frames[i]
    print(f"   Frame {frame_id}: {ambe_hex} (SF: {sf_id})")

print("\n3. Last 5 frames (transmission end):")
for i in range(max(0, len(frames)-5), len(frames)):
    frame_id, ambe_hex, sf_id = frames[i]
    print(f"   Frame {frame_id}: {ambe_hex} (SF: {sf_id})")

# Look for patterns by superframe
cursor.execute("""
    SELECT superframe_id, COUNT(*) as frame_count 
    FROM U_00000000_S0 
    GROUP BY superframe_id 
    ORDER BY superframe_id
""")

superframes = cursor.fetchall()
print(f"\n4. Superframes: {len(superframes)}")

# Analyze first and last frames of each superframe
print("\n5. Frames at Superframe Boundaries:")
for sf_id, frame_count in superframes[:3]:  # First 3 superframes
    # First frame of superframe
    cursor.execute("""
        SELECT id, ambe_hex 
        FROM U_00000000_S0 
        WHERE superframe_id = ? 
        ORDER BY id 
        LIMIT 3
    """, (sf_id,))
    start_frames = cursor.fetchall()
    
    # Last frame of superframe
    cursor.execute("""
        SELECT id, ambe_hex 
        FROM U_00000000_S0 
        WHERE superframe_id = ? 
        ORDER BY id DESC 
        LIMIT 3
    """, (sf_id,))
    end_frames = cursor.fetchall()
    
    print(f"\n   Superframe {sf_id} ({frame_count} frames):")
    print("   Start:")
    for frame_id, ambe_hex in start_frames:
        print(f"      Frame {frame_id}: {ambe_hex}")
    print("   End:")
    for frame_id, ambe_hex in reversed(end_frames):
        print(f"      Frame {frame_id}: {ambe_hex}")

# Look for specific patterns that might be beeps
print("\n6. Searching for Typical Beep Patterns:")

# Beeps often have repeated byte patterns
cursor.execute("""
    SELECT ambe_hex, COUNT(*) as count 
    FROM U_00000000_S0 
    WHERE ambe_hex != '0000000000000000'  -- Not silence
    GROUP BY ambe_hex 
    HAVING count >= 3  -- Appears multiple times
    ORDER BY count DESC 
    LIMIT 10
""")

repeated_patterns = cursor.fetchall()
for pattern, count in repeated_patterns:
    hex_bytes = bytes.fromhex(pattern)
    unique_bytes = len(set(hex_bytes))
    zero_count = sum(1 for b in hex_bytes if b == 0)
    
    print(f"\n   Pattern: {pattern}")
    print(f"   Count: {count}, Unique bytes: {unique_bytes}, Zeros: {zero_count}")
    
    # Check for potential beep characteristics
    if unique_bytes <= 4 and zero_count >= 4:
        print(f"   ** HIGH CONFIDENCE BEEP PATTERN **")
    elif unique_bytes <= 6:
        print(f"   ** Possible beep/tone pattern **")

# Let's look for transitions (silence -> pattern -> silence)
print("\n7. Looking for Beep Transitions:")
for i in range(1, len(frames)-1):
    prev_frame = frames[i-1][1]
    curr_frame = frames[i][1]
    next_frame = frames[i+1][1]
    
    # Look for pattern: silence -> non-silence -> silence
    if prev_frame == "0000000000000000" and curr_frame != "0000000000000000":
        print(f"\n   Transition at frame {frames[i][0]}:")
        print(f"   Before: {prev_frame} (silence)")
        print(f"   Current: {curr_frame}")
        print(f"   After: {next_frame}")
        if i < 10:  # Only show first few
            print("   ** Possible beep start **")

conn.close()

print("\n=== Summary ===")
print("Beep patterns in unencrypted DMR typically show:")
print("1. Repeated patterns (same tone = same AMBE encoding)")
print("2. Limited byte diversity (tones have simple patterns)")
print("3. Surrounded by silence (0000000000000000)")
print("4. Appear at transmission boundaries")
print("5. Multiple occurrences of identical patterns")