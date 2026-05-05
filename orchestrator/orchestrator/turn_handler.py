import asyncio
import logging
import httpx
from orchestrator.agent_registry import AgentConfig
from orchestrator.health_monitor import HealthMonitor
from orchestrator.routing import select_experts

logger = logging.getLogger(__name__)


async def handle_turn(
    turn_event: dict,
    agents: list[AgentConfig],
    health_monitor: HealthMonitor,
    confidence_threshold: float,
    agent_timeout: int,
    router_service_url: str,
    routing_threshold: float = 0.05,
) -> None:
    healthy = [a for a in agents if health_monitor.is_healthy(a.name)]
    if not healthy:
        logger.warning("No healthy agents for turn event session=%s", turn_event["session_id"])
        return

    routed = select_experts(turn_event, healthy, routing_threshold)

    session_id = turn_event["session_id"]
    callback_url = f"{router_service_url}/sessions/{session_id}/whisper"

    await asyncio.gather(
        *[_call_agent(a, turn_event, callback_url, confidence_threshold, agent_timeout) for a in routed],
        return_exceptions=True,
    )


async def _call_agent(
    agent: AgentConfig,
    turn_event: dict,
    callback_url: str,
    confidence_threshold: float,
    timeout: int,
) -> None:
    payload = {
        "session_id": turn_event["session_id"],
        "context": {
            "history": turn_event["history_tail"],
            "goals": turn_event["goals"],
            "project_map": turn_event["project_map"],
        },
        "callback_url": callback_url,
        "confidence_threshold": confidence_threshold,
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{agent.url}/whisper", json=payload, timeout=float(timeout))
            if resp.status_code != 202:
                logger.warning("Agent %s returned %s for whisper dispatch", agent.name, resp.status_code)
        except Exception as exc:
            logger.warning("Agent %s error [%s] url=%s: %s", agent.name, type(exc).__name__, agent.url, exc)
