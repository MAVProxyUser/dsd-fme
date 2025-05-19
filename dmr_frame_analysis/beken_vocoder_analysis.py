#!/usr/bin/env python3
"""Analyze Beken BK378 vocoder characteristics for improved attack"""

import sqlite3
import numpy as np
from collections import Counter

def analyze_beken_patterns():
    """Analyze patterns specific to Beken vocoder implementation"""
    
    print("=== BEKEN BK378 VOCODER ANALYSIS ===")
    
    # Beken vocoder characteristics:
    # - Uses modified AMBE+2 algorithm
    # - Specific silence/comfort noise patterns
    # - Predictable bit allocations
    # - Known initialization sequences
    
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn = sqlite3.connect(cleartext_db)
    cursor = conn.cursor()
    
    print("\n1. ANALYZING CLEARTEXT BEKEN PATTERNS")
    
    # Get all cleartext AMBE frames
    cursor.execute("SELECT ambe_hex FROM U_00000000_S0")
    cleartext_frames = [row[0] for row in cursor.fetchall()]
    
    # Look for Beken-specific patterns
    beken_patterns = {
        'silence': [],
        'comfort_noise': [],
        'init_sequence': [],
        'end_sequence': []
    }
    
    # Known Beken silence patterns
    beken_silence_patterns = [
        '0000000000000000',  # Complete silence
        '0000000000000080',  # Silence with end flag
        '0080000000000000',  # Silence with start flag
        'FC00000000000000',  # Comfort noise pattern
        '0040000000000000',  # Low energy frame
    ]
    
    # Analyze frame patterns
    for i, frame in enumerate(cleartext_frames):
        # Check for known patterns
        if frame in beken_silence_patterns:
            beken_patterns['silence'].append((i, frame))
        
        # Check first/last frames
        if i < 5:
            beken_patterns['init_sequence'].append((i, frame))
        if i >= len(cleartext_frames) - 5:
            beken_patterns['end_sequence'].append((i, frame))
        
        # Check for comfort noise (low energy, specific bit patterns)
        frame_int = int(frame, 16)
        if bin(frame_int).count('1') < 10:  # Very few bits set
            beken_patterns['comfort_noise'].append((i, frame))
    
    print("\nBeken-specific patterns found:")
    print(f"  Silence frames: {len(beken_patterns['silence'])}")
    print(f"  Comfort noise: {len(beken_patterns['comfort_noise'])}")
    
    # Analyze bit structure specific to Beken
    print("\n2. BEKEN BIT ALLOCATION ANALYSIS")
    
    # Beken uses specific bit allocations:
    # Bits 0-5: Fundamental frequency (6 bits)
    # Bits 6-11: First spectral magnitude (6 bits)
    # Bits 12-47: Additional spectral data (36 bits)
    # Bit 48: Frame sync/flag
    
    bit_positions = {
        'fundamental': [],
        'first_spectral': [],
        'frame_flags': []
    }
    
    for frame in cleartext_frames[:100]:  # Sample
        frame_int = int(frame, 16)
        
        # Extract Beken-specific fields
        fundamental = frame_int & 0x3F  # Bits 0-5
        first_spectral = (frame_int >> 6) & 0x3F  # Bits 6-11
        frame_flag = (frame_int >> 48) & 0x1  # Bit 48
        
        bit_positions['fundamental'].append(fundamental)
        bit_positions['first_spectral'].append(first_spectral)
        bit_positions['frame_flags'].append(frame_flag)
    
    print("\nBeken field statistics:")
    print(f"  Fundamental freq range: {min(bit_positions['fundamental'])}-{max(bit_positions['fundamental'])}")
    print(f"  First spectral range: {min(bit_positions['first_spectral'])}-{max(bit_positions['first_spectral'])}")
    print(f"  Frame flags: {Counter(bit_positions['frame_flags'])}")
    
    # Look for Beken initialization sequence
    print("\n3. BEKEN INITIALIZATION SEQUENCE")
    
    if beken_patterns['init_sequence']:
        print("First frames (potential init):")
        for idx, frame in beken_patterns['init_sequence'][:3]:
            print(f"  Frame {idx}: {frame}")
    
    # Analyze end-of-transmission patterns
    print("\n4. BEKEN END-OF-TRANSMISSION")
    
    if beken_patterns['end_sequence']:
        print("Last frames (potential EOT):")
        for idx, frame in beken_patterns['end_sequence'][-3:]:
            print(f"  Frame {idx}: {frame}")
    
    conn.close()
    
    # Now apply to encrypted frames
    print("\n\n=== APPLYING BEKEN KNOWLEDGE TO ENCRYPTED FRAMES ===")
    
    encrypted_db = "dmr_capture_20250518_112024_998484.db"
    conn_enc = sqlite3.connect(encrypted_db)
    cursor_enc = conn_enc.cursor()
    
    # Get encrypted frames
    cursor_enc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%_S0' LIMIT 1")
    enc_table = cursor_enc.fetchone()[0]
    
    cursor_enc.execute(f"SELECT id, ambe_hex FROM '{enc_table}'")
    encrypted_frames = cursor_enc.fetchall()
    
    print(f"\nTesting Beken patterns on {len(encrypted_frames)} encrypted frames")
    
    # Try known Beken patterns as plaintext
    best_candidates = []
    
    for pattern_name, pattern in [
        ('complete_silence', '0000000000000000'),
        ('silence_with_flag', '0000000000000080'),
        ('beken_comfort', 'FC00000000000000'),
        ('low_energy', '0040000000000000')
    ]:
        # Test this pattern on first encrypted frame
        enc_frame = encrypted_frames[0][1]
        enc_int = int(enc_frame, 16)
        plain_int = int(pattern, 16)
        keystream = enc_int ^ plain_int
        
        # Test keystream on other frames
        score = 0
        for _, test_frame in encrypted_frames[1:10]:
            test_int = int(test_frame, 16)
            decrypted = test_int ^ keystream
            
            # Check if decrypted looks like valid Beken AMBE
            fundamental = decrypted & 0x3F
            if 0 < fundamental < 50:  # Valid voice range
                score += 10
            
            first_spectral = (decrypted >> 6) & 0x3F
            if 0 < first_spectral < 60:  # Valid spectral range
                score += 5
        
        best_candidates.append({
            'pattern': pattern_name,
            'keystream': f"{keystream:016X}",
            'score': score
        })
    
    # Sort by score
    best_candidates.sort(key=lambda x: x['score'], reverse=True)
    
    print("\nBest Beken-based keystream candidates:")
    for candidate in best_candidates:
        print(f"  Pattern: {candidate['pattern']}")
        print(f"  Keystream: {candidate['keystream']}")
        print(f"  Score: {candidate['score']}/140")
        print()
    
    conn_enc.close()
    
    print("=== BEKEN VOCODER ATTACK STRATEGY ===")
    print("1. Use known Beken silence/comfort patterns")
    print("2. Exploit Beken bit allocation structure")
    print("3. Look for initialization sequences")
    print("4. Target end-of-transmission patterns")
    print("5. Validate against Beken-specific constraints")

if __name__ == "__main__":
    analyze_beken_patterns()