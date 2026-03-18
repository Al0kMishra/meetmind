"""
transcription/whisper_engine.py
────────────────────────────────
Wraps faster-whisper for streaming transcription.

Why faster-whisper over original Whisper?
  - 4-8× faster on same hardware
  - Lower memory footprint via CTranslate2 quantisation
  - Produces word-level timestamps (useful for diarization merge)

Model size guide (for Windows CPU):
  tiny   → ~1s/chunk,  accuracy ~ok    (good for testing)
  base   → ~2s/chunk,  accuracy good   ← recommended default
  small  → ~4s/chunk,  accuracy better (use if you have a GPU)
  medium → ~8s/chunk,  very accurate   (GPU strongly recommended)
"""

import os
import numpy as np
from dataclasses import dataclass
from faster_whisper import WhisperModel
from dotenv import load_dotenv

load_dotenv()

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")


@dataclass
class TranscriptSegment:
    """A single recognised speech segment with timing info."""
    start:  float   # seconds from chunk start
    end:    float
    text:   str
    words:  list    # list of (word, start, end, probability) if available


class WhisperEngine:
    """
    Loads faster-whisper once, then accepts raw audio arrays
    and returns a list of TranscriptSegment objects.

    The engine runs on CPU by default (works on all Windows machines).
    If you have an NVIDIA GPU, set device="cuda" for 10× speedup.

    Usage:
        engine = WhisperEngine()
        segments = engine.transcribe(audio_chunk_float32)
        for seg in segments:
            print(f"[{seg.start:.1f}s] {seg.text}")
    """

    def __init__(self):
        print(f"[Whisper] Loading model '{WHISPER_MODEL}' on CPU …")
        self.model = WhisperModel(
            WHISPER_MODEL,
            device          = "cpu",
            compute_type    = "int8",   # int8 quantisation → faster on CPU
        )
        print(f"[Whisper] Model ready.")

    def transcribe(self, audio: np.ndarray, language: str = None) -> list[TranscriptSegment]:
        """
        Transcribe a float32 numpy array (16 kHz mono).

        Args:
            audio    : float32 numpy array, shape (N,), values in [-1, 1]
            language : ISO code e.g. "en". None = auto-detect.

        Returns:
            List of TranscriptSegment (may be empty if silence)
        """
        if len(audio) == 0:
            return []

        # faster-whisper returns a generator — consume it fully
        raw_segments, info = self.model.transcribe(
            audio,
            language          = language,
            beam_size         = 5,
            word_timestamps   = True,    # needed for diarization merge
            vad_filter        = True,    # skip silent regions automatically
            vad_parameters    = dict(min_silence_duration_ms=500),
        )

        segments = []
        for seg in raw_segments:
            words = []
            if seg.words:
                words = [(w.word, w.start, w.end, w.probability)
                         for w in seg.words]
            segments.append(TranscriptSegment(
                start = seg.start,
                end   = seg.end,
                text  = seg.text.strip(),
                words = words,
            ))

        return segments
