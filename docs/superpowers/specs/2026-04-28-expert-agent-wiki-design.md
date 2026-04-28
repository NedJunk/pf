# Expert Agent Wiki — Design Spec

**Date:** 2026-04-28
**Status:** Approved

## Overview

Expand `ExpertAgentBase` so every expert agent maintains a persistent, schema-driven wiki following the Karpathy LLM Wiki pattern. Each agent accumulates knowledge in its own wiki over time; the wiki is consulted at whisper time to enrich responses. A future USER PROFILE agent (backlog) will own a shared user knowledge wiki using the same base class capability.

## Scope

- Add `WikiManager` and wiki lifecycle to `expert-agents/base/`
- Add `POST /ingest` endpoint and `POST /sessions/{id}/close` orchestrator endpoint
- Instantiate wiki capability in `expert-agents/dev-coach/` as the first concrete agent
- Update `router-service` to notify orchestrator on session close

Out of scope: USER PROFILE agent, nested agent delegation, provider abstraction (noted in backlog).

---

## Components

### `WikiManager` (`expert-agents/base/`)

Plain file I/O class — no LLM awareness. Single responsibility: read and write the wiki directory.

```
read_index() -> str
read_page(name: str) -> str
write_page(name: str, content: str)   # atomic: write temp, rename
list_pages() -> list[str]
append_log(entry: str)
scaffold_if_empty()                   # creates index.md and log.md if absent
```

All writes are atomic (write to temp file, rename) to prevent half-written pages from a crashed ingest. `WikiManager` is a reusable primitive — no agent-specific logic belongs here.

### `ExpertAgentBase` additions

**New attributes (set at startup):**
- `_wiki: WikiManager` — instantiated from `WIKI_DIR` env var (default `/app/wiki`)
- `_wiki_schema: str` — loaded once at startup from the path given by `WIKI_SCHEMA_PATH` env var (default `/app/wiki_schema.md`). Each agent's `Dockerfile` copies its `wiki_schema.md` to `/app/wiki_schema.md` at build time.

**New endpoint:**
```
POST /ingest
Body: { session_id: str, transcript: str }
Response: 202 Accepted
```
Returns immediately. Wiki update runs as a FastAPI `BackgroundTask`.

**New methods:**
- `_ingest_session(session_id, transcript)` — default implementation: LLM reads transcript + schema, creates/updates pages, updates `index.md`, appends `log.md`. Agents may override.
- `_query_wiki(context: str) -> str` — reads `index.md`, asks LLM to identify relevant page names given the conversation context, reads those pages, returns a context string. Returns empty string on any failure (non-blocking).

**`/whisper` handler change:** calls `_query_wiki(context)` before building the Gemini prompt. Wiki context is injected between the system prompt and the conversation turn.

### Wiki Directory Structure

```
wiki/
  index.md        # catalog: [[page-link]] + one-line summary per entry
  log.md          # append-only: ## [YYYY-MM-DD] ingest | <session_id>
  pages/          # free-form LLM-generated markdown pages
```

`index.md` and `log.md` are scaffolded on first startup if absent.

### `wiki_schema.md`

Lives in each agent's package directory, copied into the container at build time. Defines:
- What knowledge the agent tracks
- Page naming conventions
- What each index entry should contain
- Any domain-specific ingest instructions

This is the sole customization point for agents — no Python override required for standard wiki behavior.

---

## Data Flow

### Post-Session Ingest

```
router-service
  → writes transcript to ./transcripts/ (unchanged)
  → POST /sessions/{session_id}/close { session_id, transcript }
      to orchestrator (fire-and-forget; failure logged, session close unaffected)

orchestrator /sessions/{id}/close
  → fans out POST /ingest { session_id, transcript }
      to all healthy agents (same pattern as /whisper dispatch)
  → per-agent failures logged and skipped

agent /ingest
  → returns 202 immediately
  → BackgroundTask: _ingest_session(session_id, transcript)
      → LLM reads transcript + wiki_schema
      → creates/updates pages in wiki/pages/
      → updates wiki/index.md
      → appends wiki/log.md
      → on failure: logs with session_id, appends failed-ingest entry to log.md
```

### Whisper-Time Query

```
orchestrator → POST /whisper { context } (unchanged)

agent
  → _query_wiki(context)
      → reads index.md
      → LLM identifies relevant page names
      → reads those pages
      → returns context string (empty string on failure, logged at WARNING)
  → builds Gemini prompt: system_prompt + wiki_schema + wiki_context + turn
  → returns whisper if above confidence threshold (unchanged)
```

---

## Orchestrator Changes

New endpoint: `POST /sessions/{session_id}/close`

- Accepts `{ session_id: str, transcript: str }`
- Fans out `POST /ingest` to all healthy agents using existing health registry
- Mirrors the `/whisper` dispatch pattern; failure per agent is logged and skipped, not propagated
- All failures (orchestrator unreachable from router-service, per-agent ingest failure) are logged with session ID and relevant HTTP status or exception

---

## Router-Service Changes

In `live_session.py`, on session close (after transcript is written):

- Fire-and-forget POST to `orchestrator/sessions/{session_id}/close` with transcript content
- Failure is caught, logged with session ID — does not affect session close path

---

## Dev-Coach Instantiation

`expert-agents/dev-coach/wiki_schema.md` — instructs the LLM to track:
- Technical decisions and their rationale
- Recurring problems and resolutions
- Architectural patterns observed
- Tech choices (libraries, approaches, tradeoffs noted)

`docker-compose.yml` volume mount:
```yaml
volumes:
  - ./expert-agents/dev-coach/wiki:/app/wiki
```

Wiki lives on the host filesystem — inspectable in Obsidian or any markdown tool, consistent with the `./transcripts/` convention.

No Python override needed in dev-coach. Schema file is the only customization.

---

## Error Handling

| Failure point | Behaviour |
|---|---|
| router-service → orchestrator POST fails | Logged with session ID; session close unaffected |
| Orchestrator → agent `/ingest` fails | Logged with session ID and status; other agents unaffected |
| `_ingest_session` background task fails | Caught, logged, appended to `log.md` as failed-ingest entry |
| `_query_wiki` fails (any reason) | Returns empty string; whisper proceeds without wiki context; logged at WARNING |
| Wiki file write interrupted | Atomic write (temp+rename) prevents partial pages |

---

## Testing

| Target | Approach |
|---|---|
| `WikiManager` | Unit tests with temp directory: read/write/list/log/scaffold operations |
| `_query_wiki()` | Pre-populated mock wiki + stubbed LLM; verify correct pages selected and returned |
| `_ingest_session()` | Integration test with transcript fixture + stubbed LLM; verify index and log updated |
| `POST /ingest` | Verify 202 returned immediately; background task queued |
| Orchestrator `/sessions/{id}/close` | Fan-out to mock agents using existing mock-agent pattern in orchestrator test suite |

---

## Backlog Items Noted

- **USER PROFILE agent** — a dedicated agent that owns the shared user knowledge wiki. Receives transcripts at session end via the same `/ingest` mechanism. Registered in `orchestrator/agents.yaml` like any other agent.
- **Provider abstraction** — wiki ingest and query currently use Gemini directly. The LLM/voice provider abstraction (Epic 3) should cover expert agent LLMs so neither the whisper nor the wiki maintenance path is hardcoded to Gemini.
