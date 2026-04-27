# Expert Selection Evaluation Framework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pytest-based evaluation suite that scores orchestrator routing decisions against a human-labeled corpus of 19 seed cases covering three domain experts (TechnicalPM, ArtistManager, HealthCoach).

**Architecture:** A pure routing function stub in the orchestrator defines the interface the eval tests against. Labeled test cases live in JSON evalset files under `evals/evalsets/`. A pytest runner parametrizes over all cases and a conftest hook prints a per-expert precision/recall table after each run.

**Tech Stack:** Python 3.11, pytest, JSON (no new dependencies)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `orchestrator/orchestrator/routing.py` | Create | `select_expert()` stub — defines the routing interface |
| `evals/README.md` | Create | Labeling guide and transcript → evalset workflow |
| `evals/conftest.py` | Create | Loads results from tests, prints precision/recall summary |
| `evals/test_expert_selection.py` | Create | Parametrized pytest runner over all evalset cases |
| `evals/evalsets/tech-pm.evalset.json` | Create | 4 clear TechnicalPM cases + 1 negative |
| `evals/evalsets/artist-manager.evalset.json` | Create | 4 clear ArtistManager cases + 1 negative |
| `evals/evalsets/health-coach.evalset.json` | Create | 4 clear HealthCoach cases + 1 negative |
| `evals/evalsets/overlap.evalset.json` | Create | 4 overlap (ArtistManager vs HealthCoach) cases |

---

## Task 1: Routing Stub

**Files:**
- Create: `orchestrator/orchestrator/routing.py`

- [ ] **Step 1: Create the routing module**

```python
# orchestrator/orchestrator/routing.py
from typing import Optional


def select_expert(context: dict, registry: list[str]) -> Optional[str]:
    """Return the name of the most relevant expert, or None.

    Args:
        context: dict with keys history_tail (list[str]), goals (list[str]),
                 project_map (list[str])
        registry: list of registered expert names to choose from

    Raises NotImplementedError until routing logic is implemented (Epic 4).
    """
    raise NotImplementedError(
        "Routing logic not yet implemented. "
        "See docs/superpowers/specs/2026-04-27-expert-selection-eval-design.md"
    )
```

- [ ] **Step 2: Verify the module is importable**

```bash
cd orchestrator && pip install -e ".[dev]" -q && python3 -c "from orchestrator.routing import select_expert; print('ok')"
```

Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add orchestrator/orchestrator/routing.py
git commit -m "feat: add select_expert stub in orchestrator routing module"
```

---

## Task 2: Eval README

**Files:**
- Create: `evals/README.md`

- [ ] **Step 1: Create the README**

```markdown
# Expert Selection Eval Suite

Evaluates whether the orchestrator routes a conversation turn to the correct
domain expert. Ground truth is human judgment. This suite grows over time:
start with hand-written seed cases, promote interesting turns from real
session transcripts as they accumulate.

## Experts

| Name | Domain |
|---|---|
| `TechnicalPM` | This project — infrastructure, architecture, code decisions |
| `ArtistManager` | Singer-songwriter career — bookings, releases, touring, creative direction |
| `HealthCoach` | Health and wellness — physical health, mental health, habits, energy |

## Test Case Format

Cases live in `evalsets/` as `.evalset.json` files. Each file is a JSON
array of cases:

```json
[
  {
    "id": "tech-001",
    "description": "Deployment target decision",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I keep going back and forth on whether to use Railway or just run this on a VPS.",
        "Assistant: What's driving the hesitation — cost, control, or something else?",
        "User: Mostly control. I don't love the idea of being locked into another platform."
      ],
      "goals": ["Get the router service deployed somewhere stable"],
      "project_map": ["voice-first development partner — router service"]
    },
    "expected_expert": "TechnicalPM",
    "note": ""
  }
]
```

### Fields

| Field | Required | Notes |
|---|---|---|
| `id` | yes | `{abbrev}-{number}`: `tech-001`, `art-002`, `hlth-003`, `ovlp-001` |
| `description` | yes | One phrase — what's happening in the conversation |
| `category` | yes | `clear`, `overlap`, or `negative` |
| `context.history_tail` | yes | 2–5 turns immediately preceding the routing decision |
| `context.goals` | yes | Session goals as entered at start; use `[]` if none |
| `context.project_map` | yes | Session project map; use `[]` if none |
| `expected_expert` | yes | Agent name, or `null` for negative cases |
| `note` | overlap only | Required for `overlap` — one sentence explaining the judgment call |

### Categories

**`clear`** — only one expert could reasonably apply.

**`overlap`** — ArtistManager and HealthCoach both have a plausible claim.
Label the one more directly relevant to what the speaker is asking about
right now. A note is required.

**`negative`** — no expert injection needed. `expected_expert` is `null`.

## Adding Cases from Transcripts

1. Open a transcript from `transcripts/`
2. Find a turn where the routing decision is interesting
3. Copy the 2–5 preceding turns into `history_tail`
4. Choose the correct expert (or `null`)
5. Add to the appropriate evalset file and run `pytest evals/ -v`

## Running the Suite

```bash
# Install the orchestrator package first (once per environment)
pip install -e "orchestrator/"

# Run all eval cases
pytest evals/ -v
```

Output reports per-case pass/fail and a per-expert precision/recall table.
```

- [ ] **Step 2: Commit**

```bash
git add evals/README.md
git commit -m "docs: add eval suite README with labeling guide"
```

---

## Task 3: Eval Runner and Conftest

**Files:**
- Create: `evals/conftest.py`
- Create: `evals/test_expert_selection.py`

- [ ] **Step 1: Write the failing test first — create test_expert_selection.py**

```python
# evals/test_expert_selection.py
import json
import pytest
from pathlib import Path

from orchestrator.routing import select_expert

EVALSET_DIR = Path(__file__).parent / "evalsets"
REGISTRY = ["TechnicalPM", "ArtistManager", "HealthCoach"]


def load_cases():
    cases = []
    for path in sorted(EVALSET_DIR.glob("*.evalset.json")):
        for case in json.loads(path.read_text()):
            cases.append(case)
    return cases


@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c["id"])
def test_expert_selection(case, eval_results):
    result = select_expert(case["context"], REGISTRY)
    eval_results.append({"expected": case["expected_expert"], "actual": result})
    assert result == case["expected_expert"], (
        f"Expected {case['expected_expert']!r}, got {result!r} — {case['description']}"
    )
```

- [ ] **Step 2: Run — verify 0 tests collected (no evalset files yet)**

```bash
pytest evals/ -v
```

Expected output:
```
collected 0 items
```

- [ ] **Step 3: Create conftest.py with precision/recall summary**

```python
# evals/conftest.py
from collections import defaultdict
import pytest

_eval_results = []


@pytest.fixture
def eval_results():
    return _eval_results


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not _eval_results:
        return

    experts = sorted({r["expected"] for r in _eval_results if r["expected"] is not None})
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    correct = 0

    for r in _eval_results:
        expected, actual = r["expected"], r["actual"]
        if expected == actual:
            correct += 1
            if expected is not None:
                tp[expected] += 1
        else:
            if actual is not None:
                fp[actual] += 1
            if expected is not None:
                fn[expected] += 1

    terminalreporter.write_sep("─", "Expert Selection Results")
    terminalreporter.write_line(
        f"{'Expert':<20} {'Precision':>10} {'Recall':>8} {'F1':>6}"
    )
    terminalreporter.write_line("─" * 48)
    for expert in experts:
        p = tp[expert] / (tp[expert] + fp[expert]) if (tp[expert] + fp[expert]) > 0 else 0.0
        r = tp[expert] / (tp[expert] + fn[expert]) if (tp[expert] + fn[expert]) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        terminalreporter.write_line(f"{expert:<20} {p:>10.2f} {r:>8.2f} {f1:>6.2f}")
    terminalreporter.write_line("─" * 48)
    terminalreporter.write_line(
        f"Overall: {correct}/{len(_eval_results)} cases correct"
    )
```

- [ ] **Step 4: Run again — verify still 0 collected, no errors**

```bash
pytest evals/ -v
```

Expected output:
```
collected 0 items
```

- [ ] **Step 5: Commit**

```bash
git add evals/conftest.py evals/test_expert_selection.py
git commit -m "feat: add eval runner and precision/recall conftest"
```

---

## Task 4: TechnicalPM Evalset

**Files:**
- Create: `evals/evalsets/tech-pm.evalset.json`

- [ ] **Step 1: Create the evalset file**

```json
[
  {
    "id": "tech-001",
    "description": "Deployment target decision",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I keep going back and forth on whether to use Railway or just run this on a VPS.",
        "Assistant: What's driving the hesitation — cost, control, or something else?",
        "User: Mostly control. I don't love the idea of being locked into another platform."
      ],
      "goals": ["Get the router service deployed somewhere stable"],
      "project_map": ["voice-first development partner — router service"]
    },
    "expected_expert": "TechnicalPM",
    "note": ""
  },
  {
    "id": "tech-002",
    "description": "Abstracting the LLM provider",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I want to make it possible to swap out Gemini for a local model later.",
        "Assistant: That's worth doing carefully. Where would you put the abstraction boundary?",
        "User: I'm thinking somewhere in the router service but I'm not sure if that's the right layer."
      ],
      "goals": ["Design a provider abstraction layer for the voice model"],
      "project_map": ["voice-first development partner — router service"]
    },
    "expected_expert": "TechnicalPM",
    "note": ""
  },
  {
    "id": "tech-003",
    "description": "Debugging flaky CI tests",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: The turn handler tests are failing but only in CI, not locally.",
        "Assistant: That usually means environment differences. What's the error?",
        "User: It's a timeout — the mock agent isn't responding fast enough in the test environment."
      ],
      "goals": ["Fix flaky CI tests in the orchestrator"],
      "project_map": ["voice-first development partner — orchestrator service"]
    },
    "expected_expert": "TechnicalPM",
    "note": ""
  },
  {
    "id": "tech-004",
    "description": "Choosing a vector store for knowledge retrieval",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I need to pick something for storing and retrieving session knowledge. Chroma, Pinecone, or just SQLite with embeddings?",
        "Assistant: What's your priority — simplicity, performance, or avoiding cloud dependencies?",
        "User: Definitely local first. I want it to run without any external services."
      ],
      "goals": ["Design the knowledge storage layer"],
      "project_map": ["voice-first development partner — knowledge layer"]
    },
    "expected_expert": "TechnicalPM",
    "note": ""
  },
  {
    "id": "tech-neg-001",
    "description": "Opening greeting with no content yet",
    "category": "negative",
    "context": {
      "history_tail": [
        "User: Hey, let's get started.",
        "Assistant: Good to hear from you. What are we working on today?"
      ],
      "goals": [],
      "project_map": []
    },
    "expected_expert": null,
    "note": ""
  }
]
```

- [ ] **Step 2: Run — verify 5 tests collected, all error on NotImplementedError**

```bash
pip install -e "orchestrator/" -q && pytest evals/ -v
```

Expected output:
```
ERRORS
evals/test_expert_selection.py::test_expert_selection[tech-001] - NotImplementedError: ...
evals/test_expert_selection.py::test_expert_selection[tech-002] - NotImplementedError: ...
evals/test_expert_selection.py::test_expert_selection[tech-003] - NotImplementedError: ...
evals/test_expert_selection.py::test_expert_selection[tech-004] - NotImplementedError: ...
evals/test_expert_selection.py::test_expert_selection[tech-neg-001] - NotImplementedError: ...
5 errors
```

- [ ] **Step 3: Commit**

```bash
git add evals/evalsets/tech-pm.evalset.json
git commit -m "eval: add TechnicalPM seed cases (4 clear, 1 negative)"
```

---

## Task 5: ArtistManager Evalset

**Files:**
- Create: `evals/evalsets/artist-manager.evalset.json`

- [ ] **Step 1: Create the evalset file**

```json
[
  {
    "id": "art-001",
    "description": "Deciding whether to take an unpaid gig for exposure",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: A decent venue offered a spot but they're not paying — just exposure.",
        "Assistant: What's your current situation with paid shows?",
        "User: I've got two paid gigs this month but this venue has a good crowd for my genre."
      ],
      "goals": ["Build a sustainable gigging strategy"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": "ArtistManager",
    "note": ""
  },
  {
    "id": "art-002",
    "description": "Timing a single release around a live show",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I'm trying to figure out when to drop the single. I've got a show in six weeks.",
        "Assistant: Do you want the release to drive attendance or do you want the crowd to already know it?",
        "User: Ideally both, but if I had to choose I'd want them to know it by the time they show up."
      ],
      "goals": ["Release a new single and maximise its impact"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": "ArtistManager",
    "note": ""
  },
  {
    "id": "art-003",
    "description": "Deciding whether to lean into a new sound",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: The last few songs I've written have a completely different vibe than my existing catalogue.",
        "Assistant: Different how — production, genre, mood?",
        "User: More electronic, darker. My current fans expect something more folk-adjacent."
      ],
      "goals": ["Define artistic direction for the next project"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": "ArtistManager",
    "note": ""
  },
  {
    "id": "art-004",
    "description": "Building a consistent social media presence between releases",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I know I should be posting more but I genuinely don't know what to say when nothing's happening.",
        "Assistant: What do your most engaged posts tend to be about?",
        "User: Behind-the-scenes stuff gets way more response than anything polished."
      ],
      "goals": ["Grow audience between releases"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": "ArtistManager",
    "note": ""
  },
  {
    "id": "art-neg-001",
    "description": "User acknowledging a point mid-conversation",
    "category": "negative",
    "context": {
      "history_tail": [
        "Assistant: Releasing before the show gives the audience familiarity, but releasing after lets the live performance create anticipation.",
        "User: Yeah, that's a good way to think about it.",
        "Assistant: What's your instinct?"
      ],
      "goals": ["Release a new single and maximise its impact"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": null,
    "note": ""
  }
]
```

- [ ] **Step 2: Run — verify 10 tests collected, all error**

```bash
pytest evals/ -v 2>&1 | tail -5
```

Expected output:
```
10 errors
```

- [ ] **Step 3: Commit**

```bash
git add evals/evalsets/artist-manager.evalset.json
git commit -m "eval: add ArtistManager seed cases (4 clear, 1 negative)"
```

---

## Task 6: HealthCoach Evalset

**Files:**
- Create: `evals/evalsets/health-coach.evalset.json`

- [ ] **Step 1: Create the evalset file**

```json
[
  {
    "id": "hlth-001",
    "description": "Addressing chronic low energy in the afternoon",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I crash every afternoon around 2pm no matter what I do.",
        "Assistant: What does your sleep look like — time, quality, consistency?",
        "User: I sleep about 7 hours but it's not consistent. Some nights I'm up until 1am."
      ],
      "goals": ["Improve daily energy levels"],
      "project_map": []
    },
    "expected_expert": "HealthCoach",
    "note": ""
  },
  {
    "id": "hlth-002",
    "description": "Building a sustainable exercise habit",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I've tried getting into running three times and always quit after two weeks.",
        "Assistant: What usually causes you to stop?",
        "User: It starts feeling like a chore and I dread it the night before."
      ],
      "goals": ["Establish a consistent fitness routine"],
      "project_map": []
    },
    "expected_expert": "HealthCoach",
    "note": ""
  },
  {
    "id": "hlth-003",
    "description": "Managing work-related stress and mental load",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I feel like I can't switch off at the end of the day. Work thoughts just follow me everywhere.",
        "Assistant: Is there a specific time when it gets worse, or is it constant?",
        "User: Worse in the evenings. I'll be watching TV and suddenly I'm anxious about tomorrow's tasks."
      ],
      "goals": ["Reduce stress and improve mental recovery"],
      "project_map": []
    },
    "expected_expert": "HealthCoach",
    "note": ""
  },
  {
    "id": "hlth-004",
    "description": "Improving eating habits around a deep work schedule",
    "category": "clear",
    "context": {
      "history_tail": [
        "User: I skip lunch most days because I'm in flow and don't want to break it.",
        "Assistant: And how does that affect your afternoon?",
        "User: I'm ravenous by 4pm and end up eating whatever's convenient, which is usually junk."
      ],
      "goals": ["Build better nutrition habits that fit a deep work schedule"],
      "project_map": []
    },
    "expected_expert": "HealthCoach",
    "note": ""
  },
  {
    "id": "hlth-neg-001",
    "description": "User asking what the assistant is here to help with",
    "category": "negative",
    "context": {
      "history_tail": [
        "User: Can you remind me what you're actually here to help me with?",
        "Assistant: I'm here to help you think through what's on your mind and structure your thinking. I'll ask questions to help you clarify goals and next steps."
      ],
      "goals": [],
      "project_map": []
    },
    "expected_expert": null,
    "note": ""
  }
]
```

- [ ] **Step 2: Run — verify 15 tests collected, all error**

```bash
pytest evals/ -v 2>&1 | tail -5
```

Expected output:
```
15 errors
```

- [ ] **Step 3: Commit**

```bash
git add evals/evalsets/health-coach.evalset.json
git commit -m "eval: add HealthCoach seed cases (4 clear, 1 negative)"
```

---

## Task 7: Overlap Evalset

**Files:**
- Create: `evals/evalsets/overlap.evalset.json`

- [ ] **Step 1: Create the evalset file**

```json
[
  {
    "id": "ovlp-001",
    "description": "Vocal strain affecting upcoming shows",
    "category": "overlap",
    "context": {
      "history_tail": [
        "User: My voice has been getting tired much faster during rehearsals lately.",
        "Assistant: Is this new, or has it been building over time?",
        "User: About three weeks since it started. I've got two shows next month I'm worried about."
      ],
      "goals": ["Protect vocal health ahead of live shows"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": "HealthCoach",
    "note": "The immediate concern is physical — vocal cord health and recovery. ArtistManager is downstream (show planning) but the speaker is asking about the symptom, not the scheduling consequence."
  },
  {
    "id": "ovlp-002",
    "description": "Anxiety in the hour before going on stage",
    "category": "overlap",
    "context": {
      "history_tail": [
        "User: I get really bad stage fright. It's not just nerves — it's affecting my performance.",
        "Assistant: Does it hit before you go on, during, or both?",
        "User: Mostly in the hour before. By the time I'm on stage it's manageable but the buildup is rough."
      ],
      "goals": ["Perform consistently and confidently live"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": "HealthCoach",
    "note": "Stage fright in the hour before a show is an anxiety management problem, not a performance strategy problem. ArtistManager might address pre-show routines at a career level, but the speaker is describing a psychological symptom."
  },
  {
    "id": "ovlp-003",
    "description": "Exhaustion and motivation loss mid-tour",
    "category": "overlap",
    "context": {
      "history_tail": [
        "User: I'm three weeks into a five week run and I'm completely burnt out.",
        "Assistant: Is it physical exhaustion, or is the motivation gone too?",
        "User: Both. I'm going through the motions on stage and I hate that."
      ],
      "goals": ["Complete the tour without burning out further"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": "HealthCoach",
    "note": "The speaker describes burnout symptoms — physical and motivational depletion. Recovery strategies are the primary need. ArtistManager could address show-by-show adjustments but that is secondary to the underlying state."
  },
  {
    "id": "ovlp-004",
    "description": "Creative block following a difficult personal period",
    "category": "overlap",
    "context": {
      "history_tail": [
        "User: I haven't been able to write anything in two months. Every time I sit down nothing comes.",
        "Assistant: Has anything changed in your life around the time it started?",
        "User: I went through a rough patch personally. I think I'm out of it now but the writing hasn't come back."
      ],
      "goals": ["Rebuild a creative writing practice"],
      "project_map": ["singer-songwriter career development"]
    },
    "expected_expert": "ArtistManager",
    "note": "The speaker reports being through the personal difficulty and is now focused on rebuilding creative practice. This is a craft and routine question, not an active mental health intervention. ArtistManager addresses creative process; HealthCoach would be appropriate if the mood issues were ongoing."
  }
]
```

- [ ] **Step 2: Run — verify 19 tests collected, all error on NotImplementedError**

```bash
pytest evals/ -v 2>&1 | tail -8
```

Expected output:
```
evals/test_expert_selection.py::test_expert_selection[ovlp-001] ERROR
evals/test_expert_selection.py::test_expert_selection[ovlp-002] ERROR
evals/test_expert_selection.py::test_expert_selection[ovlp-003] ERROR
evals/test_expert_selection.py::test_expert_selection[ovlp-004] ERROR
19 errors
```

- [ ] **Step 3: Commit**

```bash
git add evals/evalsets/overlap.evalset.json
git commit -m "eval: add overlap seed cases (ArtistManager vs HealthCoach)"
```

---

## Completion Check

After all tasks, verify the full suite state:

```bash
pytest evals/ -v 2>&1 | grep -E "collected|error|passed|failed"
```

Expected: `19 errors` — all cases defined, routing not yet implemented. This is the correct state: the eval suite exists and is waiting for routing logic (Epic 4, "Build: improved routing").

When routing is implemented in `orchestrator/orchestrator/routing.py`, run `pytest evals/ -v` to see results with the precision/recall table.
