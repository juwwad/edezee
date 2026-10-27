"""Pydantic contracts for every boundary in the Edezee pipeline.

Keeping the schemas in one module means the API, the LLM validator, and the
evaluation harness all agree on what a "slide" is.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Depth(str, Enum):
    """How much detail a generated deck should carry."""

    HIGH_LEVEL = "High-Level"
    IN_DEPTH = "In-Depth"


class Grounding(str, Enum):
    """Where the factual content of a slide came from."""

    RESEARCH = "research"
    MODEL_KNOWLEDGE = "model-knowledge"
    PLACEHOLDER = "placeholder"


class GenerateRequest(BaseModel):
    # `min_length` is deliberately not set here. Pydantic's built-in message
    # ("String should have at least 1 character") is developer-facing, and it
    # fires before `_not_blank` can produce the plain-language one. The validator
    # handles empty and whitespace-only input identically.
    syllabus_text: str = Field(
        ...,
        description="Raw syllabus text. One topic per line is preferred but not required.",
        max_length=20_000,
    )
    depth: Depth = Depth.HIGH_LEVEL
    deck_title: str = Field(
        default="",
        max_length=200,
        description="Optional deck title. Defaults to 'Course Presentation'.",
    )

    @field_validator("syllabus_text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "We couldn't find any topics in that text. Add at least one topic, "
                "one per line, and try again."
            )
        return value


# Deck design rule: never crowd a slide. Overflow is trimmed rather than
# rejected, because failing a whole topic over one extra bullet is worse for the
# teacher than silently dropping the least important line.
MAX_BULLETS_PER_SLIDE = 5


class SlideContent(BaseModel):
    """The structured payload the LLM must return for a single topic."""

    slide_title: str = Field(..., min_length=1)
    bullet_points: list[str] = Field(..., min_length=1)
    speaker_notes: str = Field(default="")

    @field_validator("bullet_points")
    @classmethod
    def _trim_bullets(cls, bullets: list[str]) -> list[str]:
        cleaned = [b.strip() for b in bullets if b and b.strip()]
        if not cleaned:
            raise ValueError("bullet_points must contain at least one non-empty entry")
        return cleaned[:MAX_BULLETS_PER_SLIDE]

    @field_validator("speaker_notes")
    @classmethod
    def _cap_notes(cls, notes: str) -> str:
        return notes.strip()[:2_000]

    @field_validator("slide_title")
    @classmethod
    def _clean_title(cls, title: str) -> str:
        return title.strip()


class Slide(BaseModel):
    """A compiled slide plus the provenance metadata the UI displays."""

    topic: str
    slide_number: int
    slide_title: str
    bullet_points: list[str]
    speaker_notes: str = ""
    grounding: Grounding = Grounding.MODEL_KNOWLEDGE
    sources: list[str] = Field(default_factory=list)
    attempts: int = 1
    degraded: bool = False
    error: str | None = None


class TopicResult(BaseModel):
    """Outcome of the per-topic pipeline stage, before slide assembly."""

    topic: str
    content: SlideContent
    grounding: Grounding
    sources: list[str] = Field(default_factory=list)
    attempts: int = 1
    degraded: bool = False
    error: str | None = None


class PipelineDiagnostics(BaseModel):
    """Machine-readable run summary returned alongside every deck."""

    request_id: str
    topic_count: int
    slides_generated: int
    degraded_slides: int
    failed_topics: list[str] = Field(default_factory=list)
    total_latency_ms: int
    per_topic_latency_ms: dict[str, int] = Field(default_factory=dict)
    llm_calls: int = 0
    research_calls: int = 0
    research_used: bool = False
    model: str = ""
    depth: Depth = Depth.HIGH_LEVEL
    warnings: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    """JSON envelope returned when the client asks for the plan, not the file."""

    deck_title: str
    slides: list[Slide]
    diagnostics: PipelineDiagnostics


class HealthResponse(BaseModel):
    status: Literal["ok"]
    llm_configured: bool
    research_configured: bool
    model: str
