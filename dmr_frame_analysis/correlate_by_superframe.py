#!/usr/bin/env python3

import sqlite3
import glob
from datetime import datetime

# Get the latest two databases
databases = sorted(glob.glob("dmr_capture_*.db"))[-2:]

print(f"Correlating by superframe ID between:")
print(f"  DB1: {databases[0]}")
print(f"  DB2: {databases[1]}")

def analyze_database(db_file):
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    
    # Get radio ID
    cursor.execute("SELECT DISTINCT source_id FROM superframes WHERE source_id IS NOT NULL")
    source_id = cursor.fetchone()
    source_id = source_id[0] if source_id else "Unknown"
    
    # Get superframe data
    cursor.execute("""
        SELECT id, start_timestamp, slot, h_mi, c_mi, source_id, target_id
        FROM superframes
        ORDER BY start_timestamp
    """)
    superframes = cursor.fetchall()
    
    # Get AMBE frame counts per superframe
    frame_counts = {}
    
    # Get all AMBE tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S0'")
    tables = cursor.fetchall()
    
    for table_name in tables:
        table = table_name[0]
        cursor.execute(f"""
            SELECT superframe_id, COUNT(*) as count, AVG(mi_full) as avg_mi
            FROM {table}
            WHERE superframe_id IS NOT NULL
            GROUP BY superframe_id
        """)
        
        for sf_id, count, avg_mi in cursor.fetchall():
            if sf_id not in frame_counts:
                frame_counts[sf_id] = {
                    'total': 0,
                    'encrypted': 0,
                    'unencrypted': 0,
                    'tables': []
                }
            
            frame_counts[sf_id]['total'] += count
            
            if table.startswith('U_'):
                frame_counts[sf_id]['unencrypted'] += count
            else:
                frame_counts[sf_id]['encrypted'] += count
            
            frame_counts[sf_id]['tables'].append(table)
    
    db.close()
    
    return {
        'source_id': source_id,
        'superframes': superframes,
        'frame_counts': frame_counts
    }

# Analyze both databases
data1 = analyze_database(databases[0])
data2 = analyze_database(databases[1])

print(f"\nRadio {data1['source_id']}: {len(data1['superframes'])} superframes")
print(f"Radio {data2['source_id']}: {len(data2['superframes'])} superframes")

# Check superframe_id usage
sf_with_frames1 = sum(1 for sf_id in data1['frame_counts'] if data1['frame_counts'][sf_id]['total'] > 0)
sf_with_frames2 = sum(1 for sf_id in data2['frame_counts'] if data2['frame_counts'][sf_id]['total'] > 0)

print(f"\nSuperframes with AMBE data:")
print(f"  Radio {data1['source_id']}: {sf_with_frames1}/{len(data1['superframes'])}")
print(f"  Radio {data2['source_id']}: {sf_with_frames2}/{len(data2['superframes'])}")

# Find time-based correlations
correlations = []

for sf1 in data1['superframes']:
    sf1_id, sf1_time, sf1_slot, sf1_h_mi, sf1_c_mi, sf1_src, sf1_tgt = sf1
    sf1_timestamp = datetime.strptime(sf1_time, '%Y-%m-%d %H:%M:%S')
    
    for sf2 in data2['superframes']:
        sf2_id, sf2_time, sf2_slot, sf2_h_mi, sf2_c_mi, sf2_src, sf2_tgt = sf2
        sf2_timestamp = datetime.strptime(sf2_time, '%Y-%m-%d %H:%M:%S')
        
        time_diff = abs((sf1_timestamp - sf2_timestamp).total_seconds())
        
        if time_diff < 1.0:  # Within 1 second
            # Get frame counts
            fc1 = data1['frame_counts'].get(sf1_id, {'total': 0})
            fc2 = data2['frame_counts'].get(sf2_id, {'total': 0})
            
            correlations.append({
                'sf1_id': sf1_id,
                'sf2_id': sf2_id,
                'time1': sf1_timestamp,
                'time2': sf2_timestamp,
                'time_diff': time_diff,
                'frames1': fc1['total'],
                'frames2': fc2['total'],
                'encrypted1': fc1.get('encrypted', 0) > 0,
                'encrypted2': fc2.get('encrypted', 0) > 0,
                'same_slot': sf1_slot == sf2_slot
            })

print(f"\nFound {len(correlations)} time-correlated superframe pairs")

if correlations:
    # Analyze correlations
    exact_time_matches = sum(1 for c in correlations if c['time_diff'] == 0)
    same_slot_matches = sum(1 for c in correlations if c['same_slot'])
    
    print(f"  Exact time matches: {exact_time_matches}")
    print(f"  Same slot matches: {same_slot_matches}")
    
    # Frame count correlations
    frame_matches = sum(1 for c in correlations if c['frames1'] == c['frames2'] and c['frames1'] > 0)
    print(f"  Matching frame counts: {frame_matches}")
    
    # Encryption patterns
    both_encrypted = sum(1 for c in correlations if c['encrypted1'] and c['encrypted2'])
    both_unencrypted = sum(1 for c in correlations if not c['encrypted1'] and not c['encrypted2'])
    mixed = sum(1 for c in correlations if c['encrypted1'] != c['encrypted2'])
    
    print(f"\nEncryption patterns:")
    print(f"  Both encrypted: {both_encrypted}")
    print(f"  Both unencrypted: {both_unencrypted}")
    print(f"  Mixed (one encrypted): {mixed}")
    
    # Show sample correlations
    print(f"\nSample correlations (first 10):")
    print("SF1 ID | SF2 ID | Time Diff | Frames1 | Frames2 | Enc1 | Enc2 | Same Slot")
    print("-" * 70)
    
    for c in correlations[:10]:
        print(f"{c['sf1_id']:6d} | {c['sf2_id']:6d} | {c['time_diff']:9.3f} | "
              f"{c['frames1']:7d} | {c['frames2']:7d} | "
              f"{'Y' if c['encrypted1'] else 'N':4s} | "
              f"{'Y' if c['encrypted2'] else 'N':4s} | "
              f"{'Y' if c['same_slot'] else 'N'}")

# Check if superframe_id is being properly set in AMBE tables
print("\nSuperframe ID validation:")

for db_file, data in [(databases[0], data1), (databases[1], data2)]:
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S0'")
    tables = cursor.fetchall()
    
    for table_name in tables:
        table = table_name[0]
        
        # Check for NULL superframe_ids
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE superframe_id IS NULL")
        null_count = cursor.fetchone()[0]
        
        # Check for invalid superframe_ids
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM {table} 
            WHERE superframe_id IS NOT NULL 
            AND superframe_id NOT IN (SELECT id FROM superframes)
        """)
        invalid_count = cursor.fetchone()[0]
        
        if null_count > 0 or invalid_count > 0:
            print(f"  {db_file} - {table}: {null_count} NULL, {invalid_count} invalid")
    
    db.close()