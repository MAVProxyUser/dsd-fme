#!/usr/bin/env python3
"""
Test DMR decryption with predicted IVs and known patterns
"""
import sqlite3
import json
import binascii
import numpy as np
from collections import defaultdict

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

def rc4_keystream(key, length):
    """Generate RC4 keystream"""
    S = list(range(256))
    j = 0
    
    # Key scheduling
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    
    # Keystream generation
    i = j = 0
    keystream = []
    
    for _ in range(length):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        keystream.append(S[(S[i] + S[j]) % 256])
    
    return bytes(keystream)

def analyze_ambe_patterns():
    """Analyze AMBE patterns for known plaintext"""
    
    print("DMR Decryption Test")
    print("===================\n")
    
    # Find all databases
    import glob
    db_files = sorted(glob.glob("dmr_capture_*.db"))
    
    if not db_files:
        print("No capture databases found!")
        return
    
    # Analyze AMBE patterns
    ambe_patterns = defaultdict(list)
    
    for db_file in db_files:
        print(f"Analyzing {db_file}...")
        
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get all AMBE tables
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'C_%'
        """)
        tables = cursor.fetchall()
        
        for table_name in tables:
            table = table_name[0]
            # Extract MI from table name
            parts = table.split('_')
            if len(parts) >= 2:
                c_mi = int(parts[1], 16)
                
                # Get AMBE frames
                cursor.execute(f"SELECT ambe_hex FROM {table}")
                frames = cursor.fetchall()
                
                for ambe_hex, in frames:
                    ambe_bytes = binascii.unhexlify(ambe_hex.replace('0x', ''))
                    ambe_patterns[c_mi].append(ambe_bytes)
        
        conn.close()
    
    print(f"\nFound {len(ambe_patterns)} unique C-MI values with AMBE data")
    
    # Look for common patterns (potential known plaintext)
    print("\nSearching for common AMBE patterns...")
    
    pattern_counts = defaultdict(int)
    for c_mi, frames in ambe_patterns.items():
        for frame in frames:
            # Convert to tuple for hashing
            pattern_counts[frame] += 1
    
    # Most common patterns (possible silence or roger beep)
    common_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    print("\nMost common AMBE patterns:")
    for i, (pattern, count) in enumerate(common_patterns):
        print(f"  {i+1}. {binascii.hexlify(pattern).decode()[:16]}... (count: {count})")
    
    # Test decryption with common patterns
    print("\n=== DECRYPTION ATTEMPTS ===")
    
    # Common test keys for DMR
    test_keys = [
        b'\x00\x00\x00\x00\x00',  # All zeros
        b'\xFF\xFF\xFF\xFF\xFF',  # All ones
        b'\x01\x23\x45\x67\x89',  # Sequential
        b'\x12\x34\x56\x78\x9A',  # Common test
    ]
    
    # Try to decrypt common patterns
    for pattern_num, (common_pattern, count) in enumerate(common_patterns[:3]):
        print(f"\nTesting pattern {pattern_num + 1} (occurs {count} times)")
        
        # Find which C-MI values have this pattern
        matching_mi = []
        for c_mi, frames in ambe_patterns.items():
            if common_pattern in frames:
                matching_mi.append(c_mi)
        
        print(f"Found in {len(matching_mi)} different C-MI contexts")
        
        # Try decryption with different keys
        for key_num, test_key in enumerate(test_keys):
            # For first matching MI
            if matching_mi:
                c_mi = matching_mi[0]
                
                # DMR uses MI as part of IV
                iv = c_mi.to_bytes(4, byteorder='big')
                
                # Combine key and IV (simplified DMR key schedule)
                rc4_key = test_key + iv
                
                # Generate keystream
                keystream = rc4_keystream(rc4_key, len(common_pattern))
                
                # XOR to get potential plaintext
                plaintext = bytes(a ^ b for a, b in zip(common_pattern, keystream))
                
                # Check if plaintext looks valid
                # AMBE2+ has specific byte patterns
                if plaintext[0] == 0x00 or plaintext[0] == 0xFF:
                    print(f"  Key {key_num}: {binascii.hexlify(plaintext).decode()[:32]}... POSSIBLE")
                else:
                    print(f"  Key {key_num}: {binascii.hexlify(plaintext).decode()[:32]}...")
    
    # Statistical analysis
    print("\n=== STATISTICAL ANALYSIS ===")
    
    # Analyze byte distribution in encrypted AMBE
    all_bytes = []
    for frames in ambe_patterns.values():
        for frame in frames:
            all_bytes.extend(frame)
    
    byte_dist = np.bincount(all_bytes, minlength=256)
    entropy = -sum(p * np.log2(p) for p in byte_dist/len(all_bytes) if p > 0)
    
    print(f"Byte entropy: {entropy:.2f} bits (max: 8.0)")
    print(f"Most common bytes: {np.argsort(-byte_dist)[:5]}")
    
    # Chi-squared test for randomness
    expected = len(all_bytes) / 256
    chi_squared = sum((count - expected)**2 / expected for count in byte_dist)
    
    print(f"Chi-squared: {chi_squared:.2f} (expected ~255 for random)")
    
    if chi_squared < 200 or chi_squared > 310:
        print("Distribution appears non-random - potential weakness!")
    
    return ambe_patterns

def attempt_known_plaintext_attack():
    """Attempt known plaintext attack with roger beep"""
    
    print("\n=== KNOWN PLAINTEXT ATTACK ===")
    
    # Known AMBE patterns for specific sounds
    known_patterns = {
        'silence': b'\x00\x00\x00\x00\x00\x00\x00',
        'tone_1khz': b'\xFF\x00\xFF\x00\xFF\x00\xFF',
        'roger_beep': b'\x55\xAA\x55\xAA\x55\xAA\x55',  # Hypothetical
    }
    
    # Load pattern model
    try:
        with open('dmr_master_pattern.json', 'r') as f:
            model = json.load(f)
        
        print("Loaded pattern model")
        
        # Get databases
        import glob
        db_files = sorted(glob.glob("dmr_capture_*.db"))
        
        if not db_files:
            return
        
        # Search for known patterns in captured data
        latest_db = db_files[-1]
        conn = sqlite3.connect(latest_db)
        cursor = conn.cursor()
        
        # Get recent C-MI values
        cursor.execute("""
            SELECT DISTINCT control_mi 
            FROM dmr_correlations 
            ORDER BY timestamp DESC 
            LIMIT 10
        """)
        recent_mi = cursor.fetchall()
        
        print(f"\nSearching for known patterns in recent frames...")
        
        for c_mi, in recent_mi:
            table_name = f"C_{c_mi:08X}_S0"
            
            try:
                cursor.execute(f"SELECT ambe_hex FROM {table_name}")
                frames = cursor.fetchall()
                
                for ambe_hex, in frames:
                    ambe_bytes = binascii.unhexlify(ambe_hex.replace('0x', ''))
                    
                    # Check against known patterns
                    for pattern_name, known_pattern in known_patterns.items():
                        if len(ambe_bytes) >= len(known_pattern):
                            # Simple correlation check
                            correlation = sum(1 for a, b in zip(ambe_bytes, known_pattern) if a == b)
                            
                            if correlation > len(known_pattern) * 0.7:  # 70% match
                                print(f"Potential {pattern_name} in MI 0x{c_mi:08X}")
                                
                                # Attempt key recovery
                                iv = c_mi.to_bytes(4, byteorder='big')
                                
                                # If we know plaintext and ciphertext
                                # keystream = plaintext XOR ciphertext
                                keystream = bytes(a ^ b for a, b in zip(known_pattern, ambe_bytes[:len(known_pattern)]))
                                
                                print(f"  Recovered keystream: {binascii.hexlify(keystream).decode()[:16]}...")
                                
            except sqlite3.OperationalError:
                pass  # Table doesn't exist
        
        conn.close()
        
    except FileNotFoundError:
        print("No pattern model found. Run dmr_master_analysis.py first!")

if __name__ == "__main__":
    # Analyze AMBE patterns
    ambe_patterns = analyze_ambe_patterns()
    
    # Attempt known plaintext attack
    attempt_known_plaintext_attack()
    
    print("\n=== RECOMMENDATIONS ===")
    print("1. Capture transmission with known audio (roger beep, silence)")
    print("2. Use multiple radios with same key but different IDs")
    print("3. Capture at different times to see IV evolution")
    print("4. Analyze correlation between audio content and AMBE patterns")