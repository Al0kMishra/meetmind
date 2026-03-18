"""
main.py
────────
Entry point. Wires all components together.
Now saves every session to SQLite via database/db.py
"""

import os
import threading
import asyncio
import time
from datetime import datetime

import uvicorn
from rich.console import Console
from dotenv import load_dotenv

load_dotenv()
console = Console()

from audio.capture                import AudioCapture, CHUNK_DURATION_S
from transcription.whisper_engine import WhisperEngine
from transcription.diarization    import DiarizationEngine
from transcription.merger          import TranscriptMerger
from intelligence.llm              import IntelligenceEngine
from database.db                   import (
    init_db, create_meeting, end_meeting,
    save_utterance, save_intelligence,
)
from backend.server import (
    app, set_event_loop,
    push_utterance, push_intelligence, push_status, set_meeting_running, push_meeting_ended,
    start_event, stop_event,
)

USE_DIARIZATION = bool(os.getenv("HF_TOKEN", "").strip())

_server_loop = None

def run_server():
    global _server_loop
    _server_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_server_loop)
    set_event_loop(_server_loop)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000,
                            log_level="warning", loop="asyncio")
    server = uvicorn.Server(config)
    _server_loop.run_until_complete(server.serve())


def diarize_async(engine, audio, result_holder):
    try:
        result_holder[0] = engine.diarize(audio)
    except Exception as e:
        result_holder[0] = []


def run_pipeline():
    console.rule("[bold blue]Meeting Intelligence System[/bold blue]")

    # Init DB first
    init_db()

    console.print("\n[cyan]Loading Whisper model…[/cyan]")
    whisper = WhisperEngine()

    if USE_DIARIZATION:
        console.print("[cyan]Loading Diarization engine…[/cyan]")
        diarizer = DiarizationEngine()
    else:
        console.print("[yellow]⚠ HF_TOKEN not set — no speaker diarization.[/yellow]")
        diarizer = None

    time.sleep(1.5)

    console.print("\n[bold green]✓ System ready![/bold green]")
    console.print("Open [bold]frontend/index.html[/bold] in your browser.\n")
    push_status("System ready — press Start to begin recording")

    session = 0
    try:
        while True:
            console.print("[dim]Waiting for Start button in browser…[/dim]")
            start_event.wait()
            start_event.clear()
            stop_event.clear()

            session += 1
            title      = f"Meeting {datetime.now().strftime('%d %b %Y, %H:%M')}"
            meeting_id = create_meeting(title)

            console.print(f"\n[bold green]▶ Recording session {session} — DB ID #{meeting_id}[/bold green]")
            push_status("Recording… speak clearly into your mic")
            set_meeting_running(True)

            merger     = TranscriptMerger()
            llm_engine = IntelligenceEngine()
            capture    = AudioCapture()
            word_count = 0

            capture.start()

            try:
                while not stop_event.is_set():
                    audio_chunk = capture.get_chunk(timeout=1.0)
                    if audio_chunk is None:
                        continue

                    # Diarization (parallel)
                    diar_holder = [None]
                    if diarizer:
                        t = threading.Thread(
                            target=diarize_async,
                            args=(diarizer, audio_chunk, diar_holder),
                            daemon=True,
                        )
                        t.start()

                    # Whisper
                    whisper_segments = whisper.transcribe(audio_chunk)

                    if diarizer:
                        t.join(timeout=CHUNK_DURATION_S * 3)
                    diar_result = diar_holder[0] or []

                    # Merge
                    new_utterances = merger.merge(whisper_segments, diar_result)
                    merger.advance(CHUNK_DURATION_S)

                    for utt in new_utterances:
                        # Save to DB
                        save_utterance(
                            meeting_id = meeting_id,
                            speaker    = utt.speaker,
                            text       = utt.text,
                            start_s    = utt.start,
                            end_s      = utt.end,
                        )
                        word_count += len(utt.text.split())

                        # Push to browser
                        utt_dict = {
                            "speaker": utt.speaker,
                            "start":   utt.start,
                            "end":     utt.end,
                            "text":    utt.text,
                        }
                        push_utterance(utt_dict)
                        console.print(
                            f"  [dim]{_fmt(utt.start)}[/dim] "
                            f"[bold cyan]{utt.speaker}[/bold cyan]: {utt.text}"
                        )

                    # LLM extraction
                    recent = merger.get_recent_transcript(last_n_seconds=120)
                    result = llm_engine.maybe_extract(recent)
                    if result:
                        # Save to DB
                        save_intelligence(
                            meeting_id     = meeting_id,
                            action_items   = [vars(a) for a in result.action_items],
                            decisions      = result.decisions,
                            open_questions = result.open_questions,
                            summary        = result.summary,
                            is_final       = False,
                        )
                        push_intelligence(result.to_dict())

            finally:
                capture.stop()
                set_meeting_running(False)

            # Final summary
            console.print("\n[yellow]Generating final summary…[/yellow]")
            push_status("Stopped — generating final summary…")

            full = merger.get_full_transcript()
            if full.strip():
                final = llm_engine.get_final_summary(full)
                if final:
                    # Save final to DB
                    save_intelligence(
                        meeting_id     = meeting_id,
                        action_items   = [vars(a) for a in final.action_items],
                        decisions      = final.decisions,
                        open_questions = final.open_questions,
                        summary        = final.summary,
                        is_final       = True,
                    )
                    push_intelligence(final.to_dict())
                    push_status("Done! View history or press Start for a new session.")
                    console.print(f"\n[bold green]Final Summary:[/bold green]\n{final}")

            # Mark meeting as ended in DB
            end_meeting(meeting_id, word_count)
            push_meeting_ended(meeting_id)
            console.print(f"\n[bold]Meeting #{meeting_id} saved to database.[/bold]")
            console.print(f"[dim]View at: GET http://localhost:8000/meetings/{meeting_id}[/dim]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down…[/yellow]")


def _fmt(s):
    return f"{int(s//60):02d}:{int(s%60):02d}"


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    run_pipeline()