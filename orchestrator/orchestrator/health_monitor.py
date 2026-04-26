import asyncio
import logging
import httpx
from orchestrator.agent_registry import AgentConfig

logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 30


class HealthMonitor:
    def __init__(self, agents: list[AgentConfig]) -> None:
        self._agents = agents
        self._healthy: set[str] = {a.name for a in agents}
        self._task: asyncio.Task | None = None

    def is_healthy(self, name: str) -> bool:
        return name in self._healthy

    def start(self) -> None:
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            await self._poll_all()

    async def _poll_all(self) -> None:
        async with httpx.AsyncClient() as client:
            for agent in self._agents:
                try:
                    resp = await client.get(f"{agent.url}/health", timeout=5.0)
                    if resp.status_code == 200:
                        self._healthy.add(agent.name)
                    else:
                        self._healthy.discard(agent.name)
                        logger.warning("Agent %s unhealthy: %s", agent.name, resp.status_code)
                except Exception as exc:
                    self._healthy.discard(agent.name)
                    logger.warning("Agent %s unreachable: %s", agent.name, exc)
