#!/usr/bin/env python3
"""
Analyze transmission gaps using superframe IDs and timestamps
"""
import sqlite3
from datetime import datetime

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def analyze_transmissions(db_path):
    """Analyze transmission patterns and gaps"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all superframes with timestamps and MI values
    cur.execute("""
        SELECT id, start_timestamp, h_mi, c_mi, source_id, target_id
        FROM superframes
        ORDER BY start_timestamp, id
    """)
    
    superframes = cur.fetchall()
    
    print("Transmission Analysis:")
    print("=" * 60)
    
    prev_timestamp = None
    prev_c_mi = None
    h_mi = 0x6C8AB637
    
    for i, (sf_id, timestamp, h_mi_val, c_mi_val, src, tgt) in enumerate(superframes):
        # Skip if no MI values
        if not c_mi_val:
            continue
            
        # Parse timestamp
        ts = datetime.fromisoformat(timestamp)
        
        # Calculate gap from previous
        gap_seconds = 0
        if prev_timestamp:
            gap_seconds = (ts - prev_timestamp).total_seconds()
        
        print(f"\nSuperframe {sf_id}:")
        print(f"  Time: {timestamp}")
        if prev_timestamp:
            print(f"  Gap: {gap_seconds:.1f} seconds")
            if gap_seconds > 1.0:
                print(f"  *** TRANSMISSION GAP DETECTED ***")
        
        print(f"  Source: {src}, Target: {tgt}")
        print(f"  H_MI: 0x{h_mi_val:08x}")
        print(f"  C_MI: 0x{c_mi_val:08x}")
        
        # Check LFSR progression
        if prev_c_mi and h_mi_val == h_mi:
            # Calculate expected next MI
            expected = dmr_lfsr_next(prev_c_mi)
            
            # Check if it matches
            if c_mi_val == expected:
                print(f"  LFSR: ✓ Sequential (expected 0x{expected:08x})")
            else:
                # Find actual position
                mi = h_mi
                for step in range(32767):
                    mi = dmr_lfsr_next(mi)
                    if mi == c_mi_val:
                        print(f"  LFSR: Gap detected - jumped to step {step+1}")
                        
                        # Calculate how many steps were skipped
                        prev_mi = h_mi
                        prev_step = 0
                        for s in range(32767):
                            prev_mi = dmr_lfsr_next(prev_mi)
                            if prev_mi == prev_c_mi:
                                prev_step = s + 1
                                break
                        
                        if prev_step:
                            skipped = step + 1 - prev_step - 1
                            print(f"  LFSR: Skipped {skipped} steps (from {prev_step} to {step+1})")
                        break
        
        prev_timestamp = ts
        prev_c_mi = c_mi_val
    
    # Now analyze AMBE frame tables
    print("\n\nAMBE Frame Analysis:")
    print("=" * 60)
    
    # Get all AMBE tables
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')
        ORDER BY name
    """)
    
    tables = cur.fetchall()
    
    for table in tables:
        table_name = table[0]
        parts = table_name.split('_')
        mi_value = int(parts[1], 16)
        
        # Get frame details with superframe correlation
        cur.execute(f"""
            SELECT COUNT(*), MIN(superframe_id), MAX(superframe_id)
            FROM {table_name}
        """)
        
        count, min_sf, max_sf = cur.fetchone()
        
        if count > 0:
            print(f"\n{table_name}:")
            print(f"  MI: 0x{mi_value:08x}")
            print(f"  Frames: {count}")
            print(f"  Superframes: {min_sf} to {max_sf}")
            
            # Get timestamps for this MI
            cur.execute(f"""
                SELECT DISTINCT superframe_id, timestamp
                FROM {table_name}
                ORDER BY superframe_id
            """)
            
            sf_times = cur.fetchall()
            if len(sf_times) > 1:
                print(f"  Appears in {len(sf_times)} different transmissions:")
                prev_ts = None
                for sf_id, ts_str in sf_times:
                    ts = datetime.fromisoformat(ts_str)
                    gap = ""
                    if prev_ts:
                        gap_sec = (ts - prev_ts).total_seconds()
                        gap = f" (gap: {gap_sec:.1f}s)"
                    print(f"    SF {sf_id}: {ts_str}{gap}")
                    prev_ts = ts
    
    conn.close()

if __name__ == "__main__":
    # Analyze Radio 1234 (encrypted)
    print("=== Radio 1234 (Encrypted) ===")
    analyze_transmissions("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234505.db")
    
    print("\n\n=== Radio 6969 (Unencrypted) ===")
    analyze_transmissions("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234506.db")