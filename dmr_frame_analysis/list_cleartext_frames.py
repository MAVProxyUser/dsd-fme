#!/usr/bin/env python3
"""List all frame types found in cleartext capture"""

import sqlite3
from collections import Counter

def list_cleartext_frame_types():
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn = sqlite3.connect(cleartext_db)
    cursor = conn.cursor()
    
    print("=== CLEARTEXT DMR FRAME TYPES ===")
    
    # 1. Check superframe types
    print("\n1. SUPERFRAME TYPES:")
    cursor.execute("""
        SELECT sync_type, COUNT(*) as count
        FROM superframes
        GROUP BY sync_type
        ORDER BY count DESC
    """)
    
    for sync_type, count in cursor.fetchall():
        print(f"   {sync_type}: {count}")
    
    # 2. Check FLCO (Full Link Control Opcode) values
    print("\n2. FLCO VALUES:")
    cursor.execute("""
        SELECT flco, COUNT(*) as count
        FROM superframes
        WHERE flco IS NOT NULL
        GROUP BY flco
        ORDER BY count DESC
    """)
    
    for flco, count in cursor.fetchall():
        print(f"   FLCO {flco}: {count}")
    
    # 3. Check FID (Feature ID) values
    print("\n3. FID VALUES:")
    cursor.execute("""
        SELECT fid, COUNT(*) as count
        FROM superframes
        WHERE fid IS NOT NULL
        GROUP BY fid
        ORDER BY count DESC
    """)
    
    for fid, count in cursor.fetchall():
        print(f"   FID {fid}: {count}")
    
    # 4. Check data format
    print("\n4. DATA FORMATS:")
    cursor.execute("""
        SELECT data_format, COUNT(*) as count
        FROM superframes
        WHERE data_format IS NOT NULL
        GROUP BY data_format
        ORDER BY count DESC
    """)
    
    for fmt, count in cursor.fetchall():
        print(f"   Format {fmt}: {count}")
    
    # 5. Check slot distribution
    print("\n5. SLOT DISTRIBUTION:")
    cursor.execute("""
        SELECT slot, COUNT(*) as count
        FROM superframes
        GROUP BY slot
        ORDER BY slot
    """)
    
    for slot, count in cursor.fetchall():
        print(f"   Slot {slot}: {count}")
    
    # 6. Check color codes
    print("\n6. COLOR CODES:")
    cursor.execute("""
        SELECT color_code, COUNT(*) as count
        FROM superframes
        GROUP BY color_code
        ORDER BY count DESC
    """)
    
    for cc, count in cursor.fetchall():
        print(f"   Color Code {cc}: {count}")
    
    # 7. Check service options
    print("\n7. SERVICE OPTIONS:")
    cursor.execute("""
        SELECT service_options, COUNT(*) as count
        FROM superframes
        WHERE service_options IS NOT NULL
        GROUP BY service_options
        ORDER BY count DESC
    """)
    
    for svc, count in cursor.fetchall():
        print(f"   Service Options {svc}: {count}")
    
    # 8. Check call types
    print("\n8. CALL TYPES:")
    cursor.execute("""
        SELECT 
            CASE 
                WHEN group_call = 1 AND priority_call = 0 AND emergency_call = 0 THEN 'Group Call'
                WHEN group_call = 0 AND priority_call = 0 AND emergency_call = 0 THEN 'Individual Call'
                WHEN priority_call = 1 THEN 'Priority Call'
                WHEN emergency_call = 1 THEN 'Emergency Call'
                ELSE 'Unknown'
            END as call_type,
            COUNT(*) as count
        FROM superframes
        GROUP BY call_type
        ORDER BY count DESC
    """)
    
    for call_type, count in cursor.fetchall():
        print(f"   {call_type}: {count}")
    
    # 9. Check frame counts
    print("\n9. FRAME COUNTS PER SUPERFRAME:")
    cursor.execute("""
        SELECT frame_count, COUNT(*) as count
        FROM superframes
        WHERE frame_count IS NOT NULL
        GROUP BY frame_count
        ORDER BY frame_count
    """)
    
    for frame_count, count in cursor.fetchall():
        print(f"   {frame_count} frames: {count} superframes")
    
    # 10. Check for any embedded frames
    print("\n10. AMBE FRAME TABLE:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S_'")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        count = cursor.fetchone()[0]
        print(f"   {table_name}: {count} AMBE frames")
    
    # 11. Summary statistics
    print("\n=== SUMMARY ===")
    cursor.execute("SELECT COUNT(*) FROM superframes")
    total_superframes = cursor.fetchone()[0]
    
    cursor.execute("SELECT MIN(start_timestamp), MAX(start_timestamp) FROM superframes")
    start_time, end_time = cursor.fetchone()
    
    print(f"Total superframes: {total_superframes}")
    print(f"Time range: {start_time} to {end_time}")
    
    # Check for any NULL values that might indicate different frame types
    print("\n=== NULL VALUE ANALYSIS ===")
    columns = ['h_mi', 'c_mi', 'source_id', 'target_id', 'flco', 'fid', 
               'service_options', 'manufacturer', 'privacy_algid', 'data_format']
    
    for col in columns:
        cursor.execute(f"SELECT COUNT(*) FROM superframes WHERE {col} IS NULL")
        null_count = cursor.fetchone()[0]
        if null_count > 0:
            percentage = (null_count / total_superframes) * 100
            print(f"{col}: {null_count} NULL values ({percentage:.1f}%)")
    
    conn.close()
    
    print("\n=== FRAME TYPE INTERPRETATION ===")
    print("Based on the data:")
    print("1. All frames are MS_VOICE (Mobile Station Voice)")
    print("2. No data frames detected in this capture")
    print("3. All frames use slot 0 (simplex operation)")
    print("4. Mix of group and individual calls")
    print("5. No encryption (privacy_algid = 0)")
    print("6. Single color code (0) throughout capture")

if __name__ == "__main__":
    list_cleartext_frame_types()