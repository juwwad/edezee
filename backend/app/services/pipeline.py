"""End-to-end orchestration: syllabus text in, structured deck plan out.

The pipeline is intentionally linear and observable. Every stage emits a
progress event, every topic records its own timing and failure story, and a
single failing topic degrades to a placeholder slide instead of destroying the
whole deck. A teacher who pasted twelve topics should still get eleven good
slides when one topic goes wrong.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from app.config import Settings
from app.models import (
    Depth,
    Grounding,
    PipelineDiagnostics,
    Slide,
    SlideContent,
    TopicResult,
)
from app.services.llm import LLMService
from app.services.parser import parse_topics
from app.services.research import ResearchService

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, int, int], Awaitable[None] | None]

PLACEHOLDER_BULLETS = [
    "This topic could not be researched or drafted automatically.",
    "Review the syllabus entry and regenerate, or add the slide manually.",
]


class PipelineError(ValueError):
    """Raised for input problems the caller should surface to the user."""


class Pipeline:
    """Coordinates parsing, research, drafting, and slide assembly."""

    def __init__(
        self,
        settings: Settings,
        *,
        llm: LLMService | None = None,
        research: ResearchService | None = None,
    ) -> None:
        self._settings = settings
        self._llm = llm or LLMService(settings)
        self._research = research or ResearchService(settings)

    async def aclose(self) -> None:
        """Release the pooled HTTP connections owned by the sub-services."""
        await self._llm.aclose()
        await self._research.aclose()

    async def generate(
        self,
        syllabus_text: str,
        *,
        depth: Depth = Depth.HIGH_LEVEL,
        deck_title: str = "",
        on_progress: ProgressCallback | None = None,
    ) -> tuple[str, list[Slide], PipelineDiagnostics]:
        """Run the full pipeline and return ``(deck_title, slides, diagnostics)``."""

        started = time.perf_counter()
        request_id = uuid.uuid4().hex[:12]

        topics = parse_topics(syllabus_text, max_topics=self._settings.max_topics)
        if not topics:
            raise PipelineError(
                "We couldn't find any topics in that text. Put one topic per line and try again."
            )

        warnings: list[str] = []
        truncated = len(parse_topics(syllabus_text, max_topics=10_000))
        if truncated > len(topics):
            warnings.append(
                f"Input contained {truncated} topics; only the first {len(topics)} were processed."
            )
        if not self._llm.configured:
            raise PipelineError(
                "The slide generator is not configured on the server. Ask your administrator to set OPENROUTER_API_KEY."
            )
        if not self._research.configured:
            warnings.append(
                "Web research is disabled, so slides rely on the model's own knowledge."
            )

        await self._emit(on_progress, "parsing", f"Parsing {len(topics)} topics...", 0, len(topics))

        results: list[TopicResult] = []
        per_topic_latency: dict[str, int] = {}
        llm_calls = 0
        research_calls = 0
        research_used = False
        research_failures = 0

        for index, topic in enumerate(topics, start=1):
            topic_started = time.perf_counter()
            await self._emit(
                on_progress,
                "researching",
                f"Researching topic {index} of {len(topics)}: {topic}",
                index - 1,
                len(topics),
            )

            bundle = None
            if self._research.configured:
                research_calls += 1
                bundle = await self._research.research(topic, depth=depth.value)
                research_used = research_used or bundle.ok
                if not bundle.ok:
                    logger.info("Topic %r proceeding without research: %s", topic, bundle.error)
                    research_failures += 1

            await self._emit(
                on_progress,
                "drafting",
                f"Drafting slide {index} of {len(topics)}: {topic}",
                index - 1,
                len(topics),
            )

            draft = await self._llm.draft_topic(
                topic,
                depth=depth,
                research=bundle,
                course_title=deck_title,
            )
            llm_calls += draft.llm_calls
            per_topic_latency[topic] = int((time.perf_counter() - topic_started) * 1000)

            if draft.content is not None:
                grounding = (
                    Grounding.RESEARCH
                    if bundle is not None and bundle.ok
                    else Grounding.MODEL_KNOWLEDGE
                )
                results.append(
                    TopicResult(
                        topic=topic,
                        content=draft.content,
                        grounding=grounding,
                        sources=list(bundle.sources) if bundle and bundle.ok else [],
                        attempts=draft.attempts,
                    )
                )
            else:
                logger.error("Topic %r failed after %s attempts: %s", topic, draft.attempts, draft.error)
                warnings.append(f"Topic '{topic}' failed and was replaced with a placeholder slide.")
                results.append(
                    TopicResult(
                        topic=topic,
                        content=SlideContent(
                            slide_title=topic,
                            bullet_points=PLACEHOLDER_BULLETS,
                            speaker_notes=(
                                "Automatic generation failed for this topic. "
                                f"Reason: {draft.error or 'unknown error'}."
                            ),
                        ),
                        grounding=Grounding.PLACEHOLDER,
                        attempts=draft.attempts,
                        degraded=True,
                        error=draft.error,
                    )
                )

            if self._settings.inter_topic_delay_seconds and index < len(topics):
                await asyncio.sleep(self._settings.inter_topic_delay_seconds)

        if research_failures and not research_used:
            warnings.append(
                f"Web research failed for all {research_failures} topic(s); "
                "slides rely on the model's own knowledge."
            )
        elif research_failures:
            warnings.append(
                f"Web research failed for {research_failures} of {len(topics)} topic(s)."
            )

        await self._emit(
            on_progress, "compiling", "Compiling presentation...", len(topics), len(topics)
        )

        slides = [
            Slide(
                topic=result.topic,
                slide_number=index,
                slide_title=result.content.slide_title,
                bullet_points=result.content.bullet_points,
                speaker_notes=result.content.speaker_notes,
                grounding=result.grounding,
                sources=result.sources,
                attempts=result.attempts,
                degraded=result.degraded,
                error=result.error,
            )
            for index, result in enumerate(results, start=1)
        ]

        diagnostics = PipelineDiagnostics(
            request_id=request_id,
            topic_count=len(topics),
            slides_generated=len(slides),
            degraded_slides=sum(1 for slide in slides if slide.degraded),
            failed_topics=[slide.topic for slide in slides if slide.degraded],
            total_latency_ms=int((time.perf_counter() - started) * 1000),
            per_topic_latency_ms=per_topic_latency,
            llm_calls=llm_calls,
            research_calls=research_calls,
            research_used=research_used,
            model=self._settings.openrouter_model,
            depth=depth,
            warnings=warnings,
        )

        return (deck_title or "Course Presentation"), slides, diagnostics

    @staticmethod
    async def _emit(
        callback: ProgressCallback | None,
        stage: str,
        message: str,
        completed: int,
        total: int,
    ) -> None:
        if callback is None:
            return
        result = callback(stage, message, completed, total)
        if asyncio.iscoroutine(result):
            await result
