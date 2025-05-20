#!/bin/bash

# Optimized search script v3 for finding DMR RC4-40 keys
# Adjusted based on benchmark results

# Configuration
LOG_FILE="optimized_v3_search_results.log"
KEYS_FOUND_FILE="/home/ubuntu/dsd-fme/arc4keyfinder/keys_found.txt"
BUILD_DIR="/home/ubuntu/dsd-fme_sqlite/build"
CPU_FINDER="/home/ubuntu/dsd-fme_sqlite/arc4keyfinder_multicore"
GPU_FINDER="/home/ubuntu/dsd-fme_sqlite/arc4keyfinder_cuda"

# Check for required tools
if [ ! -f "$CPU_FINDER" ]; then
    echo "ERROR: CPU executable not found at $CPU_FINDER"
    exit 1
fi

if [ ! -f "$GPU_FINDER" ]; then
    echo "WARNING: GPU executable not found at $GPU_FINDER, falling back to CPU only"
    GPU_AVAILABLE=false
else
    GPU_AVAILABLE=true
fi

# Backup keys_found.txt
if [ -f "$KEYS_FOUND_FILE" ]; then
    cp "$KEYS_FOUND_FILE" "${KEYS_FOUND_FILE}.bak"
fi

# Initialize log
echo "OPTIMIZED DMR RC4-40 Key Search Run V3 - $(date)" > $LOG_FILE
echo "=======================================" >> $LOG_FILE
echo "CPU: $(nproc) cores" >> $LOG_FILE
if $GPU_AVAILABLE; then
    echo "GPU: Available" >> $LOG_FILE
else
    echo "GPU: Not available" >> $LOG_FILE
fi
echo "=======================================" >> $LOG_FILE

# Find all SQLite databases in the build directory
DB_FILES=$(find "$BUILD_DIR" -name "*.db" | sort)
echo "Found $(echo "$DB_FILES" | wc -l) databases to search" >> $LOG_FILE
echo "=======================================" >> $LOG_FILE

# Block categorization adjusted based on benchmark results
# Our testing showed that parallel search has different outcomes than sequential search
# Using sequential search for common blocks is actually faster for our use case

# Common block values that might be used for DMR keys
# Based on known patterns and manufacturer defaults
# We'll try these in sequential fashion first for KNOWN_BLOCKS
KNOWN_BLOCKS=(78 32 DD AA BB CC)
 
# Blocks to try with GPU (where GPU excels) - used for PHASE 1 initial scan
GPU_BLOCKS=(78 32 DD AA 00 FF 77 33 11 22 44 88 55)

# Blocks to try with CPU (where CPU excels) - used for PHASE 1 initial scan
CPU_BLOCKS=(56 55 34 CC 54 35 CD BC AB BA 66 76 67)

# Track counts
TOTAL_TABLES=0
TOTAL_DATABASES=0
SUCCESS_COUNT=0

# Process a table with optimized block allocation
process_table() {
    local db_file=$1
    local table=$2
    
    # Extract the MI value from the table name
    MI=${table%_S0}
    MI=${MI#C_}
    
    echo -e "\nProcessing Table: $table (MI: $MI)" | tee -a $LOG_FILE
    
    # Get the first 3 AMBE frames from this table
    FRAMES=$(sqlite3 "$db_file" "SELECT ambe_hex FROM \"$table\" WHERE ambe_hex IS NOT NULL ORDER BY id LIMIT 3;")
    
    # Count how many frames we got
    FRAME_COUNT=$(echo "$FRAMES" | grep -v '^$' | wc -l)
    
    # Skip if we don't have at least 3 frames
    if [ "$FRAME_COUNT" -lt 3 ]; then
        echo "  Skipping: Not enough frames ($FRAME_COUNT/3)" >> $LOG_FILE
        return
    fi

    # Extract the frames
    FRAME1=$(echo "$FRAMES" | sed -n '1p')
    FRAME2=$(echo "$FRAMES" | sed -n '2p')
    FRAME3=$(echo "$FRAMES" | sed -n '3p')
    
    echo "  Frames: $FRAME1, $FRAME2, $FRAME3" >> $LOG_FILE
    
    # PHASE 1: Try common, known blocks sequentially first
    # This is actually faster for common keys than parallel search in our environment
    if $GPU_AVAILABLE; then
        echo -e "\n  [PHASE 1] Sequential search of known blocks with GPU" | tee -a $LOG_FILE
        echo "  ------------------------------------------------" | tee -a $LOG_FILE
        echo "  Strategy: Testing common blocks sequentially with GPU" | tee -a $LOG_FILE
        echo "  Reason: Benchmark showed sequential GPU search is faster for first few blocks" | tee -a $LOG_FILE
        echo "  Testing blocks: ${KNOWN_BLOCKS[*]}" | tee -a $LOG_FILE
        echo "  ------------------------------------------------" | tee -a $LOG_FILE
        
        BLOCK_COUNT=0
        TOTAL_KNOWN_BLOCKS=${#KNOWN_BLOCKS[@]}
        
        for BLOCK in "${KNOWN_BLOCKS[@]}"; do
            BLOCK_COUNT=$((BLOCK_COUNT + 1))
            echo "  [GPU] Testing common block: $BLOCK ($BLOCK_COUNT/$TOTAL_KNOWN_BLOCKS)" | tee -a $LOG_FILE
            
            # Count current lines in keys_found.txt
            CURRENT_LINES=0
            if [ -f "$KEYS_FOUND_FILE" ]; then
                CURRENT_LINES=$(wc -l < "$KEYS_FOUND_FILE")
            fi
            
            # Time the GPU execution
            START_TIME=$(date +%s)
            
            # Run GPU key finder
            TMP_OUTPUT=$(mktemp)
            echo "    Launching GPU search for block $BLOCK..." | tee -a $LOG_FILE
            $GPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
            GPU_EXIT=$?
            
            END_TIME=$(date +%s)
            ELAPSED=$((END_TIME - START_TIME))
            
            # Check for key
            if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
                # Get the new line count
                NEW_LINES=0
                if [ -f "$KEYS_FOUND_FILE" ]; then
                    NEW_LINES=$(wc -l < "$KEYS_FOUND_FILE")
                fi
                
                # Check if line count increased
                if [ "$NEW_LINES" -gt "$CURRENT_LINES" ]; then
                    # Get the last line of keys_found.txt
                    LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
                    
                    echo "  SUCCESS! GPU found key in $ELAPSED seconds: $LAST_KEY" | tee -a $LOG_FILE
                    echo "  Found key: $LAST_KEY (Table: $table, Block: $BLOCK, GPU, Time: ${ELAPSED}s)" >> "optimized_successful_keys.log"
                    
                    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
                    
                    # Remove temp file and exit function
                    rm -f "$TMP_OUTPUT"
                    return
                fi
            else
                echo "    No key found for block $BLOCK (search took ${ELAPSED}s)" | tee -a $LOG_FILE
            fi
            
            rm -f "$TMP_OUTPUT"
        }
    else
        echo -e "\n  [PHASE 1] Sequential search not available - GPU not found" | tee -a $LOG_FILE
    fi
    
    # PHASE 2: Parallel scan with specialized blocks
    # Try remaining blocks with GPU-optimized and CPU-optimized sets running in parallel
    KEY_FOUND=false
    echo -e "\n  [PHASE 2] Parallel specialized block search" | tee -a $LOG_FILE
    echo "  ------------------------------------------------" | tee -a $LOG_FILE
    echo "  Strategy: Assign blocks to processors based on benchmark performance" | tee -a $LOG_FILE
    echo "  Reason: Some blocks perform better on GPU, others on CPU" | tee -a $LOG_FILE
    echo "  ------------------------------------------------" | tee -a $LOG_FILE
    
    # Remove blocks we've already tried
    REMAINING_GPU_BLOCKS=()
    for BLOCK in "${GPU_BLOCKS[@]}"; do
        SKIP=false
        for KNOWN_BLOCK in "${KNOWN_BLOCKS[@]}"; do
            if [ "$BLOCK" = "$KNOWN_BLOCK" ]; then
                SKIP=true
                break
            fi
        done
        
        if [ "$SKIP" = false ]; then
            REMAINING_GPU_BLOCKS+=("$BLOCK")
        fi
    done
    
    REMAINING_CPU_BLOCKS=()
    for BLOCK in "${CPU_BLOCKS[@]}"; do
        SKIP=false
        for KNOWN_BLOCK in "${KNOWN_BLOCKS[@]}"; do
            if [ "$BLOCK" = "$KNOWN_BLOCK" ]; then
                SKIP=true
                break
            fi
        done
        
        if [ "$SKIP" = false ]; then
            REMAINING_CPU_BLOCKS+=("$BLOCK")
        fi
    done
    
    echo "  GPU-optimized blocks: ${REMAINING_GPU_BLOCKS[*]}" | tee -a $LOG_FILE
    echo "  CPU-optimized blocks: ${REMAINING_CPU_BLOCKS[*]}" | tee -a $LOG_FILE
    echo "  Launching parallel search processes..." | tee -a $LOG_FILE
    
    # Track start time for Phase 2
    PHASE2_START_TIME=$(date +%s)
    
    # Create a temporary directory for process communication
    TEMP_DIR=$(mktemp -d)
    PHASE2_SUCCESS_FILE="$TEMP_DIR/phase2_success"
    
    # Launch GPU processes for GPU optimized blocks
    if $GPU_AVAILABLE; then
        GPU_PID_LIST=""
        for BLOCK in "${REMAINING_GPU_BLOCKS[@]}"; do
            (
                # Count current lines in keys_found.txt
                CURRENT_LINES=0
                if [ -f "$KEYS_FOUND_FILE" ]; then
                    CURRENT_LINES=$(wc -l < "$KEYS_FOUND_FILE")
                fi
                
                # Create a marker file for each process
                PROCESS_FILE="$TEMP_DIR/gpu_${BLOCK}_started"
                touch "$PROCESS_FILE"
                
                # Record start time
                BLOCK_START_TIME=$(date +%s)
                
                # Run GPU key finder
                TMP_OUTPUT=$(mktemp)
                $GPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
                
                # Record end time
                BLOCK_END_TIME=$(date +%s)
                BLOCK_ELAPSED=$((BLOCK_END_TIME - BLOCK_START_TIME))
                
                # Remove the started marker
                rm -f "$PROCESS_FILE"
                
                # Create a completed marker
                touch "$TEMP_DIR/gpu_${BLOCK}_completed"
                
                # Check for key
                if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
                    # Get the new line count
                    NEW_LINES=0
                    if [ -f "$KEYS_FOUND_FILE" ]; then
                        NEW_LINES=$(wc -l < "$KEYS_FOUND_FILE")
                    fi
                    
                    # Check if line count increased
                    if [ "$NEW_LINES" -gt "$CURRENT_LINES" ]; then
                        # Get the last line of keys_found.txt
                        LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
                        
                        echo "  SUCCESS! GPU found key in block $BLOCK after ${BLOCK_ELAPSED}s: $LAST_KEY" > "$PHASE2_SUCCESS_FILE"
                        echo "  Found key: $LAST_KEY (Table: $table, Block: $BLOCK, GPU, Parallel, Time: ${BLOCK_ELAPSED}s)" >> "optimized_successful_keys.log"
                        
                        # Touch flag file to signal to other processes
                        touch "/tmp/key_found_${MI}"
                    fi
                fi
                
                rm -f "$TMP_OUTPUT"
            ) &
            GPU_PID_LIST="$GPU_PID_LIST $!"
        done
        echo "  Launched ${#REMAINING_GPU_BLOCKS[@]} GPU search processes" | tee -a $LOG_FILE
    else
        echo "  GPU not available, skipping GPU-optimized blocks" | tee -a $LOG_FILE
    fi
    
    # Launch CPU processes for CPU optimized blocks
    CPU_PID_LIST=""
    for BLOCK in "${REMAINING_CPU_BLOCKS[@]}"; do
        (
            # Count current lines in keys_found.txt
            CURRENT_LINES=0
            if [ -f "$KEYS_FOUND_FILE" ]; then
                CURRENT_LINES=$(wc -l < "$KEYS_FOUND_FILE")
            fi
            
            # Create a marker file for each process
            PROCESS_FILE="$TEMP_DIR/cpu_${BLOCK}_started"
            touch "$PROCESS_FILE"
            
            # Record start time
            BLOCK_START_TIME=$(date +%s)
            
            # Run CPU key finder
            TMP_OUTPUT=$(mktemp)
            $CPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
            
            # Record end time
            BLOCK_END_TIME=$(date +%s)
            BLOCK_ELAPSED=$((BLOCK_END_TIME - BLOCK_START_TIME))
            
            # Remove the started marker
            rm -f "$PROCESS_FILE"
            
            # Create a completed marker
            touch "$TEMP_DIR/cpu_${BLOCK}_completed"
            
            # Check for key
            if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
                # Get the new line count
                NEW_LINES=0
                if [ -f "$KEYS_FOUND_FILE" ]; then
                    NEW_LINES=$(wc -l < "$KEYS_FOUND_FILE")
                fi
                
                # Check if line count increased
                if [ "$NEW_LINES" -gt "$CURRENT_LINES" ]; then
                    # Get the last line of keys_found.txt
                    LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
                    
                    echo "  SUCCESS! CPU found key in block $BLOCK after ${BLOCK_ELAPSED}s: $LAST_KEY" > "$PHASE2_SUCCESS_FILE"
                    echo "  Found key: $LAST_KEY (Table: $table, Block: $BLOCK, CPU, Parallel, Time: ${BLOCK_ELAPSED}s)" >> "optimized_successful_keys.log"
                    
                    # Touch flag file to signal to other processes
                    touch "/tmp/key_found_${MI}"
                fi
            fi
            
            rm -f "$TMP_OUTPUT"
        ) &
        CPU_PID_LIST="$CPU_PID_LIST $!"
    done
    echo "  Launched ${#REMAINING_CPU_BLOCKS[@]} CPU search processes" | tee -a $LOG_FILE
    
    # Wait for all processes to finish or for a key to be found
    echo "  Waiting for parallel processes to complete..." | tee -a $LOG_FILE
    
    # Monitor progress
    while true; do
        # Check if a key was found
        if [ -f "/tmp/key_found_${MI}" ]; then
            # Key found, terminate other processes
            if [ -n "$GPU_PID_LIST" ]; then
                for PID in $GPU_PID_LIST; do
                    kill -9 $PID 2>/dev/null || true
                done
            fi
            
            for PID in $CPU_PID_LIST; do
                kill -9 $PID 2>/dev/null || true
            done
            
            # Output success message
            if [ -f "$PHASE2_SUCCESS_FILE" ]; then
                cat "$PHASE2_SUCCESS_FILE" | tee -a $LOG_FILE
            fi
            
            break
        fi
        
        # Check if all processes are done
        RUNNING_PROCESSES=$(find "$TEMP_DIR" -name "*_started" | wc -l)
        if [ "$RUNNING_PROCESSES" -eq 0 ]; then
            # All processes have completed
            COMPLETED_PROCESSES=$(find "$TEMP_DIR" -name "*_completed" | wc -l)
            echo "  All parallel processes completed (${COMPLETED_PROCESSES} total)" | tee -a $LOG_FILE
            break
        fi
        
        # Brief sleep to avoid CPU spinning
        sleep 0.5
    done
    
    # Calculate total time for Phase 2
    PHASE2_END_TIME=$(date +%s)
    PHASE2_ELAPSED=$((PHASE2_END_TIME - PHASE2_START_TIME))
    echo "  Phase 2 took ${PHASE2_ELAPSED} seconds to complete" | tee -a $LOG_FILE
    
    # Clean up temporary directory
    rm -rf "$TEMP_DIR"
    
    # Check if a key was found
    if [ -f "/tmp/key_found_${MI}" ]; then
        rm -f "/tmp/key_found_${MI}"
        KEY_FOUND=true
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        return
    fi
    
    # PHASE 3: Launch deep search if no key found in priority blocks
    echo -e "\n  [PHASE 3] Deep search for remaining blocks" | tee -a $LOG_FILE
    echo "  ------------------------------------------------" | tee -a $LOG_FILE
    echo "  Strategy: Comprehensive search of all remaining blocks" | tee -a $LOG_FILE
    echo "  Reason: Keys not found in common and optimized blocks require thorough search" | tee -a $LOG_FILE
    echo "  ------------------------------------------------" | tee -a $LOG_FILE
    
    # Create a new file for deep search to run independently
    DEEP_SEARCH_FILE="deep_search_${MI}.sh"
    echo "  Preparing deep search script: $DEEP_SEARCH_FILE" | tee -a $LOG_FILE
    
    cat > "$DEEP_SEARCH_FILE" << EOF
#!/bin/bash

# Deep Search Script (Generated by optimized_v3_search.sh)

# Deep search for MI $MI in $table
echo "Deep Search for MI: $MI in table $table started at \$(date)" > "deep_search_${MI}.log"
echo "Database: $db_file" >> "deep_search_${MI}.log"
echo "=========================================" >> "deep_search_${MI}.log"

# Get initial key count to track new keys
INITIAL_KEYS=0
if [ -f "$KEYS_FOUND_FILE" ]; then
    INITIAL_KEYS=\$(wc -l < "$KEYS_FOUND_FILE")
fi

# Set up search blocks
declare -a BLOCKS
for i in {0..255}; do
    if [ \$i -lt 16 ]; then
        BLOCKS[\$i]=\$(printf "0%X" \$i)
    else
        BLOCKS[\$i]=\$(printf "%X" \$i)
    fi
done

# Remove blocks we've already checked
ALL_CHECKED_BLOCKS=( "${KNOWN_BLOCKS[@]}" "${GPU_BLOCKS[@]}" "${CPU_BLOCKS[@]}" )
for BLOCK in \${ALL_CHECKED_BLOCKS[@]}; do
    for i in \${!BLOCKS[@]}; do
        if [ "\${BLOCKS[\$i]}" = "$BLOCK" ]; then
            unset BLOCKS[\$i]
        fi
    done
done

# Keep track of progress
TOTAL_BLOCKS=\${#BLOCKS[@]}
BLOCKS_PROCESSED=0

echo "Searching remaining \$TOTAL_BLOCKS blocks..." >> "deep_search_${MI}.log"

# Process by groups of 16 blocks (0x00-0x0F, 0x10-0x1F, etc.)
GROUP_SIZE=16
GROUP_COUNT=\$(( (\$TOTAL_BLOCKS + \$GROUP_SIZE - 1) / \$GROUP_SIZE ))

for GROUP in \$(seq 1 \$GROUP_COUNT); do
    GROUP_START=\$(( (\$GROUP - 1) * \$GROUP_SIZE ))
    GROUP_END=\$(( \$GROUP_START + \$GROUP_SIZE - 1 ))
    
    if [ \$GROUP_END -ge \$TOTAL_BLOCKS ]; then
        GROUP_END=\$(( \$TOTAL_BLOCKS - 1 ))
    fi
    
    # Get blocks for this group
    GROUP_BLOCKS=()
    for i in \$(seq \$GROUP_START \$GROUP_END); do
        if [ -n "\${BLOCKS[\$i]}" ]; then
            GROUP_BLOCKS+=("\${BLOCKS[\$i]}")
        fi
    done
    
    # Initialize counters for this group
    GROUP_COUNT=\${#GROUP_BLOCKS[@]}
    GROUP_PROCESSED=0
    
    # Process this group
    FIRST_BLOCK=\${GROUP_BLOCKS[0]}
    LAST_BLOCK=\${GROUP_BLOCKS[-1]}
    echo "Searching block range: \$FIRST_BLOCK-\$LAST_BLOCK (\$GROUP/\$GROUP_COUNT)" >> "deep_search_${MI}.log"
    
    for BLOCK in \${GROUP_BLOCKS[@]}; do
        echo "  Testing block: \$BLOCK" >> "deep_search_${MI}.log"
        
        # Try GPU first if available
        if $GPU_AVAILABLE; then
            # Count current lines in keys_found.txt
            CURRENT_LINES=0
            if [ -f "$KEYS_FOUND_FILE" ]; then
                CURRENT_LINES=\$(wc -l < "$KEYS_FOUND_FILE")
            fi
            
            # Run GPU key finder
            $GPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "\$BLOCK" -e "\$BLOCK" > /dev/null 2>&1
            
            # Check if a key was found
            if [ -f "$KEYS_FOUND_FILE" ]; then
                NEW_LINES=\$(wc -l < "$KEYS_FOUND_FILE")
                if [ "\$NEW_LINES" -gt "\$CURRENT_LINES" ]; then
                    LAST_KEY=\$(tail -n 1 "$KEYS_FOUND_FILE")
                    echo "GPU SUCCESS! Key found: \$LAST_KEY" >> "deep_search_${MI}.log"
                    echo "Found key: \$LAST_KEY (MI: $MI, Block: \$BLOCK, GPU)" >> "deep_search_keys.log"
                    exit 0
                fi
            fi
        else
            # If GPU not available, use CPU
            # Count current lines in keys_found.txt
            CURRENT_LINES=0
            if [ -f "$KEYS_FOUND_FILE" ]; then
                CURRENT_LINES=\$(wc -l < "$KEYS_FOUND_FILE")
            fi
            
            # Run CPU key finder
            $CPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "\$BLOCK" -e "\$BLOCK" > /dev/null 2>&1
            
            # Check if a key was found
            if [ -f "$KEYS_FOUND_FILE" ]; then
                NEW_LINES=\$(wc -l < "$KEYS_FOUND_FILE")
                if [ "\$NEW_LINES" -gt "\$CURRENT_LINES" ]; then
                    LAST_KEY=\$(tail -n 1 "$KEYS_FOUND_FILE")
                    echo "CPU SUCCESS! Key found: \$LAST_KEY" >> "deep_search_${MI}.log"
                    echo "Found key: \$LAST_KEY (MI: $MI, Block: \$BLOCK, CPU)" >> "deep_search_keys.log"
                    exit 0
                fi
            fi
        fi
        
        # Update group progress
        GROUP_PROCESSED=\$(( \$GROUP_PROCESSED + 1 ))
        
        # Update total progress
        BLOCKS_PROCESSED=\$(( \$BLOCKS_PROCESSED + 1 ))
        
        # Status update for each group
        if [ \$(( \$GROUP_PROCESSED % 16 )) -eq 0 ] || [ \$GROUP_PROCESSED -eq \$GROUP_COUNT ]; then
            echo "  Completed block group \$FIRST_BLOCK-\$LAST_BLOCK (\$GROUP/\$GROUP_COUNT of current group)" >> "deep_search_${MI}.log"
        fi
    done
done

# Check if we found any keys
FINAL_KEYS=0
if [ -f "$KEYS_FOUND_FILE" ]; then
    FINAL_KEYS=\$(wc -l < "$KEYS_FOUND_FILE")
fi

if [ "\$FINAL_KEYS" -gt "\$INITIAL_KEYS" ]; then
    echo "Search complete. Found \$((\$FINAL_KEYS - \$INITIAL_KEYS)) keys!" >> "deep_search_${MI}.log"
else
    echo "Search complete. No keys found for MI $MI." >> "deep_search_${MI}.log"
fi
EOF

    # Make deep search script executable
    chmod +x "$DEEP_SEARCH_FILE"
    
    # Launch deep search as a background process
    nohup "./$DEEP_SEARCH_FILE" > /dev/null 2>&1 &
    DEEP_PID=$!
    
    echo "  Deep search launched with PID $DEEP_PID" | tee -a $LOG_FILE
    echo "  $DEEP_PID" >> "deep_search_pids.txt"
}

# Process each database
for DB_FILE in $DB_FILES; do
    TOTAL_DATABASES=$((TOTAL_DATABASES + 1))
    
    echo -e "\n======================================="  >> $LOG_FILE
    echo "Analyzing database: $DB_FILE" | tee -a $LOG_FILE
    echo "======================================="  >> $LOG_FILE
    
    # Get a list of all C_*_S0 tables
    TABLES=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%_S0' ORDER BY name")
    TABLE_COUNT=$(echo "$TABLES" | grep -v '^$' | wc -l)
    
    echo "Found $TABLE_COUNT tables to analyze in this database" | tee -a $LOG_FILE
    
    # Skip if no tables found
    if [ "$TABLE_COUNT" -eq 0 ]; then
        echo "No C_*_S0 tables found in this database. Skipping." | tee -a $LOG_FILE
        continue
    fi
    
    # Process each table
    for TABLE in $TABLES; do
        # Skip empty lines
        if [ -z "$TABLE" ]; then
            continue
        fi
        
        TOTAL_TABLES=$((TOTAL_TABLES + 1))
        
        # Process this table
        process_table "$DB_FILE" "$TABLE"
        
        # Status update
        echo "Progress: $TOTAL_TABLES tables processed, $SUCCESS_COUNT keys found" | tee -a $LOG_FILE
        
        # Periodically back up the log
        if [ $((TOTAL_TABLES % 10)) -eq 0 ]; then
            cp $LOG_FILE "${LOG_FILE}.bak"
        fi
    done
    
    echo "Completed analysis of database: $DB_FILE" | tee -a $LOG_FILE
done

# Final summary
echo -e "\n=======================================" >> $LOG_FILE
echo "Search complete - $(date)" >> $LOG_FILE
echo "Total databases processed: $TOTAL_DATABASES" >> $LOG_FILE
echo "Total tables processed: $TOTAL_TABLES" >> $LOG_FILE
echo "Total keys found in quick scan: $SUCCESS_COUNT" >> $LOG_FILE
echo "Deep searches launched: $(wc -l < deep_search_pids.txt 2>/dev/null || echo 0)" >> $LOG_FILE
echo "=======================================" >> $LOG_FILE

echo "Search complete. Quick scan results in $LOG_FILE."
echo "Deep searches are still running in the background."
echo "Check deep_search_keys.log for keys found by deep searches."