import asyncio
import logging
import httpx
from orchestrator.agent_registry import AgentConfig
from orchestrator.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)

_ingested_sessions: set[str] = set()


async def handle_session_close(
    close_event: dict,
    agents: list[AgentConfig],
    health_monitor: HealthMonitor,
    timeout: int,
) -> None:
    session_id = close_event["session_id"]
    if session_id in _ingested_sessions:
        logger.warning(
            "Duplicate close event for session=%s — skipping ingest", session_id
        )
        return
    _ingested_sessions.add(session_id)

    healthy = [a for a in agents if health_monitor.is_healthy(a.name)]
    if not healthy:
        logger.warning(
            "No healthy agents for session close session=%s", session_id
        )
        return

    await asyncio.gather(
        *[_call_ingest(a, close_event, timeout) for a in healthy],
        return_exceptions=True,
    )


async def _call_ingest(agent: AgentConfig, close_event: dict, timeout: int) -> None:
    session_id = close_event["session_id"]
    payload = {
        "session_id": session_id,
        "transcript": close_event["transcript"],
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{agent.url}/ingest", json=payload, timeout=float(timeout)
            )
            if resp.status_code == 202:
                logger.info(
                    "Agent %s /ingest accepted session=%s", agent.name, session_id
                )
            else:
                logger.warning(
                    "Agent %s /ingest returned %s session=%s",
                    agent.name,
                    resp.status_code,
                    session_id,
                )
        except httpx.TimeoutException:
            logger.warning(
                "Agent %s /ingest timed out session=%s", agent.name, session_id
            )
        except Exception as exc:
            logger.warning(
                "Agent %s /ingest error session=%s: %s", agent.name, session_id, exc
            )
