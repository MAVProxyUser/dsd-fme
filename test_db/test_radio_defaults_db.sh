#!/bin/bash

# Script to test the recovery of radio default keys from test database

DB_PATH="test_db/radio_defaults_test.db"
RESULTS_FILE="test_db/default_keys_results.txt"
LOG_DIR="test_db/logs"

# Create logs directory if it doesn't exist
mkdir -p $LOG_DIR

# Build the unified implementation
echo "Building unified implementation..."
make -f Makefile.unified

# Initialize results file
echo "# DMR Radio Default Keys Test Results" > $RESULTS_FILE
echo "# $(date)" >> $RESULTS_FILE
echo "" >> $RESULTS_FILE
echo "| Table | Key (Expected) | Block | Status | Time (s) | Method |" >> $RESULTS_FILE
echo "|-------|--------------|-------|--------|----------|--------|" >> $RESULTS_FILE

# Get list of test tables with their expected keys
echo "Getting test tables from database..."
TABLES=$(sqlite3 $DB_PATH "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%_S0' ORDER BY name;")

# Test each table
for TABLE in $TABLES; do
    # Extract the key from the table name
    KEY_HEX=${TABLE:2:8}
    BLOCK_HEX=${KEY_HEX: -2}
    
    # Get the MI from the database
    MI_HEX=$(sqlite3 $DB_PATH "SELECT mi_hex FROM radio_defaults_info WHERE key_hex='$KEY_HEX' LIMIT 1;")
    
    echo "========================================================"
    echo "Testing table: $TABLE"
    echo "Expected key: $KEY_HEX (Block: $BLOCK_HEX)"
    echo "Using MI: $MI_HEX (different from key for realistic testing)"
    
    # Get the frames from the database
    FRAMES=()
    while read -r FRAME; do
        FRAMES+=("$FRAME")
    done < <(sqlite3 $DB_PATH "SELECT ambe_hex FROM $TABLE ORDER BY id LIMIT 18;")
    
    # Print frame information
    echo "Found ${#FRAMES[@]} frames:"
    for ((i=0; i<${#FRAMES[@]} && i<3; i++)); do
        echo "Frame $((i+1)): ${FRAMES[i]}"
    done
    if [ ${#FRAMES[@]} -gt 3 ]; then
        echo "... plus $((${#FRAMES[@]}-3)) additional frames"
    fi
    
    # Test 1: Using radio defaults optimization
    echo -e "\nTest 1: Using --radio-defaults optimization"
    LOG_FILE="$LOG_DIR/${KEY_HEX}_radio_defaults.log"
    
    # Build the command for first 3 frames
    CMD="./arc4keyfinder_unified --mode 1 --mi \"$MI_HEX\" --radio-defaults --verbose"
    for ((i=0; i<3 && i<${#FRAMES[@]}; i++)); do
        CMD+=" --frame \"${FRAMES[i]}\""
    done
    
    # Run the command and time it
    echo "Running: $CMD"
    START_TIME=$(date +%s.%N)
    $CMD > $LOG_FILE 2>&1
    RESULT=$?
    END_TIME=$(date +%s.%N)
    TIME_TAKEN=$(echo "$END_TIME - $START_TIME" | bc)
    
    # Check if key was found
    if grep -q "SUCCESS! KEY FOUND" $LOG_FILE; then
        echo "✅ Key found with radio defaults optimization!"
        echo "| $TABLE | $KEY_HEX | 0x$BLOCK_HEX | ✅ Success | $TIME_TAKEN | Radio Defaults |" >> $RESULTS_FILE
    else
        echo "❌ Key not found with radio defaults optimization."
        echo "| $TABLE | $KEY_HEX | 0x$BLOCK_HEX | ❌ Failed | $TIME_TAKEN | Radio Defaults |" >> $RESULTS_FILE
    fi
    
    # Test 2: Without optimization (targeted block)
    echo -e "\nTest 2: Using targeted block search (no optimization)"
    LOG_FILE="$LOG_DIR/${KEY_HEX}_targeted.log"
    
    # Build the command for first 3 frames with targeted block
    CMD="./arc4keyfinder_unified --mode 1 --mi \"$MI_HEX\" --start-block 0x$BLOCK_HEX --end-block 0x$BLOCK_HEX --verbose"
    for ((i=0; i<3 && i<${#FRAMES[@]}; i++)); do
        CMD+=" --frame \"${FRAMES[i]}\""
    done
    
    # Run the command and time it
    echo "Running: $CMD"
    START_TIME=$(date +%s.%N)
    $CMD > $LOG_FILE 2>&1
    RESULT=$?
    END_TIME=$(date +%s.%N)
    TIME_TAKEN=$(echo "$END_TIME - $START_TIME" | bc)
    
    # Check if key was found
    if grep -q "SUCCESS! KEY FOUND" $LOG_FILE; then
        echo "✅ Key found with targeted block search!"
        echo "| $TABLE | $KEY_HEX | 0x$BLOCK_HEX | ✅ Success | $TIME_TAKEN | Targeted Block |" >> $RESULTS_FILE
    else
        echo "❌ Key not found with targeted block search."
        echo "| $TABLE | $KEY_HEX | 0x$BLOCK_HEX | ❌ Failed | $TIME_TAKEN | Targeted Block |" >> $RESULTS_FILE
    fi
    
    # Test 3: If table has 18 AMBE frames, test with optimal frames
    if [ ${#FRAMES[@]} -eq 18 ]; then
        echo -e "\nTest 3: Using --optimal-frames with 18 AMBE frames (3 superframes)"
        LOG_FILE="$LOG_DIR/${KEY_HEX}_optimal_frames.log"
        
        # Build the command for all 18 frames
        CMD="./arc4keyfinder_unified --mode 1 --mi \"$MI_HEX\" --start-block 0x$BLOCK_HEX --end-block 0x$BLOCK_HEX --optimal-frames --verbose"
        for FRAME in "${FRAMES[@]}"; do
            CMD+=" --frame \"$FRAME\""
        done
        
        # Run the command and time it
        echo "Running: $CMD"
        START_TIME=$(date +%s.%N)
        $CMD > $LOG_FILE 2>&1
        RESULT=$?
        END_TIME=$(date +%s.%N)
        TIME_TAKEN=$(echo "$END_TIME - $START_TIME" | bc)
        
        # Check if key was found
        if grep -q "SUCCESS! KEY FOUND" $LOG_FILE; then
            echo "✅ Key found with optimal frames!"
            echo "| $TABLE | $KEY_HEX | 0x$BLOCK_HEX | ✅ Success | $TIME_TAKEN | Optimal 18 Frames |" >> $RESULTS_FILE
        else
            echo "❌ Key not found with optimal frames."
            echo "| $TABLE | $KEY_HEX | 0x$BLOCK_HEX | ❌ Failed | $TIME_TAKEN | Optimal 18 Frames |" >> $RESULTS_FILE
        fi
    fi
    
    echo -e "\n"
done

echo "Tests completed!"
echo "Results written to: $RESULTS_FILE"
echo "Detailed logs in: $LOG_DIR/"

# Print summary table
cat $RESULTS_FILE