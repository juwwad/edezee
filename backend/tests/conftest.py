"""Shared pytest fixtures: a deterministic fake LLM and a fake search client.

Tests must exercise the real pipeline, parser, validator, and PPTX writer. The
only things replaced are the two external network calls, which are replaced at
the HTTP client boundary (not by patching pipeline internals), so the code
under test is the same code that runs in production.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings


def make_settings(**overrides) -> Settings:
    base = dict(
        openrouter_api_key="test-key",
        openrouter_base_url="https://llm.test/v1",
        openrouter_model="test/model",
        tavily_api_key="",
        tavily_base_url="https://search.test",
        max_topic_attempts=2,
        llm_timeout_seconds=5,
        max_topics=40,
        inter_topic_delay_seconds=0,
    )
    base.update(overrides)
    return Settings(**base)


def llm_response(payload: dict | str, status: int = 200) -> httpx.Response:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        status,
        json={"choices": [{"message": {"role": "assistant", "content": content}}]},
        request=httpx.Request("POST", "https://llm.test/v1/chat/completions"),
    )


class FakeLLMTransport(httpx.AsyncBaseTransport):
    """Returns canned responses in order, then repeats the last one.

    ``responses`` items may be an ``httpx.Response`` or a callable taking the
    parsed request body.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        self.requests.append(body)
        item = self.responses[min(len(self.requests) - 1, len(self.responses) - 1)]
        if callable(item):
            return item(body)
        return item


@pytest.fixture
def settings() -> Settings:
    return make_settings()
