#!/usr/bin/env python3

import sqlite3
import glob
from collections import defaultdict
import struct

# Get the latest two databases
databases = sorted(glob.glob("dmr_capture_*.db"))[-2:]

print(f"Analyzing plaintext-ciphertext correlation between:")
print(f"  Unencrypted: {databases[0]}")  # Radio 6969
print(f"  Encrypted: {databases[1]}")    # Radio 1234

def get_matching_frames(db_unenc, db_enc):
    """Find frames that match by timestamp and extract plaintext/ciphertext pairs"""
    
    conn_unenc = sqlite3.connect(db_unenc)
    conn_enc = sqlite3.connect(db_enc)
    
    # Get unencrypted frames
    cursor_unenc = conn_unenc.cursor()
    cursor_unenc.execute("""
        SELECT a.timestamp, a.ambe_hex, s.start_timestamp, a.superframe_id
        FROM U_00000000_S0 a
        JOIN superframes s ON a.superframe_id = s.id
        ORDER BY a.timestamp
    """)
    unenc_frames = {row[0]: row for row in cursor_unenc.fetchall()}
    
    # Get encrypted frames with matching timestamps
    matching_pairs = []
    
    cursor_enc = conn_enc.cursor()
    
    # Get all encrypted tables
    cursor_enc.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')")
    enc_tables = cursor_enc.fetchall()
    
    for table_name in enc_tables:
        table = table_name[0]
        mi_value = table.split('_')[1]  # Extract MI from table name
        
        cursor_enc.execute(f"""
            SELECT a.timestamp, a.ambe_hex, s.start_timestamp, a.superframe_id, a.mi_full
            FROM {table} a
            JOIN superframes s ON a.superframe_id = s.id
            WHERE a.timestamp IN ({','.join(['?']*len(unenc_frames))})
            ORDER BY a.timestamp
        """, list(unenc_frames.keys()))
        
        for enc_row in cursor_enc.fetchall():
            timestamp = enc_row[0]
            if timestamp in unenc_frames:
                unenc_row = unenc_frames[timestamp]
                matching_pairs.append({
                    'timestamp': timestamp,
                    'plaintext': unenc_row[1],  # AMBE hex from unencrypted
                    'ciphertext': enc_row[1],   # AMBE hex from encrypted
                    'mi': enc_row[4],
                    'table': table,
                    'sf_time_unenc': unenc_row[2],
                    'sf_time_enc': enc_row[2],
                    'sf_id_unenc': unenc_row[3],
                    'sf_id_enc': enc_row[3]
                })
    
    conn_unenc.close()
    conn_enc.close()
    
    return matching_pairs

# Get matching frames
pairs = get_matching_frames(databases[0], databases[1])

print(f"\nFound {len(pairs)} matching plaintext-ciphertext pairs")

if pairs:
    # Group by MI value
    by_mi = defaultdict(list)
    for pair in pairs:
        by_mi[pair['mi']].append(pair)
    
    print(f"Unique MI values: {len(by_mi)}")
    
    # Analyze patterns for each MI
    for mi, mi_pairs in sorted(by_mi.items())[:5]:  # First 5 MIs
        print(f"\nMI: {mi} ({mi:08X}) - {len(mi_pairs)} pairs")
        
        # Look for XOR patterns
        xor_patterns = []
        
        for i, pair in enumerate(mi_pairs[:5]):  # First 5 pairs
            pt_bytes = bytes.fromhex(pair['plaintext'])
            ct_bytes = bytes.fromhex(pair['ciphertext'])
            
            # Calculate XOR
            xor_result = bytes(a ^ b for a, b in zip(pt_bytes, ct_bytes))
            
            print(f"  Pair {i}:")
            print(f"    Plaintext:  {pair['plaintext']}")
            print(f"    Ciphertext: {pair['ciphertext']}")
            print(f"    XOR:        {xor_result.hex().upper()}")
            
            xor_patterns.append(xor_result)
        
        # Check if XOR patterns are consistent (would indicate stream cipher)
        if len(xor_patterns) > 1:
            all_same = all(xp == xor_patterns[0] for xp in xor_patterns[1:])
            if all_same:
                print(f"  *** XOR pattern is CONSTANT for MI {mi:08X} ***")
            else:
                print(f"  XOR patterns vary for MI {mi:08X}")
    
    # Look for LFSR progression
    print("\n\nAnalyzing LFSR/RC4 characteristics:")
    
    # Get consecutive frames
    sorted_pairs = sorted(pairs, key=lambda x: x['timestamp'])
    
    # Track keystream bytes
    keystream_by_position = defaultdict(list)
    
    for pair in sorted_pairs[:100]:  # First 100 pairs
        pt_bytes = bytes.fromhex(pair['plaintext'])
        ct_bytes = bytes.fromhex(pair['ciphertext'])
        
        # Extract keystream (plaintext XOR ciphertext = keystream)
        keystream = bytes(a ^ b for a, b in zip(pt_bytes, ct_bytes))
        
        for pos, byte in enumerate(keystream):
            keystream_by_position[pos].append((pair['mi'], byte))
    
    # Check for repeating patterns in keystream
    print("\nKeystream byte analysis (first 8 bytes):")
    for pos in range(min(8, len(keystream_by_position))):
        bytes_at_pos = keystream_by_position[pos]
        
        # Group by MI
        by_mi_pos = defaultdict(list)
        for mi, byte in bytes_at_pos:
            by_mi_pos[mi].append(byte)
        
        print(f"\nByte position {pos}:")
        for mi, bytes_list in sorted(by_mi_pos.items())[:3]:
            unique_bytes = set(bytes_list)
            if len(unique_bytes) == 1:
                print(f"  MI {mi:08X}: Constant byte {unique_bytes.pop():02X}")
            else:
                print(f"  MI {mi:08X}: {len(unique_bytes)} different values")
    
    # Check for Call End pattern
    print("\n\nLooking for Call End (5555 pattern) correlations:")
    
    call_end_pattern = "5555555555555555"
    end_pairs = [p for p in pairs if p['plaintext'].startswith(call_end_pattern)]
    
    print(f"Found {len(end_pairs)} potential Call End frames")
    
    if end_pairs:
        print("\nCall End analysis:")
        for i, pair in enumerate(end_pairs[:5]):
            print(f"\n  End frame {i}:")
            print(f"    MI:         {pair['mi']:08X}")
            print(f"    Plaintext:  {pair['plaintext']}")
            print(f"    Ciphertext: {pair['ciphertext']}")
            
            # Calculate keystream
            pt_bytes = bytes.fromhex(pair['plaintext'])
            ct_bytes = bytes.fromhex(pair['ciphertext'])
            keystream = bytes(a ^ b for a, b in zip(pt_bytes, ct_bytes))
            
            print(f"    Keystream:  {keystream.hex().upper()}")
            
            # Check if this matches expected RC4 output
            # with known polynomial x^32 + x^4 + x^2 + 1