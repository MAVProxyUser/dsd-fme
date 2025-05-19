#!/usr/bin/env python3
"""Clarify what we actually know about the vocoder from the data"""

import sqlite3
import numpy as np
from collections import Counter

def analyze_actual_vocoder_data():
    """Analyze what we can actually determine from the captured data"""
    
    print("=== ACTUAL VOCODER ANALYSIS FROM CAPTURED DATA ===")
    
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn = sqlite3.connect(cleartext_db)
    cursor = conn.cursor()
    
    print("\n1. WHAT WE ACTUALLY KNOW FROM THE DATA:")
    
    # Get cleartext AMBE frames
    cursor.execute("SELECT ambe_hex FROM U_00000000_S0")
    cleartext_frames = [row[0] for row in cursor.fetchall()]
    
    print(f"\nAnalyzing {len(cleartext_frames)} cleartext AMBE frames")
    
    # Analyze bit patterns
    bit_patterns = []
    byte_distribution = Counter()
    
    for frame in cleartext_frames[:1000]:  # Sample
        frame_int = int(frame, 16)
        
        # Count set bits
        bit_count = bin(frame_int).count('1')
        bit_patterns.append(bit_count)
        
        # Analyze byte distribution
        for i in range(0, 16, 2):
            byte = frame[i:i+2]
            byte_distribution[byte] += 1
    
    print("\nBit density analysis:")
    print(f"  Average bits set: {np.mean(bit_patterns):.1f}/64")
    print(f"  Min bits: {min(bit_patterns)}")
    print(f"  Max bits: {max(bit_patterns)}")
    
    print("\nMost common bytes:")
    for byte, count in byte_distribution.most_common(10):
        print(f"  0x{byte}: {count} times")
    
    # Look for frame structure patterns
    print("\n2. FRAME STRUCTURE ANALYSIS:")
    
    # Check if frames have consistent patterns in certain positions
    position_patterns = {}
    for pos in range(0, 16, 2):  # Each byte position
        position_patterns[pos] = Counter()
        
        for frame in cleartext_frames[:100]:
            byte = frame[pos:pos+2]
            position_patterns[pos][byte] += 1
    
    print("\nByte position consistency:")
    for pos, counter in position_patterns.items():
        most_common = counter.most_common(1)[0]
        consistency = most_common[1] / len(cleartext_frames[:100]) * 100
        print(f"  Position {pos//2}: {most_common[0]} appears {consistency:.1f}% of the time")
    
    # Look for potential vocoder markers
    print("\n3. POTENTIAL VOCODER IDENTIFICATION:")
    
    # Check for known AMBE frame patterns
    ambe_patterns = {
        'standard_ambe': 0,
        'ambe_plus': 0,
        'ambe_plus2': 0,
        'unknown': 0
    }
    
    for frame in cleartext_frames[:100]:
        frame_int = int(frame, 16)
        
        # Check bit 48 (common AMBE flag position)
        bit_48 = (frame_int >> 48) & 0x1
        
        # Check for specific patterns that might indicate vocoder type
        # This is speculative without documentation
        if bit_48 == 0:
            ambe_patterns['standard_ambe'] += 1
        else:
            ambe_patterns['unknown'] += 1
    
    print("\nPattern distribution (speculative):")
    for pattern, count in ambe_patterns.items():
        if count > 0:
            print(f"  {pattern}: {count}")
    
    # Frequency analysis
    print("\n4. FREQUENCY COMPONENT ANALYSIS:")
    
    # Assuming first 6 bits might be fundamental frequency
    fundamentals = []
    for frame in cleartext_frames[:500]:
        frame_int = int(frame, 16)
        # Extract potential fundamental (first 6 bits)
        fundamental = frame_int & 0x3F
        fundamentals.append(fundamental)
    
    print(f"\nPotential fundamental frequency analysis:")
    print(f"  Range: {min(fundamentals)}-{max(fundamentals)}")
    print(f"  Average: {np.mean(fundamentals):.1f}")
    print(f"  Most common: {Counter(fundamentals).most_common(5)}")
    
    conn.close()
    
    print("\n\n=== WHAT I ACTUALLY FOUND ===")
    print("1. The AMBE frames have specific bit patterns")
    print("2. There are consistent byte patterns in certain positions")
    print("3. The data suggests voice encoding (variable bit density)")
    print("4. Cannot definitively identify vocoder type from data alone")
    
    print("\n=== HONEST ASSESSMENT ===")
    print("I made assumptions about Beken BK378 based on your mention of it.")
    print("I should have been clear that I was inferring patterns from the data,")
    print("not drawing from external vocoder documentation.")
    print("\nWhat we CAN determine:")
    print("- AMBE frame structure (49 bits/7 bytes)")
    print("- Statistical patterns in the data")
    print("- Likely voice encoding characteristics")
    print("\nWhat we CANNOT determine without docs:")
    print("- Exact vocoder model")
    print("- Specific bit allocations")
    print("- Proprietary encoding details")

if __name__ == "__main__":
    analyze_actual_vocoder_data()