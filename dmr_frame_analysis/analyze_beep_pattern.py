#!/usr/bin/env python3
"""Analyze what the DMR beep patterns actually look like in AMBE frames"""
import sqlite3
import numpy as np
from collections import Counter

def ambe_to_bytes(ambe_hex):
    """Convert AMBE hex string to bytes"""
    return bytes.fromhex(ambe_hex)

def analyze_pattern(ambe_bytes):
    """Analyze patterns in AMBE data"""
    # Convert to numpy array for analysis
    data = np.frombuffer(ambe_bytes, dtype=np.uint8)
    
    # Check for patterns
    unique_values = len(np.unique(data))
    mean_val = np.mean(data)
    std_val = np.std(data)
    
    # Check for specific byte patterns that might indicate beeps
    # DMR beeps are typically tones at specific frequencies
    
    return {
        'unique_values': unique_values,
        'mean': mean_val,
        'std': std_val,
        'bytes': data.tolist(),
        'hex': ambe_bytes.hex()
    }

# Connect to database
conn = sqlite3.connect('dmr_capture_20250517_205116.db')
cursor = conn.cursor()

print("=== DMR Beep Pattern Analysis ===\n")

# Look at unencrypted frames first to see clear patterns
print("1. Unencrypted AMBE Frames (Clear Audio):")
cursor.execute("""
    SELECT ambe_hex, id 
    FROM U_00000000_S0 
    ORDER BY id 
    LIMIT 20
""")

unenc_frames = cursor.fetchall()
for i, (ambe_hex, frame_id) in enumerate(unenc_frames):
    ambe_bytes = ambe_to_bytes(ambe_hex)
    analysis = analyze_pattern(ambe_bytes)
    print(f"Frame {frame_id}: {ambe_hex}")
    print(f"  Unique values: {analysis['unique_values']}, Mean: {analysis['mean']:.2f}, Std: {analysis['std']:.2f}")
    
    # Look for potential beep indicators
    if analysis['std'] < 30:  # Low variance might indicate tone
        print(f"  ** Possible tone/beep - low variance")
    
    # Check for repeating patterns
    byte_counts = Counter(analysis['bytes'])
    if len(byte_counts) < 4:  # Few unique bytes
        print(f"  ** Possible pattern - only {len(byte_counts)} unique bytes")
    
    if i < 5:  # Show full hex for first few
        print(f"  Data: {analysis['hex']}\n")

# Now look at encrypted frames at transmission boundaries
print("\n2. Encrypted AMBE Frames (Transmission Start):")
cursor.execute("""
    SELECT h.ambe_hex, h.mi_full, h.id
    FROM H_6C8AB637_S0 h
    ORDER BY h.id
    LIMIT 5
""")

enc_start_frames = cursor.fetchall()
for i, (ambe_hex, mi, frame_id) in enumerate(enc_start_frames):
    ambe_bytes = ambe_to_bytes(ambe_hex)
    analysis = analyze_pattern(ambe_bytes)
    print(f"Frame {frame_id} (MI: 0x{mi:08X}):")
    print(f"  Hex: {ambe_hex}")
    print(f"  Decrypted would show beep pattern\n")

# Look for silence patterns (common at transmission boundaries)
print("3. Looking for Silence Patterns:")
cursor.execute("""
    SELECT ambe_hex, COUNT(*) as count
    FROM U_00000000_S0
    GROUP BY ambe_hex
    ORDER BY count DESC
    LIMIT 5
""")

common_patterns = cursor.fetchall()
print("Most common AMBE patterns (likely silence or tones):")
for pattern, count in common_patterns:
    print(f"  {pattern}: appears {count} times")
    # Analyze the pattern
    ambe_bytes = ambe_to_bytes(pattern)
    if all(b == 0 for b in ambe_bytes):
        print(f"    ** All zeros - definite silence")
    elif len(set(ambe_bytes)) < 3:
        print(f"    ** Very few unique bytes - likely tone or silence")

# Look for beep signature in DMR
print("\n4. Known DMR Beep Characteristics:")
print("- DMR beeps are typically 1-beep at start, 3-beeps at end")
print("- Beep frequency: usually 2400Hz or 2600Hz")
print("- Duration: ~200-500ms per beep")
print("- AMBE encodes these as specific bit patterns")

# Analyze a captured beep pattern if we can find one
cursor.execute("""
    SELECT ambe_hex
    FROM U_00000000_S0
    WHERE ambe_hex LIKE '%00000000%' OR ambe_hex LIKE '%FFFF%'
    LIMIT 10
""")

potential_beeps = cursor.fetchall()
if potential_beeps:
    print("\n5. Potential Beep/Silence Patterns Found:")
    for i, (pattern,) in enumerate(potential_beeps):
        print(f"  Pattern {i+1}: {pattern}")
        # Check if it's mostly zeros or ones
        ambe_bytes = ambe_to_bytes(pattern)
        zero_count = sum(1 for b in ambe_bytes if b == 0)
        ff_count = sum(1 for b in ambe_bytes if b == 0xFF)
        if zero_count > 4:
            print(f"    ** Contains {zero_count} zero bytes - likely silence")
        if ff_count > 2:
            print(f"    ** Contains {ff_count} 0xFF bytes - possible tone")

conn.close()

print("\n=== Beep Pattern Summary ===")
print("DMR beeps in AMBE frames typically show:")
print("1. Repeating patterns (tones have consistent frequency)")
print("2. Lower variance than speech")
print("3. Specific bit patterns for 2400/2600Hz tones")
print("4. Silence (zeros) between beeps")
print("5. 1 beep at transmission start, 3 beeps at end")