import os
import re
from datetime import datetime


class TranscriptWriter:
    def __init__(self, output_dir: str) -> None:
        self._output_dir = output_dir

    def write_transcript(self, session_id: str, history: list[str]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        short_id = session_id[:8]
        topic = self._topic_slug(history)
        name = f"{timestamp}_{short_id}_{topic}" if topic else f"{timestamp}_{short_id}"
        file_path = os.path.join(self._output_dir, f"{name}.md")
        content = f"# Session Transcript: {session_id}\n\n" + "\n\n".join(history)
        with open(file_path, "w") as f:
            f.write(content)
        return file_path

    def _topic_slug(self, history: list[str]) -> str:
        for line in history:
            if line.startswith("User:"):
                words = line[5:].strip().split()[:5]
                return re.sub(r"[^a-z0-9]+", "-", " ".join(words).lower()).strip("-")[:40]
        return ""
