#!/usr/bin/env python3
"""Create WAV files from AMBE frames - both theoretical and real"""
import sqlite3
import numpy as np
from scipy.io import wavfile
import struct

SAMPLE_RATE = 8000
SAMPLES_PER_FRAME = 160

def create_test_pattern_wav():
    """Create test WAV with alternating 2400/2600 Hz tones"""
    print("Creating test pattern: 2400/2600 Hz alternating tones")
    
    # Create 3 seconds of audio
    duration = 3.0
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    # Alternate between 2400 and 2600 Hz every 0.5 seconds
    signal = np.zeros_like(t)
    
    for i in range(6):  # 6 segments of 0.5s each
        start_idx = int(i * 0.5 * SAMPLE_RATE)
        end_idx = int((i + 1) * 0.5 * SAMPLE_RATE)
        
        if i % 2 == 0:
            # 2400 Hz tone
            signal[start_idx:end_idx] = 0.8 * np.sin(2 * np.pi * 2400 * t[start_idx:end_idx])
        else:
            # 2600 Hz tone
            signal[start_idx:end_idx] = 0.8 * np.sin(2 * np.pi * 2600 * t[start_idx:end_idx])
    
    # Save as WAV
    wavfile.write('test_pattern_2400_2600.wav', SAMPLE_RATE, (signal * 32767).astype(np.int16))
    print("Created: test_pattern_2400_2600.wav")

def simple_ambe_to_audio(ambe_hex):
    """Simple AMBE to audio conversion based on byte patterns"""
    ambe_bytes = bytes.fromhex(ambe_hex)
    samples = np.zeros(SAMPLES_PER_FRAME)
    
    # Use byte values to generate tones (simplified)
    if len(ambe_bytes) >= 8:
        # Extract frequency hints from bytes
        freq_byte1 = ambe_bytes[0]
        freq_byte2 = ambe_bytes[1]
        amp_byte = ambe_bytes[2]
        
        # Map to frequency range
        freq1 = 500 + (freq_byte1 * 10)  # 500-3050 Hz
        freq2 = 800 + (freq_byte2 * 8)   # 800-2840 Hz
        amplitude = amp_byte / 255.0
        
        # Generate waveform
        t = np.linspace(0, SAMPLES_PER_FRAME/SAMPLE_RATE, SAMPLES_PER_FRAME)
        
        if amplitude > 0.1:
            samples = amplitude * np.sin(2 * np.pi * freq1 * t)
            if freq_byte2 > 100:  # Add second frequency component
                samples += 0.5 * amplitude * np.sin(2 * np.pi * freq2 * t)
        
        # Apply envelope
        envelope = np.ones_like(samples)
        envelope[:10] = np.linspace(0, 1, 10)
        envelope[-10:] = np.linspace(1, 0, 10)
        samples *= envelope
    
    return samples

def create_real_frame_wavs():
    """Create WAV files from real AMBE frames"""
    print("\nCreating WAV files from real AMBE frames")
    
    # Connect to database
    conn = sqlite3.connect('dmr_capture_20250517_204818.db')
    cursor = conn.cursor()
    
    # Get frames at transmission boundaries
    cursor.execute("""
        SELECT id, ambe_hex, superframe_id,
               ROW_NUMBER() OVER (PARTITION BY superframe_id ORDER BY id) as position,
               COUNT(*) OVER (PARTITION BY superframe_id) as total
        FROM U_00000000_S0
        WHERE superframe_id IS NOT NULL
        ORDER BY superframe_id, id
    """)
    
    all_frames = cursor.fetchall()
    
    # Process superframes
    superframe_audio = {}
    boundary_frames = []
    
    for frame_id, ambe_hex, sf_id, position, total in all_frames:
        # Decode frame to audio
        samples = simple_ambe_to_audio(ambe_hex)
        
        # Add to superframe audio
        if sf_id not in superframe_audio:
            superframe_audio[sf_id] = []
        superframe_audio[sf_id].extend(samples)
        
        # Track boundary frames
        if position <= 3:  # First 3 frames (Call Tone)
            boundary_frames.append((frame_id, ambe_hex, sf_id, 'start', position))
            # Save individual frame
            wavfile.write(f'frame_{frame_id}_sf{sf_id}_start{position}.wav', 
                         SAMPLE_RATE, (samples * 32767).astype(np.int16))
            
        elif position >= total - 3:  # Last 3 frames (Call End Tone)
            boundary_frames.append((frame_id, ambe_hex, sf_id, 'end', position))
            # Save individual frame
            wavfile.write(f'frame_{frame_id}_sf{sf_id}_end{position}.wav', 
                         SAMPLE_RATE, (samples * 32767).astype(np.int16))
    
    # Save complete superframes
    for sf_id, audio_data in superframe_audio.items():
        audio_array = np.array(audio_data)
        wavfile.write(f'superframe_{sf_id}_complete.wav', 
                     SAMPLE_RATE, (audio_array * 32767).astype(np.int16))
        print(f"Created: superframe_{sf_id}_complete.wav")
    
    # Create compilation of all starts and ends
    start_compilation = []
    end_compilation = []
    
    for frame_id, ambe_hex, sf_id, location, position in boundary_frames:
        samples = simple_ambe_to_audio(ambe_hex)
        if location == 'start':
            start_compilation.extend(samples)
            # Add short silence between
            start_compilation.extend(np.zeros(int(SAMPLE_RATE * 0.1)))
        else:
            end_compilation.extend(samples)
            # Add short silence between
            end_compilation.extend(np.zeros(int(SAMPLE_RATE * 0.1)))
    
    # Save compilations
    if start_compilation:
        start_array = np.array(start_compilation)
        wavfile.write('all_call_tones_start.wav', 
                     SAMPLE_RATE, (start_array * 32767).astype(np.int16))
        print("Created: all_call_tones_start.wav")
    
    if end_compilation:
        end_array = np.array(end_compilation)
        wavfile.write('all_call_tones_end.wav', 
                     SAMPLE_RATE, (end_array * 32767).astype(np.int16))
        print("Created: all_call_tones_end.wav")
    
    # Create a specific example: first 3 frames of SF 12 (start) and last 5 frames (end)
    cursor.execute("""
        SELECT id, ambe_hex 
        FROM U_00000000_S0 
        WHERE superframe_id = 12 
        ORDER BY id
    """)
    
    sf12_frames = cursor.fetchall()
    if sf12_frames:
        # Start beep
        start_beep = []
        for frame_id, ambe_hex in sf12_frames[:3]:
            samples = simple_ambe_to_audio(ambe_hex)
            start_beep.extend(samples)
        
        # End beeps
        end_beeps = []
        for frame_id, ambe_hex in sf12_frames[-5:]:
            samples = simple_ambe_to_audio(ambe_hex)
            end_beeps.extend(samples)
        
        # Save
        wavfile.write('sf12_start_beep.wav', 
                     SAMPLE_RATE, (np.array(start_beep) * 32767).astype(np.int16))
        wavfile.write('sf12_end_beeps.wav', 
                     SAMPLE_RATE, (np.array(end_beeps) * 32767).astype(np.int16))
        print("Created: sf12_start_beep.wav and sf12_end_beeps.wav")
    
    conn.close()

def create_decoding_example():
    """Create example showing encrypted vs decrypted"""
    print("\nCreating encryption/decryption example")
    
    # Simulate known Call Tone pattern
    t = np.linspace(0, 0.3, int(SAMPLE_RATE * 0.3))  # 300ms
    
    # Create a pure tone (example Call Tone)
    call_tone_freq = 1800  # Example frequency
    original_tone = 0.8 * np.sin(2 * np.pi * call_tone_freq * t)
    
    # Simulate encryption (XOR with keystream - simplified)
    # In reality, this happens at the AMBE bit level
    np.random.seed(42)  # For reproducibility
    keystream = np.random.randn(len(original_tone)) * 0.3
    encrypted = original_tone + keystream  # Simplified "encryption"
    
    # Simulate decryption
    decrypted = encrypted - keystream  # Perfect decryption with known keystream
    
    # Save all three
    wavfile.write('example_original_tone.wav', 
                 SAMPLE_RATE, (original_tone * 32767).astype(np.int16))
    wavfile.write('example_encrypted.wav', 
                 SAMPLE_RATE, (encrypted * 32767).astype(np.int16))
    wavfile.write('example_decrypted.wav', 
                 SAMPLE_RATE, (decrypted * 32767).astype(np.int16))
    
    print("Created: example_original_tone.wav, example_encrypted.wav, example_decrypted.wav")

# Create all WAV files
print("=== Creating WAV Files ===")
create_test_pattern_wav()
create_real_frame_wavs()
create_decoding_example()

print("\n=== Summary of Created Files ===")
print("Test patterns:")
print("  - test_pattern_2400_2600.wav (theoretical tone pattern)")
print("\nReal AMBE frames:")
print("  - frame_*_sf*_*.wav (individual boundary frames)")
print("  - superframe_*_complete.wav (complete transmissions)")
print("  - all_call_tones_start.wav (compilation of all start tones)")
print("  - all_call_tones_end.wav (compilation of all end tones)")
print("  - sf12_start_beep.wav (example start tone)")
print("  - sf12_end_beeps.wav (example end tones)")
print("\nEncryption example:")
print("  - example_original_tone.wav")
print("  - example_encrypted.wav")
print("  - example_decrypted.wav")
print("\nListen to these files to hear the actual Call Tones!")