import logging
import os
import re
from pathlib import Path

from google import genai
from expert_agent_base.base import ExpertAgentBase, WhisperContext, WhisperResponse

logger = logging.getLogger(__name__)

_ROADMAP_CHAR_LIMIT = 4000
_SIMILARITY_THRESHOLD = 0.7
_SESSION_WHISPER_MEMORY = 10


def _jaccard(a: str, b: str) -> float:
    words_a = set(re.findall(r"\w+", a.lower()))
    words_b = set(re.findall(r"\w+", b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)

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
{recent_section}{roadmap_section}{schema_section}{wiki_context}
Recent conversation:
{history_tail}

Your suggestion (or NO_WHISPER):"""

_SYNTHESIZE_PROMPT = """\
You are performing a Karpathy-style knowledge compression pass on an expert agent wiki,
with awareness of the current product roadmap and milestone state.

CURRENT ROADMAP / BACKLOG STATE:
{roadmap}

WIKI INDEX:
{index}

WIKI PAGES:
{pages}

RECENT INGEST LOG:
{log}

Your task:
1. Identify recurring patterns and redundant entries across pages
2. Merge overlapping content -- one dense, precise entry beats three vague ones
3. Sharpen descriptions -- remove filler, tighten language
4. Orient patterns and problems to the current epic/milestone state: flag entries
   that are obsolete given the roadmap, and surface entries relevant to active epics
5. Rewrite pages with genuinely new compressed content; skip pages already tight
6. Update the index to reflect any new or rewritten pages

Write only pages that changed:

--- PAGE: <filename.md> ---
<full markdown page content>
--- END PAGE ---

Then the updated index:

--- INDEX ---
<full index.md content>
--- INDEX END ---

If nothing needs compression, output exactly: NO_CHANGES"""


def _load_roadmap(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")[:_ROADMAP_CHAR_LIMIT]
    except (FileNotFoundError, OSError) as exc:
        logger.warning("Could not load roadmap from %s: %s", path, exc)
        return ""


class DevCoach(ExpertAgentBase):
    def __init__(self) -> None:
        model = os.environ.get("DEV_COACH_MODEL", "gemini-3-flash-preview")
        super().__init__(model=model)
        self._client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        self._roadmap = _load_roadmap(os.environ.get("ROADMAP_PATH", ""))
        self._session_whispers: dict[str, list[str]] = {}

    async def _generate(self, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )
        return (response.text or "").strip()

    async def _synthesize(self) -> None:
        if not self._roadmap:
            await super()._synthesize()
            return
        from expert_agent_base.wiki import parse_ingest_response
        import datetime
        index = self._wiki.read_index()
        page_names = self._wiki.list_pages()
        pages_text = ""
        for name in page_names:
            try:
                pages_text += "\n\n### " + name + "\n" + self._wiki.read_page(name)
            except (FileNotFoundError, OSError):
                pass
        log = self._wiki.read_log()
        prompt = _SYNTHESIZE_PROMPT.format(
            roadmap=self._roadmap,
            index=index,
            pages=pages_text.strip(),
            log=log,
        )
        raw = await self._generate(prompt)
        if raw.strip() == "NO_CHANGES":
            return
        pages, new_index = parse_ingest_response(raw)
        for filename, content in pages:
            self._wiki.write_page(filename, content)
        if new_index:
            self._wiki.write_index(new_index)
        date = datetime.date.today().isoformat()
        self._wiki.append_log("\n## [" + date + "] synthesize")

    async def whisper(self, context: WhisperContext) -> WhisperResponse | None:
        if len(context.history) < 2:
            return None

        recent = self._session_whispers.get(context.session_id, [])
        recent_section = (
            "Suggestions already given this session — do not repeat or rephrase these:\n"
            + "\n".join(f"- {w}" for w in recent[-5:])
            + "\n\n"
            if recent
            else ""
        )
        roadmap_section = (
            f"Current roadmap/backlog state:\n{self._roadmap}\n\n"
            if self._roadmap
            else ""
        )
        schema_section = f"\nAgent knowledge schema:\n{self._wiki_schema}\n" if self._wiki_schema else ""
        wiki_section = (
            f"\nRelevant wiki context:\n{context.wiki_context}\n"
            if context.wiki_context
            else ""
        )
        prompt = _PROMPT.format(
            goals="; ".join(context.goals) or "None",
            project_map="; ".join(context.project_map) or "None",
            recent_section=recent_section,
            roadmap_section=roadmap_section,
            schema_section=schema_section,
            wiki_context=wiki_section,
            history_tail="\n".join(context.history),
        )

        text = await self._generate(prompt)
        if text.startswith("NO_WHISPER"):
            return None

        for prev in recent:
            if _jaccard(text, prev) >= _SIMILARITY_THRESHOLD:
                logger.debug(
                    "DevCoach suppressed near-duplicate whisper (jaccard=%.2f): %r",
                    _jaccard(text, prev), text[:80],
                )
                return None

        session_history = self._session_whispers.setdefault(context.session_id, [])
        session_history.append(text)
        if len(session_history) > _SESSION_WHISPER_MEMORY:
            session_history.pop(0)

        return WhisperResponse(source="DevCoach", message=text, confidence=0.8)


_coach = DevCoach()
app = _coach.app
