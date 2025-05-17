#!/usr/bin/env python3
"""
Analyze the flaw in DMR capture that shows 11.5 hours of "decoded" audio
from only 30 minutes of actual capture time. This demonstrates the issue
with interpreting AMBE+2 codec artifacts as actual audio.
"""

import sqlite3
import numpy as np
from datetime import datetime, timedelta

def analyze_capture_vs_audio_time():
    """
    Compare actual capture time vs apparent "decoded" audio duration
    """
    # Connect to the most comprehensive database
    db_path = 'frame_log_EHAM100_2024-11-28_to_2024-12-01.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get actual capture time span
        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp), COUNT(*) 
            FROM frame_log 
            WHERE frame_type = 'DMR'
        """)
        
        result = cursor.fetchone()
        if result:
            min_time, max_time, frame_count = result
            
            # Parse timestamps
            start_time = datetime.fromisoformat(min_time.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(max_time.replace('Z', '+00:00'))
            
            # Calculate actual capture duration
            actual_duration = end_time - start_time
            actual_minutes = actual_duration.total_seconds() / 60
            
            print(f"Actual capture analysis:")
            print(f"Start time: {start_time}")
            print(f"End time: {end_time}")
            print(f"Duration: {actual_duration}")
            print(f"Total minutes: {actual_minutes:.2f}")
            print(f"Total frames: {frame_count}")
            
            # Now analyze the "beep" patterns that appear to be audio
            cursor.execute("""
                SELECT timestamp, data 
                FROM frame_log 
                WHERE frame_type = 'DMR' 
                AND data LIKE '%BEEP%'
                ORDER BY timestamp
            """)
            
            beep_count = 0
            first_beep = None
            last_beep = None
            
            for row in cursor.fetchall():
                timestamp, data = row
                beep_count += 1
                beep_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                if first_beep is None:
                    first_beep = beep_time
                last_beep = beep_time
            
            if beep_count > 0:
                beep_duration = last_beep - first_beep
                beep_minutes = beep_duration.total_seconds() / 60
                
                print(f"\nBeep pattern analysis:")
                print(f"Total beeps found: {beep_count}")
                print(f"First beep: {first_beep}")
                print(f"Last beep: {last_beep}")
                print(f"Beep span: {beep_duration}")
                print(f"Beep span minutes: {beep_minutes:.2f}")
                
                # Calculate the discrepancy
                print(f"\nDiscrepancy analysis:")
                print(f"Capture time: {actual_minutes:.2f} minutes")
                print(f"Apparent 'audio' time: {11.5 * 60} minutes (690 minutes)")
                print(f"Multiplication factor: {(11.5 * 60) / actual_minutes:.2f}x")
            
            # Analyze frame timing for AMBE+2 artifacts
            cursor.execute("""
                SELECT timestamp, data 
                FROM frame_log 
                WHERE frame_type = 'DMR' 
                AND (data LIKE '%audio%' OR data LIKE '%voice%')
                ORDER BY timestamp
                LIMIT 1000
            """)
            
            audio_frames = cursor.fetchall()
            
            if len(audio_frames) > 1:
                # Calculate inter-frame timing
                inter_frame_times = []
                
                for i in range(1, len(audio_frames)):
                    t1 = datetime.fromisoformat(audio_frames[i-1][0].replace('Z', '+00:00'))
                    t2 = datetime.fromisoformat(audio_frames[i][0].replace('Z', '+00:00'))
                    delta = (t2 - t1).total_seconds()
                    inter_frame_times.append(delta)
                
                avg_inter_frame = np.mean(inter_frame_times)
                
                print(f"\nAMBE+2 frame timing analysis:")
                print(f"Average inter-frame time: {avg_inter_frame:.6f} seconds")
                print(f"Expected for 20ms frames: 0.020 seconds")
                print(f"Timing ratio: {avg_inter_frame / 0.020:.2f}x")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        print("Expected behavior - database might not be available in this environment")

def explain_vocoder_artifacts():
    """
    Explain why the person's AES assumption is wrong
    """
    print("\n=== Why the AES Assumption is Wrong ===")
    print("\n1. AMBE+2 Vocoder Behavior:")
    print("   - AMBE+2 is a low-bitrate voice codec (2450 bits/sec)")
    print("   - Designed for human speech patterns")
    print("   - When fed non-speech data, it produces artifacts")
    print("   - These artifacts can appear as 'beep' patterns")
    
    print("\n2. The 11.5 Hour 'Audio' Problem:")
    print("   - 30 minutes of capture time")
    print("   - Claims 11.5 hours of decoded audio")
    print("   - That's a 23x multiplication factor")
    print("   - Physically impossible without time dilation!")
    
    print("\n3. What's Actually Happening:")
    print("   - AMBE+2 decoder is fed with non-audio data")
    print("   - Vocoder tries to interpret random/encrypted bits")
    print("   - Produces repetitive patterns (beeps)")
    print("   - Frame timing confusion causes time calculation errors")
    
    print("\n4. Evidence Against AES:")
    print("   - AES-128 produces completely random ciphertext")
    print("   - Would not produce consistent beep patterns")
    print("   - DMR uses RC4 for Basic Privacy")
    print("   - Enhanced Privacy uses AES but with proper audio headers")
    
    print("\n5. The Real Explanation:")
    print("   - DMR Basic Privacy uses 40-bit RC4")
    print("   - MI (Message Indicator) allows synchronization")
    print("   - LFSR-based key generation creates patterns")
    print("   - Vocoder artifacts from decoding encrypted voice data")

if __name__ == "__main__":
    print("DMR Capture Time vs Audio Time Analysis")
    print("======================================")
    
    # First, show the theoretical problem
    explain_vocoder_artifacts()
    
    # Then try to analyze actual data
    print("\n\nAttempting to analyze actual capture data...")
    analyze_capture_vs_audio_time()