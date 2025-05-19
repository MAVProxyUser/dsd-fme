#!/usr/bin/env python3
"""Decode key AMBE frames at transmission boundaries"""
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import spectrogram
import os

# AMBE parameters
SAMPLES_PER_FRAME = 160  # 8kHz * 20ms
SAMPLE_RATE = 8000

def simple_ambe_decode(ambe_hex):
    """Simplified AMBE frame decoder for demonstration"""
    # Convert hex to bytes
    ambe_bytes = bytes.fromhex(ambe_hex)
    
    # Generate samples based on byte patterns
    samples = np.zeros(SAMPLES_PER_FRAME, dtype=np.float32)
    
    # Use byte values to create audio characteristics
    # This is highly simplified - real AMBE is much more complex
    
    # Extract some pseudo-parameters
    if len(ambe_bytes) >= 8:
        # Use first few bytes for frequency components
        freq1 = 200 + (ambe_bytes[0] * 10)
        freq2 = 400 + (ambe_bytes[1] * 10)
        freq3 = 800 + (ambe_bytes[2] * 8)
        
        # Use other bytes for amplitudes
        amp1 = ambe_bytes[3] / 255.0
        amp2 = ambe_bytes[4] / 255.0
        amp3 = ambe_bytes[5] / 255.0
        
        # Generate waveform
        t = np.linspace(0, 0.02, SAMPLES_PER_FRAME)
        
        if amp1 > 0.1:
            samples += np.sin(2 * np.pi * freq1 * t) * amp1
        if amp2 > 0.1:
            samples += np.sin(2 * np.pi * freq2 * t) * amp2 * 0.7
        if amp3 > 0.1:
            samples += np.sin(2 * np.pi * freq3 * t) * amp3 * 0.5
    
    return samples

# Create output directory
os.makedirs("key_frames", exist_ok=True)

# Connect to database
conn = sqlite3.connect('dmr_capture_20250517_204818.db')
cursor = conn.cursor()

print("=== Decoding Key AMBE Frames at Boundaries ===\n")

# Get superframes
cursor.execute("""
    SELECT DISTINCT superframe_id 
    FROM U_00000000_S0 
    WHERE superframe_id IS NOT NULL 
    ORDER BY superframe_id
""")

superframes = [sf[0] for sf in cursor.fetchall()]
print(f"Found {len(superframes)} superframes")

# Process start and end of each superframe
for sf_id in superframes:
    # Get first 3 and last 5 frames
    cursor.execute("""
        SELECT id, ambe_hex 
        FROM U_00000000_S0 
        WHERE superframe_id = ? 
        ORDER BY id 
        LIMIT 3
    """, (sf_id,))
    start_frames = cursor.fetchall()
    
    cursor.execute("""
        SELECT id, ambe_hex 
        FROM U_00000000_S0 
        WHERE superframe_id = ? 
        ORDER BY id DESC 
        LIMIT 5
    """, (sf_id,))
    end_frames = list(reversed(cursor.fetchall()))
    
    print(f"\nSuperframe {sf_id}:")
    
    # Create figure for this superframe
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    
    # Process start frames (Call Tone)
    start_samples = []
    print("  Start frames (Call Tone):")
    for frame_id, ambe_hex in start_frames:
        print(f"    Frame {frame_id}: {ambe_hex}")
        samples = simple_ambe_decode(ambe_hex)
        start_samples.extend(samples)
        
        # Create individual spectrogram
        plt.figure(figsize=(8, 4))
        f, t, Sxx = spectrogram(samples, SAMPLE_RATE, nperseg=32)
        plt.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
        plt.ylim([0, 4000])
        plt.title(f"SF {sf_id} - Frame {frame_id} (Start)")
        plt.ylabel('Frequency [Hz]')
        plt.xlabel('Time [sec]')
        plt.colorbar(label='Power [dB]')
        plt.tight_layout()
        plt.savefig(f"key_frames/sf{sf_id}_frame{frame_id}_start.png")
        plt.close()
    
    # Process end frames (Call End Tone)
    end_samples = []
    print("  End frames (Call End Tone):")
    for frame_id, ambe_hex in end_frames:
        print(f"    Frame {frame_id}: {ambe_hex}")
        samples = simple_ambe_decode(ambe_hex)
        end_samples.extend(samples)
        
        # Create individual spectrogram
        plt.figure(figsize=(8, 4))
        f, t, Sxx = spectrogram(samples, SAMPLE_RATE, nperseg=32)
        plt.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
        plt.ylim([0, 4000])
        plt.title(f"SF {sf_id} - Frame {frame_id} (End)")
        plt.ylabel('Frequency [Hz]')
        plt.xlabel('Time [sec]')
        plt.colorbar(label='Power [dB]')
        plt.tight_layout()
        plt.savefig(f"key_frames/sf{sf_id}_frame{frame_id}_end.png")
        plt.close()
    
    # Create combined spectrograms
    ax1 = axes[0]
    f, t, Sxx = spectrogram(np.array(start_samples), SAMPLE_RATE, nperseg=128)
    im1 = ax1.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
    ax1.set_ylim([0, 4000])
    ax1.set_title(f"Superframe {sf_id} - Start (First 3 frames)")
    ax1.set_ylabel('Frequency [Hz]')
    plt.colorbar(im1, ax=ax1, label='Power [dB]')
    
    ax2 = axes[1]
    f, t, Sxx = spectrogram(np.array(end_samples), SAMPLE_RATE, nperseg=128)
    im2 = ax2.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
    ax2.set_ylim([0, 4000])
    ax2.set_title(f"Superframe {sf_id} - End (Last 5 frames)")
    ax2.set_ylabel('Frequency [Hz]')
    ax2.set_xlabel('Time [sec]')
    plt.colorbar(im2, ax=ax2, label='Power [dB]')
    
    plt.tight_layout()
    plt.savefig(f"key_frames/sf{sf_id}_combined.png", dpi=150)
    plt.close()

# Create summary visualization
print("\n=== Creating Summary Visualization ===")

plt.figure(figsize=(15, 10))

# Get representative frames
cursor.execute("""
    SELECT id, ambe_hex, superframe_id,
           ROW_NUMBER() OVER (PARTITION BY superframe_id ORDER BY id) as position,
           COUNT(*) OVER (PARTITION BY superframe_id) as total
    FROM U_00000000_S0
    WHERE superframe_id IS NOT NULL
""")

all_data = cursor.fetchall()

# Find frames at position 1 (start) and last positions (end)
start_frames = [(id, hex, sf) for id, hex, sf, pos, total in all_data if pos == 1]
end_frames = [(id, hex, sf) for id, hex, sf, pos, total in all_data if pos >= total - 2]

# Plot a few examples
fig, axes = plt.subplots(2, 3, figsize=(15, 8))

# Plot first 3 start frames
for i, (frame_id, ambe_hex, sf_id) in enumerate(start_frames[:3]):
    ax = axes[0, i]
    samples = simple_ambe_decode(ambe_hex)
    f, t, Sxx = spectrogram(samples, SAMPLE_RATE, nperseg=32)
    ax.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
    ax.set_ylim([0, 4000])
    ax.set_title(f"Start - SF {sf_id}, Frame {frame_id}")
    ax.set_ylabel('Freq [Hz]' if i == 0 else '')
    
# Plot first 3 end frames
for i, (frame_id, ambe_hex, sf_id) in enumerate(end_frames[:3]):
    ax = axes[1, i]
    samples = simple_ambe_decode(ambe_hex)
    f, t, Sxx = spectrogram(samples, SAMPLE_RATE, nperseg=32)
    ax.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
    ax.set_ylim([0, 4000])
    ax.set_title(f"End - SF {sf_id}, Frame {frame_id}")
    ax.set_ylabel('Freq [Hz]' if i == 0 else '')
    ax.set_xlabel('Time [sec]')

plt.suptitle("Call Tone Analysis - Start vs End Patterns")
plt.tight_layout()
plt.savefig("call_tone_summary.png", dpi=150)
plt.close()

conn.close()

print("\n=== Analysis Complete ===")
print(f"Created spectrograms in 'key_frames' directory")
print("Files created:")
print("- Individual frame spectrograms")
print("- Combined start/end spectrograms for each superframe")
print("- call_tone_summary.png - overview of patterns")
print("\nLook for:")
print("1. Consistent frequency patterns at transmission starts")
print("2. Multiple tones (3 beeps) at transmission ends")
print("3. Clear differences between voice and tone patterns")