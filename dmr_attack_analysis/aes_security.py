#!/usr/bin/env python3

# Calculate attack complexities
print("Attack Complexity Comparison:")
print("=" * 40)

# RC4 attacks
print("RC4 with predictable IVs:")
print(f"  IV space: 2^32 = {2**32:,}")
print(f"  Known attacks: ~2^24 operations")
print(f"  Time at 1M ops/sec: {2**24 / 1_000_000:.1f} seconds")
print(f"  Practical? YES")

# AES-128 attacks
print("\nAES-128 with predictable IVs:")
print(f"  IV space: 2^128 = {2**128:.2e}")
print(f"  Best known attack: ~2^126 operations")
print(f"  Time at 1M ops/sec: {2**126 / 1_000_000 / 365 / 24 / 3600:.2e} years")
print(f"  Practical? NO")

# AES-256 attacks
print("\nAES-256 with predictable IVs:")
print(f"  Key space: 2^256 = {2**256:.2e}")
print(f"  Best known attack: ~2^254 operations")
print(f"  Time at 1M ops/sec: {2**254 / 1_000_000 / 365 / 24 / 3600:.2e} years")
print(f"  Practical? NO")

print("\nSpecific DMR Vulnerabilities:")
print("\nRC4 Mode:")
print("  1. Static H- MI creates patterns")
print("  2. Small IV space allows correlation")
print("  3. RC4 biases amplify weaknesses")
print("  4. Practical attacks possible")

print("\nAES Mode:")
print("  1. Static H- MI still predictable")
print("  2. But 128-bit IVs prevent correlation")
print("  3. No known AES weaknesses to exploit")
print("  4. Only theoretical attacks remain")

print("\nRecommendation Summary:")
print("RC4: Vulnerable to practical attacks")
print("AES-128: Secure against all known attacks")
print("AES-256: Overkill but maximum security")

print("\nEven with the same LFSR predictability,")
print("AES makes attacks computationally infeasible")