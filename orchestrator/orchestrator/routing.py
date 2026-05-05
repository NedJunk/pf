import json
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = float(os.environ.get("ROUTING_RELEVANCE_THRESHOLD", "0.05"))


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _context_words(turn_event: dict) -> set:
    """Extract lowercase words from history_tail, goals, and project_map."""
    lines = (
        turn_event.get("history_tail", [])
        + turn_event.get("goals", [])
        + turn_event.get("project_map", [])
    )
    words = set()
    for line in lines:
        words.update(str(line).lower().split())
    return words


def select_experts(turn_event: dict, agents: list, threshold: float = _DEFAULT_THRESHOLD) -> list:
    """Return agents whose capability tags score above threshold against the turn context.

    Falls back to returning all agents if none score above threshold.
    Logs a routing_decision JSON line per call at INFO level.
    """
    ctx = _context_words(turn_event)
    session_id = turn_event.get("session_id", "unknown")

    candidates = []
    for agent in agents:
        tag_words = set(
            w for tag in (agent.tags or []) for w in str(tag).lower().split()
        )
        score = _jaccard(tag_words, ctx) if tag_words else 0.0
        candidates.append({"agent": agent, "name": agent.name, "score": score})

    selected = [c for c in candidates if c["score"] >= threshold]
    fallback = len(selected) == 0

    if fallback:
        selected = candidates  # broadcast-all fallback

    logger.info(
        json.dumps({
            "event": "routing_decision",
            "session_id": session_id,
            "candidates": [
                {"name": c["name"], "score": round(c["score"], 4), "selected": c in selected}
                for c in candidates
            ],
            "fallback": fallback,
        })
    )

    return [c["agent"] for c in selected]
