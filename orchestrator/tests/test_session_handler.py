import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from orchestrator.agent_registry import AgentConfig
from orchestrator.session_handler import handle_session_close
import orchestrator.session_handler as _sh


@pytest.fixture(autouse=True)
def reset_ingested_sessions():
    _sh._ingested_sessions.clear()
    yield
    _sh._ingested_sessions.clear()


def _event():
    return {"session_id": "s1", "transcript": "User: hello\nAssistant: hi"}


def _monitor(healthy=True):
    m = MagicMock()
    m.is_healthy.return_value = healthy
    return m


def _agent():
    return AgentConfig(name="DevCoach", url="http://dev-coach:8082")


@pytest.mark.asyncio
async def test_fans_out_ingest_to_healthy_agents():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 202
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        await handle_session_close(_event(), [_agent()], _monitor(), timeout=2)

    assert any("dev-coach" in u and "ingest" in u for u in posted)


@pytest.mark.asyncio
async def test_skips_unhealthy_agents():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 202
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        await handle_session_close(_event(), [_agent()], _monitor(healthy=False), timeout=2)

    assert len(posted) == 0


@pytest.mark.asyncio
async def test_logs_and_continues_on_agent_error():
    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        call_count += 1
        raise Exception("agent down")

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        await handle_session_close(_event(), [_agent()], _monitor(), timeout=2)

    assert call_count == 1


@pytest.mark.asyncio
async def test_duplicate_close_event_does_not_double_ingest():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 202
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        await handle_session_close(_event(), [_agent()], _monitor(), timeout=2)
        await handle_session_close(_event(), [_agent()], _monitor(), timeout=2)

    ingest_calls = [u for u in posted if "ingest" in u]
    assert len(ingest_calls) == 1


@pytest.mark.asyncio
async def test_logs_non_202_response():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 500
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("orchestrator.session_handler.httpx.AsyncClient", return_value=cm):
        await handle_session_close(_event(), [_agent()], _monitor(), timeout=2)

    assert len(posted) == 1
