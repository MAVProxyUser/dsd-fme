#!/bin/bash

# Script to test the optimized v2 search implementation on test data
# This will test three known keys in our test database

TEST_DB="/home/ubuntu/dsd-fme_sqlite/test_db/comprehensive_test_dmr.db"
LOG_FILE="optimized_v2_search_benchmark.log"
KEYS_FOUND_FILE="/home/ubuntu/dsd-fme/arc4keyfinder/keys_found.txt"

# Backup keys_found.txt
if [ -f "$KEYS_FOUND_FILE" ]; then
    cp "$KEYS_FOUND_FILE" "${KEYS_FOUND_FILE}.bak"
fi

# Empty the keys found file
> "$KEYS_FOUND_FILE"

# Initialize log
echo "OPTIMIZED V2 DMR RC4-40 Key Search Test - $(date)" > $LOG_FILE
echo "=======================================" >> $LOG_FILE
echo "System information:" >> $LOG_FILE
echo "CPU: $(cat /proc/cpuinfo | grep 'model name' | head -n 1 | cut -d: -f2 || grep 'CPU part' /proc/cpuinfo | head -n1)" >> $LOG_FILE
echo "CPU cores: $(nproc)" >> $LOG_FILE
echo -e "GPU: Xavier integrated GPU (Tegra)" >> $LOG_FILE
echo -e "RAM: $(free -h | grep Mem | awk '{print $2}')" >> $LOG_FILE
echo "=======================================" >> $LOG_FILE

# Test cases - define known MI and block values
declare -A TEST_CASES=(
    ["ABCDEF12"]="78"  # Known key: 0x12345678
    ["FEDC5432"]="32"  # Known key: 0x98765432
    ["12345678"]="DD"  # Known key: 0xAABBCCDD
)

echo "Running tests with optimized v2 search script on comprehensive_test_dmr.db" >> $LOG_FILE
echo "Test database contains 3 tables with known keys:" >> $LOG_FILE
echo "C_ABCDEF12_S0: Key 0x12345678 (block 0x78)" >> $LOG_FILE
echo "C_FEDC5432_S0: Key 0x98765432 (block 0x32)" >> $LOG_FILE
echo "C_12345678_S0: Key 0xAABBCCDD (block 0xDD)" >> $LOG_FILE
echo "=======================================" >> $LOG_FILE

# Import path and settings from optimized_search_v2.sh
BUILD_DIR="/home/ubuntu/dsd-fme_sqlite/test_db"
CPU_FINDER="/home/ubuntu/dsd-fme_sqlite/arc4keyfinder_multicore"
GPU_FINDER="/home/ubuntu/dsd-fme_sqlite/arc4keyfinder_cuda"

# Check for required tools
if [ ! -f "$CPU_FINDER" ]; then
    echo "ERROR: CPU executable not found at $CPU_FINDER" | tee -a $LOG_FILE
    exit 1
fi

if [ ! -f "$GPU_FINDER" ]; then
    echo "WARNING: GPU executable not found at $GPU_FINDER, falling back to CPU only" | tee -a $LOG_FILE
    GPU_AVAILABLE=false
else
    GPU_AVAILABLE=true
fi

# Block categories based on benchmark results
GPU_PRIORITY_BLOCKS=(78 32 DD AA) # Known or common keys, GPU is 2x faster
CPU_PRIORITY_BLOCKS=(55 56 34 CC) # Random blocks, CPU performs better
BALANCED_BLOCKS=(00 FF 01 87 88 99 12 BB) # Medium priority, GPU is slightly faster

# Process a table with optimized v2 approach
process_table_optimized_v2() {
    local table=$1
    local expected_block=$2
    
    # Extract the MI value from the table name
    MI=${table%_S0}
    MI=${MI#C_}
    
    echo -e "\n=======================================" | tee -a $LOG_FILE
    echo "Testing Table: $table (MI: $MI, Expected block: $expected_block)" | tee -a $LOG_FILE
    echo "=======================================" | tee -a $LOG_FILE
    
    # Get the first 3 AMBE frames from this table
    FRAMES=$(sqlite3 "$TEST_DB" "SELECT ambe_hex FROM \"$table\" WHERE ambe_hex IS NOT NULL ORDER BY id LIMIT 3;")
    
    # Extract the frames
    FRAME1=$(echo "$FRAMES" | sed -n '1p')
    FRAME2=$(echo "$FRAMES" | sed -n '2p')
    FRAME3=$(echo "$FRAMES" | sed -n '3p')
    
    echo "  Frames: $FRAME1, $FRAME2, $FRAME3" >> $LOG_FILE
    
    # Empty the keys found file
    > "$KEYS_FOUND_FILE"
    
    # APPROACH 2: Optimized v2 search - using optimized block allocation
    echo "Optimized v2 search approach - block categorization:" | tee -a $LOG_FILE
    START_TIME=$(date +%s)
    
    KEY_FOUND=false
    
    # First try GPU priority blocks with GPU
    if $GPU_AVAILABLE; then
        echo "  Testing GPU priority blocks: ${GPU_PRIORITY_BLOCKS[*]}" | tee -a $LOG_FILE
        
        # For parallel processing, launch all GPU priority blocks at once
        for BLOCK in "${GPU_PRIORITY_BLOCKS[@]}"; do
            (
                TMP_OUTPUT=$(mktemp)
                $GPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
                
                if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
                    # Check if a key was found
                    if [ -f "$KEYS_FOUND_FILE" ] && [ -s "$KEYS_FOUND_FILE" ]; then
                        LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
                        echo "  SUCCESS! GPU found key in block $BLOCK: $LAST_KEY" | tee -a $LOG_FILE
                        # Signal to parent process
                        touch "/tmp/key_found_${MI}"
                    fi
                fi
                
                rm -f "$TMP_OUTPUT"
            ) &
        done
        
        # Wait for all GPU processes to complete
        wait
        
        # Check if any process found a key
        if [ -f "/tmp/key_found_${MI}" ]; then
            KEY_FOUND=true
            rm -f "/tmp/key_found_${MI}"
        fi
    fi
    
    # If key not found, try CPU priority blocks
    if [ "$KEY_FOUND" = false ]; then
        echo "  Testing CPU priority blocks: ${CPU_PRIORITY_BLOCKS[*]}" | tee -a $LOG_FILE
        
        # For parallel processing, launch all CPU priority blocks at once
        for BLOCK in "${CPU_PRIORITY_BLOCKS[@]}"; do
            (
                TMP_OUTPUT=$(mktemp)
                $CPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
                
                if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
                    # Check if a key was found
                    if [ -f "$KEYS_FOUND_FILE" ] && [ -s "$KEYS_FOUND_FILE" ]; then
                        LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
                        echo "  SUCCESS! CPU found key in block $BLOCK: $LAST_KEY" | tee -a $LOG_FILE
                        # Signal to parent process
                        touch "/tmp/key_found_${MI}"
                    fi
                fi
                
                rm -f "$TMP_OUTPUT"
            ) &
        done
        
        # Wait for all CPU processes to complete
        wait
        
        # Check if any process found a key
        if [ -f "/tmp/key_found_${MI}" ]; then
            KEY_FOUND=true
            rm -f "/tmp/key_found_${MI}"
        fi
    fi
    
    # If still not found, try balanced blocks with mixed GPU/CPU
    if [ "$KEY_FOUND" = false ]; then
        echo "  Testing balanced blocks: ${BALANCED_BLOCKS[*]}" | tee -a $LOG_FILE
        
        # Split the balanced blocks between CPU and GPU
        GPU_BALANCED_BLOCKS=()
        CPU_BALANCED_BLOCKS=()
        
        i=0
        for BLOCK in "${BALANCED_BLOCKS[@]}"; do
            if [ $((i % 10)) -lt 6 ]; then
                # 60% to GPU
                GPU_BALANCED_BLOCKS+=("$BLOCK")
            else
                # 40% to CPU
                CPU_BALANCED_BLOCKS+=("$BLOCK")
            fi
            i=$((i + 1))
        done
        
        # Launch GPU processes
        if $GPU_AVAILABLE; then
            for BLOCK in "${GPU_BALANCED_BLOCKS[@]}"; do
                (
                    TMP_OUTPUT=$(mktemp)
                    $GPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
                    
                    if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
                        # Check if a key was found
                        if [ -f "$KEYS_FOUND_FILE" ] && [ -s "$KEYS_FOUND_FILE" ]; then
                            LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
                            echo "  SUCCESS! GPU found key in balanced block $BLOCK: $LAST_KEY" | tee -a $LOG_FILE
                            # Signal to parent process
                            touch "/tmp/key_found_${MI}"
                        fi
                    fi
                    
                    rm -f "$TMP_OUTPUT"
                ) &
            done
        fi
        
        # Launch CPU processes
        for BLOCK in "${CPU_BALANCED_BLOCKS[@]}"; do
            (
                TMP_OUTPUT=$(mktemp)
                $CPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
                
                if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
                    # Check if a key was found
                    if [ -f "$KEYS_FOUND_FILE" ] && [ -s "$KEYS_FOUND_FILE" ]; then
                        LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
                        echo "  SUCCESS! CPU found key in balanced block $BLOCK: $LAST_KEY" | tee -a $LOG_FILE
                        # Signal to parent process
                        touch "/tmp/key_found_${MI}"
                    fi
                fi
                
                rm -f "$TMP_OUTPUT"
            ) &
        done
        
        # Wait for all processes to complete
        wait
        
        # Check if any process found a key
        if [ -f "/tmp/key_found_${MI}" ]; then
            KEY_FOUND=true
            rm -f "/tmp/key_found_${MI}"
        fi
    fi
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    if [ "$KEY_FOUND" = true ]; then
        echo "  Found key in $ELAPSED seconds" | tee -a $LOG_FILE
    else
        echo "  No key found in priority blocks. Would launch deep search." | tee -a $LOG_FILE
    fi
}

# Test each case
for MI in "${!TEST_CASES[@]}"; do
    TABLE="C_${MI}_S0"
    BLOCK="${TEST_CASES[$MI]}"
    
    process_table_optimized_v2 "$TABLE" "$BLOCK"
done

echo -e "\n=======================================" | tee -a $LOG_FILE
echo "Test complete - $(date)" | tee -a $LOG_FILE
echo "=======================================" | tee -a $LOG_FILE

# Restore original keys_found.txt
if [ -f "${KEYS_FOUND_FILE}.bak" ]; then
    mv "${KEYS_FOUND_FILE}.bak" "$KEYS_FOUND_FILE"
fi