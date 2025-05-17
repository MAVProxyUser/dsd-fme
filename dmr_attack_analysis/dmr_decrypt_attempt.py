#!/usr/bin/env python3
"""
DMR RC4 Decryption Attempt using predicted IVs
"""
import sqlite3
import json
from Crypto.Cipher import ARC4
import binascii

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

def rc4_decrypt(key, ciphertext):
    """Decrypt using RC4"""
    cipher = ARC4.new(key)
    return cipher.decrypt(ciphertext)

def predict_next_mi(current_mi, pattern_model):
    """Predict next MI using learned pattern"""
    # Simple prediction - use most common jump
    jumps = pattern_model['jump_distribution']
    most_likely_jump = int(max(jumps, key=jumps.get))
    
    # Generate LFSR sequence
    lfsr_seq = []
    current = current_mi
    for _ in range(10):
        current = lfsr_next(current)
        lfsr_seq.append(current)
    
    # Apply predicted jump
    if 0 <= most_likely_jump < len(lfsr_seq):
        return lfsr_seq[most_likely_jump]
    else:
        return lfsr_seq[0]  # Default to next

print("DMR RC4 Decryption Attempt")
print("==========================\n")

# Load pattern model
try:
    with open('dmr_pattern_model.json', 'r') as f:
        pattern_model = json.load(f)
    print(f"Loaded pattern model with {pattern_model['total_frames']} frames")
except:
    print("No pattern model found. Run multi_db_analysis.py first!")
    pattern_model = {'jump_distribution': {'1': 100}}

# Find latest database
import glob
db_files = glob.glob("dmr_capture_*.db")
db_files.extend(glob.glob("dsd_fme.db"))

if not db_files:
    print("No database found!")
    exit(1)

latest_db = sorted(db_files)[-1]
print(f"Using database: {latest_db}")

conn = sqlite3.connect(latest_db)
cursor = conn.cursor()

# Get latest H-MI and C-MI
cursor.execute("""
    SELECT header_mi, control_mi 
    FROM dmr_correlations 
    ORDER BY timestamp DESC 
    LIMIT 1
""")
last_h_mi, last_c_mi = cursor.fetchone()

print(f"\nLast captured IVs:")
print(f"  H-MI: 0x{last_h_mi:08X}")
print(f"  C-MI: 0x{last_c_mi:08X}")

# Predict next C-MI values
print("\nPredicting next 10 C-MI values:")
current = last_c_mi
predictions = []

for i in range(10):
    next_mi = predict_next_mi(current, pattern_model)
    predictions.append(next_mi)
    print(f"  {i+1}: 0x{next_mi:08X}")
    current = next_mi

# Attempt decryption of AMBE frames
print("\n=== DECRYPTION ATTEMPTS ===")

# RC4 key construction for DMR
# Key = Hash(EncKey || IV)
# For testing, we'll try known patterns

# Get some AMBE frames
ambe_table = f"C_{last_c_mi:08X}_S0"
cursor.execute(f"SELECT ambe_hex FROM {ambe_table} LIMIT 5")
ambe_frames = cursor.fetchall()

print(f"\nAttempting to decrypt {len(ambe_frames)} AMBE frames from {ambe_table}")

# Common DMR encryption keys (for testing)
test_keys = [
    b'\x00' * 5,  # All zeros
    b'\xFF' * 5,  # All ones
    b'\x01\x23\x45\x67\x89',  # Sequential
]

for i, (ambe_hex,) in enumerate(ambe_frames):
    print(f"\nAMBE Frame {i+1}: {ambe_hex}")
    
    # Convert hex to bytes
    ambe_bytes = binascii.unhexlify(ambe_hex.replace('0x', ''))
    
    # Construct IV from MI
    iv = last_c_mi.to_bytes(4, byteorder='big')
    
    # Try different keys
    for key_num, enc_key in enumerate(test_keys):
        # DMR key derivation (simplified)
        rc4_key = enc_key + iv
        
        try:
            decrypted = rc4_decrypt(rc4_key, ambe_bytes)
            
            # Check if decryption looks valid
            # AMBE frames have specific patterns
            if decrypted[0] & 0xF0 == 0x00:  # Simple validity check
                print(f"  Key {key_num}: {decrypted.hex()} (POSSIBLE MATCH)")
            else:
                print(f"  Key {key_num}: {decrypted.hex()[:16]}... (invalid)")
        except Exception as e:
            print(f"  Key {key_num}: Error - {e}")

# Advanced attack with predicted IVs
print("\n=== ADVANCED ATTACK ===")
print("Using predicted IVs for known plaintext attack")

# Roger beep pattern (if captured)
roger_beep_pattern = b'\x00\x00\x00\x00\x00\x00\x00'  # Placeholder

# For each predicted IV
for i, predicted_mi in enumerate(predictions[:3]):
    print(f"\nTrying predicted MI {i+1}: 0x{predicted_mi:08X}")
    
    # Construct IV
    iv = predicted_mi.to_bytes(4, byteorder='big')
    
    # Try known plaintext attack
    # If we know roger beep creates specific AMBE pattern
    for test_key in test_keys:
        rc4_key = test_key + iv
        
        # Encrypt known plaintext
        cipher = ARC4.new(rc4_key)
        test_ciphertext = cipher.encrypt(roger_beep_pattern)
        
        print(f"  Test ciphertext: {test_ciphertext.hex()[:16]}...")

conn.close()

print("\n=== NEXT STEPS ===")
print("1. Capture more data with known patterns (roger beep)")
print("2. Improve IV prediction accuracy")
print("3. Try statistical attacks on RC4 keystream")
print("4. Correlate AMBE patterns with audio content")