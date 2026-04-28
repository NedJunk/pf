import pytest
from unittest.mock import MagicMock, patch
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


def _context():
    return {
        "session_id": "s1",
        "context": {"history": ["User: hi"], "goals": [], "project_map": []},
    }


def test_cannot_instantiate_base_directly():
    with pytest.raises(TypeError):
        ExpertAgentBase(model="any")


def test_health_endpoint_returns_ok():
    client = TestClient(ConcreteAgent(model="m").app)
    assert client.get("/health").json() == {"status": "ok"}


def test_whisper_endpoint_returns_200_with_payload():
    client = TestClient(ConcreteAgent(model="m").app)
    resp = client.post("/whisper", json=_context())
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "Test"
    assert data["message"] == "hello"
    assert data["confidence"] == 0.9


def test_whisper_endpoint_returns_204_when_none():
    client = TestClient(SilentAgent(model="m").app)
    resp = client.post("/whisper", json=_context())
    assert resp.status_code == 204


def test_whisper_endpoint_returns_503_on_exception():
    class BrokenAgent(ExpertAgentBase):
        async def _generate(self, prompt: str) -> str:
            return ""
        async def whisper(self, context):
            raise RuntimeError("LLM unavailable")

    client = TestClient(BrokenAgent(model="m").app)
    resp = client.post("/whisper", json=_context())
    assert resp.status_code == 503


def test_ingest_endpoint_returns_202():
    client = TestClient(ConcreteAgent(model="m").app)
    resp = client.post("/ingest", json={"session_id": "s1", "transcript": "User: hello"})
    assert resp.status_code == 202


def test_whisper_context_has_wiki_context_field():
    ctx = WhisperContext(session_id="s1", history=[], goals=[], project_map=[])
    assert ctx.wiki_context == ""
