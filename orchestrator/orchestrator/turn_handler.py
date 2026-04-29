import asyncio
import logging
import httpx
from orchestrator.agent_registry import AgentConfig
from orchestrator.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)


async def handle_turn(
    turn_event: dict,
    agents: list[AgentConfig],
    health_monitor: HealthMonitor,
    confidence_threshold: float,
    agent_timeout: int,
    router_service_url: str,
) -> None:
    healthy = [a for a in agents if health_monitor.is_healthy(a.name)]
    if not healthy:
        logger.warning("No healthy agents for turn event session=%s", turn_event["session_id"])
        return

    results = await asyncio.gather(
        *[_call_agent(a, turn_event, agent_timeout) for a in healthy],
        return_exceptions=True,
    )

    session_id = turn_event["session_id"]
    async with httpx.AsyncClient() as client:
        for result in results:
            if isinstance(result, Exception) or result is None:
                continue
            if result["confidence"] < confidence_threshold:
                continue
            try:
                await client.post(
                    f"{router_service_url}/sessions/{session_id}/whisper",
                    json={"source": result["source"], "message": result["message"]},
                    timeout=5.0,
                )
            except Exception as exc:
                logger.warning("Failed to post whisper to router: %s", exc)


async def _call_agent(agent: AgentConfig, turn_event: dict, timeout: int) -> dict | None:
    payload = {
        "session_id": turn_event["session_id"],
        "context": {
            "history": turn_event["history_tail"],
            "goals": turn_event["goals"],
            "project_map": turn_event["project_map"],
        },
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{agent.url}/whisper", json=payload, timeout=float(timeout))
            if resp.status_code == 204:
                return None
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Agent %s returned %s", agent.name, resp.status_code)
            return None
        except asyncio.TimeoutError:
            logger.warning("Agent %s timed out", agent.name)
            return None
        except Exception as exc:
            logger.warning("Agent %s error [%s] url=%s: %s", agent.name, type(exc).__name__, agent.url, exc)
            return None
