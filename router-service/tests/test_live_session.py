import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from router_service.live_session import LiveSession


def _session(**kwargs):
    defaults = dict(
        session_id="test-id",
        project_map=["auth module"],
        goals=["ship MVP"],
        api_key="test-key",
        orchestrator_url="http://orchestrator:8081",
        transcript_output_dir="/tmp/transcripts",
        history_tail_length=10,
        live_api_model="gemini-test-model",
    )
    defaults.update(kwargs)
    return LiveSession(**defaults)


def _mock_gemini(responses=None):
    """Returns (mock_genai, mock_gemini_session)."""
    mock_session = AsyncMock()
    mock_session.send_realtime_input = AsyncMock()

    async def _receive():
        for r in (responses or []):
            yield r
        await asyncio.get_running_loop().create_future()  # block until cancelled

    mock_session.receive = _receive

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.aio.live.connect.return_value = mock_cm

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    return mock_genai, mock_session


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_connect_opens_gemini_session_without_context_injection(mock_genai):
    _, mock_session = _mock_gemini()
    mock_genai.Client.return_value.aio.live.connect.return_value.__aenter__ = (
        AsyncMock(return_value=mock_session)
    )
    mock_genai.Client.return_value.aio.live.connect.return_value.__aexit__ = (
        AsyncMock(return_value=None)
    )

    session = _session()
    await session.connect()

    mock_genai.Client.return_value.aio.live.connect.assert_called_once()
    call_kwargs = mock_genai.Client.return_value.aio.live.connect.call_args
    assert call_kwargs.kwargs["model"] == "gemini-test-model"

    # No context injected at connect — Router asks verbally
    mock_session.send_realtime_input.assert_not_called()


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_turn_complete_sends_control_frame_and_posts_turn_event(mock_httpx, mock_genai):
    turn_complete_response = MagicMock()
    turn_complete_response.server_content = MagicMock()
    turn_complete_response.server_content.model_turn = None
    turn_complete_response.server_content.input_transcription = None
    turn_complete_response.server_content.output_transcription = None
    turn_complete_response.server_content.turn_complete = True
    turn_complete_response.server_content.interrupted = False

    mock_genai_inst, mock_session = _mock_gemini(responses=[turn_complete_response])
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock()
    mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_ws = AsyncMock()
    sent_texts = []
    mock_ws.send_text = AsyncMock(side_effect=lambda t: sent_texts.append(t))
    mock_ws.send_bytes = AsyncMock()
    mock_ws.receive = AsyncMock(side_effect=asyncio.CancelledError)

    session = _session()
    session._gemini_session = mock_session

    task = asyncio.create_task(session._gemini_to_browser(mock_ws))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    frames = [json.loads(t) for t in sent_texts]
    assert any(f["type"] == "turn_complete" for f in frames)
    mock_http_client.post.assert_called()


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_whisper_drain_sends_control_frame_then_injects_to_gemini(mock_genai):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    mock_ws = AsyncMock()
    sent_texts = []
    mock_ws.send_text = AsyncMock(side_effect=lambda t: sent_texts.append(t))

    session = _session()
    session._gemini_session = mock_session
    session.inject_whisper(source="DevCoach", message="try TDD")

    task = asyncio.create_task(session._whisper_drain(mock_ws))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    frames = [json.loads(t) for t in sent_texts]
    whisper_frames = [f for f in frames if f["type"] == "whisper"]
    assert len(whisper_frames) == 1
    assert whisper_frames[0]["source"] == "DevCoach"
    assert whisper_frames[0]["message"] == "try TDD"

    gemini_calls = str(mock_session.send_realtime_input.call_args_list)
    assert "[WHISPER from DevCoach]" in gemini_calls
    assert "try TDD" in gemini_calls


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_close_writes_transcript(mock_genai, tmp_path):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    session = _session(transcript_output_dir=str(tmp_path))
    session._gemini_session = mock_session
    session._gemini_cm = MagicMock()
    session._gemini_cm.__aexit__ = AsyncMock(return_value=None)
    session._history = ["User: hello", "Assistant: hi"]

    await session.close()

    transcript_file = tmp_path / "test-id.md"
    assert transcript_file.exists()
    content = transcript_file.read_text()
    assert "User: hello" in content
    assert "Assistant: hi" in content
