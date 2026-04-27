# CLAUDE.md — voice-router

This is the **Router Core library** — a Python package, not a runnable service. The runnable service that wraps it is `../router-service/`. The git repo root is one level up (`/Users/dg/Dev/gcsb`).

## Role in the System

`voice-router` is the brain of the Router Service. It owns:
- `BEHAVIORAL_CONTRACT` — the system prompt defining the Router's facilitation style
- `Facilitator` — wraps Gemini to generate facilitation responses
- `TranscriptWriter` — writes verbatim session transcripts to disk
- `Router` — thin facade sequencing facilitate → history → whisper handling

The **Router Service** (`../router-service/`) wraps this library with a FastAPI app, Gemini Live API session management, and a browser client.

## Commands

```bash
# First-time setup (from this directory)
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run a specific test
pytest tests/router/test_router.py::test_whispers_cleared_after_facilitate -v
```

## Key Constraints

- Router must NOT do deep analysis or code generation — it facilitates capture only
- No tech commitments beyond what's already chosen: Python 3.11+, Gemini 2.0 Flash, pytest
