#!/usr/bin/env python3

import sqlite3
import glob
from collections import defaultdict

# Get all databases
databases = sorted(glob.glob("dmr_capture_*.db"))

for db_file in databases:
    print(f"\n{'='*60}")
    print(f"Checking database: {db_file}")
    print(f"{'='*60}")
    
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    
    # 1. Check superframes table
    cursor.execute("SELECT COUNT(*) FROM superframes")
    sf_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT source_id) as unique_sources,
            COUNT(DISTINCT target_id) as unique_targets,
            COUNT(DISTINCT h_mi) as unique_h_mi,
            COUNT(DISTINCT c_mi) as unique_c_mi,
            SUM(CASE WHEN source_id IS NOT NULL THEN 1 ELSE 0 END) as with_source,
            SUM(CASE WHEN target_id IS NOT NULL THEN 1 ELSE 0 END) as with_target,
            SUM(CASE WHEN h_mi IS NOT NULL THEN 1 ELSE 0 END) as with_h_mi,
            SUM(CASE WHEN c_mi IS NOT NULL THEN 1 ELSE 0 END) as with_c_mi
        FROM superframes
    """)
    
    stats = cursor.fetchone()
    
    print("\nSuperframes Table:")
    print(f"  Total superframes: {stats[0]}")
    print(f"  Unique source IDs: {stats[1]}")
    print(f"  Unique target IDs: {stats[2]}")
    print(f"  Unique H-MI values: {stats[3]}")
    print(f"  Unique C-MI values: {stats[4]}")
    print(f"  Superframes with source: {stats[5]} ({stats[5]/stats[0]*100:.1f}%)")
    print(f"  Superframes with target: {stats[6]} ({stats[6]/stats[0]*100:.1f}%)")
    print(f"  Superframes with H-MI: {stats[7]} ({stats[7]/stats[0]*100:.1f}%)")
    print(f"  Superframes with C-MI: {stats[8]} ({stats[8]/stats[0]*100:.1f}%)")
    
    # 2. Check AMBE tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S0'")
    ambe_tables = cursor.fetchall()
    
    print(f"\nAMBE Tables: {len(ambe_tables)}")
    
    h_tables = []
    c_tables = []
    u_tables = []
    
    for table_name in ambe_tables:
        table = table_name[0]
        cursor.execute(f"""
            SELECT 
                COUNT(*) as frame_count,
                COUNT(DISTINCT superframe_id) as sf_count,
                COUNT(CASE WHEN superframe_id IS NULL THEN 1 END) as null_sf
            FROM {table}
        """)
        
        frame_count, sf_count, null_sf = cursor.fetchone()
        
        if table.startswith('H_'):
            h_tables.append((table, frame_count, sf_count, null_sf))
        elif table.startswith('C_'):
            c_tables.append((table, frame_count, sf_count, null_sf))
        elif table.startswith('U_'):
            u_tables.append((table, frame_count, sf_count, null_sf))
    
    # Show table summaries
    if h_tables:
        print("\n  H-MI Tables:")
        for table, frames, sfs, nulls in h_tables[:3]:
            print(f"    {table}: {frames} frames, {sfs} superframes, {nulls} NULL sf_ids")
    
    if c_tables:
        print("\n  C-MI Tables:")
        for table, frames, sfs, nulls in c_tables[:3]:
            print(f"    {table}: {frames} frames, {sfs} superframes, {nulls} NULL sf_ids")
    
    if u_tables:
        print("\n  Unencrypted Tables:")
        for table, frames, sfs, nulls in u_tables[:3]:
            print(f"    {table}: {frames} frames, {sfs} superframes, {nulls} NULL sf_ids")
    
    # 3. Check correlations table
    cursor.execute("SELECT COUNT(*) FROM dmr_correlations")
    corr_count = cursor.fetchone()[0]
    
    print(f"\nCorrelations Table: {corr_count} entries")
    
    if corr_count > 0:
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT header_mi) as unique_h_mi,
                COUNT(DISTINCT control_mi) as unique_c_mi,
                COUNT(DISTINCT slot) as unique_slots
            FROM dmr_correlations
        """)
        
        corr_stats = cursor.fetchone()
        print(f"  Unique header MIs: {corr_stats[0]}")
        print(f"  Unique control MIs: {corr_stats[1]}")
        print(f"  Unique slots: {corr_stats[2]}")
    
    # 4. Check metadata table
    cursor.execute("SELECT COUNT(*) FROM dmr_metadata")
    meta_count = cursor.fetchone()[0]
    
    print(f"\nMetadata Table: {meta_count} entries")
    
    if meta_count > 0:
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT talkgroup) as unique_tg,
                COUNT(DISTINCT superframe_id) as unique_sf,
                COUNT(CASE WHEN superframe_id IS NULL THEN 1 END) as null_sf
            FROM dmr_metadata
        """)
        
        meta_stats = cursor.fetchone()
        print(f"  Unique talkgroups: {meta_stats[0]}")
        print(f"  Unique superframes: {meta_stats[1]}")
        print(f"  NULL superframe_ids: {meta_stats[2]}")
    
    # 5. Check superframe-to-ambe relationships
    print("\nSuperframe-to-AMBE Correlation Check:")
    
    # Sample check - first 5 superframes
    cursor.execute("SELECT id FROM superframes LIMIT 5")
    sf_ids = [row[0] for row in cursor.fetchall()]
    
    for sf_id in sf_ids:
        # Get superframe info
        cursor.execute("""
            SELECT slot, h_mi, c_mi, source_id, target_id 
            FROM superframes 
            WHERE id = ?
        """, (sf_id,))
        
        sf_info = cursor.fetchone()
        if sf_info:
            slot, h_mi, c_mi, source, target = sf_info
            
            print(f"\n  Superframe {sf_id}:")
            print(f"    Slot: {slot}, Source: {source}, Target: {target}")
            h_mi_str = f"{h_mi:08X}" if h_mi is not None else "None"
            c_mi_str = f"{c_mi:08X}" if c_mi is not None else "None"
            print(f"    H-MI: {h_mi_str}, C-MI: {c_mi_str}")
            
            # Count frames in each table for this superframe
            frame_counts = {}
            
            for table_name in ambe_tables:
                table = table_name[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE superframe_id = ?", (sf_id,))
                count = cursor.fetchone()[0]
                if count > 0:
                    frame_counts[table] = count
            
            if frame_counts:
                print("    AMBE frames:")
                for table, count in frame_counts.items():
                    print(f"      {table}: {count}")
            else:
                print("    No AMBE frames found")
    
    # 6. Check data integrity
    print("\n\nData Integrity Checks:")
    
    # Check for orphaned AMBE frames
    orphaned_count = 0
    for table_name in ambe_tables:
        table = table_name[0]
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM {table} a
            WHERE a.superframe_id IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM superframes s WHERE s.id = a.superframe_id)
        """)
        
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            orphaned_count += orphaned
            print(f"  {table} has {orphaned} orphaned frames")
    
    if orphaned_count == 0:
        print("  ✓ No orphaned AMBE frames")
    
    # Check for MI consistency
    cursor.execute("""
        SELECT COUNT(*)
        FROM superframes s
        JOIN dmr_correlations c ON s.h_mi = c.header_mi
        WHERE s.c_mi != c.control_mi
    """)
    
    inconsistent = cursor.fetchone()[0]
    if inconsistent > 0:
        print(f"  ⚠ {inconsistent} MI inconsistencies between superframes and correlations")
    else:
        print("  ✓ MI values consistent between tables")
    
    db.close()

print("\n\nSpot check complete.")
print("All databases have been analyzed for:")
print("- Superframe completeness")
print("- AMBE table relationships")
print("- Correlation data")
print("- Metadata integrity")
print("- Radio ID tracking")