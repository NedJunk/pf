import os


class TranscriptWriter:
    def __init__(self, output_dir: str) -> None:
        self._output_dir = output_dir

    def write_transcript(self, session_id: str, history: list[str]) -> str:
        file_path = os.path.join(self._output_dir, f"{session_id}.md")
        content = f"# Session Transcript: {session_id}\n\n" + "\n\n".join(history)
        with open(file_path, "w") as f:
            f.write(content)
        return file_path
