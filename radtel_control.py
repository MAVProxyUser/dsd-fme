#!/usr/bin/env python3
"""
Radtel Radio Control via USB Serial
Works with CH341 USB-Serial converters commonly used with Radtel radios
"""

import serial
import serial.tools.list_ports
import time
import struct
import argparse
import sys

class RadtelControl:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        """Initialize connection to Radtel radio"""
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        
    def list_ports(self):
        """List available serial ports"""
        ports = serial.tools.list_ports.comports()
        print("Available serial ports:")
        for port in ports:
            print(f"  {port.device}: {port.description} [{port.hwid}]")
            if "CH341" in port.description or "ch341" in port.hwid:
                print(f"    ^ Likely Radtel cable")
                
    def connect(self):
        """Connect to the radio"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
                rtscts=False,
                dsrdtr=False
            )
            print(f"Connected to {self.port} at {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from radio"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Disconnected")
            
    def send_command(self, cmd_bytes):
        """Send command to radio"""
        if not self.ser or not self.ser.is_open:
            print("Not connected to radio")
            return None
            
        try:
            self.ser.write(cmd_bytes)
            self.ser.flush()
            return True
        except serial.SerialException as e:
            print(f"Error sending command: {e}")
            return None
            
    def read_response(self, timeout=1.0):
        """Read response from radio"""
        if not self.ser or not self.ser.is_open:
            print("Not connected to radio")
            return None
            
        self.ser.timeout = timeout
        try:
            response = self.ser.read(1024)  # Read up to 1024 bytes
            return response
        except serial.SerialException as e:
            print(f"Error reading response: {e}")
            return None
            
    def handshake(self):
        """Attempt basic handshake with radio"""
        # Common handshake sequences for Radtel radios
        handshake_sequences = [
            b'PROGRAM',  # Common programming mode entry
            b'\x02PROGRAM',  # With STX
            b'\x50\x52\x4F\x47\x52\x41\x4D',  # PROGRAM in hex
            b'\xAA\x06\x00\x00\x00\x00',  # Alternative sequence
        ]
        
        for seq in handshake_sequences:
            print(f"Trying handshake: {seq.hex()}")
            self.send_command(seq)
            time.sleep(0.1)
            response = self.read_response(timeout=0.5)
            if response and len(response) > 0:
                print(f"Got response: {response.hex()}")
                return True
                
        return False
        
    def read_info(self):
        """Try to read radio information"""
        # Common info request commands
        info_commands = [
            b'\x02\x00\x00\x00\x00',  # Model info
            b'\x02\x01\x00\x00\x00',  # Firmware version
            b'\x52',  # Read command
        ]
        
        info = {}
        for cmd in info_commands:
            self.send_command(cmd)
            time.sleep(0.1)
            response = self.read_response(timeout=0.5)
            if response and len(response) > 0:
                info[cmd.hex()] = response
                
        return info
        
    def enter_programming_mode(self):
        """Enter programming mode"""
        # Various sequences used by different Radtel models
        sequences = [
            b'PROGRAM',
            b'\x02PROGRAM\x17',
            b'\x02PROGRAM',
            b'\xAA\x06',  # Some models use this
        ]
        
        for seq in sequences:
            print(f"Trying programming mode: {seq.hex()}")
            self.send_command(seq)
            time.sleep(0.1)
            response = self.read_response(timeout=0.5)
            if response and len(response) > 0:
                if b'ACK' in response or response[0] == 0x06:  # ACK byte
                    print("Successfully entered programming mode")
                    return True
                    
        return False
        
    def test_communication(self):
        """Test basic communication with radio"""
        print("\nTesting communication...")
        
        # Try handshake
        if self.handshake():
            print("Handshake successful!")
        else:
            print("Handshake failed - radio may require specific initialization")
            
        # Try reading info
        info = self.read_info()
        if info:
            print("\nRadio information:")
            for cmd, response in info.items():
                print(f"  Command {cmd}: {response.hex()}")
                # Try to decode as ASCII if possible
                try:
                    ascii_str = response.decode('ascii', errors='ignore')
                    if ascii_str.isprintable():
                        print(f"    ASCII: {ascii_str}")
                except:
                    pass
                    
        # Try programming mode
        if self.enter_programming_mode():
            print("\nSuccessfully entered programming mode")
        else:
            print("\nCould not enter programming mode")


def main():
    parser = argparse.ArgumentParser(description='Radtel Radio Control')
    parser.add_argument('-p', '--port', default='/dev/ttyUSB0',
                      help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('-b', '--baudrate', type=int, default=9600,
                      help='Baud rate (default: 9600)')
    parser.add_argument('-l', '--list', action='store_true',
                      help='List available serial ports')
    parser.add_argument('-t', '--test', action='store_true',
                      help='Test communication with radio')
    
    args = parser.parse_args()
    
    control = RadtelControl(args.port, args.baudrate)
    
    if args.list:
        control.list_ports()
        return
        
    if not control.connect():
        print("Failed to connect to radio")
        sys.exit(1)
        
    try:
        if args.test:
            control.test_communication()
        else:
            # Basic test
            print("Connected to radio. Use -t flag to test communication.")
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        control.disconnect()


if __name__ == '__main__':
    main()