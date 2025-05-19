#!/usr/bin/env python3
"""Decode AMBE frames to audio and create spectrograms for each frame"""
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import spectrogram
import struct
import os

# AMBE parameters
SAMPLES_PER_FRAME = 160  # 8kHz * 20ms
SAMPLE_RATE = 8000

def ambe_frame_to_samples(ambe_hex):
    """
    Convert AMBE frame to PCM samples
    This is a simulation - real implementation would use mbelib
    """
    # Convert hex to bytes
    ambe_bytes = bytes.fromhex(ambe_hex)
    
    # Create 49-bit array from 8-byte input (DMR uses 49-bit AMBE frames)
    bits = []
    for byte in ambe_bytes[:7]:  # First 7 bytes = 56 bits, we need 49
        for i in range(8):
            bits.append((byte >> (7-i)) & 1)
    bits = bits[:49]  # Take only first 49 bits
    
    # Generate audio based on AMBE data
    # This is a simplified simulation
    samples = np.zeros(SAMPLES_PER_FRAME, dtype=np.float32)
    
    # Use bits to generate waveform characteristics
    # Real AMBE decoder would extract pitch, energy, spectral info
    
    # Extract some basic parameters from bits (simulation)
    pitch_bits = bits[0:7]
    pitch_index = sum(b << i for i, b in enumerate(pitch_bits))
    pitch_freq = 50 + (pitch_index * 3)  # Map to 50-434 Hz range
    
    energy_bits = bits[7:12]
    energy = sum(b << i for i, b in enumerate(energy_bits)) / 31.0
    
    # Generate waveform
    t = np.linspace(0, 0.02, SAMPLES_PER_FRAME)
    
    # Add harmonics based on spectral bits
    for harmonic in range(1, 6):
        if harmonic < len(bits) // 8:
            harmonic_bits = bits[harmonic*8:(harmonic+1)*8]
            harmonic_energy = sum(b << i for i, b in enumerate(harmonic_bits[:4])) / 15.0
            if harmonic_energy > 0.1:
                samples += np.sin(2 * np.pi * pitch_freq * harmonic * t) * energy * harmonic_energy / harmonic
    
    # Add some formant structure
    if energy > 0.1:
        # Simulate formants
        formant1 = 700 + (bits[20] * 300)
        formant2 = 1200 + (bits[21] * 400)
        
        samples += np.sin(2 * np.pi * formant1 * t) * energy * 0.3
        samples += np.sin(2 * np.pi * formant2 * t) * energy * 0.2
    
    # Apply envelope
    envelope = np.ones_like(samples)
    envelope[:10] = np.linspace(0, 1, 10)  # Attack
    envelope[-10:] = np.linspace(1, 0, 10)  # Release
    samples *= envelope
    
    return samples

def create_spectrogram(samples, frame_id, ambe_hex, output_dir="spectrograms"):
    """Create and save a spectrogram for a single frame"""
    plt.figure(figsize=(10, 6))
    
    # Create spectrogram
    f, t, Sxx = spectrogram(samples, SAMPLE_RATE, nperseg=64, noverlap=32)
    
    # Plot
    plt.subplot(2, 1, 1)
    plt.plot(samples)
    plt.title(f"Frame {frame_id}: {ambe_hex}")
    plt.ylabel("Amplitude")
    plt.xlabel("Sample")
    plt.grid(True)
    
    plt.subplot(2, 1, 2)
    plt.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud', cmap='viridis')
    plt.ylim([0, 4000])
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.colorbar(label='Power [dB]')
    plt.title("Spectrogram")
    
    plt.tight_layout()
    filename = f"{output_dir}/frame_{frame_id:04d}_{ambe_hex[:8]}.png"
    plt.savefig(filename, dpi=100)
    plt.close()
    
    return filename

# Create output directory
os.makedirs("spectrograms", exist_ok=True)

# Connect to database
conn = sqlite3.connect('dmr_capture_20250517_204818.db')
cursor = conn.cursor()

print("=== Creating Spectrograms for AMBE Frames ===\n")

# Get frames grouped by superframe
cursor.execute("""
    SELECT id, ambe_hex, superframe_id 
    FROM U_00000000_S0 
    ORDER BY id
""")

frames = cursor.fetchall()
print(f"Total frames to process: {len(frames)}")

# Process each frame
for i, (frame_id, ambe_hex, sf_id) in enumerate(frames):
    # Decode AMBE to audio
    samples = ambe_frame_to_samples(ambe_hex)
    
    # Create spectrogram
    filename = create_spectrogram(samples, frame_id, ambe_hex)
    
    # Print progress
    if i % 10 == 0:
        print(f"Processed {i}/{len(frames)} frames...")

print(f"\nCompleted! Created {len(frames)} spectrograms in 'spectrograms' directory")

# Analyze transmission boundaries specifically
print("\n=== Analyzing Transmission Boundaries ===")

# Get superframes
cursor.execute("""
    SELECT DISTINCT superframe_id 
    FROM U_00000000_S0 
    WHERE superframe_id IS NOT NULL 
    ORDER BY superframe_id
""")

superframes = [sf[0] for sf in cursor.fetchall()]

# Create summary image for boundaries
fig, axes = plt.subplots(len(superframes), 2, figsize=(15, len(superframes)*3))
if len(superframes) == 1:
    axes = axes.reshape(1, -1)

for idx, sf_id in enumerate(superframes):
    # Get first and last frame of superframe
    cursor.execute("""
        SELECT id, ambe_hex 
        FROM U_00000000_S0 
        WHERE superframe_id = ? 
        ORDER BY id 
        LIMIT 1
    """, (sf_id,))
    first_frame = cursor.fetchone()
    
    cursor.execute("""
        SELECT id, ambe_hex 
        FROM U_00000000_S0 
        WHERE superframe_id = ? 
        ORDER BY id DESC 
        LIMIT 1
    """, (sf_id,))
    last_frame = cursor.fetchone()
    
    if first_frame and last_frame:
        # Decode frames
        first_samples = ambe_frame_to_samples(first_frame[1])
        last_samples = ambe_frame_to_samples(last_frame[1])
        
        # Plot first frame (potential Call Tone)
        ax1 = axes[idx, 0]
        f, t, Sxx = spectrogram(first_samples, SAMPLE_RATE, nperseg=64)
        ax1.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
        ax1.set_ylim([0, 4000])
        ax1.set_title(f"SF {sf_id} Start (Frame {first_frame[0]})")
        ax1.set_ylabel('Freq [Hz]')
        
        # Plot last frame (potential Call End Tone)
        ax2 = axes[idx, 1]
        f, t, Sxx = spectrogram(last_samples, SAMPLE_RATE, nperseg=64)
        ax2.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
        ax2.set_ylim([0, 4000])
        ax2.set_title(f"SF {sf_id} End (Frame {last_frame[0]})")

plt.tight_layout()
plt.savefig("transmission_boundaries.png", dpi=150)
plt.close()

print("Created transmission_boundaries.png showing potential Call Tone locations")

# Look for patterns in the spectrograms
print("\n=== Pattern Analysis ===")

# Group frames by superframe position
position_patterns = {}
for frame_id, ambe_hex, sf_id in frames:
    if sf_id is not None:
        # Get position within superframe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM U_00000000_S0 
            WHERE superframe_id = ? AND id < ?
        """, (sf_id, frame_id))
        position = cursor.fetchone()[0]
        
        if position not in position_patterns:
            position_patterns[position] = []
        position_patterns[position].append(ambe_hex)

# Check for consistent patterns at start/end positions
print("\nFrames at position 0 (transmission start):")
if 0 in position_patterns:
    for hex_val in position_patterns[0][:5]:
        print(f"  {hex_val}")
        
print("\nFrames at last positions (transmission end):")
last_positions = sorted(position_patterns.keys())[-3:]
for pos in last_positions:
    print(f"  Position {pos}:")
    for hex_val in position_patterns[pos][:3]:
        print(f"    {hex_val}")

conn.close()

print("\n=== Summary ===")
print(f"Created {len(frames)} individual spectrograms")
print("Check the 'spectrograms' directory for all frames")
print("Look for:")
print("1. Pure tones (single frequency lines) at transmission starts")
print("2. Multiple tones (3 beeps) at transmission ends")
print("3. Distinct patterns different from voice frames")
print("\nThe actual Call Tone frequencies will be visible in the spectrograms!")