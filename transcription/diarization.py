"""
transcription/diarization.py
─────────────────────────────
Uses pyannote.audio to answer: "who spoke when?"

Output is a list of DiarizationSegment — each has a start time,
end time, and a speaker label like "SPEAKER_00", "SPEAKER_01", etc.

Setup required (one-time):
  1. Create a free HuggingFace account at https://huggingface.co
  2. Generate a token at https://huggingface.co/settings/tokens
  3. Accept terms at: https://hf.co/pyannote/speaker-diarization-3.1
  4. Set HF_TOKEN=hf_... in your .env file

Notes:
  - The first run downloads ~1.5GB of model weights (cached after that)
  - pyannote runs on CPU but is slow (~3-5s per 3s chunk)
  - For production: batch audio in larger segments (30s) and run in thread
"""

import os
import io
import numpy as np
import scipy.io.wavfile as wav
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN    = os.getenv("HF_TOKEN", "")
SAMPLE_RATE = 16000


@dataclass
class DiarizationSegment:
    """A time span attributed to a specific speaker."""
    start:   float
    end:     float
    speaker: str     # e.g. "SPEAKER_00"


class DiarizationEngine:
    """
    Wraps pyannote speaker-diarization-3.1 pipeline.

    Usage:
        engine = DiarizationEngine()
        segments = engine.diarize(audio_chunk_float32)
        for seg in segments:
            print(f"{seg.speaker}: {seg.start:.1f}s → {seg.end:.1f}s")

    Lazy-loads the model on first call to avoid slowing startup.
    """

    def __init__(self):
        self._pipeline = None   # loaded lazily on first diarize() call

    def _load(self):
        """Download / load the pyannote pipeline (runs once)."""
        if not HF_TOKEN:
            raise ValueError(
                "HF_TOKEN not set in .env.\n"
                "Get one at https://huggingface.co/settings/tokens\n"
                "and accept terms at https://hf.co/pyannote/speaker-diarization-3.1"
            )
        from pyannote.audio import Pipeline
        import torch

        print("[Diarization] Loading pyannote pipeline (first run downloads ~1.5 GB) …")
        self._pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token = HF_TOKEN,
        )
        # Use GPU if available, else CPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._pipeline.to(torch.device(device))
        print(f"[Diarization] Pipeline ready on {device}.")

    def diarize(self, audio: np.ndarray) -> list[DiarizationSegment]:
        """
        Run speaker diarization on a float32 numpy array (16 kHz mono).

        Returns list of DiarizationSegment ordered by start time.
        Returns empty list on silence or very short audio.
        """
        if self._pipeline is None:
            self._load()

        # pyannote expects a WAV file-like object or dict with tensor
        # Easiest cross-platform approach: write to in-memory WAV buffer
        import torch

        audio_int16 = (audio * 32767).astype(np.int16)
        buf = io.BytesIO()
        wav.write(buf, SAMPLE_RATE, audio_int16)
        buf.seek(0)

        # Run pipeline
        diarization = self._pipeline({"uri": "chunk", "audio": buf})

        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(DiarizationSegment(
                start   = turn.start,
                end     = turn.end,
                speaker = speaker,
            ))

        return sorted(segments, key=lambda s: s.start)
