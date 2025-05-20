#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

// Byte swap functions
uint32_t byte_swap_32(uint32_t value) {
    return ((value & 0xFF) << 24) | 
           ((value & 0xFF00) << 8) | 
           ((value & 0xFF0000) >> 8) | 
           ((value >> 24) & 0xFF);
}

int main() {
    // Known test key (same as in our tests)
    uint32_t test_key = 0x12345678;
    
    // Key bytes 
    uint8_t key_bytes[4];
    key_bytes[0] = (test_key >> 24) & 0xFF;
    key_bytes[1] = (test_key >> 16) & 0xFF;
    key_bytes[2] = (test_key >> 8) & 0xFF;
    key_bytes[3] = test_key & 0xFF;
    
    printf("Test key: 0x%08X\n", test_key);
    printf("Key bytes: %02X %02X %02X %02X\n", key_bytes[0], key_bytes[1], key_bytes[2], key_bytes[3]);
    
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
    
    // Output S-box values
    printf("RC4 S-box first values: %02X %02X %02X %02X %02X\n", 
           rc4_sbox[0], rc4_sbox[1], rc4_sbox[2], rc4_sbox[3], rc4_sbox[4]);
    
    // First byte of keystream in DMR Mode 1 is S[1]
    printf("First keystream byte (S[1]): %02X\n", rc4_sbox[1]);
    
    // Generate keystream
    uint8_t keystream[12];
    keystream[0] = rc4_sbox[1]; // First byte is S[1]
    
    uint8_t rc4_i = 0;
    uint8_t rc4_j = 0;
    
    // Generate 12 bytes of keystream for DMR Mode 1
    printf("\nKeystream generation:\n");
    for (int i = 1; i < 12; i++) {
        // RC4 keystream generation step
        rc4_i = (rc4_i + 1) & 0xFF;
        rc4_j = (rc4_j + rc4_sbox[rc4_i]) & 0xFF;
        
        // Swap S[i] and S[j]
        uint8_t temp = rc4_sbox[rc4_i];
        rc4_sbox[rc4_i] = rc4_sbox[rc4_j];
        rc4_sbox[rc4_j] = temp;
        
        // Output S[S[i] + S[j]]
        keystream[i] = rc4_sbox[(rc4_sbox[rc4_i] + rc4_sbox[rc4_j]) & 0xFF];
        printf("Keystream byte %d: %02X\n", i, keystream[i]);
    }
    
    // Define sample plaintext for test
    uint8_t plaintext[12] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66};
    uint8_t encrypted[12];
    
    // Encrypt using keystream (XOR)
    for (int i = 0; i < 12; i++) {
        encrypted[i] = plaintext[i] ^ keystream[i];
    }
    
    // Output full keystream
    printf("\nFull keystream: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", keystream[i]);
    }
    printf("\n");
    
    // Output plaintext
    printf("\nPlaintext: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", plaintext[i]);
    }
    printf("\n");
    
    // Output encrypted data
    printf("\nEncrypted data: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", encrypted[i]);
    }
    printf("\n");
    
    // For command-line args format
    printf("\nCommand-line frame format for keyfinder:\n");
    printf("-f %02X%02X%02X%02X00 ", encrypted[0], encrypted[1], encrypted[2], encrypted[3]);
    printf("-f %02X%02X%02X%02X00 ", encrypted[4], encrypted[5], encrypted[6], encrypted[7]);
    printf("-f %02X%02X%02X%02X00\n", encrypted[8], encrypted[9], encrypted[10], encrypted[11]);
    
    return 0;
}