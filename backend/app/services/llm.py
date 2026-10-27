"""OpenRouter-compatible chat client with strict JSON contract enforcement.

The reliability story for Edezee lives here. A naive "ask the model for JSON"
implementation fails often enough to be unusable in a classroom: models wrap
JSON in prose, emit trailing commas, or return an empty bullet list. Every one
of those cases is handled explicitly, in order, and recorded in the result so
the UI can tell the teacher exactly what happened.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.models import Depth, SlideContent
from app.services.research import ResearchBundle

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S | re.I)
_JSON_OBJECT = re.compile(r"\{.*\}", re.S)

_SYSTEM_PROMPT = """You are a curriculum assistant that turns a single syllabus topic into \
presentation-ready slide content for a teacher.

Rules:
- Return ONE JSON object and nothing else. No prose, no markdown fences.
- Write for the requested depth: "{depth_label}".
- Use 3 to 5 bullet points. Each bullet is one short sentence (max ~140 characters).
- Bullet points must be specific and factual. Never write placeholders like "TBD" or "N/A".
- "speaker_notes" is 2 to 4 sentences of teaching guidance, not a repeat of the bullets.
- Use only information supported by the supplied research notes when they are provided.

Schema:
{{"slide_title": str, "bullet_points": [str, ...], "speaker_notes": str}}"""

_DEPTH_LABELS = {
    Depth.HIGH_LEVEL: "a high-level overview a first-time learner can follow",
    Depth.IN_DEPTH: "an in-depth technical treatment with precise terminology",
}


@dataclass
class DraftResult:
    """Outcome of drafting one topic, including the failure story."""

    content: SlideContent | None = None
    attempts: int = 1
    llm_calls: int = 0
    error: str | None = None
    repaired: bool = False
    raw_excerpt: str = ""


class LLMError(RuntimeError):
    """Raised internally when a single LLM call cannot produce valid content."""


class LLMService:
    """Drafts slide content one topic at a time.

    A single topic is drafted per call. That is deliberate: batching a whole
    syllabus into one prompt is exactly what causes generic output and output
    truncation on long decks.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None

    def _http(self) -> httpx.AsyncClient:
        """Reuse one connection pool across topics.

        A client per call costs a fresh TLS handshake for every topic, which is
        real latency on a pipeline that makes one call per topic.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds)
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    @property
    def configured(self) -> bool:
        return self._settings.llm_configured

    async def draft_topic(
        self,
        topic: str,
        *,
        depth: Depth,
        research: ResearchBundle | None = None,
        course_title: str = "",
    ) -> DraftResult:
        """Draft one topic, retrying transient failures up to the configured cap."""

        if not self.configured:
            return DraftResult(
                attempts=0,
                error="LLM provider is not configured (set OPENROUTER_API_KEY)",
            )

        last_error: str = "unknown error"
        calls = 0
        raw_excerpt = ""

        for attempt in range(1, self._settings.max_topic_attempts + 1):
            try:
                calls += 1
                raw = await self._call_model(topic, depth=depth, research=research, course_title=course_title)
                raw_excerpt = raw[:400]
                content, repaired = self._parse_content(raw)
                return DraftResult(
                    content=content,
                    attempts=attempt,
                    llm_calls=calls,
                    repaired=repaired,
                    raw_excerpt=raw_excerpt,
                )
            except LLMError as exc:
                last_error = str(exc)
                logger.warning("Draft attempt %s/%s failed for %r: %s", attempt, self._settings.max_topic_attempts, topic, exc)
                if attempt < self._settings.max_topic_attempts:
                    await asyncio.sleep(min(2 ** attempt, 8))

        return DraftResult(
            attempts=self._settings.max_topic_attempts,
            llm_calls=calls,
            error=last_error,
            raw_excerpt=raw_excerpt,
        )

    async def _call_model(
        self,
        topic: str,
        *,
        depth: Depth,
        research: ResearchBundle | None,
        course_title: str,
    ) -> str:
        system = _SYSTEM_PROMPT.format(depth_label=_DEPTH_LABELS[depth])
        user = self._build_user_prompt(topic, research=research, course_title=course_title)

        payload: dict[str, Any] = {
            "model": self._settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._settings.openrouter_site_url,
            "X-Title": self._settings.openrouter_app_name,
        }

        client = self._http()
        try:
            response = await client.post(
                f"{self._settings.openrouter_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            if response.status_code >= 400:
                # Some gateways reject response_format; retry once without it.
                if response.status_code == 400 and "response_format" in response.text:
                    payload.pop("response_format", None)
                    response = await client.post(
                        f"{self._settings.openrouter_base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMError(f"model timed out after {self._settings.llm_timeout_seconds}s") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"model returned HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"network error contacting model: {exc}") from exc

        return self._extract_message_text(data)

    @staticmethod
    def _extract_message_text(data: dict) -> str:
        try:
            choices = data["choices"]
            message = choices[0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected model response shape: {str(data)[:200]}") from exc

        content = message.get("content")
        if isinstance(content, list):
            # Some providers return content parts instead of a plain string.
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))

        # Reasoning models sometimes leave `content` empty and put everything in
        # `reasoning_content`. The JSON we need is still in there, so recover it
        # rather than burning a retry.
        if not isinstance(content, str) or not content.strip():
            reasoning = message.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning.strip():
                content = reasoning

        if not isinstance(content, str) or not content.strip():
            raise LLMError("model returned an empty message")
        return content.strip()

    def _build_user_prompt(self, topic: str, *, research: ResearchBundle | None, course_title: str) -> str:
        lines = []
        if course_title:
            lines.append(f"Course: {course_title}")
        lines.append(f"Topic: {topic}")
        if research and research.ok and research.snippets:
            lines.append("")
            lines.append("Research notes (use these facts):")
            for index, snippet in enumerate(research.snippets[:6], start=1):
                lines.append(f"[{index}] {snippet[:600]}")
        else:
            lines.append("")
            lines.append("No research notes available. Use accurate general knowledge and stay conservative.")
        lines.append("")
        lines.append("Return the JSON object now.")
        return "\n".join(lines)

    def _parse_content(self, raw: str) -> tuple[SlideContent, bool]:
        """Parse model output into :class:`SlideContent`, repairing where safe."""

        payload, repaired = self._load_json(raw)
        try:
            return SlideContent.model_validate(payload), repaired
        except ValidationError as exc:
            coerced = self._coerce(payload)
            if coerced is not None:
                try:
                    return SlideContent.model_validate(coerced), True
                except ValidationError:
                    pass
            raise LLMError(f"model JSON did not match the slide schema: {self._summarise(exc)}") from exc

    @staticmethod
    def _load_json(raw: str) -> tuple[dict, bool]:
        repaired = False
        text = raw.strip()

        fenced = _JSON_FENCE.search(text)
        if fenced:
            text = fenced.group(1).strip()
            repaired = True

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            match = _JSON_OBJECT.search(text)
            if not match:
                raise LLMError("model output contained no JSON object") from None
            candidate = match.group(0)
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                candidate = re.sub(r",\s*([}\]])", r"\1", candidate)  # trailing commas
                candidate = candidate.replace("'", '"')
                try:
                    payload = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise LLMError(f"model output was not valid JSON: {exc.msg}") from exc
            repaired = True

        if not isinstance(payload, dict):
            raise LLMError("model JSON was not an object")
        return payload, repaired

    @staticmethod
    def _coerce(payload: dict) -> dict | None:
        """Best-effort normalisation of near-miss shapes.

        Models occasionally return ``{"title": ..., "bullets": ...}`` or a list
        of strings for bullets under a different key. We only accept shapes we
        can map unambiguously; anything else is treated as a failure.
        """

        title = payload.get("slide_title") or payload.get("title")
        bullets = payload.get("bullet_points") or payload.get("bullets") or payload.get("points")
        notes = payload.get("speaker_notes") or payload.get("notes") or payload.get("speakerNotes")

        if isinstance(bullets, str):
            bullets = [line.strip(" -•") for line in bullets.splitlines() if line.strip()]
        if isinstance(bullets, list):
            bullets = [str(item) for item in bullets]

        if not title or not bullets:
            return None

        return {
            "slide_title": str(title),
            "bullet_points": bullets,
            "speaker_notes": str(notes) if notes else "",
        }

    @staticmethod
    def _summarise(exc: ValidationError) -> str:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(part) for part in first.get("loc", ())) or "payload"
        return f"{loc}: {first.get('msg', 'invalid value')}"
