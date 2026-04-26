# MVP Vertical Slice Design

**Date:** 2026-04-25
**Status:** Approved

## 1. Overview

This spec defines the MVP for the Voice-First Development Partner — a browser-based voice interface backed by three independently deployable services. The evaluation target is dog-fooding: conducting development sessions using the system itself.

**Success criterion:** Open a browser, start a session, have a voice conversation with the Router facilitated by Gemini Live, and receive contextually relevant coaching whispers from the Dev Coach expert agent.

**What this is not:** a production deployment, a polished UI, or a fully-featured Orchestrator. It is the minimum vertical slice needed to evaluate whether the system concept works.

---

## 2. Monorepo Structure

All services live under the `gcsb/` repo root. Each service is independently buildable and testable.

```
gcsb/
├── docs/
│   ├── specs/                          # system-wide architecture specs
│   └── superpowers/specs/              # brainstormed design docs (this file)
├── voice-router/                       # existing Router Core (Python package)
│   ├── src/router/
│   │   ├── behavioral_contract.py      # NEW: system prompt extracted here
│   │   ├── facilitator.py              # unchanged
│   │   ├── router.py                   # unchanged
│   │   ├── state_store.py              # unchanged
│   │   └── transcript_writer.py        # unchanged
│   ├── tests/                          # existing
│   ├── pyproject.toml                  # existing
│   └── Dockerfile                      # NEW: runs pytest; not a server
├── router-service/                     # NEW: FastAPI server + browser client
│   ├── src/router_service/
│   │   ├── main.py
│   │   ├── live_session.py
│   │   ├── session_registry.py
│   │   └── client/
│   │       ├── index.html
│   │       ├── audio.js
│   │       └── session.js
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── orchestrator/                       # NEW: stub with config-driven agent registry
│   ├── src/orchestrator/
│   │   ├── main.py
│   │   ├── agent_registry.py
│   │   └── agents.yaml
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── expert-agents/
│   ├── base/                           # NEW: Python ABC for expert agents
│   │   ├── src/expert_agent_base/
│   │   │   └── base.py
│   │   └── pyproject.toml
│   └── dev-coach/                      # NEW: LLM-backed coaching agent
│       ├── src/dev_coach/
│       │   └── main.py
│       ├── tests/
│       ├── Dockerfile
│       └── pyproject.toml
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci.yml
```

**Package dependency graph:**

```
voice-router  ──────────────────→  router-service
expert-agents/base  ────────────→  dev-coach
orchestrator  (no local package dependencies)
```

`voice-router` and `expert-agents/base` are installed as local path dependencies in their consumers' `pyproject.toml`. No package registry needed.

---

## 3. Router Service & Gemini Live API Integration

### 3.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Serve browser client (`index.html`) |
| `POST` | `/sessions` | Create session; body: `{project_map: [str], goals: [str]}` → `{session_id: str}` |
| `WS` | `/sessions/{id}/audio` | Browser audio stream (bidirectional) |
| `POST` | `/sessions/{id}/whisper` | Receive whisper from Orchestrator |
| `DELETE` | `/sessions/{id}` | Close session |
| `GET` | `/health` | `{"status": "ok"}` |

### 3.2 Behavioral Contract

The existing `Facilitator` system prompt is extracted from `facilitator.py` into `voice-router/src/router/behavioral_contract.py` — a new module exporting a single string constant `BEHAVIORAL_CONTRACT`. The `Facilitator` imports it from there; `LiveSession` imports it from the same place. No changes to existing classes.

`behavioral_contract.py` gains one addition: a clause instructing Gemini how to handle whisper injections:

> "You will occasionally receive messages prefixed with `[WHISPER from …]:`. Treat these as private suggestions from domain experts. Weave the insight naturally into your next response — do not quote it directly or attribute it by name."

### 3.3 `LiveSession`

Manages a single Gemini Live API WebSocket session.

**Setup (on `POST /sessions`):**

Connects to the Gemini Live API WSS endpoint and sends `BidiGenerateContentSetup`:

```json
{
  "config": {
    "model": "<LIVE_API_MODEL env var>",
    "response_modalities": ["AUDIO"],
    "input_audio_transcription": {},
    "output_audio_transcription": {},
    "system_instruction": {
      "parts": [{"text": "<BEHAVIORAL_CONTRACT>"}]
    }
  }
}
```

Both `input_audio_transcription` and `output_audio_transcription` are enabled from day one. Gemini transcribes both sides internally at no additional latency cost. Transcripts are accessed via `serverContent.input_transcription.text` and `serverContent.output_transcription.text` in server messages.

Immediately after setup, project map and goals are injected as a `realtimeInput.text` message before the browser WebSocket connects, priming Gemini with session context.

**During the session — three concurrent async tasks:**

1. **Browser → Gemini**: reads raw 16-bit PCM binary frames from the browser WebSocket, base64-encodes them, forwards as `realtimeInput.audio` with `mimeType: audio/pcm;rate=16000`.

2. **Gemini → Browser**: reads server messages from the Gemini Live WebSocket. Audio chunks are decoded from base64 and forwarded as binary frames to the browser. Input and output transcription fragments are accumulated turn by turn into a rolling history list.

3. **Whisper drain**: watches an `asyncio.Queue`. When a whisper arrives (via `POST /sessions/{id}/whisper`), sends a `realtimeInput.text` message formatted as `[WHISPER from {source}]: {message}`.

**Turn events:**

When the Gemini server message contains `serverContent.turnComplete: true`, the accumulated transcript for that turn is captured and a turn event is posted to the Orchestrator — fire-and-forget. A failed POST is logged but never propagates to the session.

Turn event payload:

```json
{
  "session_id": "string",
  "history_tail": ["User: ...", "Assistant: ...", "User: ..."],
  "goals": ["string"],
  "project_map": ["string"]
}
```

`history_tail` is a rolling window of the last 10 interleaved user and assistant transcript lines (both sides, thanks to the transcription flags). Window size is configurable via `HISTORY_TAIL_LENGTH` env var. This is the most important observability data in the system.

### 3.4 Audio Format

| Direction | Format |
|---|---|
| Browser → Router Service | Raw 16-bit PCM, 16kHz, little-endian (browser resamples before sending) |
| Router Service → Gemini | Base64-encoded, `audio/pcm;rate=16000` |
| Gemini → Router Service | Base64-encoded 24kHz PCM |
| Router Service → Browser | Raw bytes decoded from base64 |

The browser handles downsampling to 16kHz and playback of 24kHz PCM. The server never touches sample rates.

### 3.5 Session Registry

In-memory `Dict[str, LiveSession]`. Session IDs are UUIDs generated at `POST /sessions`. Concurrency is handled by asyncio's single event loop — no locking needed.

### 3.6 Error Handling

- Gemini Live fails to connect at session start → 503, no registry entry created
- Browser WebSocket disconnects → `LiveSession.close()` tears down the Gemini connection, removes registry entry
- Whisper POST to unknown session → 404
- Orchestrator turn event POST fails → log warning, session continues unaffected

---

## 4. Orchestrator

### 4.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/turns` | Receive turn event from Router Service |
| `GET` | `/health` | `{"status": "ok"}` |

### 4.2 Turn Handling Flow

1. Receive turn event: `{session_id, history_tail, goals, project_map}`
2. Filter agent registry to currently-healthy agents
3. Call each healthy agent's `POST /whisper` concurrently (`asyncio.gather`) with the full context
4. Collect responses: 200 → has whisper, 204 → skip, error/timeout → log and skip
5. Drop whispers below `confidence_threshold`
6. For each passing whisper: `POST /sessions/{session_id}/whisper` to the Router Service — fire-and-forget, failures are logged but not retried

Agent calls use a configurable timeout (default 2 seconds). A slow agent is worse than a silent one given the narrow window between turn completion and the next user utterance. Whispers that arrive late are queued at the Router Service and injected at the next turn boundary.

### 4.3 Agent Registry (`agents.yaml`)

```yaml
confidence_threshold: 0.5
agent_timeout_seconds: 2
agents:
  - name: "DevCoach"
    url: "http://dev-coach:8082"
```

This is the only file edited to add or remove an expert agent. No code changes required. The registry is loaded at startup.

### 4.4 Health Monitoring

A background `asyncio` task polls each registered agent's `GET /health` every 30 seconds. Agents that fail to respond are removed from active rotation; they are re-added automatically when they recover. On each turn event, only healthy agents are called.

### 4.5 Error Handling

- Agent call exceeds timeout → log, skip; agent remains healthy (timeouts are transient)
- Agent returns 5xx → log, skip, mark unhealthy
- Router Service whisper POST fails → log, no retry (session may have ended between the turn event and the whisper POST — this is a normal race)
- All agents unhealthy or registry empty → log warning, return 200 with nothing forwarded

### 4.6 Future Work: Dynamic Agent Registry

The MVP loads `agents.yaml` at startup. Two planned evolution points:

- **Hot-reload** (trivial): watch `agents.yaml` for changes, reload without restart.
- **Self-registration** (spec-aligned): a `POST /agents` endpoint where an agent announces itself on startup with its URL, name, and description. The Orchestrator adds it to the live registry; health polling manages its lifecycle. This is the pattern that enables spinning agents up and down based on conversation context, and is a prerequisite for the Option C (event-driven) migration.

---

## 5. Expert Agent Base & Dev Coach

### 5.1 `expert-agents/base` — Python ABC

All Python expert agents extend a shared abstract base class. The base class defines:

- Abstract method: `whisper(context: WhisperContext) -> WhisperResponse | None`
- Concrete: FastAPI app setup, `POST /whisper` route (calls `whisper()`, returns 200 or 204), `GET /health` route
- Constructor parameter: `model` — the LLM model identifier, injected by each subclass

Adding a new Python expert agent means subclassing this base, implementing `whisper()`, and passing a model to `super().__init__()`. The HTTP plumbing, request validation, and health endpoint are inherited.

**Future work:** Configurable model selection is a hard requirement before any comparative evaluation. The `model` parameter on the ABC is where this lands — injectable via environment variable or agent registry config so different agent instances can run different models side by side.

### 5.2 Dev Coach

Extends the ABC. Implements `whisper()` as follows:

**Early return:** if `history_tail` has fewer than 2 entries, return `None` (→ 204) without calling the LLM. There is not yet enough context to coach on.

**LLM call:** Gemini Flash (model injected via `DEV_COACH_MODEL` env var, defaulting to `gemini-2.0-flash`). Prompt:

```
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

Your suggestion (or NO_WHISPER):
```

**Response parsing:** if the response starts with `NO_WHISPER`, return `None` (→ 204). Otherwise return `WhisperResponse(source="DevCoach", message=<text>, confidence=0.8)`.

Fixed confidence of 0.8 is intentional for the MVP — every non-204 response is forwarded. Real confidence scoring is a future iteration.

**Error handling:**
- Gemini API call fails → raise exception (base class catches and returns 503)
- Gemini returns empty/null response (safety filter) → return `None` (→ 204)

**Tests:**

| Test | Mock | Expected |
|---|---|---|
| Useful context | Gemini returns a suggestion | 200 with message |
| Nothing to add | Gemini returns `NO_WHISPER` | 204 |
| Fewer than 2 history entries | No LLM call made | 204 |
| Gemini API error | Exception raised | 503 |
| `/health` | — | 200 `{"status": "ok"}` |

---

## 6. Browser Client

Static files served by the Router Service at `GET /`. No framework, no build step — plain HTML and two JavaScript files. Editable and reloadable in one second during active dog-fooding.

### `index.html`

- **Start Session** button (opens session init form)
- **End Session** button
- Status indicator: `Connecting / Listening / Speaking / Ended`
- Scrolling transcript pane — populated from `{"type": "transcript", ...}` control frames received over the WebSocket

### `session.js` — session lifecycle

- On Start: collects project map and goals from a brief form (two text fields), `POST /sessions`, stores `session_id`, opens `WS /sessions/{id}/audio`
- On End: `DELETE /sessions/{id}`, closes WebSocket
- Handles WebSocket close/error events, updates status indicator

### `audio.js` — audio pipeline

**Mic → server:**
- `getUserMedia({audio: true})`
- `AudioContext` + `AudioWorkletNode` for real-time PCM processing
- Worklet resamples to 16kHz and outputs raw 16-bit little-endian PCM chunks
- Chunks sent as binary WebSocket frames

**Server → speaker:**
- Receives binary frames (raw 24kHz PCM)
- Buffers and schedules playback via `AudioContext` to avoid gaps
- On receipt of `{"type": "interrupted"}` control frame: flushes playback buffer

### Control Frames

Binary frames carry audio; text frames carry JSON control messages.

| Direction | Frame | Purpose |
|---|---|---|
| Client → Server | `{"type": "end_turn"}` | Manual turn boundary (for testing; VAD handles normal flow) |
| Server → Client | `{"type": "interrupted"}` | Gemini interrupted; client flushes audio buffer |
| Server → Client | `{"type": "transcript", "role": "user"\|"assistant", "text": "..."}` | Live transcript line for display |

---

## 7. CI/CD & Local Development

### 7.1 Port Map

| Service | Port |
|---|---|
| Router Service | 8080 |
| Orchestrator | 8081 |
| Dev Coach | 8082 |

### 7.2 `docker-compose.yml`

`voice-router` and `expert-agents/base` are Python packages installed inside images — they are not running services and do not appear in docker-compose.

Build context is set to the repo root for all services so that Dockerfiles can access local package dependencies across service boundaries.

```yaml
services:
  router-service:
    build:
      context: .
      dockerfile: router-service/Dockerfile
    ports: ["8080:8080"]
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - ORCHESTRATOR_URL=http://orchestrator:8081
      - LIVE_API_MODEL=${LIVE_API_MODEL:-gemini-2.0-flash-live-001}
    depends_on:
      orchestrator:
        condition: service_healthy

  orchestrator:
    build:
      context: .
      dockerfile: orchestrator/Dockerfile
    ports: ["8081:8081"]
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
    ports: ["8082:8082"]
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DEV_COACH_MODEL=${DEV_COACH_MODEL:-gemini-2.0-flash}
```

`depends_on` with `condition: service_healthy` requires `HEALTHCHECK` to be defined in each service's Dockerfile (see §7.4).

### 7.3 `.env.example`

```bash
GEMINI_API_KEY=your_key_here
LIVE_API_MODEL=gemini-2.0-flash-live-001
DEV_COACH_MODEL=gemini-2.0-flash
CONFIDENCE_THRESHOLD=0.5
AGENT_TIMEOUT_SECONDS=2
HISTORY_TAIL_LENGTH=10
```

Copy to `.env`, fill in `GEMINI_API_KEY`, run `docker compose up`. That is the full local dev onboarding.

### 7.4 Dockerfile Pattern

**Three server services** (`router-service`, `orchestrator`, `dev-coach`) share this pattern:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
# Copy local package dependencies first (build context is repo root)
COPY voice-router/ voice-router/          # router-service only
COPY expert-agents/base/ expert-agents/base/  # dev-coach only
COPY <service>/ <service>/
RUN pip install -e "<service>/.[dev]"
HEALTHCHECK --interval=30s --timeout=5s CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:<port>/health')"
CMD ["uvicorn", "<module>:app", "--host", "0.0.0.0", "--port", "<port>"]
```

`curl` is not installed in `python:3.11-slim`. The `HEALTHCHECK` uses Python's standard library instead. The `HEALTHCHECK` is required for `depends_on: condition: service_healthy` in docker-compose.

**`voice-router` Dockerfile** is different — it is not a server and does not appear in docker-compose:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY voice-router/ voice-router/
RUN pip install -e "voice-router/.[dev]"
CMD ["pytest", "voice-router/tests/"]
```

Used in CI to verify the Router Core in a clean environment.

### 7.5 GitHub Actions (`ci.yml`)

One workflow, path-filtered jobs. Each job is independent — a failure in one does not block others.

| Job | Triggers on changes in | CI job dependency |
|---|---|---|
| `voice-router` | `voice-router/**` | — |
| `router-service` | `router-service/**`, `voice-router/**` | `voice-router` |
| `orchestrator` | `orchestrator/**` | — |
| `dev-coach` | `expert-agents/**` | — |

Each job: install dependencies → run pytest → docker build. A test failure stops the image build.

**Unit tests never touch external APIs.** All Gemini calls and inter-service HTTP calls are mocked. `GEMINI_API_KEY` is not available to unit test jobs — intentionally. A test that fails without the key has a missing mock.

Integration tests (real Gemini, real inter-service calls) are triggered via `workflow_dispatch` only. They are not a gate on every push. For the MVP, the integration test is: `docker compose up`, open browser, start a session, confirm whispers arrive.

---

## 8. Future Work

The following items are explicitly deferred but must not be forgotten:

| Item | Trigger |
|---|---|
| **Configurable model selection for expert agents** | Required before any comparative A/B/C evaluation. The `model` parameter on the ABC base class is the implementation point. |
| **Dynamic agent self-registration** (`POST /agents`) | Required before agents can be spun up/down based on conversation context. Pre-condition for Option C migration. |
| **Hot-reload of `agents.yaml`** | Low-effort improvement; do when restarting the Orchestrator to add an agent becomes friction. |
| **Real confidence scoring in Dev Coach** | Replace fixed 0.8 with a structured LLM output. |
| **User speech transcription in turn events** | Already included from day one via `input_audio_transcription`. No work deferred here. |
| **Telephony adapter (Twilio)** | Replaces browser client for phone-call interface; the Router Service WebSocket endpoint is already provider-agnostic. |
| **Authentication and security** | Deferred per system architecture spec; addressed once server layer is proven. |
| **Gemini vendor abstraction** | Deferred per system architecture spec. |
| **docker-compose.override.yml for hot reload** | Mount source volumes and enable `--reload` for faster inner dev loop. |

---

## 9. Out of Scope for MVP

- Real Orchestrator routing logic (LLM-assisted agent selection)
- Multiple expert agents
- Persistent session history or knowledge graph
- Web Speech API fallback
- Any telephony integration
- Authentication
