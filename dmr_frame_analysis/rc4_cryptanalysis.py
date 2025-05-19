#!/usr/bin/env python3

import sqlite3
import glob
from collections import defaultdict
import numpy as np

# Get the latest two databases
databases = sorted(glob.glob("dmr_capture_*.db"))[-2:]

print(f"RC4 Cryptanalysis using plaintext-ciphertext pairs:")
print(f"  Unencrypted: {databases[0]}")
print(f"  Encrypted: {databases[1]}")

def get_frame_pairs():
    """Get all matching plaintext-ciphertext pairs"""
    
    conn_unenc = sqlite3.connect(databases[0])
    conn_enc = sqlite3.connect(databases[1])
    
    # Get unencrypted frames
    cursor_unenc = conn_unenc.cursor()
    cursor_unenc.execute("""
        SELECT timestamp, ambe_hex, superframe_id
        FROM U_00000000_S0
        ORDER BY timestamp
    """)
    
    unenc_data = {}
    for row in cursor_unenc.fetchall():
        unenc_data[row[0]] = {'plaintext': row[1], 'sf_id': row[2]}
    
    # Get encrypted frames
    pairs = []
    cursor_enc = conn_enc.cursor()
    
    # Get all encrypted tables
    cursor_enc.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')")
    enc_tables = cursor_enc.fetchall()
    
    for table_name in enc_tables:
        table = table_name[0]
        
        cursor_enc.execute(f"""
            SELECT timestamp, ambe_hex, mi_full, superframe_id
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
                    'mi': row[2],
                    'sf_id_unenc': unenc_data[timestamp]['sf_id'],
                    'sf_id_enc': row[3]
                })
    
    conn_unenc.close()
    conn_enc.close()
    
    return pairs

# Get all pairs
pairs = get_frame_pairs()
print(f"\nTotal plaintext-ciphertext pairs: {len(pairs)}")

# Group by MI value
by_mi = defaultdict(list)
for pair in pairs:
    by_mi[pair['mi']].append(pair)

print(f"Unique MI values: {len(by_mi)}")

# Analyze RC4 keystream properties
print("\n=== RC4 Keystream Analysis ===")

# For each MI, collect the keystream
keystreams_by_mi = {}

for mi, mi_pairs in by_mi.items():
    keystream_bytes = []
    
    for pair in mi_pairs:
        pt = bytes.fromhex(pair['plaintext'])
        ct = bytes.fromhex(pair['ciphertext'])
        
        # Keystream = plaintext XOR ciphertext
        keystream = bytes(p ^ c for p, c in zip(pt, ct))
        keystream_bytes.append(keystream)
    
    keystreams_by_mi[mi] = keystream_bytes

# Look for the known H-MI value (fixed in Motorola implementation)
H_MI_FIXED = 0x6C8AB637

if H_MI_FIXED in keystreams_by_mi:
    print(f"\nFound fixed H-MI {H_MI_FIXED:08X} with {len(keystreams_by_mi[H_MI_FIXED])} keystream samples")
    
    # Analyze this keystream
    h_keystreams = keystreams_by_mi[H_MI_FIXED]
    
    # Check for patterns or biases
    byte_frequencies = defaultdict(lambda: defaultdict(int))
    
    for ks in h_keystreams:
        for pos, byte in enumerate(ks):
            byte_frequencies[pos][byte] += 1
    
    print("\nByte position biases (positions with strong biases):")
    for pos in range(8):
        freqs = byte_frequencies[pos]
        total = sum(freqs.values())
        
        if total > 0:
            # Find most common byte
            most_common = max(freqs.items(), key=lambda x: x[1])
            bias = most_common[1] / total
            
            if bias > 0.2:  # More than 20% occurrence
                print(f"  Position {pos}: Byte {most_common[0]:02X} appears {most_common[1]}/{total} times ({bias:.1%})")

# Look for LFSR state recovery
print("\n=== LFSR State Recovery ===")

# The LFSR polynomial is x^32 + x^4 + x^2 + 1
# This means: next_bit = bit[31] ^ bit[3] ^ bit[1] ^ bit[0]

def lfsr_step(state, polynomial=0x10000015):
    """Single step of the LFSR"""
    feedback = 0
    for i in range(32):
        if polynomial & (1 << i):
            feedback ^= (state >> i) & 1
    
    return ((state >> 1) | (feedback << 31)) & 0xFFFFFFFF

def recover_lfsr_state(keystream_samples):
    """Try to recover the LFSR state from keystream samples"""
    
    # Look for consecutive samples
    consecutive_pairs = []
    
    for i in range(len(keystream_samples) - 1):
        if keystream_samples[i][:4] != bytes(4) and keystream_samples[i+1][:4] != bytes(4):
            # Extract first 4 bytes as potential LFSR output
            val1 = int.from_bytes(keystream_samples[i][:4], 'big')
            val2 = int.from_bytes(keystream_samples[i+1][:4], 'big')
            
            consecutive_pairs.append((val1, val2))
    
    print(f"Found {len(consecutive_pairs)} consecutive keystream pairs")
    
    # Try to find LFSR state that produces these outputs
    if consecutive_pairs:
        for i, (val1, val2) in enumerate(consecutive_pairs[:5]):
            # Check if val2 could be the next LFSR state after val1
            next_state = lfsr_step(val1)
            
            print(f"\nPair {i}:")
            print(f"  Value 1: {val1:08X}")
            print(f"  Value 2: {val2:08X}")
            print(f"  Expected next: {next_state:08X}")
            print(f"  Match: {val2 == next_state}")

# Analyze known patterns
print("\n=== Known Pattern Analysis ===")

# Look for silence frames (all zeros)
silence_pattern = "0000000000000000"
silence_pairs = [p for p in pairs if p['plaintext'] == silence_pattern]

print(f"Found {len(silence_pairs)} silence frames")

if silence_pairs:
    # Group by MI
    silence_by_mi = defaultdict(list)
    for pair in silence_pairs:
        silence_by_mi[pair['mi']].append(pair)
    
    print("\nSilence frame keystreams by MI:")
    for mi, s_pairs in list(silence_by_mi.items())[:3]:
        print(f"\nMI {mi:08X} ({len(s_pairs)} samples):")
        
        # Extract keystreams (ciphertext when plaintext is 0)
        for i, pair in enumerate(s_pairs[:3]):
            ks = pair['ciphertext']
            print(f"  Keystream {i}: {ks}")

# Look for repeating patterns in any MI
print("\n=== Repeating Pattern Detection ===")

for mi, mi_pairs in list(by_mi.items())[:5]:
    if len(mi_pairs) > 10:
        print(f"\nMI {mi:08X} ({len(mi_pairs)} samples):")
        
        # Look for repeated plaintexts
        pt_counts = defaultdict(list)
        for pair in mi_pairs:
            pt_counts[pair['plaintext']].append(pair['ciphertext'])
        
        # Find plaintexts that appear multiple times
        repeated_pts = [(pt, cts) for pt, cts in pt_counts.items() if len(cts) > 1]
        
        if repeated_pts:
            for pt, cts in repeated_pts[:2]:
                print(f"\n  Plaintext {pt} appears {len(cts)} times:")
                for i, ct in enumerate(cts[:3]):
                    print(f"    Ciphertext {i}: {ct}")
                
                # Check if ciphertexts are different (confirming stream cipher)
                if len(set(cts)) == len(cts):
                    print("    All ciphertexts different - confirms stream cipher")
                else:
                    print("    Some ciphertexts repeat - possible key reuse!")

# LFSR period analysis
print("\n=== LFSR Period Analysis ===")

# The backdoor LFSR has period 2^15-1 = 32767
LFSR_PERIOD = 32767

# Check if we can find evidence of the period
for mi, mi_pairs in by_mi.items():
    if len(mi_pairs) > 100:
        print(f"\nAnalyzing MI {mi:08X} with {len(mi_pairs)} samples:")
        
        # Sort by timestamp
        sorted_pairs = sorted(mi_pairs, key=lambda x: x['timestamp'])
        
        # Look for patterns that might repeat after LFSR_PERIOD steps
        keystreams = []
        for pair in sorted_pairs:
            pt = bytes.fromhex(pair['plaintext'])
            ct = bytes.fromhex(pair['ciphertext'])
            ks = bytes(p ^ c for p, c in zip(pt, ct))
            keystreams.append(ks)
        
        # Check for exact period
        period_matches = 0
        for i in range(len(keystreams) - LFSR_PERIOD):
            if i + LFSR_PERIOD < len(keystreams):
                if keystreams[i] == keystreams[i + LFSR_PERIOD]:
                    period_matches += 1
        
        if period_matches > 0:
            print(f"  Found {period_matches} exact matches at period {LFSR_PERIOD}!")
        
        break  # Just check one MI with enough samples