# Expert Agent Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, schema-driven wiki to `ExpertAgentBase` so every expert agent accumulates knowledge across sessions and enriches whisper responses from that knowledge.

**Architecture:** Each agent owns a `WikiManager` (file I/O only) and a `wiki_schema.md` that governs what it tracks. The base class provides default `_ingest_session` and `_query_wiki` implementations via a new abstract `_generate` method. The orchestrator dispatches transcripts to agents at session close; agents update their wikis as background tasks.

**Tech Stack:** Python 3.11, FastAPI BackgroundTasks, Google Gemini (via `google-genai`), pytest, httpx, standard-library `pathlib`/`re`/`datetime`

---

## File Map

| Status | File | Change |
|--------|------|--------|
| Create | `expert-agents/base/expert_agent_base/wiki.py` | `WikiManager` class + `parse_ingest_response` |
| Create | `expert-agents/base/tests/test_wiki.py` | Unit tests for WikiManager |
| Modify | `expert-agents/base/expert_agent_base/base.py` | Add `wiki_context` to `WhisperContext`; add `_generate` abstract; add wiki attrs + `/ingest` + `_ingest_session` + `_query_wiki` to `ExpertAgentBase` |
| Modify | `expert-agents/base/tests/test_base.py` | Update test helpers to implement `_generate`; add wiki env fixture; add `/ingest` tests |
| Modify | `expert-agents/dev-coach/dev_coach/main.py` | Implement `_generate`; update whisper prompt to use `context.wiki_context` |
| Create | `expert-agents/dev-coach/wiki_schema.md` | Dev-coach wiki schema (Markdown) |
| Modify | `expert-agents/dev-coach/Dockerfile` | `COPY` wiki_schema.md to `/app/wiki_schema.md` |
| Create | `orchestrator/orchestrator/session_handler.py` | `handle_session_close` fan-out function |
| Create | `orchestrator/tests/test_session_handler.py` | Tests for session close fan-out |
| Modify | `orchestrator/orchestrator/main.py` | Add `POST /sessions/{session_id}/close` endpoint |
| Modify | `router-service/router_service/live_session.py` | Call orchestrator on session close |
| Modify | `router-service/tests/test_live_session.py` | Add test for close notification |
| Modify | `docker-compose.yml` | Add wiki volume mount for dev-coach |

---

## Task 1: WikiManager

**Files:**
- Create: `expert-agents/base/expert_agent_base/wiki.py`
- Create: `expert-agents/base/tests/test_wiki.py`

- [ ] **Step 1: Write the failing tests**

Create `expert-agents/base/tests/test_wiki.py`:

```python
import pytest
from pathlib import Path
from expert_agent_base.wiki import WikiManager, parse_ingest_response


@pytest.fixture
def wiki(tmp_path):
    w = WikiManager(str(tmp_path / "wiki"))
    w.scaffold_if_empty()
    return w


def test_scaffold_creates_index_and_log(tmp_path):
    w = WikiManager(str(tmp_path / "wiki"))
    w.scaffold_if_empty()
    assert (tmp_path / "wiki" / "index.md").exists()
    assert (tmp_path / "wiki" / "log.md").exists()
    assert (tmp_path / "wiki" / "pages").is_dir()


def test_scaffold_is_idempotent(tmp_path):
    w = WikiManager(str(tmp_path / "wiki"))
    w.scaffold_if_empty()
    w.scaffold_if_empty()  # should not raise or overwrite
    assert (tmp_path / "wiki" / "index.md").exists()


def test_read_index_returns_scaffold_content(wiki):
    content = wiki.read_index()
    assert "# Wiki Index" in content


def test_write_and_read_page(wiki):
    wiki.write_page("decisions.md", "# Decisions\n\nUse TDD.")
    assert wiki.read_page("decisions.md") == "# Decisions\n\nUse TDD."


def test_write_page_is_atomic(wiki, tmp_path):
    wiki.write_page("test.md", "content")
    # tmp file should be gone after write
    assert not list((tmp_path / "wiki" / "pages").glob("*.tmp"))


def test_list_pages_returns_md_files(wiki):
    wiki.write_page("a.md", "A")
    wiki.write_page("b.md", "B")
    pages = wiki.list_pages()
    assert set(pages) == {"a.md", "b.md"}


def test_list_pages_empty_when_no_pages(wiki):
    assert wiki.list_pages() == []


def test_append_log(wiki):
    wiki.append_log("## [2026-04-28] ingest | abc123")
    assert "abc123" in wiki.read_log()


def test_write_index(wiki):
    wiki.write_index("# Updated Index\n\n- [[page.md]] — some page")
    assert "Updated Index" in wiki.read_index()


def test_parse_ingest_response_extracts_pages():
    raw = """
--- PAGE: decisions.md ---
# Decisions
Use TDD.
--- END PAGE ---

--- INDEX ---
# Wiki Index

- [[decisions.md]] — TDD decision
--- INDEX END ---
"""
    pages, index = parse_ingest_response(raw)
    assert len(pages) == 1
    assert pages[0][0] == "decisions.md"
    assert "Use TDD" in pages[0][1]
    assert "decisions.md" in index


def test_parse_ingest_response_handles_missing_index():
    raw = "--- PAGE: x.md ---\ncontent\n--- END PAGE ---\n"
    pages, index = parse_ingest_response(raw)
    assert len(pages) == 1
    assert index is None


def test_parse_ingest_response_empty_response():
    pages, index = parse_ingest_response("nothing useful here")
    assert pages == []
    assert index is None
```

- [ ] **Step 2: Run tests to see them fail**

```bash
cd expert-agents/base && pytest tests/test_wiki.py -v
```
Expected: `ImportError: cannot import name 'WikiManager'`

- [ ] **Step 3: Implement `wiki.py`**

Create `expert-agents/base/expert_agent_base/wiki.py`:

```python
import re
from pathlib import Path


class WikiManager:
    INDEX = "index.md"
    LOG = "log.md"
    PAGES_DIR = "pages"

    def __init__(self, wiki_dir: str) -> None:
        self._dir = Path(wiki_dir)

    def scaffold_if_empty(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / self.PAGES_DIR).mkdir(exist_ok=True)
        index = self._dir / self.INDEX
        if not index.exists():
            index.write_text("# Wiki Index\n\n", encoding="utf-8")
        log = self._dir / self.LOG
        if not log.exists():
            log.write_text("# Wiki Log\n\n", encoding="utf-8")

    def read_index(self) -> str:
        return (self._dir / self.INDEX).read_text(encoding="utf-8")

    def read_log(self) -> str:
        return (self._dir / self.LOG).read_text(encoding="utf-8")

    def read_page(self, name: str) -> str:
        return (self._dir / self.PAGES_DIR / name).read_text(encoding="utf-8")

    def write_page(self, name: str, content: str) -> None:
        pages_dir = self._dir / self.PAGES_DIR
        pages_dir.mkdir(parents=True, exist_ok=True)
        target = pages_dir / name
        tmp = target.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(target)

    def write_index(self, content: str) -> None:
        target = self._dir / self.INDEX
        tmp = target.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(target)

    def list_pages(self) -> list[str]:
        pages_dir = self._dir / self.PAGES_DIR
        if not pages_dir.exists():
            return []
        return [f.name for f in pages_dir.iterdir() if f.suffix == ".md"]

    def append_log(self, entry: str) -> None:
        log = self._dir / self.LOG
        with log.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")


def parse_ingest_response(response: str) -> tuple[list[tuple[str, str]], str | None]:
    pages = []
    for match in re.finditer(
        r"--- PAGE: (.+?) ---\n(.*?)--- END PAGE ---", response, re.DOTALL
    ):
        pages.append((match.group(1).strip(), match.group(2).strip()))
    index_match = re.search(
        r"--- INDEX ---\n(.*?)--- INDEX END ---", response, re.DOTALL
    )
    index = index_match.group(1).strip() if index_match else None
    return pages, index
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
cd expert-agents/base && pytest tests/test_wiki.py -v
```
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add expert-agents/base/expert_agent_base/wiki.py expert-agents/base/tests/test_wiki.py
git commit -m "feat: add WikiManager and parse_ingest_response to expert-agent-base"
```

---

## Task 2: Base Class Wiki Setup + `/ingest` Endpoint + `_generate` Abstract

**Files:**
- Modify: `expert-agents/base/expert_agent_base/base.py`
- Modify: `expert-agents/base/tests/test_base.py`

- [ ] **Step 1: Write the failing tests**

Replace the contents of `expert-agents/base/tests/test_base.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from expert_agent_base.base import ExpertAgentBase, WhisperContext, WhisperResponse


@pytest.fixture(autouse=True)
def wiki_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("WIKI_SCHEMA_PATH", str(tmp_path / "schema.md"))


class ConcreteAgent(ExpertAgentBase):
    async def _generate(self, prompt: str) -> str:
        return ""

    async def whisper(self, context: WhisperContext) -> WhisperResponse:
        return WhisperResponse(source="Test", message="hello", confidence=0.9)


class SilentAgent(ExpertAgentBase):
    async def _generate(self, prompt: str) -> str:
        return ""

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
        async def _generate(self, prompt: str) -> str:
            return ""
        async def whisper(self, context):
            raise RuntimeError("LLM unavailable")

    client = TestClient(BrokenAgent(model="m").app)
    resp = client.post("/whisper", json=_context())
    assert resp.status_code == 503


def test_ingest_endpoint_returns_202():
    client = TestClient(ConcreteAgent(model="m").app)
    resp = client.post("/ingest", json={"session_id": "s1", "transcript": "User: hello"})
    assert resp.status_code == 202


def test_whisper_context_has_wiki_context_field():
    ctx = WhisperContext(session_id="s1", history=[], goals=[], project_map=[])
    assert ctx.wiki_context == ""
```

- [ ] **Step 2: Run tests to see them fail**

```bash
cd expert-agents/base && pytest tests/test_base.py -v
```
Expected: multiple failures — `_generate` not abstract, no `/ingest` endpoint, no `wiki_context` on `WhisperContext`

- [ ] **Step 3: Update `base.py`**

Replace `expert-agents/base/expert_agent_base/base.py` with:

```python
import datetime
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse, Response

from expert_agent_base.wiki import WikiManager, parse_ingest_response

logger = logging.getLogger(__name__)

_INGEST_PROMPT = """\
You are maintaining a wiki for an expert agent. Extract key information from the session transcript and update the wiki.

WIKI SCHEMA:
{schema}

CURRENT INDEX:
{index}

SESSION TRANSCRIPT (session_id: {session_id}):
{transcript}

Write any pages to create or update using this exact format:

--- PAGE: <filename.md> ---
<full markdown page content>
--- END PAGE ---

Then write the updated index.md:

--- INDEX ---
<full index.md content>
--- INDEX END ---

Only include pages with genuinely useful information. Skip if transcript has nothing worth recording."""

_QUERY_WIKI_PROMPT = """\
Given the wiki index and a conversation context, list the filenames of the most relevant wiki pages.

WIKI INDEX:
{index}

CONVERSATION CONTEXT:
{context}

Output up to 5 filenames, one per line. No explanation, no numbering.
If nothing is relevant, output exactly: NONE"""


@dataclass
class WhisperContext:
    session_id: str
    history: list[str]
    goals: list[str]
    project_map: list[str]
    wiki_context: str = field(default="")


@dataclass
class WhisperResponse:
    source: str
    message: str
    confidence: float


class ExpertAgentBase(ABC):
    def __init__(self, model: str) -> None:
        self.model = model
        wiki_dir = os.environ.get("WIKI_DIR", "/app/wiki")
        schema_path = os.environ.get("WIKI_SCHEMA_PATH", "/app/wiki_schema.md")
        self._wiki = WikiManager(wiki_dir)
        self._wiki.scaffold_if_empty()
        schema_file = Path(schema_path)
        self._wiki_schema = schema_file.read_text(encoding="utf-8") if schema_file.exists() else ""
        self._app = self._build_app()

    @property
    def app(self) -> FastAPI:
        return self._app

    @abstractmethod
    async def _generate(self, prompt: str) -> str:
        ...

    @abstractmethod
    async def whisper(self, context: WhisperContext) -> Optional[WhisperResponse]:
        ...

    async def _ingest_session(self, session_id: str, transcript: str) -> None:
        if not self._wiki_schema:
            return
        index = self._wiki.read_index()
        prompt = _INGEST_PROMPT.format(
            schema=self._wiki_schema,
            index=index,
            session_id=session_id,
            transcript=transcript,
        )
        raw = await self._generate(prompt)
        pages, new_index = parse_ingest_response(raw)
        for filename, content in pages:
            self._wiki.write_page(filename, content)
        if new_index:
            self._wiki.write_index(new_index)
        date = datetime.date.today().isoformat()
        self._wiki.append_log(f"\n## [{date}] ingest | {session_id}")

    async def _query_wiki(self, context: str) -> str:
        try:
            index = self._wiki.read_index()
            if not index.strip() or index.strip() == "# Wiki Index":
                return ""
            prompt = _QUERY_WIKI_PROMPT.format(index=index, context=context)
            raw = (await self._generate(prompt)).strip()
            if not raw or raw == "NONE":
                return ""
            page_names = [line.strip() for line in raw.splitlines() if line.strip()]
            parts = []
            for name in page_names[:5]:
                try:
                    content = self._wiki.read_page(name)
                    parts.append(f"### {name}\n{content}")
                except (FileNotFoundError, OSError):
                    pass
            return "\n\n".join(parts)
        except Exception as exc:
            logger.warning("_query_wiki failed: %s", exc)
            return ""

    async def _safe_ingest(self, session_id: str, transcript: str) -> None:
        try:
            await self._ingest_session(session_id, transcript)
        except Exception as exc:
            logger.error("Wiki ingest failed session=%s: %s", session_id, exc)
            date = datetime.date.today().isoformat()
            try:
                self._wiki.append_log(f"\n## [{date}] FAILED | {session_id} | {exc}")
            except Exception:
                pass

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.post("/ingest", status_code=202)
        async def ingest_endpoint(body: dict, background_tasks: BackgroundTasks):
            background_tasks.add_task(self._safe_ingest, body["session_id"], body["transcript"])
            return {}

        @app.post("/whisper")
        async def whisper_endpoint(body: dict):
            context = WhisperContext(
                session_id=body["session_id"],
                history=body["context"]["history"],
                goals=body["context"]["goals"],
                project_map=body["context"]["project_map"],
            )
            context.wiki_context = await self._query_wiki("\n".join(context.history))
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

- [ ] **Step 4: Run tests and verify they pass**

```bash
cd expert-agents/base && pytest tests/ -v
```
Expected: all tests in `test_base.py` and `test_wiki.py` pass

- [ ] **Step 5: Commit**

```bash
git add expert-agents/base/expert_agent_base/base.py expert-agents/base/tests/test_base.py
git commit -m "feat: add wiki lifecycle, /ingest endpoint, and _generate abstract to ExpertAgentBase"
```

---

## Task 3: DevCoach — `_generate`, Wiki Prompt Integration, and `wiki_schema.md`

**Files:**
- Modify: `expert-agents/dev-coach/dev_coach/main.py`
- Create: `expert-agents/dev-coach/wiki_schema.md`
- Modify: `expert-agents/dev-coach/Dockerfile`
- Modify: `expert-agents/dev-coach/tests/test_whisper.py`

- [ ] **Step 1: Write the failing tests**

Add to `expert-agents/dev-coach/tests/test_whisper.py` (append after existing tests):

```python
@pytest.fixture(autouse=True)
def wiki_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("WIKI_SCHEMA_PATH", str(tmp_path / "schema.md"))


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_generate_calls_gemini_with_prompt(mock_genai):
    mock_resp = MagicMock()
    mock_resp.text = "result text"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    coach = DevCoach()
    result = await coach._generate("test prompt")
    assert result == "result text"
    mock_client.aio.models.generate_content.assert_awaited_once()


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_whisper_includes_wiki_context_in_prompt(mock_genai):
    mock_resp = MagicMock()
    mock_resp.text = "Consider pair programming."
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    from expert_agent_base.base import WhisperContext
    coach = DevCoach()
    ctx = WhisperContext(
        session_id="s1",
        history=["User: Hello", "Assistant: Hi"],
        goals=["ship MVP"],
        project_map=["voice-router"],
        wiki_context="### decisions.md\nWe use TDD.",
    )
    result = await coach.whisper(ctx)
    assert result is not None

    call_args = mock_client.aio.models.generate_content.call_args
    prompt_text = call_args.kwargs["contents"][0]["parts"][0]["text"]
    assert "We use TDD" in prompt_text
```

- [ ] **Step 2: Run tests to see them fail**

```bash
cd expert-agents/dev-coach && pytest tests/test_whisper.py -v
```
Expected: new tests fail — `_generate` not defined, `wiki_context` not in prompt

- [ ] **Step 3: Update `dev_coach/main.py`**

Replace `expert-agents/dev-coach/dev_coach/main.py` with:

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
{wiki_context}
Recent conversation:
{history_tail}

Your suggestion (or NO_WHISPER):"""


class DevCoach(ExpertAgentBase):
    def __init__(self) -> None:
        model = os.environ.get("DEV_COACH_MODEL", "gemini-2.0-flash")
        super().__init__(model=model)
        self._client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

    async def _generate(self, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )
        return (response.text or "").strip()

    async def whisper(self, context: WhisperContext) -> WhisperResponse | None:
        if len(context.history) < 2:
            return None

        wiki_section = (
            f"\nRelevant wiki context:\n{context.wiki_context}\n"
            if context.wiki_context
            else ""
        )
        prompt = _PROMPT.format(
            goals="; ".join(context.goals) or "None",
            project_map="; ".join(context.project_map) or "None",
            wiki_context=wiki_section,
            history_tail="\n".join(context.history),
        )

        text = await self._generate(prompt)
        if text.startswith("NO_WHISPER"):
            return None

        return WhisperResponse(source="DevCoach", message=text, confidence=0.8)


_coach = DevCoach()
app = _coach.app
```

- [ ] **Step 4: Create `wiki_schema.md`**

Create `expert-agents/dev-coach/wiki_schema.md`:

```markdown
# Dev Coach Wiki Schema

This wiki accumulates knowledge about the developer's technical work across sessions.

## What to Track

- **Technical decisions** — architectural choices, library selections, tradeoffs considered
- **Recurring problems** — issues that come up repeatedly and how they were resolved
- **Patterns observed** — coding patterns, testing approaches, workflows the developer favours
- **Tech choices** — frameworks, tools, languages, and why they were chosen

## What NOT to Track

- Generic advice or coaching not specific to this developer's work
- Temporary context that won't be relevant in future sessions
- Session mechanics (connection issues, audio problems, etc.)

## Page Naming Conventions

- `decisions-<topic>.md` — for architectural or technical decisions
- `patterns-<topic>.md` — for observed coding or workflow patterns
- `problems-<topic>.md` — for recurring issues and resolutions
- `tech-<name>.md` — for notes on a specific tool or library

## Index Entry Format

Each entry in index.md should be:
`- [[filename.md]] — one-line summary (last updated: YYYY-MM-DD)`

## Page Format

Each page should start with a `# Title` and include:
- A brief summary
- Key details with dates where relevant
- Cross-references to related pages using `[[filename.md]]`
```

- [ ] **Step 5: Update `Dockerfile`**

In `expert-agents/dev-coach/Dockerfile`, add a `COPY` line for the schema:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY expert-agents/base/ expert-agents/base/
COPY expert-agents/dev-coach/ expert-agents/dev-coach/
RUN pip install -e "expert-agents/base/" -e "expert-agents/dev-coach/[dev]"
COPY expert-agents/dev-coach/wiki_schema.md /app/wiki_schema.md
HEALTHCHECK --interval=30s --timeout=5s CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8082/health')"
CMD ["uvicorn", "dev_coach.main:app", "--host", "0.0.0.0", "--port", "8082"]
```

- [ ] **Step 6: Run all dev-coach tests**

```bash
cd expert-agents/dev-coach && pytest tests/ -v
```
Expected: all tests pass (the existing tests plus the two new ones)

- [ ] **Step 7: Run all base tests to check nothing regressed**

```bash
cd expert-agents/base && pytest tests/ -v
```
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add expert-agents/dev-coach/dev_coach/main.py \
        expert-agents/dev-coach/wiki_schema.md \
        expert-agents/dev-coach/Dockerfile \
        expert-agents/dev-coach/tests/test_whisper.py
git commit -m "feat: implement _generate and wiki context in DevCoach; add wiki_schema.md"
```

---

## Task 4: Orchestrator — Session Close Handler + Endpoint

**Files:**
- Create: `orchestrator/orchestrator/session_handler.py`
- Create: `orchestrator/tests/test_session_handler.py`
- Modify: `orchestrator/orchestrator/main.py`

- [ ] **Step 1: Write the failing tests**

Create `orchestrator/tests/test_session_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from orchestrator.agent_registry import AgentConfig
from orchestrator.session_handler import handle_session_close


def _event():
    return {"session_id": "s1", "transcript": "User: hello\nAssistant: hi"}


def _monitor(healthy=True):
    m = MagicMock()
    m.is_healthy.return_value = healthy
    return m


def _agent():
    return AgentConfig(name="DevCoach", url="http://dev-coach:8082")


@pytest.mark.asyncio
async def test_fans_out_ingest_to_healthy_agents():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 202
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        await handle_session_close(_event(), [_agent()], _monitor(), timeout=2)

    assert any("dev-coach" in u and "ingest" in u for u in posted)


@pytest.mark.asyncio
async def test_skips_unhealthy_agents():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 202
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        await handle_session_close(_event(), [_agent()], _monitor(healthy=False), timeout=2)

    assert len(posted) == 0


@pytest.mark.asyncio
async def test_logs_and_continues_on_agent_error():
    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        call_count += 1
        raise Exception("agent down")

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        # should not raise
        await handle_session_close(_event(), [_agent()], _monitor(), timeout=2)

    assert call_count == 1


@pytest.mark.asyncio
async def test_logs_non_202_response():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 500
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        await handle_session_close(_event(), [_agent()], _monitor(), timeout=2)

    assert len(posted) == 1  # still attempted, just logged the error
```

- [ ] **Step 2: Run tests to see them fail**

```bash
cd orchestrator && pytest tests/test_session_handler.py -v
```
Expected: `ImportError: cannot import name 'handle_session_close'`

- [ ] **Step 3: Create `session_handler.py`**

Create `orchestrator/orchestrator/session_handler.py`:

```python
import asyncio
import logging
import httpx
from orchestrator.agent_registry import AgentConfig
from orchestrator.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)


async def handle_session_close(
    close_event: dict,
    agents: list[AgentConfig],
    health_monitor: HealthMonitor,
    timeout: int,
) -> None:
    healthy = [a for a in agents if health_monitor.is_healthy(a.name)]
    if not healthy:
        logger.warning(
            "No healthy agents for session close session=%s", close_event["session_id"]
        )
        return

    await asyncio.gather(
        *[_call_ingest(a, close_event, timeout) for a in healthy],
        return_exceptions=True,
    )


async def _call_ingest(agent: AgentConfig, close_event: dict, timeout: int) -> None:
    payload = {
        "session_id": close_event["session_id"],
        "transcript": close_event["transcript"],
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{agent.url}/ingest", json=payload, timeout=float(timeout)
            )
            if resp.status_code != 202:
                logger.warning(
                    "Agent %s /ingest returned %s session=%s",
                    agent.name,
                    resp.status_code,
                    close_event["session_id"],
                )
        except asyncio.TimeoutError:
            logger.warning(
                "Agent %s /ingest timed out session=%s",
                agent.name,
                close_event["session_id"],
            )
        except Exception as exc:
            logger.warning(
                "Agent %s /ingest error session=%s: %s",
                agent.name,
                close_event["session_id"],
                exc,
            )
```

- [ ] **Step 4: Add the endpoint to `orchestrator/main.py`**

Replace `orchestrator/orchestrator/main.py` with:

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from orchestrator.agent_registry import load_registry
from orchestrator.health_monitor import HealthMonitor
from orchestrator.turn_handler import handle_turn
from orchestrator.session_handler import handle_session_close

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


@app.post("/turns", status_code=200)
async def receive_turn(body: dict):
    if not _ROUTER_SERVICE_URL:
        raise HTTPException(status_code=503, detail="ROUTER_SERVICE_URL not configured")
    await handle_turn(
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
```

- [ ] **Step 5: Run all orchestrator tests**

```bash
cd orchestrator && pytest tests/ -v
```
Expected: all tests pass (existing + new session_handler tests)

- [ ] **Step 6: Commit**

```bash
git add orchestrator/orchestrator/session_handler.py \
        orchestrator/orchestrator/main.py \
        orchestrator/tests/test_session_handler.py
git commit -m "feat: add session close handler and /sessions/{id}/close endpoint to orchestrator"
```

---

## Task 5: Router-Service — Session Close Notification

**Files:**
- Modify: `router-service/router_service/live_session.py`
- Modify: `router-service/tests/test_live_session.py`

- [ ] **Step 1: Write the failing test**

Append to `router-service/tests/test_live_session.py`:

```python
@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_close_notifies_orchestrator_with_transcript(mock_httpx, mock_genai, tmp_path):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    posted = []

    async def mock_post(url, **kwargs):
        posted.append((url, kwargs))
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_http_client = AsyncMock()
    mock_http_client.post = mock_post
    mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)

    session = _session(transcript_output_dir=str(tmp_path))
    session._gemini_session = mock_session
    session._gemini_cm = MagicMock()
    session._gemini_cm.__aexit__ = AsyncMock(return_value=None)
    session._history = ["User: hello", "Assistant: hi"]

    await session.close()

    session_close_calls = [
        (url, kw) for url, kw in posted
        if "sessions" in url and "close" in url
    ]
    assert len(session_close_calls) == 1
    url, kwargs = session_close_calls[0]
    assert "test-id" in url
    assert "transcript" in kwargs["json"]
    assert "User: hello" in kwargs["json"]["transcript"]


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_close_succeeds_even_if_orchestrator_unreachable(mock_httpx, mock_genai, tmp_path):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    async def mock_post(url, **kwargs):
        raise Exception("connection refused")

    mock_http_client = AsyncMock()
    mock_http_client.post = mock_post
    mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)

    session = _session(transcript_output_dir=str(tmp_path))
    session._gemini_session = mock_session
    session._gemini_cm = MagicMock()
    session._gemini_cm.__aexit__ = AsyncMock(return_value=None)
    session._history = ["User: hello"]

    # should not raise
    await session.close()
    assert (tmp_path / "test-id.md").exists()
```

- [ ] **Step 2: Run tests to see them fail**

```bash
cd router-service && pytest tests/test_live_session.py -v
```
Expected: two new tests fail — orchestrator not called on close

- [ ] **Step 3: Update `live_session.py`**

In `router-service/router_service/live_session.py`, update the `close` method to add the orchestrator notification after writing the transcript:

```python
async def close(self) -> None:
    if self._closed:
        return
    self._closed = True
    for task in self._tasks:
        task.cancel()
    await asyncio.gather(*self._tasks, return_exceptions=True)
    if self._gemini_cm:
        try:
            await self._gemini_cm.__aexit__(None, None, None)
        except RuntimeError:
            pass
        finally:
            self._gemini_cm = None
    transcript = ""
    try:
        os.makedirs(self._transcript_output_dir, exist_ok=True)
        TranscriptWriter(self._transcript_output_dir).write_transcript(
            self.session_id, self._history
        )
        transcript = "\n".join(self._history)
    except Exception as exc:
        logger.error("Failed to write transcript for session %s: %s", self.session_id, exc)
    await self._post_session_close(transcript)

async def _post_session_close(self, transcript: str) -> None:
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{self._orchestrator_url}/sessions/{self.session_id}/close",
                json={"transcript": transcript},
                timeout=5.0,
            )
        except Exception as exc:
            logger.warning(
                "Failed to notify orchestrator of session close session=%s: %s",
                self.session_id,
                exc,
            )
```

- [ ] **Step 4: Run all router-service tests**

```bash
cd router-service && pytest tests/ -v
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add router-service/router_service/live_session.py \
        router-service/tests/test_live_session.py
git commit -m "feat: notify orchestrator of session close with transcript"
```

---

## Task 6: Docker Compose — Wiki Volume Mount

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add volume mount to `docker-compose.yml`**

In `docker-compose.yml`, add a `volumes` entry to the `dev-coach` service:

```yaml
  dev-coach:
    build:
      context: .
      dockerfile: expert-agents/dev-coach/Dockerfile
    ports:
      - "8082:8082"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DEV_COACH_MODEL=${DEV_COACH_MODEL:-gemini-2.0-flash}
    volumes:
      - ./expert-agents/dev-coach/wiki:/app/wiki
```

- [ ] **Step 2: Create the wiki directory so it is tracked by git**

```bash
mkdir -p expert-agents/dev-coach/wiki
touch expert-agents/dev-coach/wiki/.gitkeep
```

- [ ] **Step 3: Add wiki contents to .gitignore**

In `expert-agents/dev-coach/.gitignore` (or create it), add:

```
wiki/index.md
wiki/log.md
wiki/pages/
```

This keeps the `.gitkeep` so the directory is tracked but not the generated wiki content.

- [ ] **Step 4: Verify full test suite still passes**

```bash
cd expert-agents/base && pytest && cd ../dev-coach && pytest && cd ../../orchestrator && pytest && cd ../router-service && pytest
```
Expected: all tests pass across all packages

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml \
        expert-agents/dev-coach/wiki/.gitkeep \
        expert-agents/dev-coach/.gitignore
git commit -m "chore: add wiki volume mount and gitignore for dev-coach"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| `WikiManager` with read/write/list/log/scaffold | Task 1 |
| `parse_ingest_response` | Task 1 |
| `_generate` abstract method | Task 2 |
| `wiki_context` on `WhisperContext` | Task 2 |
| `/ingest` endpoint returns 202 | Task 2 |
| `_ingest_session` default (LLM + schema → pages + index + log) | Task 2 |
| `_query_wiki` (index → relevant pages → context string) | Task 2 |
| `_query_wiki` wired into `/whisper` | Task 2 |
| `_safe_ingest` catches + logs failures, appends failed-ingest to log | Task 2 |
| DevCoach `_generate` | Task 3 |
| DevCoach uses `wiki_context` in whisper prompt | Task 3 |
| `wiki_schema.md` for dev-coach | Task 3 |
| Dockerfile copies `wiki_schema.md` to `/app/wiki_schema.md` | Task 3 |
| Orchestrator `handle_session_close` fan-out | Task 4 |
| Orchestrator `POST /sessions/{id}/close` endpoint | Task 4 |
| Orchestrator failures per-agent logged, not propagated | Task 4 |
| Router-service notifies orchestrator on close | Task 5 |
| Close notification failure does not break session close | Task 5 |
| Close notification logged on failure | Task 5 |
| Docker compose wiki volume mount | Task 6 |
| Wiki directory scaffolded on first startup | Task 2 (`scaffold_if_empty` called in `__init__`) |
| Atomic page writes | Task 1 |

All spec requirements are covered.
