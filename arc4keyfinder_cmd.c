#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>

// Byte swap functions
uint32_t byte_swap_32(uint32_t value) {
    return ((value & 0xFF) << 24) | 
           ((value & 0xFF00) << 8) | 
           ((value & 0xFF0000) >> 8) | 
           ((value >> 24) & 0xFF);
}

// RC4 KSA algorithm step
uint8_t rc4_ksa_step(uint8_t *i, uint8_t *j, uint8_t *s_box) {
    uint8_t temp;
    uint8_t index_i = *i + 1;
    *i = index_i;
    uint8_t index_j = *j + s_box[index_i];
    *j = index_j;
    
    // Swap S[i] and S[j]
    temp = s_box[index_i];
    s_box[index_i] = s_box[index_j];
    s_box[index_j] = temp;
    
    // Return S[S[i] + S[j]]
    return s_box[(uint8_t)(s_box[index_i] + s_box[index_j])];
}

void convert_hex_to_binary(const char *src, unsigned char *dst, int len) {
    if (len <= 0) return;
    
    char hex_str[3] = {0};
    for (int i = 0; i < len/2; i++) {
        hex_str[0] = src[i*2];
        hex_str[1] = src[i*2 + 1];
        dst[i] = (unsigned char)strtol(hex_str, NULL, 16);
    }
}

int main(int argc, char *argv[]) {
    if (argc < 7) {
        printf("Usage: %s -f <encrypted_frame1> -f <encrypted_frame2> -f <encrypted_frame3> -k <test_key>\n", argv[0]);
        return 1;
    }
    
    unsigned char encrypted_frames[3][10] = {0};
    int frame_count = 0;
    uint32_t test_key = 0;
    
    // Parse command line
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-f") == 0 && i + 1 < argc) {
            if (frame_count < 3) {
                convert_hex_to_binary(argv[i+1], encrypted_frames[frame_count], strlen(argv[i+1]));
                printf("Frame %d: %s\n", frame_count+1, argv[i+1]);
                frame_count++;
            }
            i++;
        } 
        else if (strcmp(argv[i], "-k") == 0 && i + 1 < argc) {
            test_key = strtoul(argv[i+1], NULL, 16);
            printf("Test key: 0x%08X\n", test_key);
            i++;
        }
    }
    
    if (frame_count < 3 || test_key == 0) {
        printf("Error: Need 3 frames and a test key\n");
        return 1;
    }
    
    // Expected plaintext
    unsigned char plaintext[12] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66};
    
    // Step 1: Decrypt the frames to get test_data
    printf("\n=== Step 1: Calculate target keystream ===\n");
    uint8_t test_data[12] = {0};
    
    // XOR encrypted frames with plaintext to get keystream
    for (int i = 0; i < 4; i++) {
        test_data[i] = encrypted_frames[0][i] ^ plaintext[i];
    }
    for (int i = 0; i < 4; i++) {
        test_data[i+4] = encrypted_frames[1][i] ^ plaintext[i+4];
    }
    for (int i = 0; i < 4; i++) {
        test_data[i+8] = encrypted_frames[2][i] ^ plaintext[i+8];
    }
    
    printf("Target keystream: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", test_data[i]);
    }
    printf("\n\n");
    
    // Step 2: Generate keystream with the test key and see if it matches
    printf("=== Step 2: Generate keystream with test key ===\n");
    
    // Byte-swap the key for DMR
    uint32_t swapped_key = byte_swap_32(test_key);
    printf("Byte-swapped key: 0x%08X\n", swapped_key);
    
    // Initialize RC4 S-box
    uint8_t rc4_sbox[256];
    for (int i = 0; i < 256; i++) {
        rc4_sbox[i] = i;
    }
    
    // RC4 KSA
    uint8_t j = 0;
    for (int i = 0; i < 256; i++) {
        j = (j + rc4_sbox[i] + ((uint8_t*)&swapped_key)[i % 4]) & 0xFF;
        uint8_t temp = rc4_sbox[i];
        rc4_sbox[i] = rc4_sbox[j];
        rc4_sbox[j] = temp;
    }
    
    // Generate keystream
    uint8_t generated_keystream[12];
    generated_keystream[0] = rc4_sbox[1]; // First byte is S[1] for DMR Mode 1
    
    uint8_t rc4_i = 0;
    uint8_t rc4_j = 0;
    
    for (int i = 1; i < 12; i++) {
        generated_keystream[i] = rc4_ksa_step(&rc4_i, &rc4_j, rc4_sbox);
    }
    
    printf("Generated keystream: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", generated_keystream[i]);
    }
    printf("\n");
    
    // Compare keystreams
    bool match = true;
    for (int i = 0; i < 12; i++) {
        if (generated_keystream[i] != test_data[i]) {
            printf("Mismatch at position %d: generated=%02X, target=%02X\n", 
                  i, generated_keystream[i], test_data[i]);
            match = false;
        }
    }
    
    if (match) {
        printf("\nSUCCESS: Generated keystream matches target keystream!\n");
    } else {
        printf("\nFAILURE: Keystreams don't match\n");
    }
    
    return 0;
}