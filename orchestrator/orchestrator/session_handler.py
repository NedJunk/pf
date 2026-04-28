import asyncio
import logging
import httpx
from orchestrator.agent_registry import AgentConfig
from orchestrator.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)


async def handle_session_close(
    close_event: dict,
    agents: list[AgentConfig],
    health_monitor: HealthMonitor,
    timeout: int,
) -> None:
    healthy = [a for a in agents if health_monitor.is_healthy(a.name)]
    if not healthy:
        logger.warning(
            "No healthy agents for session close session=%s", close_event["session_id"]
        )
        return

    await asyncio.gather(
        *[_call_ingest(a, close_event, timeout) for a in healthy],
        return_exceptions=True,
    )


async def _call_ingest(agent: AgentConfig, close_event: dict, timeout: int) -> None:
    payload = {
        "session_id": close_event["session_id"],
        "transcript": close_event["transcript"],
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{agent.url}/ingest", json=payload, timeout=float(timeout)
            )
            if resp.status_code != 202:
                logger.warning(
                    "Agent %s /ingest returned %s session=%s",
                    agent.name,
                    resp.status_code,
                    close_event["session_id"],
                )
        except asyncio.TimeoutError:
            logger.warning(
                "Agent %s /ingest timed out session=%s",
                agent.name,
                close_event["session_id"],
            )
        except Exception as exc:
            logger.warning(
                "Agent %s /ingest error session=%s: %s",
                agent.name,
                close_event["session_id"],
                exc,
            )
