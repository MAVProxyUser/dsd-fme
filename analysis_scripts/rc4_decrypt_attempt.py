#!/usr/bin/env python3
import sqlite3
import binascii
from Crypto.Cipher import ARC4

# Connect to database
db = sqlite3.connect('dmr_capture_20250517_010359.db')
cursor = db.cursor()

# Known beep patterns (plaintext)
beep_patterns = [
    '029C3C0000188000',
    '02E07020005A1000', 
    '02AA7D00008D3400'
]

# C-MIs where these beep patterns were found
beep_cmis = {
    '029C3C0000188000': 0x11E3BB5A,
    '02E07020005A1000': 0x2A77B3F0,
    '02AA7D00008D3400': 0xDC09BDB4
}

print('=== RC4 DECRYPTION ATTEMPT ===\n')

# For each beep pattern, attempt decryption
for plaintext_hex, c_mi in beep_cmis.items():
    print(f'Testing C-MI 0x{c_mi:08X} with plaintext {plaintext_hex}')
    
    # Get the superframe data for this C-MI
    cursor.execute("""
        SELECT sf.h_mi, sf.color_code, c.algid, c.slot, c.timestamp
        FROM dmr_correlations c
        JOIN superframes sf ON c.control_mi = sf.c_mi
        WHERE c.control_mi = ?
        LIMIT 1
    """, (c_mi,))
    
    result = cursor.fetchone()
    if not result:
        # Try without superframe join
        cursor.execute("""
            SELECT header_mi, algid, slot, timestamp
            FROM dmr_correlations
            WHERE control_mi = ?
            LIMIT 1
        """, (c_mi,))
        result = cursor.fetchone()
        
        if result:
            h_mi = result[0]
            algid = result[1]
            slot = result[2]
            color_code = 0  # Default
        else:
            print('  No correlation data found\n')
            continue
    else:
        h_mi = result[0]
        color_code = result[1]
        algid = result[2] 
        slot = result[3]
    
    print(f'  H-MI: 0x{h_mi:08X}')
    print(f'  Algo ID: {algid}')
    print(f'  Slot: {slot}')
    print(f'  Color Code: {color_code}')
    
    # Try different IV compositions
    iv_attempts = [
        # Standard DMR RC4 IV: H-MI (4 bytes) || C-MI (4 bytes)
        h_mi.to_bytes(4, 'big') + c_mi.to_bytes(4, 'big'),
        
        # Reversed byte order
        h_mi.to_bytes(4, 'little') + c_mi.to_bytes(4, 'little'),
        
        # Just C-MI (some implementations)
        c_mi.to_bytes(4, 'big'),
        
        # With color code appended
        h_mi.to_bytes(4, 'big') + c_mi.to_bytes(4, 'big') + color_code.to_bytes(1, 'big'),
        
        # XOR combination
        (h_mi ^ c_mi).to_bytes(4, 'big')
    ]
    
    # Convert plaintext to bytes
    plaintext_bytes = binascii.unhexlify(plaintext_hex)
    
    # Try each IV variant
    for i, iv in enumerate(iv_attempts):
        print(f'\n  Attempt {i+1} - IV: {binascii.hexlify(iv).decode()}')
        
        # Initialize RC4 with the IV
        cipher = ARC4.new(iv)
        
        # Encrypt the known plaintext
        ciphertext = cipher.encrypt(plaintext_bytes)
        ciphertext_hex = binascii.hexlify(ciphertext).decode()
        
        print(f'    Generated ciphertext: {ciphertext_hex}')
        
        # Get the actual encrypted frame from the database
        table_name = f'C_{c_mi:08X}_S{slot}'
        cursor.execute(f"SELECT ambe_hex FROM '{table_name}' WHERE ambe_hex = ?", (plaintext_hex,))
        result = cursor.fetchone()
        
        if result:
            print(f'    Actual ciphertext:    {result[0]}')
            
            # If they match, we've found the correct IV construction!
            if ciphertext_hex.upper() == result[0].upper():
                print('    *** MATCH FOUND! ***')
                print(f'    Correct IV construction: Method {i+1}')
                
                # Try to decrypt other frames with this IV
                print('\n    Decrypting other frames:')
                cipher = ARC4.new(iv)  # Reinitialize
                
                cursor.execute(f"SELECT id, ambe_hex FROM '{table_name}' ORDER BY id LIMIT 10")
                frames = cursor.fetchall()
                
                for frame_id, encrypted_hex in frames:
                    encrypted_bytes = binascii.unhexlify(encrypted_hex)
                    decrypted = cipher.encrypt(encrypted_bytes)  # RC4 encrypt = decrypt
                    decrypted_hex = binascii.hexlify(decrypted).decode()
                    print(f'      Frame {frame_id}: {decrypted_hex[:16]}...')
        else:
            print('    (Frame not found in database)')
    
    print('\n' + '='*50 + '\n')

# Also try to find patterns in the decrypted data
print('=== PATTERN ANALYSIS ===\n')

# Check if beeps have a common pattern when decrypted
print('Looking for common patterns in decrypted beeps...')

# For now, let's also check raw hex patterns
print('\nRaw beep patterns (hex):')
for pattern in beep_patterns:
    print(f'  {pattern}')
    # Convert to binary representation
    binary = bin(int(pattern, 16))[2:].zfill(len(pattern)*4)
    print(f'    Binary: {binary[:32]}...')
    # Check byte distribution
    bytes_list = [pattern[i:i+2] for i in range(0, len(pattern), 2)]
    print(f'    Bytes: {" ".join(bytes_list)}')
    print()

db.close()