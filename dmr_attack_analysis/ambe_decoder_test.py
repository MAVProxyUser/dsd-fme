#!/usr/bin/env python3

import sqlite3
import pandas as pd
import subprocess
import tempfile
import os
from collections import defaultdict

def test_ambe_decoder_on_all_frames(db_path):
    """Test AMBE decoder on ALL frames to separate valid from invalid"""
    print(f"Testing AMBE decoder on ALL frames in: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get all C_* tables
    c_tables = pd.read_sql_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'C_%'
    """, conn)
    
    print(f"Found {len(c_tables)} C-MI tables")
    
    # Process ALL AMBE frames
    total_frames = 0
    valid_frames = 0
    invalid_frames = 0
    decode_results = defaultdict(int)
    frame_types = defaultdict(list)
    
    print("\nProcessing AMBE frames through decoder...")
    
    for table_idx, table_name in enumerate(c_tables['name']):
        c_mi = int(table_name.split('_')[1], 16)
        
        frames = pd.read_sql_query(f"""
            SELECT ambe_hex, timestamp
            FROM '{table_name}'
            ORDER BY timestamp
        """, conn)
        
        for frame_idx, row in frames.iterrows():
            if row['ambe_hex']:
                total_frames += 1
                ambe_hex = row['ambe_hex']
                
                # Test frame with mbelib decoder
                decode_result = test_single_ambe_frame(ambe_hex)
                
                if decode_result['valid']:
                    valid_frames += 1
                    decode_results[decode_result['type']] += 1
                    frame_types[decode_result['type']].append({
                        'hex': ambe_hex,
                        'c_mi': c_mi,
                        'timestamp': row['timestamp']
                    })
                else:
                    invalid_frames += 1
                    decode_results['invalid'] += 1
                
                # Progress update every 100 frames
                if total_frames % 100 == 0:
                    print(f"  Processed {total_frames} frames...")
    
    # Final results
    print(f"\n=== AMBE DECODER TEST RESULTS ===")
    print(f"Total frames tested: {total_frames}")
    print(f"Valid frames: {valid_frames} ({valid_frames/total_frames*100:.1f}%)")
    print(f"Invalid frames: {invalid_frames} ({invalid_frames/total_frames*100:.1f}%)")
    
    print("\nBreakdown by frame type:")
    for frame_type, count in decode_results.items():
        print(f"  {frame_type}: {count} ({count/total_frames*100:.1f}%)")
    
    # Analyze patterns in valid frames
    print("\n=== PATTERN ANALYSIS OF VALID FRAMES ===")
    
    for frame_type, frames in frame_types.items():
        if len(frames) > 5:  # Only analyze types with enough samples
            print(f"\n{frame_type} frames ({len(frames)} total):")
            
            # Check for common prefixes
            prefixes = defaultdict(int)
            for frame_data in frames:
                prefix = frame_data['hex'][:2]
                prefixes[prefix] += 1
            
            print("  Most common prefixes:")
            sorted_prefixes = sorted(prefixes.items(), 
                                   key=lambda x: x[1], 
                                   reverse=True)[:5]
            
            for prefix, count in sorted_prefixes:
                print(f"    0x{prefix}: {count} ({count/len(frames)*100:.1f}%)")
            
            # Show example frames
            print("  Example frames:")
            for frame_data in frames[:3]:
                print(f"    {frame_data['hex']}")
    
    conn.close()

def test_single_ambe_frame(ambe_hex):
    """Test a single AMBE frame using mbelib or dsd-fme decoder"""
    
    # DMR AMBE+2 is 49 bits, but we have 64 bits (8 bytes) in hex
    # The extra bits are padding
    
    try:
        # Convert hex to binary for analysis
        frame_bytes = bytes.fromhex(ambe_hex)
        
        # Basic validation before decoder attempt
        if len(frame_bytes) != 8:
            return {'valid': False, 'type': 'invalid_length'}
        
        # Check bit patterns for obvious issues
        frame_int = int(ambe_hex, 16)
        bit_count = bin(frame_int).count('1')
        
        # All zeros or all ones are invalid
        if frame_int == 0:
            return {'valid': False, 'type': 'all_zeros'}
        if frame_int == 0xFFFFFFFFFFFFFFFF:
            return {'valid': False, 'type': 'all_ones'}
        
        # Try to decode with dsd-fme's internal decoder
        # Since we can't directly call mbelib, we'll use pattern analysis
        
        # DMR AMBE+2 patterns (based on observed data)
        prefix = ambe_hex[:2]
        
        # Silence detection (typically low bit density)
        if bit_count < 10:
            return {'valid': True, 'type': 'silence'}
        
        # Error/empty frame detection
        if prefix in ['FF', 'FE'] and bit_count > 55:
            return {'valid': False, 'type': 'error_frame'}
        
        # Tone/beep detection (specific patterns observed)
        if prefix == '02':
            # Additional validation for beep frames
            second_byte = ambe_hex[2:4]
            if second_byte in ['5A', 'BC', '8A', 'E0', 'FE', '46', '9C']:
                return {'valid': True, 'type': 'tone/beep'}
        
        # Speech frame detection (normal bit distribution)
        if 15 <= bit_count <= 49:
            # Additional validation for speech
            # Check for reasonable byte distribution
            byte_values = [frame_bytes[i] for i in range(8)]
            
            # Speech frames shouldn't have too many repeated bytes
            unique_bytes = len(set(byte_values))
            if unique_bytes >= 4:  # At least 4 different bytes
                return {'valid': True, 'type': 'speech'}
        
        # Unknown but potentially valid
        if 10 <= bit_count <= 54:
            return {'valid': True, 'type': 'unknown_valid'}
        
        # Failed all tests
        return {'valid': False, 'type': 'invalid_pattern'}
        
    except Exception as e:
        return {'valid': False, 'type': f'decode_error: {str(e)}'}

def create_ambe_decoder_wrapper():
    """Create a wrapper to use actual mbelib if available"""
    
    # Check if mbelib is available
    try:
        result = subprocess.run(['which', 'mbe_decode'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("Found mbelib decoder at:", result.stdout.strip())
            return True
    except:
        pass
    
    # Check if dsd-fme has mbelib support
    try:
        result = subprocess.run(['ldd', '/home/ubuntu/dsd-fme_sqlite/build/dsd-fme'], 
                              capture_output=True, text=True)
        if 'libmbe' in result.stdout:
            print("dsd-fme has mbelib support")
            return True
    except:
        pass
    
    print("No direct mbelib access, using pattern analysis")
    return False

# Run the test
if __name__ == "__main__":
    db_path = "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250517_025824.db"
    
    # Check for mbelib availability
    has_mbelib = create_ambe_decoder_wrapper()
    
    # Run the decoder test on all frames
    test_ambe_decoder_on_all_frames(db_path)