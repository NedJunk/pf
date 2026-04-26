import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from orchestrator.agent_registry import AgentConfig
from orchestrator.health_monitor import HealthMonitor


def _agents():
    return [AgentConfig(name="Agent1", url="http://agent1:8082")]


def _mock_http_client(status_code=200, raises=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_client = AsyncMock()
    if raises:
        mock_client.get = AsyncMock(side_effect=raises)
    else:
        mock_client.get = AsyncMock(return_value=mock_resp)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_all_agents_start_healthy():
    monitor = HealthMonitor(_agents())
    assert monitor.is_healthy("Agent1")


@pytest.mark.asyncio
async def test_agent_marked_unhealthy_on_connection_error():
    monitor = HealthMonitor(_agents())
    with patch("orchestrator.health_monitor.httpx.AsyncClient",
               return_value=_mock_http_client(raises=Exception("refused"))):
        await monitor._poll_all()
    assert not monitor.is_healthy("Agent1")


@pytest.mark.asyncio
async def test_agent_marked_unhealthy_on_non_200():
    monitor = HealthMonitor(_agents())
    with patch("orchestrator.health_monitor.httpx.AsyncClient",
               return_value=_mock_http_client(status_code=503)):
        await monitor._poll_all()
    assert not monitor.is_healthy("Agent1")


@pytest.mark.asyncio
async def test_agent_recovers_after_successful_poll():
    monitor = HealthMonitor(_agents())
    monitor._healthy.discard("Agent1")
    with patch("orchestrator.health_monitor.httpx.AsyncClient",
               return_value=_mock_http_client(status_code=200)):
        await monitor._poll_all()
    assert monitor.is_healthy("Agent1")
