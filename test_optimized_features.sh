#!/bin/bash

# Test script demonstrating the new radio default key and 18-frame optimizations

echo "Building unified implementation..."
make -f Makefile.unified

# Create a directory for test data
mkdir -p test_db/optimized_test

echo -e "\n====================================================="
echo "DEMONSTRATING RADIO DEFAULT KEY OPTIMIZATION"
echo "====================================================="

# Test with a radio default key (channel 42 = key 0000002A)
KEY_HEX="0000002A"
BLOCK="2A"
FRAME1="${BLOCK}05077400004000"
FRAME2="ED2D4F7100006000"
FRAME3="596AF1C800008000"

echo -e "\nTesting with radio default key $KEY_HEX (Channel 42):"
echo "Frame 1: $FRAME1 (Notice first byte matches block: $BLOCK)"
echo "Frame 2: $FRAME2" 
echo "Frame 3: $FRAME3"
echo "MI: $KEY_HEX"

# Run with radio defaults optimization enabled
echo -e "\nRunning with --radio-defaults:"
time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
    --mi "$KEY_HEX" --radio-defaults --verbose

# Compare with standard search
echo -e "\nRunning without --radio-defaults (standard search):"
time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
    --mi "$KEY_HEX" --start-block 0x10 --end-block 0x30 --verbose

echo -e "\n====================================================="
echo "DEMONSTRATING 18-FRAME SUPERFRAME OPTIMIZATION"
echo "====================================================="

# Generate 18 frames for a full superframe
TEST_KEY="ABCDEF78"
TEST_BLOCK="78"
FRAME1="${TEST_BLOCK}05077400004000"
FRAME2="ED2D4F7100006000"
FRAME3="596AF1C800008000"

echo -e "\nGenerating 18-frame superframe data..."
FRAMES_18=(
    "$FRAME1" "$FRAME2" "$FRAME3"
    "A104B23100001000" "F392A45600002000" "C823D67800003000"
    "3B561A9000004000" "D49F2E1200005000" "9A37C56700006000"
    "4E70F89A00007000" "B2C5D34500008000" "2871E69B00009000"
    "7F39AD4C0000A000" "E5C12F670000B000" "0A73B8900000C000"
    "5946CD120000D000" "C08F315E0000E000" "86D7492A0000F000"
)

# Write frame data to a file
echo "Writing 18-frame data to test_db/optimized_test/superframe_test.txt"
rm -f test_db/optimized_test/superframe_test.txt
for frame in "${FRAMES_18[@]}"; do
    echo "$frame" >> test_db/optimized_test/superframe_test.txt
done

# Test with standard 3-frame approach
echo -e "\nTesting with standard 3-frame approach:"
time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
    --mi "$TEST_KEY" --start-block "0x$TEST_BLOCK" --end-block "0x$TEST_BLOCK" --verbose

# Build command with all 18 frames
echo -e "\nTesting with optimal 18-frame approach:"
COMMAND="./arc4keyfinder_unified --mode 1 --mi \"$TEST_KEY\" --start-block 0x$TEST_BLOCK --end-block 0x$TEST_BLOCK --optimal-frames --verbose"
for frame in "${FRAMES_18[@]}"; do
    COMMAND+=" --frame \"$frame\""
done

# Execute the command
time eval "$COMMAND"

echo -e "\n====================================================="
echo "DEMONSTRATING KEYS TESTED COUNTER FIX"
echo "====================================================="

# Test the key counter fix with a full search where the key is near the end
echo -e "\nTesting key counter fix with a challenging key (key block at end of search range):"
HARD_KEY="000000F7"
HARD_BLOCK="F7"
FRAME1="F705077400004000"
FRAME2="ED2D4F7100006000"
FRAME3="596AF1C800008000"

echo "Frame 1: $FRAME1"
echo "Frame 2: $FRAME2" 
echo "Frame 3: $FRAME3"
echo "MI: $HARD_KEY"

# Run a search that will test many keys
time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
    --mi "$HARD_KEY" --start-block 0x00 --end-block 0xFF --verbose

echo -e "\nAll optimization tests completed."