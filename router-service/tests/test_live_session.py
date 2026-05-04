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
    mock_httpx.AsyncClient.return_value = mock_http_client

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
    session._model_generating.set()   # allow drain to proceed immediately
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

    # Whisper must use send_client_content(turn_complete=False), not
    # send_realtime_input(text=...) — the latter triggers a Gemini audio
    # response (BUG-10). See _whisper_drain comment for full decision record.
    mock_session.send_realtime_input.assert_not_called()
    client_content_calls = str(mock_session.send_client_content.call_args_list)
    assert "[WHISPER from DevCoach]" in client_content_calls
    assert "try TDD" in client_content_calls

    assert any("[Whisper from DevCoach]: try TDD" in entry for entry in session._history)


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
async def test_whisper_drain_waits_until_model_generating(mock_genai):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value

    mock_ws = AsyncMock()
    mock_ws.send_text = AsyncMock()

    session = _session()
    session._gemini_session = mock_session
    session.inject_whisper(source="DevCoach", message="try TDD")

    # _model_generating is clear — drain must block
    task = asyncio.create_task(session._whisper_drain(mock_ws))
    await asyncio.sleep(0.05)
    mock_session.send_client_content.assert_not_called()

    # Set the event — drain must now inject
    session._model_generating.set()
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    mock_session.send_client_content.assert_called_once()
    assert "[WHISPER from DevCoach]" in str(mock_session.send_client_content.call_args_list)


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_close_writes_transcript(mock_httpx, mock_genai, tmp_path):
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value
    mock_httpx.AsyncClient.return_value = AsyncMock()

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
    mock_httpx.AsyncClient.return_value = mock_http_client

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
    mock_httpx.AsyncClient.return_value = mock_http_client

    session = _session(transcript_output_dir=str(tmp_path))
    session._gemini_session = mock_session
    session._gemini_cm = MagicMock()
    session._gemini_cm.__aexit__ = AsyncMock(return_value=None)
    session._history = ["User: hello"]

    await session.close()
    assert len(list(tmp_path.glob("*.md"))) == 1


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_close_records_user_turn_before_concurrent_assistant_response(
    mock_httpx, mock_genai, tmp_path
):
    # BUG-22: when Gemini's response arrives concurrently with the user's final turn,
    # close() must write the user turn before the assistant response in history.
    mock_genai_inst, mock_session = _mock_gemini()
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value
    mock_httpx.AsyncClient.return_value = AsyncMock()

    session = _session(transcript_output_dir=str(tmp_path))
    session._gemini_session = mock_session
    session._gemini_cm = MagicMock()
    session._gemini_cm.__aexit__ = AsyncMock(return_value=None)
    session._history = ["User: earlier turn", "Assistant: earlier response"]
    session._input_buf = ["Not just yet. I'm going to end this session."]
    session._output_buf = ["Understood."]

    await session.close()

    user_idx = next(i for i, e in enumerate(session._history) if "Not just yet" in e)
    assistant_idx = next(i for i, e in enumerate(session._history) if "Understood" in e)
    assert user_idx < assistant_idx, (
        "User farewell must precede assistant response in transcript (BUG-22)"
    )


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_turn_complete_records_user_turn_before_concurrent_assistant_response(
    mock_httpx, mock_genai
):
    # BUG-22: when output_transcription for the assistant's response arrives before
    # the user's turn_complete fires, the user turn must still appear first in history.
    input_chunk = MagicMock()
    input_chunk.data = None
    input_chunk.server_content = MagicMock()
    sc_in = input_chunk.server_content
    sc_in.input_transcription = MagicMock(text="Goodbye for now.")
    sc_in.output_transcription = None
    sc_in.turn_complete = False
    sc_in.interrupted = False

    output_chunk = MagicMock()
    output_chunk.data = None
    output_chunk.server_content = MagicMock()
    sc_out = output_chunk.server_content
    sc_out.input_transcription = None
    sc_out.output_transcription = MagicMock(text="Understood.")
    sc_out.turn_complete = False
    sc_out.interrupted = False

    turn_complete_response = MagicMock()
    turn_complete_response.data = None
    turn_complete_response.server_content = MagicMock()
    sc_tc = turn_complete_response.server_content
    sc_tc.input_transcription = None
    sc_tc.output_transcription = None
    sc_tc.turn_complete = True
    sc_tc.interrupted = False

    mock_genai_inst, mock_session = _mock_gemini(
        responses=[input_chunk, output_chunk, turn_complete_response]
    )
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value
    mock_httpx.AsyncClient.return_value = AsyncMock()

    mock_ws = AsyncMock()
    mock_ws.send_text = AsyncMock()
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

    user_idx = next(
        (i for i, e in enumerate(session._history) if e.startswith("User:")), None
    )
    assistant_idx = next(
        (i for i, e in enumerate(session._history) if e.startswith("Assistant:")), None
    )
    assert user_idx is not None and assistant_idx is not None
    assert user_idx < assistant_idx, (
        "User turn must precede concurrent assistant response in history (BUG-22)"
    )


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_output_transcription_drops_whisper_pollution(mock_httpx, mock_genai):
    # BUG-12: send_client_content(turn_complete=False) causes Gemini to echo whisper
    # text as output_transcription. Verify these events are dropped — not written to
    # _output_buf, _history, or sent to the browser as transcript frames.
    whisper_response = MagicMock()
    whisper_response.data = None
    whisper_response.server_content = MagicMock()
    whisper_response.server_content.input_transcription = None
    sc = whisper_response.server_content
    sc.output_transcription = MagicMock()
    sc.output_transcription.text = "[WHISPER from DevCoach]: use TDD for this fix"
    sc.turn_complete = False
    sc.interrupted = False

    mock_genai_inst, mock_session = _mock_gemini(responses=[whisper_response])
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value
    mock_httpx.AsyncClient.return_value = AsyncMock()

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

    assert session._output_buf == []
    assert not any("[WHISPER from" in entry for entry in session._history)
    whisper_transcript_frames = [
        t for t in sent_texts if "[WHISPER from" in t
    ]
    assert whisper_transcript_frames == []


def _make_response(input_text=None, output_text=None, turn_complete=False, interrupted=False):
    r = MagicMock()
    r.data = None
    sc = MagicMock()
    r.server_content = sc
    sc.input_transcription = MagicMock(text=input_text) if input_text else None
    sc.output_transcription = MagicMock(text=output_text) if output_text else None
    sc.turn_complete = turn_complete
    sc.interrupted = interrupted
    return r


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_multipart_whisper_echo_continuation_is_dropped(mock_httpx, mock_genai):
    # BUG-19: Gemini splits the whisper echo across multiple output_transcription chunks.
    # The first chunk starts with "[WHISPER from" and is caught by the existing filter.
    # The second chunk starts with the source name ("insight_engine]: ...") and must
    # also be suppressed via the _in_whisper_echo state flag.
    #
    # In practice, Gemini sends the whisper echo as its own sequence terminated by a
    # turn_complete; the real assistant response arrives in a separate sequence after
    # the next user turn. This test covers the intra-echo suppression only.
    chunk1 = _make_response(output_text="[WHISPER from ")
    chunk2 = _make_response(output_text="insight_engine]: User is seeking tools for X")
    echo_turn_complete = _make_response(turn_complete=True)
    # After echo turn_complete, _in_whisper_echo resets; real response is unaffected.
    real_response = _make_response(output_text="What specifically triggered that idea?")
    real_turn_complete = _make_response(turn_complete=True)

    mock_genai_inst, mock_session = _mock_gemini(
        responses=[chunk1, chunk2, echo_turn_complete, real_response, real_turn_complete]
    )
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value
    mock_httpx.AsyncClient.return_value = AsyncMock()

    mock_ws = AsyncMock()
    sent_texts = []
    mock_ws.send_text = AsyncMock(side_effect=lambda t: sent_texts.append(t))
    mock_ws.send_bytes = AsyncMock()

    session = _session()
    session._gemini_session = mock_session

    task = asyncio.create_task(session._gemini_to_browser(mock_ws))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert "insight_engine" not in " ".join(session._output_buf)
    assert "insight_engine" not in " ".join(session._history)
    assert not any("insight_engine" in t for t in sent_texts if '"role": "assistant"' in t)
    real_output = [e for e in session._history if "What specifically" in e]
    assert real_output, "real assistant response after whisper echo turn_complete must be kept"


@pytest.mark.asyncio
@patch("router_service.live_session.genai")
@patch("router_service.live_session.httpx")
async def test_model_generating_not_cleared_on_empty_assistant_turn_complete(
    mock_httpx, mock_genai
):
    # BUG-23: after an interrupted event, _output_buf is flushed immediately. If a
    # subsequent turn_complete fires on the assistant branch with _output_buf already
    # empty, _model_generating must NOT be cleared — clearing it would block
    # _whisper_drain for the next real user turn.
    user_chunk = _make_response(input_text="Tell me more.")
    user_turn_complete = _make_response(input_text=None, turn_complete=True)
    # Simulate: output starts arriving, user interrupts, then aborted turn_complete
    output_chunk = _make_response(output_text="Sure, I can —")
    interrupted_event = _make_response(interrupted=True)
    aborted_turn_complete = _make_response(turn_complete=True)  # assistant branch, buf already empty

    mock_genai_inst, mock_session = _mock_gemini(
        responses=[user_chunk, user_turn_complete, output_chunk, interrupted_event, aborted_turn_complete]
    )
    mock_genai.Client.return_value = mock_genai_inst.Client.return_value
    mock_httpx.AsyncClient.return_value = AsyncMock()

    mock_ws = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.send_bytes = AsyncMock()

    session = _session()
    session._gemini_session = mock_session

    task = asyncio.create_task(session._gemini_to_browser(mock_ws))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert session._model_generating.is_set(), (
        "_model_generating must remain set after an interrupted+empty assistant turn_complete (BUG-23)"
    )
