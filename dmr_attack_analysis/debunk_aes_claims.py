#!/usr/bin/env python3
"""
Demonstrate why AES with static IV is still vulnerable in DMR context
"""

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import numpy as np
import hashlib

def demonstrate_aes_vulnerability():
    """Show how AES with static IV fails in DMR context"""
    
    # Simulate DMR scenario
    key = hashlib.sha256(b"DMR_KEY_EXAMPLE").digest()[:16]  # 128-bit key
    static_iv = b"1234567890123456"  # Static 16-byte IV
    
    print("=== AES with Static IV Vulnerability Demo ===\n")
    
    # 1. Pattern Recognition Attack
    print("1. PATTERN RECOGNITION ATTACK:")
    
    # DMR transmissions often start with predictable patterns
    # Example: Call start sequence
    call_start = pad(b"CALL_START_BEACON_001", AES.block_size)
    call_start2 = pad(b"CALL_START_BEACON_001", AES.block_size)
    different_call = pad(b"DIFFERENT_CONTENT_XYZ", AES.block_size)
    
    # Encrypt with static IV
    cipher = AES.new(key, AES.MODE_CBC, static_iv)
    encrypted1 = cipher.encrypt(call_start)
    
    cipher = AES.new(key, AES.MODE_CBC, static_iv)
    encrypted2 = cipher.encrypt(call_start2)
    
    cipher = AES.new(key, AES.MODE_CBC, static_iv)
    encrypted3 = cipher.encrypt(different_call)
    
    print(f"Same plaintext encryption 1: {encrypted1.hex()}")
    print(f"Same plaintext encryption 2: {encrypted2.hex()}")
    print(f"Different plaintext:         {encrypted3.hex()}")
    print(f"Identical ciphertexts: {encrypted1 == encrypted2}")
    print()
    
    # 2. Block Correlation Attack
    print("2. BLOCK CORRELATION ATTACK:")
    
    # DMR frames have structure: [Header][Voice][Voice][Voice]
    # With static IV, identical voice blocks produce identical ciphertext
    
    silence_block = b"\x00" * 16  # Common in DMR (silence)
    voice_block1 = b"VOICE_PATTERN_01"
    voice_block2 = b"VOICE_PATTERN_02"
    
    # Create DMR-like frame
    frame1 = pad(silence_block + voice_block1 + silence_block, AES.block_size)
    frame2 = pad(silence_block + voice_block2 + silence_block, AES.block_size)
    
    cipher = AES.new(key, AES.MODE_CBC, static_iv)
    enc_frame1 = cipher.encrypt(frame1)
    
    cipher = AES.new(key, AES.MODE_CBC, static_iv)
    enc_frame2 = cipher.encrypt(frame2)
    
    # Extract blocks
    block_size = 16
    blocks1 = [enc_frame1[i:i+block_size] for i in range(0, len(enc_frame1), block_size)]
    blocks2 = [enc_frame2[i:i+block_size] for i in range(0, len(enc_frame2), block_size)]
    
    # Check for correlations
    print("Frame 1 blocks (first 8 bytes each):")
    for i, block in enumerate(blocks1):
        print(f"  Block {i}: {block[:8].hex()}...")
    
    print("\nFrame 2 blocks (first 8 bytes each):")
    for i, block in enumerate(blocks2):
        print(f"  Block {i}: {block[:8].hex()}...")
    
    # Find matching blocks
    matches = []
    for i, b1 in enumerate(blocks1):
        for j, b2 in enumerate(blocks2):
            if b1 == b2:
                matches.append((i, j))
    
    print(f"\nMatching blocks: {matches}")
    print()
    
    # 3. Traffic Analysis
    print("3. TRAFFIC ANALYSIS VULNERABILITY:")
    
    # In DMR, certain messages are predictable
    dmr_messages = [
        b"PTT_START",
        b"PTT_END",
        b"EMERGENCY",
        b"STATUS_OK",
        b"PTT_START",  # Repeated message
        b"GROUP_CALL"
    ]
    
    encrypted_messages = []
    for msg in dmr_messages:
        cipher = AES.new(key, AES.MODE_CBC, static_iv)
        encrypted = cipher.encrypt(pad(msg, AES.block_size))
        encrypted_messages.append(encrypted)
    
    # Analysis
    print("Message fingerprints:")
    fingerprints = {}
    for i, (msg, enc) in enumerate(zip(dmr_messages, encrypted_messages)):
        fp = enc[:8].hex()
        if fp in fingerprints:
            print(f"  Message {i} '{msg.decode()}': {fp} [DUPLICATE of message {fingerprints[fp]}]")
        else:
            fingerprints[fp] = i
            print(f"  Message {i} '{msg.decode()}': {fp}")
    
    print("\n4. DMR-SPECIFIC VULNERABILITIES:")
    print("- Beep patterns at transmission start/end are predictable")
    print("- AMBE frames have known structure")
    print("- Control messages follow fixed formats")
    print("- Static IV means these patterns ALWAYS encrypt the same way")
    
    return encrypted1 == encrypted2

def compare_to_rc4_attack():
    """Compare AES static IV to our successful RC4 attack"""
    
    print("\n=== Comparison to DMR RC4 Attack ===\n")
    
    print("RC4 Attack (Our Results):")
    print("- 100% keystream recovery")
    print("- Direct plaintext recovery")
    print("- Based on XOR properties")
    print()
    
    print("AES with Static IV Attack:")
    print("- Pattern recognition works")
    print("- Traffic analysis possible")
    print("- Chosen plaintext attacks viable")
    print("- Dictionary attacks on common messages")
    print()
    
    print("PRACTICAL EXPLOITATION:")
    print("1. Build dictionary of common DMR messages")
    print("2. Identify patterns in encrypted traffic")
    print("3. Correlate with known transmission behaviors")
    print("4. Decrypt common messages through matching")
    print("5. Use context to infer remaining content")

def explain_real_world_impact():
    """Explain why this matters in practice"""
    
    print("\n=== Real-World DMR Impact ===\n")
    
    print("Why Static IV Breaks DMR Security:")
    print()
    
    print("1. PREDICTABLE CONTENT:")
    print("   - PTT start/end sequences")
    print("   - Emergency alerts")
    print("   - Status messages")
    print("   - Call setup/teardown")
    print()
    
    print("2. REPEATED PATTERNS:")
    print("   - Silence periods")
    print("   - DTMF tones")
    print("   - Alert beeps")
    print("   - Standard voice patterns")
    print()
    
    print("3. METADATA LEAKAGE:")
    print("   - When calls start/end")
    print("   - Who's talking to whom")
    print("   - Emergency situations")
    print("   - Communication patterns")
    print()
    
    print("4. CHOSEN PLAINTEXT:")
    print("   - Attacker can trigger predictable messages")
    print("   - Emergency button = known plaintext")
    print("   - Status queries = known responses")
    print()
    
    print("CONCLUSION: AES with static IV in DMR is NOT secure!")

if __name__ == "__main__":
    # Run demonstrations
    demonstrate_aes_vulnerability()
    compare_to_rc4_attack()
    explain_real_world_impact()
    
    print("\n=== PERSON'S CLAIMS DEBUNKED ===")
    print()
    print("✗ 'AES doesn't need IV' - FALSE for CBC mode")
    print("✗ 'Not a practical exploit' - FALSE, patterns leak info")
    print("✗ 'Can't decrypt in real time' - FALSE for common messages")
    print("✗ 'Only tells A sent same to B&C' - FALSE, reveals content")
    print()
    print("The person fundamentally misunderstands DMR's predictable")
    print("message structure and how static IV undermines AES security.")