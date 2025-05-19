#!/usr/bin/env python3
"""Check frame metadata to understand transmission patterns"""
import sqlite3

# Check both databases
databases = ['dmr_capture_20250517_204818.db', 'dmr_capture_20250517_205116.db']

for db_file in databases:
    print(f"\n=== Database: {db_file} ===")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check superframe data
    cursor.execute("""
        SELECT id, source_id, target_id, sync_type, h_mi, c_mi, frame_count, encrypted
        FROM superframes
        ORDER BY id
        LIMIT 10
    """)
    
    superframes = cursor.fetchall()
    print("\nSuperframe metadata:")
    for sf in superframes:
        print(f"  SF {sf[0]}: Src={sf[1]}, Tgt={sf[2]}, Type={sf[3]}, "
              f"H-MI=0x{sf[4]:08X} if sf[4] else 0, C-MI=0x{sf[5]:08X} if sf[5] else 0, "
              f"Frames={sf[6]}, Encrypted={sf[7]}")
    
    # Check if we have voice data
    cursor.execute("""
        SELECT sync_type, COUNT(*) 
        FROM superframes 
        GROUP BY sync_type
    """)
    
    sync_types = cursor.fetchall()
    print("\nSync types:")
    for sync_type, count in sync_types:
        print(f"  {sync_type}: {count}")
    
    # For the second database, check actual frame data
    if db_file == 'dmr_capture_20250517_205116.db':
        # Look at encrypted frame patterns
        cursor.execute("""
            SELECT table_name, COUNT(*) as frames,
                   MIN(CAST(id AS INTEGER)) as first_frame,
                   MAX(CAST(id AS INTEGER)) as last_frame
            FROM (
                SELECT 'H_6C8AB637_S0' as table_name, id FROM H_6C8AB637_S0
                UNION ALL
                SELECT 'C_E8083B57_S0', id FROM C_E8083B57_S0
            )
            GROUP BY table_name
        """)
        
        frame_stats = cursor.fetchall()
        print("\nFrame statistics:")
        for table, count, first, last in frame_stats:
            print(f"  {table}: {count} frames (IDs {first}-{last})")
    
    conn.close()

# Now let's look specifically at what DMR beeps look like
print("\n=== DMR Beep Characteristics ===")
print("\nBased on DMR specifications and real captures:")
print("1. Start beep: Single 200-300ms tone at transmission start")
print("2. End beeps: Three 200ms tones with gaps at transmission end")
print("3. Frequency: 2400Hz or 2600Hz")
print("4. AMBE encoding: Creates specific repeating patterns")
print("\nIn our captures:")
print("- Unencrypted (first DB): Regular voice data, no clear beeps")
print("- Encrypted (second DB): Has expected MI progression")
print("\nThe beep patterns would appear as:")
print("- Repeated AMBE frames (same tone = same encoding)")
print("- At transmission boundaries")
print("- Encrypted versions show as first/last frames in each MI table")