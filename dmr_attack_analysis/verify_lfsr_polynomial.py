#!/usr/bin/env python3

import sqlite3
import pandas as pd
from collections import defaultdict

def lfsr_next(current_mi):
    """Calculate the next MI value using polynomial x^32 + x^4 + x^2 + 1"""
    lfsr = current_mi
    
    for _ in range(32):
        # Polynomial: x^32 + x^4 + x^2 + 1
        # Taps at positions: 32, 4, 2, 0
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

def analyze_lfsr_sequence(db_path):
    print(f"Analyzing: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get all C-MI values with timestamps
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
    """, conn)
    
    # Collect C-MI values with their earliest timestamp
    c_mi_data = []
    
    for table_name in c_tables['name']:
        c_mi = int(table_name.split('_')[1], 16)
        
        # Get earliest timestamp for this C-MI
        timestamps = pd.read_sql_query(f"""
            SELECT MIN(timestamp) as first_seen 
            FROM '{table_name}'
        """, conn)
        
        if timestamps['first_seen'].iloc[0]:
            c_mi_data.append({
                'c_mi': c_mi,
                'timestamp': pd.to_datetime(timestamps['first_seen'].iloc[0])
            })
    
    # Sort by timestamp to get actual sequence
    c_mi_data.sort(key=lambda x: x['timestamp'])
    
    print(f"\n=== C-MI SEQUENCE IN ORDER ===")
    for i, data in enumerate(c_mi_data[:20]):
        print(f"#{i+1}: 0x{data['c_mi']:08X} at {data['timestamp']}")
    
    # Test LFSR progression
    print(f"\n=== LFSR POLYNOMIAL VERIFICATION ===")
    print("Testing polynomial x^32 + x^4 + x^2 + 1")
    
    correct_predictions = 0
    total_tests = 0
    
    for i in range(len(c_mi_data) - 1):
        current = c_mi_data[i]['c_mi']
        actual_next = c_mi_data[i + 1]['c_mi']
        
        # Test direct LFSR step
        predicted_next = lfsr_next(current)
        
        # Test multiple steps (in case of jumps)
        temp = current
        for steps in range(1, 10):
            temp = lfsr_next(temp)
            if temp == actual_next:
                print(f"✓ 0x{current:08X} → 0x{actual_next:08X} ({steps} steps)")
                correct_predictions += 1
                break
        else:
            print(f"✗ 0x{current:08X} → 0x{actual_next:08X} (not found in 10 steps)")
        
        total_tests += 1
        if total_tests >= 10:  # Test first 10 transitions
            break
    
    print(f"\nCorrect predictions: {correct_predictions}/{total_tests}")
    
    # Analyze AMBE data for attack
    print(f"\n=== AMBE FRAME ANALYSIS FOR ATTACK ===")
    
    # Look for potential known patterns
    ambe_patterns = defaultdict(int)
    total_ambe_frames = 0
    
    for table_name in c_tables['name'][:20]:  # Sample first 20 tables
        frames = pd.read_sql_query(f"""
            SELECT ambe_hex FROM '{table_name}'
        """, conn)
        
        for frame in frames['ambe_hex']:
            if frame:
                # Look for common patterns (silence, beeps, etc.)
                if frame.startswith('00'):  # Potential silence
                    ambe_patterns['silence'] += 1
                elif frame.startswith('02'):  # Potential beep/tone
                    ambe_patterns['beep'] += 1
                elif frame == 'FFFFFFFFFFFF':  # Empty frame
                    ambe_patterns['empty'] += 1
                
                total_ambe_frames += 1
    
    print(f"Total AMBE frames analyzed: {total_ambe_frames}")
    print("Potential known patterns:")
    for pattern, count in ambe_patterns.items():
        print(f"  {pattern}: {count} ({count/total_ambe_frames*100:.1f}%)")
    
    conn.close()

def demonstrate_attack_methodology():
    print("\n=== ATTACK METHODOLOGY EXPLANATION ===")
    print("""
    1. WHAT WE'RE ATTACKING:
       - DMR encryption uses RC4 with IVs derived from H-MI and C-MI
       - Fixed H-MI (0x6C8AB637) means the keystream becomes predictable
       - Each superframe position has a specific C-MI value
    
    2. THE PARALLEL ATTACK:
       - Collect 30+ transmissions
       - Group encrypted AMBE frames by superframe position
       - Attack each superframe position in parallel
    
    3. KNOWN PLAINTEXT SOURCES:
       - Silence periods (many AMBE codecs encode silence predictably)
       - Call End Beep patterns (0x02 prefix we've observed)
       - DMR protocol overhead (predictable patterns)
    
    4. AMBE DECODING VALIDATION:
       - Use AMBE decoder to validate decrypted frames
       - Invalid AMBE frames indicate wrong keystream guess
       - Valid AMBE frames confirm correct keystream recovery
    
    5. THE PROCESS:
       - XOR encrypted AMBE with guessed plaintext
       - This reveals portions of the RC4 keystream
       - Compare keystreams across multiple transmissions
       - When patterns match, we've found the correct plaintext
    """)

# Find the latest database
import glob
import os

db_files = glob.glob("/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_*.db")
if db_files:
    latest_db = max(db_files, key=os.path.getctime)
    analyze_lfsr_sequence(latest_db)
    demonstrate_attack_methodology()