#!/bin/bash

# Enhanced test script demonstrating both optimal (18-frame) and minimal (3-frame) approaches

echo "Building unified implementation..."
make -f Makefile.unified

# Create a directory for our test data if it doesn't exist
mkdir -p test_db/optimal_test

# ==========================================
# SCENARIO 1: Optimal 18-frame superframe data
# ==========================================
echo -e "\n[SCENARIO 1] Testing with optimal 18-frame superframe (Key: 00000001)"

# Generate 18 frames of synthesized data for the first superframe
# For demonstration, we're generating AMBE frames that would be encrypted with key 00000001
# These would normally come from a database query
FRAMES_18=(
    "7805077400004000" # Key byte 0x01 leaks into first frame
    "ED2D4F7100006000"
    "596AF1C800008000"
    "A104B23100001000"
    "F392A45600002000"
    "C823D67800003000"
    "3B561A9000004000"
    "D49F2E1200005000"
    "9A37C56700006000"
    "4E70F89A00007000"
    "B2C5D34500008000"
    "2871E69B00009000"
    "7F39AD4C0000A000"
    "E5C12F670000B000"
    "0A73B8900000C000"
    "5946CD120000D000"
    "C08F315E0000E000"
    "86D7492A0000F000"
)

# Create a file to store the test data
echo "Writing 18-frame test data to test_db/optimal_test/superframe_key_00000001.txt"
rm -f test_db/optimal_test/superframe_key_00000001.txt
for frame in "${FRAMES_18[@]}"; do
    echo "$frame" >> test_db/optimal_test/superframe_key_00000001.txt
done

# Run the test with all 18 frames - this should find the key very quickly
echo -e "\nRunning with all 18 frames from superframe:"
COMMAND="./arc4keyfinder_unified --mode 1 --mi \"00000001\" --start-block 0x01 --end-block 0x01 --verbose"

# Add each frame to the command
for frame in "${FRAMES_18[@]}"; do
    COMMAND+=" --frame \"$frame\""
done

# Execute and time the command
time eval "$COMMAND"

# ==========================================
# SCENARIO 2: Minimal 3-frame approach with radio sequential keys
# ==========================================
echo -e "\n[SCENARIO 2] Testing with minimal 3-frame approach"

# Create test data for several radio default sequential keys (00000001-00000100)
# We'll test a few different ones to check the "keys tested" counter
declare -A TEST_KEYS
TEST_KEYS=(
    ["00000001"]="01" # First key, should be found very quickly
    ["00000042"]="42" # Middle key, should take longer
    ["0000007F"]="7F" # Higher key, will test more keys
    ["000000B3"]="B3" # Even higher, testing more of the keyspace
)

for key_hex in "${!TEST_KEYS[@]}"; do
    block="${TEST_KEYS[$key_hex]}"
    echo -e "\nTesting with key $key_hex (block $block)"
    
    # Generate 3 frames that would be encrypted with this key
    # The first byte of first frame often leaks the block byte
    FRAME1="${block}05077400004000"
    FRAME2="ED2D4F7100006000"
    FRAME3="596AF1C800008000"
    
    echo "FRAME1: $FRAME1"
    echo "FRAME2: $FRAME2" 
    echo "FRAME3: $FRAME3"
    echo "MI: $key_hex"
    
    # Run the search with timing to compare performance
    echo -e "\nRunning targeted block search (block 0x$block only):"
    time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
        --mi "$key_hex" --start-block "0x$block" --end-block "0x$block" --verbose
        
    # For one of the tests, run a full search to properly test the counter
    if [ "$block" == "B3" ]; then
        echo -e "\nRunning full search for key $key_hex to test key counter:"
        time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
            --mi "$key_hex" --verbose
    fi
done

echo -e "\nAll tests completed."