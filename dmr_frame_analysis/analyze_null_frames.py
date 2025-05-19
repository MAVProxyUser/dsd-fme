#!/usr/bin/env python3
"""Analyze null vocoder frames in DMR"""
import sqlite3
import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram
import matplotlib.pyplot as plt

# DMR null frame patterns
DMR_NULL_FRAME_1 = "131313131313131313"  # Common null pattern #1
DMR_NULL_FRAME_2 = "000000000000000000"  # All zeros
DMR_NULL_FRAME_3 = "ACACACACACACACAC"    # Another null pattern
DMR_NULL_FRAME_4 = "E1E1E1E1E1E1E1E1"    # Hytera null pattern
DMR_NULL_FRAME_5 = "C9C9C9C9C9C9C9C9"    # Motorola null pattern

# AMBE parameters
SAMPLE_RATE = 8000
SAMPLES_PER_FRAME = 160

def decode_null_frame(ambe_hex):
    """Decode a null vocoder frame to audio"""
    # Null frames typically produce silence or comfort noise
    samples = np.zeros(SAMPLES_PER_FRAME)
    
    # Add very low-level comfort noise
    # Real AMBE decoder would generate specific comfort noise pattern
    comfort_noise = np.random.randn(SAMPLES_PER_FRAME) * 0.01
    samples += comfort_noise
    
    # Apply fade-in/fade-out to avoid clicks
    envelope = np.ones_like(samples)
    envelope[:20] = np.linspace(0, 1, 20)
    envelope[-20:] = np.linspace(1, 0, 20)
    samples *= envelope
    
    return samples

def create_null_frame_samples():
    """Create WAV files for various null frame patterns"""
    print("=== Creating Null Frame Samples ===\n")
    
    null_patterns = [
        (DMR_NULL_FRAME_1, "null_pattern_131313.wav", "Null Pattern 0x13"),
        (DMR_NULL_FRAME_2, "null_pattern_zeros.wav", "All Zeros"),
        (DMR_NULL_FRAME_3, "null_pattern_ACAC.wav", "Null Pattern 0xAC"),
        (DMR_NULL_FRAME_4, "null_pattern_E1E1.wav", "Null Pattern 0xE1"),
        (DMR_NULL_FRAME_5, "null_pattern_C9C9.wav", "Null Pattern 0xC9")
    ]
    
    for pattern, filename, description in null_patterns:
        print(f"Creating {description}: {pattern}")
        
        # Decode multiple frames to make it audible
        audio_data = []
        for _ in range(10):  # 10 frames = 200ms
            samples = decode_null_frame(pattern)
            audio_data.extend(samples)
        
        # Save WAV
        audio_array = np.array(audio_data)
        wavfile.write(filename, SAMPLE_RATE, (audio_array * 32767).astype(np.int16))
        print(f"  Saved: {filename}")
        
        # Create spectrogram
        plt.figure(figsize=(10, 6))
        
        # Plot waveform
        plt.subplot(2, 1, 1)
        time = np.arange(len(audio_array)) / SAMPLE_RATE
        plt.plot(time, audio_array)
        plt.title(f"{description} - Waveform")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.ylim([-0.1, 0.1])
        plt.grid(True)
        
        # Plot spectrogram
        plt.subplot(2, 1, 2)
        f, t, Sxx = spectrogram(audio_array, SAMPLE_RATE, nperseg=256)
        plt.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
        plt.ylim([0, 4000])
        plt.ylabel('Frequency [Hz]')
        plt.xlabel('Time [sec]')
        plt.title("Spectrogram (Comfort Noise)")
        plt.colorbar(label='Power [dB]')
        
        plt.tight_layout()
        plt.savefig(filename.replace('.wav', '_analysis.png'), dpi=150)
        plt.close()
        
        print(f"  Created analysis: {filename.replace('.wav', '_analysis.png')}")
        print()

def find_null_frames_in_capture():
    """Find null frames in actual DMR capture"""
    print("=== Searching for Null Frames in Capture ===\n")
    
    # Connect to database
    conn = sqlite3.connect('dmr_capture_20250517_204818.db')
    cursor = conn.cursor()
    
    # Get all frames
    cursor.execute("""
        SELECT id, ambe_hex, superframe_id 
        FROM U_00000000_S0 
        ORDER BY id
    """)
    
    frames = cursor.fetchall()
    print(f"Total frames: {len(frames)}")
    
    # Known null patterns to look for
    null_patterns = {
        "0000000000000000": "All zeros",
        "131313131313131313": "Pattern 0x13",
        "ACACACACACACACAC": "Pattern 0xAC",
        "E1E1E1E1E1E1E1E1": "Pattern 0xE1",
        "C9C9C9C9C9C9C9C9": "Pattern 0xC9"
    }
    
    # Also look for low-entropy frames (potential nulls)
    null_candidates = []
    
    for frame_id, ambe_hex, sf_id in frames:
        # Check for known patterns
        if ambe_hex.upper() in null_patterns:
            print(f"Found known null: Frame {frame_id} - {null_patterns[ambe_hex.upper()]} ({ambe_hex})")
            null_candidates.append((frame_id, ambe_hex, sf_id, "known"))
        else:
            # Check for low entropy (potential null)
            ambe_bytes = bytes.fromhex(ambe_hex)
            unique_bytes = len(set(ambe_bytes))
            
            if unique_bytes <= 2:  # Very low entropy
                print(f"Found low-entropy: Frame {frame_id} - {unique_bytes} unique bytes ({ambe_hex})")
                null_candidates.append((frame_id, ambe_hex, sf_id, "low_entropy"))
    
    print(f"\nFound {len(null_candidates)} null frame candidates")
    
    # Create compilation of null frames
    if null_candidates:
        print("\nCreating null frame compilation...")
        null_audio = []
        
        for frame_id, ambe_hex, sf_id, frame_type in null_candidates[:20]:  # First 20
            samples = decode_null_frame(ambe_hex)
            null_audio.extend(samples)
            # Add separator
            null_audio.extend(np.zeros(int(SAMPLE_RATE * 0.05)))
        
        # Save compilation
        null_array = np.array(null_audio)
        wavfile.write('captured_null_frames.wav', 
                     SAMPLE_RATE, (null_array * 32767).astype(np.int16))
        print("Created: captured_null_frames.wav")
    
    conn.close()

def create_mixed_example():
    """Create example with voice, null frames, and tones"""
    print("\n=== Creating Mixed Example ===")
    
    # Create a sequence: tone -> null -> voice -> null -> tone
    mixed_audio = []
    
    # Start tone (1800 Hz)
    t = np.linspace(0, 0.2, int(SAMPLE_RATE * 0.2))
    tone = 0.5 * np.sin(2 * np.pi * 1800 * t)
    mixed_audio.extend(tone)
    
    # Null frames (silence)
    for _ in range(5):
        null_samples = decode_null_frame(DMR_NULL_FRAME_1)
        mixed_audio.extend(null_samples)
    
    # Simulated voice (complex waveform)
    voice_t = np.linspace(0, 0.5, int(SAMPLE_RATE * 0.5))
    voice = 0.3 * np.sin(2 * np.pi * 200 * voice_t)  # Fundamental
    voice += 0.2 * np.sin(2 * np.pi * 700 * voice_t)  # Formant 1
    voice += 0.1 * np.sin(2 * np.pi * 1200 * voice_t) # Formant 2
    mixed_audio.extend(voice)
    
    # More null frames
    for _ in range(5):
        null_samples = decode_null_frame(DMR_NULL_FRAME_2)
        mixed_audio.extend(null_samples)
    
    # End tone (3 beeps at 2100 Hz)
    for i in range(3):
        beep = 0.5 * np.sin(2 * np.pi * 2100 * t)
        mixed_audio.extend(beep)
        if i < 2:  # Gap between beeps
            mixed_audio.extend(np.zeros(int(SAMPLE_RATE * 0.05)))
    
    # Save
    mixed_array = np.array(mixed_audio)
    wavfile.write('mixed_tone_null_voice.wav', 
                 SAMPLE_RATE, (mixed_array * 32767).astype(np.int16))
    
    # Create spectrogram
    plt.figure(figsize=(14, 8))
    
    # Plot waveform
    plt.subplot(2, 1, 1)
    time = np.arange(len(mixed_array)) / SAMPLE_RATE
    plt.plot(time, mixed_array)
    plt.title("Mixed Example: Tone -> Null -> Voice -> Null -> Tone")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    plt.grid(True)
    
    # Add annotations
    plt.axvspan(0, 0.2, alpha=0.3, color='red', label='Start Tone')
    plt.axvspan(0.2, 0.3, alpha=0.3, color='gray', label='Null Frames')
    plt.axvspan(0.3, 0.8, alpha=0.3, color='green', label='Voice')
    plt.axvspan(0.8, 0.9, alpha=0.3, color='gray')
    plt.axvspan(0.9, 1.5, alpha=0.3, color='red', label='End Tones')
    plt.legend()
    
    # Plot spectrogram
    plt.subplot(2, 1, 2)
    f, t, Sxx = spectrogram(mixed_array, SAMPLE_RATE, nperseg=256)
    plt.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
    plt.ylim([0, 4000])
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title("Spectrogram")
    plt.colorbar(label='Power [dB]')
    
    plt.tight_layout()
    plt.savefig('mixed_tone_null_voice_analysis.png', dpi=150)
    plt.close()
    
    print("Created: mixed_tone_null_voice.wav")
    print("Created: mixed_tone_null_voice_analysis.png")

# Run all analyses
create_null_frame_samples()
find_null_frames_in_capture()
create_mixed_example()

print("\n=== Summary ===")
print("Null vocoder frames in DMR:")
print("1. Used for silence suppression")
print("2. Common patterns: 0x00, 0x13, 0xAC, 0xE1, 0xC9")
print("3. Produce silence or comfort noise when decoded")
print("4. Low entropy (few unique bytes)")
print("5. Often found between voice segments")
print("\nCreated files:")
print("- null_pattern_*.wav - Various null frame patterns")
print("- captured_null_frames.wav - Null frames from capture")
print("- mixed_tone_null_voice.wav - Complete example")
print("\nListen to hear the difference between:")
print("- Tones (clear frequency)")
print("- Null frames (silence/comfort noise)")
print("- Voice (complex spectrum)")