import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from orchestrator.agent_registry import load_registry
from orchestrator.health_monitor import HealthMonitor
from orchestrator.turn_handler import handle_turn

_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "agents.yaml")
_agents, _threshold, _timeout = load_registry(_REGISTRY_PATH)
_monitor = HealthMonitor(_agents)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _monitor.start()
    yield
    await _monitor.stop()


app = FastAPI(lifespan=lifespan)


@app.post("/turns", status_code=200)
async def receive_turn(body: dict):
    await handle_turn(
        turn_event=body,
        agents=_agents,
        health_monitor=_monitor,
        confidence_threshold=_threshold,
        agent_timeout=_timeout,
        router_service_url=os.environ["ROUTER_SERVICE_URL"],
    )
    return {}


@app.get("/health")
async def health():
    return {"status": "ok"}
