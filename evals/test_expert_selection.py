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
    if case["category"] == "overlap":
        assert case.get("note"), f"{case['id']}: overlap cases require a non-empty 'note' field"

    try:
        result = select_expert(case["context"], REGISTRY)
    except NotImplementedError:
        eval_results.append({"expected": case["expected_expert"], "actual": "__not_implemented__"})
        pytest.fail(f"{case['id']}: select_expert raised NotImplementedError — routing not yet implemented")

    eval_results.append({"expected": case["expected_expert"], "actual": result})
    assert result == case["expected_expert"], (
        f"Expected {case['expected_expert']!r}, got {result!r} — {case['description']}"
    )
