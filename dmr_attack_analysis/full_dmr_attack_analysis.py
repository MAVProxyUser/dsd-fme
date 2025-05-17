#!/usr/bin/env python3
"""
Full DMR Attack Analysis - Comprehensive Analysis of Encrypted and Unencrypted Frames
This implements the complete attack methodology against DMR encryption
"""

import sqlite3
import json
import numpy as np
from collections import Counter, defaultdict
import struct
import binascii

class FullDMRAttack:
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
        self.known_beep_patterns = set()
        self.results = {
            'unencrypted_analysis': {},
            'encrypted_analysis': {},
            'attack_results': {},
            'statistics': {}
        }
    
    def analyze_unencrypted_frames(self):
        """Extract beep patterns from unencrypted frames"""
        print("\n=== ANALYZING UNENCRYPTED FRAMES ===")
        
        conn = sqlite3.connect(self.unencrypted_db)
        cursor = conn.cursor()
        
        # Get all unencrypted frames
        cursor.execute("SELECT ambe_hex FROM U_00000000_S0")
        frames = cursor.fetchall()
        
        pattern_counter = Counter()
        frame_data = []
        
        print(f"Total unencrypted frames: {len(frames)}")
        
        # Analyze each frame
        for i, (ambe_hex,) in enumerate(frames):
            frame_data.append(ambe_hex)
            pattern_counter[ambe_hex] += 1
        
        # Find the most common patterns (likely beeps)
        top_patterns = pattern_counter.most_common(20)
        
        print("\nTop 20 most common AMBE patterns:")
        for pattern, count in top_patterns[:20]:
            print(f"  {pattern}: {count} occurrences ({count/len(frames)*100:.1f}%)")
        
        # Identify potential beep patterns (high frequency)
        potential_beeps = []
        for pattern, count in pattern_counter.items():
            if count >= len(frames) * 0.05:  # At least 5% occurrence
                potential_beeps.append((pattern, count))
                self.known_beep_patterns.add(pattern)
        
        print(f"\nIdentified {len(potential_beeps)} potential beep patterns")
        
        self.results['unencrypted_analysis'] = {
            'total_frames': len(frames),
            'unique_patterns': len(pattern_counter),
            'top_patterns': dict(top_patterns[:10]),
            'beep_patterns': [p[0] for p in potential_beeps],
            'pattern_frequencies': dict(pattern_counter)
        }
        
        conn.close()
        return potential_beeps
    
    def calculate_lfsr_progression(self, current_mi, steps=1):
        """Calculate LFSR progression using verified polynomial x^32 + x^4 + x^2 + 1"""
        lfsr = current_mi
        
        for _ in range(steps):
            for _ in range(32):  # 32 clock cycles per output
                bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
                lfsr = (lfsr << 1) | bit
        
        return lfsr & 0xFFFFFFFF
    
    def test_rc4_decrypt(self, encrypted_hex, hmi, cmi, known_pattern):
        """Test RC4 decryption with known plaintext"""
        # Build IV: H-MI || C-MI
        iv = struct.pack('>II', hmi, cmi)
        
        # Initialize RC4
        cipher = RC4(iv)
        
        # Get keystream for this AMBE frame
        ambe_bytes = binascii.unhexlify(encrypted_hex)
        keystream = cipher.encrypt(b'\x00' * len(ambe_bytes))
        
        # XOR to decrypt
        decrypted = bytes(a ^ b for a, b in zip(ambe_bytes, keystream))
        decrypted_hex = binascii.hexlify(decrypted).decode().upper()
        
        return decrypted_hex == known_pattern, decrypted_hex, keystream
    
    def analyze_encrypted_frames(self):
        """Analyze encrypted frames and test attack methodology"""
        print("\n=== ANALYZING ENCRYPTED FRAMES ===")
        
        all_encrypted_frames = []
        
        # Collect all encrypted frames
        for db_path in self.encrypted_dbs:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if the encrypted table exists
            cursor.execute(f"SELECT COUNT(*) FROM E_{self.fixed_hmi:08X}_S0")
            count = cursor.fetchone()[0]
            
            if count > 0:
                cursor.execute(f"SELECT mi_full, ambe_hex FROM E_{self.fixed_hmi:08X}_S0 ORDER BY id")
                frames = cursor.fetchall()
                all_encrypted_frames.extend(frames)
                print(f"  {db_path}: {len(frames)} frames")
            
            conn.close()
        
        print(f"\nTotal encrypted frames: {len(all_encrypted_frames)}")
        
        # Group frames by C-MI value
        cmi_groups = defaultdict(list)
        for cmi, ambe_hex in all_encrypted_frames:
            cmi_groups[cmi].append(ambe_hex)
        
        print(f"Unique C-MI values: {len(cmi_groups)}")
        
        # Test attack on each C-MI group
        attack_successes = []
        
        for cmi, frames in cmi_groups.items():
            if len(frames) < 3:  # Skip small groups
                continue
                
            print(f"\nTesting C-MI 0x{cmi:08X} with {len(frames)} frames")
            
            # Try each known beep pattern
            for beep_pattern in list(self.known_beep_patterns)[:5]:  # Test top 5 patterns
                successes = 0
                
                for frame in frames[:10]:  # Test first 10 frames
                    success, decrypted, keystream = self.test_rc4_decrypt(
                        frame, self.fixed_hmi, cmi, beep_pattern
                    )
                    if success:
                        successes += 1
                
                if successes > 0:
                    success_rate = successes / min(10, len(frames))
                    print(f"  Pattern {beep_pattern}: {successes}/{min(10, len(frames))} matches ({success_rate*100:.1f}%)")
                    attack_successes.append({
                        'cmi': cmi,
                        'pattern': beep_pattern,
                        'success_rate': success_rate,
                        'frame_count': len(frames)
                    })
        
        self.results['encrypted_analysis'] = {
            'total_frames': len(all_encrypted_frames),
            'unique_cmis': len(cmi_groups),
            'cmi_distribution': {f"0x{k:08X}": len(v) for k, v in cmi_groups.items()},
            'attack_successes': attack_successes
        }
        
        return attack_successes
    
    def verify_lfsr_predictions(self):
        """Verify LFSR predictions against actual C-MI sequences"""
        print("\n=== VERIFYING LFSR PREDICTIONS ===")
        
        # Get C-MI sequences from encrypted databases
        cmi_sequences = []
        
        for db_path in self.encrypted_dbs:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT DISTINCT mi_full FROM E_{self.fixed_hmi:08X}_S0 ORDER BY id")
            cmis = [row[0] for row in cursor.fetchall()]
            
            if len(cmis) > 1:
                cmi_sequences.append(cmis)
                print(f"  {db_path}: {len(cmis)} C-MI values")
            
            conn.close()
        
        # Test LFSR predictions
        prediction_results = []
        
        for sequence in cmi_sequences:
            if len(sequence) < 2:
                continue
                
            correct_predictions = 0
            total_predictions = 0
            
            for i in range(len(sequence) - 1):
                current_cmi = sequence[i]
                actual_next = sequence[i + 1]
                predicted_next = self.calculate_lfsr_progression(current_cmi)
                
                if predicted_next == actual_next:
                    correct_predictions += 1
                
                total_predictions += 1
                
                if i < 5:  # Show first 5 predictions
                    print(f"    0x{current_cmi:08X} -> 0x{predicted_next:08X} (actual: 0x{actual_next:08X}) {'✓' if predicted_next == actual_next else '✗'}")
            
            accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
            prediction_results.append({
                'sequence_length': len(sequence),
                'correct_predictions': correct_predictions,
                'total_predictions': total_predictions,
                'accuracy': accuracy
            })
            
            print(f"  Accuracy: {correct_predictions}/{total_predictions} ({accuracy*100:.1f}%)")
        
        self.results['lfsr_verification'] = prediction_results
        return prediction_results
    
    def calculate_statistics(self):
        """Calculate comprehensive statistics"""
        print("\n=== CALCULATING STATISTICS ===")
        
        stats = {
            'unencrypted_frame_count': self.results['unencrypted_analysis']['total_frames'],
            'encrypted_frame_count': self.results['encrypted_analysis']['total_frames'],
            'total_frame_count': self.results['unencrypted_analysis']['total_frames'] + 
                                self.results['encrypted_analysis']['total_frames'],
            'unique_patterns_unencrypted': self.results['unencrypted_analysis']['unique_patterns'],
            'identified_beep_patterns': len(self.known_beep_patterns),
            'unique_cmis': self.results['encrypted_analysis']['unique_cmis'],
            'attack_success_rate': 0
        }
        
        # Calculate overall attack success rate
        if self.results['encrypted_analysis']['attack_successes']:
            success_rates = [s['success_rate'] for s in self.results['encrypted_analysis']['attack_successes']]
            stats['attack_success_rate'] = np.mean(success_rates)
            stats['attack_success_std'] = np.std(success_rates)
        
        # Calculate LFSR prediction accuracy
        if self.results['lfsr_verification']:
            accuracies = [r['accuracy'] for r in self.results['lfsr_verification']]
            stats['lfsr_accuracy_mean'] = np.mean(accuracies)
            stats['lfsr_accuracy_std'] = np.std(accuracies)
        
        self.results['statistics'] = stats
        
        print(f"Total frames analyzed: {stats['total_frame_count']}")
        print(f"  - Unencrypted: {stats['unencrypted_frame_count']}")
        print(f"  - Encrypted: {stats['encrypted_frame_count']}")
        print(f"Unique patterns in unencrypted: {stats['unique_patterns_unencrypted']}")
        print(f"Identified beep patterns: {stats['identified_beep_patterns']}")
        print(f"Attack success rate: {stats['attack_success_rate']*100:.1f}% ± {stats.get('attack_success_std', 0)*100:.1f}%")
        print(f"LFSR prediction accuracy: {stats.get('lfsr_accuracy_mean', 0)*100:.1f}% ± {stats.get('lfsr_accuracy_std', 0)*100:.1f}%")
        
        return stats
    
    def run_full_attack(self):
        """Run the complete attack methodology"""
        print("=== DMR ENCRYPTION FULL ATTACK ANALYSIS ===")
        print(f"Fixed H-MI: 0x{self.fixed_hmi:08X}")
        print(f"LFSR Polynomial: x^32 + x^4 + x^2 + 1")
        print("="*50)
        
        # Step 1: Analyze unencrypted frames
        beep_patterns = self.analyze_unencrypted_frames()
        
        # Step 2: Analyze encrypted frames
        attack_results = self.analyze_encrypted_frames()
        
        # Step 3: Verify LFSR predictions
        lfsr_results = self.verify_lfsr_predictions()
        
        # Step 4: Calculate statistics
        stats = self.calculate_statistics()
        
        # Save results
        with open('full_attack_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print("\n=== ATTACK SUMMARY ===")
        print(f"Successfully analyzed {stats['total_frame_count']} frames")
        print(f"Identified {len(self.known_beep_patterns)} beep patterns from unencrypted frames")
        print(f"Attack success rate: {stats['attack_success_rate']*100:.1f}%")
        print(f"LFSR prediction accuracy: {stats.get('lfsr_accuracy_mean', 0)*100:.1f}%")
        print("\nResults saved to full_attack_results.json")

# Add RC4 implementation
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


if __name__ == "__main__":
    attack = FullDMRAttack()
    attack.run_full_attack()