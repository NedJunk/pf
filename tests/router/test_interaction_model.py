"""
Validates Router behavior against the example transcripts from Task 2.
These tests confirm the interaction model contract before the server layer is added.
"""
from unittest.mock import MagicMock, patch
from src.router.router import Router


@patch("src.router.facilitator.genai")
def test_whisper_is_passed_into_facilitator_prompt(mock_genai, tmp_path):
    """Router must include injected whispers in the Gemini prompt."""
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(
        text="The Project Manager is flagging that we have a 'wellness' project. Does this belong there?"
    )

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.inject_whisper("ProjectManager", "We have an existing 'wellness' project in the map.")
    router.facilitate("It should go under wellness.")

    call_args = str(mock_client.models.generate_content.call_args)
    assert "ProjectManager" in call_args
    assert "wellness" in call_args


@patch("src.router.facilitator.genai")
def test_router_does_not_retain_whispers_across_turns(mock_genai, tmp_path):
    """Whispers are consumed once voiced — they must not persist into the next turn."""
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(text="Noted.")

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.inject_whisper("PM", "One-time note.")
    router.facilitate("First input.")

    router.facilitate("Second input.")

    second_call_args = str(mock_client.models.generate_content.call_args)
    assert "One-time note." not in second_call_args


@patch("src.router.facilitator.genai")
def test_full_session_transcript_matches_history(mock_genai, tmp_path):
    """Transcript must be verbatim — every turn in history appears in the file."""
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(
        text="What kind of habits are you tracking?"
    )

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.facilitate("I need to track habits.")
    file_path = router.end_session("habits-session")

    content = open(file_path).read()
    for entry in router.get_state().history:
        assert entry in content
