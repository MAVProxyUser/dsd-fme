#!/usr/bin/env python3
"""Demonstrate what we can and cannot see in encrypted vs cleartext DMR"""

import sqlite3

def compare_visibility():
    encrypted_db = "dmr_capture_20250518_112024_998484.db"
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    
    print("=== ENCRYPTED vs CLEARTEXT VISIBILITY ===\n")
    
    # Analyze encrypted database
    print("1. ENCRYPTED DATABASE:")
    conn_enc = sqlite3.connect(encrypted_db)
    cursor_enc = conn_enc.cursor()
    
    # What we CAN see in encrypted
    cursor_enc.execute("SELECT id, sync_type, slot, c_mi, h_mi FROM superframes LIMIT 5")
    print("\nWhat we CAN see (frame headers/metadata):")
    for row in cursor_enc.fetchall():
        print(f"  ID: {row[0]}, Type: {row[1]}, Slot: {row[2]}, C-MI: {row[3]:08X}, H-MI: {row[4]:08X}")
    
    # What we CANNOT see (encrypted AMBE)
    cursor_enc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%_S0' LIMIT 1")
    enc_table = cursor_enc.fetchone()[0]
    cursor_enc.execute(f"SELECT ambe_hex FROM '{enc_table}' LIMIT 5")
    
    print("\nWhat we CANNOT see (encrypted AMBE payloads):")
    for row in cursor_enc.fetchall():
        print(f"  Encrypted AMBE: {row[0]} <- This is RC4 encrypted!")
    
    conn_enc.close()
    
    # Analyze cleartext database
    print("\n\n2. CLEARTEXT DATABASE:")
    conn_clr = sqlite3.connect(cleartext_db)
    cursor_clr = conn_clr.cursor()
    
    # What we see in cleartext
    cursor_clr.execute("SELECT id, sync_type, slot FROM superframes LIMIT 5")
    print("\nWhat we see (frame headers):")
    for row in cursor_clr.fetchall():
        print(f"  ID: {row[0]}, Type: {row[1]}, Slot: {row[2]} (no MI values)")
    
    # Clear AMBE we can see
    cursor_clr.execute("SELECT ambe_hex FROM U_00000000_S0 LIMIT 5")
    print("\nWhat we see (cleartext AMBE):")
    for row in cursor_clr.fetchall():
        print(f"  Clear AMBE: {row[0]} <- Raw vocoder data!")
    
    conn_clr.close()
    
    print("\n\n=== KEY UNDERSTANDING ===")
    print("1. MS_VOICE is the frame type - we see this in BOTH encrypted and cleartext")
    print("2. The AMBE payload is what's encrypted - this is our attack surface")
    print("3. In encrypted frames:")
    print("   - We see: sync_type, slot, color_code, MI values")
    print("   - We DON'T see: actual voice data (it's RC4 encrypted)")
    print("4. In cleartext frames:")
    print("   - We see: everything including raw AMBE")
    print("   - No MI values (not needed without encryption)")
    
    print("\n=== ATTACK VECTORS ===")
    print("1. IV REUSE: Same C-MI = same keystream")
    print("2. FRAME STRUCTURE: AMBE has predictable patterns")
    print("3. VOCODER CHARACTERISTICS:")
    print("   - Silence frames: often 0x0000... or specific patterns")
    print("   - Voice patterns: frequency ranges, transitions")
    print("   - Static/noise: predictable spectral patterns")
    print("4. TIMING: Frames at same position likely similar")
    print("5. KNOWN PLAINTEXT: If we transmit known audio")
    
    print("\n=== WHAT WE'RE ACTUALLY BREAKING ===")
    print("The RC4 stream cipher encrypting the AMBE payloads")
    print("NOT the frame headers or DMR protocol - those are visible!")

if __name__ == "__main__":
    compare_visibility()