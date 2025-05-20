#!/bin/bash

# Test script for the unified RC4 key finder implementation

# Build the unified implementation
echo "Building unified implementation..."
make -f Makefile.unified

# Run a test with the --test flag to use test data
echo -e "\nRunning test with test data:"
./arc4keyfinder_unified --test --verbose

# If you have actual data to test, you can use it with parameters like:
# ./arc4keyfinder_unified --mode 1 --frame "00112233445566778899AABBCCDDEEFF" --mi "0011223344556677" --start-block 0 --end-block 255 --verbose

echo -e "\nTest completed."