# Radtel Radio Control Scripts

These scripts provide basic control and audio transmission functionality for Radtel radios connected via USB serial cable (CH341 UART).

## Hardware Setup

Your radio is connected via USB with CH341 UART converter:
- Vendor ID: 1a86
- Product ID: 7523
- Device: /dev/ttyUSB0

## Installation

```bash
# Install required packages
pip install -r requirements_radtel.txt

# Make scripts executable
chmod +x radtel_control.py
chmod +x radtel_audio_tx.py
```

## Scripts

### 1. radtel_control.py
Basic radio control and testing:

```bash
# List available serial ports
./radtel_control.py -l

# Test communication with radio
./radtel_control.py -t

# Connect with specific baud rate
./radtel_control.py -p /dev/ttyUSB0 -b 9600 -t
```

### 2. radtel_audio_tx.py
Audio transmission functionality:

```bash
# Test PTT (Push-to-Talk)
./radtel_audio_tx.py -t

# Transmit audio file
./radtel_audio_tx.py -f audio.wav

# Set channel and transmit
./radtel_audio_tx.py -c 10 -f audio.wav

# Live microphone transmission
./radtel_audio_tx.py -l

# Specify port and baudrate
./radtel_audio_tx.py -p /dev/ttyUSB0 -b 9600 -l
```

## Important Notes

1. **CH341 Driver Issues**: If you experience disconnection issues, remove `brltty`:
   ```bash
   sudo apt remove brltty
   ```

2. **Permissions**: You may need to add your user to the `dialout` group:
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and back in for changes to take effect
   ```

3. **Baud Rate**: Common baud rates for Radtel radios:
   - 9600 (most common)
   - 19200
   - 38400
   - 57600

4. **Protocol**: The actual protocol may vary by model. These scripts implement common commands, but your specific model (RD4T) may require different commands.

## Troubleshooting

1. **Connection Issues**:
   - Check cable connection
   - Verify correct port with `dmesg | grep ttyUSB`
   - Try different baud rates

2. **No Response**:
   - Radio may need to be in programming mode
   - Some models require specific software initialization
   - Check if radio supports serial control

3. **Audio Issues**:
   - Ensure audio format matches radio requirements
   - Most radios expect 8kHz mono audio
   - Check PTT delay timing

## Protocol Notes

These scripts implement common Radtel commands, but the RD4T may have specific requirements. The actual protocol might include:
- Specific handshake sequences
- Model-specific command codes
- Different packet formats

For full functionality, you may need to:
1. Use a serial port sniffer to capture the official software's commands
2. Refer to model-specific documentation
3. Experiment with different command sequences

## Integration with DSD-FME

These scripts can be integrated with your DSD-FME setup for testing DMR vulnerabilities:

```python
# Example integration
import subprocess
import time

# Decode DMR signal
# ... DSD-FME decoding ...

# Transmit test signal
subprocess.run(['./radtel_audio_tx.py', '-f', 'test_dmr.wav'])

# Continue decoding
# ... DSD-FME analysis ...
```