import os
from .state_store import StateStore, RouterState
from .transcript_writer import TranscriptWriter
from .facilitator import Facilitator


class Router:
    def __init__(self, output_dir: str, gemini_api_key: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        self._state_store = StateStore()
        self._writer = TranscriptWriter(output_dir)
        self._facilitator = Facilitator(api_key=gemini_api_key)

    def facilitate(self, user_input: str) -> str:
        self._state_store.add_to_history(f"User: {user_input}")
        response = self._facilitator.respond(user_input, self._state_store.get_state())
        self._state_store.add_to_history(f"Router: {response}")
        self._state_store.clear_whispers()
        return response

    def inject_whisper(self, source: str, message: str) -> None:
        self._state_store.inject_whisper(source, message)

    def get_state(self) -> RouterState:
        return self._state_store.get_state()

    def end_session(self, session_id: str) -> str:
        return self._writer.write_transcript(
            session_id, self._state_store.get_state().history
        )
