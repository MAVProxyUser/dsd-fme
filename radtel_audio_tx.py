#!/usr/bin/env python3
"""
Radtel Audio Transmitter
Sends audio data to Radtel radio via USB serial interface
"""

import serial
import serial.tools.list_ports
import time
import struct
import argparse
import sys
import wave
import numpy as np
import pyaudio
from enum import Enum

class RadtelCommand(Enum):
    """Common Radtel radio commands"""
    ENTER_PROGRAM = b'PROGRAM'
    EXIT_PROGRAM = b'EXIT'
    PTT_ON = b'\x08'  # Push-to-talk on
    PTT_OFF = b'\x88'  # Push-to-talk off
    SET_FREQ = b'\x05'
    SET_CHANNEL = b'\x07'
    AUDIO_DATA = b'\x0A'

class RadtelAudioTransmitter:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600, audio_rate=8000):
        """Initialize Radtel audio transmitter"""
        self.port = port
        self.baudrate = baudrate
        self.audio_rate = audio_rate
        self.ser = None
        self.p = pyaudio.PyAudio()
        
    def connect(self):
        """Connect to radio"""
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
            print(f"Connected to {self.port}")
            return True
        except serial.SerialException as e:
            print(f"Connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from radio"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.p.terminate()
        print("Disconnected")
        
    def send_command(self, command, data=None):
        """Send command to radio"""
        if not self.ser or not self.ser.is_open:
            return False
            
        try:
            # Build command packet
            if isinstance(command, RadtelCommand):
                cmd_bytes = command.value
            else:
                cmd_bytes = command
                
            # Add data if provided
            if data is not None:
                packet = cmd_bytes + data
            else:
                packet = cmd_bytes
                
            # Add checksum (simple XOR)
            checksum = 0
            for b in packet:
                checksum ^= b
            packet += bytes([checksum])
            
            # Send packet
            self.ser.write(packet)
            self.ser.flush()
            return True
            
        except serial.SerialException as e:
            print(f"Command failed: {e}")
            return False
            
    def ptt_on(self):
        """Activate push-to-talk"""
        return self.send_command(RadtelCommand.PTT_ON)
        
    def ptt_off(self):
        """Deactivate push-to-talk"""
        return self.send_command(RadtelCommand.PTT_OFF)
        
    def send_audio_data(self, audio_bytes):
        """Send audio data to radio"""
        # Split audio into chunks
        chunk_size = 64  # Typical chunk size for serial audio
        
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i+chunk_size]
            
            # Create audio packet
            packet = RadtelCommand.AUDIO_DATA.value
            packet += bytes([len(chunk)])  # Length byte
            packet += chunk
            
            # Send packet
            self.ser.write(packet)
            self.ser.flush()
            
            # Small delay between chunks
            time.sleep(0.001)
            
    def transmit_audio_file(self, filename):
        """Transmit audio from WAV file"""
        try:
            # Open WAV file
            wf = wave.open(filename, 'rb')
            
            # Check format
            if wf.getnchannels() != 1:
                print("Error: Only mono audio supported")
                return False
                
            # Prepare audio
            sample_rate = wf.getframerate()
            print(f"Audio file: {sample_rate}Hz, {wf.getsampwidth()*8}-bit")
            
            # Activate PTT
            print("Activating PTT...")
            self.ptt_on()
            time.sleep(0.1)  # PTT delay
            
            # Send audio data
            print("Transmitting audio...")
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            
            while data:
                self.send_audio_data(data)
                data = wf.readframes(chunk_size)
                
            # Deactivate PTT
            time.sleep(0.1)
            self.ptt_off()
            print("Transmission complete")
            
            wf.close()
            return True
            
        except Exception as e:
            print(f"Error transmitting file: {e}")
            return False
            
    def transmit_live_audio(self):
        """Transmit live audio from microphone"""
        try:
            # Open microphone
            stream = self.p.open(format=pyaudio.paInt16,
                               channels=1,
                               rate=self.audio_rate,
                               input=True,
                               frames_per_buffer=256)
            
            print("Press Enter to start transmission, Ctrl+C to stop")
            input()
            
            # Activate PTT
            print("Transmitting... (Ctrl+C to stop)")
            self.ptt_on()
            time.sleep(0.1)
            
            try:
                while True:
                    # Read audio from microphone
                    audio_data = stream.read(256, exception_on_overflow=False)
                    
                    # Send to radio
                    self.send_audio_data(audio_data)
                    
            except KeyboardInterrupt:
                pass
                
            # Deactivate PTT
            self.ptt_off()
            stream.stop_stream()
            stream.close()
            print("\nTransmission stopped")
            
        except Exception as e:
            print(f"Error during live transmission: {e}")
            
    def test_ptt(self):
        """Test push-to-talk functionality"""
        print("Testing PTT...")
        
        print("PTT ON")
        self.ptt_on()
        time.sleep(2)
        
        print("PTT OFF")
        self.ptt_off()
        time.sleep(1)
        
        print("PTT test complete")
        
    def set_channel(self, channel):
        """Set radio channel"""
        if channel < 1 or channel > 999:
            print("Invalid channel number")
            return False
            
        # Convert channel to BCD format (common in radios)
        bcd_bytes = []
        temp = channel
        while temp > 0:
            digit = temp % 10
            temp //= 10
            digit2 = temp % 10
            temp //= 10
            bcd_bytes.append((digit2 << 4) | digit)
            
        # Pad to 2 bytes
        while len(bcd_bytes) < 2:
            bcd_bytes.append(0)
            
        return self.send_command(RadtelCommand.SET_CHANNEL, bytes(bcd_bytes))


def main():
    parser = argparse.ArgumentParser(description='Radtel Audio Transmitter')
    parser.add_argument('-p', '--port', default='/dev/ttyUSB0',
                      help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('-b', '--baudrate', type=int, default=9600,
                      help='Baud rate (default: 9600)')
    parser.add_argument('-c', '--channel', type=int,
                      help='Set channel before transmission')
    parser.add_argument('-f', '--file', type=str,
                      help='Audio file to transmit')
    parser.add_argument('-l', '--live', action='store_true',
                      help='Transmit live audio from microphone')
    parser.add_argument('-t', '--test-ptt', action='store_true',
                      help='Test PTT functionality')
    
    args = parser.parse_args()
    
    tx = RadtelAudioTransmitter(args.port, args.baudrate)
    
    if not tx.connect():
        print("Failed to connect to radio")
        sys.exit(1)
        
    try:
        # Set channel if specified
        if args.channel:
            print(f"Setting channel to {args.channel}")
            tx.set_channel(args.channel)
            time.sleep(0.5)
            
        # Execute requested operation
        if args.test_ptt:
            tx.test_ptt()
        elif args.file:
            tx.transmit_audio_file(args.file)
        elif args.live:
            tx.transmit_live_audio()
        else:
            print("No operation specified. Use -h for help.")
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        tx.disconnect()


if __name__ == '__main__':
    main()