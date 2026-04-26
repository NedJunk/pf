import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from orchestrator.agent_registry import AgentConfig
from orchestrator.turn_handler import handle_turn


def _event():
    return {
        "session_id": "s1",
        "history_tail": ["User: hello", "Assistant: hi"],
        "goals": ["goal1"],
        "project_map": ["mod1"],
    }


def _monitor(healthy=True):
    m = MagicMock()
    m.is_healthy.return_value = healthy
    return m


def _agent():
    return AgentConfig(name="DevCoach", url="http://dev-coach:8082")


@pytest.mark.asyncio
async def test_no_call_when_all_agents_unhealthy():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"source": "DevCoach", "message": "try TDD", "confidence": 0.8}
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(healthy=False), 0.5, 2, "http://r:8080")
    assert len(posted) == 0


@pytest.mark.asyncio
async def test_forwards_passing_whisper_to_router():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"source": "DevCoach", "message": "try TDD", "confidence": 0.8}
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 2, "http://router:8080")

    assert any("dev-coach" in u for u in posted)
    assert any("router" in u and "whisper" in u for u in posted)


@pytest.mark.asyncio
async def test_drops_whisper_below_confidence_threshold():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"source": "DevCoach", "message": "maybe", "confidence": 0.3}
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 2, "http://router:8080")

    assert not any("router" in u for u in posted)


@pytest.mark.asyncio
async def test_skips_204_from_agent():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 204
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 2, "http://router:8080")

    assert not any("router" in u for u in posted)
