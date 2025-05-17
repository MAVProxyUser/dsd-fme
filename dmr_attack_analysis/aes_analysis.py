#!/usr/bin/env python3

def lfsr_dmr_aes(mi):
    """DMR AES LFSR - expands 32-bit MI to 128-bit IV"""
    lfsr = mi & 0xFFFFFFFF
    aes_iv = bytearray(16)
    
    # First 4 bytes are the original MI
    aes_iv[0] = (lfsr >> 24) & 0xFF
    aes_iv[1] = (lfsr >> 16) & 0xFF
    aes_iv[2] = (lfsr >> 8) & 0xFF
    aes_iv[3] = lfsr & 0xFF
    
    # Generate 96 more bits (12 bytes) using LFSR
    x = 32
    for cnt in range(96):
        # Different polynomial: x^32 + x^22 + x^2 + x + 1
        bit = ((lfsr >> 31) ^ (lfsr >> 21) ^ (lfsr >> 1) ^ (lfsr >> 0)) & 0x1
        lfsr = (lfsr << 1) | bit
        
        # Pack into IV array
        byte_idx = x // 8
        bit_pos = 7 - (x % 8)
        aes_iv[byte_idx] |= (bit << bit_pos)
        x += 1
    
    # Extract next 32-bit MI from bytes 4-7
    next_mi = (aes_iv[4] << 24) | (aes_iv[5] << 16) | (aes_iv[6] << 8) | aes_iv[7]
    
    return aes_iv, next_mi

# Test with the same H- MI
h_mi = 0x6C8AB637
print("AES vs RC4 Comparison:")
print("=" * 40)
print(f"Starting H- MI: {h_mi:08X}\n")

print("RC4 (32-bit IVs):")
# RC4 sequence (from previous analysis)
rc4_sequence = [0xE8083B57, 0x4F36EE3A, 0x752FEA1C, 0x9A0C201B, 0xD3C028BF]
for i, mi in enumerate(rc4_sequence[:5]):
    print(f"  C- MI {i+1}: {mi:08X}")

print("\nAES (128-bit IVs):")
current_mi = h_mi
for i in range(5):
    aes_iv, next_mi = lfsr_dmr_aes(current_mi)
    print(f"  C- MI {i+1}: {next_mi:08X} (truncated)")
    print(f"    Full IV: {aes_iv.hex()}")
    current_mi = next_mi

print("\nKey Security Differences:")
print("1. AES uses 128-bit IVs (vs 32-bit for RC4)")
print("2. AES has stronger key schedule")
print("3. AES resistant to RC4's biases")
print("4. Same LFSR predictability issue exists")
print("5. But AES is much harder to attack")

print("\nAttack Difficulty Comparison:")
print("RC4 Vulnerabilities:")
print("  - Known biases in keystream")
print("  - Small IV space (32-bit)")
print("  - Weak key schedule")
print("  - ~2^24 complexity attacks exist")

print("\nAES Strengths:")
print("  - No known practical attacks on AES-128/256")
print("  - Larger IV space (128-bit)")
print("  - Strong key schedule")
print("  - Best attacks still ~2^126 complexity")

print("\nBottom Line:")
print("Switching to AES makes the system MUCH more secure")
print("even with the same predictable IV generation")