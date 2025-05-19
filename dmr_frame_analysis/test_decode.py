#!/usr/bin/env python3
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
