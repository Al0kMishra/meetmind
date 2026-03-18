import json
import asyncio
import threading
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Meeting Intelligence API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

start_event = threading.Event()
stop_event  = threading.Event()

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


class ConnectionManager:
    def __init__(self):
        self._connections = []

    async def connect(self, ws):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws):
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, message):
        payload = json.dumps(message)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    @property
    def count(self):
        return len(self._connections)


manager = ConnectionManager()

_meeting_state = {
    "is_running": False,
    "current_meeting_id": None,
    "utterances": [],
    "intelligence": [],
    "full_transcript": "",
}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_text(json.dumps({"type": "init", "data": _meeting_state}))
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.post("/start")
async def start_recording():
    stop_event.clear()
    start_event.set()
    _meeting_state["is_running"]      = True
    _meeting_state["utterances"]      = []
    _meeting_state["intelligence"]    = []
    _meeting_state["full_transcript"] = ""
    await manager.broadcast({"type": "status", "data": {"message": "Recording started..."}})
    return {"status": "started"}


@app.post("/stop")
async def stop_recording():
    start_event.clear()
    stop_event.set()
    _meeting_state["is_running"] = False
    await manager.broadcast({"type": "status", "data": {"message": "Stopping..."}})
    return {"status": "stopped"}


@app.get("/meetings")
async def list_meetings():
    from database.db import get_all_meetings, get_stats
    return JSONResponse({"meetings": get_all_meetings(), "stats": get_stats()})


@app.get("/meetings/{meeting_id}")
async def get_meeting_detail(meeting_id: int):
    from database.db import get_meeting, get_utterances, get_intelligence
    return JSONResponse({
        "meeting":      get_meeting(meeting_id),
        "utterances":   get_utterances(meeting_id),
        "intelligence": get_intelligence(meeting_id),
    })


@app.delete("/meetings/{meeting_id}")
async def delete_meeting_endpoint(meeting_id: int):
    from database.db import delete_meeting
    delete_meeting(meeting_id)
    return {"status": "deleted"}


@app.patch("/meetings/{meeting_id}/title")
async def update_title(meeting_id: int, body: dict):
    from database.db import update_meeting_title
    update_meeting_title(meeting_id, body.get("title", "Untitled"))
    return {"status": "updated"}


@app.get("/meetings/{meeting_id}/transcript")
async def get_transcript(meeting_id: int):
    from database.db import get_full_transcript
    return JSONResponse({"transcript": get_full_transcript(meeting_id)})


@app.get("/meetings/{meeting_id}/report")
async def download_report(meeting_id: int):
    from database.db import get_meeting, get_utterances, get_intelligence
    from backend.report import generate_report
    meeting = get_meeting(meeting_id)
    if not meeting:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    pdf_bytes = generate_report(meeting, get_utterances(meeting_id), get_intelligence(meeting_id))
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in meeting.get("title", "meeting"))[:40].strip()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
    )


_loop = None

def set_event_loop(loop):
    global _loop
    _loop = loop

def push_utterance(utterance_dict):
    _meeting_state["utterances"].append(utterance_dict)
    _meeting_state["full_transcript"] += f"\n[{utterance_dict['speaker']}]: {utterance_dict['text']}"
    if _loop:
        asyncio.run_coroutine_threadsafe(manager.broadcast({"type": "utterance", "data": utterance_dict}), _loop)

def push_intelligence(intelligence_dict):
    _meeting_state["intelligence"].append(intelligence_dict)
    if _loop:
        asyncio.run_coroutine_threadsafe(manager.broadcast({"type": "intelligence", "data": intelligence_dict}), _loop)

def push_status(message):
    if _loop:
        asyncio.run_coroutine_threadsafe(manager.broadcast({"type": "status", "data": {"message": message}}), _loop)

def set_meeting_running(state):
    _meeting_state["is_running"] = state

def push_meeting_ended(meeting_id):
    _meeting_state["current_meeting_id"] = meeting_id
    if _loop:
        asyncio.run_coroutine_threadsafe(manager.broadcast({"type": "meeting_ended", "data": {"meeting_id": meeting_id}}), _loop)


@app.get("/ui")
async def ui_root():
    return RedirectResponse(url="/ui/index.html")

@app.get("/ui/index.html")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), media_type="text/html")

@app.get("/ui/history.html")
async def serve_history():
    return FileResponse(os.path.join(FRONTEND_DIR, "history.html"), media_type="text/html")


@app.get("/health")
async def health():
    return {"status": "ok", "clients": manager.count}

@app.post("/reset")
async def reset_meeting():
    _meeting_state["utterances"]      = []
    _meeting_state["intelligence"]    = []
    _meeting_state["full_transcript"] = ""
    _meeting_state["is_running"]      = False
    stop_event.set()
    start_event.clear()
    await manager.broadcast({"type": "reset", "data": {}})
    return {"status": "reset ok"}