#!/usr/bin/env python3
"""
Analyze how LFSR jump patterns correlate with call duration
Using correct decimal values for H-MI
"""

import sqlite3
import pandas as pd
import numpy as np
from glob import glob
from collections import defaultdict
import json
import matplotlib.pyplot as plt
from datetime import datetime

def load_master_jumps():
    """Load the actual jump distribution from master analysis"""
    with open('dmr_master_pattern.json', 'r') as f:
        data = json.load(f)
    
    jump_dist = data['h_mi_patterns']['0x6C8AB637']['jump_distribution']
    return {int(k): v for k, v in jump_dist.items()}

def analyze_sessions():
    """Analyze call sessions and their LFSR patterns"""
    
    # Correct H-MI value in decimal
    H_MI_6C8AB637 = 1821029943
    
    db_files = sorted(glob("dmr_capture_*.db"))
    all_sessions = []
    
    for db_file in db_files:
        print(f"Processing {db_file}")
        conn = sqlite3.connect(db_file)
        
        # Get correlations for our H-MI
        query = f"""
        SELECT control_mi, timestamp
        FROM dmr_correlations
        WHERE header_mi = {H_MI_6C8AB637}
        ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            conn.close()
            continue
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Find call sessions (gaps > 5 seconds)
        df['time_gap'] = df['timestamp'].diff().dt.total_seconds()
        df['new_session'] = df['time_gap'] > 5
        df['session_id'] = df['new_session'].cumsum()
        
        # Analyze each session
        for session_id, session_data in df.groupby('session_id'):
            if len(session_data) < 3:  # Skip very short sessions
                continue
                
            duration = (session_data['timestamp'].iloc[-1] - 
                       session_data['timestamp'].iloc[0]).total_seconds()
            
            c_mis = session_data['control_mi'].tolist()
            
            # Calculate jumps using the known patterns
            jumps = []
            for i in range(1, len(c_mis)):
                jump = get_jump_from_master(c_mis[i-1], c_mis[i])
                jumps.append(jump)
            
            all_sessions.append({
                'duration': duration,
                'c_mi_count': len(c_mis),
                'jumps': jumps,
                'start_c_mi': c_mis[0],
                'end_c_mi': c_mis[-1],
                'db': db_file
            })
        
        conn.close()
    
    return all_sessions

def get_jump_from_master(c_mi1, c_mi2):
    """Get the actual jump value from our master analysis data"""
    # For now, calculate simple LFSR steps
    state = c_mi1
    
    # Try forward steps (most common)
    for step in range(1, 6):
        bit = ((state >> 31) ^ (state >> 3) ^ (state >> 1)) & 0x1
        state = ((state << 1) | bit) & 0xFFFFFFFF
        
        if state == c_mi2:
            return step
    
    # Try backward steps
    state = c_mi1
    for step in range(1, 3):
        # Simplified reverse step
        new_bit = state & 1
        state = (state >> 1) | (new_bit << 31)
        
        if state == c_mi2:
            return -step
    
    # Unknown jump
    return 0

def analyze_correlation(sessions):
    """Analyze correlation between call duration and jump patterns"""
    
    # Load known jump distribution
    master_jumps = load_master_jumps()
    
    # Create visualizations
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Jump frequency by call duration
    duration_bins = [(0, 10), (10, 30), (30, 60), (60, 120), (120, float('inf'))]
    bin_labels = ['0-10s', '10-30s', '30-60s', '60-120s', '120s+']
    
    jump_by_duration = defaultdict(lambda: defaultdict(int))
    
    for session in sessions:
        duration = session['duration']
        bin_label = None
        
        for (low, high), label in zip(duration_bins, bin_labels):
            if low <= duration < high:
                bin_label = label
                break
        
        if bin_label:
            for jump in session['jumps']:
                if jump != 0:  # Exclude unknowns
                    jump_by_duration[bin_label][jump] += 1
    
    # Plot jump distribution by duration
    common_jumps = [1, -1, 2, 3, -2, 4]
    x = np.arange(len(bin_labels))
    width = 0.8
    
    bottom = np.zeros(len(bin_labels))
    colors = plt.cm.tab10(np.linspace(0, 0.5, len(common_jumps)))
    
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
    ax1.set_title('LFSR Jump Patterns by Call Duration')
    ax1.set_xticks(x)
    ax1.set_xticklabels(bin_labels)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Average jump magnitude by duration
    avg_jumps_by_duration = {}
    
    for label in bin_labels:
        jumps_for_bin = []
        for session in sessions:
            duration = session['duration']
            
            for (low, high), bin_label in zip(duration_bins, bin_labels):
                if low <= duration < high and bin_label == label:
                    jumps_for_bin.extend([abs(j) for j in session['jumps'] if j != 0])
                    break
        
        if jumps_for_bin:
            avg_jumps_by_duration[label] = {
                'mean': np.mean(jumps_for_bin),
                'std': np.std(jumps_for_bin)
            }
    
    labels = list(avg_jumps_by_duration.keys())
    means = [avg_jumps_by_duration[l]['mean'] for l in labels]
    stds = [avg_jumps_by_duration[l]['std'] for l in labels]
    
    x = np.arange(len(labels))
    ax2.bar(x, means, yerr=stds, capsize=5, alpha=0.7)
    ax2.set_xlabel('Call Duration')
    ax2.set_ylabel('Average Jump Magnitude')
    ax2.set_title('Average LFSR Jump Size by Call Duration')
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.grid(True, alpha=0.3)
    
    # 3. Call duration distribution
    durations = [s['duration'] for s in sessions]
    ax3.hist(durations, bins=30, edgecolor='black', alpha=0.7)
    ax3.set_xlabel('Duration (seconds)')
    ax3.set_ylabel('Number of Calls')
    ax3.set_title('Distribution of Call Durations')
    ax3.grid(True, alpha=0.3)
    
    # Add statistics
    mean_dur = np.mean(durations)
    median_dur = np.median(durations)
    ax3.axvline(mean_dur, color='red', linestyle='--', 
                label=f'Mean: {mean_dur:.1f}s')
    ax3.axvline(median_dur, color='green', linestyle='--', 
                label=f'Median: {median_dur:.1f}s')
    ax3.legend()
    
    # 4. Scatter plot of duration vs jump diversity
    duration_list = []
    diversity_list = []
    
    for session in sessions:
        if session['jumps']:
            unique_jumps = len(set([j for j in session['jumps'] if j != 0]))
            total_jumps = len([j for j in session['jumps'] if j != 0])
            
            if total_jumps > 0:
                diversity = unique_jumps / total_jumps
                duration_list.append(session['duration'])
                diversity_list.append(diversity)
    
    ax4.scatter(duration_list, diversity_list, alpha=0.6)
    ax4.set_xlabel('Call Duration (seconds)')
    ax4.set_ylabel('Jump Pattern Diversity')
    ax4.set_title('Jump Pattern Diversity vs Call Duration')
    ax4.grid(True, alpha=0.3)
    
    # Add trend line
    if duration_list:
        z = np.polyfit(duration_list, diversity_list, 1)
        p = np.poly1d(z)
        ax4.plot(sorted(duration_list), p(sorted(duration_list)), 
                "r--", alpha=0.8, label=f'Trend: {z[0]:.4f}x + {z[1]:.4f}')
        ax4.legend()
    
    plt.tight_layout()
    plt.savefig('call_duration_lfsr_correlation.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Print detailed statistics
    print("\n=== DETAILED ANALYSIS ===")
    
    print(f"\nTotal sessions analyzed: {len(sessions)}")
    print(f"Average session duration: {np.mean(durations):.1f} seconds")
    print(f"Session duration range: {min(durations):.1f} - {max(durations):.1f} seconds")
    
    # Jump patterns by duration
    print("\nJump patterns by call duration:")
    for label in bin_labels:
        sessions_in_bin = [s for s in sessions 
                          for (low, high), l in zip(duration_bins, bin_labels)
                          if low <= s['duration'] < high and l == label]
        
        if sessions_in_bin:
            print(f"\n{label} ({len(sessions_in_bin)} sessions):")
            
            # Get jump distribution
            all_jumps = []
            for s in sessions_in_bin:
                all_jumps.extend([j for j in s['jumps'] if j != 0])
            
            if all_jumps:
                jump_counts = defaultdict(int)
                for j in all_jumps:
                    jump_counts[j] += 1
                
                total = len(all_jumps)
                for jump, count in sorted(jump_counts.items(), 
                                        key=lambda x: x[1], reverse=True)[:5]:
                    percent = count / total * 100
                    print(f"  Jump {jump:+2d}: {percent:5.1f}% ({count} occurrences)")
    
    # Correlation analysis
    if duration_list and diversity_list:
        correlation = np.corrcoef(duration_list, diversity_list)[0, 1]
        print(f"\nCorrelation between duration and pattern diversity: {correlation:.3f}")
    
    # Compare short vs long calls
    short_sessions = [s for s in sessions if s['duration'] < 10]
    long_sessions = [s for s in sessions if s['duration'] > 60]
    
    if short_sessions and long_sessions:
        short_jumps = []
        long_jumps = []
        
        for s in short_sessions:
            short_jumps.extend([j for j in s['jumps'] if j != 0])
        
        for s in long_sessions:
            long_jumps.extend([j for j in s['jumps'] if j != 0])
        
        if short_jumps and long_jumps:
            print(f"\nShort calls (<10s): {len(short_sessions)} sessions")
            print(f"  Average jump: {np.mean([abs(j) for j in short_jumps]):.2f}")
            print(f"  Most common: {max(set(short_jumps), key=short_jumps.count)}")
            
            print(f"\nLong calls (>60s): {len(long_sessions)} sessions")
            print(f"  Average jump: {np.mean([abs(j) for j in long_jumps]):.2f}")
            print(f"  Most common: {max(set(long_jumps), key=long_jumps.count)}")
    
    return sessions

def main():
    print("Call Duration vs LFSR Pattern Analysis")
    print("=" * 40)
    
    sessions = analyze_sessions()
    
    if sessions:
        analyze_correlation(sessions)
        print("\nAnalysis complete. Results saved to call_duration_lfsr_correlation.png")
    else:
        print("No session data found")

if __name__ == "__main__":
    main()