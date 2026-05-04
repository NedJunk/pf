# GEMINI.md — Project Handoff Context

This file is the equivalent of CLAUDE.md but written for Gemini. It contains everything you need to pick up this project with full context, including architectural decisions, current bugs, open backlog, and hard-won Gemini Live API gotchas.

---

## What This Is

A **voice-first development partner** — a voice assistant that facilitates development sessions. The developer talks through their work; expert agents whisper contextual insights back through the voice interface. The Router (named **Kai**) is an Active Facilitator only — it captures and structures thinking, never performs deep analysis or code generation.

Personal project, single user. Security is explicitly deferred.

---

## Services

| Directory | Role | Port |
|---|---|---|
| `voice-router/` | Router Core library (Python package, no server) | — |
| `router-service/` | FastAPI service + Gemini Live API + browser client | 8080 |
| `orchestrator/` | Turn handler, agent registry, health monitor | 8081 |
| `expert-agents/dev-coach/` | First expert agent (DevCoach) | 8082 |
| `expert-agents/base/` | ExpertAgentBase ABC shared by all agents | — |

---

## Running the Stack

```bash
cp .env.example .env          # add GEMINI_API_KEY
docker compose up --build     # starts all three services
open http://localhost:8080    # browser client
```

Docker runtime is **Colima** (not Docker Desktop). Start with `colima start` if containers won't launch.

If you see `docker-credential-desktop` errors, remove `"credsStore": "desktop"` from `~/.docker/config.json`. Install the docker-compose plugin separately: `brew install docker-compose` and symlink to `~/.docker/cli-plugins/`.

## Running Tests

```bash
cd voice-router && pytest
cd router-service && pytest
cd orchestrator && pytest
cd expert-agents/dev-coach && pytest
```

---

## Architecture

```
Browser ──WebSocket──▶ router-service ──▶ Gemini Live API (bidirectional audio)
                             │
                    POST /turns (after each user turn)
                             ▼
                        orchestrator
                             │
                  fan-out to all healthy agents
                             │
                      POST /whisper
                             ▼
                       dev-coach (+ future agents)
                             │
              confidence ≥ threshold → whisper injected
              into Gemini session as:
              [WHISPER from {source}]: {message}
```

- After each user turn, `router-service` POSTs to `orchestrator/turns`
- Orchestrator fans out to all healthy expert agents via `/whisper`
- Agents return `{source, message, confidence}` or 204 for no whisper
- Agents above confidence threshold → whisper injected into Gemini session via `send_client_content(turn_complete=False)`
- **Whisper delivery is fire-and-forget — no retry**
- Transcripts written to `./transcripts/` on session close

---

## Key Files

| File | Purpose |
|---|---|
| `orchestrator/orchestrator/agents.yaml` | Agent registry — add new agents here |
| `router-service/router_service/live_session.py` | Gemini Live API session management |
| `voice-router/src/router/behavioral_contract.py` | Kai's system prompt (Router identity + behavioral rules) |
| `docs/specs/2026-04-25-full-system-architecture-design.md` | Full system design spec |
| `docs/backlog.md` | Groomed product backlog (stable reference codes: BUG-xx, E{epic}-{item}) |
| `docs/architecture/c4-diagrams.md` | C4 diagrams — uses Mermaid C4 syntax, not rendered by GitHub |
| `scripts/dev-logs.sh` | Log retrieval: all services, filters health checks, supports `-n`/`-s`/`-f`/`-i` |
| `scripts/session-review.sh` | Compact session review bundle (transcript + log metrics) |

---

## Environment Variables

```bash
GEMINI_API_KEY=your_key_here
LIVE_API_MODEL=gemini-2.5-flash-native-audio-latest
DEV_COACH_MODEL=gemini-3-flash-preview
CONFIDENCE_THRESHOLD=0.5
AGENT_TIMEOUT_SECONDS=15
HISTORY_TAIL_LENGTH=10
```

**Note:** `docker-compose.yml` still defaults `DEV_COACH_MODEL=gemini-2.0-flash` — override via `.env`. The `LIVE_API_MODEL` default in compose is correct.

**Debug logging:** Set `LOG_LEVEL=DEBUG` on the `router-service` container to see `output_transcription`/`input_transcription` chunks and turn state. Useful for diagnosing BUG-12.

---

## Router Identity (Kai)

The voice agent is named **Kai**. Its behavioral contract (`behavioral_contract.py`) defines it as an Active Facilitator:
- Asks clarifying questions and captures thinking — does not generate code or perform deep analysis
- Never speaks, repeats, or acknowledges whisper content
- Never asks closing questions ("Is there anything else?")
- If asked its name, says "Kai" and continues — does not refer to itself as "the router"
- **Whisper handling:** Do not state insights directly. Use the silent whisper context to form better, more targeted questions for the user, but do not reveal that you received a whisper or state the insight as a fact.

---

## Current Backlog State (as of 2026-05-01)

### Now (priority order)

*Core Stability Milestone complete. Remaining work: routing efficiency.*

1. **E4-E — Design: agent routing improvements (Fix Fan-Out Problem)** — The orchestrator currently POSTs to every agent on every turn, which will not scale. Wire up the `select_expert` stub before adding more agents.

### Recently Resolved (2026-05-03)

- **BUG-12** — Transcript pollution from whisper injections — fixed: `_gemini_to_browser` drops `output_transcription` events whose text starts with `[WHISPER from`.
- **BUG-13** — Router opening with fallback phrase — fixed: `send_realtime_input` removed from `connect()`; behavioral contract updated with explicit "wait for user's first input" instruction.
- **BUG-15** — Prompt contradiction on whisper handling — fixed: behavioral contract now says "use the insight to ask a more targeted question"; `transcripts.py` ground truth updated to show silent incorporation.
- **BUG-03** — httpx client created per call — fixed: `AsyncClient` stored as `LiveSession._http_client`, reused across all turns, closed in `close()`.

### Deprioritized (Moved to Epic 4)

- **E4-H — Design: researcher agent** — second expert agent using Gemini Deep Research.
- **E4-L — Build: `/synthesize` endpoint on ExpertAgentBase**

### Milestone Map

| Milestone | Status | Focus |
|---|---|---|
| M0 | Done | Foundation |
| M1 | Done | Reliable Core |
| M2 | Next | Expert Ecosystem + Eval Foundation (E4-L, researcher agent E4-H/I/J/K, E1-A/B/C) |
| M3 | Future | Knowledge Layer Alpha |
| M4 | Future | Expert Ecosystem Expansion + smarter routing |
| M5 | Future | Telephony Alpha (Twilio, gated on M3) |
| M6 | Future | Provider Independence |

PM agent (E4-A/B/C/D) is **won't-do** — DevCoach covers the use case at current scale.

---

## Gemini Live API — Critical Gotchas

These were discovered through real debugging sessions and will save you hours.

### `receive()` is per-turn, not a persistent stream

Always call it inside `while True`. It breaks after `turn_complete` — the session stays alive but the generator ends. Without the loop the session closes after the first response.

```python
while True:
    async for response in session.receive():
        ...  # handle turn
```

### Multiple consecutive `turn_complete` events per logical response

Gemini can generate one conceptual response as 3 short audio turns, each with its own `turn_complete`. Coalesce consecutive model turns or the transcript fragments. See `_flush_output_buf()` in `live_session.py` — it scans backward past whisper entries before checking for a trailing assistant entry.

### `response.data` returns decoded bytes — do NOT base64-decode

`inline_data.data` from the SDK is already raw PCM bytes. Calling `base64.b64decode()` on it raises an exception on the first frame and silently kills the receive task.

### Disable thinking mode for real-time voice

`gemini-2.5-flash-native-audio-latest` has thinking enabled by default. It returns `thought` and `text` parts alongside audio, causing SDK warnings and session instability.

```python
"generation_config": {"thinking_config": {"thinking_budget": 0}}
```

### Whisper injection — use `send_client_content`, not `send_realtime_input`

`send_realtime_input(text=...)` is the VAD user-turn channel — Gemini treats any text sent there as a user utterance and immediately generates an audio response. Whispers must use:

```python
session.send_client_content(turns=..., turn_complete=False)
```

This suppresses audio but causes Gemini to emit `output_transcription` events for the injected content (BUG-12 — transcript pollution, unresolved).

### First whisper race condition (BUG-10 partial — check this)

The `send_client_content` injection path may not be active when the session's very first whisper arrives from the orchestrator. Session e98fae54 showed the first whisper going through a residual pre-fix code path and being vocalized. Whispers 2+ were silent. Check `live_session.py` initialization ordering if this recurs.

### `send_realtime_input(text=...)` triggers an immediate model response

Used in `connect()` to inject session context before the WebSocket opens. The model starts thinking/responding immediately — `receive()` will pick this up as the first turn.

### Verified models on this API key (2026-04-27)

- `gemini-2.5-flash-native-audio-latest` ← use this for the live voice session
- `gemini-2.5-flash-native-audio-preview-09-2025`
- `gemini-2.5-flash-native-audio-preview-12-2025`
- `gemini-3.1-flash-live-preview`
- `gemini-2.0-flash-live-001` is GONE from v1beta API

DevCoach uses `gemini-3-flash-preview` (or env override). The compose default `gemini-2.0-flash` is stale — always override via `.env`.

### Audio format

- Browser → server: PCM Int16, 16kHz, mono, sent as ArrayBuffer over WebSocket
- Server → Gemini: `types.Blob(data=bytes, mime_type="audio/pcm;rate=16000")`
- Gemini → browser: `response.data` returns raw PCM bytes at 24kHz

---

## Architecture Constraints — Don't Cross These

Two questions to ask before touching agent invocation:
1. Does this move routing logic into the Router (router-service)? It should live in the Orchestrator.
2. Does this create a direct agent→Router channel bypassing the Orchestrator? It should go through the Orchestrator.

Yes to either makes a future Option C (event-driven) migration harder.

`orchestrator/orchestrator/routing.py` has a `select_expert()` stub raising `NotImplementedError` that is never called — the orchestrator currently broadcasts directly in `turn_handler.py`. Either wire it up or tombstone it before building on E4-E (smarter routing).

`goals` and `project_map` in turn event payloads are always empty — the browser client never populates them. Relevant for future PM/researcher agent design.

---

## Working Norms

- **Backlog reference codes are stable** — use them when discussing work items (e.g. "BUG-12", "E4-L"). The user finds the codes less memorable than descriptions mid-session, but they are the canonical reference.
- **Prune the Now section** — move closed `[x]` items out before adding new ones.
- **Keep sessions focused** — one epic or one bug cluster per session. Commit at natural breakpoints.
- **Deferred items need explicit notes** — if something is considered but not done, record whether it's a "warmup task next session" or "moved down — not a priority."
- **Model selection:** use smaller/cheaper models for bounded subtasks (single file edits, config updates, writing one test). Reserve larger models for synthesis across many files.
