#!/usr/bin/env python3
"""Understanding how AMBE+2 vocoder generates null frames"""

print("=== How AMBE+2 Vocoder Generates Null Frames ===\n")

print("1. AMBE+2 Vocoder Background:")
print("   - Advanced Multi-Band Excitation vocoder")
print("   - Used in DMR at 3600 bps (2450 bps voice + FEC)")
print("   - Generates frames every 20ms")
print("   - Can produce different frame types\n")

print("2. Why Vocoder Creates Null Frames:")
print("   a) Silence Suppression:")
print("      - When no voice detected (VAD - Voice Activity Detection)")
print("      - Saves bandwidth by not transmitting silence")
print("      - Replaced with null/comfort noise frames\n")
print("   b) Comfort Noise Generation:")
print("      - Prevents 'dead air' feeling")
print("      - Maintains channel presence")
print("      - Low-level background noise\n")
print("   c) Frame Padding:")
print("      - Fill timing gaps")
print("      - Maintain synchronization")
print("      - Replace corrupted frames\n")

print("3. AMBE+2 Frame Types:")
print("   - Voice frames: Normal speech encoding")
print("   - Silence frames: No speech detected")
print("   - Tone frames: DTMF or call tones")
print("   - Null frames: Padding/comfort noise\n")

print("4. Vocoder Null Frame Characteristics:")
print("   - Fixed patterns for efficiency")
print("   - Very low entropy (repeated bytes)")
print("   - Predictable spectral content")
print("   - Manufacturer-specific implementations\n")

print("5. Common Null Frame Scenarios in DMR:")
print("   - Start of transmission (before voice)")
print("   - End of transmission (after voice)")
print("   - During pauses in speech")
print("   - Lost frame replacement")
print("   - Channel idle maintenance\n")

# Simulate what vocoder null frames might look like
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile

def generate_vocoder_null_frame():
    """Simulate what a vocoder null frame produces"""
    
    # AMBE parameters for null frame
    # These would normally come from the vocoder
    pitch = 0  # Unvoiced
    gain = 0.05  # Very low
    spectral_params = [0] * 32  # Flat spectrum
    
    # Generate comfort noise
    samples = np.random.randn(160) * gain  # 20ms at 8kHz
    
    # Apply vocoder spectral shaping (simplified)
    # Real AMBE would use sophisticated spectral modeling
    envelope = np.ones_like(samples)
    envelope[:10] = np.linspace(0, 1, 10)
    envelope[-10:] = np.linspace(1, 0, 10)
    samples *= envelope
    
    return samples

# Create example null frame audio
print("6. Generating Example Vocoder Null Frames:\n")

# Generate multiple null frames
null_audio = []
for i in range(50):  # 1 second worth
    frame = generate_vocoder_null_frame()
    null_audio.extend(frame)

# Save as WAV
null_array = np.array(null_audio)
wavfile.write('vocoder_null_example.wav', 8000, (null_array * 32767).astype(np.int16))
print("Created: vocoder_null_example.wav")

# Create spectrogram
plt.figure(figsize=(12, 6))

plt.subplot(2, 1, 1)
time = np.arange(len(null_array)) / 8000
plt.plot(time, null_array)
plt.title("Vocoder Null Frame Output (Comfort Noise)")
plt.xlabel("Time (s)")
plt.ylabel("Amplitude")
plt.grid(True)

plt.subplot(2, 1, 2)
from scipy.signal import spectrogram
f, t, Sxx = spectrogram(null_array, 8000, nperseg=256)
plt.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
plt.ylim([0, 4000])
plt.ylabel('Frequency [Hz]')
plt.xlabel('Time [sec]')
plt.title("Spectrogram (White Noise Characteristics)")
plt.colorbar(label='Power [dB]')

plt.tight_layout()
plt.savefig('vocoder_null_characteristics.png', dpi=150)
plt.close()

print("Created: vocoder_null_characteristics.png")

# Explain the bit patterns
print("\n7. AMBE+2 Null Frame Bit Patterns:")
print("   - 49 bits total in DMR")
print("   - Pitch: 0 (unvoiced)")
print("   - Gain: Minimal")
print("   - Spectral: Flat/white noise")
print("   - FEC: Standard error correction")
print("\n   Typical patterns might be:")
print("   - All parameters set to minimum")
print("   - Repeated byte values")
print("   - Manufacturer-specific encoding")

# Check what happens in practice
print("\n8. In Practice:")
print("   - Motorola might use one pattern")
print("   - Hytera might use another")
print("   - Pattern depends on vocoder chip/firmware")
print("   - May vary with radio settings")

print("\n9. For DMR Encryption Attack:")
print("   - Null frames = known plaintext")
print("   - Occur at predictable times")
print("   - Same null pattern encrypted differently per MI")
print("   - Helps recover keystream")

print("\n=== Summary ===")
print("The vocoder generates null frames for valid reasons:")
print("1. Silence suppression (save bandwidth)")
print("2. Comfort noise (avoid dead air)")
print("3. Frame padding (maintain timing)")
print("4. Error recovery (replace bad frames)")
print("\nThese null frames become another form of known")
print("plaintext for cryptanalysis, just like Call Tones!")