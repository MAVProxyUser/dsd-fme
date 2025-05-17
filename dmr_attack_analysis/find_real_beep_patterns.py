#!/usr/bin/env python3
"""
Find real beep patterns in DMR captures
"""

import sqlite3
import json
from collections import Counter
import numpy as np

class DMRBeepFinder:
    def __init__(self):
        self.all_databases = [
            'dmr_capture_20250517_005052.db',
            'dmr_capture_20250517_005411.db', 
            'dmr_capture_20250517_010359.db',
            'dmr_capture_20250517_013614.db',
            'dmr_capture_20250517_013819.db',
            'dmr_capture_20250517_021613.db',
            'dmr_capture_20250517_025824.db',
            'dmr_capture_20250517_033740.db'
        ]
        
        self.fixed_hmi = 0x6C8AB637
        self.patterns = Counter()
        
    def find_beep_patterns(self):
        """Find actual beep patterns from transmission boundaries"""
        print("=== FINDING REAL BEEP PATTERNS ===\n")
        
        # Look for patterns at the start/end of transmissions
        start_patterns = Counter()
        end_patterns = Counter()
        
        for db_path in self.all_databases:
            print(f"Analyzing {db_path}...")
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [t[0] for t in cursor.fetchall()]
                
                for table in tables:
                    if table.startswith(('C_', 'H_', 'U_')):
                        # Get frames ordered by ID
                        cursor.execute(f"SELECT id, ambe_hex FROM {table} ORDER BY id")
                        frames = cursor.fetchall()
                        
                        if len(frames) > 5:
                            # Get first 3 frames (potential beep start)
                            for i in range(min(3, len(frames))):
                                start_patterns[frames[i][1]] += 1
                            
                            # Get last 3 frames (potential beep end)  
                            for i in range(max(0, len(frames)-3), len(frames)):
                                end_patterns[frames[i][1]] += 1
                
                conn.close()
                
            except Exception as e:
                print(f"  Error: {e}")
        
        print("\n=== TOP START PATTERNS ===")
        for pattern, count in start_patterns.most_common(20):
            print(f"{pattern}: {count} occurrences")
        
        print("\n=== TOP END PATTERNS ===")
        for pattern, count in end_patterns.most_common(20):
            print(f"{pattern}: {count} occurrences")
        
        # Find most common patterns overall
        all_patterns = start_patterns + end_patterns
        
        print("\n=== MOST COMMON PATTERNS (LIKELY BEEPS) ===")
        beep_candidates = []
        for pattern, count in all_patterns.most_common(20):
            if count > 10:  # Must appear frequently
                beep_candidates.append(pattern)
                print(f"{pattern}: {count} total occurrences")
        
        return beep_candidates
    
    def test_patterns_against_encrypted(self, beep_patterns):
        """Test beep patterns against encrypted frames"""
        print("\n=== TESTING PATTERNS AGAINST ENCRYPTED FRAMES ===")
        
        success_count = 0
        test_count = 0
        
        for db_path in self.all_databases[:3]:  # Test first 3 databases
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get encrypted frames from tables with our fixed H-MI
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
                tables = cursor.fetchall()
                
                for table_name, in tables[:5]:  # Test first 5 tables
                    # Get frames from this table
                    cursor.execute(f"SELECT ambe_hex FROM {table_name} WHERE algid = 1 LIMIT 10")
                    frames = cursor.fetchall()
                    
                    for frame, in frames:
                        test_count += 1
                        
                        # Simple check: do any patterns appear frequently?
                        for pattern in beep_patterns[:5]:
                            if pattern in all_patterns and all_patterns[pattern] > 20:
                                success_count += 1
                                break
                
                conn.close()
                
            except Exception as e:
                print(f"  Error: {e}")
        
        success_rate = success_count / test_count if test_count > 0 else 0
        print(f"\nPattern match rate: {success_count}/{test_count} ({success_rate*100:.1f}%)")
        
        return success_rate
    
    def extract_unencrypted_patterns(self):
        """Extract patterns from unencrypted frames"""
        print("\n=== EXTRACTING UNENCRYPTED PATTERNS ===")
        
        unencrypted_patterns = Counter()
        
        for db_path in self.all_databases:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check for unencrypted tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'U_%'")
                u_tables = cursor.fetchall()
                
                for table_name, in u_tables:
                    cursor.execute(f"SELECT ambe_hex FROM {table_name}")
                    frames = cursor.fetchall()
                    
                    for frame, in frames:
                        unencrypted_patterns[frame] += 1
                
                conn.close()
                
            except Exception as e:
                print(f"  Error: {e}")
        
        print(f"\nTotal unique unencrypted patterns: {len(unencrypted_patterns)}")
        
        # Find recurring patterns (possible beeps)
        recurring = []
        for pattern, count in unencrypted_patterns.most_common(50):
            if count > 5:  # Appears more than 5 times
                recurring.append(pattern)
                print(f"{pattern}: {count} occurrences")
        
        return recurring
    
    def run_analysis(self):
        """Run complete beep pattern analysis"""
        print("=== DMR BEEP PATTERN ANALYSIS ===\n")
        
        # Find patterns at transmission boundaries
        boundary_patterns = self.find_beep_patterns()
        
        # Extract patterns from unencrypted frames
        unencrypted_patterns = self.extract_unencrypted_patterns()
        
        # Combine all patterns
        all_candidates = list(set(boundary_patterns + unencrypted_patterns))
        
        print(f"\n=== FINAL BEEP CANDIDATES ===")
        print(f"Found {len(all_candidates)} potential beep patterns")
        
        # Save results
        results = {
            'boundary_patterns': boundary_patterns,
            'unencrypted_patterns': unencrypted_patterns,
            'all_candidates': all_candidates
        }
        
        with open('real_beep_patterns.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print("\nResults saved to real_beep_patterns.json")
        
        return all_candidates

if __name__ == "__main__":
    finder = DMRBeepFinder()
    patterns = finder.run_analysis()