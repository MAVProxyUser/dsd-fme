#!/usr/bin/env python3
"""
Final analysis of call duration vs LFSR jump patterns
Using the correct LFSR calculation method
"""

import sqlite3
import pandas as pd
import numpy as np
from glob import glob
from collections import defaultdict, Counter
import json
import matplotlib.pyplot as plt
from datetime import datetime

def lfsr_next(current_mi):
    """Calculate the next MI value using the LFSR algorithm (32 steps)"""
    lfsr = current_mi
    
    for _ in range(32):
        bit = ((lfsr >> 31) ^ (lfsr >> 3) ^ (lfsr >> 1)) & 0x1
        lfsr = (lfsr << 1) | bit
    
    return lfsr & 0xFFFFFFFF

def build_lfsr_lookup(start_mi, length=10000):
    """Build lookup table for LFSR sequence positions"""
    sequence = []
    current = start_mi
    
    for i in range(length):
        current = lfsr_next(current)
        sequence.append(current)
    
    # Create bidirectional lookup
    position_lookup = {val: idx for idx, val in enumerate(sequence)}
    
    return sequence, position_lookup

def analyze_call_sessions():
    """Extract and analyze call sessions"""
    
    H_MI = 1821029943  # 0x6C8AB637
    db_files = sorted(glob("dmr_capture_*.db"))
    
    # Build LFSR lookup table
    print("Building LFSR lookup table...")
    lfsr_sequence, lfsr_lookup = build_lfsr_lookup(H_MI)
    
    all_sessions = []
    
    for db_file in db_files:
        print(f"Processing {db_file}")
        conn = sqlite3.connect(db_file)
        
        # Get correlations
        query = f"""
        SELECT control_mi, timestamp
        FROM dmr_correlations
        WHERE header_mi = {H_MI}
        ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            conn.close()
            continue
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Find sessions (gaps > 5 seconds)
        df['time_gap'] = df['timestamp'].diff().dt.total_seconds()
        df['new_session'] = df['time_gap'] > 5
        df['session_id'] = df['new_session'].cumsum()
        
        # Analyze each session
        for session_id, session_data in df.groupby('session_id'):
            if len(session_data) < 3:
                continue
            
            duration = (session_data['timestamp'].iloc[-1] - 
                       session_data['timestamp'].iloc[0]).total_seconds()
            
            c_mis = session_data['control_mi'].tolist()
            
            # Find positions in LFSR sequence
            positions = []
            for c_mi in c_mis:
                if c_mi in lfsr_lookup:
                    positions.append(lfsr_lookup[c_mi])
            
            # Calculate jumps (position differences)
            jumps = []
            for i in range(1, len(positions)):
                jump = positions[i] - positions[i-1]
                jumps.append(jump)
            
            if jumps:  # Only include sessions with valid jumps
                all_sessions.append({
                    'duration': duration,
                    'c_mi_count': len(c_mis),
                    'valid_positions': len(positions),
                    'jumps': jumps,
                    'start_c_mi': c_mis[0],
                    'end_c_mi': c_mis[-1],
                    'db': db_file
                })
        
        conn.close()
    
    return all_sessions

def analyze_jump_patterns(sessions):
    """Analyze jump patterns by call duration"""
    
    # Load master jump distribution for comparison
    with open('dmr_master_pattern.json', 'r') as f:
        master_data = json.load(f)
    
    master_jumps = master_data['h_mi_patterns']['0x6C8AB637']['jump_distribution']
    master_jumps = {int(k): v for k, v in master_jumps.items()}
    
    # Create visualizations
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Jump distribution by duration
    duration_bins = [(0, 10), (10, 30), (30, 60), (60, 120), (120, float('inf'))]
    bin_labels = ['0-10s', '10-30s', '30-60s', '60-120s', '120s+']
    
    jump_by_duration = defaultdict(lambda: defaultdict(int))
    session_counts = defaultdict(int)
    
    for session in sessions:
        duration = session['duration']
        
        for (low, high), label in zip(duration_bins, bin_labels):
            if low <= duration < high:
                session_counts[label] += 1
                for jump in session['jumps']:
                    jump_by_duration[label][jump] += 1
                break
    
    # Focus on common jumps
    common_jumps = [1, -1, 2, 3, -2, 4]
    x = np.arange(len(bin_labels))
    width = 0.8
    
    bottom = np.zeros(len(bin_labels))
    colors = plt.cm.tab10(range(len(common_jumps)))
    
    for i, jump in enumerate(common_jumps):
        values = []
        for label in bin_labels:
            total = sum(jump_by_duration[label].values())
            if total > 0:
                percent = jump_by_duration[label][jump] / total * 100
            else:
                percent = 0
            values.append(percent)
        
        ax1.bar(x, values, width, bottom=bottom, 
                label=f'Jump {jump:+d}', color=colors[i])
        bottom += values
    
    ax1.set_xlabel('Call Duration')
    ax1.set_ylabel('Jump Distribution (%)')
    ax1.set_title('LFSR Jump Pattern Distribution by Call Duration')
    ax1.set_xticks(x)
    ax1.set_xticklabels([f'{l}\n(n={session_counts[l]})' for l in bin_labels])
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Average absolute jump by duration
    avg_jumps = {}
    
    for label in bin_labels:
        jumps_in_bin = []
        for session in sessions:
            duration = session['duration']
            for (low, high), bin_label in zip(duration_bins, bin_labels):
                if low <= duration < high and bin_label == label:
                    jumps_in_bin.extend([abs(j) for j in session['jumps']])
                    break
        
        if jumps_in_bin:
            avg_jumps[label] = {
                'mean': np.mean(jumps_in_bin),
                'std': np.std(jumps_in_bin),
                'count': len(jumps_in_bin)
            }
    
    labels = list(avg_jumps.keys())
    means = [avg_jumps[l]['mean'] for l in labels]
    stds = [avg_jumps[l]['std'] for l in labels]
    
    x = np.arange(len(labels))
    ax2.bar(x, means, yerr=stds, capsize=5, alpha=0.7, color='skyblue')
    ax2.set_xlabel('Call Duration')
    ax2.set_ylabel('Average |Jump|')
    ax2.set_title('Average Absolute Jump Size by Call Duration')
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.grid(True, alpha=0.3)
    
    # Add count annotations
    for i, label in enumerate(labels):
        count = avg_jumps[label]['count']
        ax2.text(i, means[i] + stds[i] + 0.1, f'n={count}', 
                ha='center', va='bottom')
    
    # 3. Call duration histogram
    durations = [s['duration'] for s in sessions]
    ax3.hist(durations, bins=30, edgecolor='black', alpha=0.7, color='orange')
    ax3.set_xlabel('Duration (seconds)')
    ax3.set_ylabel('Number of Calls')
    ax3.set_title('Distribution of Call Durations')
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(0, max(durations) * 1.1)
    
    # Statistics
    mean_dur = np.mean(durations)
    median_dur = np.median(durations)
    ax3.axvline(mean_dur, color='red', linestyle='--', 
                label=f'Mean: {mean_dur:.1f}s')
    ax3.axvline(median_dur, color='green', linestyle='--', 
                label=f'Median: {median_dur:.1f}s')
    ax3.legend()
    
    # 4. Jump pattern entropy by duration
    entropy_by_duration = {}
    
    for label in bin_labels:
        jump_dist = jump_by_duration[label]
        if jump_dist:
            total = sum(jump_dist.values())
            probabilities = [count/total for count in jump_dist.values()]
            # Calculate Shannon entropy
            entropy = -sum(p * np.log2(p) for p in probabilities if p > 0)
            entropy_by_duration[label] = entropy
    
    if entropy_by_duration:
        labels = list(entropy_by_duration.keys())
        entropies = list(entropy_by_duration.values())
        
        x = np.arange(len(labels))
        ax4.bar(x, entropies, alpha=0.7, color='green')
        ax4.set_xlabel('Call Duration')
        ax4.set_ylabel('Pattern Entropy (bits)')
        ax4.set_title('Jump Pattern Entropy by Call Duration')
        ax4.set_xticks(x)
        ax4.set_xticklabels(labels)
        ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('call_duration_jump_correlation_final.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Detailed statistics
    print("\n=== JUMP PATTERN ANALYSIS BY CALL DURATION ===")
    
    for label in bin_labels:
        if label in jump_by_duration and jump_by_duration[label]:
            print(f"\n{label} ({session_counts[label]} sessions):")
            
            jump_dist = jump_by_duration[label]
            total = sum(jump_dist.values())
            
            # Top jumps
            top_jumps = sorted(jump_dist.items(), key=lambda x: x[1], reverse=True)[:5]
            for jump, count in top_jumps:
                percent = count / total * 100
                print(f"  Jump {jump:+3d}: {percent:5.1f}% ({count} occurrences)")
            
            # Compare to master distribution
            master_total = sum(master_jumps.values())
            print("\n  Master distribution for comparison:")
            for jump, count in sorted(master_jumps.items(), 
                                     key=lambda x: x[1], reverse=True)[:5]:
                percent = count / master_total * 100
                print(f"  Jump {jump:+3d}: {percent:5.1f}% ({count} occurrences)")
    
    # Statistical tests
    print("\n=== STATISTICAL ANALYSIS ===")
    
    # Test if jump patterns differ by duration
    short_jumps = []
    long_jumps = []
    
    for session in sessions:
        if session['duration'] < 10:
            short_jumps.extend(session['jumps'])
        elif session['duration'] > 60:
            long_jumps.extend(session['jumps'])
    
    if short_jumps and long_jumps:
        # Compare distributions
        short_counter = Counter(short_jumps)
        long_counter = Counter(long_jumps)
        
        all_jumps = set(short_counter.keys()) | set(long_counter.keys())
        common_jumps = sorted([j for j in all_jumps if -10 <= j <= 10])
        
        short_dist = [short_counter.get(j, 0) for j in common_jumps]
        long_dist = [long_counter.get(j, 0) for j in common_jumps]
        
        # Chi-square test
        from scipy.stats import chi2_contingency
        chi2, p_value, dof, expected = chi2_contingency([short_dist, long_dist])
        
        print(f"\nShort calls (<10s): {len(short_jumps)} jumps")
        print(f"Long calls (>60s): {len(long_jumps)} jumps")
        print(f"Chi-square test: χ² = {chi2:.3f}, p = {p_value:.6f}")
        
        if p_value < 0.05:
            print("Jump patterns differ significantly between short and long calls")
        else:
            print("No significant difference in jump patterns")
    
    # Overall correlation
    all_durations = [s['duration'] for s in sessions]
    all_avg_jumps = [np.mean([abs(j) for j in s['jumps']]) for s in sessions]
    
    if all_durations and all_avg_jumps:
        correlation = np.corrcoef(all_durations, all_avg_jumps)[0, 1]
        print(f"\nCorrelation between duration and average |jump|: {correlation:.3f}")
    
    return sessions

def main():
    print("Call Duration vs LFSR Jump Pattern Analysis")
    print("=" * 40)
    
    sessions = analyze_call_sessions()
    
    if sessions:
        analyze_jump_patterns(sessions)
        
        # Summary
        print(f"\n=== SUMMARY ===")
        print(f"Total sessions analyzed: {len(sessions)}")
        total_jumps = sum(len(s['jumps']) for s in sessions)
        print(f"Total jumps analyzed: {total_jumps}")
        
        print("\nResults saved to call_duration_jump_correlation_final.png")
    else:
        print("No session data found")

if __name__ == "__main__":
    main()