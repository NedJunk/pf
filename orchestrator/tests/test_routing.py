import pytest
from orchestrator.agent_registry import AgentConfig
from orchestrator.routing import select_experts


def _event(history=None, goals=None, project_map=None):
    return {
        "session_id": "s1",
        "history_tail": history or [],
        "goals": goals or [],
        "project_map": project_map or [],
    }


def _agent(name="AgentA", tags=None):
    return AgentConfig(name=name, url=f"http://{name.lower()}:8000", tags=tags or [])


def test_select_experts_above_threshold():
    agent = _agent(name="DevCoach", tags=["bug", "test", "refactor"])
    event = _event(history=["User: I have a bug in the test"])
    result = select_experts(event, [agent], threshold=0.05)
    assert agent in result


def test_select_experts_below_threshold_falls_back():
    agent = _agent(name="DevCoach", tags=["bug", "sprint"])
    # No overlap between tags and context words ("hello", "world")
    event = _event(history=["User: hello world"])
    result = select_experts(event, [agent], threshold=0.99)
    # fallback: all agents returned
    assert agent in result
    assert len(result) == 1


def test_select_experts_multi_agent_partial():
    agent_a = _agent(name="DevCoach", tags=["bug", "test", "refactor"])
    agent_b = _agent(name="ArchBot", tags=["architecture", "design", "diagram"])
    # Context only mentions bug-related terms
    event = _event(history=["User: there is a bug in the test suite"])
    result = select_experts(event, [agent_a, agent_b], threshold=0.05)
    assert agent_a in result
    assert agent_b not in result


def test_select_experts_empty_tags_does_not_crash():
    agent = _agent(name="Tagless", tags=[])
    event = _event(history=["User: working on a sprint bug"])
    # score will be 0.0 (no tags), no agent above threshold → fallback
    result = select_experts(event, [agent], threshold=0.05)
    # fallback: returns all
    assert agent in result
    assert len(result) == 1


def test_select_experts_threshold_zero_selects_all_with_tags():
    agent_a = _agent(name="DevCoach", tags=["bug", "test"])
    agent_b = _agent(name="ArchBot", tags=["architecture"])
    event = _event(history=["User: hello"])
    result = select_experts(event, [agent_a, agent_b], threshold=0.0)
    assert agent_a in result
    assert agent_b in result
