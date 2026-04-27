# CLAUDE.md

**Voice-First Development Partner** — a voice assistant that facilitates development sessions. The Router captures and structures developer thinking via voice; Expert Agents whisper contextual insights back through it. The Router is an Active Facilitator only — it never performs deep analysis or code generation.

## Services

| Directory | Role | Port |
|---|---|---|
| `voice-router/` | Router Core library (Python package, no server) | — |
| `router-service/` | FastAPI service + Gemini Live API + browser client | 8080 |
| `orchestrator/` | Turn handler, agent registry, health monitor | 8081 |
| `expert-agents/dev-coach/` | First expert agent (Gemini 2.0 Flash) | 8082 |
| `expert-agents/base/` | ExpertAgentBase ABC shared by all agents | — |

## Running the Full Stack

```bash
cp .env.example .env          # add GEMINI_API_KEY
docker compose up --build     # starts all three services
open http://localhost:8080    # browser client
```

Docker runtime: **Colima** (not Docker Desktop). Start with `colima start` if containers won't start.

## Running Tests

Each package has its own test suite — run from within the package directory:

```bash
cd voice-router && pytest
cd router-service && pytest
cd orchestrator && pytest
cd expert-agents/dev-coach && pytest
```

## Architecture

- Browser → `router-service` WebSocket → Gemini Live API (bidirectional audio)
- After each user turn: `router-service` POSTs to `orchestrator/turns`
- Orchestrator fans out to all healthy expert agents via `/whisper`
- Agents above confidence threshold → whisper injected into Gemini session as `[WHISPER from {source}]: {message}`
- Transcripts written to `./transcripts/` on session close

## Key Files

- `orchestrator/orchestrator/agents.yaml` — agent registry (add new agents here)
- `router-service/router_service/live_session.py` — Gemini Live API session management
- `voice-router/src/router/behavioral_contract.py` — Router's system prompt
- `docs/specs/2026-04-25-full-system-architecture-design.md` — full system design spec

## Gemini Live API Notes

- Model: `gemini-2.5-flash-native-audio-latest`
- `receive()` is per-turn — always wrap in `while True`
- Thinking mode disabled (`thinking_budget: 0`) — real-time voice doesn't benefit from it
- Audio in: PCM Int16 16kHz; audio out: PCM 24kHz via `response.data` (already decoded bytes)
