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