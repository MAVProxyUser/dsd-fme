#!/usr/bin/env python3
"""Analyze the created WAV files"""
import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram
import matplotlib.pyplot as plt

def analyze_wav(filename, title):
    """Analyze a WAV file and create spectrogram"""
    # Read WAV file
    rate, data = wavfile.read(filename)
    
    # Convert to float
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32767.0
    
    # Create figure
    plt.figure(figsize=(12, 8))
    
    # Plot waveform
    plt.subplot(2, 1, 1)
    time = np.arange(len(data)) / rate
    plt.plot(time, data)
    plt.title(f"{title} - Waveform")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    plt.grid(True)
    
    # Plot spectrogram
    plt.subplot(2, 1, 2)
    f, t, Sxx = spectrogram(data, rate, nperseg=256)
    plt.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
    plt.ylim([0, 4000])
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title("Spectrogram")
    plt.colorbar(label='Power [dB]')
    
    plt.tight_layout()
    
    # Save figure
    output_name = filename.replace('.wav', '_analysis.png')
    plt.savefig(output_name, dpi=150)
    plt.close()
    
    return rate, data, output_name

# Analyze key files
print("=== Analyzing WAV Files ===\n")

files_to_analyze = [
    ('test_pattern_2400_2600.wav', 'Test Pattern: 2400/2600 Hz'),
    ('all_call_tones_start.wav', 'All Call Tones (Start)'),
    ('all_call_tones_end.wav', 'All Call Tones (End)'),
    ('sf12_start_beep.wav', 'Superframe 12 - Start Beep'),
    ('sf12_end_beeps.wav', 'Superframe 12 - End Beeps'),
    ('example_original_tone.wav', 'Example: Original Tone'),
    ('example_encrypted.wav', 'Example: Encrypted'),
    ('example_decrypted.wav', 'Example: Decrypted')
]

for filename, title in files_to_analyze:
    try:
        rate, data, output = analyze_wav(filename, title)
        duration = len(data) / rate
        print(f"{filename}:")
        print(f"  Duration: {duration:.3f} seconds")
        print(f"  Sample rate: {rate} Hz")
        print(f"  Analysis saved to: {output}")
        print()
    except Exception as e:
        print(f"Error analyzing {filename}: {e}")
        print()

print("=== Audio File Summary ===")
print("\nKey observations:")
print("1. Start tones: Single beep at transmission start")
print("2. End tones: Multiple beeps at transmission end")
print("3. Frequency: Check spectrograms for actual tone frequencies")
print("4. Pattern: Consistent patterns indicate Call Tones")
print("\nListen to the files to hear the actual tones!")
print("Use an audio player to play the WAV files directly.")