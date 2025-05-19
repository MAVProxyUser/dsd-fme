#!/usr/bin/env python3
"""Analyze encrypted beep patterns in DMR frames"""
import sqlite3
import struct
from collections import Counter

def analyze_encrypted_frame(ambe_hex):
    """Analyze an encrypted AMBE frame for patterns"""
    # Convert hex to bytes
    ambe_bytes = bytes.fromhex(ambe_hex)
    
    # Convert to 64-bit integer for easier analysis
    ambe_int = int.from_bytes(ambe_bytes, byteorder='big')
    
    # Check for patterns
    byte_values = [b for b in ambe_bytes]
    unique_bytes = len(set(byte_values))
    
    # Check for specific patterns that might indicate encrypted beeps
    has_pattern = False
    
    # Look for byte repetitions
    byte_counts = Counter(byte_values)
    max_repeat = max(byte_counts.values())
    
    return {
        'hex': ambe_hex,
        'bytes': byte_values,
        'unique_bytes': unique_bytes,
        'max_repeat': max_repeat,
        'int_value': ambe_int
    }

# Connect to database
conn = sqlite3.connect('dmr_capture_20250517_205116.db')
cursor = conn.cursor()

print("=== DMR Encrypted Beep Pattern Analysis ===\n")

# Encrypted beeps are XORed with keystream, but patterns still visible
print("1. First frames in each MI table (likely transmission start with beep):")

# Get all C-MI tables
cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name LIKE 'C_%'
    ORDER BY name
""")

c_tables = cursor.fetchall()

for table_name, in c_tables:
    # Get first few frames from each table
    cursor.execute(f"""
        SELECT ambe_hex, id 
        FROM {table_name} 
        ORDER BY id 
        LIMIT 3
    """)
    
    frames = cursor.fetchall()
    mi_value = table_name.split('_')[1]
    print(f"\n{table_name} (MI: 0x{mi_value}):")
    
    for ambe_hex, frame_id in frames:
        analysis = analyze_encrypted_frame(ambe_hex)
        print(f"  Frame {frame_id}: {ambe_hex}")
        print(f"    Unique bytes: {analysis['unique_bytes']}, Max repeat: {analysis['max_repeat']}")

# Look for patterns across frames
print("\n2. Looking for encrypted beep signatures:")

# Get frames that might be at transmission boundaries
cursor.execute("""
    SELECT c.table_name, c.ambe_hex, c.id
    FROM (
        SELECT name as table_name, ambe_hex, id,
               ROW_NUMBER() OVER (PARTITION BY name ORDER BY id) as rn,
               ROW_NUMBER() OVER (PARTITION BY name ORDER BY id DESC) as rn_desc
        FROM C_E8083B57_S0
        UNION ALL
        SELECT name as table_name, ambe_hex, id,
               ROW_NUMBER() OVER (PARTITION BY name ORDER BY id) as rn,
               ROW_NUMBER() OVER (PARTITION BY name ORDER BY id DESC) as rn_desc
        FROM C_4F36EE3A_S0
    ) c
    WHERE c.rn <= 3 OR c.rn_desc <= 3
""")

# Simpler query
cursor.execute("""
    SELECT ambe_hex FROM C_E8083B57_S0 
    ORDER BY id LIMIT 3
""")
start_frames = cursor.fetchall()

cursor.execute("""
    SELECT ambe_hex FROM C_E8083B57_S0 
    ORDER BY id DESC LIMIT 3
""")
end_frames = cursor.fetchall()

print("\nTransmission start frames (C_E8083B57_S0):")
for frame, in start_frames:
    print(f"  {frame}")

print("\nTransmission end frames (C_E8083B57_S0):")
for frame, in reversed(end_frames):
    print(f"  {frame}")

# Analyze the actual unencrypted beep pattern from our previous captures
print("\n3. Known DMR beep characteristics (from unencrypted analysis):")
print("- Single beep at transmission start: ~200-300ms")
print("- Triple beep at transmission end: 3x ~200ms beeps")
print("- Beep frequency: typically 2400Hz or 2600Hz")
print("- AMBE encoding creates specific patterns")

print("\n4. What encrypted beeps look like:")
print("- Beep pattern XORed with RC4 keystream")
print("- Same beep + same position = same ciphertext")
print("- Pattern still detectable across multiple transmissions")
print("- Keystream recovery: K = C ⊕ P (known beep)")

# Show example of keystream recovery
print("\n5. Keystream Recovery Example:")
print("If we know the plaintext beep pattern P and have ciphertext C:")
print("Keystream K = C ⊕ P")
print("\nThen for any other frame at same position:")
print("Plaintext = Ciphertext ⊕ K")

conn.close()

print("\n=== Summary ===")
print("Encrypted beeps are valuable because:")
print("1. Known plaintext at predictable positions")
print("2. Same MI position = same keystream")
print("3. Beeps occur at every transmission start/end")
print("4. Pattern is consistent across radios")