# Orchestrator Routing Design (E4-E)

**Status:** Design — approved for implementation as E4-F  
**Date:** 2026-05-05  
**Author:** dave gurnsey

---

## Problem

The orchestrator currently broadcasts every turn to all healthy agents. With one agent this is fine. As the agent ecosystem grows (researcher, debug, domain-specific agents) the broadcast model has three failure modes:

1. **LLM cost waste** — every agent generates a response regardless of relevance. Agents that have nothing to add must still call their model and decide.
2. **Whisper noise** — more agents → more injections per turn → more for the router to filter → higher risk of contradiction or confusion.
3. **Latency creep** — `asyncio.gather` waits for the slowest agent. Low-relevance agents slow delivery of high-relevance whispers.

---

## Options Considered

| Option | Summary | Pro | Con |
|--------|---------|-----|-----|
| A | Keyword routing (pattern matching in orchestrator) | No latency, no cost | Brittle, needs maintenance per agent |
| B | Two-round: cheap relevance-check endpoint then full whisper | Accurate | Extra HTTP round trip per agent |
| C | LLM classifier in orchestrator | High accuracy | Adds latency, needs model + prompt |
| **D** | **Capability tags in agents.yaml + Jaccard match** | No extra round trip, no LLM call, extensible | Requires curated tag lists per agent |
| E | Turn-category routing (coarse buckets) | Simple logic | Too coarse for multi-domain agents |

---

## Decision: Option D — Capability Tags + Jaccard Match

Each agent declares a list of capability tags in `agents.yaml`. On each turn the orchestrator scores the history tail against each agent's tags using word-overlap (Jaccard, same approach as DevCoach dedup). Agents above a configurable relevance threshold receive the turn; others are skipped.

**Why this over the alternatives:**
- No additional round-trip (unlike B)
- No LLM cost or latency (unlike C)
- Tags are readable and auditable — easier to maintain than patterns (unlike A)
- Plugs directly into the existing `select_expert()` stub and `agents.yaml` schema

---

## Design

### agents.yaml schema change

```yaml
agents:
  - name: DevCoach
    url: http://dev-coach:8082
    tags:
      - bug
      - backlog
      - sprint
      - test
      - implementation
      - refactor
      - architecture

  - name: ResearcherAgent          # future
    url: http://researcher:8083
    tags:
      - research
      - spike
      - explore
      - unfamiliar
      - how does
      - design
```

Tags are lowercase, multi-word phrases allowed. Matching is word-overlap: split the last N history tail lines and the turn goals into a word set, then Jaccard against each agent's tag word set.

### Scoring

```python
def score_agent(agent_tags: list[str], context_words: set[str]) -> float:
    """Jaccard overlap of tag words against current-turn word set."""
    tag_words = set(w for tag in agent_tags for w in tag.lower().split())
    if not tag_words:
        return 0.0
    return len(tag_words & context_words) / len(tag_words | context_words)
```

Threshold: configurable via `ROUTING_RELEVANCE_THRESHOLD` env var, default `0.05`. A low default is intentional — we want to err toward inclusion while the evalset is thin.

### Fallback

If zero agents score above threshold, fall back to broadcast-all. This preserves the current behaviour when tagging is ambiguous and avoids silent failure.

### select_expert() vs multi-expert fan-out

`select_expert()` as currently stubbed returns at most one agent. The routing design keeps multi-expert fan-out (N agents can be above threshold simultaneously). `select_expert()` is renamed/repurposed as `select_experts()` returning `list[AgentConfig]`.

---

## Implementation Plan (E4-F)

1. **`agents.yaml`**: Add `tags:` list to each agent entry.
2. **`agent_registry.py`**: Extend `AgentConfig` dataclass with `tags: list[str]`.
3. **`routing.py`**: Replace `select_expert()` stub with `select_experts(context, agents)` → `list[AgentConfig]`. Implement Jaccard scoring. Add fallback-to-all when no match.
4. **`turn_handler.py`**: Call `select_experts()` before `asyncio.gather`; pass filtered list.
5. **Env var**: `ROUTING_RELEVANCE_THRESHOLD` (float, default 0.05) in `docker-compose.yml` and `orchestrator/main.py`.
6. **Tests**: Unit tests for `select_experts()` — threshold filtering, fallback, multi-agent selection, empty tag list.
7. **Logging**: Log selected agents and their scores at `DEBUG` level per turn.

---

## Evaluation Hook

`select_experts()` should log structured JSON at `INFO` level for each turn:

```json
{
  "event": "routing_decision",
  "session_id": "...",
  "candidates": [
    {"name": "DevCoach", "score": 0.12, "selected": true},
    {"name": "ResearcherAgent", "score": 0.02, "selected": false}
  ],
  "fallback": false
}
```

This feeds directly into the E1 evalset runner once labelled examples are available.

---

## Open Questions

- **Tag authoring**: who maintains tags? Current answer: the agent owner (dave) updates `agents.yaml`. No self-registration.
- **Turn granularity**: score against the last N lines of history tail only, or include goals/project_map? Start with history tail only; add goals if precision is low.
- **Threshold tuning**: 0.05 is a guess. Let the E1 evalset drive calibration once 10+ labelled examples exist.
