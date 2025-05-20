#!/bin/bash

# Script to test the original search implementation on test data
# This will test three known keys in our test database

TEST_DB="/home/ubuntu/dsd-fme_sqlite/test_db/comprehensive_test_dmr.db"
LOG_FILE="original_search_benchmark.log"
KEYS_FOUND_FILE="/home/ubuntu/dsd-fme/arc4keyfinder/keys_found.txt"

# Backup keys_found.txt
if [ -f "$KEYS_FOUND_FILE" ]; then
    cp "$KEYS_FOUND_FILE" "${KEYS_FOUND_FILE}.bak"
fi

# Empty the keys found file
> "$KEYS_FOUND_FILE"

# Initialize log
echo "ORIGINAL DMR RC4-40 Key Search Test - $(date)" > $LOG_FILE
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

echo "Running tests with original search script on comprehensive_test_dmr.db" >> $LOG_FILE
echo "Test database contains 3 tables with known keys:" >> $LOG_FILE
echo "C_ABCDEF12_S0: Key 0x12345678 (block 0x78)" >> $LOG_FILE
echo "C_FEDC5432_S0: Key 0x98765432 (block 0x32)" >> $LOG_FILE
echo "C_12345678_S0: Key 0xAABBCCDD (block 0xDD)" >> $LOG_FILE
echo "=======================================" >> $LOG_FILE

# Import path and settings from optimized_search.sh
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

# Process a table with original approach
process_table_original() {
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
    
    # APPROACH 1: Simulate original search - trying priority blocks first
    PRIORITY_BLOCKS=(78 32 56 DD 12 34 AA BB CC 00 FF)
    
    echo "Original search approach - sequential priority blocks:" | tee -a $LOG_FILE
    START_TIME=$(date +%s)
    
    KEY_FOUND=false
    
    for BLOCK in "${PRIORITY_BLOCKS[@]}"; do
        echo "  Testing block: $BLOCK" | tee -a $LOG_FILE
        
        # Try GPU first if available
        if $GPU_AVAILABLE; then
            TMP_OUTPUT=$(mktemp)
            $GPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
            
            if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
                LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
                echo "  SUCCESS! GPU found key: $LAST_KEY" | tee -a $LOG_FILE
                KEY_FOUND=true
                rm -f "$TMP_OUTPUT"
                break
            fi
            
            rm -f "$TMP_OUTPUT"
        fi
        
        # Try CPU as fallback or if GPU not available
        TMP_OUTPUT=$(mktemp)
        $CPU_FINDER -m 1 -f "$FRAME1" -f "$FRAME2" -f "$FRAME3" -i "$MI" -s "$BLOCK" -e "$BLOCK" > "$TMP_OUTPUT" 2>&1
        
        if grep -q "KEY FOUND" "$TMP_OUTPUT"; then
            LAST_KEY=$(tail -n 1 "$KEYS_FOUND_FILE")
            echo "  SUCCESS! CPU found key: $LAST_KEY" | tee -a $LOG_FILE
            KEY_FOUND=true
            rm -f "$TMP_OUTPUT"
            break
        fi
        
        rm -f "$TMP_OUTPUT"
    done
    
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
    
    process_table_original "$TABLE" "$BLOCK"
done

echo -e "\n=======================================" | tee -a $LOG_FILE
echo "Test complete - $(date)" | tee -a $LOG_FILE
echo "=======================================" | tee -a $LOG_FILE

# Restore original keys_found.txt
if [ -f "${KEYS_FOUND_FILE}.bak" ]; then
    mv "${KEYS_FOUND_FILE}.bak" "$KEYS_FOUND_FILE"
fi