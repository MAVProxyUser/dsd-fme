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
__device__ __host__ uint32_t byte_swap_32(uint32_t x) {
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

// Function to initialize CUDA and check for errors
bool init_cuda() {
    int device_count = 0;
    cudaError_t error = cudaGetDeviceCount(&device_count);
    
    if (error != cudaSuccess) {
        printf("CUDA Error: Unable to get device count: %s\n", cudaGetErrorString(error));
        return false;
    }
    
    if (device_count == 0) {
        printf("No CUDA devices found. Cannot use GPU acceleration.\n");
        return false;
    }
    
    // Print information about CUDA devices
    for (int i = 0; i < device_count; i++) {
        cudaDeviceProp prop;
        cudaGetDeviceProperties(&prop, i);
        printf("CUDA Device %d: %s\n", i, prop.name);
        printf("  Compute capability: %d.%d\n", prop.major, prop.minor);
        printf("  Max threads per block: %d\n", prop.maxThreadsPerBlock);
        printf("  Multiprocessors: %d\n", prop.multiProcessorCount);
    }
    
    // Set first device as active
    cudaSetDevice(0);
    return true;
}

// Function to convert hex string to binary
void convert_hex_to_binary(const char *src, unsigned char *dst, int len) {
    if (len <= 0) return;
    
    char hex_str[3] = {0};
    for (int i = 0; i < len/2; i++) {
        hex_str[0] = src[i*2];
        hex_str[1] = src[i*2 + 1];
        dst[i] = (unsigned char)strtol(hex_str, NULL, 16);
    }
}

// Function to print usage instructions
void print_usage(const char *progname) {
    printf("Usage: %s [options]\n", progname);
    printf("Options:\n");
    printf("    -m, --mode MODE          DMR mode (1-3, only 1 supported currently)\n");
    printf("    -f, --frame FRAME        AMBE frame (up to 3, hexadecimal)\n");
    printf("    -i, --mi MI              Message Indicator (MI) value (hexadecimal)\n");
    printf("    -s, --start-block BLOCK  Start block for brute force (hexadecimal, 00-FF)\n");
    printf("    -e, --end-block BLOCK    End block for brute force (hexadecimal, 00-FF)\n");
    printf("    -d, --debug              Enable debug output\n");
    printf("    -v, --verbose            Enable verbose output\n");
    printf("    -h, --help               Display this help and exit\n");
    printf("Example:\n");
    printf("    %s -m 1 -f 7805077400004000 -f ED2D4F7100006000 -f 596AF1C800008000 -i ABCDEF12 -s 78 -e 78\n", progname);
}

// Main function
int main(int argc, char **argv) {
    char mode = '1';  // Default to DMR Mode 1
    char ambe_frames[3][33] = {{0}};
    int num_frames = 0;
    char mi[9] = {0};
    int start_block = 0;
    int end_block = 0xFF;
    bool debug_mode = false;
    bool verbose_mode = false;
    
    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-m") == 0 || strcmp(argv[i], "--mode") == 0) {
            if (i + 1 < argc) {
                mode = argv[i+1][0];
                i++;
            }
        } else if (strcmp(argv[i], "-f") == 0 || strcmp(argv[i], "--frame") == 0) {
            if (i + 1 < argc && num_frames < 3) {
                strncpy(ambe_frames[num_frames], argv[i+1], 32);
                ambe_frames[num_frames][32] = '\0';
                num_frames++;
                i++;
            }
        } else if (strcmp(argv[i], "-i") == 0 || strcmp(argv[i], "--mi") == 0) {
            if (i + 1 < argc) {
                strncpy(mi, argv[i+1], 8);
                mi[8] = '\0';
                i++;
            }
        } else if (strcmp(argv[i], "-s") == 0 || strcmp(argv[i], "--start-block") == 0) {
            if (i + 1 < argc) {
                start_block = strtol(argv[i+1], NULL, 16);
                i++;
            }
        } else if (strcmp(argv[i], "-e") == 0 || strcmp(argv[i], "--end-block") == 0) {
            if (i + 1 < argc) {
                end_block = strtol(argv[i+1], NULL, 16);
                i++;
            }
        } else if (strcmp(argv[i], "-d") == 0 || strcmp(argv[i], "--debug") == 0) {
            debug_mode = true;
        } else if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--verbose") == 0) {
            verbose_mode = true;
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        }
    }
    
    // Validate mode
    if (mode != '1' && mode != '3') {
        printf("Error: Only modes 1 and 3 are supported\n");
        return 1;
    }
    
    // Validate number of frames
    if (num_frames < 3) {
        printf("Error: At least 3 frames are required\n");
        return 1;
    }
    
    printf("Selected DMR mode: %c\n", mode);
    
    // Initialize CUDA
    if (!init_cuda()) {
        printf("Failed to initialize CUDA. Exiting.\n");
        return 1;
    }
    
    // Process the AMBE frames to extract keystream
    unsigned char test_data[12] = {0};
    unsigned char plaintext[12] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66};
    
    printf("Using plaintext pattern: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", plaintext[i]);
    }
    printf("\n");
    
    // Process encrypted frames to extract keystream
    for (int i = 0; i < num_frames && i < 3; i++) {
        if (strlen(ambe_frames[i]) > 0) {
            printf("Processing frame %d: %s\n", i+1, ambe_frames[i]);
            
            unsigned char frame_data[16] = {0};
            convert_hex_to_binary(ambe_frames[i], frame_data, strlen(ambe_frames[i]));
            
            // XOR with plaintext to extract keystream (for DMR Mode 1)
            for (int j = 0; j < 4; j++) {
                test_data[i * 4 + j] = frame_data[j] ^ plaintext[i * 4 + j];
            }
            
            printf("Extracted keystream segment %d: ", i+1);
            for (int j = 0; j < 4; j++) {
                printf("%02X ", test_data[i * 4 + j]);
            }
            printf("\n");
        }
    }
    
    printf("\nDerived target keystream: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", test_data[i]);
    }
    printf("\n");
    
    // Set up the key finder parameters
    KeyFinderParams host_params;
    memcpy(host_params.test_data, test_data, 12);
    host_params.key_found = 0;
    host_params.found_key = 0;
    
    for (int block = start_block; block <= end_block; block++) {
        printf("\nTesting block: %02X\n", block);
        
        host_params.block = block;
        host_params.key_base_start = 0;
        host_params.key_base_end = 0xFFFFFF;  // 24 bits (3 bytes)
        
        // Allocate device memory for parameters
        KeyFinderParams *device_params;
        cudaMalloc((void**)&device_params, sizeof(KeyFinderParams));
        cudaMemcpy(device_params, &host_params, sizeof(KeyFinderParams), cudaMemcpyHostToDevice);
        
        // Calculate grid and block dimensions
        int threadsPerBlock = 256;
        int blocksPerGrid = 1024;  // Maximum is typically 65535
        
        printf("Launching GPU search with %d blocks, %d threads per block...\n", 
               blocksPerGrid, threadsPerBlock);
        
        // Launch kernel
        brute_force_kernel<<<blocksPerGrid, threadsPerBlock>>>(device_params);
        
        // Wait for completion
        cudaDeviceSynchronize();
        
        // Copy back results
        cudaMemcpy(&host_params, device_params, sizeof(KeyFinderParams), cudaMemcpyDeviceToHost);
        
        // Free device memory
        cudaFree(device_params);
        
        // Check if key was found
        if (host_params.key_found) {
            printf("\n========================================\n");
            printf("KEY FOUND!\n");
            printf("Key: %08X\n", host_params.found_key);
            printf("Key bytes: %02X %02X %02X %02X\n",
                   (host_params.found_key >> 24) & 0xFF,
                   (host_params.found_key >> 16) & 0xFF,
                   (host_params.found_key >> 8) & 0xFF,
                   host_params.found_key & 0xFF);
            printf("Block byte (last byte): %02X\n", host_params.found_key & 0xFF);
            printf("========================================\n");
            
            // Write key to file
            FILE *key_file = fopen("/home/ubuntu/dsd-fme/arc4keyfinder/keys_found.txt", "a");
            if (key_file != NULL) {
                if (mode == '1')
                    fprintf(key_file, "Motorola/Hytera DMR Mode 1 Key found: %08X - ", host_params.found_key);
                else if (mode == '3')
                    fprintf(key_file, "Anytone DMR Key found: %08X - ", host_params.found_key);
                
                for (int i = 0; i < 4; i++) {
                    fprintf(key_file, "%02X ", ((unsigned char*)&host_params.found_key)[3-i]);
                }
                fprintf(key_file, "\n");
                fclose(key_file);
            }
            
            break;  // Exit the loop if key is found
        } else {
            printf("No key found for block %02X\n", block);
        }
    }
    
    return 0;
}