#!/usr/bin/env python3
"""
Analyze frequency content of decoded AMBE files
"""

import numpy as np
import wave
from scipy import signal
import matplotlib.pyplot as plt

def analyze_wav_file(filename):
    """Analyze frequency content of WAV file"""
    try:
        with wave.open(filename, 'rb') as wav:
            params = wav.getparams()
            audio_data = wav.readframes(params.nframes)
            
        # Convert to numpy array
        samples = np.frombuffer(audio_data, dtype=np.int16)
        sample_rate = params.framerate
        
        # Compute FFT
        freqs, powers = signal.periodogram(samples, sample_rate)
        
        # Find peak frequencies
        peak_indices = signal.find_peaks(powers, height=np.max(powers)/10)[0]
        peak_freqs = freqs[peak_indices]
        peak_powers = powers[peak_indices]
        
        # Sort by power
        sorted_indices = np.argsort(peak_powers)[::-1]
        
        print(f"\n{filename}:")
        print(f"  Sample rate: {sample_rate} Hz")
        print(f"  Duration: {len(samples)/sample_rate:.2f} seconds")
        print(f"  Max amplitude: {np.max(np.abs(samples))/32768:.3f}")
        
        print("  Top frequencies:")
        for i in range(min(5, len(sorted_indices))):
            idx = sorted_indices[i]
            freq = peak_freqs[idx]
            power = 10 * np.log10(peak_powers[idx])
            print(f"    {freq:.1f} Hz: {power:.1f} dB")
        
        # Check for 2400/2600 Hz specifically
        for target_freq in [2400, 2600]:
            idx = np.argmin(np.abs(freqs - target_freq))
            power = 10 * np.log10(powers[idx]) if powers[idx] > 0 else -100
            print(f"  Power at {target_freq} Hz: {power:.1f} dB")
            
        return freqs, powers
        
    except Exception as e:
        print(f"Error analyzing {filename}: {e}")
        return None, None

def create_comparison_plot():
    """Create frequency comparison plot"""
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    files = [
        ("reference_tones.wav", "Reference 2400/2600 Hz"),
        ("cleartext_tone_test_decoded.wav", "Cleartext frames"),
        ("synthetic_tone_test_decoded.wav", "Synthetic AMBE")
    ]
    
    for i, (filename, title) in enumerate(files):
        freqs, powers = analyze_wav_file(filename)
        if freqs is not None:
            axes[i].semilogy(freqs, powers)
            axes[i].set_xlim(0, 4000)
            axes[i].set_title(title)
            axes[i].set_ylabel('Power')
            axes[i].grid(True)
            
            # Mark 2400/2600 Hz
            axes[i].axvline(2400, color='r', linestyle='--', alpha=0.5)
            axes[i].axvline(2600, color='r', linestyle='--', alpha=0.5)
    
    axes[-1].set_xlabel('Frequency (Hz)')
    plt.tight_layout()
    plt.savefig('frequency_comparison.png', dpi=150)
    print("\nSaved frequency comparison to frequency_comparison.png")

def main():
    print("=== Frequency Analysis of Decoded AMBE ===")
    
    # Analyze key files
    files_to_analyze = [
        "reference_tones.wav",
        "cleartext_tone_test_decoded.wav",
        "synthetic_tone_test_decoded.wav",
        "test_ambe_decoded.wav"
    ]
    
    for filename in files_to_analyze:
        analyze_wav_file(filename)
    
    # Create comparison plot
    create_comparison_plot()
    
    print("\n=== Analysis Complete ===")

if __name__ == "__main__":
    main()