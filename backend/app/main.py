"""Edezee HTTP API.

Two ways to run the pipeline, because the two consumers need different things:

* ``POST /api/v1/generate`` returns the finished ``.pptx`` in one response. It is
  the simple contract, and it is what the evaluation harness drives.
* ``POST /api/v1/generate/stream`` streams Server-Sent Events so the browser can
  show "Drafting slide 2 of 5" instead of a frozen spinner. The final event
  carries the same diagnostics as the JSON endpoint.

The deck file itself is never written to disk. It is built in memory and
streamed, which keeps the service stateless and avoids leaking student content
between requests.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import Settings, get_settings
from app.models import (
    Depth,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    PipelineDiagnostics,
)
from app.services.pipeline import Pipeline, PipelineError
from app.services.pptx_service import build_presentation

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        # Release the shared connection pools so a restart does not leak sockets.
        await app.state.pipeline.aclose()

    app = FastAPI(
        title="Edezee API",
        version="1.0.0",
        description="Turn a course syllabus into a ready-to-teach PowerPoint deck.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    if settings.demo_mode:
        from app.services.demo import build_demo_llm

        app.state.pipeline = Pipeline(settings, llm=build_demo_llm(settings))
        logger.warning("DEMO_MODE is on: serving deterministic sample content, no model calls.")
    else:
        app.state.pipeline = Pipeline(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Edezee-Diagnostics"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return one plain-language sentence instead of a Pydantic error array.

        The UI reads `detail` as a string. Leaking the raw array would put
        "String should have at most 20000 characters" in front of a teacher, so
        every Pydantic error type we can trigger is mapped to our own wording.
        """
        message = _plain_message(exc.errors())
        logger.info("Rejected request %s: %s", request.url.path, message)
        return JSONResponse(status_code=422, content={"detail": message})

    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            llm_configured=settings.llm_configured,
            research_configured=settings.research_configured,
            model=settings.openrouter_model,
        )

    @app.post("/api/v1/generate")
    async def generate(request: Request, payload: GenerateRequest) -> StreamingResponse:
        """Run the pipeline and return the finished deck in a single response."""

        pipeline: Pipeline = request.app.state.pipeline
        try:
            deck_title, slides, diagnostics = await pipeline.generate(
                payload.syllabus_text,
                depth=payload.depth,
                deck_title=payload.deck_title,
            )
        except PipelineError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        deck_bytes = build_presentation(slides, deck_title=deck_title, subtitle=_subtitle(payload.depth))
        filename = _filename(deck_title)
        logger.info(
            "Generated deck %s: %s slides, %s degraded, %sms",
            diagnostics.request_id,
            diagnostics.slides_generated,
            diagnostics.degraded_slides,
            diagnostics.total_latency_ms,
        )

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Edezee-Diagnostics": json.dumps(diagnostics.model_dump(mode="json")),
            "X-Edezee-Slides": str(diagnostics.slides_generated),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Edezee-Diagnostics, X-Edezee-Slides",
        }
        return StreamingResponse(iter([deck_bytes]), media_type=PPTX_MIME, headers=headers)

    @app.post("/api/v1/generate/plan", response_model=GenerateResponse)
    async def generate_plan(payload: GenerateRequest, request: Request) -> GenerateResponse:
        """Return the structured deck plan as JSON (used by tests and the eval harness)."""

        pipeline: Pipeline = request.app.state.pipeline
        try:
            deck_title, slides, diagnostics = await pipeline.generate(
                payload.syllabus_text,
                depth=payload.depth,
                deck_title=payload.deck_title,
            )
        except PipelineError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return GenerateResponse(deck_title=deck_title, slides=slides, diagnostics=diagnostics)

    @app.post("/api/v1/generate/stream")
    async def generate_stream(payload: GenerateRequest, request: Request) -> StreamingResponse:
        """Stream progress events, then the base64 deck payload.

        Event shapes:
          ``{"type": "progress", "stage": str, "message": str, "completed": int, "total": int}``
          ``{"type": "done", "filename": str, "slides": int, "diagnostics": {...}, "deck_base64": str}``
          ``{"type": "error", "message": str}``
        """

        pipeline: Pipeline = request.app.state.pipeline

        async def event_stream() -> AsyncIterator[str]:
            queue: asyncio.Queue[tuple[str, str, int, int] | None] = asyncio.Queue()

            async def on_progress(stage: str, message: str, completed: int, total: int) -> None:
                await queue.put((stage, message, completed, total))

            async def run_pipeline():
                try:
                    deck_title, slides, diagnostics = await pipeline.generate(
                        payload.syllabus_text,
                        depth=payload.depth,
                        deck_title=payload.deck_title,
                        on_progress=on_progress,
                    )
                    deck_bytes = build_presentation(
                        slides, deck_title=deck_title, subtitle=_subtitle(payload.depth)
                    )
                    return deck_title, slides, diagnostics, deck_bytes
                finally:
                    await queue.put(None)

            task = asyncio.create_task(run_pipeline())

            while True:
                item = await queue.get()
                if item is None:
                    break
                stage, message, completed, total = item
                yield _sse(
                    {
                        "type": "progress",
                        "stage": stage,
                        "message": message,
                        "completed": completed,
                        "total": total,
                    }
                )

            try:
                deck_title, slides, diagnostics, deck_bytes = await task
            except PipelineError as exc:
                yield _sse({"type": "error", "message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001 - report, never leak a stack trace
                logger.exception("Pipeline crashed")
                yield _sse({"type": "error", "message": f"Unexpected server error: {exc}"})
                return

            import base64

            yield _sse(
                {
                    "type": "done",
                    "filename": _filename(deck_title),
                    "slides": len(slides),
                    "diagnostics": diagnostics.model_dump(mode="json"),
                    "slide_plan": [slide.model_dump(mode="json") for slide in slides],
                    "deck_base64": base64.b64encode(deck_bytes).decode("ascii"),
                }
            )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# Maps the Pydantic error types reachable from our request models to text a
# teacher can act on. Keys are `error["type"]` values, not messages, so this
# keeps working when Pydantic rewords its built-in strings.
_VALIDATION_MESSAGES = {
    "json_invalid": "That request could not be read. Please try the request again.",
    "missing": "No syllabus topics were sent. Please paste at least one topic.",
    "string_too_long": "That text is too long. Please shorten it and try again.",
    "string_too_short": "Please add some text and try again.",
    "enum": "Choose one of the offered options and try again.",
    "literal_error": "Choose one of the offered options and try again.",
    "list_type": "One of the fields was not formatted correctly. Please try again.",
    "string_type": "One of the fields was not formatted correctly. Please try again.",
}

_DEFAULT_INVALID_MESSAGE = (
    "That request could not be read. Please check the topics and try again."
)


def _plain_message(errors: list[dict]) -> str:
    """Turn the first Pydantic error into one plain-language sentence.

    A custom ``ValueError`` raised by a field validator is our own prose, so it
    is returned untouched. Everything else is mapped by ``type`` and sharpened
    with the field name where a generic sentence would be ambiguous.
    """
    if not errors:
        return _DEFAULT_INVALID_MESSAGE

    first = errors[0]
    raw = str(first.get("msg", ""))
    if raw.startswith("Value error, "):
        # Our own validator wording, written for the user.
        return raw.removeprefix("Value error, ").strip() or _DEFAULT_INVALID_MESSAGE

    error_type = first.get("type", "")
    message = _VALIDATION_MESSAGES.get(error_type, _DEFAULT_INVALID_MESSAGE)

    if error_type in {"string_too_long", "string_too_short"}:
        field = str(first.get("loc", ("",))[-1])
        labels = {
            "syllabus_text": "That syllabus is too long. Use 40 topics or fewer and try again.",
            "deck_title": "That deck title is too long. Please shorten it and try again.",
        }
        message = labels.get(field, message)

    return message


def _filename(deck_title: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in deck_title).strip()
    safe = (safe or "edezee-presentation").replace(" ", "_")
    return f"{safe}_{int(time.time())}.pptx"


def _subtitle(depth: Depth) -> str:
    label = "High-level overview" if depth is Depth.HIGH_LEVEL else "In-depth technical"
    return f"{label} · Generated by Edezee"


app = create_app()
