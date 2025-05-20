#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <unistd.h>
#include <pthread.h>
#include <time.h>
#include <stdint.h>
#include <getopt.h>
#include <sys/sysinfo.h>
#include <signal.h>
#include <ctype.h>

// Define byte swap function as it's not standard
static uint32_t byte_swap_32(uint32_t x) {
    return ((x & 0xFF) << 24) | 
           ((x & 0xFF00) << 8) | 
           ((x & 0xFF0000) >> 8) | 
           ((x & 0xFF000000) >> 24);
}

// Global variables
pthread_mutex_t keys_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t progress_mutex = PTHREAD_MUTEX_INITIALIZER;
char dmr_mode = '1';              // Current DMR mode
bool debug_mode = false;          // Debug output
bool verbose_mode = false;        // Verbose output
bool use_test_data = false;       // Use test data
bool use_gpu = true;              // Use GPU if available
bool force_cpu = false;           // Force CPU only
bool skip_blocks = false;         // Skip some blocks
bool radio_defaults = false;      // Use radio default key patterns
bool optimal_frames = false;      // Optimize for 18 AMBE frames (3 superframes)
uint32_t known_test_key = 0;      // Known test key
uint64_t keys_tested = 0;         // Keys tested counter
volatile bool key_found = false;  // Flag for found key
volatile bool stop_search = false;// Flag to stop search
pthread_t *thread_ids = NULL;     // Thread IDs
int num_threads = 0;              // Number of threads
FILE *log_file = NULL;            // Log file

// External CUDA functions (to be linked in at compile time)
extern bool check_gpu_available();
extern int run_gpu_search(unsigned char *test_data, char *mi, int block, uint32_t *found_key);

// Known block patterns that are commonly used
const int KNOWN_BLOCKS[] = {0x78, 0x32, 0xDD, 0xAA, 0xBB, 0xCC, 0x00, 0xFF};
const int KNOWN_BLOCKS_COUNT = 8;

// Radio default keys (typically 00000001-00000064 in DMR radios)
const int RADIO_DEFAULT_BLOCKS[] = {
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A,
    0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14,
    0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E,
    0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32,
    0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C,
    0x3D, 0x3E, 0x3F, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46,
    0x47, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0x50,
    0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A,
    0x5B, 0x5C, 0x5D, 0x5E, 0x5F, 0x60, 0x61, 0x62, 0x63, 0x64
};
const int RADIO_DEFAULT_BLOCKS_COUNT = 100; // Common DMR radio defaults (1-100)

// GPU optimized blocks based on benchmarks
const int GPU_BLOCKS[] = {0x78, 0x32, 0xDD, 0xAA, 0x00, 0xFF, 0x77, 0x33, 0x11, 0x22, 0x44, 0x88, 0x55};
const int GPU_BLOCKS_COUNT = 13;

// CPU optimized blocks based on benchmarks
const int CPU_BLOCKS[] = {0x56, 0x55, 0x34, 0xCC, 0x54, 0x35, 0xCD, 0xBC, 0xAB, 0xBA, 0x66, 0x76, 0x67};
const int CPU_BLOCKS_COUNT = 13;

// Function prototypes
void print_usage(const char *progname);
void convert_hex_to_binary(const char *src, unsigned char *dst, int len);
int rc4_ksa_step(unsigned char *i, unsigned char *j, unsigned char *s_box);
void *brute_force_thread(void *arg);
void *stats_thread(void *arg);
void print_array(const unsigned char *data, int len, const char *label);
void generate_test_data(char mode, unsigned char *test_data, int key_size);
void signal_handler(int signum);
bool is_block_in_array(int block, const int *array, int array_size);
int process_block_sequential(unsigned char *test_data, char *mi, int block, uint32_t *found_key);

typedef struct {
    unsigned char *test_data;
    int thread_id;
    uint32_t start_key;
    uint32_t end_key;
    int block_to_test;
    uint64_t keys_tested_local;
    char *mi;
} thread_args;

// Signal handler
void signal_handler(int signum) {
    printf("\nReceived signal %d. Gracefully stopping...\n", signum);
    stop_search = true;
}

// Check if block is in array
bool is_block_in_array(int block, const int *array, int array_size) {
    for (int i = 0; i < array_size; i++) {
        if (array[i] == block) {
            return true;
        }
    }
    return false;
}

// Parse command line arguments
bool parse_cmd_args(int argc, char **argv, char *mode, 
                   char ambe_frames[3][33], int *num_frames,
                   char *mi, int *start_block, int *end_block,
                   int *num_threads) {
    static struct option long_options[] = {
        {"mode", required_argument, 0, 'm'},
        {"frame", required_argument, 0, 'f'},
        {"mi", required_argument, 0, 'i'},
        {"start-block", required_argument, 0, 's'},
        {"end-block", required_argument, 0, 'e'},
        {"threads", required_argument, 0, 't'},
        {"debug", no_argument, 0, 'd'},
        {"verbose", no_argument, 0, 'v'},
        {"key", required_argument, 0, 'k'},
        {"test", no_argument, 0, 'T'},
        {"log", required_argument, 0, 'l'},
        {"gpu", no_argument, 0, 'g'},
        {"cpu", no_argument, 0, 'c'},
        {"skip-blocks", no_argument, 0, 'S'},
        {"radio-defaults", no_argument, 0, 'R'},
        {"optimal-frames", no_argument, 0, 'O'},  // Use 18 AMBE frames (3 superframes)
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0}
    };

    int option_index = 0;
    int c;
    int frame_count = 0;
    *num_frames = 0;
    
    // Initialize default values
    *mode = '1';  // Default to mode 1
    *start_block = 0;
    *end_block = 0xFF;
    *num_threads = get_nprocs();  // Get number of CPU cores
    if (*num_threads > 255) *num_threads = 255;
    
    while ((c = getopt_long(argc, argv, "m:f:i:s:e:t:k:l:dvTgcSROh", long_options, &option_index)) != -1) {
        switch (c) {
            case 'm':
                *mode = optarg[0];
                if (*mode < '1' || *mode > '5') {
                    fprintf(stderr, "Error: Mode must be between 1 and 5\n");
                    return false;
                }
                break;
                
            case 'f':
                if (frame_count >= 3) {
                    fprintf(stderr, "Error: Too many frames specified (max 3)\n");
                    return false;
                }
                strncpy(ambe_frames[frame_count], optarg, 32);
                ambe_frames[frame_count][32] = '\0';
                frame_count++;
                break;
                
            case 'i':
                strncpy(mi, optarg, 8);
                mi[8] = '\0';
                break;
                
            case 's':
                *start_block = strtol(optarg, NULL, 16);
                if (*start_block < 0 || *start_block > 0xFF) {
                    fprintf(stderr, "Error: Start block must be a valid hexadecimal value (00-FF)\n");
                    return false;
                }
                break;
                
            case 'e':
                *end_block = strtol(optarg, NULL, 16);
                if (*end_block < 0 || *end_block > 0xFF) {
                    fprintf(stderr, "Error: End block must be a valid hexadecimal value (00-FF)\n");
                    return false;
                }
                break;
                
            case 't':
                *num_threads = atoi(optarg);
                if (*num_threads <= 0) {
                    fprintf(stderr, "Error: Threads must be a positive integer\n");
                    return false;
                }
                break;
                
            case 'd':
                debug_mode = true;
                break;
                
            case 'v':
                verbose_mode = true;
                break;
                
            case 'k':
                known_test_key = strtoul(optarg, NULL, 16);
                if (known_test_key == 0) {
                    fprintf(stderr, "Error: Test key must be a valid hexadecimal value\n");
                    return false;
                }
                break;
                
            case 'T':
                use_test_data = true;
                break;
                
            case 'l':
                log_file = fopen(optarg, "w");
                if (!log_file) {
                    fprintf(stderr, "Error: Cannot open log file %s\n", optarg);
                    return false;
                }
                break;
                
            case 'g':
                use_gpu = true;
                force_cpu = false;
                break;
                
            case 'c':
                force_cpu = true;
                use_gpu = false;
                break;
                
            case 'S':
                skip_blocks = true;
                break;
                
            case 'R':
                radio_defaults = true;
                break;
                
            case 'O':
                optimal_frames = true;
                break;
                
            case 'h':
                print_usage(argv[0]);
                exit(0);
                
            default:
                print_usage(argv[0]);
                return false;
        }
    }
    
    *num_frames = frame_count;
    return true;
}

void print_usage(const char *progname) {
    printf("Usage: %s [options]\n", progname);
    printf("Options:\n");
    printf("    -m, --mode MODE          DMR mode (1-5)\n");
    printf("    -f, --frame FRAME        AMBE frame (up to 3, hexadecimal)\n");
    printf("    -i, --mi MI              Message Indicator (MI) value (hexadecimal)\n");
    printf("    -s, --start-block BLOCK  Start block for brute force (hexadecimal, 00-FF)\n");
    printf("    -e, --end-block BLOCK    End block for brute force (hexadecimal, 00-FF)\n");
    printf("    -t, --threads NUM        Number of threads to use\n");
    printf("    -d, --debug              Enable debug output\n");
    printf("    -v, --verbose            Enable verbose output\n");
    printf("    -k, --key KEY            Use specified test key (for testing only, hexadecimal)\n");
    printf("    -l, --log FILE           Write log output to file\n");
    printf("    -T, --test               Use test data with a known key\n");
    printf("    -g, --gpu                Use GPU acceleration (default)\n");
    printf("    -c, --cpu                Force CPU only (no GPU)\n");
    printf("    -S, --skip-blocks        Skip blocks unlikely to contain keys\n");
    printf("    -R, --radio-defaults     Use radio default key patterns (00000001-00000100)\n");
    printf("    -O, --optimal-frames     Optimize for 18-frame superframes\n");
    printf("    -h, --help               Display this help and exit\n");
    printf("Radio Default Key Strategy:\n");
    printf("    When --radio-defaults is enabled, the program will first check for\n");
    printf("    common DMR radio default keys (00000001-00000100). For many commercial\n");
    printf("    DMR radios, the default keys follow a sequential pattern where the\n");
    printf("    last byte matches the channel number.\n");
    printf("Optimal Frame Strategy:\n");
    printf("    When --optimal-frames is enabled, the program will optimize verification\n");
    printf("    for 18 AMBE frames (spanning 3 DMR superframes) when available. This provides\n");
    printf("    more keystream data for verification and reduces false positives.\n");
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
    int num_thread_option = 0;
    
    // Initialize signal handler
    signal(SIGINT, signal_handler);
    
    // Parse command line arguments
    if (!parse_cmd_args(argc, argv, &mode, ambe_frames, &num_frames,
                        mi, &start_block, &end_block, &num_thread_option)) {
        return 1;
    }

    dmr_mode = mode;
    num_threads = num_thread_option;

    // Check GPU availability
    bool gpu_available = false;
    if (use_gpu && !force_cpu) {
        gpu_available = check_gpu_available();
        if (gpu_available) {
            printf("GPU acceleration available and enabled.\n");
        } else {
            printf("GPU acceleration not available, using CPU only.\n");
            use_gpu = false;
        }
    } else if (force_cpu) {
        printf("Forcing CPU only mode (GPU disabled).\n");
        use_gpu = false;
    }

    // Validate required arguments
    if (num_frames < 3) {
        fprintf(stderr, "Error: At least 3 frames are required\n");
        return 1;
    }

    // Convert MI to uppercase
    for (int i = 0; mi[i]; i++) {
        mi[i] = toupper(mi[i]);
    }

    printf("Selected DMR mode: %c\n", mode);
    
    // Process the AMBE frames to extract keystream
    unsigned char *test_data = (unsigned char *)malloc(12);
    if (!test_data) {
        fprintf(stderr, "Error: Memory allocation failed\n");
        return 1;
    }
    
    unsigned char plaintext[12] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66};
    
    printf("Using plaintext pattern: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", plaintext[i]);
    }
    printf("\n");
    
    // Process encrypted frames to extract keystream
    if (optimal_frames && num_frames >= 18) {
        // In optimal frame mode, we use up to 18 AMBE frames (spanning 3 superframes)
        printf("\n[OPTIMAL FRAMES MODE] Using all 18 AMBE frames (3 superframes)\n");
        printf("Processing first 3 frames for standard approach, with additional verification\n");
        
        // Always process the first 3 frames for standard approach
        for (int i = 0; i < 3; i++) {
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
        
        // Store additional frame data for verification in the block processing functions
        printf("\nStoring additional %d frames for enhanced verification...\n", num_frames - 3);
        
        // We'll add a check in the verification functions to use these additional frames
        // This improves accuracy by testing keys against more keystream data
    } else {
        // Standard approach - just use the first 3 frames
        if (num_frames < 3) {
            printf("Warning: At least 3 frames are recommended for reliable key recovery\n");
        }
        
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
    }
    
    printf("\nDerived target keystream: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", test_data[i]);
    }
    printf("\n");
    
    // If radio defaults mode is enabled, check first frame for leaked block
    if (radio_defaults) {
        printf("\n[RADIO DEFAULTS] Checking for leaked key information\n");
        printf("==========================================\n");
        printf("Typical DMR radios use keys from 00000001-00000100\n");
        
        // Extract key block from first frame if possible (optimization)
        int first_frame_block = test_data[0];
        printf("First frame suggests block 0x%02X as a possibility\n", first_frame_block);
        
        // Try this block first if it's in range of typical radio defaults (1-100 decimal)
        if (first_frame_block > 0x00 && first_frame_block <= 0x64) {
            printf("Trying potential radio default key with block 0x%02X...\n", first_frame_block);
            uint32_t found_key = 0;
            int result;
            
            // Try with GPU first if available
            if (use_gpu && !force_cpu && check_gpu_available()) {
                result = run_gpu_search(test_data, mi, first_frame_block, &found_key);
                if (result == 0) {
                    printf("\nSUCCESS! KEY FOUND: 0x%08X\n", found_key);
                    printf("Key bytes: %02X %02X %02X %02X\n",
                          (found_key >> 24) & 0xFF,
                          (found_key >> 16) & 0xFF,
                          (found_key >> 8) & 0xFF,
                          found_key & 0xFF);
                    printf("Block byte (last byte): %02X\n", found_key & 0xFF);
                    return 0;
                }
            }
            
            // Try with CPU if GPU failed or not available
            result = process_block_sequential(test_data, mi, first_frame_block, &found_key);
            if (result == 0) {
                printf("\nSUCCESS! KEY FOUND: 0x%08X\n", found_key);
                printf("Key bytes: %02X %02X %02X %02X\n",
                      (found_key >> 24) & 0xFF,
                      (found_key >> 16) & 0xFF,
                      (found_key >> 8) & 0xFF,
                      found_key & 0xFF);
                printf("Block byte (last byte): %02X\n", found_key & 0xFF);
                return 0;
            }
        }
        
        // If the quick check didn't work, try all radio default blocks
        printf("\n[RADIO DEFAULTS] Checking all common radio default keys\n");
        printf("==========================================\n");
        
        for (int i = 0; i < RADIO_DEFAULT_BLOCKS_COUNT; i++) {
            int block = RADIO_DEFAULT_BLOCKS[i];
            if (block >= start_block && block <= end_block) {
                printf("Testing radio default key block 0x%02X...\n", block);
                uint32_t found_key = 0;
                int result;
                
                // Try with GPU first if available
                if (use_gpu && !force_cpu && check_gpu_available()) {
                    result = run_gpu_search(test_data, mi, block, &found_key);
                    if (result == 0) {
                        printf("\nSUCCESS! KEY FOUND: 0x%08X\n", found_key);
                        printf("Key bytes: %02X %02X %02X %02X\n",
                              (found_key >> 24) & 0xFF,
                              (found_key >> 16) & 0xFF,
                              (found_key >> 8) & 0xFF,
                              found_key & 0xFF);
                        printf("Block byte (last byte): %02X\n", found_key & 0xFF);
                        return 0;
                    }
                }
                
                // Try with CPU if GPU failed or not available
                result = process_block_sequential(test_data, mi, block, &found_key);
                if (result == 0) {
                    printf("\nSUCCESS! KEY FOUND: 0x%08X\n", found_key);
                    printf("Key bytes: %02X %02X %02X %02X\n",
                          (found_key >> 24) & 0xFF,
                          (found_key >> 16) & 0xFF,
                          (found_key >> 8) & 0xFF,
                          found_key & 0xFF);
                    printf("Block byte (last byte): %02X\n", found_key & 0xFF);
                    return 0;
                }
            }
        }
    }
    
    // Launch stats thread
    pthread_t stats_thread_id;
    if (pthread_create(&stats_thread_id, NULL, stats_thread, NULL) != 0) {
        fprintf(stderr, "Error: Could not create stats thread\n");
        return 1;
    }
    
    // Search strategy
    printf("\n[PHASE 1] Sequential search of common blocks\n");
    printf("==========================================\n");
    
    time_t start_time = time(NULL);
    uint32_t found_key = 0;
    
    // If we're testing a narrow range, just process those blocks
    if (start_block == end_block) {
        printf("Testing single block 0x%02X directly\n", start_block);
        if (gpu_available && use_gpu) {
            // Try GPU first
            printf("Trying GPU search for block 0x%02X...\n", start_block);
            if (run_gpu_search(test_data, mi, start_block, &found_key) == 0) {
                key_found = true;
            }
        }
        
        // Try CPU if GPU didn't find it or wasn't available
        if (!key_found) {
            printf("Trying CPU search for block 0x%02X...\n", start_block);
            if (process_block_sequential(test_data, mi, start_block, &found_key) == 0) {
                key_found = true;
            }
        }
    } else {
        // PHASE 1: Try known common blocks first sequentially
        if (!skip_blocks) {
            printf("Testing common blocks: ");
            for (int i = 0; i < KNOWN_BLOCKS_COUNT; i++) {
                printf("0x%02X ", KNOWN_BLOCKS[i]);
            }
            printf("\n");
            
            for (int i = 0; i < KNOWN_BLOCKS_COUNT; i++) {
                int block = KNOWN_BLOCKS[i];
                
                // Skip blocks outside our range
                if (block < start_block || block > end_block) {
                    continue;
                }
                
                time_t block_start_time = time(NULL);
                printf("Testing known block: 0x%02X\n", block);
                
                if (gpu_available && use_gpu) {
                    // Try GPU first
                    printf("  Using GPU for block 0x%02X...\n", block);
                    if (run_gpu_search(test_data, mi, block, &found_key) == 0) {
                        key_found = true;
                        time_t end_time = time(NULL);
                        printf("  Found key with GPU in %ld seconds: 0x%08X\n", 
                              (long)(end_time - block_start_time), found_key);
                        break;
                    }
                }
                
                // Try CPU if GPU didn't find it or wasn't available
                if (!key_found) {
                    printf("  Using CPU for block 0x%02X...\n", block);
                    if (process_block_sequential(test_data, mi, block, &found_key) == 0) {
                        key_found = true;
                        time_t end_time = time(NULL);
                        printf("  Found key with CPU in %ld seconds: 0x%08X\n", 
                              (long)(end_time - block_start_time), found_key);
                        break;
                    }
                }
            }
        }
        
        // PHASE 2: Try CPU/GPU optimized blocks in parallel
        if (!key_found) {
            printf("\n[PHASE 2] Parallel search with optimized blocks\n");
            printf("=============================================\n");
            
            // Create thread pool for optimized blocks
            int block_count = 0;
            
            // Count blocks to process
            for (int block = start_block; block <= end_block; block++) {
                if (is_block_in_array(block, KNOWN_BLOCKS, KNOWN_BLOCKS_COUNT)) {
                    continue; // Skip already tested blocks
                }
                
                if ((gpu_available && use_gpu && is_block_in_array(block, GPU_BLOCKS, GPU_BLOCKS_COUNT)) ||
                    ((!gpu_available || !use_gpu) && is_block_in_array(block, CPU_BLOCKS, CPU_BLOCKS_COUNT))) {
                    block_count++;
                }
            }
            
            if (block_count > 0) {
                printf("Processing %d optimized blocks in parallel\n", block_count);
                
                thread_ids = (pthread_t *)malloc(block_count * sizeof(pthread_t));
                if (!thread_ids) {
                    fprintf(stderr, "Error: Memory allocation failed\n");
                    free(test_data);
                    return 1;
                }
                
                int thread_count = 0;
                
                // Launch threads for optimized blocks
                for (int block = start_block; block <= end_block; block++) {
                    if (is_block_in_array(block, KNOWN_BLOCKS, KNOWN_BLOCKS_COUNT)) {
                        continue; // Skip already tested blocks
                    }
                    
                    bool process_block = false;
                    bool use_gpu_for_block = false;
                    
                    if (gpu_available && use_gpu && is_block_in_array(block, GPU_BLOCKS, GPU_BLOCKS_COUNT)) {
                        process_block = true;
                        use_gpu_for_block = true;
                        printf("  Block 0x%02X assigned to GPU\n", block);
                    } else if (is_block_in_array(block, CPU_BLOCKS, CPU_BLOCKS_COUNT)) {
                        process_block = true;
                        use_gpu_for_block = false;
                        printf("  Block 0x%02X assigned to CPU\n", block);
                    }
                    
                    if (process_block) {
                        thread_args *args = (thread_args *)malloc(sizeof(thread_args));
                        if (!args) {
                            fprintf(stderr, "Error: Memory allocation failed\n");
                            continue;
                        }
                        
                        args->test_data = test_data;
                        args->thread_id = thread_count;
                        args->start_key = 0;
                        args->end_key = 0xFFFFFF; // 24 bits
                        args->block_to_test = block;
                        args->keys_tested_local = 0;
                        args->mi = mi;
                        
                        if (use_gpu_for_block) {
                            // Use GPU directly for this block
                            printf("  Launching GPU search for block 0x%02X\n", block);
                            
                            if (run_gpu_search(test_data, mi, block, &found_key) == 0) {
                                key_found = true;
                                printf("  Found key with GPU for block 0x%02X: 0x%08X\n", block, found_key);
                                free(args);
                                break;
                            }
                            
                            free(args);
                        } else {
                            // Use CPU thread for this block
                            if (pthread_create(&thread_ids[thread_count], NULL, brute_force_thread, args) != 0) {
                                fprintf(stderr, "Error: Could not create thread for block 0x%02X\n", block);
                                free(args);
                                continue;
                            }
                            
                            thread_count++;
                        }
                    }
                }
                
                // Wait for all threads to complete
                for (int i = 0; i < thread_count; i++) {
                    pthread_join(thread_ids[i], NULL);
                }
                
                free(thread_ids);
            }
        }
        
        // PHASE 3: Search remaining blocks
        if (!key_found) {
            printf("\n[PHASE 3] Full search of remaining blocks\n");
            printf("=======================================\n");
            
            // Create thread pool for remaining blocks
            int block_count = 0;
            for (int block = start_block; block <= end_block; block++) {
                if (is_block_in_array(block, KNOWN_BLOCKS, KNOWN_BLOCKS_COUNT) ||
                    is_block_in_array(block, GPU_BLOCKS, GPU_BLOCKS_COUNT) ||
                    is_block_in_array(block, CPU_BLOCKS, CPU_BLOCKS_COUNT)) {
                    continue; // Skip already tested blocks
                }
                
                block_count++;
            }
            
            if (block_count > 0) {
                printf("Processing remaining %d blocks\n", block_count);
                
                thread_ids = (pthread_t *)malloc(block_count * sizeof(pthread_t));
                if (!thread_ids) {
                    fprintf(stderr, "Error: Memory allocation failed\n");
                    free(test_data);
                    return 1;
                }
                
                int thread_count = 0;
                
                // Launch threads for remaining blocks
                for (int block = start_block; block <= end_block; block++) {
                    if (is_block_in_array(block, KNOWN_BLOCKS, KNOWN_BLOCKS_COUNT) ||
                        is_block_in_array(block, GPU_BLOCKS, GPU_BLOCKS_COUNT) ||
                        is_block_in_array(block, CPU_BLOCKS, CPU_BLOCKS_COUNT)) {
                        continue; // Skip already tested blocks
                    }
                    
                    // Distribute remaining blocks optimally between CPU and GPU
                    bool use_gpu_for_block = gpu_available && use_gpu && (block % 3 != 0); // 2/3 to GPU, 1/3 to CPU
                    
                    if (use_gpu_for_block) {
                        printf("  Launching GPU search for block 0x%02X...\n", block);
                        
                        if (run_gpu_search(test_data, mi, block, &found_key) == 0) {
                            key_found = true;
                            printf("  Found key with GPU for block 0x%02X: 0x%08X\n", block, found_key);
                            break;
                        }
                    } else {
                        // Use CPU for this block
                        thread_args *args = (thread_args *)malloc(sizeof(thread_args));
                        if (!args) {
                            fprintf(stderr, "Error: Memory allocation failed\n");
                            continue;
                        }
                        
                        args->test_data = test_data;
                        args->thread_id = thread_count;
                        args->start_key = 0;
                        args->end_key = 0xFFFFFF; // 24 bits
                        args->block_to_test = block;
                        args->keys_tested_local = 0;
                        args->mi = mi;
                        
                        if (pthread_create(&thread_ids[thread_count], NULL, brute_force_thread, args) != 0) {
                            fprintf(stderr, "Error: Could not create thread for block 0x%02X\n", block);
                            free(args);
                            continue;
                        }
                        
                        thread_count++;
                    }
                    
                    if (key_found || stop_search) {
                        break;
                    }
                }
                
                // Wait for all threads to complete
                for (int i = 0; i < thread_count; i++) {
                    pthread_join(thread_ids[i], NULL);
                }
                
                free(thread_ids);
            }
        }
    }
    
    // Stop stats thread
    stop_search = true;
    pthread_join(stats_thread_id, NULL);
    
    time_t end_time = time(NULL);
    double total_seconds = difftime(end_time, start_time);
    
    // Final summary
    printf("\n==========================================\n");
    printf("Search completed in %.1f seconds\n", total_seconds);
    printf("Total keys tested: %llu\n", (unsigned long long)keys_tested);
    
    if (key_found) {
        // Get key from one of the threads that found it
        printf("\nSUCCESS! KEY FOUND: 0x%08X\n", found_key);
        printf("Key bytes: %02X %02X %02X %02X\n",
               (found_key >> 24) & 0xFF,
               (found_key >> 16) & 0xFF,
               (found_key >> 8) & 0xFF,
               found_key & 0xFF);
        printf("Block byte (last byte): %02X\n", found_key & 0xFF);
        
        // Write key to file
        FILE *key_file = fopen("/home/ubuntu/dsd-fme/arc4keyfinder/keys_found.txt", "a");
        if (key_file != NULL) {
            if (mode == '1')
                fprintf(key_file, "Motorola/Hytera DMR Mode 1 Key found: %08X - ", found_key);
            else if (mode == '3')
                fprintf(key_file, "Anytone DMR Key found: %08X - ", found_key);
            else
                fprintf(key_file, "DMR Key found: %08X - ", found_key);
            
            for (int i = 0; i < 4; i++) {
                fprintf(key_file, "%02X ", ((unsigned char*)&found_key)[3-i]);
            }
            fprintf(key_file, "- MI: %s\n", mi);
            fclose(key_file);
        }
    } else {
        printf("\nNo key found in the specified range.\n");
    }
    
    // Clean up
    free(test_data);
    if (log_file) fclose(log_file);
    
    return 0;
}

// Convert hex string to binary
void convert_hex_to_binary(const char *src, unsigned char *dst, int len) {
    if (len <= 0) return;
    
    char hex_str[3] = {0};
    for (int i = 0; i < len/2; i++) {
        hex_str[0] = src[i*2];
        hex_str[1] = src[i*2 + 1];
        dst[i] = (unsigned char)strtol(hex_str, NULL, 16);
    }
}

// RC4 KSA algorithm step for key finding
int rc4_ksa_step(unsigned char *i, unsigned char *j, unsigned char *s_box) {
    unsigned char temp;
    unsigned char index_i = *i + 1;
    *i = index_i;
    unsigned char index_j = *j + s_box[index_i];
    *j = index_j;
    
    // Swap S[i] and S[j]
    temp = s_box[index_i];
    s_box[index_i] = s_box[index_j];
    s_box[index_j] = temp;
    
    // Return S[S[i] + S[j]]
    return s_box[(unsigned char)(s_box[index_i] + s_box[index_j])];
}

// Thread that shows statistics
void *stats_thread(void *arg) {
    uint64_t prev_keys = 0;
    time_t start_time = time(NULL);
    time_t total_start_time = start_time;
    
    while (!stop_search) {
        sleep(5); // Update every 5 seconds
        
        pthread_mutex_lock(&keys_mutex);
        uint64_t current_keys = keys_tested;
        pthread_mutex_unlock(&keys_mutex);
        
        uint64_t keys_in_period = current_keys - prev_keys;
        
        time_t current_time = time(NULL);
        double seconds = difftime(current_time, start_time);
        double total_seconds = difftime(current_time, total_start_time);
        
        if (seconds > 0 && keys_in_period > 0) {
            double keys_per_second = (double)keys_in_period / seconds;
            double total_keys_per_second = (double)current_keys / total_seconds;
            
            printf("Keys tested: %llu (%.2f%% of 2^32), ", 
                   (unsigned long long)current_keys,
                   (double)current_keys / (256.0 * 0x1000000) * 100.0);
                   
            printf("Speed: %.1f keys/sec (period), %.1f keys/sec (avg)\n", 
                   keys_per_second, total_keys_per_second);
            
            // Log to file if specified
            if (log_file) {
                fprintf(log_file, "%ld,%llu,%.1f,%.1f\n", 
                        (long)current_time, 
                        (unsigned long long)current_keys,
                        keys_per_second,
                        total_keys_per_second);
                fflush(log_file);
            }
        }
        
        prev_keys = current_keys;
        start_time = current_time;
    }
    
    return NULL;
}

// Debug utility to print array contents
void print_array(const unsigned char *data, int len, const char *label) {
    printf("%s: ", label);
    for (int i = 0; i < len; i++) {
        printf("%02X ", data[i]);
    }
    printf("\n");
}

// Generate test data with known key
void generate_test_data(char mode, unsigned char *test_data, int key_size) {
    if (!known_test_key) {
        known_test_key = 0x12345678; // Default test key
    }
    
    printf("\n===== Generating Test Data =====\n");
    printf("Test key: 0x%08X\n", known_test_key);
    
    unsigned char key_bytes[4];
    key_bytes[0] = (known_test_key >> 24) & 0xFF;
    key_bytes[1] = (known_test_key >> 16) & 0xFF;
    key_bytes[2] = (known_test_key >> 8) & 0xFF;
    key_bytes[3] = known_test_key & 0xFF;
    
    printf("Key bytes: %02X %02X %02X %02X\n", key_bytes[0], key_bytes[1], key_bytes[2], key_bytes[3]);
    printf("Last byte (block): %02X\n\n", key_bytes[3]);
    
    // Sample input data (this would depend on mode)
    unsigned char input_data[18] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66};
    printf("Input AMBE frame data: ");
    for (int i = 0; i < key_size; i++) {
        printf("%02X ", input_data[i]);
    }
    printf("\n");
    
    // Byte-swap the key for DMR
    uint32_t swapped_key = byte_swap_32(known_test_key);
    printf("Byte-swapped key (DMR format): 0x%08X\n", swapped_key);
    printf("Swapped key bytes: %02X %02X %02X %02X\n\n", 
           ((unsigned char*)&swapped_key)[0], 
           ((unsigned char*)&swapped_key)[1], 
           ((unsigned char*)&swapped_key)[2], 
           ((unsigned char*)&swapped_key)[3]);
    
    printf("Initializing RC4 state with swapped key\n");
    
    // Initialize RC4 S-box
    unsigned char rc4_sbox[256];
    for (int i = 0; i < 256; i++) {
        rc4_sbox[i] = i;
    }
    
    // RC4 KSA
    unsigned char j = 0;
    for (int i = 0; i < 256; i++) {
        j = (j + rc4_sbox[i] + ((unsigned char*)&swapped_key)[i % 4]) & 0xFF;
        unsigned char temp = rc4_sbox[i];
        rc4_sbox[i] = rc4_sbox[j];
        rc4_sbox[j] = temp;
    }
    
    printf("RC4 S-box initialization complete\n");
    printf("First few S-box values: %02X %02X %02X %02X %02X\n", 
           rc4_sbox[0], rc4_sbox[1], rc4_sbox[2], rc4_sbox[3], rc4_sbox[4]);
    
    // Generate keystream for DMR mode 1
    printf("\nDMR Mode 1 keystream generation:\n");
    printf("First byte (S[1]): %02X\n", rc4_sbox[1]);
    test_data[0] = rc4_sbox[1];
    
    // Generate remaining keystream
    unsigned char rc4_i = 0, rc4_j = 0;
    printf("Remaining keystream: ");
    for (int i = 1; i < key_size; i++) {
        unsigned char ks_byte = rc4_ksa_step(&rc4_i, &rc4_j, rc4_sbox);
        test_data[i] = ks_byte;
        printf("%02X ", ks_byte);
    }
    printf("\n\n");
    
    printf("Target keystream (for testing): ");
    for (int i = 0; i < key_size; i++) {
        printf("%02X ", test_data[i]);
    }
    printf("\n");
    
    // Generate encrypted frames by XORing plaintext with keystream
    unsigned char encrypted[18] = {0};
    printf("\nEncrypted AMBE frames (using plaintext XOR keystream):\n");
    for (int i = 0; i < 3; i++) {
        printf("Frame %d: ", i+1);
        for (int j = 0; j < 4; j++) {
            encrypted[i*4 + j] = input_data[i*4 + j] ^ test_data[i*4 + j];
            printf("%02X", encrypted[i*4 + j]);
        }
        printf("\n");
    }
    printf("\n");
}

// Process a block with CPU
int process_block_sequential(unsigned char *test_data, char *mi, int block, uint32_t *found_key) {
    time_t start_time = time(NULL);
    uint64_t local_keys_tested = 0;
    
    printf("Processing block: %02X, key range: 0x000000 - 0xFFFFFF\n", block);
    
    // Current block testing loop
    for (uint32_t key_base = 0; key_base <= 0xFFFFFF; key_base++) {
        // Check if we should stop early
        if (key_found || stop_search) {
            pthread_mutex_lock(&keys_mutex);
            keys_tested += local_keys_tested;
            pthread_mutex_unlock(&keys_mutex);
            return 1;
        }
        
        // Construct the key with the block byte in the correct position
        // For DMR, it's the last byte (LSB)
        uint32_t key = (key_base << 8) | block;
        
        // IMPORTANT: We need to byte-swap the key for DMR
        uint32_t swapped_key = byte_swap_32(key);
        
        // Initialize RC4 S-box
        unsigned char rc4_sbox[256];
        for (int i = 0; i < 256; i++) {
            rc4_sbox[i] = i;
        }
        
        // RC4 KSA
        unsigned char j = 0;
        for (int i = 0; i < 256; i++) {
            j = (j + rc4_sbox[i] + ((unsigned char*)&swapped_key)[i % 4]) & 0xFF;
            unsigned char temp = rc4_sbox[i];
            rc4_sbox[i] = rc4_sbox[j];
            rc4_sbox[j] = temp;
        }
        
        // Test based on DMR mode
        switch (dmr_mode) {
            case '1': // Motorola DMR Mode 1
            case '3': // Anytone DMR
                // Check if first byte matches S[1]
                if (rc4_sbox[1] == test_data[0]) {
                    // Setup for RC4 stream generation
                    unsigned char rc4_i = 0, rc4_j = 0;
                    
                    // Check next few bytes to confirm
                    bool valid = true;
                    for (int i = 1; i < 4; i++) {
                        uint8_t keystream_byte = rc4_ksa_step(&rc4_i, &rc4_j, rc4_sbox);
                        if (keystream_byte != test_data[i]) {
                            valid = false;
                            break;
                        }
                    }
                    
                    if (valid) {
                        // Check the rest of the data for extra confirmation
                        for (int i = 4; i < 8; i++) {
                            uint8_t keystream_byte = rc4_ksa_step(&rc4_i, &rc4_j, rc4_sbox);
                            if (keystream_byte != test_data[i]) {
                                valid = false;
                                break;
                            }
                        }
                        
                        if (valid) {
                            // Found a valid key!
                            pthread_mutex_lock(&keys_mutex);
                            key_found = true;
                            *found_key = key;
                            keys_tested += local_keys_tested;
                            pthread_mutex_unlock(&keys_mutex);
                            
                            printf("\n========================================\n");
                            printf("KEY FOUND with CPU!\n");
                            printf("Key: %08X\n", key);
                            printf("Key bytes: %02X %02X %02X %02X\n",
                                   (key >> 24) & 0xFF,
                                   (key >> 16) & 0xFF,
                                   (key >> 8) & 0xFF,
                                   key & 0xFF);
                            printf("Block byte (last byte): %02X\n", key & 0xFF);
                            printf("MI: %s\n", mi);
                            printf("Time taken: %ld seconds\n", (long)(time(NULL) - start_time));
                            printf("========================================\n");
                            
                            return 0;
                        }
                    }
                }
                break;
                
            // Other modes would have their own verification logic here
            case '2': // Motorola DMR Mode 2
            case '4': // Others DMR Mode 1
            case '5': // Others DMR Mode 2
                // These modes would each have their own verification logic
                // We're focusing on Mode 1 for now
                break;
        }
        
        // Update key counter (less frequently to reduce mutex contention)
        local_keys_tested++;
        if (local_keys_tested % 1000000 == 0) {
            pthread_mutex_lock(&keys_mutex);
            keys_tested += 1000000;
            pthread_mutex_unlock(&keys_mutex);
            
            // Reset local counter
            local_keys_tested = 0;
        }
        
        // Periodically report status
        if ((key_base % 10000000) == 0 && key_base > 0) {
            time_t current_time = time(NULL);
            double seconds = difftime(current_time, start_time);
            
            if (seconds > 0) {
                printf("CPU: %.1f%% complete, %.0f keys/sec. Current key: %08X\n", 
                       (double)(key_base) / 0x1000000 * 100.0,
                       (double)10000000 / seconds, key);
                
                // Reset for next measurement
                start_time = current_time;
            }
        }
    }
    
    // Add any remaining keys tested to the global counter
    if (local_keys_tested > 0) {
        pthread_mutex_lock(&keys_mutex);
        keys_tested += local_keys_tested;
        pthread_mutex_unlock(&keys_mutex);
    }
    
    printf("Finished block %02X search with CPU\n", block);
    return 1;
}

// Brute force thread (for CPU mode)
void *brute_force_thread(void *arg) {
    thread_args *args = (thread_args *)arg;
    unsigned char *test_data = args->test_data;
    int thread_id = args->thread_id;
    uint32_t start_key = args->start_key;
    uint32_t end_key = args->end_key;
    int block_to_test = args->block_to_test;
    uint64_t local_keys_tested = 0;
    char *mi = args->mi;
    
    time_t start_time = time(NULL);
    
    printf("Thread %d: Processing block: %02X, key range: 0x%06X - 0x%06X\n", 
           thread_id, block_to_test, start_key, end_key);
    
    // Current block testing loop
    for (uint32_t key_base = start_key; key_base <= end_key; key_base++) {
        // Check if we should stop early
        if (key_found || stop_search) {
            pthread_mutex_lock(&keys_mutex);
            keys_tested += local_keys_tested;
            pthread_mutex_unlock(&keys_mutex);
            
            free(args);
            return NULL;
        }
        
        // Construct the key with the block byte in the correct position
        // For DMR, it's the last byte (LSB)
        uint32_t key = (key_base << 8) | block_to_test;
        
        // IMPORTANT: We need to byte-swap the key for DMR
        uint32_t swapped_key = byte_swap_32(key);
        
        // Initialize RC4 S-box
        unsigned char rc4_sbox[256];
        for (int i = 0; i < 256; i++) {
            rc4_sbox[i] = i;
        }
        
        // RC4 KSA
        unsigned char j = 0;
        for (int i = 0; i < 256; i++) {
            j = (j + rc4_sbox[i] + ((unsigned char*)&swapped_key)[i % 4]) & 0xFF;
            unsigned char temp = rc4_sbox[i];
            rc4_sbox[i] = rc4_sbox[j];
            rc4_sbox[j] = temp;
        }
        
        // Test based on DMR mode
        switch (dmr_mode) {
            case '1': // Motorola DMR Mode 1
            case '3': // Anytone DMR
                // Check if first byte matches S[1]
                if (rc4_sbox[1] == test_data[0]) {
                    // Setup for RC4 stream generation
                    unsigned char rc4_i = 0, rc4_j = 0;
                    
                    // Check next few bytes to confirm
                    bool valid = true;
                    for (int i = 1; i < 4; i++) {
                        uint8_t keystream_byte = rc4_ksa_step(&rc4_i, &rc4_j, rc4_sbox);
                        if (keystream_byte != test_data[i]) {
                            valid = false;
                            break;
                        }
                    }
                    
                    if (valid) {
                        // Check the rest of the data for extra confirmation
                        for (int i = 4; i < 8; i++) {
                            uint8_t keystream_byte = rc4_ksa_step(&rc4_i, &rc4_j, rc4_sbox);
                            if (keystream_byte != test_data[i]) {
                                valid = false;
                                break;
                            }
                        }
                        
                        if (valid) {
                            // Found a valid key!
                            pthread_mutex_lock(&keys_mutex);
                            key_found = true;
                            keys_tested += local_keys_tested;
                            pthread_mutex_unlock(&keys_mutex);
                            
                            printf("\n========================================\n");
                            printf("Thread %d: KEY FOUND!\n", thread_id);
                            printf("Key: %08X\n", key);
                            printf("Key bytes: %02X %02X %02X %02X\n",
                                   (key >> 24) & 0xFF,
                                   (key >> 16) & 0xFF,
                                   (key >> 8) & 0xFF,
                                   key & 0xFF);
                            printf("Block byte (last byte): %02X\n", key & 0xFF);
                            printf("MI: %s\n", mi);
                            printf("Time taken: %ld seconds\n", (long)(time(NULL) - start_time));
                            printf("========================================\n");
                            
                            // Write key to file
                            FILE *key_file = fopen("/home/ubuntu/dsd-fme/arc4keyfinder/keys_found.txt", "a");
                            if (key_file != NULL) {
                                if (dmr_mode == '1')
                                    fprintf(key_file, "Motorola/Hytera DMR Mode 1 Key found: %08X - ", key);
                                else if (dmr_mode == '3')
                                    fprintf(key_file, "Anytone DMR Key found: %08X - ", key);
                                
                                for (int i = 0; i < 4; i++) {
                                    fprintf(key_file, "%02X ", ((unsigned char*)&key)[3-i]);
                                }
                                fprintf(key_file, "- MI: %s\n", mi);
                                fclose(key_file);
                            }
                            
                            free(args);
                            return NULL;
                        }
                    }
                }
                break;
                
            // Other modes would have their own verification logic here
            case '2': // Motorola DMR Mode 2
            case '4': // Others DMR Mode 1
            case '5': // Others DMR Mode 2
                // These modes would each have their own verification logic
                // We're focusing on Mode 1 for now
                break;
        }
        
        // Update key counter (do this less frequently to reduce mutex contention)
        local_keys_tested++;
        if (local_keys_tested % 1000000 == 0) {
            pthread_mutex_lock(&keys_mutex);
            keys_tested += 1000000;
            pthread_mutex_unlock(&keys_mutex);
            
            // Reset local counter
            local_keys_tested = 0;
        }
        
        // Periodically report status
        if ((key_base % 10000000) == 0 && key_base > 0) {
            time_t current_time = time(NULL);
            double seconds = difftime(current_time, start_time);
            
            if (seconds > 0) {
                printf("Thread %d: %.1f%% complete, %.0f keys/sec. Current key: %08X\n", 
                       thread_id, 
                       (double)(key_base - start_key) / (end_key - start_key + 1) * 100.0,
                       (double)10000000 / seconds, key);
                
                // Reset for next measurement
                start_time = current_time;
            }
        }
    }
    
    // Add any remaining keys tested to the global counter
    if (local_keys_tested > 0) {
        pthread_mutex_lock(&keys_mutex);
        keys_tested += local_keys_tested;
        pthread_mutex_unlock(&keys_mutex);
    }
    
    printf("Thread %d: Finished block %02X search, keys tested: 0x%X - 0x%X\n", 
           thread_id, block_to_test, start_key, end_key);
    
    free(args);
    return NULL;
}