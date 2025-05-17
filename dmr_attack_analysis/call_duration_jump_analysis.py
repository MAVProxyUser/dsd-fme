#!/usr/bin/env python3
"""
Analyze correlation between call duration and LFSR jump patterns
"""

import sqlite3
import pandas as pd
import numpy as np
from glob import glob
from collections import defaultdict
import matplotlib.pyplot as plt
from datetime import datetime

def load_jump_distribution():
    """Load jump distribution from master pattern file"""
    jump_dist = {
        1: 417,
        -1: 291,
        2: 254,
        3: 173,
        -2: 109,
        4: 79,
        5: 17
    }
    return jump_dist

def analyze_call_sessions():
    """Extract call sessions and their jump patterns"""
    
    db_files = sorted(glob("dmr_capture_*.db"))
    all_calls = []
    
    for db_file in db_files:
        print(f"Processing {db_file}")
        conn = sqlite3.connect(db_file)
        
        # Get all correlations
        query = """
        SELECT header_mi, control_mi, timestamp, slot
        FROM dmr_correlations
        ORDER BY header_mi, timestamp
        """
        
        df = pd.read_sql_query(query, conn)
        if df.empty:
            conn.close()
            continue
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Group by H-MI to find sessions
        for h_mi, group in df.groupby('header_mi'):
            group = group.sort_values('timestamp')
            
            # Identify call boundaries (gap > 5 seconds)
            group['time_gap'] = group['timestamp'].diff()
            group['new_call'] = group['time_gap'] > pd.Timedelta(seconds=5)
            group['call_id'] = group['new_call'].cumsum()
            
            # Process each call
            for call_id, call_data in group.groupby('call_id'):
                if len(call_data) < 3:  # Skip very short calls
                    continue
                    
                start_time = call_data['timestamp'].iloc[0]
                end_time = call_data['timestamp'].iloc[-1]
                duration = (end_time - start_time).total_seconds()
                
                # Extract C-MI sequence
                c_mis = call_data['control_mi'].tolist()
                
                # Calculate jumps
                jumps = []
                for i in range(1, len(c_mis)):
                    # Simple LFSR step calculation
                    jump = calculate_lfsr_jump(c_mis[i-1], c_mis[i])
                    jumps.append(jump)
                
                all_calls.append({
                    'h_mi': h_mi,
                    'duration': duration,
                    'n_frames': len(c_mis),
                    'jumps': jumps,
                    'start_time': start_time,
                    'db': db_file
                })
        
        conn.close()
    
    return all_calls

def calculate_lfsr_jump(mi1, mi2):
    """Calculate LFSR steps between states"""
    state = mi1
    
    # Try forward steps
    for step in range(1, 10):
        # LFSR with polynomial x^32 + x^4 + x^2 + 1
        bit = ((state >> 31) ^ (state >> 3) ^ (state >> 1)) & 0x1
        state = ((state << 1) | bit) & 0xFFFFFFFF
        
        if state == mi2:
            return step
    
    # Try backward steps
    state = mi1
    for step in range(1, 5):
        # Reverse LFSR
        new_bit = ((state >> 30) ^ (state >> 2) ^ state) & 0x1
        state = ((state >> 1) | (new_bit << 31)) & 0xFFFFFFFF
        
        if state == mi2:
            return -step
    
    # If not found in small range, return 0
    return 0

def analyze_patterns(calls):
    """Analyze jump patterns by call duration"""
    
    # Categorize calls by duration
    duration_bins = [0, 5, 10, 20, 30, 60, 120, float('inf')]
    bin_labels = ['0-5s', '5-10s', '10-20s', '20-30s', '30-60s', '60-120s', '120s+']
    
    calls_by_duration = defaultdict(list)
    
    for call in calls:
        duration = call['duration']
        for i in range(len(duration_bins) - 1):
            if duration_bins[i] <= duration < duration_bins[i+1]:
                calls_by_duration[bin_labels[i]].append(call)
                break
    
    # Create visualizations
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. Jump distribution by call duration
    jump_distributions = {}
    
    for label, call_list in calls_by_duration.items():
        all_jumps = []
        for call in call_list:
            all_jumps.extend(call['jumps'])
        
        if all_jumps:
            jump_counts = defaultdict(int)
            for jump in all_jumps:
                if -5 <= jump <= 5:  # Focus on common jumps
                    jump_counts[jump] += 1
            
            total = sum(jump_counts.values())
            jump_distributions[label] = {
                jump: count/total*100 for jump, count in jump_counts.items()
            }
    
    # Plot stacked bar chart
    jump_types = [1, -1, 2, 3, -2, 4]
    x = np.arange(len(bin_labels))
    width = 0.8
    
    bottom = np.zeros(len(bin_labels))
    colors = plt.cm.tab10(np.linspace(0, 0.5, len(jump_types)))
    
    for i, jump in enumerate(jump_types):
        values = []
        for label in bin_labels:
            if label in jump_distributions:
                values.append(jump_distributions[label].get(jump, 0))
            else:
                values.append(0)
        
        ax1.bar(x, values, width, bottom=bottom, 
                label=f'Jump {jump:+d}', color=colors[i])
        bottom += values
    
    ax1.set_xlabel('Call Duration')
    ax1.set_ylabel('Jump Distribution (%)')
    ax1.set_title('LFSR Jump Pattern Distribution by Call Duration')
    ax1.set_xticks(x)
    ax1.set_xticklabels(bin_labels, rotation=45)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Average jump value by duration
    avg_jumps = {}
    std_jumps = {}
    
    for label, call_list in calls_by_duration.items():
        all_jumps = []
        for call in call_list:
            all_jumps.extend([j for j in call['jumps'] if j != 0])
        
        if all_jumps:
            avg_jumps[label] = np.mean(all_jumps)
            std_jumps[label] = np.std(all_jumps)
    
    labels = list(avg_jumps.keys())
    means = list(avg_jumps.values())
    stds = list(std_jumps.values())
    
    x = np.arange(len(labels))
    ax2.bar(x, means, yerr=stds, capsize=5, alpha=0.7)
    ax2.set_xlabel('Call Duration')
    ax2.set_ylabel('Average Jump Distance')
    ax2.set_title('Average LFSR Jump by Call Duration')
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45)
    ax2.grid(True, alpha=0.3)
    
    # 3. Call duration distribution
    durations = [call['duration'] for call in calls]
    ax3.hist(durations, bins=50, edgecolor='black', alpha=0.7)
    ax3.set_xlabel('Duration (seconds)')
    ax3.set_ylabel('Number of Calls')
    ax3.set_title('Distribution of Call Durations')
    ax3.set_xlim(0, 300)
    ax3.grid(True, alpha=0.3)
    
    # Add statistics
    mean_duration = np.mean(durations)
    median_duration = np.median(durations)
    ax3.axvline(mean_duration, color='red', linestyle='--', 
                label=f'Mean: {mean_duration:.1f}s')
    ax3.axvline(median_duration, color='green', linestyle='--', 
                label=f'Median: {median_duration:.1f}s')
    ax3.legend()
    
    # 4. Jump pattern stability over call duration
    stability_data = []
    duration_labels = []
    
    for label, call_list in sorted(calls_by_duration.items()):
        if len(call_list) >= 3:  # Need enough samples
            jump_stabilities = []
            
            for call in call_list:
                if len(call['jumps']) >= 5:
                    # Calculate variance of jumps within the call
                    jump_variance = np.var([j for j in call['jumps'] if j != 0])
                    jump_stabilities.append(jump_variance)
            
            if jump_stabilities:
                stability_data.append(jump_stabilities)
                duration_labels.append(label)
    
    if stability_data:
        ax4.boxplot(stability_data, labels=duration_labels)
        ax4.set_xlabel('Call Duration')
        ax4.set_ylabel('Jump Pattern Variance')
        ax4.set_title('LFSR Pattern Stability by Call Duration')
        ax4.grid(True, alpha=0.3)
        ax4.set_xticklabels(duration_labels, rotation=45)
    
    plt.tight_layout()
    plt.savefig('call_duration_jump_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Print summary statistics
    print("\n=== SUMMARY STATISTICS ===")
    
    print(f"\nTotal calls analyzed: {len(calls)}")
    print(f"Average call duration: {np.mean(durations):.1f} seconds")
    print(f"Median call duration: {np.median(durations):.1f} seconds")
    
    print("\nJump patterns by call duration:")
    for label in bin_labels:
        if label in jump_distributions:
            n_calls = len(calls_by_duration[label])
            print(f"\n{label} ({n_calls} calls):")
            for jump in sorted(jump_distributions[label].keys()):
                percent = jump_distributions[label][jump]
                print(f"  Jump {jump:+2d}: {percent:5.1f}%")
    
    # Correlation analysis
    all_durations = []
    all_avg_jumps = []
    
    for call in calls:
        if call['jumps']:
            valid_jumps = [j for j in call['jumps'] if j != 0]
            if valid_jumps:
                all_durations.append(call['duration'])
                all_avg_jumps.append(np.mean(valid_jumps))
    
    if all_durations:
        correlation = np.corrcoef(all_durations, all_avg_jumps)[0,1]
        print(f"\nCorrelation between duration and average jump: {correlation:.3f}")
    
    # Test hypothesis: Do longer calls use different jump patterns?
    short_calls = [c for c in calls if c['duration'] < 10]
    long_calls = [c for c in calls if c['duration'] > 60]
    
    if short_calls and long_calls:
        short_jumps = []
        long_jumps = []
        
        for call in short_calls:
            short_jumps.extend([j for j in call['jumps'] if j != 0])
        
        for call in long_calls:
            long_jumps.extend([j for j in call['jumps'] if j != 0])
        
        if short_jumps and long_jumps:
            print(f"\nShort calls (<10s) average jump: {np.mean(short_jumps):.2f}")
            print(f"Long calls (>60s) average jump: {np.mean(long_jumps):.2f}")
            
            # Chi-square test for distribution difference
            jump_types = [1, -1, 2, 3, -2, 4]
            short_dist = []
            long_dist = []
            
            for jt in jump_types:
                short_dist.append(short_jumps.count(jt))
                long_dist.append(long_jumps.count(jt))
            
            from scipy.stats import chi2_contingency
            chi2, p_value, _, _ = chi2_contingency([short_dist, long_dist])
            print(f"\nChi-square test for jump distribution difference:")
            print(f"Chi2: {chi2:.3f}, p-value: {p_value:.6f}")
            
            if p_value < 0.05:
                print("Jump patterns differ significantly between short and long calls")
            else:
                print("No significant difference in jump patterns")

def main():
    print("Call Duration vs LFSR Jump Pattern Analysis")
    print("=" * 40)
    
    calls = analyze_call_sessions()
    
    if calls:
        analyze_patterns(calls)
        print("\nAnalysis complete. Results saved to call_duration_jump_analysis.png")
    else:
        print("No call data found")

if __name__ == "__main__":
    main()