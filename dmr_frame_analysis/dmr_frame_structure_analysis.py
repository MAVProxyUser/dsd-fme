#!/usr/bin/env python3
"""
DMR Voice Frame Structure Analysis
Understanding the complete 288-bit voice frame and encryption
"""

def analyze_dmr_frame_structure():
    print("=== DMR Voice Frame Structure ===")
    print("Total: 144 dibits = 288 bits\n")
    
    print("Frame Layout:")
    print("1. CACH: 12 dibits (24 bits)")
    print("2. AMBE Frame 1: 36 dibits (72 bits)")
    print("3. AMBE Frame 2 (first half): 18 dibits (36 bits)")
    print("4. Sync/Embedded Signaling: 24 dibits (48 bits)")
    print("5. AMBE Frame 2 (second half): 18 dibits (36 bits)")
    print("6. AMBE Frame 3: 36 dibits (72 bits)")
    print()
    
    print("=== AMBE Frame Structure (96 bits each) ===")
    print("Total bits: 4 × 24 = 96 bits")
    print("Current logging: Only 64 bits (missing 32 bits!)")
    print()
    
    print("AMBE+2 Vocoder (3600 bps):")
    print("- Frame duration: 20ms")
    print("- Bits per frame: 72 (3600 × 0.02)")
    print("- But DMR uses 49 bits for vocoder")
    print("- Remaining bits: FEC/padding")
    print()
    
    print("=== Encryption Details ===")
    print("Only 49 vocoder bits are encrypted")
    print("FEC is applied AFTER encryption")
    print("All 3 frames in a burst use the SAME IV")
    print()
    
    print("=== Critical Issues with Current Implementation ===")
    print("1. We're only logging 64/96 bits per AMBE frame")
    print("2. Missing 32 bits × 3 frames = 96 bits per burst")
    print("3. This is 33% data loss!")
    print()
    
    print("=== Required Changes ===")
    print("1. Modify db_logger.c to capture full 96-bit frames")
    print("2. Update SQLite schema to handle larger values")
    print("3. Adjust analysis scripts for complete frames")
    print()
    
    # Show the interleaving pattern
    print("=== DMR Interleaving Pattern ===")
    rW = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2]
    rX = [23, 10, 22, 9, 21, 8, 20, 7, 19, 6, 18, 5, 17, 4, 16, 3, 15, 2, 14, 1, 13, 0, 12, 10, 11, 9, 10, 8, 9, 7, 8, 6, 7, 5, 6, 4]
    rY = [0, 2, 0, 2, 0, 2, 0, 2, 0, 3, 0, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3]
    rZ = [5, 3, 4, 2, 3, 1, 2, 0, 1, 13, 0, 12, 22, 11, 21, 10, 20, 9, 19, 8, 18, 7, 17, 6, 16, 5, 15, 4, 14, 3, 13, 2, 12, 1, 11, 0]
    
    print("This pattern distributes 36 dibits across the 4×24 bit array")
    print()
    
    # Calculate encryption coverage
    print("=== Encryption Coverage ===")
    vocoder_bits = 49
    total_bits = 96
    encrypted_percentage = (vocoder_bits / total_bits) * 100
    
    print(f"Vocoder bits (encrypted): {vocoder_bits}")
    print(f"Total AMBE frame bits: {total_bits}")
    print(f"Encryption coverage: {encrypted_percentage:.1f}%")
    print(f"FEC/padding (unencrypted): {total_bits - vocoder_bits} bits")
    print()
    
    print("=== Attack Implications ===")
    print("1. All 3 frames use same IV = 3× plaintext/ciphertext pairs")
    print("2. Only 49/96 bits encrypted = easier pattern analysis")
    print("3. FEC bits are unencrypted = structure leakage")
    print("4. Current logging missing 1/3 of data = reduced attack surface")

if __name__ == "__main__":
    analyze_dmr_frame_structure()