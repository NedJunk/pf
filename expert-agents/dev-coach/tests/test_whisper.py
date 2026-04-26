import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from expert_agent_base.base import WhisperContext


def _context(history=None):
    return WhisperContext(
        session_id="s1",
        history=history if history is not None else ["User: Hello", "Assistant: Hi there"],
        goals=["ship MVP"],
        project_map=["voice-router"],
    )


def _http_context(history=None):
    return {
        "session_id": "s1",
        "context": {
            "history": history or ["User: Hello", "Assistant: Hi there"],
            "goals": ["ship MVP"],
            "project_map": ["voice-router"],
        },
    }


@patch("dev_coach.main.genai")
def test_whisper_returns_none_for_empty_history(mock_genai):
    mock_genai.Client.return_value = MagicMock()
    from dev_coach.main import DevCoach
    coach = DevCoach()
    import asyncio
    result = asyncio.run(coach.whisper(_context(history=[])))
    assert result is None
    mock_genai.Client.return_value.aio.models.generate_content.assert_not_called()


@patch("dev_coach.main.genai")
def test_whisper_returns_none_for_single_history_entry(mock_genai):
    mock_genai.Client.return_value = MagicMock()
    from dev_coach.main import DevCoach
    coach = DevCoach()
    import asyncio
    result = asyncio.run(coach.whisper(_context(history=["User: hello"])))
    assert result is None


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_whisper_returns_response_on_suggestion(mock_genai):
    mock_resp = MagicMock()
    mock_resp.text = "Consider writing the test first."
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    coach = DevCoach()
    result = await coach.whisper(_context())

    assert result is not None
    assert result.source == "DevCoach"
    assert result.message == "Consider writing the test first."
    assert result.confidence == 0.8


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_whisper_returns_none_for_no_whisper_response(mock_genai):
    mock_resp = MagicMock()
    mock_resp.text = "NO_WHISPER"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    coach = DevCoach()
    assert await coach.whisper(_context()) is None


@patch("dev_coach.main.genai")
def test_endpoint_returns_503_on_gemini_error(mock_genai):
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=Exception("API error")
    )
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    client = TestClient(DevCoach().app)
    resp = client.post("/whisper", json=_http_context())
    assert resp.status_code == 503


@patch("dev_coach.main.genai")
def test_health_returns_ok(mock_genai):
    mock_genai.Client.return_value = MagicMock()
    from dev_coach.main import DevCoach
    client = TestClient(DevCoach().app)
    assert client.get("/health").json() == {"status": "ok"}
