#!/usr/bin/env python3

# Time calculations based on actual test data
actual_test_duration = 30  # seconds
actual_frames_captured = 1350
frames_per_second = actual_frames_captured / actual_test_duration

print("Time Requirements for RC4 Attack Data Collection")
print("=" * 50)

print(f"\nActual capture rate from test:")
print(f"  Duration: {actual_test_duration} seconds")
print(f"  Frames captured: {actual_frames_captured}")
print(f"  Rate: {frames_per_second:.1f} frames/second")

# Calculate time for different attack levels (from earlier analysis)
attack_requirements = {
    "Basic Statistical": 10_000,
    "Advanced Correlation": 100_000,
    "Plaintext Recovery": 1_000_000
}

print(f"\nTime requirements per attack type:")
for attack_type, frames_needed in attack_requirements.items():
    seconds_needed = frames_needed / frames_per_second
    minutes = seconds_needed / 60
    hours = minutes / 60
    
    # Calculate PTT sessions needed (5 second average)
    ptt_sessions = seconds_needed / 5
    
    print(f"\n{attack_type} Attack ({frames_needed:,} frames):")
    print(f"  Time needed: {seconds_needed:.0f} seconds ({minutes:.1f} minutes)")
    if hours > 1:
        print(f"             ({hours:.1f} hours)")
    print(f"  PTT sessions: ~{ptt_sessions:.0f} (5 sec average)")
    print(f"  30-sec captures: {seconds_needed/30:.0f}")

# Multiple captures analysis
print(f"\nMultiple Capture Strategy:")
print(f"For plaintext recovery with same H- MI:")

scenarios = [
    (100, "100 short bursts"),
    (50, "50 medium bursts"),
    (20, "20 long bursts")
]

for captures, desc in scenarios:
    avg_duration = 1_000_000 / frames_per_second / captures
    print(f"  {desc}: {avg_duration:.1f} seconds each")

# Superframe analysis
print(f"\nSuperframe Structure in DMR:")
print(f"  Duration: 360ms (6 voice frames)")
print(f"  AMBE frames: 18 per superframe")
print(f"  Structure:")
print(f"    Voice burst 1: 3 AMBE frames")
print(f"    Voice burst 2: 3 AMBE frames")
print(f"    Voice burst 3: 3 AMBE frames")
print(f"    Voice burst 4: 3 AMBE frames")
print(f"    Voice burst 5: 3 AMBE frames")
print(f"    Voice burst 6: 3 AMBE frames")
print(f"    CACH + Sync")

print(f"\nLogging Superframes - Analysis:")
print(f"Current approach:")
print(f"  - Logs individual AMBE frames with MI context")
print(f"  - Each frame linked to its C- MI")
print(f"  - Natural grouping by timestamp")

print(f"\nPotential superframe benefits:")
print(f"  1. Timing correlation (all 18 frames as unit)")
print(f"  2. CACH data correlation")
print(f"  3. Sync pattern analysis")
print(f"  4. Inter-frame relationships")

print(f"\nRecommendation:")
print(f"  Add superframe table with:")
print(f"    - Superframe ID")
print(f"    - Start timestamp")
print(f"    - CACH data")
print(f"    - Sync type")
print(f"    - Link to 18 AMBE frames")