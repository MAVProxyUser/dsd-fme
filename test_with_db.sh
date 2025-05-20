#!/bin/bash

# Test script for the unified RC4 key finder with real database data

# Build the unified implementation
echo "Building unified implementation..."
make -f Makefile.unified

# Test data from test_db/test_dmr.db
FRAME1="7805077400004000"
FRAME2="ED2D4F7100006000"
FRAME3="596AF1C800008000"
MI="ABCDEF12"

echo -e "\nRunning test with data from test_db/test_dmr.db:"
echo "Frame 1: $FRAME1"
echo "Frame 2: $FRAME2"
echo "Frame 3: $FRAME3"
echo "MI: $MI"
echo ""

# Run with a limited block range for quicker testing (0x78 is the first byte of the first frame)
./arc4keyfinder_unified --mode 1 --frame "$FRAME1" --frame "$FRAME2" --frame "$FRAME3" --mi "$MI" --start-block 0x78 --end-block 0x78 --verbose

echo -e "\nTest completed."