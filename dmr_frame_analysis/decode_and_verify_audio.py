#!/usr/bin/env python3
"""Decode AMBE frames with best keystream candidate and verify audio"""

import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import base64

def decode_with_best_keystream():
    """Use best keystream to decode frames and analyze audio"""
    
    encrypted_db = "dmr_capture_20250518_112024_998484.db"
    conn = sqlite3.connect(encrypted_db)
    cursor = conn.cursor()
    
    print("=== DECODING ENCRYPTED AUDIO WITH BEST KEYSTREAM ===")
    
    # Use the best keystream found
    best_keystream = 0x66B8730000F58800  # From previous analysis
    
    # Get all frames for target MI
    target_mi = 0xE8083B57
    table_name = f"C_{target_mi:08X}_S0"
    
    cursor.execute(f"SELECT id, ambe_hex, superframe_id FROM '{table_name}' ORDER BY id")
    encrypted_frames = cursor.fetchall()
    
    print(f"\nDecoding {len(encrypted_frames)} frames with keystream: {best_keystream:016X}")
    
    # Decode all frames
    decoded_frames = []
    audio_parameters = []
    
    for frame_id, enc_hex, sf_id in encrypted_frames:
        enc_int = int(enc_hex, 16)
        dec_int = enc_int ^ best_keystream
        dec_hex = f"{dec_int:016X}"
        
        # Extract AMBE parameters
        fundamental = (dec_int >> 58) & 0x3F
        voicing = (dec_int >> 49) & 0x1FF
        spectral_mags = []
        
        for i in range(8):
            mag = (dec_int >> (i * 6)) & 0x3F
            spectral_mags.append(mag)
        
        decoded_frames.append(dec_hex)
        audio_parameters.append({
            'fundamental': fundamental,
            'voicing': voicing,
            'spectral': spectral_mags
        })
    
    # Analyze audio characteristics
    print("\n=== AUDIO ANALYSIS ===")
    
    fundamentals = [p['fundamental'] for p in audio_parameters]
    fundamental_hz = [f * 8 for f in fundamentals]  # Convert to Hz
    
    print(f"Fundamental frequency statistics:")
    print(f"  Range: {min(fundamental_hz)}-{max(fundamental_hz)} Hz")
    print(f"  Average: {np.mean(fundamental_hz):.1f} Hz")
    print(f"  Std Dev: {np.std(fundamental_hz):.1f} Hz")
    
    # Check for voice characteristics
    voice_range = sum(1 for f in fundamental_hz if 80 <= f <= 400)
    voice_percentage = voice_range / len(fundamental_hz) * 100
    
    print(f"\nVoice frequency analysis:")
    print(f"  Frames in voice range (80-400Hz): {voice_percentage:.1f}%")
    
    # Analyze voicing patterns
    voiced_frames = sum(1 for p in audio_parameters if p['voicing'] & 0x1)
    voiced_percentage = voiced_frames / len(audio_parameters) * 100
    
    print(f"  Voiced frames: {voiced_percentage:.1f}%")
    
    # Plot spectrogram-like visualization
    print("\n=== SPECTROGRAM VISUALIZATION ===")
    
    # Create time-frequency plot
    time_frames = range(len(audio_parameters))
    freq_data = np.array([p['spectral'] for p in audio_parameters]).T
    
    plt.figure(figsize=(12, 6))
    plt.imshow(freq_data, aspect='auto', origin='lower', cmap='viridis')
    plt.colorbar(label='Magnitude')
    plt.xlabel('Frame Number')
    plt.ylabel('Spectral Band')
    plt.title('Decoded AMBE Spectral Magnitudes')
    
    # Save plot
    plt.savefig('/home/ubuntu/dsd-fme_sqlite/build/decoded_spectrogram.png')
    plt.close()
    
    # Plot fundamental frequency over time
    plt.figure(figsize=(12, 4))
    plt.plot(fundamental_hz, label='Fundamental Frequency')
    plt.axhline(y=80, color='r', linestyle='--', alpha=0.5, label='Voice Range')
    plt.axhline(y=400, color='r', linestyle='--', alpha=0.5)
    plt.xlabel('Frame Number')
    plt.ylabel('Frequency (Hz)')
    plt.title('Fundamental Frequency Trajectory')
    plt.legend()
    
    plt.savefig('/home/ubuntu/dsd-fme_sqlite/build/fundamental_trajectory.png')
    plt.close()
    
    print("Saved visualizations to:")
    print("  - decoded_spectrogram.png")
    print("  - fundamental_trajectory.png")
    
    # Validate against known AMBE characteristics
    print("\n=== VALIDATION RESULTS ===")
    
    validation_score = 0
    
    # Check 1: Frequency range
    if 50 < np.mean(fundamental_hz) < 500:
        print("✓ Average frequency in valid range")
        validation_score += 25
    else:
        print("✗ Average frequency outside valid range")
    
    # Check 2: Frequency variation
    if 10 < np.std(fundamental_hz) < 150:
        print("✓ Natural frequency variation")
        validation_score += 25
    else:
        print("✗ Unnatural frequency variation")
    
    # Check 3: Voicing pattern
    if 30 < voiced_percentage < 80:
        print("✓ Reasonable voicing percentage")
        validation_score += 25
    else:
        print("✗ Unusual voicing percentage")
    
    # Check 4: Spectral continuity
    spectral_changes = []
    for i in range(1, len(audio_parameters)):
        change = sum(abs(audio_parameters[i]['spectral'][j] - audio_parameters[i-1]['spectral'][j]) 
                    for j in range(8))
        spectral_changes.append(change)
    
    avg_change = np.mean(spectral_changes)
    if 5 < avg_change < 50:
        print("✓ Natural spectral evolution")
        validation_score += 25
    else:
        print("✗ Unnatural spectral jumps")
    
    print(f"\nTotal validation score: {validation_score}/100")
    
    if validation_score >= 75:
        print("\n🎉 HIGH CONFIDENCE: This appears to be valid decoded speech!")
    elif validation_score >= 50:
        print("\n⚠️  MEDIUM CONFIDENCE: Partially valid audio characteristics")
    else:
        print("\n❌ LOW CONFIDENCE: Unlikely to be correctly decoded")
    
    # Save decoded frames for further analysis
    print("\n=== SAVING DECODED DATA ===")
    
    with open('/home/ubuntu/dsd-fme_sqlite/build/decoded_frames.txt', 'w') as f:
        f.write(f"Keystream: {best_keystream:016X}\n")
        f.write(f"MI: {target_mi:08X}\n")
        f.write(f"Total frames: {len(decoded_frames)}\n\n")
        
        for i, (frame, params) in enumerate(zip(decoded_frames, audio_parameters)):
            f.write(f"Frame {i}:\n")
            f.write(f"  Hex: {frame}\n")
            f.write(f"  Fundamental: {params['fundamental']} ({params['fundamental']*8} Hz)\n")
            f.write(f"  Voicing: {params['voicing']:09b}\n")
            f.write(f"  Spectral: {params['spectral']}\n\n")
    
    print("Saved decoded frames to: decoded_frames.txt")
    
    conn.close()
    
    print("\n=== NEXT STEPS ===")
    print("1. Use actual AMBE decoder (mbelib) to convert to PCM audio")
    print("2. Listen to decoded audio for intelligibility")
    print("3. Compare with reference cleartext audio patterns")
    print("4. Try other high-scoring keystream candidates")
    print("5. Capture synchronized encrypted/cleartext for definitive break")

if __name__ == "__main__":
    decode_with_best_keystream()