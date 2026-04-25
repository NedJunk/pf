from unittest.mock import MagicMock, patch
from src.router.facilitator import Facilitator
from src.router.state_store import RouterState, Whisper


def _mock_gemini_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


@patch("src.router.facilitator.genai")
def test_respond_calls_gemini_and_returns_text(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response(
        "Is this for yourself or for others?"
    )

    facilitator = Facilitator(api_key="test-key")
    response = facilitator.respond(
        user_input="I want to build a habit tracker.",
        state=RouterState(),
    )

    assert response == "Is this for yourself or for others?"
    mock_client.models.generate_content.assert_called_once()


@patch("src.router.facilitator.genai")
def test_whispers_are_included_in_prompt(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response(
        "The Project Manager notes we have a wellness project. Does this belong there?"
    )

    state = RouterState(
        whispers=[Whisper(source="ProjectManager", message="We have a 'wellness' project.")]
    )
    facilitator = Facilitator(api_key="test-key")
    facilitator.respond(user_input="Let's add a habit tracker.", state=state)

    call_args = str(mock_client.models.generate_content.call_args)
    assert "ProjectManager" in call_args
    assert "wellness" in call_args


@patch("src.router.facilitator.genai")
def test_recent_history_is_included_in_prompt(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response("Tell me more.")

    state = RouterState(history=["User: Hello", "Router: Hi there"])
    facilitator = Facilitator(api_key="test-key")
    facilitator.respond(user_input="I have an idea.", state=state)

    call_args = str(mock_client.models.generate_content.call_args)
    assert "User: Hello" in call_args or "Router: Hi there" in call_args
