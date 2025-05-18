#!/usr/bin/env python3
"""
Test script to verify Radio ID extraction and prepare capture
"""

import subprocess
import time
import os
from datetime import datetime

def prepare_capture_environment():
    """Prepare the capture environment"""
    
    # Create capture directory
    capture_dir = os.path.expanduser("~/DMR_Captures")
    os.makedirs(capture_dir, exist_ok=True)
    
    print(f"Capture directory: {capture_dir}")
    print("\nRadio Configuration:")
    print("- Radio ID 6969: CLEAR (no encryption)")
    print("- Radio ID 1234: ENCRYPTED")
    
    return capture_dir

def create_capture_script():
    """Create a capture script with proper database naming"""
    
    script_content = """#!/bin/bash
# DMR Capture Script

CAPTURE_DIR=~/DMR_Captures
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "Starting DMR capture..."
echo "Radio ID 6969: CLEAR"
echo "Radio ID 1234: ENCRYPTED"
echo ""
echo "Database will be saved as: $CAPTURE_DIR/dmr_capture_${TIMESTAMP}.db"
echo ""
echo "Press CTRL+C to stop capture"

# Run capture with 30-minute timeout (plus buffer)
timeout 1920s ./dsd-fme -i rtl:0:145.125M:40 -fs -Z "$CAPTURE_DIR/dmr_capture_${TIMESTAMP}.db"

echo "Capture complete!"
"""
    
    script_path = os.path.expanduser("~/DMR_Captures/capture_dmr.sh")
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    print(f"Created capture script: {script_path}")
    
    return script_path

def create_keyup_scripts():
    """Create scripts for testing keyup patterns"""
    
    # Script for clear radio (ID 6969)
    clear_script = """#!/bin/bash
# Keyup script for CLEAR radio (ID 6969)

echo "Radio 6969 (CLEAR) Keyup Test"
echo "This will transmit a test pattern in clear mode"
echo ""
echo "Instructions:"
echo "1. Key up radio 6969"
echo "2. Say: 'Radio six nine six nine, clear test, one two three four'"
echo "3. Key down"
echo "4. Wait 5 seconds"
echo "5. Repeat 3 times"
"""
    
    # Script for encrypted radio (ID 1234)
    encrypted_script = """#!/bin/bash
# Keyup script for ENCRYPTED radio (ID 1234)

echo "Radio 1234 (ENCRYPTED) Keyup Test"
echo "This will transmit a test pattern in encrypted mode"
echo ""
echo "Instructions:"
echo "1. Key up radio 1234"
echo "2. Say: 'Radio one two three four, encrypted test, alpha bravo charlie delta'"
echo "3. Key down"
echo "4. Wait 5 seconds"
echo "5. Repeat 3 times"
"""
    
    clear_path = os.path.expanduser("~/DMR_Captures/keyup_clear.sh")
    encrypted_path = os.path.expanduser("~/DMR_Captures/keyup_encrypted.sh")
    
    with open(clear_path, 'w') as f:
        f.write(clear_script)
    
    with open(encrypted_path, 'w') as f:
        f.write(encrypted_script)
    
    os.chmod(clear_path, 0o755)
    os.chmod(encrypted_path, 0o755)
    
    print(f"Created keyup scripts:")
    print(f"- Clear: {clear_path}")
    print(f"- Encrypted: {encrypted_path}")
    
    return clear_path, encrypted_path

def main():
    print("DMR Capture Preparation")
    print("======================\n")
    
    # Prepare environment
    capture_dir = prepare_capture_environment()
    
    # Create scripts
    capture_script = create_capture_script()
    clear_script, encrypted_script = create_keyup_scripts()
    
    print("\n=== Capture Instructions ===")
    print("\n1. Start capture in one terminal:")
    print(f"   cd /home/ubuntu/dsd-fme_sqlite && ~/DMR_Captures/capture_dmr.sh")
    
    print("\n2. In another terminal, run keyup tests:")
    print(f"   ~/DMR_Captures/keyup_clear.sh")
    print(f"   ~/DMR_Captures/keyup_encrypted.sh")
    
    print("\n3. Let TV audio play for natural traffic")
    
    print("\n4. Capture will run for 30 minutes (32 min timeout)")
    
    print("\n=== What We'll Capture ===")
    print("- Radio IDs (6969 clear, 1234 encrypted)")
    print("- MI progression for both radios")
    print("- Clear vs encrypted comparison")
    print("- Natural TV audio traffic")
    print("- Multiple key ups/downs")
    
    print("\n=== Database Location ===")
    print(f"Captures will be saved to: {capture_dir}/dmr_capture_*.db")

if __name__ == "__main__":
    main()