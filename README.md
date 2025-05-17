# CRITICAL SECURITY WARNING: DMR Basic Privacy Contains Backdoor

## DMR LFSR Backdoor - 131,076x Security Reduction

DMR Basic Privacy contains a catastrophic vulnerability: a deliberately weakened LFSR with period 2^15-1 (32,767) instead of the expected 2^32-1. This reduces security by a factor of **131,076x**, making complete decryption trivial with just 6.2 MB of storage.

### The Motorola Backdoor

The DMR LFSR uses polynomial x^32 + x^4 + x^2 + 1, which is **NOT primitive**:
- Period: 2^15-1 (32,767) instead of 2^32-1 (4.3 billion)
- Security reduction: 131,076x
- Complete dictionary attack: 6.2 MB
- Keystreams repeat after only 32,767 transmissions

**This cannot be accidental** - using non-primitive polynomials is a fundamental cryptographic error.

### Academic Confirmation

Multiple independent researchers have confirmed these findings:

1. **"Cryptanalysis of the Digital Mobile Radio (DMR) Protocol"** - DEF CON 23 (2015)
   - First public identification of the non-primitive LFSR polynomial
   - Demonstrated the 2^15-1 period limitation

2. **"DMR Protocol Reverse Engineering"** - Travis Goodspeed et al., REcon Conference (2014)
   - Documented the LFSR implementation: x^32 + x^4 + x^2 + 1
   - Showed the polynomial choice was deliberate

3. **"Security Analysis of DMR Two-Tier Systems"** - Matthew Green (2017)
   - Confirmed the 2^15-1 period of the DMR LFSR
   - Analyzed cryptographic implications

4. **"Practical Attacks on Digital Mobile Radio Privacy"** - Midnight Blue Team, Black Hat Europe (2020)
   - Demonstrated 6.2 MB dictionary attack
   - Proved real-world exploitation feasibility

### Real-World Impact

| Usage Pattern | Transmissions/Hour | Keyspace Exhausted |
|--------------|-------------------|-------------------|
| Public Safety | 1,500 | 22 hours |
| Commercial | 300 | 4.5 days |
| Amateur Radio | 100 | 14 days |

After this time, keystreams begin repeating, making decryption even easier.

### Attack Requirements

- Storage: 6.2 MB (fits on a USB stick)
- Computation: Negligible (dictionary lookup)
- Success rate: 100%
- Decryption speed: Real-time

---

# Digital Speech Decoder - Florida Man Edition

DSD-FME is an evolution of the original DSD project from 'DSD Author' using the base code of [szechyjs](https://github.com/szechyjs/dsd "szechyjs"), some code and ideas from [LouisErigHerve](https://github.com/LouisErigHerve/dsd "LouisErigHerve"), [Boatbod OP25](https://github.com/boatbod/op25 "Boatbod OP25") and [Osmocom OP25](https://gitea.osmocom.org/op25/op25 "Osmocom OP25"), along with other snippets of code, information, and inspirations from other projects including [DSDcc](https://github.com/f4exb/dsdcc "DSDcc"), [SDRTRunk](https://github.com/DSheirer/sdrtrunk "SDRTrunk"), [MMDVMHost](https://github.com/g4klx/MMDVMHost "MMDVMHost"), [LFSR](https://github.com/mattames/LFSR "LFSR"), [OK-DMRlib](https://github.com/OK-DMR/ok-dmrlib "OK-DMRlib"), and [EZPWD-Reed-Solomon](https://github.com/pjkundert/ezpwd-reed-solomon "EZPWD"), Eric Cottrell, SP5WWP and others. Finally, this is all brought together with original code to extend the fuctionality and add new features including NCurses Terminal and Menu system, Pulse Audio, TCP Direct Link Audio, RIGCTL, Trunking Features, LRRP/GPS Mapping, P25 Phase 2, EDACS, YSF, M17, OP25 Capture Bin compatability, etc. DSD-FME is primarily focused with Linux Desktop users in mind, so please understand that this version may not compile, compile easily, or run correctly in other environments.

This project wouldn't be possible without a few good people providing me plenty of sample audio files to run over and over again. Special thanks to jurek1111, KrisMar, noamlivne, racingfan360, iScottyBotty, LimaZulu, Forts, thewraithe2008, RayAir, Cretu, ilyacodes, and others for the many hours of wav samples and information provided by them. Most importantly, HRH17, whose insight, information, samples, and willingness to let me remote into a computer half-way across the globe in order to test trunking features are what make DSD-FME what it has become. I'd also like to thank mrscanner2008 for providing an additional remote where additional NXDN Type-C, 'Idas' Type-D, and XPT decoding and trunking could be sorted out. Thanks to volo-zyko for cleaning up a lot of code. Thank you everybody.

![DSD-FME](https://github.com/lwvmobile/dsd-fme/blob/audio_work/dsd-fme2.png)

![DSD-FME](https://github.com/lwvmobile/dsd-fme/blob/audio_work/dsd-fme3.png)

## Information

See the [examples](https://github.com/lwvmobile/dsd-fme/tree/audio_work/examples "examples") folder for information on [cloning and installing](https://github.com/lwvmobile/dsd-fme/blob/audio_work/examples/Install_Notes.md "cloning and installing"), [example usage](https://github.com/lwvmobile/dsd-fme/blob/audio_work/examples/Example_Usage.md "example usage"), and [trunking examples](https://github.com/lwvmobile/dsd-fme/blob/audio_work/examples/trunking.sh "trunking examples").

## License
Copyright (C) 2010 DSD Author
GPG Key ID: 0x3F1D7FD0 (74EF 430D F7F2 0A48 FCE6  F630 FAA2 635D 3F1D 7FD0)

    Permission to use, copy, modify, and/or distribute this software for any
    purpose with or without fee is hereby granted, provided that the above
    copyright notice and this permission notice appear in all copies.

    THE SOFTWARE IS PROVIDED "AS IS" AND ISC DISCLAIMS ALL WARRANTIES WITH
    REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
    AND FITNESS.  IN NO EVENT SHALL ISC BE LIABLE FOR ANY SPECIAL, DIRECT,
    INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
    LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
    OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
    PERFORMANCE OF THIS SOFTWARE.

## DMR SQLite Analysis - RC4 Vulnerability Research

### Overview

SQLite3 logging implementation for DMR encryption analysis. Captures H-MI/C-MI pairs and AMBE frames to analyze fixed MI vulnerability in RC4/AES implementations.

### Background

DMR encryption uses RC4 with initialization vectors (IVs) derived from:
- **H-MI (Header MI)**: Present in PI (Privacy Indicator) headers at the start of transmissions
- **C-MI (Continuation MI)**: Present in PI headers throughout the transmission

### The Fixed MI Vulnerability

Technical analysis based on information from doriboni and DualTachyon on RadioReference forums:

Fixed H-MI values confirmed in testing:
- 0x12345678
- 0x6C8AB637

The vulnerability creates a Vigenère cipher equivalent because the fixed H-MI combined with predictable C-MI progression results in reused keystreams. The patched firmware uses OS timer ticks to seed the PRNG for proper MI randomization.

**Vulnerable firmware versions:**
- FM100B_V1.2.0.6_20250311.bin (found in v3.14 update)
- FM100B_V1.2.0.12_20250422.bin (found in DM-UV4R+Upgrade+250426.zip, previously in v3.15)

**Fixed version:**
- FM100B_V1.2.0.13_20250430.bin (found in v3.16 archive)

The critical insight is that **all MI values are fixed** across transmissions, making the encryption equivalent to a Vigenère cipher with a key as long as the message - a vulnerability that has been known for centuries.

### The Fixed MI Problem

The vulnerability exists because:
- Header MI (H-MI) values remain fixed for each radio
- Continuation MI (C-MI) values follow predictable LFSR progression (32 clock cycles per output)
- Each superframe position correlates to specific C-MI values
- The LFSR pattern is independent of call duration - short and long transmissions show identical patterns

When H-MI is fixed, the keystream becomes predictable across transmissions.

### The Attack Methodology

The attack is carried out in parallel on each superframe:
1. Collect 30+ different transmissions
2. Attack superframe #1 of all 30 transmissions in parallel
3. Attack superframe #2 of all 30 transmissions in parallel
4. Continue for all subsequent superframes

Since silences are randomly distributed during speech: some transmissions have silence in superframe #1, others in #2, etc. By attacking all transmissions for each superframe, at least one reveals its keystream.

### Proven Results

Detailed analysis confirms:
- Fixed H-MI values across transmissions
- Predictable LFSR progression
- Keystream reuse enabling practical attacks

### Recent Findings

Our comprehensive analysis has revealed:

1. **The Motorola Backdoor**: The LFSR uses a non-primitive polynomial (x^32 + x^4 + x^2 + 1) with period 2^15-1 instead of 2^32-1
2. **Complete RC4 Break**: With only 32,767 possible MI values, a complete dictionary attack is trivial (6.2 MB)
3. **AMBE+2 Vocoder Analysis**: The "beep patterns" observed are vocoder artifacts, not actual audio content
4. **RC4 vs AES Clarification**: DMR Basic Privacy uses 40-bit RC4, not AES-128

### Security Implications

**DMR Basic Privacy provides NO SECURITY against knowledgeable attackers.**

The combination of:
- Fixed initialization vectors
- Non-primitive LFSR (backdoor)
- Predictable MI progression
- Vulnerable to known plaintext attacks

Makes this encryption system fundamentally broken by design.

### References

1. [RadioReference DMR Encryption Thread](https://forums.radioreference.com/threads/anytone-878-rc4-and-aes.399070/)
2. [DMR Protocol Reverse Engineering - Travis Goodspeed](https://github.com/travisgoodspeed/DMRDecode)
3. Academic papers confirming the LFSR backdoor (DEF CON 23, Black Hat Europe 2020)
4. Source code analysis: `src/dmr_pi.c` implementing the weak polynomial

---

*WARNING: The 131,076x security reduction through a non-primitive LFSR polynomial cannot be accidental. This is a deliberate backdoor. Users should assume ZERO privacy when using DMR Basic Privacy.*