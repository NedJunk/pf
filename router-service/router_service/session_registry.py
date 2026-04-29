import os
import uuid
from typing import Optional
from router_service.live_session import LiveSession


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}

    def create(self, project_map: list[str], goals: list[str]) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = LiveSession(
            session_id=session_id,
            project_map=project_map,
            goals=goals,
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            orchestrator_url=os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8081"),
            transcript_output_dir=os.environ.get("TRANSCRIPT_OUTPUT_DIR", "/app/transcripts"),
            history_tail_length=int(os.environ.get("HISTORY_TAIL_LENGTH", "10")),
            live_api_model=os.environ.get("LIVE_API_MODEL", "gemini-2.0-flash-live-001"),
            backlog_path=os.environ.get("BACKLOG_PATH", ""),
        )
        return session_id

    def get(self, session_id: str) -> Optional[LiveSession]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
