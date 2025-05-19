#!/usr/bin/env python3
"""Decode AMBE frames using the correct MD380 format"""

import sqlite3
import struct
import subprocess
import os

def decode_ambe_correctly():
    """Convert our AMBE frames to MD380 format and decode"""
    
    print("=== DECODING AMBE WITH CORRECT MD380 FORMAT ===")
    
    cleartext_db = "dmr_capture_20250518_112958_062803.db"
    conn = sqlite3.connect(cleartext_db)
    cursor = conn.cursor()
    
    # Get all cleartext AMBE frames
    cursor.execute("SELECT ambe_hex FROM U_00000000_S0 ORDER BY id")
    ambe_frames = [row[0] for row in cursor.fetchall()]
    
    print(f"\nProcessing {len(ambe_frames)} AMBE frames")
    
    # MD380 expects 49 bits packed into 7 bytes MSB order
    # Our frames are 64 bits - we need to extract the correct 49 bits
    
    # Create binary file in MD380 format
    md380_file = "ambe_md380_format.bin"
    
    with open(md380_file, 'wb') as f:
        for i, frame_hex in enumerate(ambe_frames):
            frame_int = int(frame_hex, 16)
            
            # DMR AMBE+2 uses lower 49 bits
            ambe_49bits = frame_int & 0x1FFFFFFFFFFFF  # Mask to 49 bits
            
            # Pack into 7 bytes MSB order
            ambe_bytes = ambe_49bits.to_bytes(7, byteorder='big')
            f.write(ambe_bytes)
            
            if i < 5:  # Show first few conversions
                print(f"Frame {i}: {frame_hex} -> {ambe_bytes.hex()}")
    
    print(f"\nWrote {len(ambe_frames)} frames to {md380_file}")
    print(f"File size: {os.path.getsize(md380_file)} bytes (should be {len(ambe_frames) * 7})")
    
    # Create decode script
    decode_script = "decode_audio.sh"
    with open(decode_script, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Decode AMBE to PCM audio\n\n")
        
        f.write("# Build md380_vocoder if needed\n")
        f.write("if [ ! -f 'md380_vocoder/md380_vocoder' ]; then\n")
        f.write("    cd md380_vocoder && make && cd ..\n")
        f.write("fi\n\n")
        
        f.write("# Decode AMBE to raw PCM\n")
        f.write(f"echo 'Decoding {len(ambe_frames)} AMBE frames...'\n")
        f.write(f"./md380_vocoder/md380_vocoder < {md380_file} > decoded_audio.pcm\n\n")
        
        f.write("# Convert raw PCM to WAV\n")
        f.write("echo 'Converting to WAV...'\n")
        f.write("sox -r 8000 -e signed -b 16 -c 1 decoded_audio.pcm decoded_audio.wav\n\n")
        
        f.write("# Create spectrogram\n")
        f.write("echo 'Creating spectrogram...'\n")
        f.write("sox decoded_audio.wav -n spectrogram -o spectrogram.png\n\n")
        
        f.write("echo 'Done! Files created:'\n")
        f.write("echo '  - decoded_audio.pcm (raw audio)'\n")
        f.write("echo '  - decoded_audio.wav (playable audio)'\n")
        f.write("echo '  - spectrogram.png (visual representation)'\n")
    
    os.chmod(decode_script, 0o755)
    
    # Also create a test with just first few frames
    test_file = "test_first_100.bin"
    with open(test_file, 'wb') as f:
        for frame_hex in ambe_frames[:100]:
            frame_int = int(frame_hex, 16)
            ambe_49bits = frame_int & 0x1FFFFFFFFFFFF
            ambe_bytes = ambe_49bits.to_bytes(7, byteorder='big')
            f.write(ambe_bytes)
    
    print(f"\nAlso created {test_file} with first 100 frames for testing")
    
    # Create Python decoder for testing
    with open("test_decode.py", 'w') as f:
        f.write("""#!/usr/bin/env python3
import subprocess
import sys

# Test decoding a small sample
print("Testing MD380 decoder with first 100 frames...")

result = subprocess.run([
    "./md380_vocoder/md380_vocoder"
], stdin=open("test_first_100.bin", "rb"), 
   stdout=open("test_output.pcm", "wb"),
   stderr=subprocess.PIPE)

if result.returncode == 0:
    print("Success! Created test_output.pcm")
    print(f"Output size: {os.path.getsize('test_output.pcm')} bytes")
    print("Expected: ~32000 bytes (100 frames * 160 samples * 2 bytes)")
else:
    print(f"Error: {result.stderr.decode()}")
""")
    
    conn.close()
    
    print("\n=== READY TO DECODE ===")
    print("1. Run: ./decode_audio.sh")
    print("   This will decode all frames to audio")
    print("\n2. Or test with: python3 test_decode.py")
    print("   This will test first 100 frames")
    
    print("\n=== AUDIO ANALYSIS ===")
    print(f"Expected audio duration: {len(ambe_frames) * 0.02:.1f} seconds")
    print(f"Expected PCM size: {len(ambe_frames) * 160 * 2} bytes")
    print(f"Sample rate: 8000 Hz")

if __name__ == "__main__":
    decode_ambe_correctly()