from dataclasses import dataclass
import yaml


@dataclass
class AgentConfig:
    name: str
    url: str


def load_registry(config_path: str) -> tuple[list[AgentConfig], float, int]:
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    agents = [
        AgentConfig(name=a["name"], url=a["url"])
        for a in data.get("agents", [])
    ]
    threshold = float(data.get("confidence_threshold", 0.5))
    timeout = int(data.get("agent_timeout_seconds", 2))
    return agents, threshold, timeout
