"""
database/db.py
───────────────
SQLite database for persisting meetings, utterances, and intelligence.
 
Schema:
  meetings    → one row per recording session
  utterances  → one row per spoken segment
  intelligence → one row per LLM extraction result
 
All operations are synchronous (SQLite is fast enough for this use case).
Database file is created automatically at data/meetings.db on first run.
"""
 
import sqlite3
import json
import os
import time
from pathlib import Path
from dataclasses import dataclass
 
# Store DB in a data/ folder inside the project
DB_PATH = Path(__file__).parent.parent / "data" / "meetings.db"
 
 
def get_connection() -> sqlite3.Connection:
    """Return a connection with row_factory set for dict-like access."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # faster concurrent writes
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
 
 
def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS meetings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    DEFAULT 'Untitled Meeting',
                started_at  REAL    NOT NULL,
                ended_at    REAL,
                duration_s  REAL,
                word_count  INTEGER DEFAULT 0,
                status      TEXT    DEFAULT 'recording'
            );
 
            CREATE TABLE IF NOT EXISTS utterances (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id  INTEGER NOT NULL REFERENCES meetings(id),
                speaker     TEXT    NOT NULL,
                text        TEXT    NOT NULL,
                start_s     REAL    NOT NULL,
                end_s       REAL    NOT NULL,
                created_at  REAL    DEFAULT (unixepoch('now'))
            );
 
            CREATE TABLE IF NOT EXISTS intelligence (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id    INTEGER NOT NULL REFERENCES meetings(id),
                action_items  TEXT    DEFAULT '[]',
                decisions     TEXT    DEFAULT '[]',
                open_questions TEXT   DEFAULT '[]',
                summary       TEXT    DEFAULT '',
                is_final      INTEGER DEFAULT 0,
                created_at    REAL    DEFAULT (unixepoch('now'))
            );
 
            CREATE INDEX IF NOT EXISTS idx_utt_meeting   ON utterances(meeting_id);
            CREATE INDEX IF NOT EXISTS idx_intel_meeting ON intelligence(meeting_id);
        """)
    print(f"[DB] Database ready at {DB_PATH}")
 
 
# ── Meeting CRUD ─────────────────────────────────────────────────
 
def create_meeting(title: str = "Untitled Meeting") -> int:
    """Insert a new meeting row and return its ID."""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO meetings (title, started_at, status) VALUES (?, ?, 'recording')",
            (title, time.time())
        )
        meeting_id = cur.lastrowid
    print(f"[DB] Created meeting #{meeting_id}: '{title}'")
    return meeting_id
 
 
def end_meeting(meeting_id: int, word_count: int = 0):
    """Mark a meeting as completed and record duration."""
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """UPDATE meetings
               SET ended_at=?, status='completed',
                   duration_s = ? - started_at,
                   word_count = ?
               WHERE id=?""",
            (now, now, word_count, meeting_id)
        )
    print(f"[DB] Ended meeting #{meeting_id}")
 
 
def update_meeting_title(meeting_id: int, title: str):
    with get_connection() as conn:
        conn.execute("UPDATE meetings SET title=? WHERE id=?", (title, meeting_id))
 
 
def get_all_meetings() -> list[dict]:
    """Return all meetings ordered by newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM meetings ORDER BY started_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]
 
 
def get_meeting(meeting_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM meetings WHERE id=?", (meeting_id,)
        ).fetchone()
    return dict(row) if row else None
 
 
def delete_meeting(meeting_id: int):
    """Delete meeting and all related data."""
    with get_connection() as conn:
        conn.execute("DELETE FROM utterances  WHERE meeting_id=?", (meeting_id,))
        conn.execute("DELETE FROM intelligence WHERE meeting_id=?", (meeting_id,))
        conn.execute("DELETE FROM meetings    WHERE id=?",          (meeting_id,))
    print(f"[DB] Deleted meeting #{meeting_id}")
 
 
# ── Utterance CRUD ───────────────────────────────────────────────
 
def save_utterance(meeting_id: int, speaker: str, text: str,
                   start_s: float, end_s: float):
    """Save a single utterance to the database."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO utterances (meeting_id, speaker, text, start_s, end_s) "
            "VALUES (?, ?, ?, ?, ?)",
            (meeting_id, speaker, text, start_s, end_s)
        )
 
 
def get_utterances(meeting_id: int) -> list[dict]:
    """Return all utterances for a meeting ordered by time."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM utterances WHERE meeting_id=? ORDER BY start_s",
            (meeting_id,)
        ).fetchall()
    return [dict(r) for r in rows]
 
 
def get_full_transcript(meeting_id: int) -> str:
    """Return transcript as a formatted string."""
    utterances = get_utterances(meeting_id)
    lines = []
    for u in utterances:
        mins = int(u["start_s"] // 60)
        secs = int(u["start_s"] % 60)
        lines.append(f"[{mins:02d}:{secs:02d}] {u['speaker']}: {u['text']}")
    return "\n".join(lines)
 
 
# ── Intelligence CRUD ────────────────────────────────────────────
 
def save_intelligence(meeting_id: int, action_items: list,
                      decisions: list, open_questions: list,
                      summary: str, is_final: bool = False):
    """Save an LLM extraction result."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO intelligence
               (meeting_id, action_items, decisions, open_questions, summary, is_final)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                meeting_id,
                json.dumps(action_items),
                json.dumps(decisions),
                json.dumps(open_questions),
                summary,
                1 if is_final else 0,
            )
        )
 
 
def get_intelligence(meeting_id: int) -> list[dict]:
    """Return all intelligence records for a meeting."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM intelligence WHERE meeting_id=? ORDER BY created_at",
            (meeting_id,)
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["action_items"]   = json.loads(d["action_items"])
        d["decisions"]      = json.loads(d["decisions"])
        d["open_questions"] = json.loads(d["open_questions"])
        results.append(d)
    return results
 
 
def get_final_intelligence(meeting_id: int) -> dict | None:
    """Return the final summary for a meeting."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM intelligence WHERE meeting_id=? AND is_final=1",
            (meeting_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["action_items"]   = json.loads(d["action_items"])
    d["decisions"]      = json.loads(d["decisions"])
    d["open_questions"] = json.loads(d["open_questions"])
    return d
 
 
# ── Stats ────────────────────────────────────────────────────────
 
def get_stats() -> dict:
    """Return overall stats for the history page."""
    with get_connection() as conn:
        total_meetings  = conn.execute("SELECT COUNT(*) FROM meetings WHERE status='completed'").fetchone()[0]
        total_words     = conn.execute("SELECT SUM(word_count) FROM meetings").fetchone()[0] or 0
        total_actions   = conn.execute("SELECT COUNT(*) FROM intelligence WHERE is_final=1").fetchone()[0]
    return {
        "total_meetings": total_meetings,
        "total_words":    total_words,
        "total_actions":  total_actions,
    }
 