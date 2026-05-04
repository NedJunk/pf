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


# --- BUG-17: whisper deduplication ---

@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_near_duplicate_whisper_is_suppressed(mock_genai):
    # BUG-17: DevCoach was sending near-identical whispers on consecutive turns.
    # The Jaccard similarity filter must suppress a second whisper whose word overlap
    # with the first exceeds the threshold.
    mock_resp = MagicMock()
    mock_resp.text = "Write a test before fixing the bug to lock in expected behavior."
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    from expert_agent_base.base import WhisperContext
    coach = DevCoach()
    ctx = WhisperContext(
        session_id="dup-session",
        history=["User: fixing a bug", "Assistant: tell me more"],
        goals=["ship MVP"],
        project_map=["voice-router"],
    )

    first = await coach.whisper(ctx)
    assert first is not None

    second = await coach.whisper(ctx)
    assert second is None, "near-duplicate whisper on same session must be suppressed"


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_distinct_whisper_is_not_suppressed(mock_genai):
    # BUG-17: a genuinely different suggestion must still be delivered even after
    # a previous whisper was sent in the same session.
    first_resp = MagicMock()
    first_resp.text = "Write a test before fixing the bug."
    second_resp = MagicMock()
    second_resp.text = "Consider extracting the retry logic into a helper function."
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=[first_resp, second_resp]
    )
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    from expert_agent_base.base import WhisperContext
    coach = DevCoach()

    def _ctx(sid="distinct-session"):
        return WhisperContext(
            session_id=sid,
            history=["User: working on auth module", "Assistant: tell me more"],
            goals=["ship MVP"],
            project_map=["voice-router"],
        )

    first = await coach.whisper(_ctx())
    assert first is not None

    second = await coach.whisper(_ctx())
    assert second is not None, "distinct suggestion must not be suppressed"


@pytest.mark.asyncio
@patch("dev_coach.main.genai")
async def test_recent_suggestions_injected_into_prompt(mock_genai):
    # BUG-17: prompt-side deduplication — recent whispers must be listed in the
    # prompt so the model can avoid repeating itself proactively.
    mock_resp = MagicMock()
    mock_resp.text = "Consider breaking the work into smaller commits."
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    mock_genai.Client.return_value = mock_client

    from dev_coach.main import DevCoach
    from expert_agent_base.base import WhisperContext
    coach = DevCoach()
    sid = "prompt-injection-session"
    coach._session_whispers[sid] = ["Write a test before the fix."]

    ctx = WhisperContext(
        session_id=sid,
        history=["User: debugging now", "Assistant: what specifically?"],
        goals=["ship MVP"],
        project_map=["voice-router"],
    )
    await coach.whisper(ctx)

    prompt_text = mock_client.aio.models.generate_content.call_args.kwargs[
        "contents"
    ][0]["parts"][0]["text"]
    assert "Write a test before the fix" in prompt_text, (
        "recent whisper history must appear in the prompt"
    )


@patch("dev_coach.main.genai")
def test_jaccard_similarity_edge_cases(mock_genai):
    mock_genai.Client.return_value = MagicMock()
    from dev_coach.main import _jaccard

    assert _jaccard("", "anything") == 0.0
    assert _jaccard("foo bar", "foo bar") == 1.0
    assert _jaccard("foo", "bar") == 0.0
    overlap = _jaccard("write a test for the fix", "test the fix before writing")
    assert 0.0 < overlap < 1.0
