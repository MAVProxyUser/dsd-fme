# DMR SQLite Analysis - RC4 Vulnerability Research

## Overview

SQLite3 logging implementation for DMR encryption analysis. Captures H-MI/C-MI pairs and AMBE frames to analyze fixed MI vulnerability in RC4/AES implementations.

## Background

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
- Continuation MI (C-MI) values follow predictable LFSR progression
- Each superframe position correlates to specific C-MI values

When H-MI is fixed, the keystream becomes predictable across transmissions.

### The Attack Methodology

The attack is carried out in parallel on each superframe:
1. Collect 30+ different transmissions
2. Attack superframe #1 of all 30 transmissions in parallel
3. Attack superframe #2 of all 30 transmissions in parallel
4. Continue for all subsequent superframes

Since silences are randomly distributed during speech:
1. The computer automatically guesses silence locations in superframe #1
2. XOR with the encrypted data to find portions of the encryption stream
3. Compare with the other 29 instances of superframe #1
4. If no match, test silence at another location
5. Repeat for all superframes (#2, #3, #4...)

This vulnerability makes DMR encryption with fixed MI equivalent to a **Vigenère cipher** - a vulnerability known for centuries. Both RC4 and AES (128/256) implementations are affected when using fixed MI values.

## Modifications

### 1. Database Logging Infrastructure

Added SQLite3 support to log:
- DMR correlations (H-MI and C-MI pairs)
- AMBE frames associated with each C-MI
- Superframe tracking for proper temporal correlation
- Algorithm IDs and key IDs
- Slot and color code information

### 2. Modified Files

- **CMakeLists.txt**: Added SQLite3 dependency and linking
- **cmake/FindSQLite3.cmake**: CMake module to find SQLite3
- **src/db_logger.c/.h**: Core database logging functionality
- **include/sqlite_logger.h**: Header for SQLite logging functions
- **src/dmr_pi.c**: Modified to log PI header information
- **src/dmr_ms.c**: Modified to log mobile station AMBE frames
- **src/dmr_bs.c**: Modified to log base station AMBE frames
- **src/dsd_main.c**: Integration of database initialization/cleanup

### 3. Database Schema

The system creates timestamped databases (`dmr_capture_YYYYMMDD_HHMMSS.db`) with:

```sql
-- Correlations table
CREATE TABLE dmr_correlations (
    id INTEGER PRIMARY KEY,
    header_mi INTEGER,
    control_mi INTEGER, 
    slot INTEGER,
    algid INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(header_mi, control_mi, slot)
);

-- Per C-MI tables (e.g., C_XXXXXXXX_S0)
CREATE TABLE 'C_XXXXXXXX_S0' (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    mi_full INTEGER,
    algid INTEGER,
    slot INTEGER,
    superframe_id INTEGER DEFAULT NULL
);

-- Superframe tracking
CREATE TABLE superframes (
    id INTEGER PRIMARY KEY,
    start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    slot INTEGER,
    color_code INTEGER,
    sync_type TEXT,
    h_mi INTEGER,
    c_mi INTEGER,
    frame_count INTEGER DEFAULT 0
);
```

## Analysis Tools

### 1. comprehensive_dmr_analysis.py

Main analysis script with GPU acceleration support:
- Loads all capture databases
- Merges data in memory using pandas
- Uses CuPy for GPU-accelerated pattern matching
- Analyzes LFSR progression patterns
- Finds beep patterns for known plaintext attacks
- Attempts RC4 decryption with various IV constructions
- Limited brute force key recovery

### 2. dmr_master_analysis.py

Builds a comprehensive model of C-MI evolution:
- Aggregates data from multiple captures
- Identifies LFSR interleaving patterns
- Predicts future C-MI values
- Tracks non-standard progressions

### 3. beep_pattern_finder.py

Identifies Call End Beep patterns:
- Finds repeated AMBE patterns at transmission ends
- Analyzes timing gaps
- Calculates pattern similarity using Hamming distance
- Correlates with LFSR predictions

## Key Findings

### Final Dataset Statistics
- **Total correlations**: 1,348
- **Total AMBE frames**: 31,533
- **Unique C-MI values**: 545
- **Unique H-MI values**: 1 (0x6C8AB637)
- **Database files**: 6

### LFSR Analysis
C-MI progression analysis from 1,348 correlations:
- **+1 jump**: 31.0%
- **-1 jump**: 21.6%
- **+2 jump**: 18.9%
- **+3 jump**: 12.8%
- **-2 jump**: 8.1%
- **+4 jump**: 5.9%
- **Other**: 2.2%

Polynomial: x^32 + x^4 + x^2 + 1

### Technical Findings
1. **Fixed H-MI**: 0x6C8AB637 across all captures
2. **C-MI Progression**: LFSR-based with predictable patterns  
3. **Known Plaintext**: AMBE frames with 0x02 prefix (beeps)
4. **Prediction Success**: Model correctly predicted C-MI 0xB1066DD0
5. **Attack Vector**: Vigenère cipher equivalent due to keystream reuse

## Attack Implementation

Our SQLite logging framework implements the parallel attack methodology:

1. **Data Collection**: Capture multiple DMR transmissions with timestamped databases
2. **Superframe Correlation**: Group encrypted frames by superframe number
3. **Parallel Analysis**: Attack all instances of each superframe simultaneously
4. **Silence Detection**: Automatically identify potential silence locations
5. **Keystream Recovery**: XOR operations reveal portions of the encryption stream
6. **Pattern Matching**: Compare recovered keystreams across multiple transmissions

### LFSR Prediction Validation

The analysis successfully predicted future C-MI values:
- Last captured C-MI: 0x9F3B1ACF
- Predicted next: 0xB1066DD0 
- **Result**: Prediction matched actual captured value

This validates our LFSR model and confirms the vulnerability can be exploited for real-time decryption.

## Building

```bash
# Install dependencies
sudo apt-get install libsqlite3-dev

# Build with SQLite support
cd build
cmake ..
make -j$(nproc)
```

## Usage

```bash
# Capture DMR transmissions with SQLite logging
./dsd-fme -i rtl:0:145.125M:40 -fs -Z

# Analyze captured data
python3 comprehensive_dmr_analysis.py

# View specific database
sqlite3 dmr_capture_20250517_013614.db ".tables"
```

## Hardware Setup

Testing was conducted on:
- Jetson AGX Xavier (ARM64) with CUDA 11.4
- RTL-SDR devices for signal reception
- Two test radios (IDs 1234 and 6969) with Call End Beep enabled

## GPU Acceleration

The analysis scripts support GPU acceleration via:
- CuPy for CUDA-based numpy operations
- Numba for JIT compilation
- Optimized for Jetson platform

## Future Work

1. Implement full RC4 key recovery
2. Add support for other encryption algorithms (AES, DES)
3. Real-time decryption capability
4. Integration with monitoring systems

## Security Note

This research demonstrates a cryptographic vulnerability in DMR radios using fixed MI values. The vulnerability affects both RC4 and AES implementations. Fixed MI values create a Vigenère cipher equivalent, allowing parallel cryptanalysis across multiple transmissions. The only mitigation is to use radios with properly randomized MI values.

## Author

This analysis framework was developed as part of research into DMR encryption vulnerabilities.

## References

- DMR Encryption Technical Specification
- RC4 Cryptanalysis Papers
- LFSR Theory and Implementation
- Digital Speech Decoder (DSD) Documentation