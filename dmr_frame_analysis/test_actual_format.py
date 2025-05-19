#!/usr/bin/env python3
"""Test with actual MD380 expected format based on source analysis"""

import sqlite3
import struct

def test_actual_md380_format():
    # Based on md380_vocoder source, it expects:
    # - AMBE+2 frames: 49 bits packed into specific format
    # - Each frame: 49 bits of AMBE data + FEC
    
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn = sqlite3.connect(cleartext_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT ambe_hex FROM U_00000000_S0 LIMIT 20")
    frames = cursor.fetchall()
    
    # MD380 format appears to expect 7 bytes per frame
    with open("test_md380_format.bin", "wb") as f:
        for frame_hex, in frames:
            frame_int = int(frame_hex, 16)
            
            # Extract 49 bits and pack into 7 bytes
            # Try different bit positions based on DMR spec
            
            # Option 1: Lower 49 bits
            ambe_49 = frame_int & 0x1FFFFFFFFFFFF
            f.write(ambe_49.to_bytes(7, byteorder='big'))
    
    conn.close()
    print("Created test_md380_format.bin")

if __name__ == "__main__":
    test_actual_md380_format()
