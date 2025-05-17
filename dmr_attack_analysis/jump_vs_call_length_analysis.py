#!/usr/bin/env python3
"""
Analyze correlation between C-MI jumps and call length
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from glob import glob
from collections import defaultdict
import numpy as np
from datetime import datetime, timedelta

def analyze_jump_patterns():
    # Load all databases
    db_files = sorted(glob("dmr_capture_*.db"))
    
    all_sessions = []
    jump_patterns = defaultdict(list)
    
    for db_file in db_files:
        print(f"\nAnalyzing {db_file}")
        conn = sqlite3.connect(db_file)
        
        # Get correlations with timestamps
        correlations_df = pd.read_sql_query("""
            SELECT header_mi, control_mi, timestamp, slot
            FROM dmr_correlations
            ORDER BY timestamp
        """, conn)
        
        if correlations_df.empty:
            continue
            
        # Convert timestamps
        correlations_df['timestamp'] = pd.to_datetime(correlations_df['timestamp'])
        
        # Group by H-MI to identify sessions
        h_mi_groups = correlations_df.groupby('header_mi')
        
        for h_mi, group in h_mi_groups:
            # Sort by timestamp
            group = group.sort_values('timestamp')
            
            # Calculate time gaps to identify separate calls
            group['time_diff'] = group['timestamp'].diff()
            
            # Split into calls based on gaps > 2 seconds
            call_boundaries = group[group['time_diff'] > pd.Timedelta(seconds=2)].index
            
            call_starts = [group.index[0]] + list(call_boundaries)
            call_ends = list(call_boundaries - 1) + [group.index[-1]]
            
            # Analyze each call
            for start_idx, end_idx in zip(call_starts, call_ends):
                call_data = group.loc[start_idx:end_idx]
                
                if len(call_data) < 2:
                    continue
                    
                # Calculate call duration
                duration = (call_data['timestamp'].iloc[-1] - 
                           call_data['timestamp'].iloc[0]).total_seconds()
                
                # Calculate C-MI jumps
                c_mis = call_data['control_mi'].tolist()
                jumps = []
                
                for i in range(1, len(c_mis)):
                    jump = calculate_jump(c_mis[i-1], c_mis[i])
                    jumps.append(jump)
                    jump_patterns[jump].append({
                        'duration': duration,
                        'position': i / len(c_mis),  # Relative position in call
                        'h_mi': h_mi,
                        'db': db_file
                    })
                
                all_sessions.append({
                    'h_mi': h_mi,
                    'duration': duration,
                    'c_mi_count': len(c_mis),
                    'jumps': jumps,
                    'avg_jump': np.mean(jumps) if jumps else 0,
                    'db': db_file
                })
        
        conn.close()
    
    return all_sessions, jump_patterns

def calculate_jump(mi1, mi2):
    """Calculate jump distance - simplified to direct difference for now"""
    # For this analysis, let's look at simple numeric differences
    # since the LFSR pattern is complex
    diff = (mi2 - mi1) & 0xFFFFFFFF
    
    # Handle wraparound
    if diff > 0x80000000:
        diff = diff - 0x100000000
        
    return diff

def plot_analysis(sessions, jump_patterns):
    # Create figure with subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. Jump distribution by call duration
    duration_bins = [0, 5, 10, 20, 30, 60, 120, 300]
    jump_by_duration = defaultdict(list)
    
    for session in sessions:
        duration_bin = None
        for i in range(len(duration_bins)-1):
            if duration_bins[i] <= session['duration'] < duration_bins[i+1]:
                duration_bin = f"{duration_bins[i]}-{duration_bins[i+1]}s"
                break
        if duration_bin is None and session['duration'] >= duration_bins[-1]:
            duration_bin = f"{duration_bins[-1]}+s"
            
        if duration_bin:
            jump_by_duration[duration_bin].extend(session['jumps'])
    
    # Plot jump distribution by duration
    labels = []
    means = []
    stds = []
    
    for bin_label in [f"{duration_bins[i]}-{duration_bins[i+1]}s" 
                      for i in range(len(duration_bins)-1)] + [f"{duration_bins[-1]}+s"]:
        if bin_label in jump_by_duration:
            jumps = jump_by_duration[bin_label]
            labels.append(bin_label)
            means.append(np.mean(jumps))
            stds.append(np.std(jumps))
    
    x = range(len(labels))
    ax1.bar(x, means, yerr=stds, capsize=5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45)
    ax1.set_ylabel('Average Jump Distance')
    ax1.set_title('Jump Distance vs Call Duration')
    ax1.grid(True, alpha=0.3)
    
    # 2. Jump frequency vs position in call
    position_bins = np.linspace(0, 1, 11)
    jump_by_position = defaultdict(list)
    
    for jump_type, occurrences in jump_patterns.items():
        for occ in occurrences:
            pos_bin = int(occ['position'] * 10) / 10
            jump_by_position[pos_bin].append(jump_type)
    
    # Most common jumps by position
    positions = sorted(jump_by_position.keys())
    jump_types = [1, -1, 2, 3, -2, 4]
    jump_counts = {jt: [] for jt in jump_types}
    
    for pos in positions:
        jumps_at_pos = jump_by_position[pos]
        total = len(jumps_at_pos)
        for jt in jump_types:
            count = jumps_at_pos.count(jt)
            jump_counts[jt].append(count / total * 100 if total > 0 else 0)
    
    # Stack plot
    bottom = np.zeros(len(positions))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    
    for i, jt in enumerate(jump_types):
        ax2.bar(positions, jump_counts[jt], bottom=bottom, width=0.08, 
                label=f'Jump {jt:+d}', color=colors[i])
        bottom += jump_counts[jt]
    
    ax2.set_xlabel('Position in Call (0=start, 1=end)')
    ax2.set_ylabel('Jump Type Distribution (%)')
    ax2.set_title('Jump Pattern Distribution by Position in Call')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Call length distribution
    durations = [s['duration'] for s in sessions]
    ax3.hist(durations, bins=30, edgecolor='black')
    ax3.set_xlabel('Call Duration (seconds)')
    ax3.set_ylabel('Count')
    ax3.set_title('Distribution of Call Durations')
    ax3.grid(True, alpha=0.3)
    
    # 4. Jump pattern correlation with call length
    call_lengths = []
    avg_jumps = []
    
    for session in sessions:
        if session['jumps']:
            call_lengths.append(session['duration'])
            avg_jumps.append(session['avg_jump'])
    
    ax4.scatter(call_lengths, avg_jumps, alpha=0.6)
    ax4.set_xlabel('Call Duration (seconds)')
    ax4.set_ylabel('Average Jump Distance')
    ax4.set_title('Average Jump Distance vs Call Duration')
    ax4.grid(True, alpha=0.3)
    
    # Add trend line
    if call_lengths:
        z = np.polyfit(call_lengths, avg_jumps, 1)
        p = np.poly1d(z)
        ax4.plot(sorted(call_lengths), p(sorted(call_lengths)), "r--", alpha=0.8)
    
    plt.tight_layout()
    plt.savefig('jump_vs_call_length_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Create summary statistics
    print("\n=== SUMMARY STATISTICS ===")
    
    # Overall jump distribution
    all_jumps = []
    for session in sessions:
        all_jumps.extend(session['jumps'])
    
    if all_jumps:
        jump_counts = defaultdict(int)
        for jump in all_jumps:
            jump_counts[jump] += 1
            
        print("\nOverall jump distribution:")
        for jump, count in sorted(jump_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            percent = count / len(all_jumps) * 100
            print(f"  Jump {jump:+3d}: {count:5d} ({percent:5.1f}%)")
    
    # Jump patterns by call length categories
    print("\nJump patterns by call length:")
    for bin_label, jumps in jump_by_duration.items():
        if jumps:
            jump_dist = defaultdict(int)
            for jump in jumps:
                jump_dist[jump] += 1
            
            print(f"\n{bin_label}:")
            total = len(jumps)
            for jump, count in sorted(jump_dist.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  Jump {jump:+3d}: {count/total*100:5.1f}%")
    
    # Correlation analysis
    if call_lengths and avg_jumps:
        correlation = np.corrcoef(call_lengths, avg_jumps)[0,1]
        print(f"\nCorrelation between call length and average jump: {correlation:.3f}")
    
    return sessions, jump_patterns

def main():
    print("Jump Pattern vs Call Length Analysis")
    print("=" * 40)
    
    sessions, jump_patterns = analyze_jump_patterns()
    
    if sessions:
        plot_analysis(sessions, jump_patterns)
        print(f"\nAnalyzed {len(sessions)} call sessions")
        print("Results saved to jump_vs_call_length_analysis.png")
    else:
        print("No data found to analyze")

if __name__ == "__main__":
    main()