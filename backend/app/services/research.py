"""Web research via the Tavily search API.

Research is a *quality* upgrade, not a hard dependency: when Tavily is not
configured or the call fails, the pipeline continues with model-internal
knowledge and records that the slide is ungrounded. That keeps the product
usable for a non-developer who has not signed up for a search vendor yet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class ResearchBundle:
    """Normalised research payload handed to the drafting prompt."""

    snippets: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    ok: bool = False
    error: str | None = None


class ResearchService:
    """Thin, testable wrapper around Tavily's ``/search`` endpoint."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None

    def _http(self) -> httpx.AsyncClient:
        """Reuse one connection pool across topics.

        Creating a client per call means a fresh TLS handshake for every topic,
        which is pure latency on a pipeline that already makes 2 calls per topic.
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
        return self._settings.research_configured

    async def research(self, topic: str, *, depth: str) -> ResearchBundle:
        """Return grounding snippets for ``topic``.

        Never raises: failures are captured in :class:`ResearchBundle` so the
        caller can degrade instead of aborting the whole deck.
        """

        if not self.configured:
            return ResearchBundle(ok=False, error="research provider not configured")

        query = self._build_query(topic, depth)
        payload = {
            "api_key": self._settings.tavily_api_key,
            "query": query,
            "search_depth": self._settings.tavily_search_depth,
            "max_results": self._settings.tavily_max_results,
            "include_answer": True,
            "include_raw_content": False,
        }

        client = self._http()
        try:
            response = await client.post(f"{self._settings.tavily_base_url}/search", json=payload)
            response.raise_for_status()
            data = response.json()
            return self._normalise(data)
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the deck
            logger.warning("Research failed for topic %r: %s", topic, exc)
            return ResearchBundle(ok=False, error=f"{type(exc).__name__}: {exc}")

    def _build_query(self, topic: str, depth: str) -> str:
        if depth == "In-Depth":
            return f"{topic} definition explanation technical details examples"
        return f"{topic} definition overview key concepts"

    @staticmethod
    def _normalise(data: dict) -> ResearchBundle:
        snippets: list[str] = []
        sources: list[str] = []

        answer = data.get("answer")
        if isinstance(answer, str) and answer.strip():
            snippets.append(answer.strip())

        for result in data.get("results") or []:
            if not isinstance(result, dict):
                continue
            content = (result.get("content") or "").strip()
            if content:
                snippets.append(content)
            url = (result.get("url") or "").strip()
            if url and url not in sources:
                sources.append(url)

        return ResearchBundle(
            snippets=snippets,
            sources=sources,
            ok=bool(snippets),
            error=None if snippets else "search returned no usable content",
        )
