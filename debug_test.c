#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

// Byte swap function as it's not standard
static uint32_t byte_swap_32(uint32_t x) {
    return ((x & 0xFF) << 24) | 
           ((x & 0xFF00) << 8) | 
           ((x & 0xFF0000) >> 8) | 
           ((x & 0xFF000000) >> 24);
}

// Plaintext pattern used in arc4keyfinder
unsigned char plaintext[12] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66};

// RC4 KSA algorithm step
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

int main() {
    // Test key 00000001
    uint32_t key = 0x00000001;
    char mi_hex[] = "12AB34CD";
    
    printf("DEBUG INFO FOR KEY SEARCH:\n");
    printf("==========================\n");
    printf("Key: 0x%08X\n", key);
    printf("MI: %s\n", mi_hex);
    
    // Print plaintext pattern
    printf("\nPlaintext pattern: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", plaintext[i]);
    }
    printf("\n");
    
    // Swap key for DMR format
    uint32_t swapped_key = byte_swap_32(key);
    printf("Swapped key: 0x%08X\n", swapped_key);
    printf("Key bytes: %02X %02X %02X %02X\n",
           (key >> 24) & 0xFF,
           (key >> 16) & 0xFF,
           (key >> 8) & 0xFF,
           key & 0xFF);
    printf("Swapped key bytes: %02X %02X %02X %02X\n",
           (swapped_key >> 24) & 0xFF,
           (swapped_key >> 16) & 0xFF,
           (swapped_key >> 8) & 0xFF,
           swapped_key & 0xFF);
    
    // Initialize RC4 S-box
    unsigned char s_box[256];
    for (int i = 0; i < 256; i++) {
        s_box[i] = i;
    }
    
    // RC4 KSA
    unsigned char j = 0;
    for (int i = 0; i < 256; i++) {
        j = (j + s_box[i] + ((unsigned char*)&swapped_key)[i % 4]) & 0xFF;
        unsigned char temp = s_box[i];
        s_box[i] = s_box[j];
        s_box[j] = temp;
    }
    
    // First byte of keystream is S[1] in DMR Mode 1
    printf("\nKeystream generation for DMR Mode 1:\n");
    printf("First keystream byte is S[1] = %02X\n", s_box[1]);
    
    // Generate keystream
    unsigned char keystream[12];
    keystream[0] = s_box[1];
    
    unsigned char rc4_i = 0, rc4_j = 0;
    printf("Remaining keystream bytes: ");
    for (int i = 1; i < 12; i++) {
        unsigned char ks_byte = rc4_ksa_step(&rc4_i, &rc4_j, s_box);
        keystream[i] = ks_byte;
        printf("%02X ", ks_byte);
    }
    printf("\n");
    
    // Full keystream
    printf("\nFull keystream: ");
    for (int i = 0; i < 12; i++) {
        printf("%02X ", keystream[i]);
    }
    printf("\n");
    
    // Generate encrypted frames
    printf("\nGenerated encrypted AMBE frames:\n");
    unsigned char encrypted[12];
    for (int i = 0; i < 12; i++) {
        encrypted[i] = plaintext[i] ^ keystream[i];
    }
    
    for (int f = 0; f < 3; f++) {
        printf("Frame %d: ", f+1);
        for (int i = 0; i < 4; i++) {
            printf("%02X", encrypted[f*4 + i]);
        }
        printf("\n");
    }
    
    printf("\nCommand-line format for testing:\n");
    printf("./arc4keyfinder_unified --mode 1 --mi \"%s\" \\\n", mi_hex);
    for (int f = 0; f < 3; f++) {
        printf("  --frame \"");
        for (int i = 0; i < 4; i++) {
            printf("%02X", encrypted[f*4 + i]);
        }
        printf("\" \\\n");
    }
    printf("  --start-block 0x01 --end-block 0x01 --verbose\n");
    
    return 0;
}