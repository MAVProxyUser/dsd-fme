#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

// This is a C++ wrapper that provides the C interface for CUDA functions

// Forward declarations of the actual CUDA functions
extern "C" {
    // These are implemented in arc4keyfinder_unified_cuda.cu
    extern bool cuda_check_gpu_available();
    extern int cuda_run_gpu_search(unsigned char *test_data, char *mi, int block, uint32_t *found_key);
}

// Wrapper functions that can be called from C
extern "C" {
    bool check_gpu_available() {
        return cuda_check_gpu_available();
    }
    
    int run_gpu_search(unsigned char *test_data, char *mi, int block, uint32_t *found_key) {
        return cuda_run_gpu_search(test_data, mi, block, found_key);
    }
}