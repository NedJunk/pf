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
