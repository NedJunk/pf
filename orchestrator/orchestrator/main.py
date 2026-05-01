import logging
import os
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException
from orchestrator.agent_registry import load_registry
from orchestrator.health_monitor import HealthMonitor
from orchestrator.turn_handler import handle_turn
from orchestrator.session_handler import handle_session_close

_log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(level=_log_level, format="%(levelname)s:%(name)s:%(message)s")
logging.getLogger("orchestrator").setLevel(_log_level)

_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "agents.yaml")
_ROUTER_SERVICE_URL = os.environ.get("ROUTER_SERVICE_URL", "")
_agents, _threshold, _timeout = load_registry(_REGISTRY_PATH)
_monitor = HealthMonitor(_agents)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _monitor.start()
    yield
    await _monitor.stop()


app = FastAPI(lifespan=lifespan)


@app.post("/turns", status_code=202)
async def receive_turn(body: dict, background_tasks: BackgroundTasks):
    if not _ROUTER_SERVICE_URL:
        raise HTTPException(status_code=503, detail="ROUTER_SERVICE_URL not configured")
    background_tasks.add_task(
        handle_turn,
        turn_event=body,
        agents=_agents,
        health_monitor=_monitor,
        confidence_threshold=_threshold,
        agent_timeout=_timeout,
        router_service_url=_ROUTER_SERVICE_URL,
    )
    return {}


@app.post("/sessions/{session_id}/close", status_code=200)
async def receive_session_close(session_id: str, body: dict):
    await handle_session_close(
        close_event={"session_id": session_id, "transcript": body["transcript"]},
        agents=_agents,
        health_monitor=_monitor,
        timeout=_timeout,
    )
    return {}


@app.get("/health")
async def health():
    return {"status": "ok"}
