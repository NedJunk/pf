from dataclasses import dataclass, field


@dataclass(frozen=True)
class Whisper:
    source: str
    message: str


@dataclass
class RouterState:
    project_map: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    whispers: list[Whisper] = field(default_factory=list)


class StateStore:
    def __init__(self) -> None:
        self._state = RouterState()

    def get_state(self) -> RouterState:
        return self._state

    def update_goals(self, goals: list[str]) -> None:
        self._state.goals = goals[:]

    def add_to_history(self, entry: str) -> None:
        self._state.history.append(entry)

    def inject_whisper(self, source: str, message: str) -> None:
        self._state.whispers.append(Whisper(source=source, message=message))

    def clear_whispers(self) -> None:
        self._state.whispers.clear()
