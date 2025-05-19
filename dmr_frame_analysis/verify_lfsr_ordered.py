#!/usr/bin/env python3
"""
Verify LFSR predictions with correct ordering
"""
import sqlite3

def dmr_lfsr_next(lfsr):
    """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
    return lfsr

def verify_lfsr_sequence(db_path):
    """Verify LFSR sequence in encrypted data"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # The backdoor H_MI
    h_mi = 0x6C8AB637
    print(f"Backdoor H_MI: 0x{h_mi:08x}")
    
    # Generate expected sequence
    print("\nExpected LFSR sequence:")
    mi = h_mi
    expected_sequence = []
    for i in range(10):
        mi = dmr_lfsr_next(mi)
        expected_sequence.append(mi)
        print(f"  Step {i+1}: 0x{mi:08x}")
    
    # Get actual C_MI values
    print("\nActual C_MI values found:")
    cur.execute("""
        SELECT DISTINCT control_mi 
        FROM dmr_correlations 
        WHERE header_mi = ?
        ORDER BY control_mi
    """, (h_mi,))
    
    actual_c_mis = [row[0] for row in cur.fetchall()]
    
    for c_mi in actual_c_mis:
        # Find position in sequence
        position = None
        for i, expected in enumerate(expected_sequence):
            if c_mi == expected:
                position = i + 1
                break
        
        if position:
            print(f"  0x{c_mi:08x} ✓ Found at position {position}")
        else:
            print(f"  0x{c_mi:08x} ✗ Not in expected sequence")
    
    # Show the actual order they appear in the database
    print("\nOrder of appearance in database:")
    cur.execute("""
        SELECT name, mi_full
        FROM (
            SELECT name, mi_full, MIN(id) as first_id
            FROM (
                SELECT 'H_6C8AB637_S0' as name, mi_full, id FROM H_6C8AB637_S0
                UNION ALL
                SELECT name, mi_full, id FROM C_E8083B57_S0
                UNION ALL
                SELECT name, mi_full, id FROM C_4F36EE3A_S0
                UNION ALL
                SELECT name, mi_full, id FROM C_752FEA1C_S0
                UNION ALL
                SELECT name, mi_full, id FROM C_9A0C201B_S0
                UNION ALL
                SELECT name, mi_full, id FROM C_D3C028BF_S0
            )
            GROUP BY name
        )
        ORDER BY first_id
    """)
    
    for i, (table_name, mi) in enumerate(cur.fetchall()):
        print(f"  {i+1}. {table_name}: 0x{mi:08x}")
        
        # Check if it matches expected sequence
        if mi == h_mi:
            print(f"      ^^ H_MI (start)")
        else:
            # Find position in LFSR sequence
            mi_test = h_mi
            for step in range(1, 100):
                mi_test = dmr_lfsr_next(mi_test)
                if mi_test == mi:
                    print(f"      ^^ {step} steps from H_MI")
                    break
    
    conn.close()

if __name__ == "__main__":
    print("=== LFSR Verification for Encrypted Radio 1234 ===")
    verify_lfsr_sequence("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_234505.db")