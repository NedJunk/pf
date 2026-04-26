import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("router_service.main.registry") as mock_reg:
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.inject_whisper = MagicMock()
        mock_reg.create.return_value = "test-session-id"
        mock_reg.get.return_value = mock_session
        from router_service.main import app
        yield TestClient(app), mock_reg, mock_session


def test_post_sessions_returns_session_id(client):
    test_client, mock_reg, _ = client
    resp = test_client.post("/sessions", json={"project_map": ["mod1"], "goals": ["g1"]})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "test-session-id"
    mock_reg.create.assert_called_once_with(project_map=["mod1"], goals=["g1"])


def test_post_whisper_to_existing_session(client):
    test_client, _, mock_session = client
    resp = test_client.post(
        "/sessions/test-session-id/whisper",
        json={"source": "DevCoach", "message": "try TDD"},
    )
    assert resp.status_code == 200
    mock_session.inject_whisper.assert_called_once_with(source="DevCoach", message="try TDD")


def test_post_whisper_to_unknown_session_returns_404(client):
    test_client, mock_reg, _ = client
    mock_reg.get.return_value = None
    resp = test_client.post(
        "/sessions/bad-id/whisper",
        json={"source": "DevCoach", "message": "hi"},
    )
    assert resp.status_code == 404


def test_delete_session_calls_close(client):
    test_client, mock_reg, mock_session = client
    resp = test_client.delete("/sessions/test-session-id")
    assert resp.status_code == 200
    mock_session.close.assert_called_once()
    mock_reg.remove.assert_called_once_with("test-session-id")


def test_health_returns_ok(client):
    test_client, _, _ = client
    resp = test_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
