<div align="center">

# 🧠 MeetMind

### Live Meeting Intelligence System

**Real-time transcription · Speaker identification · AI-powered insights · PDF reports**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Whisper](https://img.shields.io/badge/Whisper-faster--whisper-FF6B35?style=for-the-badge&logo=openai&logoColor=white)](https://github.com/SYSTRAN/faster-whisper)
[![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=for-the-badge)](https://groq.com)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

---

> **MeetMind** listens to your meetings in real-time, transcribes every word, identifies who said what, extracts action items and decisions, and generates a detailed summary — all automatically.

---

![MeetMind Demo](https://via.placeholder.com/900x500/fdf8f6/7c3aed?text=Demo+GIF+Coming+Soon)

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎙️ **Live Transcription** | Real-time speech-to-text using OpenAI Whisper (faster-whisper) |
| 👥 **Speaker Diarization** | Identifies and labels each speaker using pyannote.audio |
| 🤖 **AI Intelligence** | Extracts action items, decisions, open questions and key topics via Groq LLaMA 3.3 70B |
| 📋 **Detailed Summaries** | 5-8 sentence meeting summaries generated automatically |
| 🏷️ **Priority Detection** | Action items tagged as High / Medium / Low priority |
| 📄 **PDF Reports** | Download a beautiful formatted meeting report with one click |
| 🗄️ **Meeting History** | SQLite database stores all sessions, transcripts and summaries |
| 🔍 **Search** | Search across all past meetings by keyword |
| ✏️ **Rename Sessions** | Inline rename for any past meeting |
| ⏱️ **Live Timer** | Real-time recording duration counter |
| 📋 **Copy Summary** | One-click copy summary to clipboard |
| 🌐 **WebSocket Streaming** | Live updates pushed to browser instantly via WebSockets |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser UI                           │
│         (Pastel Dashboard · Live Transcript · Actions)      │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend                            │
│              (REST API · WebSocket · PDF)                    │
└────┬──────────────┬──────────────────┬───────────────────────┘
     │              │                  │
┌────▼────┐  ┌──────▼──────┐  ┌───────▼──────┐
│ Whisper │  │  pyannote   │  │   Groq LLM   │
│  STT    │  │ Diarization │  │ LLaMA 3.3 70B│
└────┬────┘  └──────┬──────┘  └───────┬──────┘
     │              │                  │
     └──────────────▼──────────────────┘
                    │
            ┌───────▼───────┐
            │  SQLite DB    │
            │ (meetings.db) │
            └───────────────┘
```

---

## 🛠️ Tech Stack

**Backend**
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — 4-8× faster Whisper for real-time transcription
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) — State-of-the-art speaker diarization
- [Groq](https://groq.com) — Ultra-fast LLaMA 3.3 70B inference for meeting intelligence
- [FastAPI](https://fastapi.tiangolo.com) — Async Python web framework
- [WebSockets](https://websockets.readthedocs.io) — Real-time browser updates
- [SQLite](https://sqlite.org) — Lightweight meeting history database
- [ReportLab](https://reportlab.com) — PDF report generation
- [sounddevice](https://python-sounddevice.readthedocs.io) — Cross-platform audio capture

**Frontend**
- Pure HTML/CSS/JS — No framework dependencies
- Playfair Display + DM Sans fonts
- Pastel design system with animated backgrounds

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or 3.12
- A microphone
- One of: [Groq API key](https://console.groq.com) (free) · [OpenAI API key](https://platform.openai.com) · [Anthropic API key](https://console.anthropic.com)
- [HuggingFace token](https://huggingface.co/settings/tokens) (optional, for speaker diarization)

### Installation

**1. Clone the repo**
```bash
git clone https://github.com/Al0kMishra/meetmind.git
cd meetmind
```

**2. Create virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

**3. Install PyTorch (CPU)**
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**4. Install dependencies**
```bash
pip install faster-whisper pyannote.audio
pip install sounddevice numpy scipy
pip install fastapi "uvicorn[standard]" websockets
pip install groq openai anthropic
pip install python-dotenv rich reportlab
```

**5. Configure environment**
```bash
cp .env.example .env
```

Edit `.env`:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

WHISPER_MODEL=base

# Optional — enables speaker identification
HF_TOKEN=hf_your_token_here

AUDIO_DEVICE_INDEX=
LLM_INTERVAL_SECONDS=120
```

**6. Find your microphone**
```bash
python audio/list_devices.py
```
Set `AUDIO_DEVICE_INDEX` to the correct number in `.env`.

**7. Run**
```bash
python main.py
```

**8. Open in browser**
```
http://localhost:8000/ui/index.html
```

---

## 📖 Usage

1. Open `http://localhost:8000/ui/index.html` in your browser
2. Click **▶ Start** — recording begins immediately
3. Speak naturally — transcript appears within 3 seconds
4. After ~2 minutes, AI extracts action items and generates a summary
5. Click **■ Stop** — final summary is generated
6. Click **⬇ Download Report** to get a PDF
7. View all past meetings at `http://localhost:8000/ui/history.html`

---

## 🔑 Getting API Keys

| Service | Purpose | Link | Cost |
|---|---|---|---|
| Groq | LLM inference (recommended) | [console.groq.com](https://console.groq.com) | Free |
| HuggingFace | Speaker diarization | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | Free |
| OpenAI | Alternative LLM | [platform.openai.com](https://platform.openai.com) | Paid |
| Anthropic | Alternative LLM | [console.anthropic.com](https://console.anthropic.com) | Paid |

**HuggingFace setup** — after getting your token, accept model terms at:
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0
- https://huggingface.co/pyannote/speaker-diarization-community-1

---

## 📁 Project Structure

```
meetmind/
├── main.py                     # Entry point
├── .env.example                # Environment template
│
├── audio/
│   ├── capture.py              # Mic capture with auto resampling
│   └── list_devices.py         # Find your mic device index
│
├── transcription/
│   ├── whisper_engine.py       # faster-whisper transcription
│   ├── diarization.py          # pyannote speaker diarization
│   └── merger.py               # Merge transcript + speaker labels
│
├── intelligence/
│   └── llm.py                  # LLM extraction (Groq/OpenAI/Anthropic)
│
├── backend/
│   ├── server.py               # FastAPI + WebSocket server
│   └── report.py               # PDF report generator
│
├── database/
│   └── db.py                   # SQLite operations
│
└── frontend/
    ├── index.html              # Live meeting dashboard
    └── history.html            # Meeting history page
```

---

## 🗺️ Roadmap

- [x] Live transcription
- [x] Speaker diarization
- [x] AI action item extraction
- [x] PDF report generation
- [x] Meeting history database
- [x] Search across transcripts

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built by [Alok Mishra](https://github.com/Al0kMishra) · BTech CSE · 2025**

*If this project helped you, please ⭐ star the repo!*

</div>
