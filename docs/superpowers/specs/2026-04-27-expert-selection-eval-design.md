# Expert Selection Evaluation Framework — Design Spec

## Goal

Define a regression-capable evaluation suite that measures whether the orchestrator routes a conversation turn to the correct domain expert. Ground truth is human judgment. The suite grows over time: a hand-written seed corpus covers the decision space immediately; real session transcripts are promoted into the evalset as they accumulate.

## Architecture

```
evals/
  evalsets/
    tech-pm.evalset.json          # clear cases — TechnicalPM
    artist-manager.evalset.json   # clear cases — ArtistManager
    health-coach.evalset.json     # clear cases — HealthCoach
    overlap.evalset.json          # ambiguous cases, ArtistManager vs HealthCoach
  conftest.py                     # loads evalsets, computes precision/recall summary
  test_expert_selection.py        # pytest runner
  README.md                       # labeling guide and transcript → evalset workflow
```

The runner calls a pure routing function in the orchestrator directly — no HTTP, no running services. Tests are fast and deterministic. The eval suite is independent of any specific routing implementation; it defines what correct routing looks like so the implementation can be built against it.

## Experts (Seed Registry)

| Name | Domain |
|---|---|
| `TechnicalPM` | This project — infrastructure, architecture, code decisions |
| `ArtistManager` | Singer-songwriter career — bookings, releases, touring, creative direction |
| `HealthCoach` | Health and wellness — physical health, mental health, habits, energy |

## Routing Interface

A single pure function in `orchestrator/orchestrator/routing.py`:

```python
def select_expert(context: dict, registry: list[str]) -> str | None:
    """
    Given conversation context and the list of registered expert names,
    return the name of the most relevant expert, or None if no expert
    should be called at this turn.
    """
```

The eval imports this directly. Until implemented it raises `NotImplementedError`, which surfaces as an error (not a failure) in pytest output — visually distinct from routing regressions.

## Test Case Schema

Each `.evalset.json` file is a JSON array of cases:

```json
[
  {
    "id": "tech-003",
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

### Field Reference

| Field | Required | Description |
|---|---|---|
| `id` | yes | `{abbrev}-{number}`: `tech-001`, `art-002`, `hlth-003`, `ovlp-001` |
| `description` | yes | One phrase describing what's happening in the conversation |
| `category` | yes | `clear`, `overlap`, or `negative` |
| `context.history_tail` | yes | 2–5 turns immediately preceding the routing decision |
| `context.goals` | yes | Session goals as entered at start; `[]` if none |
| `context.project_map` | yes | Session project map; `[]` if none |
| `expected_expert` | yes | Agent name, or `null` for negative cases |
| `note` | overlap only | Required for `overlap` cases — one sentence explaining the judgment call |

### Categories

**`clear`** — only one expert could reasonably apply. The other two are obviously wrong.

**`overlap`** — `ArtistManager` and `HealthCoach` both have a plausible claim. Label the one that is *more directly* relevant to what the speaker is asking about right now, not what they might need eventually. A `note` explaining the judgment is required.

**`negative`** — the conversation does not call for expert injection at this turn. `expected_expert` is `null`.

### Selection Mode

Single-label: each case has exactly one correct answer. The forced choice between overlapping experts is intentional — it surfaces domain boundary ambiguities and forces explicit judgment that clarifies how the agents should coordinate.

## Runner Design

### test_expert_selection.py

```python
import json
import pytest
from pathlib import Path
from orchestrator.orchestrator.routing import select_expert

EVALSET_DIR = Path(__file__).parent / "evalsets"
REGISTRY = ["TechnicalPM", "ArtistManager", "HealthCoach"]

def load_cases():
    cases = []
    for path in sorted(EVALSET_DIR.glob("*.evalset.json")):
        for case in json.loads(path.read_text()):
            cases.append(case)
    return cases

@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c["id"])
def test_expert_selection(case):
    result = select_expert(case["context"], REGISTRY)
    assert result == case["expected_expert"], (
        f"Expected {case['expected_expert']!r}, got {result!r} — {case['description']}"
    )
```

Each case gets its own test named by its `id`. A regression is immediately traceable: `FAILED evals/test_expert_selection.py::test_expert_selection[tech-003]`.

### conftest.py

Hooks into pytest's terminal summary to print a per-expert precision/recall table after the run. Informational only — does not affect exit code.

```
Expert Selection Results
────────────────────────────────────────
Expert          Precision   Recall   F1
TechnicalPM     1.00        0.83     0.91
ArtistManager   0.75        1.00     0.86
HealthCoach     1.00        1.00     1.00
────────────────────────────────────────
Overall         19/22 cases correct
```

Precision and recall per expert are computed across all cases in the evalset:
- **Precision**: of the cases where the runner selected this expert, what fraction were correct?
- **Recall**: of the cases where this expert was the correct answer, what fraction were selected?

## Seed Corpus

Shipped with the runner so there is something to evaluate against before real sessions exist. Approximately 15–20 hand-written cases:

| File | Count | Coverage |
|---|---|---|
| `tech-pm.evalset.json` | 4 clear | Deployment, architecture, debugging, tool choice |
| `artist-manager.evalset.json` | 4 clear | Bookings, release strategy, creative direction, fan engagement |
| `health-coach.evalset.json` | 4 clear | Exercise, sleep/energy, stress, nutrition |
| `overlap.evalset.json` | 4 overlap | Vocal health, performance anxiety, tour fatigue, burnout |
| *(distributed)* | 3 negative | Early-session turns, small talk, capability questions |

Overlap cases require the most care when writing. Each must have a `note` that makes the judgment legible to a future reader who wasn't present for the labeling decision.

## Growth Workflow

As real session transcripts accumulate in `transcripts/`:

1. Open a transcript and find a turn where the routing decision is interesting
2. Copy the 2–5 preceding turns into `history_tail`
3. Label the correct expert (or `null`)
4. Add the case to the appropriate evalset file with `category`, `description`, and `id`
5. Run `pytest evals/ -v` to confirm the case is well-formed and the suite passes

No tooling is needed for this workflow — the evalset files are edited directly. A UI for labeling is a future option if the corpus grows large enough to make direct editing cumbersome.

## CI Integration

Added to `.github/workflows/ci.yml` once a routing implementation exists in `orchestrator/orchestrator/routing.py`. Until then the suite is run locally and failures are expected.

```yaml
eval:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - run: pip install -e "orchestrator/[dev]"
    - run: pytest evals/ -v
```

## What Is Out of Scope

- **Multi-label selection**: starting with single-label (either/or) to force explicit domain boundary judgments. Multi-label support added when the overlap patterns are well understood.
- **LLM-judged scoring**: all ground truth is human-labeled. Automated semantic scoring deferred; would require a cloud dependency that conflicts with the local deployment goal.
- **A labeling UI**: direct JSON editing is sufficient at current corpus size.
- **Evaluation of whisper content quality**: this spec covers only expert selection (which agent is called), not the quality of the whisper the agent produces.
