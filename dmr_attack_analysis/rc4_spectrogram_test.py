#!/usr/bin/env python3
"""
End-to-end RC4 test with spectrograms showing exact preservation
of 2400/2600 Hz alternating beep pattern
"""

import numpy as np
import wave
import matplotlib.pyplot as plt
from scipy import signal
from Crypto.Cipher import ARC4

def create_test_pattern():
    """Create clean 2400/2600 Hz alternating pattern"""
    sample_rate = 8000
    duration = 0.5  # seconds per beep
    
    # Create time arrays
    t1 = np.linspace(0, duration, int(sample_rate * duration), False)
    t2 = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Generate beeps
    beep_2400 = np.sin(2 * np.pi * 2400 * t1)
    beep_2600 = np.sin(2 * np.pi * 2600 * t2)
    
    # Create alternating pattern (5 pairs)
    pattern = []
    for i in range(5):
        pattern.extend(beep_2400)
        pattern.extend(beep_2600)
    
    return np.array(pattern), sample_rate

def rc4_process(data, key):
    """RC4 encrypt/decrypt"""
    cipher = ARC4.new(key)
    return cipher.encrypt(data)

def create_spectrograms(original, encrypted, decrypted, sample_rate):
    """Create spectrograms for comparison"""
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    # Spectrogram parameters
    nperseg = 256
    noverlap = 128
    
    # Original spectrogram
    f, t, Sxx = signal.spectrogram(original, sample_rate, nperseg=nperseg, noverlap=noverlap)
    im1 = axes[0].pcolormesh(t, f, 10 * np.log10(Sxx), shading='gouraud', cmap='viridis')
    axes[0].set_ylabel('Frequency [Hz]')
    axes[0].set_title('Original: 2400/2600 Hz Alternating Pattern')
    axes[0].set_ylim(0, 4000)
    
    # Encrypted spectrogram
    f, t, Sxx = signal.spectrogram(encrypted, sample_rate, nperseg=nperseg, noverlap=noverlap)
    im2 = axes[1].pcolormesh(t, f, 10 * np.log10(Sxx), shading='gouraud', cmap='viridis')
    axes[1].set_ylabel('Frequency [Hz]')
    axes[1].set_title('RC4 Encrypted (appears as noise)')
    axes[1].set_ylim(0, 4000)
    
    # Decrypted spectrogram
    f, t, Sxx = signal.spectrogram(decrypted, sample_rate, nperseg=nperseg, noverlap=noverlap)
    im3 = axes[2].pcolormesh(t, f, 10 * np.log10(Sxx), shading='gouraud', cmap='viridis')
    axes[2].set_ylabel('Frequency [Hz]')
    axes[2].set_xlabel('Time [sec]')
    axes[2].set_title('RC4 Decrypted: Perfect Recovery of 2400/2600 Hz Pattern')
    axes[2].set_ylim(0, 4000)
    
    plt.tight_layout()
    
    # Add colorbars
    for ax, im in zip(axes, [im1, im2, im3]):
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Power [dB]')
    
    plt.savefig('rc4_spectrogram_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    # Create detailed frequency plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Compute FFT for a clean segment
    segment_size = 2048
    original_fft = np.fft.fft(original[:segment_size])
    decrypted_fft = np.fft.fft(decrypted[:segment_size])
    freqs = np.fft.fftfreq(segment_size, 1/sample_rate)
    
    # Plot positive frequencies only
    pos_mask = freqs > 0
    
    ax.plot(freqs[pos_mask], np.abs(original_fft[pos_mask]), 
            label='Original', linewidth=2, alpha=0.7)
    ax.plot(freqs[pos_mask], np.abs(decrypted_fft[pos_mask]), 
            label='Decrypted', linewidth=1, linestyle='--')
    
    ax.set_xlim(2000, 3000)
    ax.set_xlabel('Frequency [Hz]')
    ax.set_ylabel('Magnitude')
    ax.set_title('Frequency Spectrum: Perfect Recovery at 2400 & 2600 Hz')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Mark the expected frequencies
    ax.axvline(2400, color='red', linestyle=':', label='2400 Hz')
    ax.axvline(2600, color='red', linestyle=':', label='2600 Hz')
    
    plt.savefig('rc4_frequency_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()

def main():
    print("End-to-End RC4 Spectrogram Test")
    print("==============================")
    
    # Create test pattern
    original_signal, sample_rate = create_test_pattern()
    
    # Convert to 16-bit audio format
    original_int16 = (original_signal * 32767).astype(np.int16)
    original_bytes = original_int16.tobytes()
    
    # Use a 40-bit key (5 bytes) as in DMR Basic Privacy
    key = b'\xAB\xCD\xEF\x12\x34'
    
    # Encrypt
    encrypted_bytes = rc4_process(original_bytes, key)
    encrypted_int16 = np.frombuffer(encrypted_bytes, dtype=np.int16)
    encrypted_signal = encrypted_int16.astype(np.float32) / 32767
    
    # Decrypt (same operation with same key)
    decrypted_bytes = rc4_process(encrypted_bytes, key)
    decrypted_int16 = np.frombuffer(decrypted_bytes, dtype=np.int16)
    decrypted_signal = decrypted_int16.astype(np.float32) / 32767
    
    # Verify perfect reconstruction
    reconstruction_error = np.sum(np.abs(original_signal - decrypted_signal))
    print(f"Reconstruction error: {reconstruction_error}")
    print(f"Perfect match: {reconstruction_error < 1e-6}")
    
    # Create spectrograms
    create_spectrograms(original_signal, encrypted_signal, decrypted_signal, sample_rate)
    
    # Save audio files for verification
    for name, signal in [('original', original_int16), 
                        ('encrypted', encrypted_int16), 
                        ('decrypted', decrypted_int16)]:
        with wave.open(f'rc4_test_{name}.wav', 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(signal.tobytes())
    
    print("\nFiles created:")
    print("  rc4_spectrogram_comparison.png - Shows all three spectrograms")
    print("  rc4_frequency_comparison.png - Shows frequency match")
    print("  rc4_test_original.wav - Original audio")
    print("  rc4_test_encrypted.wav - Encrypted (sounds like noise)")
    print("  rc4_test_decrypted.wav - Decrypted (identical to original)")

if __name__ == "__main__":
    main()