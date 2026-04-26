# MVP Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full MVP vertical slice — browser-based Gemini Live voice interface, Router Service, Orchestrator, and Dev Coach expert agent — all wired together with docker-compose and GitHub Actions CI.

**Architecture:** Four services in the `gcsb/` monorepo. `voice-router` (existing) is a Python package depended on by `router-service`. `expert-agents/base` is a Python ABC package depended on by `dev-coach`. `orchestrator` has no local package deps. All services communicate over HTTP/WebSocket. All Gemini calls are mocked in unit tests — `GEMINI_API_KEY` is not set in CI unit-test jobs.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, google-genai SDK, httpx, pyyaml, pytest, pytest-asyncio, Docker, GitHub Actions. Browser client: plain HTML/JS, AudioWorklet, WebSocket.

**Spec:** `docs/superpowers/specs/2026-04-25-mvp-vertical-slice-design.md`

---

## File Structure

All paths relative to repo root (`gcsb/`).

### voice-router (modifications only)

```
voice-router/src/router/
  behavioral_contract.py        CREATE  — BEHAVIORAL_CONTRACT string constant
  facilitator.py                MODIFY  — import BEHAVIORAL_CONTRACT from there
voice-router/
  Dockerfile                    CREATE  — runs pytest; not a server
voice-router/tests/router/
  test_behavioral_contract.py   CREATE
```

### expert-agents/base (new package)

```
expert-agents/base/
  expert_agent_base/
    __init__.py                 CREATE
    base.py                     CREATE  — WhisperContext, WhisperResponse, ExpertAgentBase ABC
  tests/
    __init__.py                 CREATE
    test_base.py                CREATE
  pyproject.toml                CREATE
```

### expert-agents/dev-coach (new service)

```
expert-agents/dev-coach/
  dev_coach/
    __init__.py                 CREATE
    main.py                     CREATE  — DevCoach extends ExpertAgentBase
  tests/
    __init__.py                 CREATE
    test_whisper.py             CREATE
  Dockerfile                    CREATE
  pyproject.toml                CREATE
```

### orchestrator (new service)

```
orchestrator/
  orchestrator/
    __init__.py                 CREATE
    agent_registry.py           CREATE  — load_registry(), AgentConfig
    health_monitor.py           CREATE  — HealthMonitor
    turn_handler.py             CREATE  — handle_turn()
    main.py                     CREATE  — FastAPI app
    agents.yaml                 CREATE  — registry config
  tests/
    __init__.py                 CREATE
    test_agent_registry.py      CREATE
    test_health_monitor.py      CREATE
    test_turn_handler.py        CREATE
  Dockerfile                    CREATE
  pyproject.toml                CREATE
```

### router-service (new service)

```
router-service/
  router_service/
    __init__.py                 CREATE
    session_registry.py         CREATE  — SessionRegistry
    live_session.py             CREATE  — LiveSession
    main.py                     CREATE  — FastAPI app
    client/
      index.html                CREATE
      audio.js                  CREATE
      session.js                CREATE
  tests/
    __init__.py                 CREATE
    test_session_registry.py    CREATE
    test_live_session.py        CREATE
    test_endpoints.py           CREATE
  Dockerfile                    CREATE
  pyproject.toml                CREATE
```

### Integration

```
docker-compose.yml              CREATE
.env.example                    CREATE
.github/workflows/ci.yml        CREATE
transcripts/                    CREATE (empty dir, git-ignored)
```

---

## Task 1: Extract BEHAVIORAL_CONTRACT + voice-router Dockerfile

**Files:**
- Create: `voice-router/src/router/behavioral_contract.py`
- Modify: `voice-router/src/router/facilitator.py`
- Create: `voice-router/tests/router/test_behavioral_contract.py`
- Create: `voice-router/Dockerfile`

All commands run from `voice-router/` with the venv active (`source venv/bin/activate`).

- [ ] **Step 1: Write the failing tests**

Create `voice-router/tests/router/test_behavioral_contract.py`:

```python
from src.router.behavioral_contract import BEHAVIORAL_CONTRACT


def test_behavioral_contract_is_a_non_empty_string():
    assert isinstance(BEHAVIORAL_CONTRACT, str)
    assert len(BEHAVIORAL_CONTRACT) > 100


def test_behavioral_contract_includes_core_role():
    assert "facilitation router" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_includes_whisper_clause():
    assert "WHISPER from" in BEHAVIORAL_CONTRACT


def test_facilitator_prompt_embeds_behavioral_contract():
    from src.router.facilitator import _SYSTEM_PROMPT
    assert "facilitation router" in _SYSTEM_PROMPT
    assert "WHISPER from" in _SYSTEM_PROMPT
    assert "{goals}" in _SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/router/test_behavioral_contract.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.router.behavioral_contract'`

- [ ] **Step 3: Create `behavioral_contract.py`**

```python
# voice-router/src/router/behavioral_contract.py
BEHAVIORAL_CONTRACT = """\
You are a thin, voice-first facilitation router. Your ONLY job is to help \
the user capture and clarify their thoughts.

Rules:
- Always ask one clarifying question to deepen understanding or prompt specifics
- Suggest how input might be categorized or connected to existing work
- If expert whispers are listed below, voice the most relevant one naturally \
(e.g. "The Project Manager is noting that...")
- NEVER perform deep analysis, generate code, or offer solutions
- Keep responses short — this is a voice interaction

# --- whisper handling ---
You will occasionally receive messages prefixed with "[WHISPER from <name>]:". \
Treat these as private suggestions from domain experts. \
Weave the insight naturally into your next response — \
do not quote it directly or attribute it by name.\
"""
```

- [ ] **Step 4: Update `facilitator.py` to import from `behavioral_contract`**

Replace lines 1–22 of `voice-router/src/router/facilitator.py`:

```python
from google import genai
from .state_store import RouterState
from .behavioral_contract import BEHAVIORAL_CONTRACT

_SYSTEM_PROMPT = BEHAVIORAL_CONTRACT + """

Active goals: {goals}
Project map: {project_map}
Recent conversation:
{history}

Pending expert whispers:
{whispers}
"""


class Facilitator:
    _MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def respond(self, user_input: str, state: RouterState) -> str:
        whisper_text = (
            "\n".join(f"- [{w.source}]: {w.message}" for w in state.whispers)
            or "None"
        )
        history_text = "\n".join(state.history[-6:]) or "None"

        prompt = _SYSTEM_PROMPT.format(
            goals=state.goals or "None",
            project_map=state.project_map or "None",
            history=history_text,
            whispers=whisper_text,
        )
        full_input = f"{prompt}\n\nUser: {user_input}"

        response = self._client.models.generate_content(
            model=self._MODEL,
            contents=[{"role": "user", "parts": [{"text": full_input}]}],
        )
        return response.text
```

- [ ] **Step 5: Run all voice-router tests**

```bash
pytest -v
```

Expected: all tests pass (behavioral_contract tests + all existing tests).

- [ ] **Step 6: Create `voice-router/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY voice-router/ voice-router/
RUN pip install -e "voice-router/[dev]"
CMD ["pytest", "voice-router/tests/", "-v"]
```

- [ ] **Step 7: Verify Docker build**

Run from repo root (`gcsb/`):

```bash
docker build -f voice-router/Dockerfile -t voice-router-test .
```

Expected: build succeeds.

- [ ] **Step 8: Commit**

```bash
git add voice-router/src/router/behavioral_contract.py \
        voice-router/src/router/facilitator.py \
        voice-router/tests/router/test_behavioral_contract.py \
        voice-router/Dockerfile
git commit -m "feat: extract BEHAVIORAL_CONTRACT with whisper clause; add voice-router Dockerfile"
```

---

## Task 2: expert-agents/base — ABC Package

**Files:**
- Create: `expert-agents/base/pyproject.toml`
- Create: `expert-agents/base/expert_agent_base/__init__.py`
- Create: `expert-agents/base/expert_agent_base/base.py`
- Create: `expert-agents/base/tests/__init__.py`
- Create: `expert-agents/base/tests/test_base.py`

All commands run from `expert-agents/base/`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "expert-agent-base"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["."]
```

- [ ] **Step 2: Create package init files and write failing tests**

```bash
mkdir -p expert_agent_base tests
touch expert_agent_base/__init__.py tests/__init__.py
```

Create `expert-agents/base/tests/test_base.py`:

```python
import pytest
from fastapi.testclient import TestClient
from expert_agent_base.base import ExpertAgentBase, WhisperContext, WhisperResponse


class ConcreteAgent(ExpertAgentBase):
    async def whisper(self, context: WhisperContext) -> WhisperResponse:
        return WhisperResponse(source="Test", message="hello", confidence=0.9)


class SilentAgent(ExpertAgentBase):
    async def whisper(self, context: WhisperContext) -> None:
        return None


def _context():
    return {
        "session_id": "s1",
        "context": {"history": ["User: hi"], "goals": [], "project_map": []},
    }


def test_cannot_instantiate_base_directly():
    with pytest.raises(TypeError):
        ExpertAgentBase(model="any")


def test_health_endpoint_returns_ok():
    client = TestClient(ConcreteAgent(model="m").app)
    assert client.get("/health").json() == {"status": "ok"}


def test_whisper_endpoint_returns_200_with_payload():
    client = TestClient(ConcreteAgent(model="m").app)
    resp = client.post("/whisper", json=_context())
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "Test"
    assert data["message"] == "hello"
    assert data["confidence"] == 0.9


def test_whisper_endpoint_returns_204_when_none():
    client = TestClient(SilentAgent(model="m").app)
    resp = client.post("/whisper", json=_context())
    assert resp.status_code == 204


def test_whisper_endpoint_returns_503_on_exception():
    class BrokenAgent(ExpertAgentBase):
        async def whisper(self, context):
            raise RuntimeError("LLM unavailable")

    client = TestClient(BrokenAgent(model="m").app)
    resp = client.post("/whisper", json=_context())
    assert resp.status_code == 503
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pip install -e ".[dev]"
pytest -v
```

Expected: `ModuleNotFoundError: No module named 'expert_agent_base'`

- [ ] **Step 4: Implement `expert_agent_base/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response


@dataclass
class WhisperContext:
    session_id: str
    history: list[str]
    goals: list[str]
    project_map: list[str]


@dataclass
class WhisperResponse:
    source: str
    message: str
    confidence: float


class ExpertAgentBase(ABC):
    def __init__(self, model: str) -> None:
        self.model = model
        self._app = self._build_app()

    @property
    def app(self) -> FastAPI:
        return self._app

    @abstractmethod
    async def whisper(self, context: WhisperContext) -> Optional[WhisperResponse]:
        ...

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.post("/whisper")
        async def whisper_endpoint(body: dict):
            context = WhisperContext(
                session_id=body["session_id"],
                history=body["context"]["history"],
                goals=body["context"]["goals"],
                project_map=body["context"]["project_map"],
            )
            try:
                result = await self.whisper(context)
            except Exception as exc:
                return JSONResponse({"error": str(exc)}, status_code=503)
            if result is None:
                return Response(status_code=204)
            return JSONResponse({
                "source": result.source,
                "message": result.message,
                "confidence": result.confidence,
            })

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app
```

- [ ] **Step 5: Run tests**

```bash
pytest -v
```

Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
cd ../..  # back to gcsb/
git add expert-agents/base/
git commit -m "feat: add expert-agent-base ABC package with WhisperContext, WhisperResponse, ExpertAgentBase"
```

---

## Task 3: Dev Coach Agent

**Files:**
- Create: `expert-agents/dev-coach/pyproject.toml`
- Create: `expert-agents/dev-coach/dev_coach/__init__.py`
- Create: `expert-agents/dev-coach/dev_coach/main.py`
- Create: `expert-agents/dev-coach/tests/__init__.py`
- Create: `expert-agents/dev-coach/tests/test_whisper.py`
- Create: `expert-agents/dev-coach/Dockerfile`

All commands run from `expert-agents/dev-coach/`.

- [ ] **Step 1: Create `pyproject.toml` and scaffold**

```toml
[project]
name = "dev-coach"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "google-genai>=1.0.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["."]
```

```bash
mkdir -p dev_coach tests
touch dev_coach/__init__.py tests/__init__.py
```

Install dependencies (from `expert-agents/dev-coach/`):

```bash
pip install -e "../base" -e ".[dev]"
```

- [ ] **Step 2: Write failing tests**

Create `expert-agents/dev-coach/tests/test_whisper.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from expert_agent_base.base import WhisperContext


def _context(history=None):
    return WhisperContext(
        session_id="s1",
        history=history or ["User: Hello", "Assistant: Hi there"],
        goals=["ship MVP"],
        project_map=["voice-router"],
    )


def _http_context(history=None):
    return {
        "session_id": "s1",
        "context": {
            "history": history or ["User: Hello", "Assistant: Hi there"],
            "goals": ["ship MVP"],
            "project_map": ["voice-router"],
        },
    }


@patch("dev_coach.main.genai")
def test_whisper_returns_none_for_empty_history(mock_genai):
    mock_genai.Client.return_value = MagicMock()
    from dev_coach.main import DevCoach
    coach = DevCoach()
    import asyncio
    result = asyncio.run(coach.whisper(_context(history=[])))
    assert result is None
    mock_genai.Client.return_value.aio.models.generate_content.assert_not_called()


@patch("dev_coach.main.genai")
def test_whisper_returns_none_for_single_history_entry(mock_genai):
    mock_genai.Client.return_value = MagicMock()
    from dev_coach.main import DevCoach
    coach = DevCoach()
    import asyncio
    result = asyncio.run(coach.whisper(_context(history=["User: hello"])))
    assert result is None


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_whisper_returns_response_on_suggestion(mock_genai):
    mock_resp = MagicMock()
    mock_resp.text = "Consider writing the test first."
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    coach = DevCoach()
    result = await coach.whisper(_context())

    assert result is not None
    assert result.source == "DevCoach"
    assert result.message == "Consider writing the test first."
    assert result.confidence == 0.8


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_whisper_returns_none_for_no_whisper_response(mock_genai):
    mock_resp = MagicMock()
    mock_resp.text = "NO_WHISPER"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    coach = DevCoach()
    assert await coach.whisper(_context()) is None


@patch("dev_coach.main.genai")
def test_endpoint_returns_503_on_gemini_error(mock_genai):
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=Exception("API error")
    )
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    client = TestClient(DevCoach().app)
    resp = client.post("/whisper", json=_http_context())
    assert resp.status_code == 503


@patch("dev_coach.main.genai")
def test_health_returns_ok(mock_genai):
    mock_genai.Client.return_value = MagicMock()
    from dev_coach.main import DevCoach
    client = TestClient(DevCoach().app)
    assert client.get("/health").json() == {"status": "ok"}
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest -v
```

Expected: `ModuleNotFoundError: No module named 'dev_coach'`

- [ ] **Step 4: Implement `dev_coach/main.py`**

```python
import os
from google import genai
from expert_agent_base.base import ExpertAgentBase, WhisperContext, WhisperResponse

_PROMPT = """\
You are a development process coach embedded in a voice-first development session.
Your job is to surface ONE brief, specific, actionable suggestion when you see
a genuine opportunity. Focus on process — never generate code.

Rules:
- Two sentences maximum
- Reference what was just said — no generic advice
- If you have nothing genuinely useful to add, respond with exactly: NO_WHISPER

Session goals: {goals}
Project context: {project_map}

Recent conversation:
{history_tail}

Your suggestion (or NO_WHISPER):"""


class DevCoach(ExpertAgentBase):
    def __init__(self) -> None:
        model = os.environ.get("DEV_COACH_MODEL", "gemini-2.0-flash")
        super().__init__(model=model)
        self._client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

    async def whisper(self, context: WhisperContext) -> WhisperResponse | None:
        if len(context.history) < 2:
            return None

        prompt = _PROMPT.format(
            goals="; ".join(context.goals) or "None",
            project_map="; ".join(context.project_map) or "None",
            history_tail="\n".join(context.history),
        )

        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )

        text = (response.text or "").strip()
        if text.startswith("NO_WHISPER"):
            return None

        return WhisperResponse(source="DevCoach", message=text, confidence=0.8)


_coach = DevCoach()
app = _coach.app
```

- [ ] **Step 5: Run tests**

```bash
pytest -v
```

Expected: all 6 tests pass.

- [ ] **Step 6: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY expert-agents/base/ expert-agents/base/
COPY expert-agents/dev-coach/ expert-agents/dev-coach/
RUN pip install -e "expert-agents/base/" -e "expert-agents/dev-coach/[dev]"
HEALTHCHECK --interval=30s --timeout=5s CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8082/health')"
CMD ["uvicorn", "dev_coach.main:app", "--host", "0.0.0.0", "--port", "8082"]
```

- [ ] **Step 7: Verify Docker build (from repo root)**

```bash
docker build -f expert-agents/dev-coach/Dockerfile -t dev-coach .
```

Expected: build succeeds.

- [ ] **Step 8: Commit**

```bash
cd ../..  # gcsb/
git add expert-agents/dev-coach/
git commit -m "feat: add dev-coach expert agent with Gemini Flash LLM call and early-return guard"
```

---

## Task 4: Orchestrator — Agent Registry

**Files:**
- Create: `orchestrator/pyproject.toml`
- Create: `orchestrator/orchestrator/__init__.py`
- Create: `orchestrator/orchestrator/agent_registry.py`
- Create: `orchestrator/orchestrator/agents.yaml`
- Create: `orchestrator/tests/__init__.py`
- Create: `orchestrator/tests/test_agent_registry.py`

All commands run from `orchestrator/`.

- [ ] **Step 1: Create `pyproject.toml` and scaffold**

```toml
[project]
name = "orchestrator"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
    "httpx>=0.27.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["."]
```

```bash
mkdir -p orchestrator tests
touch orchestrator/__init__.py tests/__init__.py
pip install -e ".[dev]"
```

Create `orchestrator/orchestrator/agents.yaml`:

```yaml
confidence_threshold: 0.5
agent_timeout_seconds: 2
agents:
  - name: "DevCoach"
    url: "http://dev-coach:8082"
```

- [ ] **Step 2: Write failing tests**

Create `orchestrator/tests/test_agent_registry.py`:

```python
from orchestrator.agent_registry import load_registry


def test_load_registry_parses_agents(tmp_path):
    cfg = tmp_path / "agents.yaml"
    cfg.write_text(
        "confidence_threshold: 0.7\nagent_timeout_seconds: 3\n"
        "agents:\n  - name: Agent1\n    url: http://a1:9000\n"
    )
    agents, threshold, timeout = load_registry(str(cfg))
    assert len(agents) == 1
    assert agents[0].name == "Agent1"
    assert agents[0].url == "http://a1:9000"
    assert threshold == 0.7
    assert timeout == 3


def test_load_registry_empty_agents(tmp_path):
    cfg = tmp_path / "agents.yaml"
    cfg.write_text("confidence_threshold: 0.5\nagent_timeout_seconds: 2\nagents: []\n")
    agents, _, _ = load_registry(str(cfg))
    assert agents == []


def test_load_registry_defaults(tmp_path):
    cfg = tmp_path / "agents.yaml"
    cfg.write_text("agents: []\n")
    _, threshold, timeout = load_registry(str(cfg))
    assert threshold == 0.5
    assert timeout == 2
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest -v
```

Expected: `ModuleNotFoundError: No module named 'orchestrator.agent_registry'`

- [ ] **Step 4: Implement `orchestrator/agent_registry.py`**

```python
from dataclasses import dataclass
import yaml


@dataclass
class AgentConfig:
    name: str
    url: str


def load_registry(config_path: str) -> tuple[list[AgentConfig], float, int]:
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    agents = [
        AgentConfig(name=a["name"], url=a["url"])
        for a in data.get("agents", [])
    ]
    threshold = float(data.get("confidence_threshold", 0.5))
    timeout = int(data.get("agent_timeout_seconds", 2))
    return agents, threshold, timeout
```

- [ ] **Step 5: Run tests**

```bash
pytest -v
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
cd ..  # gcsb/
git add orchestrator/
git commit -m "feat: add orchestrator package scaffold with agent registry and agents.yaml"
```

---

## Task 5: Orchestrator — Health Monitor

**Files:**
- Create: `orchestrator/orchestrator/health_monitor.py`
- Create: `orchestrator/tests/test_health_monitor.py`

All commands run from `orchestrator/`.

- [ ] **Step 1: Write failing tests**

Create `orchestrator/tests/test_health_monitor.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from orchestrator.agent_registry import AgentConfig
from orchestrator.health_monitor import HealthMonitor


def _agents():
    return [AgentConfig(name="Agent1", url="http://agent1:8082")]


def _mock_http_client(status_code=200, raises=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_client = AsyncMock()
    if raises:
        mock_client.get = AsyncMock(side_effect=raises)
    else:
        mock_client.get = AsyncMock(return_value=mock_resp)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_all_agents_start_healthy():
    monitor = HealthMonitor(_agents())
    assert monitor.is_healthy("Agent1")


@pytest.mark.asyncio
async def test_agent_marked_unhealthy_on_connection_error():
    monitor = HealthMonitor(_agents())
    with patch("orchestrator.health_monitor.httpx.AsyncClient",
               return_value=_mock_http_client(raises=Exception("refused"))):
        await monitor._poll_all()
    assert not monitor.is_healthy("Agent1")


@pytest.mark.asyncio
async def test_agent_marked_unhealthy_on_non_200():
    monitor = HealthMonitor(_agents())
    with patch("orchestrator.health_monitor.httpx.AsyncClient",
               return_value=_mock_http_client(status_code=503)):
        await monitor._poll_all()
    assert not monitor.is_healthy("Agent1")


@pytest.mark.asyncio
async def test_agent_recovers_after_successful_poll():
    monitor = HealthMonitor(_agents())
    monitor._healthy.discard("Agent1")
    with patch("orchestrator.health_monitor.httpx.AsyncClient",
               return_value=_mock_http_client(status_code=200)):
        await monitor._poll_all()
    assert monitor.is_healthy("Agent1")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_health_monitor.py -v
```

Expected: `ModuleNotFoundError: No module named 'orchestrator.health_monitor'`

- [ ] **Step 3: Implement `orchestrator/health_monitor.py`**

```python
import asyncio
import logging
import httpx
from orchestrator.agent_registry import AgentConfig

logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 30


class HealthMonitor:
    def __init__(self, agents: list[AgentConfig]) -> None:
        self._agents = agents
        self._healthy: set[str] = {a.name for a in agents}
        self._task: asyncio.Task | None = None

    def is_healthy(self, name: str) -> bool:
        return name in self._healthy

    def start(self) -> None:
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            await self._poll_all()

    async def _poll_all(self) -> None:
        async with httpx.AsyncClient() as client:
            for agent in self._agents:
                try:
                    resp = await client.get(f"{agent.url}/health", timeout=5.0)
                    if resp.status_code == 200:
                        self._healthy.add(agent.name)
                    else:
                        self._healthy.discard(agent.name)
                        logger.warning("Agent %s unhealthy: %s", agent.name, resp.status_code)
                except Exception as exc:
                    self._healthy.discard(agent.name)
                    logger.warning("Agent %s unreachable: %s", agent.name, exc)
```

- [ ] **Step 4: Run all orchestrator tests**

```bash
pytest -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
cd ..
git add orchestrator/orchestrator/health_monitor.py orchestrator/tests/test_health_monitor.py
git commit -m "feat: add orchestrator health monitor with 30s polling and auto-recovery"
```

---

## Task 6: Orchestrator — Turn Handler, FastAPI App, Dockerfile

**Files:**
- Create: `orchestrator/orchestrator/turn_handler.py`
- Create: `orchestrator/orchestrator/main.py`
- Create: `orchestrator/tests/test_turn_handler.py`
- Create: `orchestrator/Dockerfile`

All commands run from `orchestrator/`.

- [ ] **Step 1: Write failing tests**

Create `orchestrator/tests/test_turn_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from orchestrator.agent_registry import AgentConfig
from orchestrator.turn_handler import handle_turn


def _event():
    return {
        "session_id": "s1",
        "history_tail": ["User: hello", "Assistant: hi"],
        "goals": ["goal1"],
        "project_map": ["mod1"],
    }


def _monitor(healthy=True):
    m = MagicMock()
    m.is_healthy.return_value = healthy
    return m


def _agent():
    return AgentConfig(name="DevCoach", url="http://dev-coach:8082")


def _http_client(agent_status=200, agent_json=None, router_status=200):
    mock_client = AsyncMock()
    call_count = [0]

    async def mock_post(url, **kwargs):
        call_count[0] += 1
        resp = MagicMock()
        if "dev-coach" in url:
            resp.status_code = agent_status
            resp.json.return_value = agent_json or {
                "source": "DevCoach", "message": "try TDD", "confidence": 0.8
            }
        else:
            resp.status_code = router_status
        return resp

    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, call_count


@pytest.mark.asyncio
async def test_no_call_when_all_agents_unhealthy():
    cm, call_count = _http_client()
    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(healthy=False), 0.5, 2, "http://r:8080")
    assert call_count[0] == 0


@pytest.mark.asyncio
async def test_forwards_passing_whisper_to_router():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"source": "DevCoach", "message": "try TDD", "confidence": 0.8}
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 2, "http://router:8080")

    assert any("dev-coach" in u for u in posted)
    assert any("router" in u and "whisper" in u for u in posted)


@pytest.mark.asyncio
async def test_drops_whisper_below_confidence_threshold():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"source": "DevCoach", "message": "maybe", "confidence": 0.3}
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 2, "http://router:8080")

    assert not any("router" in u for u in posted)


@pytest.mark.asyncio
async def test_skips_204_from_agent():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 204
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 2, "http://router:8080")

    assert not any("router" in u for u in posted)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_turn_handler.py -v
```

Expected: `ModuleNotFoundError: No module named 'orchestrator.turn_handler'`

- [ ] **Step 3: Implement `orchestrator/turn_handler.py`**

```python
import asyncio
import logging
import httpx
from orchestrator.agent_registry import AgentConfig
from orchestrator.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)


async def handle_turn(
    turn_event: dict,
    agents: list[AgentConfig],
    health_monitor: HealthMonitor,
    confidence_threshold: float,
    agent_timeout: int,
    router_service_url: str,
) -> None:
    healthy = [a for a in agents if health_monitor.is_healthy(a.name)]
    if not healthy:
        logger.warning("No healthy agents for turn event session=%s", turn_event["session_id"])
        return

    results = await asyncio.gather(
        *[_call_agent(a, turn_event, agent_timeout) for a in healthy],
        return_exceptions=True,
    )

    session_id = turn_event["session_id"]
    async with httpx.AsyncClient() as client:
        for result in results:
            if isinstance(result, Exception) or result is None:
                continue
            if result["confidence"] < confidence_threshold:
                continue
            try:
                await client.post(
                    f"{router_service_url}/sessions/{session_id}/whisper",
                    json={"source": result["source"], "message": result["message"]},
                    timeout=2.0,
                )
            except Exception as exc:
                logger.warning("Failed to post whisper to router: %s", exc)


async def _call_agent(agent: AgentConfig, turn_event: dict, timeout: int) -> dict | None:
    payload = {
        "session_id": turn_event["session_id"],
        "context": {
            "history": turn_event["history_tail"],
            "goals": turn_event["goals"],
            "project_map": turn_event["project_map"],
        },
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{agent.url}/whisper", json=payload, timeout=float(timeout))
            if resp.status_code == 204:
                return None
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Agent %s returned %s", agent.name, resp.status_code)
            return None
        except asyncio.TimeoutError:
            logger.warning("Agent %s timed out", agent.name)
            return None
        except Exception as exc:
            logger.warning("Agent %s error: %s", agent.name, exc)
            raise
```

- [ ] **Step 4: Run all orchestrator tests**

```bash
pytest -v
```

Expected: all 11 tests pass.

- [ ] **Step 5: Implement `orchestrator/main.py`**

```python
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
```

- [ ] **Step 6: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY orchestrator/ orchestrator/
RUN pip install -e "orchestrator/[dev]"
HEALTHCHECK --interval=30s --timeout=5s CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8081/health')"
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8081"]
```

- [ ] **Step 7: Verify Docker build (from repo root)**

```bash
docker build -f orchestrator/Dockerfile -t orchestrator .
```

Expected: build succeeds.

- [ ] **Step 8: Commit**

```bash
cd ..
git add orchestrator/orchestrator/turn_handler.py \
        orchestrator/orchestrator/main.py \
        orchestrator/tests/test_turn_handler.py \
        orchestrator/Dockerfile
git commit -m "feat: add orchestrator turn handler, FastAPI app, and Dockerfile"
```

---

## Task 7: Router Service — SessionRegistry

**Files:**
- Create: `router-service/pyproject.toml`
- Create: `router-service/router_service/__init__.py`
- Create: `router-service/router_service/session_registry.py`
- Create: `router-service/tests/__init__.py`
- Create: `router-service/tests/test_session_registry.py`

All commands run from `router-service/`.

- [ ] **Step 1: Create `pyproject.toml` and scaffold**

```toml
[project]
name = "router-service"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
    "google-genai>=1.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["."]
```

```bash
mkdir -p router_service/client tests
touch router_service/__init__.py tests/__init__.py
# Install voice-router (local dep) then this package
pip install -e "../voice-router" -e ".[dev]"
```

- [ ] **Step 2: Write failing tests**

Create `router-service/tests/test_session_registry.py`:

```python
from router_service.session_registry import SessionRegistry


def test_create_returns_uuid_session_id():
    reg = SessionRegistry()
    sid = reg.create(project_map=["mod1"], goals=["goal1"])
    assert isinstance(sid, str)
    assert len(sid) == 36  # UUID format


def test_get_returns_session_after_create():
    reg = SessionRegistry()
    sid = reg.create(project_map=[], goals=[])
    session = reg.get(sid)
    assert session is not None
    assert session.session_id == sid


def test_get_returns_none_for_unknown_id():
    reg = SessionRegistry()
    assert reg.get("nonexistent") is None


def test_remove_deletes_session():
    reg = SessionRegistry()
    sid = reg.create(project_map=[], goals=[])
    reg.remove(sid)
    assert reg.get(sid) is None


def test_multiple_sessions_are_independent():
    reg = SessionRegistry()
    sid1 = reg.create(project_map=["a"], goals=["x"])
    sid2 = reg.create(project_map=["b"], goals=["y"])
    assert sid1 != sid2
    assert reg.get(sid1).project_map == ["a"]
    assert reg.get(sid2).project_map == ["b"]
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_session_registry.py -v
```

Expected: `ModuleNotFoundError: No module named 'router_service'`

- [ ] **Step 4: Implement `router_service/session_registry.py`**

```python
import uuid
from typing import Optional


class _SessionSlot:
    """Minimal session placeholder until LiveSession is implemented."""
    def __init__(self, session_id: str, project_map: list[str], goals: list[str]) -> None:
        self.session_id = session_id
        self.project_map = project_map
        self.goals = goals


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, "_SessionSlot"] = {}

    def create(self, project_map: list[str], goals: list[str]) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = _SessionSlot(session_id, project_map, goals)
        return session_id

    def get(self, session_id: str) -> Optional["_SessionSlot"]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
```

Note: `_SessionSlot` is a placeholder; Task 8 replaces it with `LiveSession`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_session_registry.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
cd ..
git add router-service/
git commit -m "feat: add router-service package scaffold with SessionRegistry"
```

---

## Task 8: LiveSession — Gemini Setup, Streaming, Turn Events

**Files:**
- Create: `router-service/router_service/live_session.py`
- Create: `router-service/tests/test_live_session.py`
- Modify: `router-service/router_service/session_registry.py` (replace `_SessionSlot` with `LiveSession`)

All commands run from `router-service/`.

- [ ] **Step 1: Write failing tests**

Create `router-service/tests/test_live_session.py`:

```python
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from router_service.live_session import LiveSession


def _session(**kwargs):
    defaults = dict(
        session_id="test-id",
        project_map=["auth module"],
        goals=["ship MVP"],
        api_key="test-key",
        orchestrator_url="http://orchestrator:8081",
        transcript_output_dir="/tmp/transcripts",
        history_tail_length=10,
        live_api_model="gemini-test-model",
    )
    defaults.update(kwargs)
    return LiveSession(**defaults)


def _mock_gemini(responses=None):
    """Returns (mock_genai, mock_gemini_session)."""
    mock_session = AsyncMock()
    mock_session.send_realtime_input = AsyncMock()

    async def _receive():
        for r in (responses or []):
            yield r

    mock_session.receive = _receive

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.aio.live.connect.return_value = mock_cm

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    return mock_genai, mock_session


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_connect_sends_setup_and_initial_context(mock_genai):
    _, mock_session = _mock_gemini()
    mock_genai.Client.return_value.aio.live.connect.return_value.__aenter__ = (
        AsyncMock(return_value=mock_session)
    )
    mock_genai.Client.return_value.aio.live.connect.return_value.__aexit__ = (
        AsyncMock(return_value=None)
    )

    session = _session()
    await session.connect()

    mock_genai.Client.return_value.aio.live.connect.assert_called_once()
    call_kwargs = mock_genai.Client.return_value.aio.live.connect.call_args
    assert call_kwargs.kwargs["model"] == "gemini-test-model"

    # Initial context injected after connect
    mock_session.send_realtime_input.assert_called_once()
    ctx_call = mock_session.send_realtime_input.call_args
    assert "ship MVP" in str(ctx_call) or "auth module" in str(ctx_call)


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_turn_complete_sends_control_frame_and_posts_turn_event(mock_httpx, mock_genai):
    turn_complete_response = MagicMock()
    turn_complete_response.server_content = MagicMock()
    turn_complete_response.server_content.model_turn = None
    turn_complete_response.server_content.input_transcription = None
    turn_complete_response.server_content.output_transcription = None
    turn_complete_response.server_content.turn_complete = True
    turn_complete_response.server_content.interrupted = False

    mock_genai_inst, mock_session = _mock_gemini(responses=[turn_complete_response])
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock()
    mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_ws = AsyncMock()
    sent_texts = []
    mock_ws.send_text = AsyncMock(side_effect=lambda t: sent_texts.append(t))
    mock_ws.send_bytes = AsyncMock()
    mock_ws.receive = AsyncMock(side_effect=asyncio.CancelledError)

    session = _session()
    session._gemini_session = mock_session

    task = asyncio.create_task(session._gemini_to_browser(mock_ws))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    frames = [json.loads(t) for t in sent_texts]
    assert any(f["type"] == "turn_complete" for f in frames)
    mock_http_client.post.assert_called()


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_whisper_drain_sends_control_frame_then_injects_to_gemini(mock_genai):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    mock_ws = AsyncMock()
    sent_texts = []
    mock_ws.send_text = AsyncMock(side_effect=lambda t: sent_texts.append(t))

    session = _session()
    session._gemini_session = mock_session
    session.inject_whisper(source="DevCoach", message="try TDD")

    task = asyncio.create_task(session._whisper_drain(mock_ws))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    frames = [json.loads(t) for t in sent_texts]
    whisper_frames = [f for f in frames if f["type"] == "whisper"]
    assert len(whisper_frames) == 1
    assert whisper_frames[0]["source"] == "DevCoach"
    assert whisper_frames[0]["message"] == "try TDD"

    gemini_calls = str(mock_session.send_realtime_input.call_args_list)
    assert "[WHISPER from DevCoach]" in gemini_calls
    assert "try TDD" in gemini_calls


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_close_writes_transcript(mock_genai, tmp_path):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    session = _session(transcript_output_dir=str(tmp_path))
    session._gemini_session = mock_session
    session._gemini_cm = MagicMock()
    session._gemini_cm.__aexit__ = AsyncMock(return_value=None)
    session._history = ["User: hello", "Assistant: hi"]

    await session.close()

    transcript_file = tmp_path / "test-id.md"
    assert transcript_file.exists()
    content = transcript_file.read_text()
    assert "User: hello" in content
    assert "Assistant: hi" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_live_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'router_service.live_session'`

- [ ] **Step 3: Implement `router_service/live_session.py`**

```python
import asyncio
import base64
import json
import logging
import os
from typing import Optional

import httpx
from fastapi import WebSocket
from google import genai
from google.genai import types

from src.router.behavioral_contract import BEHAVIORAL_CONTRACT
from src.router.transcript_writer import TranscriptWriter

logger = logging.getLogger(__name__)


class LiveSession:
    def __init__(
        self,
        session_id: str,
        project_map: list[str],
        goals: list[str],
        api_key: str,
        orchestrator_url: str,
        transcript_output_dir: str,
        history_tail_length: int,
        live_api_model: str,
    ) -> None:
        self.session_id = session_id
        self.project_map = project_map
        self.goals = goals
        self._api_key = api_key
        self._orchestrator_url = orchestrator_url
        self._transcript_output_dir = transcript_output_dir
        self._history_tail_length = history_tail_length
        self._live_api_model = live_api_model

        self._client = genai.Client(api_key=api_key)
        self._gemini_session = None
        self._gemini_cm = None
        self._history: list[str] = []
        self._whisper_queue: asyncio.Queue = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    async def connect(self) -> None:
        config = {
            "response_modalities": ["AUDIO"],
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "system_instruction": BEHAVIORAL_CONTRACT,
        }
        self._gemini_cm = self._client.aio.live.connect(
            model=self._live_api_model, config=config
        )
        self._gemini_session = await self._gemini_cm.__aenter__()
        context = (
            f"Session context — Goals: {'; '.join(self.goals) or 'None'}. "
            f"Project map: {'; '.join(self.project_map) or 'None'}."
        )
        await self._gemini_session.send_realtime_input(text=context)

    async def stream(self, browser_ws: WebSocket) -> None:
        tasks = [
            asyncio.create_task(self._browser_to_gemini(browser_ws)),
            asyncio.create_task(self._gemini_to_browser(browser_ws)),
            asyncio.create_task(self._whisper_drain(browser_ws)),
        ]
        self._tasks = tasks
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    def inject_whisper(self, source: str, message: str) -> None:
        self._whisper_queue.put_nowait({"source": source, "message": message})

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._gemini_cm:
            await self._gemini_cm.__aexit__(None, None, None)
        try:
            os.makedirs(self._transcript_output_dir, exist_ok=True)
            TranscriptWriter(self._transcript_output_dir).write_transcript(
                self.session_id, self._history
            )
        except Exception as exc:
            logger.error("Failed to write transcript for session %s: %s", self.session_id, exc)

    async def _browser_to_gemini(self, browser_ws: WebSocket) -> None:
        try:
            while True:
                message = await browser_ws.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("bytes"):
                    await self._gemini_session.send_realtime_input(
                        audio=types.Blob(
                            data=message["bytes"], mime_type="audio/pcm;rate=16000"
                        )
                    )
        except Exception:
            pass

    async def _gemini_to_browser(self, browser_ws: WebSocket) -> None:
        async for response in self._gemini_session.receive():
            sc = response.server_content
            if not sc:
                continue
            if sc.model_turn:
                for part in sc.model_turn.parts:
                    if part.inline_data:
                        await browser_ws.send_bytes(
                            base64.b64decode(part.inline_data.data)
                        )
            if sc.input_transcription and sc.input_transcription.text:
                text = sc.input_transcription.text
                self._history.append(f"User: {text}")
                await browser_ws.send_text(
                    json.dumps({"type": "transcript", "role": "user", "text": text})
                )
            if sc.output_transcription and sc.output_transcription.text:
                text = sc.output_transcription.text
                self._history.append(f"Assistant: {text}")
                await browser_ws.send_text(
                    json.dumps({"type": "transcript", "role": "assistant", "text": text})
                )
            if sc.turn_complete:
                await browser_ws.send_text(json.dumps({"type": "turn_complete"}))
                asyncio.create_task(self._post_turn_event())
            if getattr(sc, "interrupted", False):
                await browser_ws.send_text(json.dumps({"type": "interrupted"}))

    async def _whisper_drain(self, browser_ws: WebSocket) -> None:
        while True:
            whisper = await self._whisper_queue.get()
            await browser_ws.send_text(json.dumps({
                "type": "whisper",
                "source": whisper["source"],
                "message": whisper["message"],
            }))
            await self._gemini_session.send_realtime_input(
                text=f"[WHISPER from {whisper['source']}]: {whisper['message']}"
            )

    async def _post_turn_event(self) -> None:
        tail = self._history[-self._history_tail_length:]
        payload = {
            "session_id": self.session_id,
            "history_tail": tail,
            "goals": self.goals,
            "project_map": self.project_map,
        }
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{self._orchestrator_url}/turns", json=payload, timeout=2.0
                )
            except Exception as exc:
                logger.warning("Failed to post turn event: %s", exc)
```

- [ ] **Step 4: Update `session_registry.py` to use `LiveSession`**

Replace the contents of `router-service/router_service/session_registry.py`:

```python
import os
import uuid
from typing import Optional
from router_service.live_session import LiveSession


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}

    def create(self, project_map: list[str], goals: list[str]) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = LiveSession(
            session_id=session_id,
            project_map=project_map,
            goals=goals,
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            orchestrator_url=os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8081"),
            transcript_output_dir=os.environ.get("TRANSCRIPT_OUTPUT_DIR", "/app/transcripts"),
            history_tail_length=int(os.environ.get("HISTORY_TAIL_LENGTH", "10")),
            live_api_model=os.environ.get("LIVE_API_MODEL", "gemini-2.0-flash-live-001"),
        )
        return session_id

    def get(self, session_id: str) -> Optional[LiveSession]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
```

- [ ] **Step 5: Update `test_session_registry.py` to match `LiveSession`**

The existing session registry tests reference `.project_map` — these still hold because `LiveSession` has that attribute. Run to confirm:

```bash
pytest tests/test_session_registry.py -v
```

Expected: all 5 tests pass (the property access works because `LiveSession` exposes `project_map`).

- [ ] **Step 6: Run all router-service tests**

```bash
pytest -v
```

Expected: all live_session and session_registry tests pass.

- [ ] **Step 7: Commit**

```bash
cd ..
git add router-service/router_service/live_session.py \
        router-service/router_service/session_registry.py \
        router-service/tests/test_live_session.py
git commit -m "feat: implement LiveSession — Gemini Live connect, streaming tasks, whisper drain, close"
```

---

## Task 9: Router Service — FastAPI Endpoints + Dockerfile

**Files:**
- Create: `router-service/router_service/main.py`
- Create: `router-service/tests/test_endpoints.py`
- Create: `router-service/Dockerfile`

All commands run from `router-service/`.

- [ ] **Step 1: Write failing tests**

Create `router-service/tests/test_endpoints.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("router_service.main.registry") as mock_reg:
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.inject_whisper = MagicMock()
        mock_reg.create.return_value = "test-session-id"
        mock_reg.get.return_value = mock_session
        from router_service.main import app
        yield TestClient(app), mock_reg, mock_session


def test_post_sessions_returns_session_id(client):
    test_client, mock_reg, _ = client
    resp = test_client.post("/sessions", json={"project_map": ["mod1"], "goals": ["g1"]})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "test-session-id"
    mock_reg.create.assert_called_once_with(project_map=["mod1"], goals=["g1"])


def test_post_whisper_to_existing_session(client):
    test_client, _, mock_session = client
    resp = test_client.post(
        "/sessions/test-session-id/whisper",
        json={"source": "DevCoach", "message": "try TDD"},
    )
    assert resp.status_code == 200
    mock_session.inject_whisper.assert_called_once_with(source="DevCoach", message="try TDD")


def test_post_whisper_to_unknown_session_returns_404(client):
    test_client, mock_reg, _ = client
    mock_reg.get.return_value = None
    resp = test_client.post(
        "/sessions/bad-id/whisper",
        json={"source": "DevCoach", "message": "hi"},
    )
    assert resp.status_code == 404


def test_delete_session_calls_close(client):
    test_client, mock_reg, mock_session = client
    resp = test_client.delete("/sessions/test-session-id")
    assert resp.status_code == 200
    mock_session.close.assert_called_once()
    mock_reg.remove.assert_called_once_with("test-session-id")


def test_health_returns_ok(client):
    test_client, _, _ = client
    resp = test_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_endpoints.py -v
```

Expected: `ModuleNotFoundError: No module named 'router_service.main'`

- [ ] **Step 3: Implement `router_service/main.py`**

```python
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from router_service.session_registry import SessionRegistry

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
```

- [ ] **Step 4: Run all router-service tests**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY voice-router/ voice-router/
COPY router-service/ router-service/
RUN pip install -e "voice-router/" -e "router-service/[dev]"
HEALTHCHECK --interval=30s --timeout=5s CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"
CMD ["uvicorn", "router_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 6: Verify Docker build (from repo root)**

```bash
docker build -f router-service/Dockerfile -t router-service .
```

Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
cd ..
git add router-service/router_service/main.py \
        router-service/tests/test_endpoints.py \
        router-service/Dockerfile
git commit -m "feat: add router-service FastAPI endpoints and Dockerfile"
```

---

## Task 10: Browser Client

**Files:**
- Create: `router-service/router_service/client/index.html`
- Create: `router-service/router_service/client/audio.js`
- Create: `router-service/router_service/client/session.js`

No unit tests. Verify manually by running the stack (Task 12) and opening `http://localhost:8080`.

- [ ] **Step 1: Create `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dev Partner</title>
  <style>
    body { font-family: monospace; max-width: 800px; margin: 40px auto; padding: 0 20px; }
    #status { font-weight: bold; margin: 12px 0; }
    #form { display: none; margin: 16px 0; }
    textarea { width: 100%; height: 80px; margin: 4px 0; font-family: monospace; }
    #transcript { border: 1px solid #ccc; padding: 12px; height: 400px; overflow-y: auto; white-space: pre-wrap; font-size: 13px; }
    .user { color: #0055aa; }
    .assistant { color: #222; }
    .whisper { color: #888; font-style: italic; }
    button { margin-right: 8px; padding: 6px 14px; cursor: pointer; }
    label { font-size: 13px; }
  </style>
</head>
<body>
  <h2>Dev Partner</h2>
  <div id="status">Ready</div>

  <div>
    <button id="startBtn" onclick="showForm()">Start Session</button>
    <button id="endBtn" onclick="endSession()" disabled>End Session</button>
    <label><input type="checkbox" id="debugToggle"> Debug (show whispers)</label>
  </div>

  <div id="form">
    <label>What are you working on?</label>
    <textarea id="projectMap" placeholder="e.g. voice-router — extracting behavioral contract"></textarea>
    <label>What do you want to accomplish today?</label>
    <textarea id="goals" placeholder="e.g. Extract BEHAVIORAL_CONTRACT, keep all tests green"></textarea>
    <button onclick="startSession()">Connect</button>
    <button onclick="cancelForm()">Cancel</button>
  </div>

  <div id="transcript"></div>

  <script src="audio.js"></script>
  <script src="session.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `audio.js`**

```javascript
// audio.js — mic capture, PCM resampling, playback

const SAMPLE_RATE_IN = 16000;
const SAMPLE_RATE_OUT = 24000;

const WORKLET_CODE = `
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    const pcm = new Int16Array(ch.length);
    for (let i = 0; i < ch.length; i++) {
      pcm[i] = Math.max(-32768, Math.min(32767, ch[i] * 32768));
    }
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
`;

let audioCtxIn = null;
let audioCtxOut = null;
let workletNode = null;
let micStream = null;
let onPCMChunk = null;   // callback(ArrayBuffer) set by session.js
let playbackQueue = [];
let playbackTime = 0;

async function startMic(onChunk) {
  onPCMChunk = onChunk;
  const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
  const url = URL.createObjectURL(blob);

  audioCtxIn = new AudioContext({ sampleRate: SAMPLE_RATE_IN });
  await audioCtxIn.audioWorklet.addModule(url);

  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const source = audioCtxIn.createMediaStreamSource(micStream);
  workletNode = new AudioWorkletNode(audioCtxIn, 'pcm-processor');
  workletNode.port.onmessage = (e) => onPCMChunk && onPCMChunk(e.data);
  source.connect(workletNode);
}

function stopMic() {
  if (workletNode) { workletNode.disconnect(); workletNode = null; }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  if (audioCtxIn) { audioCtxIn.close(); audioCtxIn = null; }
}

function playPCM(arrayBuffer) {
  if (!audioCtxOut) audioCtxOut = new AudioContext({ sampleRate: SAMPLE_RATE_OUT });
  const pcm = new Int16Array(arrayBuffer);
  const floats = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) floats[i] = pcm[i] / 32768;
  const buf = audioCtxOut.createBuffer(1, floats.length, SAMPLE_RATE_OUT);
  buf.copyToChannel(floats, 0);
  const src = audioCtxOut.createBufferSource();
  src.buffer = buf;
  src.connect(audioCtxOut.destination);
  const now = audioCtxOut.currentTime;
  if (playbackTime < now) playbackTime = now;
  src.start(playbackTime);
  playbackTime += buf.duration;
}

function flushPlayback() {
  if (audioCtxOut) {
    audioCtxOut.close();
    audioCtxOut = null;
    playbackTime = 0;
  }
}
```

- [ ] **Step 3: Create `session.js`**

```javascript
// session.js — session lifecycle and control frame handling

let ws = null;
let sessionId = null;

function showForm() {
  document.getElementById('form').style.display = 'block';
  document.getElementById('startBtn').disabled = true;
}

function cancelForm() {
  document.getElementById('form').style.display = 'none';
  document.getElementById('startBtn').disabled = false;
}

async function startSession() {
  const projectMap = document.getElementById('projectMap').value.trim();
  const goals = document.getElementById('goals').value.trim();

  setStatus('Connecting…');
  document.getElementById('form').style.display = 'none';

  const resp = await fetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_map: projectMap ? [projectMap] : [],
      goals: goals ? [goals] : [],
    }),
  });
  const { session_id } = await resp.json();
  sessionId = session_id;

  ws = new WebSocket(`ws://${location.host}/sessions/${session_id}/audio`);
  ws.binaryType = 'arraybuffer';

  ws.onopen = async () => {
    setStatus('Listening');
    document.getElementById('endBtn').disabled = false;
    await startMic((pcmBuffer) => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(pcmBuffer);
    });
  };

  ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      setStatus('Speaking');
      playPCM(event.data);
    } else {
      const msg = JSON.parse(event.data);
      handleControlFrame(msg);
    }
  };

  ws.onclose = () => {
    stopMic();
    setStatus('Ended');
    document.getElementById('endBtn').disabled = true;
    document.getElementById('startBtn').disabled = false;
  };

  ws.onerror = () => setStatus('Error — check console');
}

async function endSession() {
  if (sessionId) {
    await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
  }
  if (ws) ws.close();
  stopMic();
  setStatus('Ended');
  document.getElementById('endBtn').disabled = true;
  document.getElementById('startBtn').disabled = false;
}

function handleControlFrame(msg) {
  switch (msg.type) {
    case 'turn_complete':
      setStatus('Listening');
      break;
    case 'interrupted':
      flushPlayback();
      setStatus('Listening');
      break;
    case 'transcript':
      appendTranscript(msg.role, msg.text);
      break;
    case 'whisper':
      if (document.getElementById('debugToggle').checked) {
        appendWhisper(msg.source, msg.message);
      }
      break;
  }
}

function appendTranscript(role, text) {
  const div = document.getElementById('transcript');
  const line = document.createElement('div');
  line.className = role;
  line.textContent = `${role === 'user' ? 'You' : 'Dev Partner'}: ${text}`;
  div.appendChild(line);
  div.scrollTop = div.scrollHeight;
}

function appendWhisper(source, message) {
  const div = document.getElementById('transcript');
  const line = document.createElement('div');
  line.className = 'whisper';
  line.textContent = `[${source} →] ${message}`;
  div.appendChild(line);
  div.scrollTop = div.scrollHeight;
}

function setStatus(text) {
  document.getElementById('status').textContent = text;
}
```

- [ ] **Step 4: Commit**

```bash
cd ..
git add router-service/router_service/client/
git commit -m "feat: add browser client — HTML, audio worklet, session lifecycle, control frame handler"
```

---

## Task 11: docker-compose, .env.example, CI

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.github/workflows/ci.yml`
- Create: `transcripts/.gitkeep`
- Modify: `.gitignore` (add `.env`, `transcripts/*.md`)

All commands run from repo root (`gcsb/`).

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  router-service:
    build:
      context: .
      dockerfile: router-service/Dockerfile
    ports:
      - "8080:8080"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - ORCHESTRATOR_URL=http://orchestrator:8081
      - LIVE_API_MODEL=${LIVE_API_MODEL:-gemini-2.0-flash-live-001}
      - HISTORY_TAIL_LENGTH=${HISTORY_TAIL_LENGTH:-10}
      - TRANSCRIPT_OUTPUT_DIR=/app/transcripts
    volumes:
      - ./transcripts:/app/transcripts
    depends_on:
      orchestrator:
        condition: service_healthy

  orchestrator:
    build:
      context: .
      dockerfile: orchestrator/Dockerfile
    ports:
      - "8081:8081"
    environment:
      - ROUTER_SERVICE_URL=http://router-service:8080
      - CONFIDENCE_THRESHOLD=${CONFIDENCE_THRESHOLD:-0.5}
      - AGENT_TIMEOUT_SECONDS=${AGENT_TIMEOUT_SECONDS:-2}
    depends_on:
      dev-coach:
        condition: service_healthy

  dev-coach:
    build:
      context: .
      dockerfile: expert-agents/dev-coach/Dockerfile
    ports:
      - "8082:8082"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DEV_COACH_MODEL=${DEV_COACH_MODEL:-gemini-2.0-flash}
```

- [ ] **Step 2: Create `.env.example`**

```bash
GEMINI_API_KEY=your_key_here
LIVE_API_MODEL=gemini-2.0-flash-live-001
DEV_COACH_MODEL=gemini-2.0-flash
CONFIDENCE_THRESHOLD=0.5
AGENT_TIMEOUT_SECONDS=2
HISTORY_TAIL_LENGTH=10
```

- [ ] **Step 3: Create `transcripts/` and update `.gitignore`**

```bash
mkdir -p transcripts
touch transcripts/.gitkeep
```

Append to `.gitignore` (create if it doesn't exist):

```
.env
transcripts/*.md
**/venv/
**/__pycache__/
**/*.egg-info/
```

- [ ] **Step 4: Validate docker-compose syntax**

```bash
docker compose config > /dev/null && echo "OK"
```

Expected: `OK`

- [ ] **Step 5: Create `.github/workflows/ci.yml`**

```bash
mkdir -p .github/workflows
```

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  voice-router:
    runs-on: ubuntu-latest
    if: |
      contains(github.event.head_commit.modified, 'voice-router/') ||
      github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e "voice-router/[dev]"
      - run: pytest voice-router/tests/ -v
      - run: docker build -f voice-router/Dockerfile -t voice-router-test .

  router-service:
    runs-on: ubuntu-latest
    needs: voice-router
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e "voice-router/" -e "router-service/[dev]"
      - run: pytest router-service/tests/ -v
      - run: docker build -f router-service/Dockerfile -t router-service .

  orchestrator:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e "orchestrator/[dev]"
      - run: pytest orchestrator/tests/ -v
      - run: docker build -f orchestrator/Dockerfile -t orchestrator .

  dev-coach:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e "expert-agents/base/" -e "expert-agents/dev-coach/[dev]"
      - run: pytest expert-agents/dev-coach/tests/ -v
      - run: docker build -f expert-agents/dev-coach/Dockerfile -t dev-coach .
```

- [ ] **Step 6: Commit everything**

```bash
git add docker-compose.yml .env.example transcripts/.gitkeep .gitignore \
        .github/workflows/ci.yml
git commit -m "feat: add docker-compose, .env.example, transcripts volume, and GitHub Actions CI"
```

---

## Task 12: End-to-End Smoke Test

No code changes. This task verifies the full stack works.

- [ ] **Step 1: Copy `.env` and set your API key**

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=<your actual key>
```

- [ ] **Step 2: Build and start all services**

```bash
docker compose up --build
```

Expected: all three services start and pass their health checks. Watch for:
```
dev-coach      | INFO:     Application startup complete.
orchestrator   | INFO:     Application startup complete.
router-service | INFO:     Application startup complete.
```

- [ ] **Step 3: Verify health endpoints**

```bash
curl -s http://localhost:8082/health | python -m json.tool
curl -s http://localhost:8081/health | python -m json.tool
curl -s http://localhost:8080/health | python -m json.tool
```

Expected: each returns `{"status": "ok"}`.

- [ ] **Step 4: Open browser and start a session**

Navigate to `http://localhost:8080`. Click **Start Session**, fill in project context and goals, click **Connect**. Speak a sentence and verify:

1. Status shows `Listening` then `Speaking` then `Listening`
2. Transcript pane shows your words and the Dev Partner's response
3. After 2-3 exchanges, enable **Debug** toggle — verify whisper lines appear when the Dev Coach fires

- [ ] **Step 5: End session and verify transcript**

Click **End Session**. Check `transcripts/` directory:

```bash
ls transcripts/
cat transcripts/<session-id>.md
```

Expected: markdown file containing the full interleaved conversation.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "chore: end-to-end smoke test verified — MVP vertical slice complete"
```

---

## Self-Review Notes

- All Gemini API calls are mocked in unit tests; `GEMINI_API_KEY` is intentionally absent from CI unit-test jobs.
- `_SessionSlot` in `session_registry.py` is a temporary placeholder replaced in Task 8 — the tests in Task 7 still pass after the replacement because `LiveSession` exposes the same `.project_map` attribute.
- The `orchestrator/orchestrator/agents.yaml` path is relative to `__file__` in `main.py` — it resolves correctly both in the container (`/app/orchestrator/orchestrator/agents.yaml`) and in local dev.
- Browser `getUserMedia` requires `localhost` or HTTPS. The MVP runs at `http://localhost:8080` — this works in Chrome and Firefox but not from a different host without TLS.
- The `voice-router` package installs as `src.router.*` (its unusual `src`-layout convention). All router-service imports from it use `from src.router.xxx import yyy`.
- Model IDs (`LIVE_API_MODEL`, `DEV_COACH_MODEL`) are configurable via environment variables throughout — swap without code changes.
