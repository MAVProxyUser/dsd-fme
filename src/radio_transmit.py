#!/usr/bin/env python3
"""
Radio transmitter for sending audio on current channel
Uses pyaudio for audio capture and gr-osmosdr for transmission
"""

import numpy as np
import pyaudio
import argparse
import sys

# Check if GNU Radio is available
try:
    from gnuradio import gr, blocks, analog
    from gnuradio import audio as gr_audio
    from gnuradio import filter as gr_filter
    import osmosdr
    HAS_GNURADIO = True
except ImportError:
    HAS_GNURADIO = False
    print("GNU Radio not found. Falling back to basic implementation.")

# Alternative using rpitx for Raspberry Pi
try:
    import subprocess
    import tempfile
    HAS_RPITX = subprocess.run(['which', 'rpitx'], capture_output=True).returncode == 0
except:
    HAS_RPITX = False

class RadioTransmitter:
    def __init__(self, frequency=146.52e6, sample_rate=48000, deviation=5000):
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.deviation = deviation
        self.transmitting = False
        
    def transmit_gnuradio(self, audio_file=None):
        """Transmit using GNU Radio and gr-osmosdr"""
        if not HAS_GNURADIO:
            print("GNU Radio not available")
            return False
            
        try:
            # Create flow graph
            tb = gr.top_block()
            
            # Audio source
            if audio_file:
                src = blocks.wavfile_source(audio_file, repeat=False)
            else:
                src = gr_audio.source(self.sample_rate, "", True)
            
            # FM modulator
            fm_mod = analog.nbfm_tx(
                audio_rate=self.sample_rate,
                quad_rate=self.sample_rate * 4,
                tau=75e-6,
                max_dev=self.deviation,
                gain=1.0
            )
            
            # Resampler to match SDR sample rate
            resampler = gr_filter.rational_resampler_ccf(
                interpolation=int(2.048e6 / (self.sample_rate * 4)),
                decimation=1
            )
            
            # Output to SDR
            sink = osmosdr.sink(args="")
            sink.set_sample_rate(2.048e6)
            sink.set_center_freq(self.frequency, 0)
            sink.set_freq_corr(0, 0)
            sink.set_gain(14, 0)  # Adjust gain as needed
            sink.set_if_gain(20, 0)
            sink.set_bb_gain(20, 0)
            
            # Connect blocks
            tb.connect(src, fm_mod, resampler, sink)
            
            # Start transmission
            print(f"Transmitting on {self.frequency/1e6:.3f} MHz")
            tb.start()
            
            if audio_file:
                tb.wait()  # Wait for file to finish
            else:
                input("Press Enter to stop transmission...")
                
            tb.stop()
            tb.wait()
            return True
            
        except Exception as e:
            print(f"GNU Radio transmission failed: {e}")
            return False
    
    def transmit_rpitx(self, audio_file=None):
        """Transmit using rpitx on Raspberry Pi"""
        if not HAS_RPITX:
            print("rpitx not available")
            return False
            
        try:
            if audio_file:
                # Use existing audio file
                wav_file = audio_file
            else:
                # Record audio to temporary file
                wav_file = tempfile.mktemp(suffix='.wav')
                print("Recording audio (press Ctrl+C to stop)...")
                subprocess.run(['arecord', '-f', 'S16_LE', '-r', str(self.sample_rate), 
                              '-c', '1', wav_file])
            
            # Transmit using rpitx
            print(f"Transmitting on {self.frequency/1e6:.3f} MHz")
            subprocess.run(['sudo', 'rpitx', '-m', 'FM', '-f', str(self.frequency/1000),
                          '-i', wav_file])
            
            if not audio_file:
                os.remove(wav_file)
                
            return True
            
        except Exception as e:
            print(f"rpitx transmission failed: {e}")
            return False
    
    def transmit_basic(self, audio_file=None):
        """Basic audio playback (no actual radio transmission)"""
        print("WARNING: No radio hardware available. Playing audio locally only.")
        
        p = pyaudio.PyAudio()
        
        if audio_file:
            # Play from file
            import wave
            wf = wave.open(audio_file, 'rb')
            
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                          channels=wf.getnchannels(),
                          rate=wf.getframerate(),
                          output=True)
            
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
                
            stream.stop_stream()
            stream.close()
            wf.close()
        else:
            # Live audio passthrough
            stream_in = p.open(format=pyaudio.paInt16,
                             channels=1,
                             rate=self.sample_rate,
                             input=True,
                             frames_per_buffer=1024)
            
            stream_out = p.open(format=pyaudio.paInt16,
                              channels=1,
                              rate=self.sample_rate,
                              output=True,
                              frames_per_buffer=1024)
            
            print("Playing audio (press Ctrl+C to stop)...")
            try:
                while True:
                    data = stream_in.read(1024)
                    stream_out.write(data)
            except KeyboardInterrupt:
                pass
                
            stream_in.stop_stream()
            stream_out.stop_stream()
            stream_in.close()
            stream_out.close()
        
        p.terminate()
        return True
    
    def transmit(self, audio_file=None):
        """Main transmit method - tries available methods"""
        # Try GNU Radio first
        if HAS_GNURADIO:
            return self.transmit_gnuradio(audio_file)
        
        # Try rpitx for Raspberry Pi
        if HAS_RPITX:
            return self.transmit_rpitx(audio_file)
        
        # Fall back to basic audio
        return self.transmit_basic(audio_file)


def main():
    parser = argparse.ArgumentParser(description='Radio audio transmitter')
    parser.add_argument('-f', '--frequency', type=float, default=146.52e6,
                      help='Transmission frequency in Hz (default: 146.52 MHz)')
    parser.add_argument('-s', '--sample-rate', type=int, default=48000,
                      help='Audio sample rate (default: 48000)')
    parser.add_argument('-d', '--deviation', type=float, default=5000,
                      help='FM deviation in Hz (default: 5000)')
    parser.add_argument('-a', '--audio-file', type=str,
                      help='Audio file to transmit (if not specified, uses microphone)')
    
    args = parser.parse_args()
    
    tx = RadioTransmitter(args.frequency, args.sample_rate, args.deviation)
    
    print("Radio Transmitter")
    print(f"Frequency: {args.frequency/1e6:.3f} MHz")
    print(f"Sample Rate: {args.sample_rate} Hz")
    print(f"FM Deviation: {args.deviation} Hz")
    
    if not tx.transmit(args.audio_file):
        print("Transmission failed")
        sys.exit(1)
    
    print("Transmission complete")


if __name__ == '__main__':
    main()