# DMR Database Capture Requirements

## Overview
This document outlines the data capture requirements for DMR analysis using DSD-FME's SQLite database logging.

## Required Data Types

### 1. AMBE Frames
- Full hex representation of each vocoder frame
- Timestamp for each frame
- Association with superframe ID
- MI (Message Indicator) values

### 2. Encryption Data
- Header MI (H-MI) values for encryption initialization
- Control MI (C-MI) values for keystream generation
- Algorithm ID (ALGID) for encryption type
- Key ID for key management

### 3. Radio Metadata
- Source radio ID
- Target radio ID (or talkgroup)
- Manufacturer (Motorola, Hytera, Tait, etc.)
- Service options (priority, emergency, etc.)

### 4. Transmission Context
- Superframe identification
- Slot number
- Color code
- CRC status
- Timestamp

## Database Schema

The SQLite database uses the following table structure:

1. **superframes**: Master table for transmission sessions
2. **AMBE tables**: Named by MI context (H_XXXXXXXX_S0, C_XXXXXXXX_S0, U_00000000_S0)
3. **dmr_correlations**: Links H-MI and C-MI values
4. **dmr_metadata**: Additional metadata like talkgroups

## Capture Command

To capture DMR data with full logging:
```bash
./dsd-fme -i rtl:0:145.125M:40 -fs -Z
```

## Analysis Scripts

The captured databases can be analyzed using the Python scripts in this directory:
- `comprehensive_dmr_analysis.py`: Complete analysis of DMR security
- `end_to_end_test.py`: End-to-end encryption/decryption testing
- `radio_id_test.py`: Radio ID tracking and analysis