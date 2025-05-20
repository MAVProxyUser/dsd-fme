#include <stdio.h>
#include <stdint.h>
#include <string.h>

// RC4 implementation for DMR
void rc4_block_output(int drop, int keylen, int meslen, uint8_t *key, uint8_t *output_blocks) {
  int i, j, x, count;
  unsigned int keylength = (unsigned int)keylen;
  unsigned int messagelength = (unsigned int)meslen;
  unsigned int S[256];

  // Initialize S-box
  for(i=0; i<256; i++)
    S[i] = i;

  // Key scheduling algorithm
  j = 0;
  for(i = 0; i<256; i++) {
    j = (j + S[i] + key[i % keylength]) % 256;
    unsigned int temp = S[i];
    S[i] = S[j];
    S[j] = temp;
  }

  // Generate Keystream
  i = 0;
  j = 0;
  x = 0;
  unsigned int byte;

  for(count = 0; count < (messagelength + drop); count++) {
    i = (i + 1) % 256;
    j = (j + S[i]) % 256;
    unsigned int temp = S[i];
    S[i] = S[j];
    S[j] = temp;
    byte = S[(S[i] + S[j]) % 256];

    // Collect Output blocks
    if (count >= drop)
      output_blocks[x++] = byte;
  }
}

// DMR RC4 setup with key and Message Indicator (MI)
void dmr_rc4_setup(uint32_t key_value, uint32_t mi_value, uint8_t *ks_octets, int ks_length) {
  uint8_t key[5] = {0};
  uint8_t kiv[5] = {0};
  uint8_t mi[5] = {0};
  uint8_t ks[135] = {0}; // Standard DMR frame size for keystream

  // Load key_value into key array (big endian)
  key[0] = 0; // For 32-bit value, the most significant byte is 0
  key[1] = (key_value >> 24) & 0xFF;
  key[2] = (key_value >> 16) & 0xFF;
  key[3] = (key_value >> 8) & 0xFF;
  key[4] = key_value & 0xFF;

  // Load mi_value into mi array (big endian)
  mi[0] = 0; // For 32-bit value, the most significant byte is 0
  mi[1] = (mi_value >> 24) & 0xFF;
  mi[2] = (mi_value >> 16) & 0xFF;
  mi[3] = (mi_value >> 8) & 0xFF;
  mi[4] = mi_value & 0xFF;

  // Generate RC4 keystream with 0 drop bytes
  rc4_block_output(0, 5, ks_length, key, ks);

  // XOR key with MI to create KIV (Key Initialization Vector)
  for (int i = 0; i < 5; i++)
    kiv[i] = key[i] ^ mi[i];

  // Final keystream is KIV XOR with RC4 output
  for (int i = 0; i < ks_length; i++)
    ks_octets[i] = kiv[i%5] ^ ks[i];
}

// Standard DMR AMBE silence frame pattern for testing
// These are representative patterns for AMBE encoded silence
const uint8_t ambe_silence_pattern[3][8] = {
  {0x01, 0x42, 0x7A, 0x00, 0x40, 0x00, 0x00, 0x00}, // AMBE frame 1
  {0x01, 0x42, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00}, // AMBE frame 2
  {0x01, 0x42, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00}  // AMBE frame 3
};

// Function to print bytes in hex format
void print_bytes(const char *label, uint8_t *data, int length) {
  printf("%s: ", label);
  for (int i = 0; i < length; i++) {
    printf("%02X", data[i]);
    if ((i+1) % 8 == 0 && i < length-1)
      printf(" ");
  }
  printf("\n");
}

int main() {
  // Parameters
  uint32_t key = 0x00000001; // Key 0x00000001 (specific key for testing)
  uint32_t mi = 0x12AB34CD;  // MI 12AB34CD (Message Indicator, aka IV)
  uint8_t keystream[135] = {0}; // Buffer to hold the generated keystream
  
  /* In DMR, encryption works as follows:
   * 1. The 32-bit Key and 32-bit MI (Message Indicator) are used as inputs
   * 2. RC4 generates keystream using the Key
   * 3. The Key and MI are XORed to create a KIV (Key Initialization Vector)
   * 4. The final keystream is created by XORing the RC4 keystream with the KIV
   * 5. This keystream is then XORed with the DMR AMBE voice frames for encryption
   */
  
  printf("DMR RC4 Keystream Generator\n");
  printf("============================\n");
  printf("Key: 0x%08X\n", key);
  printf("MI:  0x%08X\n\n", mi);
  
  // Generate keystream using the DMR RC4 algorithm
  dmr_rc4_setup(key, mi, keystream, 135);
  
  // Print the first 24 bytes of keystream (enough for 3 AMBE frames)
  print_bytes("Keystream", keystream, 24);
  
  printf("\nEncrypted AMBE Frames (Silence Pattern XORed with Keystream):\n");
  
  // Create and print encrypted AMBE frames by XORing silence pattern with keystream
  uint8_t encrypted_ambe[3][8] = {0};
  
  for (int frame = 0; frame < 3; frame++) {
    for (int i = 0; i < 8; i++) {
      encrypted_ambe[frame][i] = ambe_silence_pattern[frame][i] ^ keystream[frame*8 + i];
    }
    
    char label[20];
    sprintf(label, "AMBE%d", frame+1);
    print_bytes(label, encrypted_ambe[frame], 8);
  }
  
  printf("\nComplete encrypted AMBE superframe (24 bytes):\n");
  uint8_t complete_frame[24] = {0};
  for (int frame = 0; frame < 3; frame++) {
    memcpy(&complete_frame[frame*8], encrypted_ambe[frame], 8);
  }
  print_bytes("Full", complete_frame, 24);
  
  return 0;
}