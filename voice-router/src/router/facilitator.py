from google import genai
from .state_store import RouterState

_SYSTEM_PROMPT = """\
You are a thin, voice-first facilitation router. Your ONLY job is to help the user capture and clarify their thoughts.

Rules:
- Always ask one clarifying question to deepen understanding or prompt specifics
- Suggest how input might be categorized or connected to existing work
- If expert whispers are listed below, voice the most relevant one naturally \
(e.g. "The Project Manager is noting that...")
- NEVER perform deep analysis, generate code, or offer solutions
- Keep responses short — this is a voice interaction

Active goals: {goals}
Project map: {project_map}
Recent conversation:
{history}

Pending expert whispers:
{whispers}
"""


class Facilitator:
    _MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def respond(self, user_input: str, state: RouterState) -> str:
        whisper_text = (
            "\n".join(f"- [{w.source}]: {w.message}" for w in state.whispers)
            or "None"
        )
        history_text = "\n".join(state.history[-6:]) or "None"

        prompt = _SYSTEM_PROMPT.format(
            goals=state.goals or "None",
            project_map=state.project_map or "None",
            history=history_text,
            whispers=whisper_text,
        )
        full_input = f"{prompt}\n\nUser: {user_input}"

        response = self._client.models.generate_content(
            model=self._MODEL,
            contents=[{"role": "user", "parts": [{"text": full_input}]}],
        )
        return response.text
