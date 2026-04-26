from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response


@dataclass
class WhisperContext:
    session_id: str
    history: list[str]
    goals: list[str]
    project_map: list[str]


@dataclass
class WhisperResponse:
    source: str
    message: str
    confidence: float


class ExpertAgentBase(ABC):
    def __init__(self, model: str) -> None:
        self.model = model
        self._app = self._build_app()

    @property
    def app(self) -> FastAPI:
        return self._app

    @abstractmethod
    async def whisper(self, context: WhisperContext) -> Optional[WhisperResponse]:
        ...

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.post("/whisper")
        async def whisper_endpoint(body: dict):
            context = WhisperContext(
                session_id=body["session_id"],
                history=body["context"]["history"],
                goals=body["context"]["goals"],
                project_map=body["context"]["project_map"],
            )
            try:
                result = await self.whisper(context)
            except Exception as exc:
                return JSONResponse({"error": str(exc)}, status_code=503)
            if result is None:
                return Response(status_code=204)
            return JSONResponse({
                "source": result.source,
                "message": result.message,
                "confidence": result.confidence,
            })

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app
