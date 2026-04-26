import pytest
from orchestrator.agent_registry import load_registry


def test_load_registry_parses_agents(tmp_path):
    cfg = tmp_path / "agents.yaml"
    cfg.write_text(
        "confidence_threshold: 0.7\nagent_timeout_seconds: 3\n"
        "agents:\n  - name: Agent1\n    url: http://a1:9000\n"
    )
    agents, threshold, timeout = load_registry(str(cfg))
    assert len(agents) == 1
    assert agents[0].name == "Agent1"
    assert agents[0].url == "http://a1:9000"
    assert threshold == 0.7
    assert timeout == 3


def test_load_registry_empty_agents(tmp_path):
    cfg = tmp_path / "agents.yaml"
    cfg.write_text("confidence_threshold: 0.5\nagent_timeout_seconds: 2\nagents: []\n")
    agents, _, _ = load_registry(str(cfg))
    assert agents == []


def test_load_registry_defaults(tmp_path):
    cfg = tmp_path / "agents.yaml"
    cfg.write_text("agents: []\n")
    _, threshold, timeout = load_registry(str(cfg))
    assert threshold == 0.5
    assert timeout == 2


def test_load_registry_raises_on_malformed_agent_entry(tmp_path):
    cfg = tmp_path / "agents.yaml"
    cfg.write_text("confidence_threshold: 0.5\nagent_timeout_seconds: 2\nagents:\n  - name: Agent1\n")
    with pytest.raises(ValueError, match="Malformed agent entry"):
        load_registry(str(cfg))


def test_load_registry_raises_on_out_of_range_threshold(tmp_path):
    cfg = tmp_path / "agents.yaml"
    cfg.write_text("confidence_threshold: 1.5\nagent_timeout_seconds: 2\nagents: []\n")
    with pytest.raises(ValueError, match="confidence_threshold"):
        load_registry(str(cfg))
