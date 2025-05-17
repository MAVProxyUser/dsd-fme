#!/usr/bin/env python3
"""
Analyze end beep patterns for known plaintext attack
"""
import sqlite3
import glob
import binascii
from collections import Counter, defaultdict
from datetime import datetime

def find_end_beep_patterns():
    """Find repeating AMBE patterns that could be end beeps"""
    
    print("End Beep Pattern Analysis")
    print("========================\n")
    
    # Get all databases
    db_files = sorted(glob.glob("dmr_capture_*.db"))
    
    if not db_files:
        print("No databases found!")
        return
    
    print(f"Found {len(db_files)} database(s):")
    for db in db_files:
        print(f"  {db}")
    
    # Analyze each database
    all_patterns = defaultdict(lambda: {'count': 0, 'locations': []})
    radio_patterns = defaultdict(lambda: defaultdict(list))
    
    for db_file in db_files:
        print(f"\nAnalyzing {db_file}...")
        
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get correlations to identify radio IDs
        cursor.execute("""
            SELECT DISTINCT control_mi, slot 
            FROM dmr_correlations 
            ORDER BY timestamp
        """)
        mi_to_slot = dict(cursor.fetchall())
        
        # Get all C- tables
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'C_%'
        """)
        tables = cursor.fetchall()
        
        for table_name in tables:
            table = table_name[0]
            
            # Extract MI from table name
            try:
                c_mi = int(table.split('_')[1], 16)
                slot = mi_to_slot.get(c_mi, 0)
                
                # Get last few AMBE frames (where end beep would be)
                cursor.execute(f"""
                    SELECT ambe_hex, timestamp 
                    FROM {table} 
                    ORDER BY timestamp DESC 
                    LIMIT 5
                """)
                frames = cursor.fetchall()
                
                # Look for patterns in the last frames
                for i, (ambe_hex, timestamp) in enumerate(frames):
                    ambe_bytes = binascii.unhexlify(ambe_hex.replace('0x', ''))
                    pattern_key = ambe_bytes
                    
                    all_patterns[pattern_key]['count'] += 1
                    all_patterns[pattern_key]['locations'].append({
                        'db': db_file,
                        'table': table,
                        'c_mi': c_mi,
                        'slot': slot,
                        'position': i,
                        'timestamp': timestamp
                    })
                    
                    # Track by radio/slot
                    radio_patterns[slot][pattern_key].append({
                        'c_mi': c_mi,
                        'table': table,
                        'db': db_file
                    })
                    
            except (ValueError, IndexError):
                continue
        
        conn.close()
    
    # Find most common patterns
    print("\n=== MOST COMMON PATTERNS ===")
    common_patterns = sorted(all_patterns.items(), 
                           key=lambda x: x[1]['count'], 
                           reverse=True)[:10]
    
    end_beep_candidates = []
    
    for i, (pattern, info) in enumerate(common_patterns):
        print(f"\nPattern {i+1}:")
        print(f"  Hex: {binascii.hexlify(pattern).decode()[:32]}...")
        print(f"  Count: {info['count']}")
        print(f"  Found in {len(set(loc['table'] for loc in info['locations']))} tables")
        
        # Check if pattern appears at end of transmissions
        end_positions = sum(1 for loc in info['locations'] if loc['position'] <= 2)
        if end_positions > info['count'] * 0.8:  # 80% at end
            print(f"  **LIKELY END BEEP** ({end_positions}/{info['count']} at end)")
            end_beep_candidates.append(pattern)
    
    # Analyze by radio ID
    print("\n=== PATTERNS BY RADIO/SLOT ===")
    for slot, patterns in radio_patterns.items():
        print(f"\nSlot {slot}:")
        slot_common = Counter()
        for pattern, occurrences in patterns.items():
            slot_common[pattern] = len(occurrences)
        
        for pattern, count in slot_common.most_common(5):
            print(f"  {binascii.hexlify(pattern).decode()[:16]}... : {count} times")
    
    # Look for identical patterns across radios
    print("\n=== CROSS-RADIO PATTERNS ===")
    if len(radio_patterns) > 1:
        slots = list(radio_patterns.keys())
        slot1_patterns = set(radio_patterns[slots[0]].keys())
        slot2_patterns = set(radio_patterns[slots[1]].keys()) if len(slots) > 1 else set()
        
        common = slot1_patterns & slot2_patterns
        print(f"Patterns found in both radios: {len(common)}")
        
        for pattern in list(common)[:5]:
            print(f"  {binascii.hexlify(pattern).decode()[:16]}...")
    
    return end_beep_candidates

def attempt_beep_decryption(beep_patterns):
    """Attempt to decrypt using known beep patterns"""
    
    print("\n=== BEEP DECRYPTION ATTEMPT ===")
    
    if not beep_patterns:
        print("No beep patterns found!")
        return
    
    # Test with common DMR keys
    test_keys = [
        b'\x00\x00\x00\x00\x00',  # All zeros
        b'\xFF\xFF\xFF\xFF\xFF',  # All ones  
        b'\x01\x23\x45\x67\x89',  # Sequential
        b'\x12\x34\x56\x78\x9A',  # Common test
    ]
    
    # For each beep pattern
    for beep_num, beep_pattern in enumerate(beep_patterns[:3]):
        print(f"\nBeep pattern {beep_num + 1}:")
        print(f"  Ciphertext: {binascii.hexlify(beep_pattern).decode()[:32]}...")
        
        # RC4 keystream recovery
        # If we know this is a beep (known plaintext)
        # Keystream = Ciphertext XOR Plaintext
        
        # Common beep plaintexts
        test_plaintexts = [
            b'\x00\x00\x00\x00\x00\x00\x00',  # Silence
            b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF',  # Full scale
            b'\x55\xAA\x55\xAA\x55\xAA\x55',  # Alternating
        ]
        
        for pt_num, plaintext in enumerate(test_plaintexts):
            # Ensure same length
            plaintext = plaintext[:len(beep_pattern)]
            
            # Recover potential keystream
            keystream = bytes(c ^ p for c, p in zip(beep_pattern, plaintext))
            
            print(f"  If plaintext {pt_num}: keystream = {binascii.hexlify(keystream).decode()[:16]}...")
            
            # Check if keystream looks valid (RC4 properties)
            # RC4 keystream should be relatively random
            unique_bytes = len(set(keystream))
            if unique_bytes > len(keystream) * 0.5:  # >50% unique
                print(f"    Possible match (entropy: {unique_bytes}/{len(keystream)})")

def analyze_radio_ids():
    """Extract and analyze radio IDs from captures"""
    
    print("\n=== RADIO ID ANALYSIS ===")
    
    db_files = sorted(glob.glob("dmr_capture_*.db"))
    
    radio_data = defaultdict(lambda: {'frames': 0, 'c_mi_values': set()})
    
    for db_file in db_files:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get extended info if available
        try:
            cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT control_mi) 
                FROM dmr_correlations 
                WHERE slot = 0
            """)
            slot0_frames, slot0_mi = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT control_mi) 
                FROM dmr_correlations 
                WHERE slot = 1
            """)
            slot1_frames, slot1_mi = cursor.fetchone()
            
            print(f"\n{db_file}:")
            print(f"  Slot 0: {slot0_frames} frames, {slot0_mi} unique C-MI")
            print(f"  Slot 1: {slot1_frames} frames, {slot1_mi} unique C-MI")
            
            # If we captured radio ID info (future enhancement)
            # This would extract actual radio IDs from frames
            
        except Exception as e:
            print(f"Error analyzing {db_file}: {e}")
        
        conn.close()

if __name__ == "__main__":
    # Find end beep patterns
    beep_patterns = find_end_beep_patterns()
    
    # Attempt decryption
    if beep_patterns:
        attempt_beep_decryption(beep_patterns)
    
    # Analyze radio IDs
    analyze_radio_ids()
    
    print("\n=== RECOMMENDATIONS ===")
    print("1. Capture a known beep sequence (3 beeps in a row)")
    print("2. Transmit silence before beep for contrast")
    print("3. Use both radios with same beep pattern")
    print("4. Correlate beep timing with C-MI changes")