#!/usr/bin/env python3
"""Calculate data requirements for real-time C-MI prediction corpus"""

import sqlite3
import glob
from collections import defaultdict
from datetime import datetime
import numpy as np

def analyze_cmi_patterns():
    # Find all DMR capture databases in current directory as well
    db_files = glob.glob("/home/ubuntu/DMR_Captures/dmr_capture_*.db")
    db_files.extend(glob.glob("dmr_capture_*.db"))
    
    total_superframes = 0
    unique_cmis = set()
    cmi_transitions = defaultdict(list)
    cmi_frame_types = defaultdict(lambda: defaultdict(int))
    session_data = []
    
    for db_file in db_files:
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get superframe count
            cursor.execute("SELECT COUNT(*) FROM superframes")
            count = cursor.fetchone()[0]
            total_superframes += count
            
            # Get unique C-MI values (excluding 0)
            cursor.execute("SELECT DISTINCT c_mi FROM superframes WHERE c_mi IS NOT NULL AND c_mi != 0")
            db_cmis = [row[0] for row in cursor.fetchall()]
            unique_cmis.update(db_cmis)
            
            # Track C-MI transitions within sessions
            cursor.execute('''
                SELECT id, c_mi, sync_type, flco, group_call, encrypted 
                FROM superframes 
                WHERE c_mi IS NOT NULL AND c_mi != 0
                ORDER BY id
            ''')
            
            prev_cmi = None
            session_cmis = []
            
            for _, cmi, sync_type, flco, group_call, encrypted in cursor.fetchall():
                if cmi:
                    session_cmis.append(cmi)
                    
                    # Track frame type associations
                    frame_key = f"{sync_type}_FLCO{flco}_{'GRP' if group_call else 'IND'}_{'ENC' if encrypted else 'CLR'}"
                    cmi_frame_types[cmi][frame_key] += 1
                    
                    # Track transitions
                    if prev_cmi is not None:
                        cmi_transitions[prev_cmi].append(cmi)
                    prev_cmi = cmi
            
            if session_cmis:
                session_data.append({
                    'file': db_file,
                    'cmi_count': len(session_cmis),
                    'unique_cmis': len(set(session_cmis))
                })
                
            conn.close()
            
        except Exception as e:
            print(f"Error processing {db_file}: {e}")
    
    # Calculate statistics
    print("=== C-MI Corpus Requirements Analysis ===\n")
    
    print(f"Total databases analyzed: {len(db_files)}")
    print(f"Total superframes: {total_superframes}")
    print(f"Unique C-MI values seen: {len(unique_cmis)}")
    
    # Transition analysis
    transition_counts = []
    for src_cmi, destinations in cmi_transitions.items():
        transition_counts.extend([len(set(destinations)), len(destinations)])
    
    if transition_counts:
        print(f"\nTransition Statistics:")
        print(f"  Average unique transitions per C-MI: {np.mean([c for i, c in enumerate(transition_counts) if i % 2 == 0]):.1f}")
        print(f"  Average total transitions per C-MI: {np.mean([c for i, c in enumerate(transition_counts) if i % 2 == 1]):.1f}")
    
    # Session analysis
    if session_data:
        session_lengths = [s['cmi_count'] for s in session_data]
        unique_per_session = [s['unique_cmis'] for s in session_data]
        
        print(f"\nSession Statistics:")
        print(f"  Average C-MIs per session: {np.mean(session_lengths):.1f}")
        print(f"  Average unique C-MIs per session: {np.mean(unique_per_session):.1f}")
        print(f"  Max C-MIs in a session: {np.max(session_lengths)}")
        print(f"  Min C-MIs in a session: {np.min(session_lengths)}")
    
    # Frame type correlation
    print(f"\nFrame Type Correlations:")
    for cmi in list(unique_cmis)[:5]:  # Sample first 5
        print(f"\n  C-MI {hex(cmi)}:")
        for frame_type, count in cmi_frame_types.get(cmi, {}).items():
            print(f"    {frame_type}: {count}")
    
    # Prediction confidence calculation using LFSR
    print(f"\n=== Prediction Capability Analysis ===")
    
    # Test LFSR prediction accuracy
    def dmr_lfsr_next(lfsr):
        """Calculate next LFSR state using DMR polynomial x^32 + x^4 + x^2 + 1"""
        for _ in range(32):
            bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
            lfsr = ((lfsr << 1) | bit) & 0xFFFFFFFF
        return lfsr
    
    # Check prediction accuracy
    correct_predictions = 0
    total_transitions = 0
    
    for src_cmi, destinations in cmi_transitions.items():
        if src_cmi == 0:
            continue
        predicted_next = dmr_lfsr_next(src_cmi)
        for dest in destinations:
            total_transitions += 1
            if dest == predicted_next:
                correct_predictions += 1
    
    if total_transitions > 0:
        prediction_rate = correct_predictions / total_transitions
        print(f"LFSR prediction accuracy: {prediction_rate*100:.1f}%")
    else:
        print("No valid transitions to analyze")
    
    # Estimate data needed for reliable prediction
    print(f"\nData Requirements for Reliable Prediction:")
    
    # Based on LFSR period of 2^15-1 = 32,767
    lfsr_period = 2**15 - 1
    coverage = len(unique_cmis) / lfsr_period * 100
    
    print(f"  LFSR period: {lfsr_period:,}")
    print(f"  Current coverage: {coverage:.2f}%")
    print(f"  C-MIs needed for 50% coverage: {lfsr_period//2:,}")
    print(f"  C-MIs needed for 95% coverage: {int(lfsr_period*0.95):,}")
    
    # Time estimates
    if session_data:
        avg_cmis_per_hour = np.mean(session_lengths) * 12  # 5-min captures
        hours_for_50 = (lfsr_period//2 - len(unique_cmis)) / avg_cmis_per_hour
        hours_for_95 = (int(lfsr_period*0.95) - len(unique_cmis)) / avg_cmis_per_hour
        
        print(f"\nTime Estimates (at current rate):")
        print(f"  Average C-MIs per hour: {avg_cmis_per_hour:.0f}")
        print(f"  Hours for 50% coverage: {hours_for_50:.1f}")
        print(f"  Hours for 95% coverage: {hours_for_95:.1f}")
    
    print(f"\n=== Recommendations ===")
    print(f"1. Current data ({len(unique_cmis)} C-MIs) provides {coverage:.2f}% LFSR coverage")
    print(f"2. Real-time prediction confidence: {'HIGH' if coverage > 5 else 'LOW'}")
    if 'hours_for_50' in locals():
        print(f"3. For reliable prediction, need ~{hours_for_50:.0f} more hours of capture")
    else:
        print(f"3. Need to capture data to estimate time requirements")
    print(f"4. Frame type correlation can improve prediction accuracy")
    
    return unique_cmis, cmi_transitions, cmi_frame_types

if __name__ == "__main__":
    unique_cmis, transitions, frame_types = analyze_cmi_patterns()