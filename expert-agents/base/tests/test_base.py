import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from expert_agent_base.base import ExpertAgentBase, WhisperContext, WhisperResponse


@pytest.fixture(autouse=True)
def wiki_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("WIKI_SCHEMA_PATH", str(tmp_path / "schema.md"))


class ConcreteAgent(ExpertAgentBase):
    async def _generate(self, prompt: str) -> str:
        return ""

    async def whisper(self, context: WhisperContext) -> WhisperResponse:
        return WhisperResponse(source="Test", message="hello", confidence=0.9)


class SilentAgent(ExpertAgentBase):
    async def _generate(self, prompt: str) -> str:
        return ""

    async def whisper(self, context: WhisperContext) -> None:
        return None


def _body(callback_url="http://router:8080/sessions/s1/whisper", confidence_threshold=0.5):
    return {
        "session_id": "s1",
        "context": {"history": ["User: hi"], "goals": [], "project_map": []},
        "callback_url": callback_url,
        "confidence_threshold": confidence_threshold,
    }


def test_cannot_instantiate_base_directly():
    with pytest.raises(TypeError):
        ExpertAgentBase(model="any")


def test_health_endpoint_returns_ok():
    client = TestClient(ConcreteAgent(model="m").app)
    assert client.get("/health").json() == {"status": "ok"}


def test_whisper_endpoint_returns_202():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append((url, kwargs))
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("expert_agent_base.base.httpx.AsyncClient", return_value=cm):
        client = TestClient(ConcreteAgent(model="m").app)
        resp = client.post("/whisper", json=_body())

    assert resp.status_code == 202


def test_whisper_endpoint_delivers_callback_when_above_threshold():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append((url, kwargs))
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("expert_agent_base.base.httpx.AsyncClient", return_value=cm):
        client = TestClient(ConcreteAgent(model="m").app)
        client.post("/whisper", json=_body(confidence_threshold=0.5))

    assert len(posted) == 1
    url, kwargs = posted[0]
    assert url == "http://router:8080/sessions/s1/whisper"
    assert kwargs["json"]["source"] == "Test"
    assert kwargs["json"]["message"] == "hello"


def test_whisper_endpoint_no_callback_when_below_threshold():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("expert_agent_base.base.httpx.AsyncClient", return_value=cm):
        client = TestClient(ConcreteAgent(model="m").app)
        client.post("/whisper", json=_body(confidence_threshold=0.95))

    assert len(posted) == 0


def test_whisper_endpoint_no_callback_when_silent():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("expert_agent_base.base.httpx.AsyncClient", return_value=cm):
        client = TestClient(SilentAgent(model="m").app)
        resp = client.post("/whisper", json=_body())

    assert resp.status_code == 202
    assert len(posted) == 0


def test_whisper_endpoint_no_callback_on_exception():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    class BrokenAgent(ExpertAgentBase):
        async def _generate(self, prompt: str) -> str:
            return ""
        async def whisper(self, context):
            raise RuntimeError("LLM unavailable")

    with patch("expert_agent_base.base.httpx.AsyncClient", return_value=cm):
        client = TestClient(BrokenAgent(model="m").app)
        resp = client.post("/whisper", json=_body())

    assert resp.status_code == 202
    assert len(posted) == 0


def test_whisper_endpoint_no_callback_without_callback_url():
    posted = []

    async def mock_post(url, **kwargs):
        posted.append(url)
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)

    body = {"session_id": "s1", "context": {"history": ["User: hi"], "goals": [], "project_map": []}}
    with patch("expert_agent_base.base.httpx.AsyncClient", return_value=cm):
        client = TestClient(ConcreteAgent(model="m").app)
        resp = client.post("/whisper", json=body)

    assert resp.status_code == 202
    assert len(posted) == 0


def test_ingest_endpoint_returns_202():
    client = TestClient(ConcreteAgent(model="m").app)
    resp = client.post("/ingest", json={"session_id": "s1", "transcript": "User: hello"})
    assert resp.status_code == 202


def test_whisper_context_has_wiki_context_field():
    ctx = WhisperContext(session_id="s1", history=[], goals=[], project_map=[])
    assert ctx.wiki_context == ""
