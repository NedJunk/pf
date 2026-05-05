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
    return AgentConfig(name="DevCoach", url="http://dev-coach:8082", tags=[])


def _mock_client_cm(status_code=202):
    async def mock_post(url, **kwargs):
        resp = MagicMock()
        resp.status_code = status_code
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, mock_client


@pytest.mark.asyncio
async def test_no_call_when_all_agents_unhealthy():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 202
        return resp

    cm, mock_client = _mock_client_cm()
    mock_client.post = mock_post

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(healthy=False), 0.5, 5, "http://r:8080", routing_threshold=0.0)

    assert len(posted) == 0


@pytest.mark.asyncio
async def test_dispatches_to_agent_with_callback_url():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append((url, kwargs.get("json", {})))
        resp = MagicMock()
        resp.status_code = 202
        return resp

    cm, mock_client = _mock_client_cm()
    mock_client.post = mock_post

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 5, "http://router:8080", routing_threshold=0.0)

    assert len(posted) == 1
    url, payload = posted[0]
    assert "dev-coach" in url
    assert payload["callback_url"] == "http://router:8080/sessions/s1/whisper"
    assert payload["confidence_threshold"] == 0.5


@pytest.mark.asyncio
async def test_does_not_post_to_router_directly():
    posted_urls = []

    async def mock_post(url, **kwargs):
        posted_urls.append(url)
        resp = MagicMock()
        resp.status_code = 202
        return resp

    cm, mock_client = _mock_client_cm()
    mock_client.post = mock_post

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 5, "http://router:8080", routing_threshold=0.0)

    assert not any("router" in u for u in posted_urls), (
        "Orchestrator should not POST to router — agent calls back directly"
    )


@pytest.mark.asyncio
async def test_confidence_threshold_passed_to_agent():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(kwargs.get("json", {}))
        resp = MagicMock()
        resp.status_code = 202
        return resp

    cm, mock_client = _mock_client_cm()
    mock_client.post = mock_post

    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        await handle_turn(_event(), [_agent()], _monitor(), 0.8, 5, "http://router:8080", routing_threshold=0.0)

    assert posted[0]["confidence_threshold"] == 0.8


@pytest.mark.asyncio
async def test_logs_warning_on_non_202_response():
    cm, _ = _mock_client_cm(status_code=500)
    with patch("orchestrator.turn_handler.httpx.AsyncClient", return_value=cm):
        # should not raise
        await handle_turn(_event(), [_agent()], _monitor(), 0.5, 5, "http://router:8080", routing_threshold=0.0)
