#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('dsd_fme.db')
cursor = conn.cursor()

# Analyze frame distribution per transmission
cursor.execute("""
    SELECT c.control_mi, COUNT(f.id) as frame_count
    FROM dmr_correlations c
    LEFT JOIN C_E8083B57_S0 f ON 1=1
    WHERE c.control_mi = 0xE8083B57
    GROUP BY c.control_mi
""")

print("Frame Analysis for Cryptanalysis:")
print("=" * 40)

# DMR timing
superframe_duration = 360  # ms (6 frames × 60ms)
frames_per_superframe = 3  # 3 AMBE frames per voice burst

print(f"DMR Voice Timing:")
print(f"  Superframe duration: {superframe_duration}ms")
print(f"  AMBE frames per superframe: {frames_per_superframe * 6}")
print(f"  Updates per second: {1000/superframe_duration:.1f}")

# Required data for attacks
print("\nRequired Data for Various Attacks:")

# Basic statistical attack
basic_frames = 10000  # Conservative estimate
basic_time = (basic_frames / 18) * (superframe_duration / 1000)
print(f"1. Basic Statistical Attack:")
print(f"   Frames needed: ~{basic_frames:,}")
print(f"   Time required: ~{basic_time:.1f} seconds")
print(f"   PTT sessions: ~{basic_time/5:.0f} (5 sec average)")

# Advanced correlation attack
advanced_frames = 100000
advanced_time = (advanced_frames / 18) * (superframe_duration / 1000)
print(f"\n2. Advanced Correlation Attack:")
print(f"   Frames needed: ~{advanced_frames:,}")
print(f"   Time required: ~{advanced_time:.1f} seconds")
print(f"   PTT sessions: ~{advanced_time/5:.0f} (5 sec average)")

# Plaintext recovery
plaintext_frames = 1000000
plaintext_time = (plaintext_frames / 18) * (superframe_duration / 1000)
print(f"\n3. Plaintext Recovery Attack:")
print(f"   Frames needed: ~{plaintext_frames:,}")
print(f"   Time required: ~{plaintext_time:.1f} seconds")
print(f"   PTT sessions: ~{plaintext_time/5:.0f} (5 sec average)")

print("\nSilence/Pattern Detection Issues:")
print("1. Background noise varies 10-30dB")
print("2. Vocoder quantization adds uncertainty")
print("3. AGC/preprocessing affects 'silence'")
print("4. AMBE compression is lossy")
print("5. Even 'silence' produces varying bits")

print("\nRealistic Exploitable Patterns:")
print("1. Digital squelch tail (fixed pattern)")
print("2. Repeater courtesy tones")
print("3. MDC1200/similar data bursts")
print("4. Automated announcements")
print("5. Time/temperature recordings")

conn.close()