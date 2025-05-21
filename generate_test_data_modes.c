#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

// Define byte swap function as it's not standard
uint32_t byte_swap_32(uint32_t x) {
    return ((x & 0xFF) << 24) | 
           ((x & 0xFF00) << 8) | 
           ((x & 0xFF0000) >> 8) | 
           ((x & 0xFF000000) >> 24);
}

// Function to print bytes in hex
void print_bytes(const unsigned char *data, int len) {
    for (int i = 0; i < len; i++) {
        printf("%02X", data[i]);
    }
}

// Generate encrypted frames using a known key and plaintext for different DMR modes
void generate_test_frames(uint32_t key, const char *mi, char mode) {
    printf("Generating test frames for key: 0x%08X using DMR Mode %c\n", key, mode);
    printf("MI: %s\n", mi);
    
    // Byte-swap the key for DMR
    uint32_t swapped_key = byte_swap_32(key);
    printf("Byte-swapped key (DMR format): 0x%08X\n", swapped_key);
    
    // Initialize plaintext pattern based on the DMR mode
    unsigned char plaintext[18] = {0};
    
    switch (mode) {
        case '1': // Motorola DMR Mode 1 - standard test pattern
            memcpy(plaintext, (unsigned char[]){0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 
                                               0x77, 0x88, 0x99, 0x00, 0xAA, 0xBB}, 18);
            break;
            
        case '2': // Motorola DMR Mode 2 - specific pattern
            ((unsigned int*)plaintext)[0] = 0x9fa901f8;
            ((unsigned int*)plaintext)[1] = 0xa901f88c;
            ((unsigned int*)plaintext)[2] = 0x1f88c9f;
            *((unsigned short*)plaintext + 6) = 0x9fa9;
            *((unsigned char*)plaintext + 14) = 0x8c;
            break;
            
        case '3': // Anytone DMR - zeros
            memset(plaintext, 0, sizeof(plaintext));
            break;
            
        case '4': // Others DMR Mode 1 - 0x08 pattern
            memset(plaintext, 8, sizeof(plaintext));
            break;
            
        case '5': // Others DMR Mode 2 - using standard pattern for now
            memcpy(plaintext, (unsigned char[]){0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 
                                               0x77, 0x88, 0x99, 0x00, 0xAA, 0xBB}, 18);
            break;
    }
    
    printf("Plaintext data for Mode %c: ", mode);
    for (int i = 0; i < 12; i++) {
        printf("%02X ", plaintext[i]);
    }
    printf("\n");
    
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
    
    // Generate keystream - first byte is S[1] for DMR
    unsigned char keystream[18];
    keystream[0] = rc4_sbox[1];  // First byte is S[1]
    
    // Generate remaining keystream bytes
    unsigned char rc4_i = 0, rc4_j = 0;
    for (int i = 1; i < 18; i++) {
        unsigned char index_i = rc4_i + 1;
        rc4_i = index_i;
        unsigned char index_j = rc4_j + rc4_sbox[index_i];
        rc4_j = index_j;
        
        // Swap S[i] and S[j]
        unsigned char temp = rc4_sbox[index_i];
        rc4_sbox[index_i] = rc4_sbox[index_j];
        rc4_sbox[index_j] = temp;
        
        // Output keystream byte
        keystream[i] = rc4_sbox[(unsigned char)(rc4_sbox[index_i] + rc4_sbox[index_j])];
    }
    
    printf("Generated keystream: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", keystream[i]);
    }
    printf("\n");
    
    // Create encrypted frames by XORing plaintext with keystream
    unsigned char encrypted[18];
    for (int i = 0; i < 18; i++) {
        encrypted[i] = plaintext[i] ^ keystream[i];
    }
    
    printf("Encrypted data: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", encrypted[i]);
    }
    printf("\n");
    
    // Format as 3 AMBE frames (4 bytes each, 8 hex chars)
    printf("AMBE Frame 1: ");
    print_bytes(encrypted, 4);
    printf("00004000\n");  // Append zeros to make it look like real AMBE data
    
    printf("AMBE Frame 2: ");
    print_bytes(encrypted + 4, 4);
    printf("00006000\n");  // Append zeros
    
    printf("AMBE Frame 3: ");
    print_bytes(encrypted + 8, 4);
    printf("00008000\n");  // Append zeros
    
    // Output SQL to create a test database
    printf("\n-- SQL to create test database with these frames:\n");
    printf("CREATE TABLE \"C_%s_S0\" (id INTEGER PRIMARY KEY, ambe_hex TEXT, timestamp TEXT, stream_id INTEGER, encrypted INTEGER, mi_present INTEGER, radio_id INTEGER);\n", mi);
    printf("INSERT INTO \"C_%s_S0\" VALUES (1, '", mi);
    print_bytes(encrypted, 4);
    printf("00004000', '2025-05-20 05:00:00', 12345, 1, 1, 426);\n");
    
    printf("INSERT INTO \"C_%s_S0\" VALUES (2, '", mi);
    print_bytes(encrypted + 4, 4);
    printf("00006000', '2025-05-20 05:00:00', 12345, 1, 1, 426);\n");
    
    printf("INSERT INTO \"C_%s_S0\" VALUES (3, '", mi);
    print_bytes(encrypted + 8, 4);
    printf("00008000', '2025-05-20 05:00:00', 12345, 1, 1, 426);\n");
    
    // Output command line to test this with arc4keyfinder_unified
    printf("\n-- Command to find this key with arc4keyfinder_unified:\n");
    printf("./arc4keyfinder_unified -m %c -f ", mode);
    print_bytes(encrypted, 4);
    printf("00004000 -f ");
    print_bytes(encrypted + 4, 4);
    printf("00006000 -f ");
    print_bytes(encrypted + 8, 4);
    printf("00008000 -i %s -s %02X -e %02X\n", 
           mi, key & 0xFF, key & 0xFF);
}

// Usage: generate_test_data_modes <key> <mi> <mode>
int main(int argc, char *argv[]) {
    if (argc < 4) {
        printf("Usage: %s <key_in_hex> <mi_value> <mode_number 1-5>\n", argv[0]);
        printf("Example: %s 12345678 ABCDEF12 1\n", argv[0]);
        return 1;
    }
    
    // Parse key from hex
    uint32_t key = (uint32_t)strtoul(argv[1], NULL, 16);
    
    // Parse mode - should be 1-5
    char mode = argv[3][0];
    if (mode < '1' || mode > '5') {
        printf("Error: Mode must be between 1 and 5\n");
        return 1;
    }
    
    // Generate test data
    generate_test_frames(key, argv[2], mode);
    
    return 0;
}