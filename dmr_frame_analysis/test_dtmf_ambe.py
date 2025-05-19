#!/usr/bin/env python3
"""
Test DTMF tones through AMBE - they MUST work!
"""

import struct
import numpy as np
import subprocess

def find_dtmf_frames():
    """Find frames in cleartext that might contain DTMF"""
    
    with open("cleartext_ambe.bin", "rb") as f:
        data = f.read()
    
    # DTMF frequencies for reference
    dtmf_freqs = {
        '1': (697, 1209), '2': (697, 1336), '3': (697, 1477),
        '4': (770, 1209), '5': (770, 1336), '6': (770, 1477),
        '7': (852, 1209), '8': (852, 1336), '9': (852, 1477),
        '*': (941, 1209), '0': (941, 1336), '#': (941, 1477)
    }
    
    # Look for frames with specific patterns that might indicate tones
    frames_analysis = []
    
    for i in range(0, len(data), 8):
        if i + 8 <= len(data):
            frame = data[i:i+8]
            frame_64bit = struct.unpack('>Q', frame)[0]
            ambe_49bit = frame_64bit >> 15
            
            # AMBE+2 structure analysis
            # Bits 0-7: Fundamental frequency/pitch
            pitch = ambe_49bit & 0xFF
            
            # Bits 8-11: Gain
            gain = (ambe_49bit >> 8) & 0xF
            
            # Bits 12-15: Voicing metrics
            voicing = (ambe_49bit >> 12) & 0xF
            
            # Bits 16-48: Spectral magnitudes/HOCs (Higher Order Coefficients)
            spectral = (ambe_49bit >> 16) & 0x1FFFFFFFF
            
            frames_analysis.append({
                'index': i//8,
                'frame': frame,
                'pitch': pitch,
                'gain': gain,
                'voicing': voicing, 
                'spectral': spectral,
                'ambe_49bit': ambe_49bit
            })
    
    # Sort by different characteristics
    high_pitch_frames = sorted(frames_analysis, key=lambda x: x['pitch'], reverse=True)[:10]
    high_gain_frames = sorted(frames_analysis, key=lambda x: x['gain'], reverse=True)[:10]
    
    print("=== High Pitch Frames (might be tones) ===")
    for f in high_pitch_frames[:5]:
        print(f"Frame {f['index']}: pitch={f['pitch']}, gain={f['gain']}, voicing={f['voicing']}")
        print(f"  AMBE: 0x{f['ambe_49bit']:013X}")
    
    return frames_analysis

def create_dtmf_test():
    """Create a test with frames that should contain DTMF"""
    
    frames_analysis = find_dtmf_frames()
    
    # Find frames with characteristics similar to DTMF
    # DTMF should have: high pitch, consistent gain, low voicing (not voice)
    tone_candidates = []
    
    for frame in frames_analysis:
        # DTMF characteristics in AMBE:
        # - Steady pitch (not varying like speech)
        # - Moderate to high gain
        # - Low voicing (because it's not voice)
        if frame['pitch'] > 20 and frame['gain'] > 5 and frame['voicing'] < 8:
            tone_candidates.append(frame)
    
    print(f"\nFound {len(tone_candidates)} tone candidates")
    
    if tone_candidates:
        # Create pattern using tone candidates
        with open("dtmf_test.bin", "wb") as f:
            # Write some of each candidate
            for candidate in tone_candidates[:5]:
                for _ in range(50):  # 1 second each
                    f.write(candidate['frame'])
        
        print("Created dtmf_test.bin")
        
        # Decode it
        subprocess.run([
            "python3", "decode_ambe_final.py",
            "dtmf_test.bin", "dtmf_test_decoded.wav"
        ])
        
        # Analyze frequency
        subprocess.run([
            "sox", "dtmf_test_decoded.wav", "-n", "stat"
        ], stderr=subprocess.STDOUT)

def check_ambe_implementation():
    """Check if our AMBE implementation is correct"""
    
    # Let's verify the bit ordering and frame structure
    test_frame = bytes.fromhex("1a4c0f6000af9000")
    frame_64bit = struct.unpack('>Q', test_frame)[0]
    
    print("\n=== AMBE Frame Structure Check ===")
    print(f"Test frame: {test_frame.hex()}")
    print(f"64-bit:     0x{frame_64bit:016X}")
    print(f"Binary:     {bin(frame_64bit)[2:].zfill(64)}")
    
    # Check different extraction methods
    ambe_49bit_shift = frame_64bit >> 15
    ambe_49bit_mask = (frame_64bit >> 15) & 0x1FFFFFFFFFFFF
    
    print(f"\nExtraction methods:")
    print(f"Shift right 15:     0x{ambe_49bit_shift:013X}")
    print(f"Shift + mask:       0x{ambe_49bit_mask:013X}")
    
    # Check bit-by-bit extraction
    bits = []
    for i in range(63, 14, -1):  # Bits 63 down to 15
        bit = (frame_64bit >> i) & 1
        bits.append(str(bit))
    
    print(f"Bit-by-bit: {''.join(bits)}")
    
    # Check if we need different bit ordering
    bits_reversed = []
    for i in range(49):
        bit = (ambe_49bit_shift >> (48-i)) & 1
        bits_reversed.append(bit)
    
    print(f"\nBit array (MSB first): {bits_reversed[:10]}...")

def main():
    print("=== DTMF/Tone AMBE Test ===\n")
    
    # Check our implementation
    check_ambe_implementation()
    
    # Find and test DTMF frames
    create_dtmf_test()
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()