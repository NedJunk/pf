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


# ── E4-L: /synthesize endpoint ───────────────────────────────────────────────

_SYNTHESIZE_RESPONSE = """
--- PAGE: patterns.md ---
# Patterns

Compressed pattern content here.
--- END PAGE ---

--- INDEX ---
# Wiki Index

- patterns.md: Compressed patterns
--- INDEX END ---
"""


class SynthesizingAgent(ExpertAgentBase):
    """Agent whose _generate returns a pre-canned synthesis response."""
    def __init__(self, generate_response: str = _SYNTHESIZE_RESPONSE):
        super().__init__(model="test-model")
        self._response = generate_response

    async def _generate(self, prompt: str) -> str:
        return self._response

    async def whisper(self, context: WhisperContext) -> WhisperResponse:
        return WhisperResponse(source="Test", message="hello", confidence=0.9)


class CustomSynthesizeAgent(ExpertAgentBase):
    """Agent that overrides _synthesize with custom behavior."""
    def __init__(self):
        super().__init__(model="test-model")
        self.synthesize_called = False

    async def _generate(self, prompt: str) -> str:
        return ""

    async def whisper(self, context: WhisperContext) -> WhisperResponse:
        return WhisperResponse(source="Test", message="hi", confidence=0.9)

    async def _synthesize(self) -> None:
        self.synthesize_called = True


class FailingSynthesizeAgent(ExpertAgentBase):
    """Agent whose _generate raises during synthesis."""
    async def _generate(self, prompt: str) -> str:
        raise RuntimeError("LLM unavailable")

    async def whisper(self, context: WhisperContext) -> WhisperResponse:
        return WhisperResponse(source="Test", message="hi", confidence=0.9)


def test_synthesize_endpoint_returns_200():
    """POST /synthesize returns 200 with status ok."""
    client = TestClient(SynthesizingAgent().app)
    resp = client.post("/synthesize")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_synthesize_endpoint_updates_wiki_pages(tmp_path, monkeypatch):
    """POST /synthesize writes compressed pages back to the wiki."""
    monkeypatch.setenv("WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("WIKI_SCHEMA_PATH", str(tmp_path / "schema.md"))
    agent = SynthesizingAgent()
    # Give the wiki something to synthesize
    agent._wiki.write_page("old.md", "# Old\nVerbose content here.")
    agent._wiki.write_index("# Wiki Index\n\n- old.md: Verbose content\n")

    client = TestClient(agent.app)
    resp = client.post("/synthesize")
    assert resp.status_code == 200

    # patterns.md should have been written
    page = agent._wiki.read_page("patterns.md")
    assert "Compressed pattern content" in page

    # Index should be updated
    index = agent._wiki.read_index()
    assert "patterns.md" in index


def test_synthesize_endpoint_is_synchronous():
    """POST /synthesize blocks until complete (not fire-and-forget)."""
    completed = []

    class TrackingAgent(ExpertAgentBase):
        async def _generate(self, prompt: str) -> str:
            completed.append(True)
            return _SYNTHESIZE_RESPONSE

        async def whisper(self, context: WhisperContext) -> WhisperResponse:
            return WhisperResponse(source="Test", message="hi", confidence=0.9)

    client = TestClient(TrackingAgent(model="m").app)
    resp = client.post("/synthesize")
    assert resp.status_code == 200
    # If synchronous, completed should be populated before the response returns
    assert len(completed) == 1


def test_synthesize_agent_can_override_synthesize_hook():
    """Agents can override _synthesize() for domain-specific behavior."""
    agent = CustomSynthesizeAgent()
    client = TestClient(agent.app)
    resp = client.post("/synthesize")
    assert resp.status_code == 200
    assert agent.synthesize_called is True


def test_synthesize_safe_wrapper_catches_errors():
    """POST /synthesize returns 200 even when _synthesize raises."""
    client = TestClient(FailingSynthesizeAgent(model="m").app)
    resp = client.post("/synthesize")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_synthesize_prompt_includes_wiki_content(tmp_path, monkeypatch):
    """Default _synthesize passes wiki index and pages into the generate prompt."""
    monkeypatch.setenv("WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("WIKI_SCHEMA_PATH", str(tmp_path / "schema.md"))

    prompts_seen = []

    class CapturingAgent(ExpertAgentBase):
        async def _generate(self, prompt: str) -> str:
            prompts_seen.append(prompt)
            return ""

        async def whisper(self, context: WhisperContext) -> WhisperResponse:
            return WhisperResponse(source="Test", message="hi", confidence=0.9)

    agent = CapturingAgent(model="m")
    agent._wiki.write_page("topic.md", "# Topic\nSome content.")
    agent._wiki.write_index("# Wiki Index\n\n- topic.md: Topic notes\n")

    client = TestClient(agent.app)
    client.post("/synthesize")

    assert len(prompts_seen) == 1
    assert "topic.md" in prompts_seen[0]
    assert "Wiki Index" in prompts_seen[0]


def test_synthesize_log_appended_on_success(tmp_path, monkeypatch):
    """Default synthesis appends a log entry on completion."""
    monkeypatch.setenv("WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("WIKI_SCHEMA_PATH", str(tmp_path / "schema.md"))

    agent = SynthesizingAgent()
    client = TestClient(agent.app)
    client.post("/synthesize")

    log = agent._wiki.read_log()
    assert "synthesize" in log
