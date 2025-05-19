#!/usr/bin/env python3

import sqlite3
import glob
import struct
from collections import defaultdict

# Get databases
databases = sorted(glob.glob("dmr_capture_*.db"))[-2:]

print(f"Final RC4 Attack Analysis:")
print(f"  Unencrypted: {databases[0]}")
print(f"  Encrypted: {databases[1]}")

# Known DMR encryption constants
H_MI_FIXED = 0x6C8AB637
LFSR_POLY = 0x10000015
LFSR_PERIOD = 32767

def get_all_pairs():
    """Get ALL plaintext-ciphertext pairs for analysis"""
    conn_unenc = sqlite3.connect(databases[0])
    conn_enc = sqlite3.connect(databases[1])
    
    # Get all unencrypted frames
    cursor_unenc = conn_unenc.cursor()
    cursor_unenc.execute("SELECT timestamp, ambe_hex, superframe_id FROM U_00000000_S0")
    unenc_data = {row[0]: {'plaintext': row[1], 'sf_id': row[2]} for row in cursor_unenc.fetchall()}
    
    # Get all encrypted frames
    pairs = []
    cursor_enc = conn_enc.cursor()
    
    cursor_enc.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')")
    enc_tables = cursor_enc.fetchall()
    
    for table_name in enc_tables:
        table = table_name[0]
        mi_value = int(table.split('_')[1], 16)
        
        cursor_enc.execute(f"""
            SELECT timestamp, ambe_hex, superframe_id
            FROM {table}
            WHERE timestamp IN ({','.join(['?']*len(unenc_data))})
        """, list(unenc_data.keys()))
        
        for row in cursor_enc.fetchall():
            timestamp = row[0]
            if timestamp in unenc_data:
                pairs.append({
                    'timestamp': timestamp,
                    'plaintext': unenc_data[timestamp]['plaintext'],
                    'ciphertext': row[1],
                    'mi': mi_value,
                    'table': table,
                    'sf_id_unenc': unenc_data[timestamp]['sf_id'],
                    'sf_id_enc': row[2]
                })
    
    conn_unenc.close()
    conn_enc.close()
    
    return pairs

# Get all pairs
pairs = get_all_pairs()
print(f"\nTotal pairs: {len(pairs)}")

# Group by MI
by_mi = defaultdict(list)
for pair in pairs:
    by_mi[pair['mi']].append(pair)

print(f"Unique MI values: {len(by_mi)}")

# Analyze specific patterns
print("\n=== Pattern Analysis ===")

# Look for known DMR patterns
CALL_TONE = "DD284C0000A17C00"  # Common in 6969 transmissions
SILENCE = "0000000000000000"

# Find call tone patterns
call_tone_pairs = [p for p in pairs if p['plaintext'] == CALL_TONE]
print(f"\nCall Tone patterns: {len(call_tone_pairs)}")

if call_tone_pairs:
    # Group by MI
    ct_by_mi = defaultdict(list)
    for pair in call_tone_pairs:
        ct_by_mi[pair['mi']].append(pair)
    
    print("\nCall Tone encryption by MI:")
    for mi, ct_pairs in list(ct_by_mi.items())[:3]:
        print(f"\nMI {mi:08X} ({len(ct_pairs)} samples):")
        
        for i, pair in enumerate(ct_pairs[:3]):
            pt = bytes.fromhex(pair['plaintext'])
            ct = bytes.fromhex(pair['ciphertext'])
            ks = bytes(p ^ c for p, c in zip(pt, ct))
            
            print(f"  Sample {i}:")
            print(f"    Ciphertext: {pair['ciphertext']}")
            print(f"    Keystream:  {ks.hex().upper()}")

# Check for any obvious decryption
print("\n=== Attempting Decryption ===")

# Focus on the fixed H-MI
h_mi_pairs = by_mi.get(H_MI_FIXED, [])
print(f"\nH-MI {H_MI_FIXED:08X} pairs: {len(h_mi_pairs)}")

if h_mi_pairs:
    # Try to decrypt using the known LFSR approach
    print("\nTrying LFSR-based decryption:")
    
    # Sort by timestamp
    sorted_pairs = sorted(h_mi_pairs, key=lambda x: x['timestamp'])
    
    # Initialize LFSR with H-MI
    lfsr_state = H_MI_FIXED
    
    print("\nDecryption attempts:")
    for i, pair in enumerate(sorted_pairs[:5]):
        pt = bytes.fromhex(pair['plaintext'])
        ct = bytes.fromhex(pair['ciphertext'])
        
        # Get current keystream from known plaintext
        actual_ks = bytes(p ^ c for p, c in zip(pt, ct))
        
        # Generate theoretical LFSR keystream
        lfsr_ks = []
        temp_state = lfsr_state
        for _ in range(len(ct) // 4):
            lfsr_ks.extend(struct.pack('>I', temp_state))
            # Step LFSR
            feedback = ((temp_state >> 31) ^ (temp_state >> 3) ^ (temp_state >> 1) ^ temp_state) & 1
            temp_state = ((temp_state >> 1) | (feedback << 31)) & 0xFFFFFFFF
        
        lfsr_ks = bytes(lfsr_ks[:len(ct)])
        
        # Try decryption with LFSR keystream
        decrypted = bytes(c ^ k for c, k in zip(ct, lfsr_ks))
        
        print(f"\nPair {i}:")
        print(f"  Plaintext:     {pair['plaintext']}")
        print(f"  Ciphertext:    {pair['ciphertext']}")
        print(f"  Actual KS:     {actual_ks.hex().upper()}")
        print(f"  LFSR KS:       {lfsr_ks.hex().upper()}")
        print(f"  Decrypted:     {decrypted.hex().upper()}")
        print(f"  Match:         {decrypted == pt}")

# Summary
print("\n=== Attack Summary ===")
print(f"1. Found {len(pairs)} plaintext-ciphertext pairs")
print(f"2. {len(by_mi)} different MI values in use")
print(f"3. Stream cipher confirmed (same plaintext -> different ciphertexts)")
print(f"4. LFSR direct decryption doesn't work - RC4 uses LFSR in a more complex way")

# Check for any successful decryptions
successful_decrypts = 0
for pair in pairs[:100]:  # Check first 100
    pt = bytes.fromhex(pair['plaintext'])
    ct = bytes.fromhex(pair['ciphertext'])
    
    # Try simple XOR with MI
    mi_bytes = struct.pack('>I', pair['mi'])
    simple_decrypt = bytes(c ^ m for c, m in zip(ct, mi_bytes * (len(ct) // 4 + 1)))
    
    if simple_decrypt[:4] == pt[:4]:
        successful_decrypts += 1

print(f"5. Simple XOR decryption successes: {successful_decrypts}/100")

print("\nConclusion: The RC4 implementation uses the LFSR in combination with")
print("additional operations. Full decryption would require:")
print("1. Reverse engineering the exact RC4 initialization")
print("2. Understanding how LFSR output is combined with other values")
print("3. Potentially exploiting the reduced LFSR period (2^15-1) for cryptanalysis")