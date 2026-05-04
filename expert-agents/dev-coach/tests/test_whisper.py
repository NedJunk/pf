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
            "history": history if history is not None else ["User: Hello", "Assistant: Hi there"],
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
def test_endpoint_returns_202_even_on_gemini_error(mock_genai):
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=Exception("API error")
    )
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    client = TestClient(DevCoach().app)
    resp = client.post("/whisper", json=_http_context())
    assert resp.status_code == 202


@patch("dev_coach.main.genai")
def test_health_returns_ok(mock_genai):
    mock_genai.Client.return_value = MagicMock()
    from dev_coach.main import DevCoach
    client = TestClient(DevCoach().app)
    assert client.get("/health").json() == {"status": "ok"}


@pytest.fixture(autouse=True)
def wiki_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("WIKI_SCHEMA_PATH", str(tmp_path / "schema.md"))


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_generate_calls_gemini_with_prompt(mock_genai):
    mock_resp = MagicMock()
    mock_resp.text = "result text"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    coach = DevCoach()
    result = await coach._generate("test prompt")
    assert result == "result text"
    mock_client.aio.models.generate_content.assert_awaited_once()


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_whisper_includes_wiki_context_in_prompt(mock_genai):
    mock_resp = MagicMock()
    mock_resp.text = "Consider pair programming."
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    from expert_agent_base.base import WhisperContext
    coach = DevCoach()
    ctx = WhisperContext(
        session_id="s1",
        history=["User: Hello", "Assistant: Hi"],
        goals=["ship MVP"],
        project_map=["voice-router"],
        wiki_context="### decisions.md\nWe use TDD.",
    )
    result = await coach.whisper(ctx)
    assert result is not None

    call_args = mock_client.aio.models.generate_content.call_args
    prompt_text = call_args.kwargs["contents"][0]["parts"][0]["text"]
    assert "We use TDD" in prompt_text


@patch("dev_coach.main.genai")
def test_roadmap_loaded_from_env(mock_genai, tmp_path, monkeypatch):
    mock_genai.Client.return_value = MagicMock()
    roadmap_file = tmp_path / "backlog.md"
    roadmap_file.write_text("# Backlog\n\n## Now\n- E4-M in progress")
    monkeypatch.setenv("ROADMAP_PATH", str(roadmap_file))

    from dev_coach.main import DevCoach
    coach = DevCoach()
    assert "E4-M" in coach._roadmap


@patch("dev_coach.main.genai")
def test_roadmap_empty_when_path_not_set(mock_genai, monkeypatch):
    mock_genai.Client.return_value = MagicMock()
    monkeypatch.delenv("ROADMAP_PATH", raising=False)

    from dev_coach.main import DevCoach
    coach = DevCoach()
    assert coach._roadmap == ""


@patch("dev_coach.main.genai")
def test_roadmap_empty_when_file_missing(mock_genai, monkeypatch):
    mock_genai.Client.return_value = MagicMock()
    monkeypatch.setenv("ROADMAP_PATH", "/does/not/exist/backlog.md")

    from dev_coach.main import DevCoach
    coach = DevCoach()
    assert coach._roadmap == ""


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_whisper_includes_roadmap_in_prompt(mock_genai, tmp_path, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.text = "Consider addressing E4-M first."
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    roadmap_file = tmp_path / "backlog.md"
    roadmap_file.write_text("## Now\n- [ ] E4-M roadmap awareness")
    monkeypatch.setenv("ROADMAP_PATH", str(roadmap_file))

    from dev_coach.main import DevCoach
    from expert_agent_base.base import WhisperContext
    coach = DevCoach()
    ctx = WhisperContext(
        session_id="s1",
        history=["User: what should I work on?", "Assistant: Good question."],
        goals=["ship MVP"],
        project_map=["voice-router"],
    )
    await coach.whisper(ctx)

    prompt_text = mock_client.aio.models.generate_content.call_args.kwargs[
        "contents"
    ][0]["parts"][0]["text"]
    assert "E4-M" in prompt_text


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_whisper_excludes_roadmap_section_when_not_set(mock_genai, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.text = "NO_WHISPER"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client
    monkeypatch.delenv("ROADMAP_PATH", raising=False)

    from dev_coach.main import DevCoach
    from expert_agent_base.base import WhisperContext
    coach = DevCoach()
    ctx = WhisperContext(
        session_id="s1",
        history=["User: Hello", "Assistant: Hi"],
        goals=["ship MVP"],
        project_map=["voice-router"],
    )
    await coach.whisper(ctx)

    prompt_text = mock_client.aio.models.generate_content.call_args.kwargs[
        "contents"
    ][0]["parts"][0]["text"]
    assert "roadmap" not in prompt_text.lower()


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_synthesize_uses_roadmap_aware_prompt(mock_genai, tmp_path, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.text = "NO_CHANGES"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    roadmap_file = tmp_path / "backlog.md"
    roadmap_file.write_text("## Now\n- [ ] E4-M active")
    monkeypatch.setenv("ROADMAP_PATH", str(roadmap_file))

    from dev_coach.main import DevCoach
    coach = DevCoach()
    await coach._synthesize()

    prompt_text = mock_client.aio.models.generate_content.call_args.kwargs[
        "contents"
    ][0]["parts"][0]["text"]
    assert "E4-M active" in prompt_text
    assert "epic" in prompt_text.lower()


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_synthesize_falls_back_to_base_when_no_roadmap(mock_genai, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.text = "NO_CHANGES"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client
    monkeypatch.delenv("ROADMAP_PATH", raising=False)

    from dev_coach.main import DevCoach
    coach = DevCoach()
    await coach._synthesize()

    prompt_text = mock_client.aio.models.generate_content.call_args.kwargs[
        "contents"
    ][0]["parts"][0]["text"]
    assert "ROADMAP" not in prompt_text
