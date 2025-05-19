#!/usr/bin/env python3
"""
Create AMBE test patterns for 2400/2600 Hz tones
Based on understanding of AMBE+2 frame structure
"""

import numpy as np
import struct
import wave

def generate_reference_audio():
    """Generate 2400/2600 Hz reference pattern"""
    sample_rate = 8000
    duration = 3.0  # 3 seconds per tone
    
    # Create pattern
    patterns = []
    frequencies = [2400, 2600, 2400, 2600, 2400, 2600]
    
    for freq in frequencies:
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = np.sin(2 * np.pi * freq * t) * 0.8
        patterns.extend(tone)
    
    # Save as WAV
    audio_array = np.array(patterns)
    pcm_data = (audio_array * 32767).astype(np.int16)
    
    with wave.open("reference_tones_2400_2600.wav", "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_data.tobytes())
    
    print(f"Created reference_tones_2400_2600.wav ({len(pcm_data)} samples)")
    return audio_array

def create_ambe_tone_patterns():
    """Create AMBE patterns that should decode to tones"""
    
    # AMBE+2 frame structure (49 bits):
    # - Bits 0-7: Pitch/fundamental frequency
    # - Bits 8-23: Spectral magnitudes  
    # - Bits 24-48: Other vocoder parameters
    
    # Estimate AMBE parameters for pure tones
    # 2400 Hz tone parameters
    tone_2400 = {
        'pitch': 30,  # Pitch period for 2400 Hz
        'voiced': True,
        'energy': 200,
        'spectral': [255, 0, 0, 0]  # Energy at 2400 Hz
    }
    
    # 2600 Hz tone parameters  
    tone_2600 = {
        'pitch': 28,  # Pitch period for 2600 Hz
        'voiced': True,
        'energy': 200,
        'spectral': [255, 0, 0, 0]  # Energy at 2600 Hz
    }
    
    # Silence parameters
    silence = {
        'pitch': 0,
        'voiced': False,
        'energy': 0,
        'spectral': [0, 0, 0, 0]
    }
    
    def encode_ambe_params(params):
        """Encode parameters into 49-bit AMBE frame"""
        ambe_bits = 0
        
        # Simplified encoding (actual AMBE+2 is more complex)
        # Bits 0-7: Pitch
        ambe_bits |= (params['pitch'] & 0xFF)
        
        # Bit 8: Voicing
        if params['voiced']:
            ambe_bits |= (1 << 8)
        
        # Bits 9-16: Energy
        ambe_bits |= ((params['energy'] & 0xFF) << 9)
        
        # Bits 17-48: Spectral information
        for i, mag in enumerate(params['spectral']):
            ambe_bits |= ((mag & 0xFF) << (17 + i*8))
        
        return ambe_bits
    
    # Create test pattern
    pattern_sequence = [
        (silence, 50),      # 1 second silence
        (tone_2400, 150),   # 3 seconds 2400 Hz
        (tone_2600, 150),   # 3 seconds 2600 Hz
        (tone_2400, 150),   # 3 seconds 2400 Hz
        (tone_2600, 150),   # 3 seconds 2600 Hz
        (silence, 50)       # 1 second silence
    ]
    
    with open("tone_pattern_ambe.bin", "wb") as f:
        frame_count = 0
        
        for params, num_frames in pattern_sequence:
            ambe_bits = encode_ambe_params(params)
            
            for _ in range(num_frames):
                # Pack as 8-byte frame
                frame_64bit = (ambe_bits << 15) & 0xFFFFFFFFFFFFFFFF
                f.write(struct.pack('>Q', frame_64bit))
                frame_count += 1
        
        print(f"Created tone_pattern_ambe.bin with {frame_count} frames")
    
    # Also create a pattern based on actual cleartext analysis
    create_pattern_from_cleartext()

def create_pattern_from_cleartext():
    """Analyze cleartext frames and create tone pattern"""
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Analyze frames for patterns
    frame_groups = {
        'low_energy': [],
        'mid_energy': [],
        'high_energy': []
    }
    
    for i in range(0, min(1000, len(data)), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            ambe_49bit = frame_64bit >> 15
            
            # Simple energy estimation based on bit count
            bit_count = bin(ambe_49bit).count('1')
            
            if bit_count < 15:
                frame_groups['low_energy'].append(frame)
            elif bit_count < 25:
                frame_groups['mid_energy'].append(frame)
            else:
                frame_groups['high_energy'].append(frame)
    
    # Create alternating pattern
    with open("cleartext_tone_pattern.bin", "wb") as f:
        # Pattern: low, high, low, high, low
        for _ in range(100):  # 2 seconds
            f.write(frame_groups['low_energy'][0])
        
        for _ in range(150):  # 3 seconds
            f.write(frame_groups['high_energy'][0])
        
        for _ in range(150):  # 3 seconds
            f.write(frame_groups['low_energy'][0])
        
        for _ in range(150):  # 3 seconds
            f.write(frame_groups['high_energy'][0])
        
        for _ in range(100):  # 2 seconds
            f.write(frame_groups['low_energy'][0])
    
    print("Created cleartext_tone_pattern.bin from actual frames")

def main():
    print("=== AMBE Tone Pattern Generator ===\n")
    
    # Generate reference audio
    reference_audio = generate_reference_audio()
    
    # Create AMBE patterns
    create_ambe_tone_patterns()
    
    print("\n=== Generated Files ===")
    print("1. reference_tones_2400_2600.wav - Reference audio")
    print("2. tone_pattern_ambe.bin - Synthetic AMBE pattern")
    print("3. cleartext_tone_pattern.bin - Pattern from real frames")
    
    # Decode and compare
    print("\nDecoding patterns...")
    import subprocess
    
    # Decode synthetic pattern
    subprocess.run([
        "./test_mbelib_direct"
    ])
    
    print("\nCompare spectrograms to verify 2400/2600 Hz pattern")

if __name__ == "__main__":
    main()