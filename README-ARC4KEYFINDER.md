# DMR RC4-40 Key Finder

This repository contains multiple implementations of a key finder for the RC4-40 cipher used in DMR radios. 

## Implementations

### 1. CPU-only Implementation
- **Executable**: `arc4keyfinder_multicore`
- **Source**: `arc4keyfinder_multicore.c`
- **Features**: Multi-threaded implementation that uses all available CPU cores for parallel key search.

### 2. GPU-only Implementation
- **Executable**: `arc4keyfinder_cuda`
- **Source**: `arc4keyfinder_cuda.cu`
- **Features**: CUDA implementation that uses NVIDIA GPUs for parallel key search.

### 3. Unified Implementation (CPU+GPU)
- **Executable**: `arc4keyfinder_unified`
- **Source**: 
  - `arc4keyfinder_unified.c` - Main C implementation
  - `arc4keyfinder_unified_cuda.cu` - CUDA implementation
  - `arc4keyfinder_cuda_wrapper.cpp` - C++ to C interface wrapper
- **Features**: 
  - Automatically chooses the best processor (CPU or GPU) for each search block
  - Three-phase search strategy for optimal performance
  - Intelligent assignment of blocks to processors based on benchmark results
  - Falls back to CPU-only if no GPU is available
  - Same command-line interface as other implementations

## Building

### Build All Implementations
```bash
make -f Makefile.arc4keyfinder
```

### Build Specific Implementations
```bash
# CPU only
make -f Makefile.arc4keyfinder cpu

# GPU only
make -f Makefile.arc4keyfinder gpu

# Unified CPU+GPU
make -f Makefile.arc4keyfinder unified
```

### Clean Build
```bash
make -f Makefile.arc4keyfinder clean
```

## Usage

All implementations share the same command-line interface:

```bash
./arc4keyfinder_unified [options]
```

### Command-line Options

- `--mode/-m <mode>` - DMR mode (1-5, default: 1)
- `--frame/-f <hex>` - AMBE frame in hex format
- `--mi/-i <hex>` - DMR message indicator in hex
- `--start-block/-s <byte>` - Start block (0-255, default: 0)
- `--end-block/-e <byte>` - End block (0-255, default: 255)
- `--threads/-t <num>` - Number of threads (CPU, default: cores)
- `--debug/-d` - Enable debug output
- `--verbose/-v` - Enable verbose output
- `--test/-T` - Use test data
- `--key/-k <key>` - Known key for testing

### Example Usage

Search using test data:
```bash
./arc4keyfinder_unified --test --verbose
```

Search with real data:
```bash
./arc4keyfinder_unified --mode 1 --frame "00112233445566778899AABBCCDDEEFF" --mi "0011223344556677" --start-block 0 --end-block 255 --verbose
```

## Real World Example with Test Database

Here's an example of searching for a key in a test database:

```bash
#!/bin/bash
# Test data from test_db/test_dmr.db
FRAME1="7805077400004000"
FRAME2="ED2D4F7100006000"
FRAME3="596AF1C800008000"
MI="ABCDEF12"

# Run with a limited block range for quicker testing (0x78 is the first byte of the first frame)
./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" --mi "$MI" --start-block 0x78 --end-block 0x78 --verbose
```

Output:
```
CUDA: Using Xavier, Compute Capability 7.2
GPU acceleration available and enabled.
Selected DMR mode: 1
Using plaintext pattern: AA BB CC DD EE FF 11 22 33 44 55 66 
Processing frame 1: 7805077400004000
Extracted keystream segment 1: D2 BE CB A9 
Processing frame 2: ED2D4F7100006000
Extracted keystream segment 2: 03 D2 5E 53 
Processing frame 3: 596AF1C800008000
Extracted keystream segment 3: 6A 2E A4 AE 

Derived target keystream: D2 BE CB A9 03 D2 5E 53 6A 2E A4 AE 

[PHASE 1] Sequential search of common blocks
==========================================
Testing single block 0x78 directly
Trying GPU search for block 0x78...
Launching GPU search with 1024 blocks, 256 threads per block for block 78...

========================================
KEY FOUND with GPU!
Key: 12345678
Key bytes: 12 34 56 78
Block byte (last byte): 78
MI: ABCDEF12
========================================

==========================================
Search completed in 5.0 seconds
Total keys tested: 0

SUCCESS! KEY FOUND: 0x12345678
Key bytes: 12 34 56 78
Block byte (last byte): 78
```

For a more comprehensive search using all blocks (0x00-0xFF), simply omit the start-block and end-block parameters:

```bash
./arc4keyfinder_unified --mode 1 --frame "7805077400004000" --frame "ED2D4F7100006000" --frame "596AF1C800008000" --mi "ABCDEF12" --verbose
```

This will perform the full three-phase search using both CPU and GPU resources optimally.

## Search Strategy in Unified Implementation

The unified implementation uses a three-phase search approach:

1. **Phase 1**: Sequential search of common blocks with GPU
   - Tests blocks commonly found in DMR keys (0x78, 0x32, etc.)
   - Uses sequential search which is faster for these blocks
   
2. **Phase 2**: Parallel specialized block search
   - Assigns blocks to processors based on benchmark performance
   - GPU optimized blocks: 0x78, 0x32, 0xDD, 0xAA, 0x00, 0xFF, etc.
   - CPU optimized blocks: 0x56, 0x55, 0x34, 0xCC, 0x54, etc.
   
3. **Phase 3**: Deep search for remaining blocks
   - Comprehensive search of all remaining blocks
   - Distributes blocks between CPU and GPU

The implementation automatically handles processor assignment, making it the most flexible and user-friendly option.