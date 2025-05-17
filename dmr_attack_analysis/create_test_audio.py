#!/usr/bin/env python3
"""
Create test audio file with alternating 2400Hz and 2600Hz beeps
to verify AMBE+2 vocoder decoding behavior
"""

import numpy as np
import wave
import struct

# Parameters
SAMPLE_RATE = 8000  # AMBE+2 typically uses 8kHz
DURATION = 0.5  # Duration of each beep in seconds
SILENCE_DURATION = 0.1  # Duration of silence between beeps
NUM_ALTERNATIONS = 10  # Number of beep pairs

def create_beep(frequency, duration, sample_rate):
    """Create a sine wave beep at specified frequency"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    beep = np.sin(2 * np.pi * frequency * t)
    # Apply fade in/out to avoid clicking
    fade_samples = int(0.01 * sample_rate)
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    beep[:fade_samples] *= fade_in
    beep[-fade_samples:] *= fade_out
    return beep

def create_silence(duration, sample_rate):
    """Create silence"""
    return np.zeros(int(sample_rate * duration))

def main():
    # Generate alternating beeps
    audio_data = []
    
    for i in range(NUM_ALTERNATIONS):
        # 2400Hz beep
        beep_2400 = create_beep(2400, DURATION, SAMPLE_RATE)
        audio_data.extend(beep_2400)
        
        # Silence
        silence = create_silence(SILENCE_DURATION, SAMPLE_RATE)
        audio_data.extend(silence)
        
        # 2600Hz beep
        beep_2600 = create_beep(2600, DURATION, SAMPLE_RATE)
        audio_data.extend(beep_2600)
        
        # Silence
        audio_data.extend(silence)
    
    # Normalize to 16-bit range
    audio_data = np.array(audio_data)
    audio_data = audio_data / np.max(np.abs(audio_data))  # Normalize to [-1, 1]
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # Save as WAV file
    with wave.open('test_beep_pattern.wav', 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_data.tobytes())
    
    print(f"Created test_beep_pattern.wav with {NUM_ALTERNATIONS} alternations")
    print(f"Pattern: 2400Hz ({DURATION}s) -> silence ({SILENCE_DURATION}s) -> 2600Hz ({DURATION}s) -> silence ({SILENCE_DURATION}s)")
    print(f"Total duration: {len(audio_data) / SAMPLE_RATE:.2f} seconds")

if __name__ == "__main__":
    main()