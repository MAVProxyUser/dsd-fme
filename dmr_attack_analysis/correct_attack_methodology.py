#!/usr/bin/env python3

import sqlite3
import pandas as pd
from collections import defaultdict, Counter
import numpy as np

def analyze_encrypted_ambe_patterns(db_path):
    """Analyze ENCRYPTED AMBE frames for attack methodology"""
    print(f"Analyzing ENCRYPTED AMBE frames in: {db_path}")
    print("\nIMPORTANT: These frames are ENCRYPTED - we cannot decode them directly!")
    
    conn = sqlite3.connect(db_path)
    
    # Get all frames with their C-MI values
    frames_by_cmi = defaultdict(list)
    all_frames = []
    
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
    """, conn)
    
    print(f"\nCollecting encrypted frames from {len(c_tables)} C-MI tables...")
    
    for table_name in c_tables['name']:
        c_mi = int(table_name.split('_')[1], 16)
        
        frames = pd.read_sql_query(f"""
            SELECT ambe_hex, timestamp
            FROM '{table_name}'
            ORDER BY timestamp
        """, conn)
        
        frames_by_cmi[c_mi] = frames['ambe_hex'].tolist()
        all_frames.extend(frames['ambe_hex'].tolist())
    
    print(f"Total encrypted AMBE frames: {len(all_frames)}")
    
    # Look for patterns that might indicate beeps (even encrypted)
    print("\n=== ENCRYPTED FRAME PATTERN ANALYSIS ===")
    
    # Count consecutive repeated frames (beeps often repeat)
    repeated_sequences = defaultdict(list)
    
    for c_mi, frames in frames_by_cmi.items():
        for i in range(len(frames) - 2):
            if frames[i] == frames[i+1] == frames[i+2]:
                repeated_sequences[frames[i]].append({
                    'c_mi': c_mi,
                    'position': i,
                    'count': 3
                })
                
                # Check how many times it continues
                j = i + 3
                while j < len(frames) and frames[j] == frames[i]:
                    repeated_sequences[frames[i]][-1]['count'] += 1
                    j += 1
    
    print(f"\nFound {len(repeated_sequences)} unique repeated patterns")
    print("Top repeated encrypted frames (potential beeps):")
    
    for frame, occurrences in sorted(repeated_sequences.items(), 
                                   key=lambda x: len(x[1]), 
                                   reverse=True)[:10]:
        total_repeats = sum(occ['count'] for occ in occurrences)
        print(f"  {frame}: {len(occurrences)} sequences, {total_repeats} total repeats")
    
    # Analyze frame distribution per C-MI
    print("\n=== FRAMES PER C-MI ANALYSIS ===")
    frame_counts = [(c_mi, len(frames)) for c_mi, frames in frames_by_cmi.items()]
    frame_counts.sort(key=lambda x: x[1], reverse=True)
    
    print("Top 10 C-MI values by frame count:")
    for c_mi, count in frame_counts[:10]:
        print(f"  0x{c_mi:08X}: {count} frames")
    
    # The actual attack methodology
    print("\n=== CORRECT ATTACK METHODOLOGY ===")
    print("""
    Since these frames are ENCRYPTED:
    
    1. We CANNOT decode them directly with AMBE decoder
    2. We need to find PATTERNS in encrypted data that suggest known plaintext
    3. Potential known plaintext sources:
       - Call End Beeps (should repeat at end of each transmission)
       - Silence periods (may have predictable patterns)
       - Protocol overhead
    
    4. The attack process:
       a) Identify potential beep patterns (repeated frames at end of transmissions)
       b) Guess the plaintext AMBE beep pattern
       c) XOR encrypted frame with guessed plaintext = potential keystream
       d) Test keystream on other frames with same C-MI
       e) Decrypt frames with potential keystream
       f) THEN use AMBE decoder on DECRYPTED result to validate
    
    5. Validation:
       - If decrypted frame passes AMBE decoder = correct keystream
       - If not, try different plaintext guess
    """)
    
    return frames_by_cmi, repeated_sequences

def demonstrate_attack_attempt(frames_by_cmi, repeated_sequences):
    """Demonstrate how the attack would actually work"""
    print("\n=== ATTACK DEMONSTRATION ===")
    
    # Pick a repeated pattern (potential beep)
    if repeated_sequences:
        # Get the most repeated pattern
        most_repeated = max(repeated_sequences.items(), 
                          key=lambda x: sum(occ['count'] for occ in x[1]))
        
        encrypted_beep = most_repeated[0]
        occurrences = most_repeated[1]
        
        print(f"\nTarget encrypted pattern: {encrypted_beep}")
        print(f"Appears in {len(occurrences)} sequences")
        
        # In a real attack, we would:
        print("\nAttack steps:")
        print("1. Guess plaintext beep patterns (from DMR spec or captured unencrypted)")
        print("2. For each guess:")
        print("   - XOR with encrypted pattern")
        print("   - Get potential keystream")
        print("   - Try decrypting other frames with same C-MI")
        print("   - Test decrypted frames with AMBE decoder")
        print("3. If AMBE decoder validates = found correct keystream")
        
        # Show example calculation
        print("\nExample (simplified):")
        print(f"Encrypted: {encrypted_beep}")
        print("Guessed plaintext: [DMR beep pattern]")
        print("Keystream = Encrypted XOR Plaintext")
        print("Test on other frames with same C-MI...")
    
    else:
        print("No repeated patterns found for demonstration")

# Main execution
db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_025824.db"
frames_by_cmi, repeated_sequences = analyze_encrypted_ambe_patterns(db_path)
demonstrate_attack_attempt(frames_by_cmi, repeated_sequences)