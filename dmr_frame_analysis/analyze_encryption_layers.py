#!/usr/bin/env python3
"""Analyze DMR encryption layers and attack feasibility"""

import sqlite3
from collections import defaultdict

# Database files
dbs = {
    'encrypted_key1': "dmr_capture_20250518_112024_998484.db",
    'encrypted_key2': "dmr_capture_20250518_115502_684984.db",
    'cleartext': "dmr_capture_20250518_112958_062803.db"
}

print("=== DMR ENCRYPTION LAYERS ANALYSIS ===")

# Collect statistics
stats = {}
for label, db_file in dbs.items():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get AMBE frame count
    ambe_count = 0
    
    # For encrypted, check C_*_S* tables
    if 'encrypted' in label:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%_S_'")
        for table in cursor.fetchall():
            cursor.execute(f"SELECT COUNT(*) FROM '{table[0]}'")
            ambe_count += cursor.fetchone()[0]
    else:
        # For cleartext, check U_*_S* tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'U_%_S_'")
        for table in cursor.fetchall():
            cursor.execute(f"SELECT COUNT(*) FROM '{table[0]}'")
            ambe_count += cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM superframes")
    superframe_count = cursor.fetchone()[0]
    
    stats[label] = {
        'superframes': superframe_count,
        'ambe_frames': ambe_count,
        'audio_seconds': ambe_count * 0.02
    }
    
    conn.close()

# Display results
for label, stat in stats.items():
    print(f"\n{label.upper()}:")
    print(f"  Superframes: {stat['superframes']}")
    print(f"  AMBE frames: {stat['ambe_frames']}")
    print(f"  Audio duration: {stat['audio_seconds']:.1f}s ({stat['audio_seconds']/60:.1f} min)")

print("\n=== UNDERSTANDING THE LAYERS ===")
print("\n1. RC4 Traffic Encryption (when enabled):")
print("   - Uses MI values as Initialization Vectors")
print("   - Encrypts the entire DMR payload including AMBE")
print("   - Fixed H-MI (0x6C8AB637) + predictable C-MI = vulnerability")

print("\n2. AMBE Voice Codec:")
print("   - NOT encryption, just voice compression")
print("   - 49-bit frames represent 20ms of audio")
print("   - In encrypted mode: AMBE is encrypted by RC4")
print("   - In cleartext mode: AMBE is transmitted unencrypted")

print("\n=== ATTACK FEASIBILITY ===")
print("\n✓ What we have:")
print(f"  - {stats['encrypted_key1']['audio_seconds'] + stats['encrypted_key2']['audio_seconds']:.1f}s encrypted audio")
print(f"  - {stats['cleartext']['audio_seconds']:.1f}s cleartext audio")
print("  - 100% accurate LFSR prediction for next C-MI")
print("  - Same MI sequence across different encryption keys")

print("\n⚠️ Challenge:")
print("  - Cleartext doesn't use MI values")
print("  - Can't directly XOR cleartext/encrypted with same IV")
print("  - Need different approach")

print("\n💡 Attack Options:")
print("1. Statistical analysis of AMBE patterns")
print("2. Known plaintext attack if same audio transmitted both ways")
print("3. Exploit fixed H-MI and LFSR predictability for future captures")
print("4. Analyze if any AMBE patterns repeat across MI values")

print("\n=== IMMEDIATE ACTION ===")
print("To demonstrate the vulnerability:")
print("1. Transmit identical audio on both encrypted and cleartext")
print("2. Capture when encrypted uses a known C-MI value")
print("3. Use the 318s of encrypted audio for pattern analysis")
print("4. The fact all encrypted radios share MI sequence is the key vulnerability")