#!/usr/bin/env python3
"""
Master DMR Analysis - Works with all timestamped databases
"""
import sqlite3
import glob
import os
from datetime import datetime
from collections import defaultdict, Counter
import json
import numpy as np

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm"""
    lfsr = current_mi
    
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

def analyze_databases():
    """Analyze all DMR capture databases"""
    
    print("DMR Master Analysis")
    print("===================\n")
    
    # Find all databases
    db_files = glob.glob("dmr_capture_*.db")
    if not db_files:
        print("No DMR capture databases found!")
        print("Run captures using: ./dsd-fme -i rtl:0:145.125M:40 -fs -Z")
        return
    
    print(f"Found {len(db_files)} database(s):")
    for i, db in enumerate(sorted(db_files)):
        size = os.path.getsize(db) / 1024 / 1024  # MB
        mod_time = datetime.fromtimestamp(os.path.getmtime(db))
        print(f"  {i+1}. {db} ({size:.1f} MB) - {mod_time}")
    
    # Combine data from all databases
    all_data = defaultdict(list)
    h_mi_data = defaultdict(lambda: {'c_mi': [], 'timestamps': [], 'slots': set(), 'algids': set(), 'db_files': set()})
    
    for db_file in sorted(db_files):
        print(f"\nProcessing {db_file}...")
        
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get correlations
        cursor.execute("""
            SELECT header_mi, control_mi, timestamp, slot, algid 
            FROM dmr_correlations 
            ORDER BY timestamp
        """)
        correlations = cursor.fetchall()
        
        for h_mi, c_mi, timestamp, slot, algid in correlations:
            h_mi_data[h_mi]['c_mi'].append(c_mi)
            h_mi_data[h_mi]['timestamps'].append(timestamp)
            h_mi_data[h_mi]['slots'].add(slot)
            h_mi_data[h_mi]['algids'].add(algid)
            h_mi_data[h_mi]['db_files'].add(db_file)
        
        # Count AMBE frames
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master 
            WHERE type='table' AND (name LIKE 'H_%' OR name LIKE 'C_%')
        """)
        table_count = cursor.fetchone()[0]
        
        all_data['total_correlations'].append(len(correlations))
        all_data['total_tables'].append(table_count)
        
        conn.close()
    
    # Summary statistics
    print("\n=== SUMMARY ACROSS ALL DATABASES ===")
    print(f"Total databases: {len(db_files)}")
    print(f"Total correlations: {sum(all_data['total_correlations'])}")
    print(f"Total AMBE tables: {sum(all_data['total_tables'])}")
    print(f"Unique H-MI values: {len(h_mi_data)}")
    
    # Analyze each H-MI (radio)
    pattern_models = {}
    
    for h_mi, data in h_mi_data.items():
        print(f"\n=== H-MI: 0x{h_mi:08X} ===")
        print(f"Total C-MI values: {len(data['c_mi'])}")
        print(f"Databases: {len(data['db_files'])}")
        print(f"Slots: {data['slots']}")
        print(f"Algorithm IDs: {data['algids']}")
        
        # Sort C-MI values by timestamp
        sorted_pairs = sorted(zip(data['timestamps'], data['c_mi']))
        c_mi_sequence = [pair[1] for pair in sorted_pairs]
        
        # Generate LFSR sequence
        lfsr_sequence = []
        current = h_mi
        for _ in range(10000):  # Generate plenty
            current = lfsr_next(current)
            lfsr_sequence.append(current)
        
        # Create position lookup
        lfsr_lookup = {val: idx for idx, val in enumerate(lfsr_sequence)}
        
        # Find positions
        positions = []
        for c_mi in c_mi_sequence:
            if c_mi in lfsr_lookup:
                positions.append(lfsr_lookup[c_mi])
        
        # Calculate jumps
        jumps = []
        for i in range(len(positions) - 1):
            jump = positions[i+1] - positions[i]
            jumps.append(jump)
        
        # Analyze jump pattern
        jump_counter = Counter(jumps)
        print(f"\nJump distribution (top 10):")
        for jump, count in jump_counter.most_common(10):
            percentage = (count / len(jumps)) * 100 if jumps else 0
            print(f"  Jump {jump:3d}: {count:4d} times ({percentage:5.1f}%)")
        
        # Build pattern model
        pattern_models[h_mi] = {
            'jump_distribution': dict(jump_counter),
            'total_frames': len(c_mi_sequence),
            'sequence_length': len(set(c_mi_sequence)),
            'predictability': jump_counter[1] / len(jumps) * 100 if jumps else 0
        }
    
    # Save combined pattern model
    output_file = 'dmr_master_pattern.json'
    with open(output_file, 'w') as f:
        json.dump({
            'databases': db_files,
            'h_mi_patterns': {f"0x{k:08X}": v for k, v in pattern_models.items()},
            'total_frames': sum(v['total_frames'] for v in pattern_models.values()),
            'analysis_date': datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\n=== PATTERN MODEL SAVED ===")
    print(f"Output: {output_file}")
    
    # Attack feasibility assessment
    total_frames = sum(v['total_frames'] for v in pattern_models.values())
    print(f"\n=== ATTACK FEASIBILITY ===")
    print(f"Total frames collected: {total_frames}")
    
    if total_frames < 1000:
        print(f"Status: Need ~{1000 - total_frames} more frames")
        print("Recommendation: Capture more data")
    else:
        avg_predictability = np.mean([v['predictability'] for v in pattern_models.values()])
        print(f"Average predictability: {avg_predictability:.1f}%")
        print("Status: Sufficient data for attack")
        
        if avg_predictability > 25:
            print("Vulnerability: HIGH - LFSR pattern is predictable")
        else:
            print("Vulnerability: MODERATE - Complex interleaving detected")
    
    return pattern_models

def predict_next_frames(h_mi, last_c_mi, count=10):
    """Predict next C-MI values based on pattern model"""
    
    # Load pattern model
    try:
        with open('dmr_master_pattern.json', 'r') as f:
            model = json.load(f)
        
        h_mi_key = f"0x{h_mi:08X}"
        if h_mi_key not in model['h_mi_patterns']:
            print(f"No pattern model for H-MI {h_mi_key}")
            return []
        
        pattern = model['h_mi_patterns'][h_mi_key]
        jump_dist = pattern['jump_distribution']
        
        # Find most likely jumps
        jumps = sorted(jump_dist.items(), key=lambda x: x[1], reverse=True)
        most_likely = int(jumps[0][0]) if jumps else 1
        
        print(f"\nPredicting next {count} C-MI values:")
        print(f"Most likely jump: {most_likely}")
        
        # Generate predictions
        predictions = []
        current = last_c_mi
        
        # Generate LFSR sequence
        lfsr_seq = []
        lfsr_current = h_mi
        for _ in range(1000):
            lfsr_current = lfsr_next(lfsr_current)
            lfsr_seq.append(lfsr_current)
        
        # Find current position
        try:
            current_pos = lfsr_seq.index(current)
        except ValueError:
            print("Current C-MI not found in LFSR sequence!")
            return []
        
        # Predict next values
        for i in range(count):
            next_pos = current_pos + most_likely
            if 0 <= next_pos < len(lfsr_seq):
                next_val = lfsr_seq[next_pos]
                predictions.append(next_val)
                print(f"  {i+1}: 0x{next_val:08X}")
                current_pos = next_pos
            else:
                print(f"  {i+1}: Position out of range")
                break
        
        return predictions
        
    except FileNotFoundError:
        print("No pattern model found. Run analysis first!")
        return []

if __name__ == "__main__":
    # Run analysis
    pattern_models = analyze_databases()
    
    # If we have data, try prediction
    if pattern_models:
        h_mi = list(pattern_models.keys())[0]
        print(f"\n=== PREDICTION TEST ===")
        
        # Get last C-MI from most recent database
        db_files = sorted(glob.glob("dmr_capture_*.db"))
        if db_files:
            latest_db = db_files[-1]
            conn = sqlite3.connect(latest_db)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT control_mi FROM dmr_correlations 
                WHERE header_mi = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (h_mi,))
            
            result = cursor.fetchone()
            if result:
                last_c_mi = result[0]
                print(f"Last C-MI from {latest_db}: 0x{last_c_mi:08X}")
                
                # Predict next values
                predictions = predict_next_frames(h_mi, last_c_mi, 10)
                
                print("\nTo verify predictions:")
                print("1. Start new capture")
                print("2. Compare captured C-MI values with predictions")
                print("3. Refine pattern model based on accuracy")
            
            conn.close()