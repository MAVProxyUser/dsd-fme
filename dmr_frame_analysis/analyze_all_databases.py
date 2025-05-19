#!/usr/bin/env python3
"""Analyze ALL DMR databases to list frame types across all captures"""

import sqlite3
import glob
from collections import defaultdict, Counter

def analyze_database(db_file):
    """Analyze a single database for frame types"""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    results = {
        'sync_types': Counter(),
        'flco_values': Counter(),
        'fid_values': Counter(),
        'data_formats': Counter(),
        'call_types': Counter(),
        'slots': Counter(),
        'color_codes': Counter(),
        'encrypted': 0,
        'cleartext': 0,
        'total_superframes': 0,
        'total_ambe': 0,
        'mi_tables': []
    }
    
    # Count sync types
    cursor.execute("SELECT sync_type, COUNT(*) FROM superframes GROUP BY sync_type")
    for sync_type, count in cursor.fetchall():
        results['sync_types'][sync_type] = count
    
    # Count FLCO values
    cursor.execute("SELECT flco, COUNT(*) FROM superframes WHERE flco IS NOT NULL GROUP BY flco")
    for flco, count in cursor.fetchall():
        results['flco_values'][flco] = count
    
    # Count FID values
    cursor.execute("SELECT fid, COUNT(*) FROM superframes WHERE fid IS NOT NULL GROUP BY fid")
    for fid, count in cursor.fetchall():
        results['fid_values'][fid] = count
    
    # Count data formats
    cursor.execute("SELECT data_format, COUNT(*) FROM superframes WHERE data_format IS NOT NULL GROUP BY data_format")
    for fmt, count in cursor.fetchall():
        results['data_formats'][fmt] = count
    
    # Count slots
    cursor.execute("SELECT slot, COUNT(*) FROM superframes GROUP BY slot")
    for slot, count in cursor.fetchall():
        results['slots'][slot] = count
    
    # Count color codes
    cursor.execute("SELECT color_code, COUNT(*) FROM superframes GROUP BY color_code")
    for cc, count in cursor.fetchall():
        results['color_codes'][cc] = count
    
    # Check encryption
    cursor.execute("SELECT COUNT(*) FROM superframes WHERE c_mi IS NOT NULL AND c_mi != 0")
    results['encrypted'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM superframes WHERE c_mi IS NULL OR c_mi = 0")
    results['cleartext'] = cursor.fetchone()[0]
    
    # Total superframes
    cursor.execute("SELECT COUNT(*) FROM superframes")
    results['total_superframes'] = cursor.fetchone()[0]
    
    # Count AMBE frames
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'C_%_S_' OR name LIKE 'U_%_S_')")
    for table in cursor.fetchall():
        table_name = table[0]
        results['mi_tables'].append(table_name)
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        results['total_ambe'] += cursor.fetchone()[0]
    
    # Call types
    cursor.execute("""
        SELECT 
            CASE 
                WHEN group_call = 1 THEN 'Group'
                WHEN emergency_call = 1 THEN 'Emergency'
                WHEN priority_call = 1 THEN 'Priority'
                ELSE 'Individual'
            END as call_type,
            COUNT(*) as count
        FROM superframes
        GROUP BY call_type
    """)
    
    for call_type, count in cursor.fetchall():
        results['call_types'][call_type] = count
    
    conn.close()
    return results

def main():
    print("=== ANALYZING ALL DMR CAPTURES ===\n")
    
    # Find all database files
    db_files = []
    # Check current directory
    db_files.extend(glob.glob("dmr_capture_*.db"))
    # Check DMR_Captures directory
    db_files.extend(glob.glob("/home/ubuntu/DMR_Captures/dmr_capture_*.db"))
    
    # Remove duplicates
    db_files = list(set(db_files))
    
    print(f"Found {len(db_files)} database files\n")
    
    # Analyze each database
    all_results = {}
    combined_stats = {
        'sync_types': Counter(),
        'flco_values': Counter(),
        'fid_values': Counter(),
        'data_formats': Counter(),
        'call_types': Counter(),
        'slots': Counter(),
        'color_codes': Counter(),
        'total_encrypted': 0,
        'total_cleartext': 0,
        'total_superframes': 0,
        'total_ambe': 0
    }
    
    for db_file in sorted(db_files):
        print(f"\n--- Analyzing: {db_file} ---")
        
        try:
            results = analyze_database(db_file)
            all_results[db_file] = results
            
            # Update combined stats
            for key in ['sync_types', 'flco_values', 'fid_values', 'data_formats', 
                       'call_types', 'slots', 'color_codes']:
                combined_stats[key].update(results[key])
            
            combined_stats['total_encrypted'] += results['encrypted']
            combined_stats['total_cleartext'] += results['cleartext']
            combined_stats['total_superframes'] += results['total_superframes']
            combined_stats['total_ambe'] += results['total_ambe']
            
            # Print summary for this database
            print(f"  Superframes: {results['total_superframes']}")
            print(f"  AMBE frames: {results['total_ambe']}")
            print(f"  Encrypted: {results['encrypted']}")
            print(f"  Cleartext: {results['cleartext']}")
            print(f"  Sync types: {dict(results['sync_types'])}")
            
        except Exception as e:
            print(f"  Error: {e}")
    
    # Print combined analysis
    print("\n=== COMBINED ANALYSIS OF ALL CAPTURES ===")
    
    print("\n1. TOTAL STATISTICS:")
    print(f"   Total databases: {len(all_results)}")
    print(f"   Total superframes: {combined_stats['total_superframes']}")
    print(f"   Total AMBE frames: {combined_stats['total_ambe']}")
    print(f"   Encrypted frames: {combined_stats['total_encrypted']}")
    print(f"   Cleartext frames: {combined_stats['total_cleartext']}")
    
    print("\n2. SYNC TYPES ACROSS ALL CAPTURES:")
    for sync_type, count in combined_stats['sync_types'].most_common():
        percentage = (count / combined_stats['total_superframes']) * 100
        print(f"   {sync_type}: {count} ({percentage:.1f}%)")
    
    print("\n3. FLCO VALUES:")
    for flco, count in combined_stats['flco_values'].most_common():
        print(f"   FLCO {flco}: {count}")
    
    print("\n4. FID VALUES:")
    for fid, count in combined_stats['fid_values'].most_common():
        print(f"   FID {fid}: {count}")
    
    print("\n5. DATA FORMATS:")
    for fmt, count in combined_stats['data_formats'].most_common():
        print(f"   Format {fmt}: {count}")
    
    print("\n6. CALL TYPES:")
    for call_type, count in combined_stats['call_types'].most_common():
        percentage = (count / combined_stats['total_superframes']) * 100
        print(f"   {call_type}: {count} ({percentage:.1f}%)")
    
    print("\n7. SLOT DISTRIBUTION:")
    for slot, count in combined_stats['slots'].most_common():
        percentage = (count / combined_stats['total_superframes']) * 100
        print(f"   Slot {slot}: {count} ({percentage:.1f}%)")
    
    print("\n8. COLOR CODES:")
    for cc, count in combined_stats['color_codes'].most_common():
        percentage = (count / combined_stats['total_superframes']) * 100
        print(f"   Color Code {cc}: {count} ({percentage:.1f}%)")
    
    # Categorize databases
    print("\n=== DATABASE CATEGORIZATION ===")
    
    encrypted_dbs = []
    cleartext_dbs = []
    mixed_dbs = []
    
    for db_file, results in all_results.items():
        if results['encrypted'] > 0 and results['cleartext'] == 0:
            encrypted_dbs.append(db_file)
        elif results['cleartext'] > 0 and results['encrypted'] == 0:
            cleartext_dbs.append(db_file)
        else:
            mixed_dbs.append(db_file)
    
    print(f"\nEncrypted-only databases: {len(encrypted_dbs)}")
    for db in encrypted_dbs:
        print(f"   {db}")
    
    print(f"\nCleartext-only databases: {len(cleartext_dbs)}")
    for db in cleartext_dbs:
        print(f"   {db}")
    
    print(f"\nMixed databases: {len(mixed_dbs)}")
    for db in mixed_dbs:
        print(f"   {db}")
    
    # Audio duration calculation
    audio_duration = combined_stats['total_ambe'] * 0.02  # 20ms per frame
    print(f"\n=== TOTAL AUDIO CAPTURED ===")
    print(f"Total audio duration: {audio_duration:.1f} seconds ({audio_duration/60:.1f} minutes)")

if __name__ == "__main__":
    main()