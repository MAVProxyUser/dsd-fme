#!/usr/bin/env python3
"""
Check all radio IDs in the capture
"""
import sqlite3
import glob

def check_radio_ids(db_path):
    """Check all radio IDs"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all superframes with IDs
    cur.execute("""
        SELECT id, source_id, target_id, group_call, start_timestamp, encrypted, slot
        FROM superframes
        ORDER BY id
    """)
    
    print("All transmissions:")
    print("-" * 80)
    print(f"{'ID':>4} {'Source':>10} {'Target':>10} {'Type':>8} {'Encrypted':>10} {'Slot':>5} {'Time'}")
    print("-" * 80)
    
    for row in cur.fetchall():
        id_, src, tgt, group, ts, enc, slot = row
        call_type = "Group" if group else "Private"
        enc_status = "Yes" if enc else "No"
        
        # Handle None values
        src_str = str(src) if src is not None else "None"
        tgt_str = str(tgt) if tgt is not None else "None"
        
        print(f"{id_:4d} {src_str:>10} {tgt_str:>10} {call_type:>8} {enc_status:>10} {slot:>5} {ts}")
        
        # Decode special IDs
        if src == 16777215 or tgt == 16777215:
            print("     ^^ All Call (Broadcast) detected!")
        if src == 6969:
            print("     ^^ Radio 6969 (Channel 2, No encryption)")
        if src == 1234:
            print("     ^^ Radio 1234 (Channel 2, Encrypted)")
    
    # Summary statistics
    cur.execute("""
        SELECT 
            COUNT(DISTINCT source_id) as unique_sources,
            COUNT(DISTINCT target_id) as unique_targets,
            COUNT(*) as total_transmissions,
            SUM(CASE WHEN encrypted = 1 THEN 1 ELSE 0 END) as encrypted_count,
            SUM(CASE WHEN encrypted = 0 THEN 1 ELSE 0 END) as unencrypted_count
        FROM superframes
    """)
    
    stats = cur.fetchone()
    print("\nSummary:")
    print(f"Unique source IDs: {stats[0]}")
    print(f"Unique target IDs: {stats[1]}")
    print(f"Total transmissions: {stats[2]}")
    print(f"Encrypted: {stats[3]}")
    print(f"Unencrypted: {stats[4]}")
    
    # Check the logs for more info
    print("\nChecking log files for radio IDs...")
    
    conn.close()

if __name__ == "__main__":
    db_files = sorted(glob.glob("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_*.db"))
    
    if db_files:
        latest_db = db_files[-1]
        print(f"Analyzing {latest_db}\n")
        check_radio_ids(latest_db)
        
        # Also check logs
        print("\nLog file contents:")
        try:
            with open("/home/ubuntu/dsd-fme_sqlite/build/logs/radio_6969.log", "r") as f:
                lines = f.readlines()[-20:]  # Last 20 lines
                print("\nRadio 6969 log (last 20 lines):")
                for line in lines:
                    if "All Call" in line or "16777215" in line or "6969" in line:
                        print(line.strip())
        except:
            pass
            
        try:
            with open("/home/ubuntu/dsd-fme_sqlite/build/logs/radio_1234.log", "r") as f:
                lines = f.readlines()[-20:]  # Last 20 lines
                print("\nRadio 1234 log (last 20 lines):")
                for line in lines:
                    if "All Call" in line or "16777215" in line or "1234" in line:
                        print(line.strip())
        except:
            pass