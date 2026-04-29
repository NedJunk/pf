import logging
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from router_service.session_registry import SessionRegistry

_log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(level=_log_level, format="%(levelname)s:%(name)s:%(message)s")
logging.getLogger("router_service").setLevel(_log_level)

registry = SessionRegistry()
app = FastAPI()

CLIENT_DIR = Path(__file__).parent / "client"


@app.post("/sessions")
async def create_session(body: dict):
    session_id = registry.create(
        project_map=body.get("project_map", []),
        goals=body.get("goals", []),
    )
    session = registry.get(session_id)
    await session.connect()
    return {"session_id": session_id}


@app.websocket("/sessions/{session_id}/audio")
async def audio_ws(session_id: str, ws: WebSocket):
    session = registry.get(session_id)
    if not session:
        await ws.close(code=4004)
        return
    await ws.accept()
    try:
        await session.stream(ws)
    except WebSocketDisconnect:
        pass
    finally:
        await session.close()
        registry.remove(session_id)


@app.post("/sessions/{session_id}/whisper")
async def inject_whisper(session_id: str, body: dict):
    session = registry.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.inject_whisper(source=body["source"], message=body["message"])
    return {}


@app.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    session = registry.get(session_id)
    if session:
        await session.close()
        registry.remove(session_id)
    return {}


@app.get("/health")
async def health():
    return {"status": "ok"}


# Static files — must be mounted AFTER all API routes
if CLIENT_DIR.exists():
    app.mount("/", StaticFiles(directory=str(CLIENT_DIR), html=True), name="static")
