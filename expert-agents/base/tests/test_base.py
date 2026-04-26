import pytest
from fastapi.testclient import TestClient
from expert_agent_base.base import ExpertAgentBase, WhisperContext, WhisperResponse


class ConcreteAgent(ExpertAgentBase):
    async def whisper(self, context: WhisperContext) -> WhisperResponse:
        return WhisperResponse(source="Test", message="hello", confidence=0.9)


class SilentAgent(ExpertAgentBase):
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
        async def whisper(self, context):
            raise RuntimeError("LLM unavailable")

    client = TestClient(BrokenAgent(model="m").app)
    resp = client.post("/whisper", json=_context())
    assert resp.status_code == 503
