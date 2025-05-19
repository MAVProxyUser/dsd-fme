#!/usr/bin/env python3

import sqlite3
import glob
import numpy as np
import cupy as cp  # CuPy for CUDA acceleration on Jetson
from datetime import datetime
import time

class CudaSuperframeCorrelator:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        
        # Check CUDA availability
        print(f"CUDA devices available: {cp.cuda.runtime.getDeviceCount()}")
        if cp.cuda.runtime.getDeviceCount() > 0:
            props = cp.cuda.runtime.getDeviceProperties(0)
            print(f"Using GPU: {props['name'].decode()}")
            print(f"Compute capability: {props['major']}.{props['minor']}")
            print(f"Total memory: {props['totalGlobalMem'] / 1024**3:.2f} GB")
    
    def create_correlation_table(self):
        """Create enhanced correlation table"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS superframe_correlations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sf_id_1 INTEGER,
                sf_id_2 INTEGER,
                time_diff REAL,
                mi_match INTEGER,
                source_match INTEGER,
                target_match INTEGER,
                frame_count_diff INTEGER,
                correlation_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(sf_id_1) REFERENCES superframes(id),
                FOREIGN KEY(sf_id_2) REFERENCES superframes(id)
            )
        """)
        self.conn.commit()
    
    def load_superframe_data(self):
        """Load all superframe data into memory"""
        # First get superframe data
        query = """
            SELECT 
                id, 
                start_timestamp, 
                slot, 
                COALESCE(h_mi, 0) as h_mi, 
                COALESCE(c_mi, 0) as c_mi, 
                COALESCE(source_id, 0) as source_id, 
                COALESCE(target_id, 0) as target_id
            FROM superframes
            ORDER BY start_timestamp
        """
        
        self.cursor.execute(query)
        superframe_data = self.cursor.fetchall()
        
        # Count frames for each superframe
        frame_counts = {}
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_S0'")
        ambe_tables = [row[0] for row in self.cursor.fetchall()]
        
        for table in ambe_tables:
            self.cursor.execute(f"SELECT superframe_id, COUNT(*) FROM {table} GROUP BY superframe_id")
            for sf_id, count in self.cursor.fetchall():
                if sf_id is not None:
                    frame_counts[sf_id] = frame_counts.get(sf_id, 0) + count
        
        # Combine data
        all_data = []
        for row in superframe_data:
            sf_id = row[0]
            frame_count = frame_counts.get(sf_id, 0)
            all_data.append(row + (frame_count,))
        
        # Convert to structured array
        dtype = [
            ('id', np.int32),
            ('timestamp', 'U19'),  # String timestamp
            ('slot', np.int8),
            ('h_mi', np.uint32),
            ('c_mi', np.uint32),
            ('source_id', np.uint32),
            ('target_id', np.uint32),
            ('frame_count', np.int32)
        ]
        
        return np.array(all_data, dtype=dtype)
    
    def compute_correlations_cuda(self, data):
        """Compute correlations using CUDA"""
        n = len(data)
        
        # Convert timestamps to seconds since epoch for numerical comparison
        timestamps = np.array([
            datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S').timestamp()
            for row in data
        ])
        
        # Transfer data to GPU
        gpu_timestamps = cp.asarray(timestamps)
        gpu_h_mi = cp.asarray(data['h_mi'])
        gpu_c_mi = cp.asarray(data['c_mi'])
        gpu_source_id = cp.asarray(data['source_id'])
        gpu_target_id = cp.asarray(data['target_id'])
        gpu_frame_count = cp.asarray(data['frame_count'])
        gpu_slot = cp.asarray(data['slot'])
        
        # Prepare correlation results
        correlations = []
        
        # Process in batches to avoid memory overflow
        batch_size = 1000
        
        for i in range(0, n, batch_size):
            end_i = min(i + batch_size, n)
            batch_size_i = end_i - i
            
            # Create correlation matrices for this batch
            time_diff_matrix = cp.zeros((batch_size_i, n))
            mi_match_matrix = cp.zeros((batch_size_i, n), dtype=cp.int8)
            source_match_matrix = cp.zeros((batch_size_i, n), dtype=cp.int8)
            target_match_matrix = cp.zeros((batch_size_i, n), dtype=cp.int8)
            frame_diff_matrix = cp.zeros((batch_size_i, n))
            slot_match_matrix = cp.zeros((batch_size_i, n), dtype=cp.int8)
            
            # Compute metrics in parallel on GPU
            for j in range(batch_size_i):
                idx = i + j
                
                # Time differences
                time_diff_matrix[j] = cp.abs(gpu_timestamps - gpu_timestamps[idx])
                
                # MI matches (either H-MI or C-MI)
                h_mi_match = (gpu_h_mi == gpu_h_mi[idx]) & (gpu_h_mi != 0)
                c_mi_match = (gpu_c_mi == gpu_c_mi[idx]) & (gpu_c_mi != 0)
                mi_match_matrix[j] = h_mi_match | c_mi_match
                
                # Source/Target matches
                source_match_matrix[j] = (gpu_source_id == gpu_source_id[idx]) & (gpu_source_id != 0)
                target_match_matrix[j] = (gpu_target_id == gpu_target_id[idx]) & (gpu_target_id != 0)
                
                # Frame count differences
                frame_diff_matrix[j] = cp.abs(gpu_frame_count - gpu_frame_count[idx])
                
                # Slot matches
                slot_match_matrix[j] = gpu_slot == gpu_slot[idx]
            
            # Calculate correlation scores
            correlation_scores = cp.zeros((batch_size_i, n))
            
            # Weight factors
            w_time = 0.3
            w_mi = 0.3
            w_source = 0.2
            w_target = 0.1
            w_frames = 0.1
            
            # Normalize time differences (assume max 10 seconds is meaningful)
            time_score = 1.0 - cp.minimum(time_diff_matrix / 10.0, 1.0)
            
            # Binary scores
            mi_score = mi_match_matrix.astype(cp.float32)
            source_score = source_match_matrix.astype(cp.float32)
            target_score = target_match_matrix.astype(cp.float32)
            
            # Frame similarity (assume max 50 frame difference)
            frame_score = 1.0 - cp.minimum(frame_diff_matrix / 50.0, 1.0)
            
            # Combined score
            correlation_scores = (
                w_time * time_score +
                w_mi * mi_score +
                w_source * source_score +
                w_target * target_score +
                w_frames * frame_score
            )
            
            # Apply slot matching as a filter
            correlation_scores *= slot_match_matrix
            
            # Find significant correlations (score > 0.5)
            significant = cp.where(correlation_scores > 0.5)
            
            # Convert indices to CPU
            significant_cpu = (significant[0].get(), significant[1].get())
            
            # Convert back to CPU and store results
            for batch_j, global_j in zip(significant_cpu[0], significant_cpu[1]):
                if i + batch_j < global_j:  # Avoid duplicates
                    correlations.append({
                        'sf_id_1': int(data['id'][i + batch_j]),
                        'sf_id_2': int(data['id'][global_j]),
                        'time_diff': float(time_diff_matrix[batch_j, global_j].get()),
                        'mi_match': int(mi_match_matrix[batch_j, global_j].get()),
                        'source_match': int(source_match_matrix[batch_j, global_j].get()),
                        'target_match': int(target_match_matrix[batch_j, global_j].get()),
                        'frame_count_diff': int(frame_diff_matrix[batch_j, global_j].get()),
                        'correlation_score': float(correlation_scores[batch_j, global_j].get())
                    })
        
        return correlations
    
    def save_correlations(self, correlations):
        """Save correlations to database"""
        insert_query = """
            INSERT INTO superframe_correlations 
            (sf_id_1, sf_id_2, time_diff, mi_match, source_match, 
             target_match, frame_count_diff, correlation_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        for corr in correlations:
            self.cursor.execute(insert_query, (
                corr['sf_id_1'],
                corr['sf_id_2'],
                corr['time_diff'],
                corr['mi_match'],
                corr['source_match'],
                corr['target_match'],
                corr['frame_count_diff'],
                corr['correlation_score']
            ))
        
        self.conn.commit()
    
    def analyze_correlations(self):
        """Analyze and summarize correlations"""
        # Get statistics
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(correlation_score) as avg_score,
                MAX(correlation_score) as max_score,
                SUM(mi_match) as mi_matches,
                SUM(source_match) as source_matches,
                SUM(target_match) as target_matches
            FROM superframe_correlations
        """)
        
        stats = self.cursor.fetchone()
        
        print("\n=== Correlation Analysis ===")
        print(f"Total correlations: {stats[0]}")
        print(f"Average score: {stats[1]:.3f}")
        print(f"Maximum score: {stats[2]:.3f}")
        print(f"MI matches: {stats[3]}")
        print(f"Source matches: {stats[4]}")
        print(f"Target matches: {stats[5]}")
        
        # Get top correlations
        self.cursor.execute("""
            SELECT 
                s1.id as sf1_id,
                s2.id as sf2_id,
                s1.h_mi as h_mi_1,
                s2.h_mi as h_mi_2,
                s1.c_mi as c_mi_1,
                s2.c_mi as c_mi_2,
                c.correlation_score
            FROM superframe_correlations c
            JOIN superframes s1 ON c.sf_id_1 = s1.id
            JOIN superframes s2 ON c.sf_id_2 = s2.id
            ORDER BY c.correlation_score DESC
            LIMIT 10
        """)
        
        print("\nTop 10 Correlations:")
        print("SF1 | SF2 | H-MI-1   | H-MI-2   | C-MI-1   | C-MI-2   | Score")
        print("-" * 65)
        
        for row in self.cursor.fetchall():
            sf1_id, sf2_id, h_mi_1, h_mi_2, c_mi_1, c_mi_2, score = row
            print(f"{sf1_id:3d} | {sf2_id:3d} | "
                  f"{h_mi_1:08X} | {h_mi_2:08X} | "
                  f"{c_mi_1:08X} | {c_mi_2:08X} | "
                  f"{score:.3f}")
    
    def run(self):
        """Run the complete correlation analysis"""
        print(f"Processing database: {self.db_file}")
        
        # Create correlation table
        self.create_correlation_table()
        
        # Load data
        print("Loading superframe data...")
        start_time = time.time()
        data = self.load_superframe_data()
        print(f"Loaded {len(data)} superframes in {time.time() - start_time:.2f}s")
        
        # Compute correlations
        print("Computing correlations on GPU...")
        start_time = time.time()
        correlations = self.compute_correlations_cuda(data)
        print(f"Found {len(correlations)} correlations in {time.time() - start_time:.2f}s")
        
        # Save results
        print("Saving correlations to database...")
        self.save_correlations(correlations)
        
        # Analyze
        self.analyze_correlations()
        
        self.conn.close()


if __name__ == "__main__":
    # Process all databases
    databases = sorted(glob.glob("dmr_capture_*.db"))
    
    for db_file in databases:
        correlator = CudaSuperframeCorrelator(db_file)
        correlator.run()
        print("\n" + "="*50 + "\n")