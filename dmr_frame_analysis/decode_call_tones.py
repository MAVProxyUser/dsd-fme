#!/usr/bin/env python3
"""Decode AMBE frames to find Call Tone and Call End Tone patterns"""
import sqlite3
import subprocess
import struct
import numpy as np
from collections import Counter
import wave
import tempfile

def ambe_to_pcm(ambe_hex):
    """Convert AMBE hex to PCM using mbelib (if available)"""
    # For now, let's analyze the hex patterns directly
    # since we'd need the exact AMBE+2 decoder implementation
    return bytes.fromhex(ambe_hex)

def analyze_tone_pattern(ambe_hex):
    """Analyze AMBE frame for tone characteristics"""
    ambe_bytes = bytes.fromhex(ambe_hex)
    
    # Convert to bit representation
    bits = ''.join(format(byte, '08b') for byte in ambe_bytes)
    
    # Analyze patterns
    unique_bytes = len(set(ambe_bytes))
    zero_count = sum(1 for b in ambe_bytes if b == 0)
    
    # Look for patterns that might indicate tones
    # Tones have repetitive patterns in AMBE encoding
    byte_counts = Counter(ambe_bytes)
    most_common_byte = byte_counts.most_common(1)[0] if byte_counts else (0, 0)
    
    return {
        'hex': ambe_hex,
        'unique_bytes': unique_bytes,
        'zero_count': zero_count,
        'most_common_byte': most_common_byte,
        'is_silence': ambe_hex == '0000000000000000',
        'possible_tone': unique_bytes <= 4 and most_common_byte[1] >= 3
    }

# Connect to database
db_file = 'dmr_capture_20250517_204818.db'  # The one with cleartext frames
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print("=== Searching for Call Tone and Call End Tone Patterns ===\n")

# Get all cleartext AMBE frames
cursor.execute("""
    SELECT id, ambe_hex, superframe_id 
    FROM U_00000000_S0 
    ORDER BY id
""")

frames = cursor.fetchall()
print(f"Total cleartext AMBE frames: {len(frames)}")

# Analyze patterns
pattern_analysis = {}
for frame_id, ambe_hex, sf_id in frames:
    analysis = analyze_tone_pattern(ambe_hex)
    pattern_analysis[frame_id] = analysis

# Find repeated patterns (tones repeat)
pattern_counts = Counter([a['hex'] for a in pattern_analysis.values()])
repeated_patterns = [(p, c) for p, c in pattern_counts.items() if c >= 3]

print(f"\n1. Repeated Patterns (potential tones):")
for pattern, count in sorted(repeated_patterns, key=lambda x: x[1], reverse=True)[:10]:
    print(f"   {pattern}: {count} occurrences")
    analysis = analyze_tone_pattern(pattern)
    if analysis['is_silence']:
        print(f"      ** SILENCE **")
    elif analysis['possible_tone']:
        print(f"      ** LIKELY TONE - {analysis['unique_bytes']} unique bytes **")

# Look at transmission boundaries
print("\n2. Transmission Boundaries (where tones appear):")

# Get superframes
cursor.execute("""
    SELECT DISTINCT superframe_id 
    FROM U_00000000_S0 
    WHERE superframe_id IS NOT NULL 
    ORDER BY superframe_id
""")

superframes = [sf[0] for sf in cursor.fetchall()]

for sf_id in superframes[:5]:  # Check first 5
    # Get frames at start and end
    cursor.execute("""
        SELECT id, ambe_hex 
        FROM U_00000000_S0 
        WHERE superframe_id = ? 
        ORDER BY id
    """, (sf_id,))
    
    all_frames = cursor.fetchall()
    if not all_frames:
        continue
        
    print(f"\n   Superframe {sf_id} ({len(all_frames)} frames):")
    
    # Check start (Call Tone - single beep)
    print("   Start (Call Tone):")
    for i in range(min(3, len(all_frames))):
        frame_id, ambe_hex = all_frames[i]
        analysis = pattern_analysis[frame_id]
        print(f"      Frame {frame_id}: {ambe_hex}")
        if analysis['possible_tone']:
            print(f"         ** CALL TONE CANDIDATE **")
    
    # Check end (Call End Tone - 3 beeps)
    print("   End (Call End Tone):")
    end_frames = all_frames[-5:] if len(all_frames) >= 5 else all_frames
    tone_count = 0
    
    for frame_id, ambe_hex in end_frames:
        analysis = pattern_analysis[frame_id]
        print(f"      Frame {frame_id}: {ambe_hex}")
        if analysis['possible_tone']:
            tone_count += 1
            print(f"         ** CALL END TONE {tone_count} **")

# Frequency analysis of potential tones
print("\n3. Call Tone Characteristics:")

# DMR typically uses specific frequencies for call tones
print("   Standard DMR call tones:")
print("   - Call Tone: Single beep, 2400Hz or 2600Hz, ~200-300ms")
print("   - Call End Tone: Three beeps, same frequency, ~200ms each")
print("   - AMBE+2 encodes these as specific bit patterns")

# Find sequences of repeated patterns
print("\n4. Tone Sequences:")

sequences = []
current_pattern = None
current_count = 0
start_frame = None

for frame_id, ambe_hex, _ in frames:
    if ambe_hex == current_pattern and pattern_analysis[frame_id]['possible_tone']:
        current_count += 1
    else:
        if current_count >= 3:
            sequences.append((current_pattern, current_count, start_frame))
        current_pattern = ambe_hex
        current_count = 1
        start_frame = frame_id

# Check last sequence
if current_count >= 3:
    sequences.append((current_pattern, current_count, start_frame))

print(f"\n   Found {len(sequences)} tone sequences:")
for pattern, count, start in sequences[:10]:
    duration_ms = count * 20  # Each AMBE frame is 20ms
    print(f"   {pattern}: {count} frames ({duration_ms}ms) starting at frame {start}")
    if duration_ms >= 180 and duration_ms <= 320:
        print(f"      ** MATCHES CALL TONE DURATION **")
    if count == 3 and duration_ms == 60:
        print(f"      ** POSSIBLE CALL END TONE BEEP **")

conn.close()

print("\n=== Summary ===")
print("Call Tone Detection:")
print("1. Look for repeated AMBE patterns (same tone = same encoding)")
print("2. Duration: ~200-300ms (10-15 AMBE frames)")
print("3. Location: Start of transmission")
print("\nCall End Tone Detection:")
print("1. Three separate beeps")
print("2. Each beep: ~200ms (10 frames)")
print("3. Location: End of transmission")
print("\nIn our cleartext capture, we should see these patterns")
print("at transmission boundaries when Call Tone/Call End Tone are enabled.")