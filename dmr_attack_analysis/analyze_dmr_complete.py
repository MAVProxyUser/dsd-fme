#!/usr/bin/env python3
"""
Complete DMR Encryption Attack Analysis
Analyzes both encrypted and unencrypted frames
"""

import sqlite3
import json
import numpy as np
from collections import Counter, defaultdict
import struct
import binascii

# RC4 implementation
class RC4:
    def __init__(self, key):
        self.key = key
        self.S = list(range(256))
        self.reset()
    
    def reset(self):
        j = 0
        for i in range(256):
            j = (j + self.S[i] + self.key[i % len(self.key)]) % 256
            self.S[i], self.S[j] = self.S[j], self.S[i]
        self.i = 0
        self.j = 0
    
    def encrypt(self, data):
        output = []
        for byte in data:
            self.i = (self.i + 1) % 256
            self.j = (self.j + self.S[self.i]) % 256
            self.S[self.i], self.S[self.j] = self.S[self.j], self.S[self.i]
            K = self.S[(self.S[self.i] + self.S[self.j]) % 256]
            output.append(byte ^ K)
        return bytes(output)

class DMRAttackComplete:
    def __init__(self):
        self.unencrypted_db = 'dmr_capture_20250517_033740.db'
        self.encrypted_dbs = [
            'dmr_capture_20250517_005052.db',
            'dmr_capture_20250517_005411.db',
            'dmr_capture_20250517_010359.db',
            'dmr_capture_20250517_013614.db',
            'dmr_capture_20250517_013819.db',
            'dmr_capture_20250517_021613.db'
        ]
        self.fixed_hmi = 0x6C8AB637
        self.known_patterns = set()
        self.results = {}
    
    def analyze_unencrypted(self):
        """Analyze unencrypted frames to find common patterns"""
        print("\n=== ANALYZING UNENCRYPTED FRAMES ===")
        
        conn = sqlite3.connect(self.unencrypted_db)
        cursor = conn.cursor()
        
        # Get all unencrypted frames
        cursor.execute("SELECT ambe_hex FROM U_00000000_S0")
        frames = cursor.fetchall()
        
        print(f"Total unencrypted frames: {len(frames)}")
        
        # Count patterns
        pattern_count = Counter()
        for ambe_hex, in frames:
            pattern_count[ambe_hex] += 1
        
        # Find most common patterns
        top_patterns = pattern_count.most_common(50)
        
        print("\nTop 10 most common patterns:")
        for pattern, count in top_patterns[:10]:
            freq = count / len(frames) * 100
            print(f"  {pattern}: {count} times ({freq:.2f}%)")
            
            # Patterns that appear more than 1% are likely beeps
            if freq > 1.0:
                self.known_patterns.add(pattern)
        
        self.results['unencrypted'] = {
            'total_frames': len(frames),
            'unique_patterns': len(pattern_count),
            'pattern_distribution': dict(pattern_count),
            'top_patterns': dict(top_patterns[:20])
        }
        
        conn.close()
        return top_patterns
    
    def analyze_encrypted(self):
        """Analyze encrypted frames and test decryption"""
        print("\n=== ANALYZING ENCRYPTED FRAMES ===")
        
        all_encrypted = []
        
        for db_path in self.encrypted_dbs:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Find tables with correct H-MI
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
            tables = cursor.fetchall()
            
            for table_name, in tables:
                # Extract MI from table name
                parts = table_name.split('_')
                if len(parts) >= 2:
                    mi_hex = parts[1]
                    try:
                        mi_value = int(mi_hex, 16)
                        
                        # Check if this is our fixed H-MI
                        if mi_value == self.fixed_hmi:
                            cursor.execute(f"SELECT mi_full, ambe_hex FROM {table_name}")
                            frames = cursor.fetchall()
                            all_encrypted.extend(frames)
                            print(f"  {db_path}: {len(frames)} frames from {table_name}")
                    except ValueError:
                        continue
            
            conn.close()
        
        print(f"\nTotal encrypted frames: {len(all_encrypted)}")
        
        # Group by C-MI
        cmi_groups = defaultdict(list)
        for cmi, ambe_hex in all_encrypted:
            cmi_groups[cmi].append(ambe_hex)
        
        print(f"Unique C-MI values: {len(cmi_groups)}")
        
        # Test decryption
        self.test_decryption(cmi_groups)
        
        return cmi_groups
    
    def test_decryption(self, cmi_groups):
        """Test RC4 decryption with known patterns"""
        print("\n=== TESTING DECRYPTION ===")
        
        # If we don't have known patterns, use some common AMBE patterns
        if not self.known_patterns:
            # Common silence patterns
            self.known_patterns.add("ACE63EC8BDF60000")
            self.known_patterns.add("1114A47380000000")
            self.known_patterns.add("000000000000")
        
        successes = 0
        total_tests = 0
        
        for cmi, frames in list(cmi_groups.items())[:10]:  # Test first 10 C-MIs
            print(f"\nTesting C-MI 0x{cmi:08X} with {len(frames)} frames")
            
            for frame in frames[:5]:  # Test first 5 frames
                for pattern in list(self.known_patterns)[:3]:  # Try 3 patterns
                    success = self.test_single_decrypt(frame, cmi, pattern)
                    if success:
                        successes += 1
                        print(f"  Success: {frame} -> {pattern}")
                    total_tests += 1
        
        success_rate = successes / total_tests if total_tests > 0 else 0
        print(f"\nOverall success rate: {successes}/{total_tests} ({success_rate*100:.1f}%)")
        
        self.results['decryption'] = {
            'total_tests': total_tests,
            'successes': successes,
            'success_rate': success_rate
        }
    
    def test_single_decrypt(self, encrypted_hex, cmi, known_pattern):
        """Test decryption of a single frame"""
        try:
            # Build IV: H-MI || C-MI
            iv = struct.pack('>II', self.fixed_hmi, cmi)
            
            # Initialize RC4
            cipher = RC4(iv)
            
            # Decrypt
            encrypted_bytes = binascii.unhexlify(encrypted_hex)
            decrypted = cipher.encrypt(encrypted_bytes)
            decrypted_hex = binascii.hexlify(decrypted).decode().upper()
            
            return decrypted_hex == known_pattern.upper()
        except Exception as e:
            return False
    
    def verify_lfsr(self):
        """Verify LFSR progression"""
        print("\n=== VERIFYING LFSR PROGRESSION ===")
        
        sequences = []
        
        for db_path in self.encrypted_dbs:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get C-MI sequences
            cursor.execute("""
                SELECT DISTINCT mi_full 
                FROM C_6C8AB637_S0 
                ORDER BY id
            """)
            
            cmis = [row[0] for row in cursor.fetchall()]
            if len(cmis) > 1:
                sequences.append(cmis)
            
            conn.close()
        
        # Test predictions
        correct = 0
        total = 0
        
        for seq in sequences:
            for i in range(len(seq) - 1):
                current = seq[i]
                actual_next = seq[i + 1]
                predicted_next = self.lfsr_next(current)
                
                if predicted_next == actual_next:
                    correct += 1
                total += 1
                
                if i < 3:  # Show first few
                    match = '✓' if predicted_next == actual_next else '✗'
                    print(f"  0x{current:08X} -> 0x{predicted_next:08X} (actual: 0x{actual_next:08X}) {match}")
        
        accuracy = correct / total if total > 0 else 0
        print(f"\nLFSR accuracy: {correct}/{total} ({accuracy*100:.1f}%)")
        
        self.results['lfsr'] = {
            'predictions': total,
            'correct': correct,
            'accuracy': accuracy
        }
    
    def lfsr_next(self, current):
        """Calculate next LFSR value"""
        lfsr = current
        for _ in range(32):  # 32 clock cycles
            bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
            lfsr = (lfsr << 1) | bit
        return lfsr & 0xFFFFFFFF
    
    def run_analysis(self):
        """Run complete analysis"""
        print("=== DMR COMPLETE ATTACK ANALYSIS ===")
        print(f"Fixed H-MI: 0x{self.fixed_hmi:08X}")
        print("="*40)
        
        # Analyze unencrypted frames
        self.analyze_unencrypted()
        
        # Analyze encrypted frames
        cmi_groups = self.analyze_encrypted()
        
        # Verify LFSR
        self.verify_lfsr()
        
        # Print summary
        print("\n=== SUMMARY ===")
        print(f"Unencrypted frames: {self.results['unencrypted']['total_frames']}")
        print(f"Encrypted frames tested: {len(cmi_groups)} C-MI groups")
        print(f"Decryption success rate: {self.results.get('decryption', {}).get('success_rate', 0)*100:.1f}%")
        print(f"LFSR prediction accuracy: {self.results.get('lfsr', {}).get('accuracy', 0)*100:.1f}%")
        
        # Save results
        with open('complete_attack_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)

if __name__ == "__main__":
    attack = DMRAttackComplete()
    attack.run_analysis()