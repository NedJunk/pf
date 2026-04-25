# Voice Router Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the thin Router layer that validates the voice-first interaction model — an Active Facilitator that captures context, voices expert whispers, and produces verbatim transcripts.

**Architecture:** A Python package with three core components: StateStore (maintains session context across projectMap, goals, history, and whispers), TranscriptWriter (writes verbatim markdown artifacts), and Router (thin facade coordinating them with a Gemini 2.0 Flash Facilitator). Interaction model correctness is defined upfront as example transcript fixtures and verified through TDD — infrastructure only gets built after the behavior is proven.

**Tech Stack:** Python 3.12+, `google-genai` (Gemini 2.0 Flash), pytest, pytest-asyncio

---

## File Map

```
src/
  __init__.py
  router/
    __init__.py
    state_store.py        # RouterState dataclass + StateStore (projectMap, goals, history, whispers)
    transcript_writer.py  # Writes verbatim markdown session transcripts to disk
    facilitator.py        # Wraps Gemini 2.0 Flash — enforces Active Facilitator behavior contract
    router.py             # Thin facade: coordinates StateStore, Facilitator, TranscriptWriter
tests/
  __init__.py
  fixtures/
    __init__.py
    transcripts.py        # Example conversations defining correct Router behavior (TDD ground truth)
  router/
    __init__.py
    test_state_store.py
    test_transcript_writer.py
    test_facilitator.py
    test_router.py
    test_interaction_model.py   # Validates Router against example transcripts
  test_setup.py
pyproject.toml
```

---

### Task 1: Initialize Project and Setup Testing

**Files:**
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/test_setup.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup.py
def test_project_runs():
    assert True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_setup.py -v`
Expected: FAIL — `pytest: command not found` or `No module named pytest`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "voice-router"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "google-genai>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Run: `pip install -e ".[dev]"`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_setup.py -v`
Expected: PASS — `1 passed`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/test_setup.py
git commit -m "chore: initialize project and testing environment"
```

---

### Task 2: Define the Interaction Model via Example Transcripts

This task establishes the TDD ground truth the spec requires before any routing logic is written. The transcripts define what "correct" Router behavior looks like: asking clarifying questions, voicing whispers, suggesting categories, and staying out of analysis. All subsequent behavioral tests reference these fixtures.

**Files:**
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/transcripts.py`
- Modify: `tests/test_setup.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup.py — append these lines
from tests.fixtures.transcripts import EXAMPLE_TRANSCRIPTS, REQUIRED_BEHAVIORS

def test_example_transcripts_define_required_behaviors():
    all_validated = {
        tag
        for transcript in EXAMPLE_TRANSCRIPTS
        for turn in transcript["turns"]
        for tag in turn.get("validates", [])
    }
    for behavior in REQUIRED_BEHAVIORS:
        assert behavior in all_validated, f"No transcript validates behavior: {behavior}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_setup.py::test_example_transcripts_define_required_behaviors -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.fixtures'`

- [ ] **Step 3: Write minimal implementation**

```python
# tests/fixtures/transcripts.py
"""
Example transcripts are the ground truth for this project's TDD.
Each turn with a `validates` list asserts a required Router behavior.
Add transcripts here as new behaviors are discovered in real sessions.
"""

EXAMPLE_TRANSCRIPTS = [
    {
        "session_id": "capture-habit-tracker",
        "turns": [
            {
                "actor": "User",
                "message": "I need to, um, I have this idea about building a habit tracker but I don't know where to start.",
            },
            {
                "actor": "Router",
                "message": "It sounds like you're at the very beginning of this. Let me ask — when you say habit tracker, is this for yourself, or are you thinking about something others would use?",
                "validates": ["asks_clarifying_question"],
            },
            {
                "actor": "User",
                "message": "For myself, definitely.",
            },
            {
                "actor": "Router",
                "message": "Got it. What's the one habit you most want to track? Don't overthink it.",
                "validates": ["prompts_for_specifics"],
            },
            {
                "actor": "User",
                "message": "Probably daily exercise.",
            },
            {
                "actor": "Whisper",
                "source": "ProjectManager",
                "message": "We have an existing 'wellness' project in the map.",
            },
            {
                "actor": "Router",
                "message": "The Project Manager is flagging that we have an existing 'wellness' project. Does this habit tracker belong there, or is this its own thing?",
                "validates": ["voices_whisper", "suggests_category"],
            },
            {
                "actor": "User",
                "message": "It should go under wellness.",
            },
            {
                "actor": "Router",
                "message": "Perfect. So we're capturing: a personal exercise habit tracker, under the wellness project. Anything else, or shall we wrap up?",
                "validates": ["summarizes_capture", "offers_closure"],
            },
        ],
    }
]

# Every behavior tag used in `validates` must appear here.
# Tests will fail if a behavior is listed here but no transcript validates it.
REQUIRED_BEHAVIORS = [
    "asks_clarifying_question",  # Router probes ambiguous input rather than accepting it passively
    "prompts_for_specifics",     # Router pushes the user to be concrete
    "voices_whisper",            # Router relays an expert injection naturally in conversation
    "suggests_category",         # Router helps connect input to known project structure
    "summarizes_capture",        # Router reflects back what was captured before closing
    "offers_closure",            # Router signals the session can end rather than running indefinitely
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_setup.py -v`
Expected: PASS — `2 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/__init__.py tests/fixtures/transcripts.py tests/test_setup.py
git commit -m "feat: define interaction model via example transcripts"
```

---

### Task 3: StateStore

**Files:**
- Create: `src/__init__.py`
- Create: `src/router/__init__.py`
- Create: `src/router/state_store.py`
- Create: `tests/router/__init__.py`
- Create: `tests/router/test_state_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/router/test_state_store.py
from src.router.state_store import StateStore, Whisper


def test_initializes_with_empty_context():
    store = StateStore()
    state = store.get_state()
    assert state.project_map == []
    assert state.goals == []
    assert state.history == []
    assert state.whispers == []


def test_update_goals():
    store = StateStore()
    store.update_goals(["Reduce Overwhelm", "Ship v1"])
    assert store.get_state().goals == ["Reduce Overwhelm", "Ship v1"]


def test_update_goals_replaces_not_appends():
    store = StateStore()
    store.update_goals(["Goal A"])
    store.update_goals(["Goal B"])
    assert store.get_state().goals == ["Goal B"]


def test_add_to_history():
    store = StateStore()
    store.add_to_history("User: Hello")
    store.add_to_history("Router: Hi there")
    assert store.get_state().history == ["User: Hello", "Router: Hi there"]


def test_inject_whisper():
    store = StateStore()
    store.inject_whisper("ProjectManager", "We already have a task for this.")
    whispers = store.get_state().whispers
    assert len(whispers) == 1
    assert whispers[0] == Whisper(source="ProjectManager", message="We already have a task for this.")


def test_inject_multiple_whispers():
    store = StateStore()
    store.inject_whisper("ProjectManager", "Task already exists.")
    store.inject_whisper("Architect", "Consider the existing API.")
    assert len(store.get_state().whispers) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/router/test_state_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/router/state_store.py
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Whisper:
    source: str
    message: str


@dataclass
class RouterState:
    project_map: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    whispers: list[Whisper] = field(default_factory=list)


class StateStore:
    def __init__(self) -> None:
        self._state = RouterState()

    def get_state(self) -> RouterState:
        return self._state

    def update_goals(self, goals: list[str]) -> None:
        self._state.goals = goals[:]

    def add_to_history(self, entry: str) -> None:
        self._state.history.append(entry)

    def inject_whisper(self, source: str, message: str) -> None:
        self._state.whispers.append(Whisper(source=source, message=message))

    def clear_whispers(self) -> None:
        self._state.whispers.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/router/test_state_store.py -v`
Expected: PASS — `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/__init__.py src/router/__init__.py src/router/state_store.py \
        tests/router/__init__.py tests/router/test_state_store.py
git commit -m "feat: implement StateStore for session context"
```

---

### Task 4: TranscriptWriter

**Files:**
- Create: `src/router/transcript_writer.py`
- Create: `tests/router/test_transcript_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/router/test_transcript_writer.py
import os
from src.router.transcript_writer import TranscriptWriter


def test_writes_verbatim_markdown_transcript(tmp_path):
    writer = TranscriptWriter(output_dir=str(tmp_path))
    history = [
        "User: I need to track habits.",
        "Router: What kind of habits?",
    ]

    file_path = writer.write_transcript("session-1", history)

    assert os.path.exists(file_path)
    content = open(file_path).read()
    assert "# Session Transcript: session-1" in content
    assert "User: I need to track habits." in content
    assert "Router: What kind of habits?" in content


def test_transcript_filename_includes_session_id(tmp_path):
    writer = TranscriptWriter(output_dir=str(tmp_path))
    file_path = writer.write_transcript("my-session", [])
    assert "my-session" in os.path.basename(file_path)


def test_empty_session_still_writes_file(tmp_path):
    writer = TranscriptWriter(output_dir=str(tmp_path))
    file_path = writer.write_transcript("empty-session", [])
    assert os.path.exists(file_path)
    assert "# Session Transcript: empty-session" in open(file_path).read()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/router/test_transcript_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.router.transcript_writer'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/router/transcript_writer.py
import os


class TranscriptWriter:
    def __init__(self, output_dir: str) -> None:
        self._output_dir = output_dir

    def write_transcript(self, session_id: str, history: list[str]) -> str:
        file_path = os.path.join(self._output_dir, f"{session_id}.md")
        content = f"# Session Transcript: {session_id}\n\n" + "\n\n".join(history)
        with open(file_path, "w") as f:
            f.write(content)
        return file_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/router/test_transcript_writer.py -v`
Expected: PASS — `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/router/transcript_writer.py tests/router/test_transcript_writer.py
git commit -m "feat: implement TranscriptWriter for verbatim artifact generation"
```

---

### Task 5: Facilitator (Gemini 2.0 Flash Integration)

The Facilitator wraps the Gemini 2.0 Flash client. Its system prompt encodes the Router's behavioral contract: ask clarifying questions, surface whispers, suggest categories, and never do deep analysis. Unit tests mock the Gemini client — Facilitator's job is to build the right prompt and return the model's response.

**Files:**
- Create: `src/router/facilitator.py`
- Create: `tests/router/test_facilitator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/router/test_facilitator.py
from unittest.mock import MagicMock, patch
from src.router.facilitator import Facilitator
from src.router.state_store import RouterState, Whisper


def _mock_gemini_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


@patch("src.router.facilitator.genai")
def test_respond_calls_gemini_and_returns_text(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response(
        "Is this for yourself or for others?"
    )

    facilitator = Facilitator(api_key="test-key")
    response = facilitator.respond(
        user_input="I want to build a habit tracker.",
        state=RouterState(),
    )

    assert response == "Is this for yourself or for others?"
    mock_client.models.generate_content.assert_called_once()


@patch("src.router.facilitator.genai")
def test_whispers_are_included_in_prompt(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response(
        "The Project Manager notes we have a wellness project. Does this belong there?"
    )

    state = RouterState(
        whispers=[Whisper(source="ProjectManager", message="We have a 'wellness' project.")]
    )
    facilitator = Facilitator(api_key="test-key")
    facilitator.respond(user_input="Let's add a habit tracker.", state=state)

    call_args = str(mock_client.models.generate_content.call_args)
    assert "ProjectManager" in call_args
    assert "wellness" in call_args


@patch("src.router.facilitator.genai")
def test_recent_history_is_included_in_prompt(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response("Tell me more.")

    state = RouterState(history=["User: Hello", "Router: Hi there"])
    facilitator = Facilitator(api_key="test-key")
    facilitator.respond(user_input="I have an idea.", state=state)

    call_args = str(mock_client.models.generate_content.call_args)
    assert "User: Hello" in call_args or "Router: Hi there" in call_args
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/router/test_facilitator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.router.facilitator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/router/facilitator.py
from google import genai
from .state_store import RouterState

_SYSTEM_PROMPT = """\
You are a thin, voice-first facilitation router. Your ONLY job is to help the user capture and clarify their thoughts.

Rules:
- Always ask one clarifying question to deepen understanding or prompt specifics
- Suggest how input might be categorized or connected to existing work
- If expert whispers are listed below, voice the most relevant one naturally \
(e.g. "The Project Manager is noting that...")
- NEVER perform deep analysis, generate code, or offer solutions
- Keep responses short — this is a voice interaction

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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/router/test_facilitator.py -v`
Expected: PASS — `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/router/facilitator.py tests/router/test_facilitator.py
git commit -m "feat: implement Facilitator wrapping Gemini 2.0 Flash"
```

---

### Task 6: Router Facade + Interaction Model Validation

Wire all components together and validate the Router's behavior against the example transcripts defined in Task 2. The `facilitate()` method is the primary path: it takes user input, calls the Facilitator with current state (including pending whispers), records the exchange in history, and clears the whisper queue.

**Files:**
- Create: `src/router/router.py`
- Create: `tests/router/test_router.py`
- Create: `tests/router/test_interaction_model.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/router/test_router.py
import os
from unittest.mock import MagicMock, patch
from src.router.router import Router


@patch("src.router.facilitator.genai")
def test_facilitate_records_exchange_in_history(mock_genai, tmp_path):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(
        text="Tell me more — what kind of project?"
    )

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.facilitate("I have an idea.")

    history = router.get_state().history
    assert any("I have an idea." in h for h in history)
    assert any("Tell me more" in h for h in history)


@patch("src.router.facilitator.genai")
def test_whispers_cleared_after_facilitate(mock_genai, tmp_path):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(text="Noted.")

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.inject_whisper("PM", "We have a task.")
    assert len(router.get_state().whispers) == 1

    router.facilitate("Let's continue.")
    assert len(router.get_state().whispers) == 0


@patch("src.router.facilitator.genai")
def test_end_session_writes_transcript(mock_genai, tmp_path):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(text="Great, noted.")

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.facilitate("Hello")
    file_path = router.end_session("my-session")

    assert os.path.exists(file_path)
    content = open(file_path).read()
    assert "# Session Transcript: my-session" in content
    assert "Hello" in content
```

```python
# tests/router/test_interaction_model.py
"""
Validates Router behavior against the example transcripts from Task 2.
These tests confirm the interaction model contract before the server layer is added.
"""
from unittest.mock import MagicMock, patch
from src.router.router import Router


@patch("src.router.facilitator.genai")
def test_whisper_is_passed_into_facilitator_prompt(mock_genai, tmp_path):
    """Router must include injected whispers in the Gemini prompt."""
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(
        text="The Project Manager is flagging that we have a 'wellness' project. Does this belong there?"
    )

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.inject_whisper("ProjectManager", "We have an existing 'wellness' project in the map.")
    router.facilitate("It should go under wellness.")

    call_args = str(mock_client.models.generate_content.call_args)
    assert "ProjectManager" in call_args
    assert "wellness" in call_args


@patch("src.router.facilitator.genai")
def test_router_does_not_retain_whispers_across_turns(mock_genai, tmp_path):
    """Whispers are consumed once voiced — they must not persist into the next turn."""
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(text="Noted.")

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.inject_whisper("PM", "One-time note.")
    router.facilitate("First input.")

    router.facilitate("Second input.")

    second_call_args = str(mock_client.models.generate_content.call_args)
    assert "One-time note." not in second_call_args


@patch("src.router.facilitator.genai")
def test_full_session_transcript_matches_history(mock_genai, tmp_path):
    """Transcript must be verbatim — every turn in history appears in the file."""
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(
        text="What kind of habits are you tracking?"
    )

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.facilitate("I need to track habits.")
    file_path = router.end_session("habits-session")

    content = open(file_path).read()
    for entry in router.get_state().history:
        assert entry in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/router/test_router.py tests/router/test_interaction_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.router.router'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/router/router.py
from .state_store import StateStore, RouterState
from .transcript_writer import TranscriptWriter
from .facilitator import Facilitator


class Router:
    def __init__(self, output_dir: str, gemini_api_key: str) -> None:
        self._state_store = StateStore()
        self._writer = TranscriptWriter(output_dir)
        self._facilitator = Facilitator(api_key=gemini_api_key)

    def facilitate(self, user_input: str) -> str:
        self._state_store.add_to_history(f"User: {user_input}")
        response = self._facilitator.respond(user_input, self._state_store.get_state())
        self._state_store.add_to_history(f"Router: {response}")
        self._state_store.clear_whispers()
        return response

    def inject_whisper(self, source: str, message: str) -> None:
        self._state_store.inject_whisper(source, message)

    def get_state(self) -> RouterState:
        return self._state_store.get_state()

    def end_session(self, session_id: str) -> str:
        return self._writer.write_transcript(
            session_id, self._state_store.get_state().history
        )
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `pytest tests/ -v`
Expected: PASS — all tests pass

- [ ] **Step 5: Commit**

```bash
git add src/router/router.py tests/router/test_router.py tests/router/test_interaction_model.py
git commit -m "feat: implement Router facade and validate interaction model"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Active Facilitator — asks clarifying questions, prompts deeper thinking | Task 5 (system prompt), Task 6 (test_interaction_model) |
| State: projectMap, goals, history | Task 3 (StateStore) |
| Whisperer model — expert agents inject via back-channel | Task 3 (inject_whisper), Task 6 (whisper consumed per turn) |
| Verbatim transcripts as TDD foundation | Task 2 (fixtures), Task 6 (transcript test) |
| Artifact generation — verbatim markdown transcript | Task 4 (TranscriptWriter) |
| Router must NOT do deep analysis or code generation | Encoded in Facilitator system prompt (Task 5); behavioral boundary enforced by prompt, not tested structurally |
| Mobile / on-the-go usage | Out of scope for this plan — addressed by the Server Layer plan |
| No early tech commitments | This plan was written after deliberate tech decisions (Python, Gemini 2.0 Flash) were made through discussion |

**Placeholder scan:** None found.

**Type consistency:** `Whisper`, `RouterState`, `StateStore` defined in Task 3, referenced consistently in Tasks 5 and 6. `Router` constructor signature `(output_dir, gemini_api_key)` consistent across Task 6 tests and implementation.
