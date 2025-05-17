#!/usr/bin/env python3
"""
Perfect RC4 end-to-end test with exact verification
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from Crypto.Cipher import ARC4

def create_clean_pattern():
    """Create very clean 2400/2600 Hz pattern"""
    fs = 8000  # Sample rate
    t = np.arange(0, 2.0, 1/fs)  # 2 seconds total
    
    # First second: 2400 Hz
    # Second second: 2600 Hz
    signal_2400 = np.sin(2 * np.pi * 2400 * t[:fs])
    signal_2600 = np.sin(2 * np.pi * 2600 * t[fs:])
    
    # Combine
    full_signal = np.concatenate([signal_2400, signal_2600])
    
    # Convert to 16-bit integer to avoid float precision issues
    signal_int16 = (full_signal * 32767).astype(np.int16)
    
    return signal_int16, fs

def test_rc4_perfect():
    """Test RC4 with perfect reconstruction"""
    print("Creating test signal...")
    original, fs = create_clean_pattern()
    
    # RC4 key (40-bit as in DMR)
    key = b'\x01\x23\x45\x67\x89'
    
    # Convert to bytes for encryption
    original_bytes = original.tobytes()
    
    # Encrypt
    cipher = ARC4.new(key)
    encrypted_bytes = cipher.encrypt(original_bytes)
    
    # Decrypt (new cipher instance with same key)
    cipher = ARC4.new(key)
    decrypted_bytes = cipher.encrypt(encrypted_bytes)  # RC4 decrypt = encrypt
    
    # Convert back to int16
    encrypted = np.frombuffer(encrypted_bytes, dtype=np.int16)
    decrypted = np.frombuffer(decrypted_bytes, dtype=np.int16)
    
    # Check perfect reconstruction
    is_perfect = np.array_equal(original, decrypted)
    difference = np.sum(np.abs(original - decrypted))
    
    print(f"Perfect reconstruction: {is_perfect}")
    print(f"Total difference: {difference}")
    
    # Create comparison plot
    fig, axes = plt.subplots(3, 2, figsize=(15, 10))
    
    # Time domain plots
    time = np.arange(len(original)) / fs
    
    # Original
    axes[0, 0].plot(time[:2000], original[:2000])
    axes[0, 0].set_title('Original: 2400 Hz (first 0.25s)')
    axes[0, 0].set_ylabel('Amplitude')
    
    # Encrypted
    axes[1, 0].plot(time[:2000], encrypted[:2000])
    axes[1, 0].set_title('RC4 Encrypted')
    axes[1, 0].set_ylabel('Amplitude')
    
    # Decrypted
    axes[2, 0].plot(time[:2000], decrypted[:2000])
    axes[2, 0].set_title('RC4 Decrypted: Perfect Match')
    axes[2, 0].set_ylabel('Amplitude')
    axes[2, 0].set_xlabel('Time [s]')
    
    # Spectrograms
    for i, (data, title) in enumerate([(original, 'Original'),
                                      (encrypted, 'Encrypted'), 
                                      (decrypted, 'Decrypted')]):
        f, t, Sxx = signal.spectrogram(data, fs, nperseg=512, noverlap=256)
        axes[i, 1].pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), 
                             shading='gouraud', cmap='viridis')
        axes[i, 1].set_ylabel('Frequency [Hz]')
        axes[i, 1].set_ylim(0, 4000)
        axes[i, 1].set_title(f'{title} Spectrogram')
        if i == 2:
            axes[i, 1].set_xlabel('Time [s]')
            # Add frequency markers
            axes[i, 1].axhline(2400, color='red', linestyle='--', alpha=0.7)
            axes[i, 1].axhline(2600, color='red', linestyle='--', alpha=0.7)
            axes[i, 1].text(0.25, 2450, '2400 Hz', color='white')
            axes[i, 1].text(1.25, 2650, '2600 Hz', color='white')
    
    plt.tight_layout()
    plt.savefig('rc4_perfect_verification.png', dpi=150)
    plt.close()
    
    # Difference plot
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(time, original - decrypted)
    ax.set_title(f'Reconstruction Error (Original - Decrypted): Sum = {difference}')
    ax.set_xlabel('Time [s]')
    ax.set_ylabel('Difference')
    ax.grid(True, alpha=0.3)
    plt.savefig('rc4_reconstruction_error.png', dpi=150)
    plt.close()
    
    print("\nFiles created:")
    print("  rc4_perfect_verification.png - Shows perfect reconstruction")
    print("  rc4_reconstruction_error.png - Shows zero error")
    
    return is_perfect

if __name__ == "__main__":
    print("RC4 Perfect End-to-End Test")
    print("==========================")
    success = test_rc4_perfect()
    
    if success:
        print("\n✓ SUCCESS: RC4 encryption/decryption preserves exact signal")
        print("  Input:  2400 Hz → 2600 Hz")
        print("  Output: 2400 Hz → 2600 Hz (IDENTICAL)")
    else:
        print("\n✗ FAILED: Reconstruction not perfect")