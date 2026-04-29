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


@patch("router_service.live_session.genai")
def test_flush_output_buf_creates_new_assistant_entry(mock_genai):
    session = _session()
    session._output_buf = ["Hello ", "there"]
    session._flush_output_buf()
    assert session._history == ["Assistant: Hello there"]
    assert session._output_buf == []


@patch("router_service.live_session.genai")
def test_flush_output_buf_coalesces_consecutive_assistant_turns(mock_genai):
    session = _session()
    session._history = ["Assistant: Hello there"]
    session._output_buf = [" how are you"]
    session._flush_output_buf()
    assert session._history == ["Assistant: Hello there how are you"]
    assert session._output_buf == []


@patch("router_service.live_session.genai")
def test_flush_output_buf_inserts_space_between_coalesced_chunks(mock_genai):
    # Reproduces the run-on pattern from session 15383d0b where consecutive
    # flushes produced "...Epic 3B.Are there any..." with no separator.
    session = _session()
    session._history = ["Assistant: First thought."]
    session._output_buf = ["Second thought."]
    session._flush_output_buf()
    assert session._history == ["Assistant: First thought. Second thought."]


@patch("router_service.live_session.genai")
def test_flush_output_buf_coalesces_past_whisper_entries(mock_genai):
    # Reproduces BUG-07: _whisper_drain appends a [Whisper from ...] entry
    # between two consecutive assistant turn_completes. The second flush must
    # still coalesce into the earlier Assistant: entry, not start a new one.
    session = _session()
    session._history = [
        "Assistant: under investigation.",
        "[Whisper from DevCoach]: have you tried restarting?",
    ]
    session._output_buf = ["Are you creating a test plan?"]
    session._flush_output_buf()
    assert len(session._history) == 2
    assert session._history[0] == "Assistant: under investigation. Are you creating a test plan?"
    assert session._history[1].startswith("[Whisper from DevCoach]")


@patch("router_service.live_session.genai")
def test_flush_output_buf_does_not_coalesce_after_user_entry(mock_genai):
    session = _session()
    session._history = ["User: hi"]
    session._output_buf = ["Hello there"]
    session._flush_output_buf()
    assert session._history == ["User: hi", "Assistant: Hello there"]
    assert session._output_buf == []


@patch("router_service.live_session.genai")
def test_flush_output_buf_noop_when_empty(mock_genai):
    session = _session()
    session._history = ["User: hi"]
    session._flush_output_buf()
    assert session._history == ["User: hi"]


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_connect_appends_backlog_to_system_instruction(mock_genai, tmp_path):
    backlog_file = tmp_path / "backlog.md"
    backlog_file.write_text("# Backlog\n- BUG-04 conditional opener\n")

    _, mock_session = _mock_gemini()
    mock_genai.Client.return_value.aio.live.connect.return_value.__aenter__ = (
        AsyncMock(return_value=mock_session)
    )
    mock_genai.Client.return_value.aio.live.connect.return_value.__aexit__ = (
        AsyncMock(return_value=None)
    )

    session = _session(backlog_path=str(backlog_file))
    await session.connect()

    call_kwargs = mock_genai.Client.return_value.aio.live.connect.call_args
    si = call_kwargs.kwargs["config"]["system_instruction"]
    assert "BUG-04 conditional opener" in si
    assert "Current Project Backlog" in si


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_connect_skips_backlog_when_path_missing(mock_genai):
    _, mock_session = _mock_gemini()
    mock_genai.Client.return_value.aio.live.connect.return_value.__aenter__ = (
        AsyncMock(return_value=mock_session)
    )
    mock_genai.Client.return_value.aio.live.connect.return_value.__aexit__ = (
        AsyncMock(return_value=None)
    )

    session = _session(backlog_path="/nonexistent/backlog.md")
    await session.connect()

    call_kwargs = mock_genai.Client.return_value.aio.live.connect.call_args
    si = call_kwargs.kwargs["config"]["system_instruction"]
    assert "Current Project Backlog" not in si


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

    assert any("[Whisper from DevCoach]: try TDD" in entry for entry in session._history)


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

    transcripts = list(tmp_path.glob("*.md"))
    assert len(transcripts) == 1
    content = transcripts[0].read_text()
    assert "User: hello" in content
    assert "Assistant: hi" in content


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_close_notifies_orchestrator_with_transcript(mock_httpx, mock_genai, tmp_path):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    posted = []

    async def mock_post(url, **kwargs):
        posted.append((url, kwargs))
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_http_client = AsyncMock()
    mock_http_client.post = mock_post
    mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)

    session = _session(transcript_output_dir=str(tmp_path))
    session._gemini_session = mock_session
    session._gemini_cm = MagicMock()
    session._gemini_cm.__aexit__ = AsyncMock(return_value=None)
    session._history = ["User: hello", "Assistant: hi"]

    await session.close()

    session_close_calls = [
        (url, kw) for url, kw in posted
        if "sessions" in url and "close" in url
    ]
    assert len(session_close_calls) == 1
    url, kwargs = session_close_calls[0]
    assert "test-id" in url
    assert "transcript" in kwargs["json"]
    assert "User: hello" in kwargs["json"]["transcript"]


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_close_succeeds_even_if_orchestrator_unreachable(mock_httpx, mock_genai, tmp_path):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    async def mock_post(url, **kwargs):
        raise Exception("connection refused")

    mock_http_client = AsyncMock()
    mock_http_client.post = mock_post
    mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)

    session = _session(transcript_output_dir=str(tmp_path))
    session._gemini_session = mock_session
    session._gemini_cm = MagicMock()
    session._gemini_cm.__aexit__ = AsyncMock(return_value=None)
    session._history = ["User: hello"]

    await session.close()
    assert len(list(tmp_path.glob("*.md"))) == 1
