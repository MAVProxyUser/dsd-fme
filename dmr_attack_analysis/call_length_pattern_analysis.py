#!/usr/bin/env python3
"""
Analyze how LFSR jump patterns correlate with call length
"""

import sqlite3
import pandas as pd
import numpy as np
from glob import glob
from collections import defaultdict
import json
import matplotlib.pyplot as plt
from datetime import datetime

def load_lfsr_model():
    """Load the LFSR model from master analysis"""
    try:
        with open('dmr_master_pattern.json', 'r') as f:
            return json.load(f)
    except:
        return None

def analyze_calls_and_jumps():
    # Load LFSR model
    model = load_lfsr_model()
    
    # Get actual jump patterns from master analysis
    if model and '1819898423' in model['h_mi_data']:  # 0x6C8AB637
        jump_data = model['h_mi_data']['1819898423']['transitions']
    else:
        jump_data = {}
    
    # Load all databases
    db_files = sorted(glob("dmr_capture_*.db"))
    
    call_analysis = []
    jump_by_duration = defaultdict(list)
    
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
        
        # Group by H-MI
        h_mi_groups = correlations_df.groupby('header_mi')
        
        for h_mi, group in h_mi_groups:
            # Sort by timestamp
            group = group.sort_values('timestamp')
            
            # Find calls (separated by gaps > 5 seconds)
            group['time_diff'] = group['timestamp'].diff()
            group['new_call'] = group['time_diff'] > pd.Timedelta(seconds=5)
            group['call_id'] = group['new_call'].cumsum()
            
            # Analyze each call
            for call_id, call_data in group.groupby('call_id'):
                if len(call_data) < 2:
                    continue
                    
                # Calculate call metrics
                duration = (call_data['timestamp'].iloc[-1] - 
                           call_data['timestamp'].iloc[0]).total_seconds()
                
                c_mis = call_data['control_mi'].tolist()
                
                # Calculate jumps using our known patterns
                jumps = []
                for i in range(1, len(c_mis)):
                    key = f"{c_mis[i-1]}_{c_mis[i]}"
                    if key in jump_data:
                        jump = jump_data[key]['jump']
                    else:
                        # Fallback to calculation
                        jump = calculate_lfsr_steps(c_mis[i-1], c_mis[i])
                    jumps.append(jump)
                
                # Categorize call duration
                if duration < 5:
                    duration_cat = "0-5s"
                elif duration < 10:
                    duration_cat = "5-10s"
                elif duration < 30:
                    duration_cat = "10-30s"
                elif duration < 60:
                    duration_cat = "30-60s"
                else:
                    duration_cat = "60s+"
                
                jump_by_duration[duration_cat].extend(jumps)
                
                call_analysis.append({
                    'h_mi': h_mi,
                    'duration': duration,
                    'duration_cat': duration_cat,
                    'c_mi_count': len(c_mis),
                    'jumps': jumps,
                    'db': db_file
                })
        
        conn.close()
    
    return call_analysis, jump_by_duration

def calculate_lfsr_steps(state1, state2):
    """Calculate LFSR steps between two states"""
    state = state1
    polynomial = 0x10080004  # x^32 + x^4 + x^2 + 1
    
    for steps in range(1, 100):
        # LFSR step
        bit = 0
        for i in range(32):
            if polynomial & (1 << i):
                bit ^= (state >> i) & 1
        
        state = ((state << 1) | bit) & 0xFFFFFFFF
        
        if state == state2:
            return steps
    
    # Check negative steps
    state = state1
    for steps in range(1, 100):
        # Reverse LFSR step
        new_bit = state & 1
        state = (state >> 1) | (new_bit << 31)
        
        # Apply polynomial
        if new_bit:
            state ^= polynomial
            
        if state == state2:
            return -steps
    
    return 0  # Unknown

def plot_results(call_analysis, jump_by_duration):
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. Jump distribution by call duration
    duration_cats = ["0-5s", "5-10s", "10-30s", "30-60s", "60s+"]
    jump_stats = {}
    
    for cat in duration_cats:
        if cat in jump_by_duration:
            jumps = jump_by_duration[cat]
            jump_counts = defaultdict(int)
            for jump in jumps:
                jump_counts[jump] += 1
            
            # Get top jumps
            total = len(jumps)
            jump_stats[cat] = {
                'total': total,
                'distribution': {k: v/total*100 for k, v in 
                                sorted(jump_counts.items(), key=lambda x: x[1], reverse=True)[:5]}
            }
    
    # Plot stacked bar chart
    jump_types = [1, -1, 2, 3, -2]
    x = np.arange(len(duration_cats))
    width = 0.8
    
    bottom = np.zeros(len(duration_cats))
    colors = plt.cm.tab10(np.linspace(0, 0.5, len(jump_types)))
    
    for i, jump_type in enumerate(jump_types):
        values = []
        for cat in duration_cats:
            if cat in jump_stats:
                values.append(jump_stats[cat]['distribution'].get(jump_type, 0))
            else:
                values.append(0)
        
        ax1.bar(x, values, width, bottom=bottom, label=f'Jump {jump_type:+d}', 
                color=colors[i])
        bottom += values
    
    ax1.set_xlabel('Call Duration')
    ax1.set_ylabel('Jump Type Distribution (%)')
    ax1.set_title('LFSR Jump Pattern Distribution by Call Duration')
    ax1.set_xticks(x)
    ax1.set_xticklabels(duration_cats)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Average jumps per call by duration
    duration_jumps = defaultdict(list)
    for call in call_analysis:
        if call['jumps']:
            avg_jump = np.mean(call['jumps'])
            duration_jumps[call['duration_cat']].append(avg_jump)
    
    # Box plot
    data_to_plot = []
    labels = []
    for cat in duration_cats:
        if cat in duration_jumps:
            data_to_plot.append(duration_jumps[cat])
            labels.append(cat)
    
    ax2.boxplot(data_to_plot, labels=labels)
    ax2.set_xlabel('Call Duration')
    ax2.set_ylabel('Average Jump Distance')
    ax2.set_title('Average LFSR Jump Distance by Call Duration')
    ax2.grid(True, alpha=0.3)
    
    # 3. Call duration histogram
    durations = [call['duration'] for call in call_analysis]
    ax3.hist(durations, bins=30, edgecolor='black', alpha=0.7)
    ax3.set_xlabel('Call Duration (seconds)')
    ax3.set_ylabel('Number of Calls')
    ax3.set_title('Distribution of Call Durations')
    ax3.grid(True, alpha=0.3)
    ax3.axvline(np.mean(durations), color='red', linestyle='--', 
                label=f'Mean: {np.mean(durations):.1f}s')
    ax3.legend()
    
    # 4. Jump pattern evolution during call
    # Analyze first vs last jumps
    first_jumps = defaultdict(list)
    last_jumps = defaultdict(list)
    
    for call in call_analysis:
        if len(call['jumps']) >= 3:
            first_jumps[call['duration_cat']].extend(call['jumps'][:3])
            last_jumps[call['duration_cat']].extend(call['jumps'][-3:])
    
    # Compare distributions
    categories = []
    first_avg = []
    last_avg = []
    
    for cat in duration_cats:
        if cat in first_jumps and cat in last_jumps:
            categories.append(cat)
            first_avg.append(np.mean(first_jumps[cat]))
            last_avg.append(np.mean(last_jumps[cat]))
    
    x = np.arange(len(categories))
    width = 0.35
    
    ax4.bar(x - width/2, first_avg, width, label='First 3 jumps', alpha=0.7)
    ax4.bar(x + width/2, last_avg, width, label='Last 3 jumps', alpha=0.7)
    ax4.set_xlabel('Call Duration')
    ax4.set_ylabel('Average Jump Distance')
    ax4.set_title('Jump Pattern Evolution: Start vs End of Call')
    ax4.set_xticks(x)
    ax4.set_xticklabels(categories)
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('call_length_pattern_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Print detailed statistics
    print("\n=== DETAILED STATISTICS ===")
    
    for cat in duration_cats:
        if cat in jump_stats:
            print(f"\n{cat} calls:")
            print(f"  Total jumps: {jump_stats[cat]['total']}")
            print("  Top 5 jump patterns:")
            for jump, percent in jump_stats[cat]['distribution'].items():
                print(f"    Jump {jump:+3d}: {percent:5.1f}%")
    
    # Correlation analysis
    all_durations = []
    all_avg_jumps = []
    
    for call in call_analysis:
        if call['jumps']:
            all_durations.append(call['duration'])
            all_avg_jumps.append(np.mean(call['jumps']))
    
    if all_durations:
        correlation = np.corrcoef(all_durations, all_avg_jumps)[0,1]
        print(f"\nCorrelation between call duration and average jump: {correlation:.3f}")
    
    # Pattern stability analysis
    print("\nPattern stability by call duration:")
    for cat in duration_cats:
        if cat in jump_by_duration:
            jumps = jump_by_duration[cat]
            if jumps:
                unique_jumps = len(set(jumps))
                total_jumps = len(jumps)
                print(f"  {cat}: {unique_jumps} unique patterns out of {total_jumps} total")

def main():
    print("Call Length vs LFSR Jump Pattern Analysis")
    print("=" * 40)
    
    call_analysis, jump_by_duration = analyze_calls_and_jumps()
    
    if call_analysis:
        plot_results(call_analysis, jump_by_duration)
        print(f"\nAnalyzed {len(call_analysis)} calls")
        print("Results saved to call_length_pattern_analysis.png")
    else:
        print("No data found to analyze")

if __name__ == "__main__":
    main()