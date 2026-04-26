from dataclasses import dataclass
import yaml


@dataclass
class AgentConfig:
    name: str
    url: str


def load_registry(config_path: str) -> tuple[list[AgentConfig], float, int]:
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    try:
        agents = [
            AgentConfig(name=a["name"], url=a["url"])
            for a in data.get("agents", [])
        ]
    except (KeyError, TypeError) as e:
        raise ValueError(f"Malformed agent entry in registry: {e}") from e
    threshold = float(data.get("confidence_threshold", 0.5))
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"confidence_threshold must be in [0, 1], got {threshold}")
    timeout = int(data.get("agent_timeout_seconds", 2))
    return agents, threshold, timeout
