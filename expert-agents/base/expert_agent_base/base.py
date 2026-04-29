import datetime
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import Response

from expert_agent_base.wiki import WikiManager, parse_ingest_response

logger = logging.getLogger(__name__)

_INGEST_PROMPT = """\
You are maintaining a wiki for an expert agent. Extract key information from the session transcript and update the wiki.

WIKI SCHEMA:
{schema}

CURRENT INDEX:
{index}

SESSION TRANSCRIPT (session_id: {session_id}):
{transcript}

Write any pages to create or update using this exact format:

--- PAGE: <filename.md> ---
<full markdown page content>
--- END PAGE ---

Then write the updated index.md:

--- INDEX ---
<full index.md content>
--- INDEX END ---

Only include pages with genuinely useful information. Skip if transcript has nothing worth recording."""

_QUERY_WIKI_PROMPT = """\
Given the wiki index and a conversation context, list the filenames of the most relevant wiki pages.

WIKI INDEX:
{index}

CONVERSATION CONTEXT:
{context}

Output up to 5 filenames, one per line. No explanation, no numbering.
If nothing is relevant, output exactly: NONE"""


@dataclass
class WhisperContext:
    session_id: str
    history: list[str]
    goals: list[str]
    project_map: list[str]
    wiki_context: str = field(default="")


@dataclass
class WhisperResponse:
    source: str
    message: str
    confidence: float


class ExpertAgentBase(ABC):
    def __init__(self, model: str) -> None:
        self.model = model
        wiki_dir = os.environ.get("WIKI_DIR", "/app/wiki")
        schema_path = os.environ.get("WIKI_SCHEMA_PATH", "/app/wiki_schema.md")
        self._wiki = WikiManager(wiki_dir)
        self._wiki.scaffold_if_empty()
        schema_file = Path(schema_path)
        self._wiki_schema = schema_file.read_text(encoding="utf-8") if schema_file.exists() else ""
        self._app = self._build_app()

    @property
    def app(self) -> FastAPI:
        return self._app

    @abstractmethod
    async def _generate(self, prompt: str) -> str:
        ...

    @abstractmethod
    async def whisper(self, context: WhisperContext) -> Optional[WhisperResponse]:
        ...

    async def _ingest_session(self, session_id: str, transcript: str) -> None:
        if not self._wiki_schema:
            return
        index = self._wiki.read_index()
        prompt = _INGEST_PROMPT.format(
            schema=self._wiki_schema,
            index=index,
            session_id=session_id,
            transcript=transcript,
        )
        raw = await self._generate(prompt)
        pages, new_index = parse_ingest_response(raw)
        for filename, content in pages:
            self._wiki.write_page(filename, content)
        if new_index:
            self._wiki.write_index(new_index)
        date = datetime.date.today().isoformat()
        self._wiki.append_log(f"\n## [{date}] ingest | {session_id}")

    async def _query_wiki(self, context: str) -> str:
        try:
            index = self._wiki.read_index()
            if not index.strip() or index.strip() == "# Wiki Index":
                return ""
            prompt = _QUERY_WIKI_PROMPT.format(index=index, context=context)
            raw = (await self._generate(prompt)).strip()
            if not raw or raw == "NONE":
                return ""
            page_names = [line.strip() for line in raw.splitlines() if line.strip()]
            parts = []
            for name in page_names[:5]:
                try:
                    content = self._wiki.read_page(name)
                    parts.append(f"### {name}\n{content}")
                except (FileNotFoundError, OSError):
                    pass
            return "\n\n".join(parts)
        except Exception as exc:
            logger.warning("_query_wiki failed: %s", exc)
            return ""

    async def _safe_ingest(self, session_id: str, transcript: str) -> None:
        try:
            await self._ingest_session(session_id, transcript)
        except Exception as exc:
            logger.error("Wiki ingest failed session=%s: %s", session_id, exc)
            date = datetime.date.today().isoformat()
            try:
                self._wiki.append_log(f"\n## [{date}] FAILED | {session_id} | {exc}")
            except Exception:
                pass

    async def _handle_whisper(self, body: dict) -> None:
        context = WhisperContext(
            session_id=body["session_id"],
            history=body["context"]["history"],
            goals=body["context"]["goals"],
            project_map=body["context"]["project_map"],
        )
        callback_url: Optional[str] = body.get("callback_url")
        confidence_threshold: float = float(body.get("confidence_threshold", 0.5))

        context.wiki_context = await self._query_wiki("\n".join(context.history))
        try:
            result = await self.whisper(context)
        except Exception as exc:
            logger.error("Whisper generation failed session=%s: %s", context.session_id, exc)
            return

        if result is None or result.confidence < confidence_threshold or not callback_url:
            return

        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    callback_url,
                    json={"source": result.source, "message": result.message},
                    timeout=5.0,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to deliver whisper callback session=%s: %s",
                    context.session_id, exc,
                )

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.post("/ingest", status_code=202)
        async def ingest_endpoint(body: dict, background_tasks: BackgroundTasks):
            background_tasks.add_task(self._safe_ingest, body["session_id"], body["transcript"])
            return {}

        @app.post("/whisper", status_code=202)
        async def whisper_endpoint(body: dict, background_tasks: BackgroundTasks):
            background_tasks.add_task(self._handle_whisper, body)
            return {}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app
