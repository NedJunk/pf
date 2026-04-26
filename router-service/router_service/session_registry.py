import uuid
from typing import Optional


class _SessionSlot:
    """Minimal session placeholder until LiveSession is implemented in Task 8."""
    def __init__(self, session_id: str, project_map: list[str], goals: list[str]) -> None:
        self.session_id = session_id
        self.project_map = project_map
        self.goals = goals


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, "_SessionSlot"] = {}

    def create(self, project_map: list[str], goals: list[str]) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = _SessionSlot(session_id, project_map, goals)
        return session_id

    def get(self, session_id: str) -> Optional["_SessionSlot"]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
