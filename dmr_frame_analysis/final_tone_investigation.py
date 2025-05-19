#!/usr/bin/env python3
"""
Final investigation: Why aren't tones working in AMBE?
"""

import struct
import numpy as np
import wave

def create_pure_tone_test():
    """Create a pure tone test to understand AMBE behavior"""
    
    # First, create reference tones
    sample_rate = 8000
    duration = 1.0  # 1 second
    
    # Create pure tones at different frequencies
    frequencies = [440, 1000, 2400, 2600]  # Hz
    
    for freq in frequencies:
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = 0.8 * np.sin(2 * np.pi * freq * t)
        
        # Save as WAV
        filename = f"pure_tone_{freq}hz.wav"
        with wave.open(filename, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            pcm = (tone * 32767).astype(np.int16)
            wav.writeframes(pcm.tobytes())
        
        print(f"Created {filename}")

def analyze_cleartext_for_patterns():
    """Look for repeating patterns that might be tones"""
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # Look for repeating frames (tones would be repetitive)
    frame_counts = {}
    
    for i in range(0, len(data), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_hex = frame.hex()
            
            if frame_hex not in frame_counts:
                frame_counts[frame_hex] = 0
            frame_counts[frame_hex] += 1
    
    # Find most repeated frames
    repeated_frames = sorted(frame_counts.items(), key=lambda x: x[1], reverse=True)
    
    print("\nMost repeated frames (potential tones/silence):")
    for frame_hex, count in repeated_frames[:10]:
        if count > 5:  # Only show frames that repeat significantly
            print(f"  {frame_hex}: {count} occurrences")
            
            # Decode this frame
            frame_bytes = bytes.fromhex(frame_hex)
            frame_64bit = struct.unpack('>Q', frame_bytes)[0]
            ambe_49bit = frame_64bit >> 15
            
            # Analyze structure
            byte1 = ambe_49bit & 0xFF
            byte2 = (ambe_49bit >> 8) & 0xFF
            byte3 = (ambe_49bit >> 16) & 0xFF
            
            print(f"    AMBE: 0x{ambe_49bit:013X}")
            print(f"    Bytes: {byte1:02X} {byte2:02X} {byte3:02X}")
            
    return repeated_frames

def test_repeated_frames():
    """Test decoding of highly repeated frames"""
    
    repeated_frames = analyze_cleartext_for_patterns()
    
    # Create test files with most repeated frames
    for idx, (frame_hex, count) in enumerate(repeated_frames[:5]):
        if count > 10:
            frame_bytes = bytes.fromhex(frame_hex)
            
            filename = f"repeated_frame_{idx}.bin"
            with open(filename, "wb") as f:
                # Write 2 seconds worth
                for _ in range(100):
                    f.write(frame_bytes)
            
            print(f"\nCreated {filename} with frame {frame_hex[:16]}...")
            
            # Decode it
            output_wav = filename.replace('.bin', '_decoded.wav')
            # Note: Would need to run decoder here

def check_ambe_implementation_issue():
    """Check if there's an issue with our AMBE implementation"""
    
    print("\n=== AMBE Implementation Check ===")
    
    # Check bit ordering
    test_value = 0x034981EC0015F  # From our first frame
    
    # Try different bit orderings
    print("Testing bit ordering:")
    
    # Method 1: Our current (MSB first)
    bits_msb = []
    for i in range(49):
        bit = (test_value >> (48-i)) & 1
        bits_msb.append(bit)
    
    # Method 2: LSB first
    bits_lsb = []
    for i in range(49):
        bit = (test_value >> i) & 1
        bits_lsb.append(bit)
    
    print(f"MSB first: {bits_msb[:10]}...")
    print(f"LSB first: {bits_lsb[:10]}...")
    
    # Method 3: Byte-wise reversal
    bytes_normal = []
    for i in range(7):
        byte_val = (test_value >> (i*8)) & 0xFF
        bytes_normal.append(byte_val)
    
    bytes_reversed = bytes_normal[::-1]
    
    print(f"Normal bytes: {' '.join(f'{b:02X}' for b in bytes_normal)}")
    print(f"Reversed bytes: {' '.join(f'{b:02X}' for b in bytes_reversed)}")

def test_known_ambe_patterns():
    """Test with known AMBE patterns for tones"""
    
    # From DMR standards, these patterns are used for testing
    test_patterns = {
        'silence': 0x00E8D30001A3E,
        '1031_tone': 0x08E8D30001A3E,  # 1031 Hz test tone
        'dtmf_1': 0x10E8D30001A3E,     # DTMF digit 1
        'dtmf_2': 0x11E8D30001A3E,     # DTMF digit 2
    }
    
    for pattern_name, ambe_value in test_patterns.items():
        filename = f"test_{pattern_name}.bin"
        
        with open(filename, "wb") as f:
            # Convert to 8-byte frame format
            frame_64bit = (ambe_value << 15) & 0xFFFFFFFFFFFFFFFF
            frame_bytes = struct.pack('>Q', frame_64bit)
            
            # Write 2 seconds
            for _ in range(100):
                f.write(frame_bytes)
        
        print(f"Created {filename}")

def main():
    print("=== Final Tone Investigation ===\n")
    
    # Create reference tones
    create_pure_tone_test()
    
    # Analyze cleartext for patterns
    analyze_cleartext_for_patterns()
    
    # Test repeated frames
    test_repeated_frames()
    
    # Check implementation
    check_ambe_implementation_issue()
    
    # Test known patterns
    test_known_ambe_patterns()
    
    print("\n=== Investigation Complete ===")
    print("\nKey findings:")
    print("1. Check repeated frames - these might be tones or silence")
    print("2. Verify bit ordering in AMBE decoder")
    print("3. Test with known DMR test patterns")

if __name__ == "__main__":
    main()