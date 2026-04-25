import os
from unittest.mock import MagicMock, patch
from src.router.router import Router


@patch("src.router.facilitator.genai")
def test_facilitate_records_exchange_in_history(mock_genai, tmp_path):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(
        text="Tell me more — what kind of project?"
    )

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.facilitate("I have an idea.")

    history = router.get_state().history
    assert any("I have an idea." in h for h in history)
    assert any("Tell me more" in h for h in history)


@patch("src.router.facilitator.genai")
def test_whispers_cleared_after_facilitate(mock_genai, tmp_path):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(text="Noted.")

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.inject_whisper("PM", "We have a task.")
    assert len(router.get_state().whispers) == 1

    router.facilitate("Let's continue.")
    assert len(router.get_state().whispers) == 0


@patch("src.router.facilitator.genai")
def test_end_session_writes_transcript(mock_genai, tmp_path):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(text="Great, noted.")

    router = Router(output_dir=str(tmp_path), gemini_api_key="test-key")
    router.facilitate("Hello")
    file_path = router.end_session("my-session")

    assert os.path.exists(file_path)
    content = open(file_path).read()
    assert "# Session Transcript: my-session" in content
    assert "Hello" in content
