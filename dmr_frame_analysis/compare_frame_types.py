#!/usr/bin/env python3
"""Compare different AMBE frame types: null, tone, voice"""
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile

def create_frame_comparison():
    """Visual comparison of different frame types"""
    
    # Define frame types
    frame_types = {
        'Null Frame (0x00)': '0000000000000000',
        'Null Frame (0x13)': '131313131313131313',
        'Null Frame (0xAC)': 'ACACACACACACACAC',
        'Call Tone (example)': '17884F2000FFF400',  # From captured data
        'Voice Frame 1': '3DA4DE6000804000',       # From captured data
        'Voice Frame 2': 'CF283220008F4800',       # From captured data
    }
    
    # Create visualization
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()
    
    for idx, (name, hex_pattern) in enumerate(frame_types.items()):
        ax = axes[idx]
        
        # Convert hex to bytes
        bytes_data = bytes.fromhex(hex_pattern)
        
        # Create byte visualization
        byte_values = [b for b in bytes_data]
        positions = list(range(len(byte_values)))
        
        # Bar plot of byte values
        bars = ax.bar(positions, byte_values, color='steelblue', edgecolor='navy')
        
        # Color code by value
        for bar, val in zip(bars, byte_values):
            if val == 0:
                bar.set_color('lightgray')
            elif val == 0x13:
                bar.set_color('lightgreen')
            elif val == 0xAC:
                bar.set_color('lightcoral')
            else:
                bar.set_color('steelblue')
        
        ax.set_title(f"{name}\n{hex_pattern}")
        ax.set_xlabel("Byte Position")
        ax.set_ylabel("Byte Value")
        ax.set_ylim([0, 256])
        ax.grid(True, alpha=0.3)
        
        # Add entropy info
        unique_bytes = len(set(byte_values))
        entropy = -sum([(byte_values.count(v)/len(byte_values)) * 
                       np.log2(byte_values.count(v)/len(byte_values)) 
                       for v in set(byte_values)])
        
        ax.text(0.02, 0.95, f"Unique: {unique_bytes}\nEntropy: {entropy:.2f}", 
                transform=ax.transAxes, 
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                verticalalignment='top')
    
    plt.tight_layout()
    plt.savefig('frame_type_comparison.png', dpi=150)
    plt.close()
    
    # Create hex pattern comparison
    fig, ax = plt.subplots(figsize=(12, 8))
    
    patterns = []
    labels = []
    
    for name, hex_pattern in frame_types.items():
        # Convert to binary representation
        binary = bin(int(hex_pattern, 16))[2:].zfill(72)  # 72 bits for 9 bytes
        binary_array = [int(b) for b in binary]
        patterns.append(binary_array)
        labels.append(name)
    
    # Create heatmap
    patterns_array = np.array(patterns)
    im = ax.imshow(patterns_array, aspect='auto', cmap='RdBu_r', 
                   interpolation='nearest')
    
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel('Bit Position')
    ax.set_title('AMBE Frame Binary Pattern Comparison')
    
    # Add colorbar
    plt.colorbar(im, ax=ax, label='Bit Value')
    
    plt.tight_layout()
    plt.savefig('frame_binary_comparison.png', dpi=150)
    plt.close()
    
    print("Created: frame_type_comparison.png")
    print("Created: frame_binary_comparison.png")

def create_null_frame_reference():
    """Create reference showing all known null patterns"""
    
    null_patterns = {
        'All Zeros (0x00)': '0000000000000000',
        'Motorola Null (0x13)': '131313131313131313',
        'Hytera Null (0xE1)': 'E1E1E1E1E1E1E1E1',
        'DMR Null (0xAC)': 'ACACACACACACACAC',
        'Alt Null (0xC9)': 'C9C9C9C9C9C9C9C9',
        'Silence Frame': 'FFFFFFFFFFFFFFFF',
    }
    
    # Create combined audio
    combined_audio = []
    sample_rate = 8000
    samples_per_frame = 160
    
    for name, pattern in null_patterns.items():
        # Generate comfort noise for null frame
        samples = np.random.randn(samples_per_frame) * 0.005  # Very quiet
        
        # Apply envelope
        envelope = np.ones_like(samples)
        envelope[:20] = np.linspace(0, 1, 20)
        envelope[-20:] = np.linspace(1, 0, 20)
        samples *= envelope
        
        # Repeat for 300ms
        for _ in range(15):  # 15 frames = 300ms
            combined_audio.extend(samples)
        
        # Add gap
        combined_audio.extend(np.zeros(int(sample_rate * 0.2)))
    
    # Save reference audio
    audio_array = np.array(combined_audio)
    wavfile.write('null_frame_reference.wav', 
                 sample_rate, (audio_array * 32767).astype(np.int16))
    
    print("Created: null_frame_reference.wav")
    
    # Create visual reference
    fig, ax = plt.subplots(figsize=(10, 6))
    
    y_pos = np.arange(len(null_patterns))
    patterns_hex = [pattern for pattern in null_patterns.values()]
    
    # Create table
    table_data = []
    for name, pattern in null_patterns.items():
        bytes_vals = bytes.fromhex(pattern)
        unique = len(set(bytes_vals))
        table_data.append([name, pattern[:8] + "...", f"{unique} unique"])
    
    table = ax.table(cellText=table_data, 
                    colLabels=['Pattern Name', 'Hex (first 8)', 'Unique Bytes'],
                    cellLoc='left',
                    loc='center')
    
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.2, 1.5)
    
    ax.axis('off')
    ax.set_title('DMR Null Vocoder Frame Reference', 
                fontsize=16, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig('null_frame_reference.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    print("Created: null_frame_reference.png")

# Create all comparisons
print("=== Creating Frame Type Comparisons ===\n")
create_frame_comparison()
create_null_frame_reference()

print("\n=== Summary ===")
print("Frame Type Characteristics:")
print("\n1. Null Frames:")
print("   - Low entropy (1-2 unique bytes)")
print("   - Common patterns: 0x00, 0x13, 0xAC, 0xE1, 0xC9")
print("   - Produce silence or comfort noise")
print("   - Used for silence suppression")
print("\n2. Tone Frames (Call Tones):")
print("   - Medium entropy")
print("   - Specific frequency patterns")
print("   - Clear spectral lines")
print("\n3. Voice Frames:")
print("   - High entropy (many unique bytes)")
print("   - Complex spectral content")
print("   - Variable patterns")
print("\nFiles created:")
print("- frame_type_comparison.png - Visual comparison")
print("- frame_binary_comparison.png - Binary patterns")
print("- null_frame_reference.png/wav - Null frame guide")