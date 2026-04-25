# Voice-First Development Partner

A thin routing layer for capturing ideas through speech. The Router acts as an Active Facilitator — it asks clarifying questions, suggests how input connects to existing work, and voices context injected by background expert agents. It does not perform analysis or generate code.

## How it works

A session flows through three phases:

1. **Capture** — User speaks; the Router facilitates with clarifying questions
2. **Context** — Expert agents inject "whispers" via back-channel; the Router voices them naturally
3. **Artifacts** — On session end, a verbatim markdown transcript is written to disk

## Setup

Requires Python 3.11+.

```bash
cd pf/
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```python
from src.router.router import Router

router = Router(output_dir="transcripts/", gemini_api_key="your-key")

# Facilitate a turn
response = router.facilitate("I need to redesign the onboarding flow.")

# Inject a whisper from a background expert agent
router.inject_whisper("ProjectManager", "There's already a UX ticket open for this.")

# Continue the session — whisper will be voiced in this turn
response = router.facilitate("I'm thinking a three-step modal.")

# End the session and write transcript
transcript_path = router.end_session("session-2026-04-25")
```

## Running tests

```bash
pytest                                          # all tests
pytest tests/router/test_router.py -v          # one file
pytest tests/router/test_router.py::test_name  # one test
```

## Architecture

```
src/router/
  state_store.py        — session state (goals, history, whispers)
  facilitator.py        — Gemini 2.0 Flash integration + behavioral system prompt
  transcript_writer.py  — writes verbatim markdown transcripts
  router.py             — thin facade coordinating the above

tests/fixtures/
  transcripts.py        — example conversations defining correct Router behavior (TDD ground truth)
```

## Docs

- [Design spec](docs/superpowers/specs/2026-04-25-voice-development-partner-design.md)
- [Implementation plan — Router Core](docs/superpowers/plans/2026-04-25-voice-router-core.md)
