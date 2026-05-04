# Expert Selection Evalset — Spec & Schema

**Date:** 2026-05-03
**Epic:** E1 — Evaluation Framework
**Status:** design draft

---

## 1. What Is Being Evaluated

The orchestrator currently broadcasts every turn to all registered agents (fan-out). The goal of E4-E/F is smarter routing: only fire agents that are likely to produce a useful whisper for a given turn.

This evalset labels *which agents should have been selected* for a given conversation turn. The E1-B runner compares orchestrator routing decisions against those labels to measure routing quality — before and after any routing change.

**The classification task per turn:**
> Given session context + turn text, which subset of registered agents (if any) should receive this turn?

Each agent in the registry is an independent binary label: fire / don't fire.

---

## 2. Test Case Schema

File format: **JSONL** — one JSON object per line, one file per session. This keeps individual cases small and makes streaming evaluation straightforward.

### 2.1 Top-Level Structure

```json
{
  "case_id": "string",
  "session_id": "string",
  "turn_index": 0,
  "context": {
    "history": ["string"],
    "goals": ["string"],
    "project_map": ["string"]
  },
  "turn": "string",
  "labels": [
    {
      "agent": "string",
      "should_fire": true,
      "confidence": 0.9,
      "rationale": "string"
    }
  ],
  "labeled_by": "human | synthetic",
  "labeled_at": "ISO-8601 datetime",
  "session_topic": "string"
}
```

### 2.2 Field Notes

| Field | Notes |
|---|---|
| `case_id` | `{session_id}:{turn_index}` — stable, derivable, unique |
| `history` | The turns *before* the current turn, in order. Same shape as `WhisperContext.history`. Mirror the orchestrator payload exactly so the runner can replay without transformation. |
| `turn` | The exact turn text the orchestrator received. |
| `labels[].agent` | Agent name as registered in `agents.yaml` (e.g. `DevCoach`, `Researcher`). |
| `labels[].should_fire` | True = this agent should receive the turn. False = this agent should not. |
| `labels[].confidence` | Labeler's confidence in the label (0.0–1.0). Cases with `confidence < 0.7` are excluded from regression gates but retained for analysis. |
| `labels[].rationale` | One sentence: why this agent should/shouldn't fire. Required for human labels; optional for synthetic. |
| `labeled_by` | `human` for transcript review workflow; `synthetic` for LLM-assisted bootstrapping. |
| `session_topic` | Slug from the transcript filename (e.g. `debugging-router-audio`). Enables per-topic metric breakdowns. |

### 2.3 Example Case

```json
{
  "case_id": "a23a2089:4",
  "session_id": "a23a2089",
  "turn_index": 4,
  "context": {
    "history": [
      "User: I'm trying to figure out why the whisper isn't reaching the router.",
      "Assistant: What part of the pipeline are you looking at first?"
    ],
    "goals": ["debug whisper delivery"],
    "project_map": ["voice-router", "router-service", "orchestrator"]
  },
  "turn": "I think it might be the callback URL not resolving inside Docker.",
  "labels": [
    {
      "agent": "DevCoach",
      "should_fire": true,
      "confidence": 0.95,
      "rationale": "Developer debugging a Docker networking issue — dev-coach wiki likely has relevant entries."
    },
    {
      "agent": "Researcher",
      "should_fire": false,
      "confidence": 0.85,
      "rationale": "Concrete debugging step, not a research question. No benefit from background research."
    }
  ],
  "labeled_by": "human",
  "labeled_at": "2026-05-03T18:30:00Z",
  "session_topic": "debugging-router-audio"
}
```

---

## 3. Labeling Workflow (E1-C)

The orchestrator currently fires all agents on all turns, so we cannot derive ground-truth labels from system behavior. Labels must come from human review of existing transcripts.

### 3.1 Process

1. Open a transcript file from `./transcripts/`.
2. For each turn in the transcript, ask: "Would a DevCoach whisper on this turn add value? Would a Researcher whisper add value?"
3. Write one JSONL case per labeled turn. Not every turn needs a label — skip turns that are ambiguous or purely conversational with no routing signal.
4. Save to `evalset/{session_id}.jsonl`.

### 3.2 Tooling Needed (E1-C deliverable)

A lightweight CLI script `scripts/label-turn.py` that:
- Takes a transcript file path
- Renders each turn with its preceding context (last 3 turns shown)
- Prompts the labeler: `DevCoach [y/n/skip]?`, `Researcher [y/n/skip]?`, `Confidence [0-1]?`, `Rationale?`
- Appends the completed case to `evalset/{session_id}.jsonl`
- Supports `--resume` to skip already-labeled turns in a session

### 3.3 Expressing Per-Agent Decisions

Each turn produces one label entry per *registered* agent. If a new agent is added to `agents.yaml`, existing evalset cases do not need retroactive labels for it — the runner scores only agents present in both the case and the current registry.

---

## 4. File Layout

```
evalset/
  README.md           # schema version, labeling instructions
  dev/
    a23a2089.jsonl    # one file per labeled session
    6275d9ca.jsonl
  fixtures/
    routing_smoke.jsonl   # hand-crafted canonical cases, checked into CI
```

- `dev/` — human-labeled production sessions. Not committed by default (may contain sensitive transcript content); gitignored, or committed with PII review.
- `fixtures/` — small, hand-crafted canonical cases covering clear-fire and clear-skip scenarios. Always committed. Used in CI regression gate (E1-D).

Schema version tracked in `evalset/README.md`. Breaking schema changes bump a `schema_version` field on each case.

---

## 5. Evaluation Metrics

The E1-B runner computes per-agent binary classification metrics across all cases with `confidence >= 0.7`.

| Metric | Definition |
|---|---|
| Precision | Of all turns the orchestrator fired this agent on, what fraction were labeled `should_fire: true`? |
| Recall | Of all turns labeled `should_fire: true` for this agent, what fraction did the orchestrator actually fire on? |
| F1 | Harmonic mean of precision and recall. Primary single-number summary. |
| False-positive rate | Turns fired but labeled false. High FPR = wasted agent calls (cost and latency). |
| False-negative rate | Turns not fired but labeled true. High FNR = missed whispers (user value lost). |

**Routing bias for this system:** false negatives (missed whispers) are worse than false positives (extra agent calls) at current scale. E1-B should report FNR prominently and set the regression gate threshold on recall, not precision.

### 5.1 Runner Interface (E1-B)

```python
# Expected interface for E1-B to consume this schema
cases = load_evalset("evalset/fixtures/routing_smoke.jsonl")
results = evaluate_routing(orchestrator_client, cases, min_confidence=0.7)
assert results["DevCoach"]["recall"] >= 0.80
```

---

## 6. Bootstrapping the Evalset

Since routing is currently broadcast-all, there are no system-generated routing decisions to label. Bootstrapping is purely human.

**Minimum viable evalset for a meaningful signal:** 30 labeled turns across at least 3 sessions covering distinct topic types (debugging, design, backlog review). At 30 cases, per-agent F1 has enough variance to detect a >15% improvement in routing quality.

**Recommended bootstrap process:**
1. Label 3 existing transcripts from `./transcripts/` (pick sessions with distinct topics).
2. Aim for ~10 turns per session — skip purely conversational exchanges.
3. Put the best 10 canonical cases (clear-fire and clear-skip) into `fixtures/routing_smoke.jsonl` for CI.
4. Remainder goes into `dev/`.

**Synthetic bootstrapping option:** LLM-assisted labeling (set `labeled_by: synthetic`) can accelerate coverage but should not be used for CI fixtures. Use only for exploratory analysis until human labels confirm the synthetic labels are reliable.

---

## 7. Dependencies and Open Questions

### 7.1 Dependencies

| Item | Dependency |
|---|---|
| E1-B (runner) | Needs this schema finalized. Can start once §2 is stable. |
| E1-C (labeling tool) | Needs §3 process. Can start immediately. |
| E1-D (CI gate) | Needs E1-B + fixtures evalset populated. |
| E4-E/F (routing logic) | Evalset is the acceptance test for routing changes. Must exist before E4-F ships. |

### 7.2 Open Questions

1. **PII in transcripts**: transcript content may include sensitive developer context. Decide before committing `dev/` cases: gitignore and document a manual review process, or strip identifying content before commit.

2. **Multi-agent label when only one agent exists**: today only DevCoach is registered. All cases will have a single label. When Researcher is added (E4-I), retroactive labeling of existing cases for Researcher is needed before E4-F evaluation is meaningful.

3. **Confidence threshold for CI gate**: `confidence >= 0.7` is a starting point. Calibrate after first 30 labels — if labelers consistently express high confidence, raise the gate.

4. **`goals` and `project_map` population**: these fields exist in `WhisperContext` but their actual content depends on how the router-service populates them. Verify against `live_session.py` before writing the labeling CLI — the context shape must match exactly what the orchestrator sends.
