#!/usr/bin/env python3
"""Generate test AMBE frames for 2400Hz/2600Hz tone pattern"""

import numpy as np
import struct
import subprocess
import wave

def generate_test_tones():
    """Generate 2400Hz/2600Hz alternating tones - 3 seconds each, 3 times"""
    sample_rate = 8000
    duration_per_tone = 3.0  # seconds
    frequencies = [2400, 2600]
    cycles = 3
    
    samples = []
    
    for cycle in range(cycles):
        for freq in frequencies:
            t = np.linspace(0, duration_per_tone, int(sample_rate * duration_per_tone))
            tone = np.sin(2 * np.pi * freq * t)
            samples.extend(tone * 0.8 * 32767)  # Scale to 16-bit
    
    # Convert to 16-bit PCM
    pcm_data = np.array(samples, dtype=np.int16)
    
    # Save as WAV
    with wave.open("test_tones.wav", "wb") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_data.tobytes())
    
    print(f"Generated test_tones.wav ({len(pcm_data)} samples)")
    return "test_tones.wav"

def encode_with_dsd_fme(wav_file):
    """Use dsd-fme to encode WAV to AMBE (would need actual encoder)"""
    # Note: dsd-fme is primarily a decoder, not encoder
    # For testing, we'll create synthetic AMBE frames
    
    # Read WAV file info
    with wave.open(wav_file, "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        duration = frames / rate
    
    # DMR uses 60ms frames (20ms per AMBE frame, 3 per superframe)
    ambe_frame_duration = 0.020  # 20ms
    num_ambe_frames = int(duration / ambe_frame_duration)
    
    print(f"Generating {num_ambe_frames} synthetic AMBE frames")
    
    # Create synthetic AMBE frames in the same 8-byte format as our cleartext
    synthetic_frames = []
    
    # Pattern: alternating high/low energy to represent different tones
    for i in range(num_ambe_frames):
        # Determine which tone period we're in
        time_pos = i * ambe_frame_duration
        tone_period = int(time_pos / 3.0) % 2  # 0 for 2400Hz, 1 for 2600Hz
        
        # Create synthetic AMBE data (64 bits total)
        # Higher bits for 2600Hz, lower for 2400Hz
        if tone_period == 0:  # 2400Hz
            # Lower energy pattern
            ambe_bits = 0x1A4C0F6000AF9000 + (i & 0xFF)
        else:  # 2600Hz  
            # Higher energy pattern
            ambe_bits = 0xD13E2120008CE800 + (i & 0xFF)
        
        # Add some variation to make frames unique
        ambe_bits ^= (i << 8)
        
        # Pack as 8 bytes (matching cleartext format)
        frame_bytes = struct.pack('>Q', ambe_bits)
        synthetic_frames.append(frame_bytes)
    
    # Write synthetic AMBE frames
    with open("test_ambe_8byte.bin", "wb") as f:
        for frame in synthetic_frames:
            f.write(frame)
    
    print(f"Created test_ambe_8byte.bin with {len(synthetic_frames)} frames")
    return "test_ambe_8byte.bin"

def convert_to_7byte(input_file):
    """Convert 8-byte AMBE to 7-byte format for decoder"""
    with open(input_file, "rb") as f:
        data = f.read()
    
    with open("test_ambe_7byte.bin", "wb") as out:
        frame_count = 0
        for i in range(0, len(data), 8):
            if i + 8 <= len(data):
                # Read 8-byte frame
                frame_8 = data[i:i+8]
                ambe_64bit = struct.unpack('>Q', frame_8)[0]
                
                # Convert to 7-byte format (first 49 bits)
                bytes_7 = []
                for j in range(6):
                    shift = 56 - (j * 8)
                    byte_val = (ambe_64bit >> shift) & 0xFF
                    bytes_7.append(byte_val)
                
                # Last byte contains bit 49 in MSB
                last_bit = (ambe_64bit >> 15) & 0x01  # Bit 49
                bytes_7.append(last_bit << 7)
                
                out.write(bytes(bytes_7))
                frame_count += 1
    
    print(f"Converted {frame_count} frames to 7-byte format")
    return "test_ambe_7byte.bin"

def main():
    print("Generating AMBE test frames for 2400Hz/2600Hz tone pattern...")
    
    # Step 1: Generate test tones
    wav_file = generate_test_tones()
    
    # Step 2: Create synthetic AMBE frames
    ambe_8byte_file = encode_with_dsd_fme(wav_file)
    
    # Step 3: Convert to 7-byte format
    ambe_7byte_file = convert_to_7byte(ambe_8byte_file)
    
    print("\nTest files created:")
    print(f"  - {wav_file}: Original test tones")
    print(f"  - {ambe_8byte_file}: AMBE in cleartext 8-byte format")
    print(f"  - {ambe_7byte_file}: AMBE in 7-byte decoder format")
    
    # Create a known good AMBE pattern based on real cleartext data
    # Using the first frame pattern from our cleartext capture
    print("\nCreating known_good_ambe.bin with real frame patterns...")
    
    known_pattern = [
        0x1A4C0F6000AF9000,  # Frame 1 from cleartext
        0xD13E2120008CE800,  # Frame 2 from cleartext  
        0x0B083400002DE800,  # Frame 3 from cleartext
        0x391C426000ED7800,  # Frame 4 from cleartext
    ]
    
    # Repeat pattern to fill duration
    with open("known_good_ambe_8byte.bin", "wb") as f:
        for i in range(900):  # ~18 seconds worth
            pattern_frame = known_pattern[i % len(known_pattern)]
            f.write(struct.pack('>Q', pattern_frame))
    
    # Convert known good to 7-byte
    convert_to_7byte_known("known_good_ambe_8byte.bin", "known_good_ambe_7byte.bin")
    
    print("\nTest frame generation complete!")
    print("Now decode with: ./decode_mbelib_correct test_ambe_7byte.bin test_decoded.wav")
    print("Or try known good: ./decode_mbelib_correct known_good_ambe_7byte.bin known_good_decoded.wav")

def convert_to_7byte_known(input_file, output_file):
    """Convert known good 8-byte AMBE to 7-byte format"""
    with open(input_file, "rb") as f:
        data = f.read()
    
    with open(output_file, "wb") as out:
        for i in range(0, len(data), 8):
            if i + 8 <= len(data):
                frame_8 = data[i:i+8]
                ambe_64bit = struct.unpack('>Q', frame_8)[0]
                
                # Convert to 7-byte - pack 49 bits
                bytes_7 = []
                
                # First 48 bits go into first 6 bytes  
                for j in range(6):
                    shift = 56 - (j * 8)
                    byte_val = (ambe_64bit >> shift) & 0xFF
                    bytes_7.append(byte_val)
                
                # 49th bit goes to MSB of 7th byte
                bit_49 = (ambe_64bit >> 15) & 0x01
                bytes_7.append(bit_49 << 7)
                
                out.write(bytes(bytes_7))

if __name__ == "__main__":
    main()