#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <cuda_runtime.h>

// Constants
#define MAX_THREADS_PER_BLOCK 1024
#define MAX_BLOCKS 65535
#define KEYS_PER_THREAD 1000  // Each thread will test this many keys

// Byte swap function as it's not standard
__device__ __host__ static uint32_t byte_swap_32(uint32_t x) {
    return ((x & 0xFF) << 24) | 
           ((x & 0xFF00) << 8) | 
           ((x & 0xFF0000) >> 8) | 
           ((x & 0xFF000000) >> 24);
}

// Structure to pass data to GPU
typedef struct {
    unsigned char test_data[12];  // Target keystream data 
    uint32_t key_base_start;      // Starting key base
    uint32_t key_base_end;        // Ending key base
    uint8_t block;                // Block value to test (last byte)
    uint32_t found_key;           // Output: found key
    int key_found;                // Output: flag if key was found
} KeyFinderParams;

// Function to check if CUDA-capable device is available
extern "C" bool cuda_check_gpu_available() {
    int deviceCount = 0;
    cudaError_t error = cudaGetDeviceCount(&deviceCount);
    if (error != cudaSuccess || deviceCount == 0) {
        printf("CUDA: No CUDA-capable device found\n");
        return false;
    }
    
    // Get device properties
    cudaDeviceProp deviceProp;
    cudaGetDeviceProperties(&deviceProp, 0);
    printf("CUDA: Using %s, Compute Capability %d.%d\n", 
           deviceProp.name, deviceProp.major, deviceProp.minor);
    return true;
}

// CUDA kernel for RC4 key search
__global__ void brute_force_kernel(KeyFinderParams *params) {
    // Each thread gets a range of keys to test
    uint32_t thread_id = blockIdx.x * blockDim.x + threadIdx.x;
    uint32_t total_threads = gridDim.x * blockDim.x;
    
    // Calculate key range for this thread
    uint64_t key_range = ((uint64_t)params->key_base_end - (uint64_t)params->key_base_start) + 1;
    uint64_t keys_per_thread = (key_range + total_threads - 1) / total_threads;
    
    uint32_t my_start = params->key_base_start + thread_id * keys_per_thread;
    uint32_t my_end = my_start + keys_per_thread - 1;
    
    // Ensure we don't go beyond the end
    if (my_end > params->key_base_end) {
        my_end = params->key_base_end;
    }
    
    // If key already found or our range is invalid, exit
    if (params->key_found || my_start > my_end) {
        return;
    }
    
    // Test keys in our range
    for (uint32_t key_base = my_start; key_base <= my_end; key_base++) {
        // Check if key already found by another thread
        if (params->key_found) {
            return;
        }
        
        // Construct key with the block byte
        uint32_t key = (key_base << 8) | params->block;
        
        // Byte swap for DMR format
        uint32_t swapped_key = byte_swap_32(key);
        
        // Initialize RC4 S-box
        unsigned char rc4_sbox[256];
        for (int i = 0; i < 256; i++) {
            rc4_sbox[i] = i;
        }
        
        // RC4 KSA (Key Scheduling Algorithm)
        unsigned char j = 0;
        for (int i = 0; i < 256; i++) {
            j = (j + rc4_sbox[i] + ((unsigned char*)&swapped_key)[i % 4]) & 0xFF;
            unsigned char temp = rc4_sbox[i];
            rc4_sbox[i] = rc4_sbox[j];
            rc4_sbox[j] = temp;
        }
        
        // DMR Mode 1: First byte is S[1]
        if (rc4_sbox[1] != params->test_data[0]) {
            continue;  // First byte doesn't match, skip to next key
        }
        
        // Generate and check next bytes of keystream
        unsigned char rc4_i = 0, rc4_j = 0;
        bool valid = true;
        
        for (int i = 1; i < 12; i++) {
            unsigned char index_i = rc4_i + 1;
            rc4_i = index_i;
            unsigned char index_j = rc4_j + rc4_sbox[index_i];
            rc4_j = index_j;
            
            // Swap S[i] and S[j]
            unsigned char temp = rc4_sbox[index_i];
            rc4_sbox[index_i] = rc4_sbox[index_j];
            rc4_sbox[index_j] = temp;
            
            // Get keystream byte and compare
            unsigned char ks_byte = rc4_sbox[(unsigned char)(rc4_sbox[index_i] + rc4_sbox[index_j])];
            
            // Only check the first 8 bytes as minimum requirement (2 frames)
            if (i < 8 && ks_byte != params->test_data[i]) {
                valid = false;
                break;
            }
        }
        
        // If key matches, save it and set flag
        if (valid) {
            // Use atomicExch to safely update shared variables
            atomicExch(&params->found_key, key);
            atomicExch(&params->key_found, 1);
            return;  // Exit after finding a key
        }
    }
}

// Function is implemented in the extern "C" check_gpu_available() function above

// Function to convert hex string to binary
void cuda_convert_hex_to_binary(const char *src, unsigned char *dst, int len) {
    if (len <= 0) return;
    
    char hex_str[3] = {0};
    for (int i = 0; i < len/2; i++) {
        hex_str[0] = src[i*2];
        hex_str[1] = src[i*2 + 1];
        dst[i] = (unsigned char)strtol(hex_str, NULL, 16);
    }
}

// Function to run GPU search for a specific block
// Returns 0 if key found, 1 if not found
extern "C" int cuda_run_gpu_search(unsigned char *test_data, char *mi, int block, uint32_t *found_key) {
    // Set up the key finder parameters
    KeyFinderParams host_params;
    memcpy(host_params.test_data, test_data, 12);
    host_params.key_found = 0;
    host_params.found_key = 0;
    host_params.block = block;
    host_params.key_base_start = 0;
    host_params.key_base_end = 0xFFFFFF;  // 24 bits (3 bytes)
    
    // Allocate device memory for parameters
    KeyFinderParams *device_params;
    cudaError_t error = cudaMalloc((void**)&device_params, sizeof(KeyFinderParams));
    if (error != cudaSuccess) {
        printf("CUDA Error: Unable to allocate device memory: %s\n", cudaGetErrorString(error));
        return 1;
    }
    
    error = cudaMemcpy(device_params, &host_params, sizeof(KeyFinderParams), cudaMemcpyHostToDevice);
    if (error != cudaSuccess) {
        printf("CUDA Error: Unable to copy data to device: %s\n", cudaGetErrorString(error));
        cudaFree(device_params);
        return 1;
    }
    
    // Calculate grid and block dimensions
    int threadsPerBlock = 256;
    int blocksPerGrid = 1024;  // Maximum is typically 65535
    
    printf("Launching GPU search with %d blocks, %d threads per block for block %02X...\n", 
           blocksPerGrid, threadsPerBlock, block);
    
    // Launch kernel
    brute_force_kernel<<<blocksPerGrid, threadsPerBlock>>>(device_params);
    
    // Wait for completion
    cudaDeviceSynchronize();
    
    // Check for errors
    error = cudaGetLastError();
    if (error != cudaSuccess) {
        printf("CUDA Error: Kernel execution failed: %s\n", cudaGetErrorString(error));
        cudaFree(device_params);
        return 1;
    }
    
    // Copy back results
    error = cudaMemcpy(&host_params, device_params, sizeof(KeyFinderParams), cudaMemcpyDeviceToHost);
    if (error != cudaSuccess) {
        printf("CUDA Error: Unable to copy data from device: %s\n", cudaGetErrorString(error));
        cudaFree(device_params);
        return 1;
    }
    
    // Free device memory
    cudaFree(device_params);
    
    // Check if key was found
    if (host_params.key_found) {
        *found_key = host_params.found_key;
        
        // Print info about the found key
        printf("\n========================================\n");
        printf("KEY FOUND with GPU!\n");
        printf("Key: %08X\n", *found_key);
        printf("Key bytes: %02X %02X %02X %02X\n",
               (*found_key >> 24) & 0xFF,
               (*found_key >> 16) & 0xFF,
               (*found_key >> 8) & 0xFF,
               *found_key & 0xFF);
        printf("Block byte (last byte): %02X\n", *found_key & 0xFF);
        printf("MI: %s\n", mi);
        printf("========================================\n");
        
        // Write key to file
        FILE *key_file = fopen("/home/ubuntu/dsd-fme/arc4keyfinder/keys_found.txt", "a");
        if (key_file != NULL) {
            fprintf(key_file, "DMR Key found (GPU): %08X - ", *found_key);
            
            for (int i = 0; i < 4; i++) {
                fprintf(key_file, "%02X ", ((unsigned char*)found_key)[3-i]);
            }
            fprintf(key_file, "- MI: %s\n", mi);
            fclose(key_file);
        }
        
        return 0; // Key found
    }
    
    return 1; // No key found
}