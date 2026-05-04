import asyncio
import base64
import json
import logging
import os
from typing import Optional

import httpx
from fastapi import WebSocket
from google import genai
from google.genai import types

from src.router.behavioral_contract import BEHAVIORAL_CONTRACT
from src.router.transcript_writer import TranscriptWriter

logger = logging.getLogger(__name__)


class LiveSession:
    def __init__(
        self,
        session_id: str,
        project_map: list[str],
        goals: list[str],
        api_key: str,
        orchestrator_url: str,
        transcript_output_dir: str,
        history_tail_length: int,
        live_api_model: str,
        backlog_path: str = "",
    ) -> None:
        self.session_id = session_id
        self.project_map = project_map
        self.goals = goals
        self._api_key = api_key
        self._orchestrator_url = orchestrator_url
        self._transcript_output_dir = transcript_output_dir
        self._history_tail_length = history_tail_length
        self._live_api_model = live_api_model
        self._backlog_path = backlog_path

        self._client = genai.Client(api_key=api_key)
        self._http_client = httpx.AsyncClient()
        self._gemini_session = None
        self._gemini_cm = None
        self._history: list[str] = []
        self._input_buf: list[str] = []
        self._output_buf: list[str] = []
        self._whisper_queue: asyncio.Queue = asyncio.Queue()
        self._model_generating: asyncio.Event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._closed = False

    async def connect(self) -> None:
        system_instruction = BEHAVIORAL_CONTRACT
        if self._backlog_path:
            from pathlib import Path
            p = Path(self._backlog_path)
            if p.exists():
                backlog = p.read_text()
                system_instruction += (
                    "\n\n# Current Project Backlog\n"
                    "You have read-only awareness of the current project backlog. "
                    "Reference specific items when the user mentions bugs, epics, or work items by code. "
                    "Do not read out or summarise backlog sections unprompted.\n\n"
                    + backlog
                )
        config = {
            "response_modalities": ["AUDIO"],
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "system_instruction": system_instruction,
            "generation_config": {
                "thinking_config": {"thinking_budget": 0},
            },
        }
        self._gemini_cm = self._client.aio.live.connect(
            model=self._live_api_model, config=config
        )
        self._gemini_session = await self._gemini_cm.__aenter__()

    async def stream(self, browser_ws: WebSocket) -> None:
        tasks = [
            asyncio.create_task(self._browser_to_gemini(browser_ws)),
            asyncio.create_task(self._gemini_to_browser(browser_ws)),
            asyncio.create_task(self._whisper_drain(browser_ws)),
        ]
        self._tasks = tasks
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    def inject_whisper(self, source: str, message: str) -> None:
        self._whisper_queue.put_nowait({"source": source, "message": message})

    def _flush_output_buf(self) -> None:
        if not self._output_buf:
            return
        text = "".join(self._output_buf)
        self._output_buf = []
        # Coalesce consecutive model turns into one history entry. Scan backward
        # past any [Whisper from ...] entries — a whisper delivered between two
        # consecutive assistant turn_completes must not break coalescing.
        idx = len(self._history) - 1
        while idx >= 0 and self._history[idx].startswith("[Whisper"):
            idx -= 1
        if idx >= 0 and self._history[idx].startswith("Assistant:"):
            self._history[idx] = self._history[idx].rstrip() + " " + text.lstrip()
        else:
            self._history.append(f"Assistant: {text}")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._gemini_cm:
            try:
                await self._gemini_cm.__aexit__(None, None, None)
            except RuntimeError:
                pass
            finally:
                self._gemini_cm = None
        if self._input_buf:
            # Record user turn FIRST — same ordering fix as turn_complete handler (BUG-22).
            self._history.append(f"User: {''.join(self._input_buf)}")
            self._input_buf = []
        self._flush_output_buf()
        transcript = ""
        try:
            os.makedirs(self._transcript_output_dir, exist_ok=True)
            TranscriptWriter(self._transcript_output_dir).write_transcript(
                self.session_id, self._history
            )
            transcript = "\n".join(self._history)
        except Exception as exc:
            logger.error("Failed to write transcript for session %s: %s", self.session_id, exc)
        await self._post_session_close(transcript)
        await self._http_client.aclose()

    async def _post_session_close(self, transcript: str) -> None:
        try:
            await self._http_client.post(
                f"{self._orchestrator_url}/sessions/{self.session_id}/close",
                json={"transcript": transcript},
                timeout=5.0,
            )
        except Exception as exc:
            logger.warning(
                "Failed to notify orchestrator of session close session=%s: %s",
                self.session_id,
                exc,
            )

    async def _browser_to_gemini(self, browser_ws: WebSocket) -> None:
        try:
            while True:
                message = await browser_ws.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("bytes"):
                    await self._gemini_session.send_realtime_input(
                        audio=types.Blob(
                            data=message["bytes"], mime_type="audio/pcm;rate=16000"
                        )
                    )
        except Exception as exc:
            logger.debug("_browser_to_gemini ended: %s", exc)

    async def _gemini_to_browser(self, browser_ws: WebSocket) -> None:
        try:
            while True:
                async for response in self._gemini_session.receive():
                    if response.data:
                        await browser_ws.send_bytes(response.data)
                    sc = response.server_content
                    if not sc:
                        continue
                    if sc.input_transcription and sc.input_transcription.text:
                        text = sc.input_transcription.text
                        self._input_buf.append(text)
                        logger.debug(
                            "[%s] input_transcription chunk #%d: %r",
                            self.session_id, len(self._input_buf), text,
                        )
                        await browser_ws.send_text(
                            json.dumps({"type": "transcript", "role": "user", "text": text})
                        )
                    if sc.output_transcription and sc.output_transcription.text:
                        text = sc.output_transcription.text
                        if text.startswith("[WHISPER from"):
                            # BUG-12: send_client_content(turn_complete=False) causes Gemini to
                            # echo the injected whisper text as output_transcription. Drop it —
                            # the whisper is already recorded in history by _whisper_drain.
                            logger.debug(
                                "[%s] dropping whisper output_transcription pollution: %r",
                                self.session_id, text[:80],
                            )
                        else:
                            self._output_buf.append(text)
                            logger.debug(
                                "[%s] output_transcription chunk #%d: %r",
                                self.session_id, len(self._output_buf), text,
                            )
                            await browser_ws.send_text(
                                json.dumps({"type": "transcript", "role": "assistant", "text": text})
                            )
                    if sc.turn_complete:
                        # BUG-07 diagnostic: if branch=user and output_buf is non-empty,
                        # the Gemini response began arriving before turn_complete — this is
                        # the race condition that caused inverted transcript ordering (BUG-22).
                        logger.debug(
                            "[%s] turn_complete: branch=%s input_buf=%d chunks output_buf=%d chunks",
                            self.session_id,
                            "user" if self._input_buf else "assistant",
                            len(self._input_buf),
                            len(self._output_buf),
                        )
                        if self._input_buf:
                            # Record user turn FIRST, then any concurrently-arrived
                            # assistant response. Flushing output before user turn caused
                            # inverted ordering when Gemini's response began arriving before
                            # the turn_complete event for the user's audio (BUG-22).
                            self._history.append(f"User: {''.join(self._input_buf)}")
                            self._input_buf = []
                            self._flush_output_buf()
                            self._model_generating.set()
                        else:
                            self._model_generating.clear()
                            self._flush_output_buf()
                        await browser_ws.send_text(json.dumps({"type": "turn_complete"}))
                        await self._post_turn_event()
                    if getattr(sc, "interrupted", False):
                        logger.debug(
                            "[%s] interrupted: output_buf has %d chunks at interrupt",
                            self.session_id, len(self._output_buf),
                        )
                        # Flush partial output immediately so stale interrupted content
                        # does not survive into the next user turn_complete path (BUG-22).
                        self._flush_output_buf()
                        await browser_ws.send_text(json.dumps({"type": "interrupted"}))
        except Exception as exc:
            logger.error("_gemini_to_browser error: %s", exc, exc_info=True)

    async def _whisper_drain(self, browser_ws: WebSocket) -> None:
        while True:
            whisper = await self._whisper_queue.get()
            await self._model_generating.wait()
            try:
                await browser_ws.send_text(json.dumps({
                    "type": "whisper",
                    "source": whisper["source"],
                    "message": whisper["message"],
                }))
                # Inject whisper as silent context via send_client_content(turn_complete=False).
                #
                # WHY NOT send_realtime_input(text=...):
                #   That channel is the VAD user-turn channel. Gemini treats any text sent
                #   there as a user utterance and immediately generates an audio response —
                #   causing the router to vocalize the whisper content aloud (BUG-10).
                #
                # WHY send_client_content(turn_complete=False):
                #   turn_complete=False tells Gemini to accumulate the content without
                #   responding. It will incorporate the whisper context when it next
                #   responds to the user's actual audio input. This is the closest
                #   purpose-built mechanism in the SDK for silent context injection.
                #
                # KNOWN RISK — SDK interleaving caution (live.py line 188):
                #   "Interleaving send_client_content and send_realtime_input in the same
                #   conversation is not recommended and can lead to unexpected results."
                #   We are deliberately doing this. The "unexpected results" language likely
                #   refers to message ordering, not crashes. Behavior under concurrent VAD
                #   was validated in testing (see BUG-10 in backlog). If this proves
                #   unstable, the fallback is Option B: buffer whispers and prepend to the
                #   next user turn at the orchestrator boundary.
                await self._gemini_session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(
                            text=f"[WHISPER from {whisper['source']}]: {whisper['message']}"
                        )],
                    ),
                    turn_complete=False,
                )
                self._history.append(
                    f"[Whisper from {whisper['source']}]: {whisper['message']}"
                )
            except Exception as exc:
                logger.warning("Failed to inject whisper from %s: %s", whisper["source"], exc)

    async def _post_turn_event(self) -> None:
        tail = self._history[-self._history_tail_length:]
        payload = {
            "session_id": self.session_id,
            "history_tail": tail,
            "goals": self.goals,
            "project_map": self.project_map,
        }
        try:
            await self._http_client.post(
                f"{self._orchestrator_url}/turns", json=payload, timeout=2.0
            )
        except Exception as exc:
            logger.warning("Failed to post turn event [%s] to %s: %s", type(exc).__name__, self._orchestrator_url, exc)
