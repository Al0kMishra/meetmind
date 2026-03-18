"""
Run this first to find your microphone's device index.
Usage: python audio/list_devices.py
"""
import sounddevice as sd

def list_devices():
    print("\n Available audio input devices:\n")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            print(f"  [{i}] {device['name']}")
            print(f"       Channels: {device['max_input_channels']}  |  Sample rate: {int(device['default_samplerate'])} Hz")
    print("\n Set AUDIO_DEVICE_INDEX in your .env to the number in brackets.")
    print(" Leave blank to use the system default.\n")

if __name__ == "__main__":
    list_devices()
