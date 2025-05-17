#!/usr/bin/env python3
"""
DMR Pattern Analysis - Find common patterns in encrypted frames
"""

import sqlite3
import json
from collections import Counter, defaultdict
import binascii

class DMRPatternAnalysis:
    def __init__(self):
        self.databases = [
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
        
    def analyze_frame_positions(self):
        """Analyze frames by their position in transmissions"""
        print("=== ANALYZING FRAME POSITIONS ===\n")
        
        position_patterns = {
            'first_frames': Counter(),
            'last_frames': Counter(),
            'second_frames': Counter(),
            'penultimate_frames': Counter()
        }
        
        for db_path in self.databases:
            print(f"Analyzing {db_path}...")
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get all C_ tables (control channel)
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
                tables = cursor.fetchall()
                
                for table_name, in tables:
                    # Get frames ordered by ID
                    cursor.execute(f"SELECT id, ambe_hex FROM {table_name} ORDER BY id")
                    frames = cursor.fetchall()
                    
                    if len(frames) >= 15:  # Standard DMR transmission length
                        # First frame of transmission
                        position_patterns['first_frames'][frames[0][1]] += 1
                        
                        # Second frame (often beep)
                        position_patterns['second_frames'][frames[1][1]] += 1
                        
                        # Penultimate frame (often beep)
                        position_patterns['penultimate_frames'][frames[-2][1]] += 1
                        
                        # Last frame
                        position_patterns['last_frames'][frames[-1][1]] += 1
                
                conn.close()
                
            except Exception as e:
                print(f"  Error: {e}")
        
        # Find most common patterns in each position
        results = {}
        for position, counter in position_patterns.items():
            print(f"\n=== TOP {position.upper()} ===")
            top_patterns = counter.most_common(10)
            results[position] = []
            
            for pattern, count in top_patterns:
                if count > 1:  # Must appear more than once
                    results[position].append((pattern, count))
                    print(f"{pattern}: {count} occurrences")
        
        return results
    
    def analyze_pattern_similarity(self):
        """Find similar patterns that might be the same beep with slight variations"""
        print("\n=== ANALYZING PATTERN SIMILARITY ===\n")
        
        all_patterns = Counter()
        
        # Collect all patterns
        for db_path in self.databases:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
                tables = cursor.fetchall()
                
                for table_name, in tables[:20]:  # Limit to first 20 tables
                    cursor.execute(f"SELECT ambe_hex FROM {table_name} LIMIT 100")
                    frames = cursor.fetchall()
                    
                    for frame, in frames:
                        all_patterns[frame] += 1
                
                conn.close()
                
            except Exception as e:
                print(f"  Error: {e}")
        
        # Group similar patterns
        pattern_groups = defaultdict(list)
        
        for pattern1, count1 in all_patterns.most_common(100):
            if count1 < 3:  # Skip rare patterns
                continue
                
            # Group by first 8 characters (similar start)
            prefix = pattern1[:8]
            pattern_groups[prefix].append((pattern1, count1))
        
        print("=== SIMILAR PATTERN GROUPS ===")
        potential_beeps = []
        
        for prefix, patterns in pattern_groups.items():
            if len(patterns) > 2:  # Multiple similar patterns
                print(f"\nGroup {prefix}:")
                for pattern, count in patterns:
                    print(f"  {pattern}: {count} occurrences")
                
                # Add most common pattern from group as potential beep
                patterns.sort(key=lambda x: x[1], reverse=True)
                potential_beeps.append(patterns[0][0])
        
        return potential_beeps
    
    def find_recurring_patterns(self):
        """Find patterns that recur across multiple databases"""
        print("\n=== FINDING RECURRING PATTERNS ===\n")
        
        pattern_dbs = defaultdict(set)
        pattern_counts = Counter()
        
        for db_path in self.databases:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Look at both encrypted and unencrypted frames
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S0'")
                tables = cursor.fetchall()
                
                for table_name, in tables:
                    cursor.execute(f"SELECT ambe_hex FROM {table_name} LIMIT 500")
                    frames = cursor.fetchall()
                    
                    for frame, in frames:
                        pattern_dbs[frame].add(db_path)
                        pattern_counts[frame] += 1
                
                conn.close()
                
            except Exception as e:
                print(f"  Error: {e}")
        
        # Find patterns that appear in multiple databases
        multi_db_patterns = []
        
        print("=== PATTERNS IN MULTIPLE DATABASES ===")
        for pattern, dbs in pattern_dbs.items():
            if len(dbs) > 1 and pattern_counts[pattern] > 5:
                multi_db_patterns.append(pattern)
                print(f"{pattern}: {pattern_counts[pattern]} total occurrences in {len(dbs)} databases")
        
        return multi_db_patterns
    
    def run_comprehensive_analysis(self):
        """Run comprehensive pattern analysis"""
        print("=== COMPREHENSIVE DMR PATTERN ANALYSIS ===\n")
        
        # Analyze frame positions
        position_results = self.analyze_frame_positions()
        
        # Analyze pattern similarity
        similar_patterns = self.analyze_pattern_similarity()
        
        # Find recurring patterns
        recurring_patterns = self.find_recurring_patterns()
        
        # Combine all results
        all_candidates = set()
        
        # Add patterns from specific positions
        for position, patterns in position_results.items():
            for pattern, count in patterns:
                if count > 3:  # Must appear frequently
                    all_candidates.add(pattern)
        
        # Add similar patterns
        all_candidates.update(similar_patterns)
        
        # Add recurring patterns
        all_candidates.update(recurring_patterns)
        
        # Convert to list
        final_candidates = list(all_candidates)
        
        print("\n=== FINAL BEEP CANDIDATES ===")
        print(f"Found {len(final_candidates)} potential beep patterns\n")
        
        # If we still don't have patterns, use some known AMBE patterns
        if len(final_candidates) < 5:
            known_patterns = [
                "AC6422C8BDF60000",  # Common beep pattern
                "ACE63EC8BDF60000",  # Variant
                "286222C8BD740000",  # Another variant
                "AC663EC2FC5A0A00",  # Different beep
                "1114A47380000000"   # Silence
            ]
            final_candidates.extend(known_patterns)
            print("Added known AMBE patterns for testing")
        
        for i, pattern in enumerate(final_candidates[:20]):
            print(f"{i+1}. {pattern}")
        
        # Save results
        results = {
            'position_patterns': {k: [(p, c) for p, c in v] for k, v in position_results.items()},
            'similar_patterns': similar_patterns,
            'recurring_patterns': recurring_patterns,
            'final_candidates': final_candidates
        }
        
        with open('dmr_pattern_analysis.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print("\nResults saved to dmr_pattern_analysis.json")
        
        return final_candidates

if __name__ == "__main__":
    analyzer = DMRPatternAnalysis()
    patterns = analyzer.run_comprehensive_analysis()