#!/usr/bin/env python3
"""Analyze frame structure and correlations in DMR capture"""

import sqlite3
import sys
from collections import defaultdict

def connect_db(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def analyze_frame_structure(db_path):
    conn = connect_db(db_path)
    if not conn:
        return
    
    cursor = conn.cursor()
    
    # Get all tables matching C_XXXXXXXX_SX pattern
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%'")
    cmi_tables = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(cmi_tables)} C-MI tables")
    
    # Analyze frame distribution
    frame_counts = defaultdict(int)
    frame_positions = defaultdict(lambda: defaultdict(int))
    
    for table in cmi_tables:
        cmi = table.replace('C_', '').replace('_S0', '')
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        frame_counts[count] += 1
        
        # Analyze frame positions within bursts
        cursor.execute(f"""
            SELECT (ROW_NUMBER() OVER (ORDER BY id) - 1) % 3 as position,
                   COUNT(*) as cnt
            FROM {table}
            GROUP BY position
        """)
        
        for row in cursor.fetchall():
            frame_positions[cmi][row['position']] = row['cnt']
    
    print("\n=== Frame Count Distribution ===")
    for count, tables in sorted(frame_counts.items()):
        print(f"{count} frames: {tables} tables ({count//3} complete + {count%3} partial bursts)")
    
    print("\n=== Frame Position Analysis ===")
    complete_bursts = 0
    partial_bursts = 0
    
    for cmi, positions in frame_positions.items():
        # Check if all positions are equal (complete bursts)
        values = list(positions.values())
        if len(values) == 3 and all(v == values[0] for v in values):
            complete_bursts += 1
        else:
            partial_bursts += 1
    
    print(f"Complete bursts (equal frames in all positions): {complete_bursts}")
    print(f"Partial bursts: {partial_bursts}")
    
    print("\n=== Inter-Frame Correlations ===")
    # Sample analysis of a few C-MIs
    for i, table in enumerate(cmi_tables[:5]):
        print(f"\nAnalyzing {table}:")
        cursor.execute(f"""
            SELECT 
                a.vocoder AS vocoder1,
                b.vocoder AS vocoder2, 
                ((ROW_NUMBER() OVER (ORDER BY a.id) - 1) % 3) as position
            FROM {table} a
            JOIN {table} b ON b.id = a.id + 1
            WHERE b.id <= (SELECT MAX(id) FROM {table})
            LIMIT 12
        """)
        
        for row in cursor.fetchall():
            xor = int(row['vocoder1'], 16) ^ int(row['vocoder2'], 16)
            print(f"  Position {row['position']}: {row['vocoder1']} ⊕ {row['vocoder2']} = 0x{xor:013X}")
    
    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/dsd-fme_sqlite/build/dmr_capture_20250518_115502_684984.db"
    analyze_frame_structure(db_path)