#!/usr/bin/env python3

# DMR timing calculations
superframe_duration = 360  # ms (6 frames × 60ms each)
frames_per_superframe = 18  # 3 AMBE frames × 6 voice bursts
updates_per_second = 1000 / superframe_duration
frames_per_second = frames_per_superframe * updates_per_second

print("30-Second RC4 Test Plan")
print("=" * 40)

print(f"DMR Voice Timing:")
print(f"  Superframe duration: {superframe_duration}ms")
print(f"  Superframes per second: {updates_per_second:.1f}")
print(f"  AMBE frames per second: {frames_per_second:.1f}")

# 30-second test
test_duration = 30
total_superframes = int(test_duration * updates_per_second)
total_frames = int(test_duration * frames_per_second)

print(f"\n30-Second Test Collection:")
print(f"  Duration: {test_duration} seconds")
print(f"  Superframes: {total_superframes}")
print(f"  AMBE frames: {total_frames}")
print(f"  C- MI updates: {total_superframes}")

print(f"\nExpected Data Structure:")
print(f"  1 H- frame at start (MI: 6C8AB637)")
print(f"  {total_superframes} C- frames with evolving MIs")
print(f"  {total_frames} AMBE frames total")

print(f"\nSilence Pattern Analysis:")
print(f"  Background noise level: Variable")
print(f"  AMBE quantization: 49 bits/frame")
print(f"  Vocoder artifacts: Present")
print(f"  Expected variation: High")

print(f"\nTest Procedure:")
print(f"1. Clear database: rm dsd_fme.db")
print(f"2. Start dsd-fme")
print(f"3. Key radio for exactly 30 seconds")
print(f"4. Release PTT")
print(f"5. Stop dsd-fme after squelch tail")
print(f"6. Analyze collected frames")

print(f"\nWhat We're Looking For:")
print(f"1. AMBE frame patterns during silence")
print(f"2. Bit distribution in 'quiet' frames")
print(f"3. Correlation between similar frames")
print(f"4. Statistical anomalies")

print(f"\nNext Test (with Roger Beep):")
print(f"1. Same 30-second duration")
print(f"2. Roger beep at end (~500ms)")
print(f"3. Known pattern to correlate")
print(f"4. Better attack reference point")