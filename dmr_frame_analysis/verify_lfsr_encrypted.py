#!/usr/bin/env python3
"""
Verify LFSR predictions on encrypted Radio 1234 data
"""
import sqlite3

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def predict_lfsr_sequence(start_mi, count):
    """Generate sequence of MI values"""
    mi = start_mi
    sequence = [mi]
    for _ in range(count):
        mi = dmr_lfsr_next(mi)
        sequence.append(mi)
    return sequence

def verify_lfsr_encrypted(db_path):
    """Verify LFSR predictions on encrypted transmissions"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # First check what H_MI and C_MI values we have
    print("Checking MI values from correlations:")
    cur.execute("""
        SELECT header_mi, control_mi, slot, algid
        FROM dmr_correlations
        ORDER BY header_mi, control_mi
    """)
    
    correlations = cur.fetchall()
    
    # Group by H_MI
    h_mi_groups = {}
    for h_mi, c_mi, slot, algid in correlations:
        if h_mi not in h_mi_groups:
            h_mi_groups[h_mi] = []
        h_mi_groups[h_mi].append(c_mi)
    
    for h_mi, c_mi_list in h_mi_groups.items():
        print(f"\nH_MI: 0x{h_mi:08x}")
        print(f"C_MI values: {[f'0x{x:08x}' for x in c_mi_list]}")
        
        # Check if this is our backdoor H_MI
        if h_mi == 0x6C8AB637:
            print("^^ This is the backdoor H_MI!")
            
            # Verify LFSR sequence
            print("\nVerifying LFSR predictions:")
            
            # Sort C_MI values
            c_mi_list_sorted = sorted(c_mi_list)
            
            # Check each C_MI
            for i, c_mi in enumerate(c_mi_list_sorted):
                # Predict what this should be based on LFSR
                expected = h_mi
                for _ in range(i+1):
                    expected = dmr_lfsr_next(expected)
                
                match = "✓" if c_mi == expected else "✗"
                print(f"  C_MI {i+1}: 0x{c_mi:08x} (expected: 0x{expected:08x}) {match}")
    
    # Now check the actual AMBE frames for each MI
    print("\n\nAnalyzing AMBE frames by MI:")
    
    # Get all encrypted tables
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')
        ORDER BY name
    """)
    
    tables = cur.fetchall()
    
    # Create MI mapping
    mi_to_frames = {}
    
    for table in tables:
        table_name = table[0]
        parts = table_name.split('_')
        mi_type = parts[0]  # H or C
        mi_value = int(parts[1], 16)
        
        # Get frame count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        
        if count > 0:
            # Get frame info
            cur.execute(f"SELECT mi_full, algid FROM {table_name} LIMIT 1")
            mi_full, algid = cur.fetchone()
            
            print(f"\n{table_name}:")
            print(f"  Type: {'Header' if mi_type == 'H' else 'Control'} MI")
            print(f"  MI: 0x{mi_value:08x}")
            print(f"  Frames: {count}")
            print(f"  AlgID: {algid}")
            
            if mi_type == 'C' and algid > 0:
                # Check against H_MI
                h_mi = 0x6C8AB637
                steps = 0
                test_mi = h_mi
                
                while steps < 32767:  # Full LFSR cycle
                    test_mi = dmr_lfsr_next(test_mi)
                    steps += 1
                    
                    if test_mi == mi_value:
                        print(f"  ✓ LFSR: {steps} steps from H_MI")
                        break
                else:
                    print(f"  ✗ Not in LFSR sequence from H_MI")
    
    conn.close()

if __name__ == "__main__":
    print("=== Verifying LFSR on Encrypted Radio 1234 ===")
    verify_lfsr_encrypted("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234505.db")