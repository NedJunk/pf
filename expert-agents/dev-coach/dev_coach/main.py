import os
from google import genai
from expert_agent_base.base import ExpertAgentBase, WhisperContext, WhisperResponse

_PROMPT = """\
You are a development process coach embedded in a voice-first development session.
Your job is to surface ONE brief, specific, actionable suggestion when you see
a genuine opportunity. Focus on process — never generate code.

Rules:
- Two sentences maximum
- Reference what was just said — no generic advice
- If you have nothing genuinely useful to add, respond with exactly: NO_WHISPER

Session goals: {goals}
Project context: {project_map}
{schema_section}{wiki_context}
Recent conversation:
{history_tail}

Your suggestion (or NO_WHISPER):"""


class DevCoach(ExpertAgentBase):
    def __init__(self) -> None:
        model = os.environ.get("DEV_COACH_MODEL", "gemini-3-flash-preview")
        super().__init__(model=model)
        self._client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

    async def _generate(self, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )
        return (response.text or "").strip()

    async def whisper(self, context: WhisperContext) -> WhisperResponse | None:
        if len(context.history) < 2:
            return None

        schema_section = f"\nAgent knowledge schema:\n{self._wiki_schema}\n" if self._wiki_schema else ""
        wiki_section = (
            f"\nRelevant wiki context:\n{context.wiki_context}\n"
            if context.wiki_context
            else ""
        )
        prompt = _PROMPT.format(
            goals="; ".join(context.goals) or "None",
            project_map="; ".join(context.project_map) or "None",
            schema_section=schema_section,
            wiki_context=wiki_section,
            history_tail="\n".join(context.history),
        )

        text = await self._generate(prompt)
        if text.startswith("NO_WHISPER"):
            return None

        return WhisperResponse(source="DevCoach", message=text, confidence=0.8)


_coach = DevCoach()
app = _coach.app
