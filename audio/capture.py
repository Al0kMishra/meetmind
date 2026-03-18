"""
audio/capture.py
────────────────
Captures microphone audio in real-time and pushes numpy chunks
into a thread-safe queue for downstream processing.
Auto-detects correct channel count for the selected device.
"""
 
import os
import queue
import threading
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
 
load_dotenv()
 
SAMPLE_RATE      = 16000
CHUNK_DURATION_S = 3
CHUNK_SAMPLES    = SAMPLE_RATE * CHUNK_DURATION_S
DEVICE_INDEX     = os.getenv("AUDIO_DEVICE_INDEX")
DEVICE_INDEX     = int(DEVICE_INDEX) if DEVICE_INDEX else None
 
 
def get_device_channels(device_index):
    """Auto-detect how many input channels the device supports."""
    try:
        info = sd.query_devices(device_index, kind='input')
        channels = int(info['max_input_channels'])
        print(f"[AudioCapture] Device has {channels} input channel(s)")
        return max(1, channels)
    except Exception:
        return 1
 
 
class AudioCapture:
    def __init__(self):
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._buffer  = np.zeros(0, dtype=np.float32)
        self._stream  = None
        self._running = threading.Event()
        self._channels = get_device_channels(DEVICE_INDEX)
 
    def start(self):
        self._running.set()
 
        # Try with detected channel count, fall back to 1 if it fails
        for channels in [self._channels, 1, 2]:
            try:
                self._stream = sd.InputStream(
                    samplerate = SAMPLE_RATE,
                    channels   = channels,
                    dtype      = "float32",
                    device     = DEVICE_INDEX,
                    callback   = self._callback,
                    blocksize  = 1024,
                )
                self._stream.start()
                self._channels = channels
                print(f"[AudioCapture] Listening on device {DEVICE_INDEX or 'default'} "
                      f"@ {SAMPLE_RATE} Hz  (chunk = {CHUNK_DURATION_S}s, "
                      f"channels = {channels})")
                return
            except sd.PortAudioError as e:
                print(f"[AudioCapture] Failed with {channels} channel(s): {e}")
                continue
 
        raise RuntimeError(
            "Could not open microphone with any channel config.\n"
            "Run: python audio/list_devices.py\n"
            "Then update AUDIO_DEVICE_INDEX in .env"
        )
 
    def stop(self):
        self._running.clear()
        if self._stream:
            self._stream.stop()
            self._stream.close()
        print("[AudioCapture] Stopped.")
 
    def get_chunk(self, timeout: float = 10.0):
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
 
    @property
    def is_running(self):
        return self._running.is_set()
 
    def _callback(self, indata: np.ndarray, frames: int, time, status):
        if status:
            print(f"[AudioCapture] Warning: {status}")
 
        # Always convert to mono regardless of channel count
        if indata.ndim == 1:
            samples = indata.copy()
        else:
            samples = indata.mean(axis=1).copy()
 
        self._buffer = np.concatenate([self._buffer, samples])
 
        while len(self._buffer) >= CHUNK_SAMPLES:
            chunk = self._buffer[:CHUNK_SAMPLES]
            self._queue.put(chunk)
            self._buffer = self._buffer[CHUNK_SAMPLES:]