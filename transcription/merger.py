"""
transcription/merger.py
────────────────────────
Merges Whisper word-level timestamps with pyannote speaker segments
to produce labelled utterances like:

    [00:01:23] SPEAKER_00: "We should ship this by Friday."
    [00:01:28] SPEAKER_01: "Agreed, let's aim for Thursday actually."

Algorithm:
  For each Whisper word (with start/end time):
    → find which speaker's segment contains the word's midpoint
    → assign that speaker to the word

  Then group consecutive words with the same speaker into utterances.

This is the standard approach — simple and robust.
The accuracy of speaker assignment depends on how cleanly
pyannote segmented the audio (usually very good with 2-3 speakers).
"""

from dataclasses import dataclass, field
from .whisper_engine import TranscriptSegment
from .diarization   import DiarizationSegment


@dataclass
class LabelledUtterance:
    """A continuous speech turn by one speaker."""
    speaker:   str
    start:     float
    end:       float
    text:      str
    chunk_idx: int = 0   # which audio chunk this came from (for ordering)

    def __str__(self):
        minutes = int(self.start // 60)
        seconds = int(self.start % 60)
        return f"[{minutes:02d}:{seconds:02d}] {self.speaker}: \"{self.text}\""


class TranscriptMerger:
    """
    Combines Whisper segments + diarization segments into
    a chronological list of LabelledUtterance objects.

    It also maintains a running full transcript as a plain string
    (used to send to the LLM for extraction every N seconds).
    """

    def __init__(self):
        self.utterances: list[LabelledUtterance] = []
        self._chunk_idx = 0
        self._time_offset = 0.0   # cumulative seconds processed

    def merge(
        self,
        whisper_segments:     list[TranscriptSegment],
        diarization_segments: list[DiarizationSegment],
    ) -> list[LabelledUtterance]:
        """
        Merge one chunk's worth of Whisper + diarization output.
        Appends results to self.utterances and returns only the
        new utterances from this chunk.

        If diarization_segments is empty (e.g. HF_TOKEN not set),
        falls back to labelling everything "SPEAKER_00".
        """
        new_utterances = []

        for wseg in whisper_segments:
            if not wseg.text:
                continue

            if wseg.words:
                # Word-level assignment — most accurate
                words_with_speakers = []
                for (word, w_start, w_end, _prob) in wseg.words:
                    abs_start = self._time_offset + w_start
                    abs_mid   = self._time_offset + (w_start + w_end) / 2
                    speaker   = self._find_speaker(abs_mid, diarization_segments)
                    words_with_speakers.append((word, abs_start, speaker))

                # Group consecutive same-speaker words into utterances
                groups = self._group_by_speaker(words_with_speakers)
                for (spk, words_list, grp_start) in groups:
                    text = " ".join(w for w, _, _ in words_list).strip()
                    if text:
                        utt = LabelledUtterance(
                            speaker   = spk,
                            start     = grp_start,
                            end       = self._time_offset + wseg.end,
                            text      = text,
                            chunk_idx = self._chunk_idx,
                        )
                        new_utterances.append(utt)
            else:
                # Segment-level assignment (no word timestamps)
                abs_mid  = self._time_offset + (wseg.start + wseg.end) / 2
                speaker  = self._find_speaker(abs_mid, diarization_segments)
                utt = LabelledUtterance(
                    speaker   = speaker,
                    start     = self._time_offset + wseg.start,
                    end       = self._time_offset + wseg.end,
                    text      = wseg.text,
                    chunk_idx = self._chunk_idx,
                )
                new_utterances.append(utt)

        self.utterances.extend(new_utterances)
        return new_utterances

    def advance(self, chunk_duration: float):
        """Call after each chunk to advance the time offset."""
        self._time_offset += chunk_duration
        self._chunk_idx   += 1

    def get_full_transcript(self) -> str:
        """Returns the complete meeting transcript as a formatted string."""
        return "\n".join(str(u) for u in self.utterances)

    def get_recent_transcript(self, last_n_seconds: float = 120.0) -> str:
        """Returns only utterances from the last N seconds (for LLM context)."""
        cutoff = self._time_offset - last_n_seconds
        recent = [u for u in self.utterances if u.end >= cutoff]
        return "\n".join(str(u) for u in recent)

    # ── Internals ───────────────────────────────────────────────

    def _find_speaker(
        self,
        abs_time: float,
        diarization_segments: list[DiarizationSegment],
    ) -> str:
        """Return speaker whose segment contains abs_time, else 'SPEAKER_00'."""
        for seg in diarization_segments:
            if seg.start <= abs_time <= seg.end:
                return seg.speaker
        return "SPEAKER_00"

    def _group_by_speaker(self, words_with_speakers):
        """
        Group [(word, start, speaker), ...] into
        [(speaker, [(word, start, speaker), ...], group_start), ...]
        merging consecutive same-speaker words.
        """
        if not words_with_speakers:
            return []

        groups = []
        cur_spk    = words_with_speakers[0][2]
        cur_group  = [words_with_speakers[0]]
        cur_start  = words_with_speakers[0][1]

        for item in words_with_speakers[1:]:
            _, _, spk = item
            if spk == cur_spk:
                cur_group.append(item)
            else:
                groups.append((cur_spk, cur_group, cur_start))
                cur_spk   = spk
                cur_group = [item]
                cur_start = item[1]

        groups.append((cur_spk, cur_group, cur_start))
        return groups
