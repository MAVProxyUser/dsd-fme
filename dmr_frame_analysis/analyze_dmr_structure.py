#!/usr/bin/env python3
"""
Analyze complete DMR voice frame structure and encryption
"""

import struct
import numpy as np

def explain_dmr_frame_structure():
    """Explain the complete DMR frame structure"""
    
    print("=== Complete DMR Voice Frame Structure ===\n")
    
    print("1. DMR Voice Burst (216 bits total):")
    print("   - 54 bits: CACH + sync pattern")
    print("   - 108 bits: Voice payload")
    print("   - 54 bits: Additional signaling\n")
    
    print("2. Voice Payload (108 bits = 54 dibits):")
    print("   - 3 AMBE frames interleaved")
    print("   - Each frame: 36 dibits (72 bits)")
    print("   - Total: 3 × 72 = 216 bits of AMBE data\n")
    
    print("3. Each AMBE Frame (72 bits):")
    print("   - 49 bits: Vocoder data (ENCRYPTED)")
    print("   - 23 bits: FEC (NOT encrypted)")
    print("   - Interleaved across the burst\n")
    
    print("4. Encryption Process:")
    print("   - Extract 49 vocoder bits")
    print("   - Pack into 7 bytes (49 bits)")
    print("   - Apply RC4 with key+MI")
    print("   - Unpack back to bit array")
    print("   - Apply FEC")
    print("   - Interleave into burst\n")

def analyze_iv_reuse_impact():
    """Analyze impact of IV reuse with complete frames"""
    
    print("=== IV Reuse Impact with Complete Frames ===\n")
    
    print("Current analysis (single frames):")
    print("- 1 ciphertext per IV")
    print("- Limited attack surface")
    print("- Missing related data\n")
    
    print("With complete frames:")
    print("- 3 ciphertexts per IV (same burst)")
    print("- All use identical keystream")
    print("- Can XOR all 3 frames:")
    print("  C1 ⊕ C2 = P1 ⊕ P2")
    print("  C1 ⊕ C3 = P1 ⊕ P3")
    print("  C2 ⊕ C3 = P2 ⊕ P3\n")
    
    print("Advantages:")
    print("- 3x more data per IV reuse")
    print("- Better statistical analysis")
    print("- Frames often related (continuous speech)")
    print("- Higher chance of known plaintext\n")

def simulate_complete_frame_attack():
    """Simulate attack with complete frames"""
    
    print("=== Simulated Attack with Complete Frames ===\n")
    
    # Simulate 3 AMBE frames with same IV
    iv = 0x12345678
    key = bytes([0xDA, 0x26, 0xB6, 0x38, 0xAF])
    
    # Three frames of speech (49 bits each)
    frame1 = 0x0123456789ABC  # Frame 1
    frame2 = 0x0FEDCBA987654  # Frame 2  
    frame3 = 0x0112233445566  # Frame 3
    
    print(f"IV: 0x{iv:08X}")
    print(f"Frame 1: 0x{frame1:013X}")
    print(f"Frame 2: 0x{frame2:013X}")
    print(f"Frame 3: 0x{frame3:013X}\n")
    
    # In reality, RC4 would generate keystream
    # For demo, simulate keystream
    keystream = 0x0AAAAAAAAAA
    
    # Encrypt all 3 with same keystream
    cipher1 = frame1 ^ keystream
    cipher2 = frame2 ^ keystream
    cipher3 = frame3 ^ keystream
    
    print("Ciphertexts (same keystream):")
    print(f"Cipher 1: 0x{cipher1:013X}")
    print(f"Cipher 2: 0x{cipher2:013X}")
    print(f"Cipher 3: 0x{cipher3:013X}\n")
    
    # XOR ciphertexts to get plaintext relationships
    xor_1_2 = cipher1 ^ cipher2
    xor_1_3 = cipher1 ^ cipher3
    xor_2_3 = cipher2 ^ cipher3
    
    print("XOR relationships (eliminates keystream):")
    print(f"C1 ⊕ C2 = 0x{xor_1_2:013X} = P1 ⊕ P2")
    print(f"C1 ⊕ C3 = 0x{xor_1_3:013X} = P1 ⊕ P3")
    print(f"C2 ⊕ C3 = 0x{xor_2_3:013X} = P2 ⊕ P3\n")
    
    # Verify these equal plaintext XORs
    plain_xor_1_2 = frame1 ^ frame2
    plain_xor_1_3 = frame1 ^ frame3
    plain_xor_2_3 = frame2 ^ frame3
    
    print("Verification (should match above):")
    print(f"P1 ⊕ P2 = 0x{plain_xor_1_2:013X}")
    print(f"P1 ⊕ P3 = 0x{plain_xor_1_3:013X}")
    print(f"P2 ⊕ P3 = 0x{plain_xor_2_3:013X}\n")

def check_our_current_data():
    """Check what we're missing in current data"""
    
    print("=== What We're Missing ===\n")
    
    print("Current data structure:")
    print("- Single AMBE frames (1 of 3)")
    print("- Don't know which position (1st, 2nd, or 3rd)")
    print("- Missing frame relationships")
    print("- Can't fully exploit IV reuse\n")
    
    print("Impact on our attack:")
    print("- Only 1/3 of available ciphertext")
    print("- Missing related plaintext patterns")
    print("- Reduced statistical analysis")
    print("- Harder to identify patterns\n")
    
    print("Recommended fix:")
    print("1. Modify db_logger.c to capture all 3 frames")
    print("2. Add burst sequence tracking")
    print("3. Preserve frame relationships")
    print("4. Update attack scripts to use complete data")

def main():
    print("=== DMR Complete Frame Analysis ===\n")
    
    # Explain structure
    explain_dmr_frame_structure()
    
    # Analyze IV reuse impact
    analyze_iv_reuse_impact()
    
    # Simulate attack
    simulate_complete_frame_attack()
    
    # Check current data
    check_our_current_data()
    
    print("\n=== Conclusion ===")
    print("We need to capture complete DMR voice frames!")
    print("This will 3x our attack capability per IV reuse.")
    print("The frames are related (same speech segment),")
    print("giving us better plaintext recovery chances.")

if __name__ == "__main__":
    main()