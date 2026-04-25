import os
from src.router.transcript_writer import TranscriptWriter


def test_writes_verbatim_markdown_transcript(tmp_path):
    writer = TranscriptWriter(output_dir=str(tmp_path))
    history = [
        "User: I need to track habits.",
        "Router: What kind of habits?",
    ]

    file_path = writer.write_transcript("session-1", history)

    assert os.path.exists(file_path)
    content = open(file_path).read()
    assert "# Session Transcript: session-1" in content
    assert "User: I need to track habits." in content
    assert "Router: What kind of habits?" in content


def test_transcript_filename_includes_session_id(tmp_path):
    writer = TranscriptWriter(output_dir=str(tmp_path))
    file_path = writer.write_transcript("my-session", [])
    assert "my-session" in os.path.basename(file_path)


def test_empty_session_still_writes_file(tmp_path):
    writer = TranscriptWriter(output_dir=str(tmp_path))
    file_path = writer.write_transcript("empty-session", [])
    assert os.path.exists(file_path)
    assert "# Session Transcript: empty-session" in open(file_path).read()
