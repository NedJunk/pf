# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Voice-First Development Partner** — a thin Router that facilitates voice capture sessions. The Router is an Active Facilitator: it asks clarifying questions, suggests categories, voices expert "whispers", and never performs deep analysis or code generation. That boundary is a core design constraint, not an implementation detail.

The git repo root is one level up (`/Users/dg/Dev/gcsb`). This `voice-router/` directory is the project root — all commands run from here.

## Commands

```bash
# First-time setup
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/router/test_state_store.py -v

# Run a single test
pytest tests/router/test_router.py::test_whispers_cleared_after_facilitate -v
```

## Architecture

Four components with clean separation:

| File | Responsibility |
|---|---|
| `src/router/state_store.py` | `RouterState` (projectMap, goals, history, whispers) + `StateStore` + `Whisper` dataclass |
| `src/router/facilitator.py` | Wraps Gemini 2.0 Flash — builds prompt from state, enforces behavioral contract via system prompt |
| `src/router/transcript_writer.py` | Writes verbatim markdown session transcripts to disk |
| `src/router/router.py` | Thin facade: sequences `facilitate()` → records history → clears whispers → delegates to others |

**Whisper lifecycle:** injected via `Router.inject_whisper()` → passed into Gemini prompt on the next `facilitate()` call → cleared from state immediately after. Whispers are consumed once.

**TDD ground truth:** `tests/fixtures/transcripts.py` defines example conversations and `REQUIRED_BEHAVIORS`. The `validates` tags on transcript turns document intended behavior — they assert coverage but do not drive the Router against a live LLM. Integration tests against the real Gemini API are needed to verify runtime behavior.

## Key Constraints (from spec)

- Router must NOT do deep analysis or code generation — it facilitates capture only
- No tech commitments beyond what's already chosen: Python 3.11+, Gemini 2.0 Flash, pytest
- Specific audio APIs and server layer are deferred to the next plan (`docs/superpowers/plans/`)

## Known Debt (carry into Server Layer plan)

- `StateStore.get_state()` returns a live mutable reference — not safe for concurrent WebSocket handlers
- `TranscriptWriter` assumes `output_dir` exists; `Router.__init__` creates it via `os.makedirs`
- `Facilitator.respond()` returns `response.text` without handling `None` (Gemini safety filter blocks)
- History sent to Gemini is capped at last 6 entries — configurable window needed for long sessions
- `Facilitator._MODEL` is a class constant; should be constructor-injectable for the server layer
