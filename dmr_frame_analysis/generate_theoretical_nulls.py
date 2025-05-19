#!/usr/bin/env python3
"""
Generate theoretical null frames based on AMBE+2 specification
"""
import numpy as np
import wave
import struct

def create_theoretical_null_frames():
    """Create theoretical null frames based on vocoder behavior"""
    
    print("Theoretical AMBE+2 Null Frames in DMR:")
    print("=====================================")
    
    # Based on AMBE+2 specification and DMR implementation
    # Null frames are typically generated for:
    # 1. Silence suppression
    # 2. Comfort noise generation
    # 3. Frame padding
    
    # Common null patterns observed in other AMBE implementations
    theoretical_nulls = {
        # Type 1: All zeros (complete silence)
        "all_zeros": "00" * 9,
        
        # Type 2: Minimal energy pattern (comfort noise seed)
        "comfort_noise": "01" * 9,
        
        # Type 3: AMBE silence pattern (based on vocoder docs)
        "ambe_silence": "0013131300000000",
        
        # Type 4: DMR padding pattern (observed in some systems)
        "dmr_padding": "ac" * 9,
        
        # Type 5: FEC null pattern (error correction friendly)
        "fec_null": "55" * 9,
    }
    
    for name, pattern in theoretical_nulls.items():
        print(f"\n{name}: {pattern}")
        
        # Analyze pattern
        bytes_data = bytes.fromhex(pattern)
        unique_bytes = len(set(bytes_data))
        bit_count = sum(bin(b).count('1') for b in bytes_data)
        
        print(f"  Unique bytes: {unique_bytes}")
        print(f"  Set bits: {bit_count}/72 ({bit_count/72*100:.1f}%)")
        
        # Show binary representation of first few bytes
        bin_repr = ' '.join(format(b, '08b') for b in bytes_data[:3])
        print(f"  Binary (first 3): {bin_repr}")
    
    # Generate audio for null frames
    print("\nGenerating audio representations...")
    
    sample_rate = 8000
    duration = 0.5  # seconds
    
    for name, pattern in theoretical_nulls.items():
        # Create synthetic audio based on null pattern
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        if name == "all_zeros":
            # Complete silence
            signal = np.zeros_like(t)
        
        elif name == "comfort_noise":
            # Low-level white noise
            signal = np.random.normal(0, 0.01, len(t))
        
        elif name == "ambe_silence":
            # Very quiet tone at 300 Hz
            signal = 0.05 * np.sin(2 * np.pi * 300 * t)
        
        elif name == "dmr_padding":
            # Alternating pattern creates buzzing
            signal = 0.1 * np.sign(np.sin(2 * np.pi * 1000 * t))
        
        elif name == "fec_null":
            # Mid-range noise
            signal = 0.05 * np.sin(2 * np.pi * 500 * t) + 0.02 * np.random.normal(0, 1, len(t))
        
        # Save as WAV
        filename = f"null_frame_{name}.wav"
        signal_int16 = np.int16(signal * 32767)
        
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(signal_int16.tobytes())
        
        print(f"  Saved: {filename}")
    
    # Show how null frames would appear in AMBE decoding
    print("\nHow null frames appear when decoded:")
    print("1. All zeros -> Complete silence")
    print("2. Comfort noise -> Soft background hiss")
    print("3. AMBE silence -> Very quiet tone")
    print("4. DMR padding -> Buzzing/clicking")
    print("5. FEC null -> Low-level static")

if __name__ == "__main__":
    create_theoretical_null_frames()