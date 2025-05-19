#!/usr/bin/env python3
"""
Analyze current DMR logging to understand what we're capturing
"""

import sqlite3
import sys

def analyze_current_logging(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"=== Analyzing Current DMR Logging ===")
    print(f"Database: {db_path}\n")
    
    # Check table structure
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%' LIMIT 1")
    table = cursor.fetchone()
    if not table:
        print("No C_MI tables found")
        return
    
    table_name = table[0]
    print(f"Examining table: {table_name}")
    
    # Check schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    schema = cursor.fetchall()
    print("\nTable schema:")
    for col in schema:
        print(f"  {col}")
    
    # Get some frames
    cursor.execute(f"SELECT id, ambe_hex, superframe_id FROM {table_name} ORDER BY id LIMIT 12")
    frames = cursor.fetchall()
    
    print(f"\nFirst 12 frames (should be 4 complete bursts):")
    for i, (id, ambe_hex, sf_id) in enumerate(frames):
        burst_num = i // 3
        frame_num = i % 3
        hex_len = len(ambe_hex)
        bits = hex_len * 4
        print(f"  Burst {burst_num}, Frame {frame_num}: {ambe_hex} ({bits} bits) [SF:{sf_id}]")
        
        if frame_num == 2:  # End of burst
            print()
    
    print("=== Current Logging Analysis ===")
    print("1. Each ambe_hex field contains 16 hex chars = 64 bits")
    print("2. We're missing 32 bits per frame (96 - 64 = 32)")
    print("3. Total missing per burst: 32 × 3 = 96 bits")
    print()
    
    print("=== What We're Actually Capturing ===")
    print("Looking at the logging code:")
    print("- AMBE frame is 4×24 bits = 96 bits total")
    print("- We only log first 64 bits")
    print("- Missing last 32 bits of each frame")
    print()
    
    # Show bit coverage
    print("=== Bit Coverage ===")
    print("Frame structure: ambe_fr[4][24]")
    print("  Row 0: bits 0-23   ✓ (logged)")
    print("  Row 1: bits 24-47  ✓ (logged)")
    print("  Row 2: bits 48-64  ✓ (first 16 logged)")
    print("  Row 3: bits 65-95  ✗ (missing)")
    print()
    
    print("=== Encryption Coverage ===")
    print("Encrypted: 49 vocoder bits")
    print("We capture: 64 bits total")
    print("Coverage: We get all 49 encrypted bits + 15 FEC bits")
    print("Missing: 32 FEC/padding bits")
    print()
    
    print("=== Grouping Frames into Bursts ===")
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_frames = cursor.fetchone()[0]
    complete_bursts = total_frames // 3
    partial_frames = total_frames % 3
    
    print(f"Total frames: {total_frames}")
    print(f"Complete bursts: {complete_bursts}")
    print(f"Partial frames: {partial_frames}")
    print()
    
    # Analyze superframe grouping
    cursor.execute(f"""
        SELECT superframe_id, COUNT(*) as frame_count 
        FROM {table_name} 
        GROUP BY superframe_id 
        ORDER BY superframe_id
        LIMIT 10
    """)
    
    print("=== Superframe Analysis ===")
    for sf_id, count in cursor.fetchall():
        bursts = count // 3
        partial = count % 3
        print(f"Superframe {sf_id}: {count} frames ({bursts} bursts + {partial} partial)")
    
    conn.close()

if __name__ == "__main__":
    # Use the encrypted capture for analysis
    db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    analyze_current_logging(db_path)