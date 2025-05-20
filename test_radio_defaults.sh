#!/bin/bash

# Test script for demonstrating radio default keys and frame count optimization
# Uses a manual approach since we can't modify the underlying code directly

echo "Building unified implementation..."
make -f Makefile.unified

# Create a directory for test data
mkdir -p test_db/radio_defaults

echo -e "\n==================================================="
echo "DEMONSTRATING RADIO DEFAULT KEY RECOVERY"
echo "==================================================="
echo "Many DMR radios use default keys in the format 0000000X where X is the channel number (1-100)"
echo "This means the last byte (block) of the key is often 0x01, 0x02, 0x03, etc."
echo "We can exploit this pattern by prioritizing these blocks in our search.\n"

# Generate test data for different channel numbers
CHANNELS=(01 10 20 30 40 50 64 99)

for channel in "${CHANNELS[@]}"; do
    # Format the key as 000000XX (hex)
    key_hex="000000$channel"
    echo -e "\n--- Testing Channel $channel (Key: $key_hex) ---"
    
    # Convert channel from hex to decimal for key construction
    channel_dec=$((16#$channel))
    
    # Create a first frame where the first byte leaks the key's last byte
    # This is a common pattern we can exploit to speed up key recovery
    FRAME1="$channel"
    # Pad the first frame to 16 hex characters (8 bytes)
    while [ ${#FRAME1} -lt 16 ]; do
        FRAME1="${FRAME1}0"
    done
    
    # Create additional frames
    FRAME2="ED2D4F7100006000"
    FRAME3="596AF1C800008000"
    
    echo "Frame 1: $FRAME1 (Notice first byte matches channel number: $channel)"
    echo "Frame 2: $FRAME2"
    echo "Frame 3: $FRAME3"
    echo "MI: $key_hex"
    
    # For channel 30 and 50, demonstrate with optimal 18-frame approach
    if [ "$channel" == "30" ] || [ "$channel" == "50" ]; then
        echo -e "\nDemonstrating optimal 18-frame approach for channel $channel"
        
        # Generate all 18 frames (just repeating our 3 for demonstration)
        frames=()
        for ((i=0; i<6; i++)); do
            frames+=("$FRAME1" "$FRAME2" "$FRAME3")
        done
        
        # Build command with all 18 frames
        COMMAND="./arc4keyfinder_unified --mode 1 --mi \"$key_hex\" --start-block 0x$channel --end-block 0x$channel --verbose"
        for frame in "${frames[@]}"; do
            COMMAND+=" --frame \"$frame\""
        done
        
        # Execute the command with timing
        time eval "$COMMAND"
    else
        # Regular 3-frame approach for other channels
        echo -e "\nUsing minimal 3-frame approach for channel $channel"
        time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
            --mi "$key_hex" --start-block "0x$channel" --end-block "0x$channel" --verbose
    fi
    
    # For channel 64 and 99, run a full search to test the counter
    if [ "$channel" == "64" ] || [ "$channel" == "99" ]; then
        echo -e "\nRunning full search for channel $channel to test key counter:"
        time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
            --mi "$key_hex" --verbose
    fi
done

echo -e "\n==================================================="
echo "DEMONSTRATING FRAME COUNT OPTIMIZATION"
echo "==================================================="
echo "DMR encryption works in superframes. Using more frames from the same superframe"
echo "increases the accuracy of key recovery. Minimum is 3 frames, optimal is 18 frames."
echo "However, frames MUST be from the same superframe.\n"

# Define a test key
TEST_KEY="ABCDEF78"
TEST_BLOCK="78"

# Demonstrate with varying numbers of frames
echo -e "\n--- Testing with minimal 3 frames ---"
FRAME1="${TEST_BLOCK}05077400004000"
FRAME2="ED2D4F7100006000"
FRAME3="596AF1C800008000"

echo "Frame 1: $FRAME1"
echo "Frame 2: $FRAME2" 
echo "Frame 3: $FRAME3"
echo "MI: $TEST_KEY"

time ./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" \
    --mi "$TEST_KEY" --start-block "0x$TEST_BLOCK" --end-block "0x$TEST_BLOCK" --verbose

echo -e "\n--- Testing with 6 frames ---"
# Add some additional frames
FRAME4="A104B23100001000"
FRAME5="F392A45600002000"
FRAME6="C823D67800003000"

COMMAND="./arc4keyfinder_unified --mode 1 --mi \"$TEST_KEY\" --start-block 0x$TEST_BLOCK --end-block 0x$TEST_BLOCK --verbose"
COMMAND+=" --frame \"$FRAME1\" --frame \"$FRAME2\" --frame \"$FRAME3\""
COMMAND+=" --frame \"$FRAME4\" --frame \"$FRAME5\" --frame \"$FRAME6\""

time eval "$COMMAND"

echo -e "\n--- Testing with optimal 18 frames ---"
# Generate additional frames for a total of 18
FRAMES_18=(
    "$FRAME1" "$FRAME2" "$FRAME3" "$FRAME4" "$FRAME5" "$FRAME6"
    "3B561A9000004000" "D49F2E1200005000" "9A37C56700006000"
    "4E70F89A00007000" "B2C5D34500008000" "2871E69B00009000"
    "7F39AD4C0000A000" "E5C12F670000B000" "0A73B8900000C000"
    "5946CD120000D000" "C08F315E0000E000" "86D7492A0000F000"
)

COMMAND="./arc4keyfinder_unified --mode 1 --mi \"$TEST_KEY\" --start-block 0x$TEST_BLOCK --end-block 0x$TEST_BLOCK --verbose"
for frame in "${FRAMES_18[@]}"; do
    COMMAND+=" --frame \"$frame\""
done

time eval "$COMMAND"

echo -e "\nAll tests completed."