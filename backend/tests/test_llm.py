"""Unit tests for the LLM drafting service.

These cover the failure modes that break naive LLM integrations in production:
fenced JSON, prose-wrapped JSON, trailing commas, renamed keys, empty bullets,
HTTP errors, and timeouts. Each case asserts both the outcome and the retry
accounting, because the diagnostics are what the operator debugs with.
"""

from __future__ import annotations

import httpx
import pytest

from app.models import Depth
from app.services.llm import LLMService
from tests.conftest import FakeLLMTransport, llm_response, make_settings

VALID = {
    "slide_title": "Introduction to Next.js",
    "bullet_points": ["A React framework.", "Supports SSR.", "Has file routing."],
    "speaker_notes": "Stress that routing is file based.",
}


def build_service(responses, **overrides):
    settings = make_settings(**overrides)
    transport = FakeLLMTransport(responses)
    client = httpx.AsyncClient(transport=transport)
    return LLMService(settings, client=client), transport


@pytest.mark.asyncio
async def test_plain_json_succeeds_first_attempt():
    service, transport = build_service([llm_response(VALID)])
    result = await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL)
    assert result.error is None
    assert result.attempts == 1
    assert result.content is not None
    assert result.content.slide_title == "Introduction to Next.js"
    assert len(transport.requests) == 1


@pytest.mark.asyncio
async def test_fenced_json_is_repaired():
    fenced = f"```json\n{VALID}\n```" if False else '```json\n' + __import__("json").dumps(VALID) + '\n```'
    service, _ = build_service([llm_response(fenced)])
    result = await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL)
    assert result.content is not None
    assert result.repaired is True
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_prose_wrapped_json_is_repaired():
    import json

    prose = "Sure! Here is the slide:\n" + json.dumps(VALID) + "\nHope that helps."
    service, _ = build_service([llm_response(prose)])
    result = await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL)
    assert result.content is not None
    assert result.repaired is True


@pytest.mark.asyncio
async def test_trailing_comma_is_repaired():
    broken = '{"slide_title": "Routing", "bullet_points": ["A", "B"], "speaker_notes": "Note",}'
    service, _ = build_service([llm_response(broken)])
    result = await service.draft_topic("Routing", depth=Depth.HIGH_LEVEL)
    assert result.content is not None
    assert result.content.slide_title == "Routing"


@pytest.mark.asyncio
async def test_renamed_keys_are_coerced():
    alt = {"title": "Data Fetching", "bullets": ["One", "Two"], "notes": "N"}
    service, _ = build_service([llm_response(alt)])
    result = await service.draft_topic("Data Fetching", depth=Depth.HIGH_LEVEL)
    assert result.content is not None
    assert result.content.slide_title == "Data Fetching"
    assert result.repaired is True


@pytest.mark.asyncio
async def test_empty_bullets_fail_after_retries():
    bad = {"slide_title": "Empty", "bullet_points": [], "speaker_notes": "x"}
    service, transport = build_service([llm_response(bad)], max_topic_attempts=2)
    result = await service.draft_topic("Empty", depth=Depth.HIGH_LEVEL)
    assert result.content is None
    assert result.error is not None
    assert result.attempts == 2
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_recovers_on_second_attempt():
    bad = llm_response({"slide_title": "x", "bullet_points": [], "speaker_notes": ""})
    good = llm_response(VALID)
    service, transport = build_service([bad, good], max_topic_attempts=3)
    result = await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL)
    assert result.content is not None
    assert result.attempts == 2
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_http_error_is_reported_not_raised():
    service, _ = build_service([httpx.Response(500, text="boom")])
    result = await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL)
    assert result.content is None
    assert "500" in (result.error or "")


@pytest.mark.asyncio
async def test_timeout_is_reported():
    def raise_timeout(_body):
        raise httpx.ReadTimeout("timed out")

    service, _ = build_service([raise_timeout])
    result = await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL)
    assert result.content is None
    assert "timed out" in (result.error or "")


@pytest.mark.asyncio
async def test_unconfigured_llm_fails_fast():
    service, transport = build_service([llm_response(VALID)], openrouter_api_key="")
    result = await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL)
    assert result.content is None
    assert result.attempts == 0
    assert "not configured" in (result.error or "")
    assert transport.requests == []


@pytest.mark.asyncio
async def test_bullets_are_capped_at_five():
    import json

    many = {
        "slide_title": "Many",
        "bullet_points": [f"Bullet {i}" for i in range(9)],
        "speaker_notes": "n",
    }
    service, _ = build_service([llm_response(json.dumps(many))])
    result = await service.draft_topic("Many", depth=Depth.IN_DEPTH)
    assert result.content is not None
    assert len(result.content.bullet_points) == 5


@pytest.mark.asyncio
async def test_research_notes_are_included_in_prompt():
    from app.services.research import ResearchBundle

    service, transport = build_service([llm_response(VALID)])
    bundle = ResearchBundle(snippets=["Next.js is a React framework."], sources=["https://x"], ok=True)
    await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL, research=bundle)
    prompt = transport.requests[0]["messages"][1]["content"]
    assert "Next.js is a React framework." in prompt


@pytest.mark.asyncio
async def test_json_recovered_from_reasoning_content():
    """Reasoning models can leave `content` empty; the JSON is still recoverable."""
    import json

    import httpx

    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "Thinking...\n" + json.dumps(VALID),
                }
            }
        ]
    }
    response = httpx.Response(
        200, json=payload, request=httpx.Request("POST", "https://llm.test/v1/chat/completions")
    )
    service, transport = build_service([response])
    result = await service.draft_topic("Next.js", depth=Depth.HIGH_LEVEL)
    assert result.content is not None
    assert result.content.slide_title == "Introduction to Next.js"
    assert len(transport.requests) == 1


@pytest.mark.asyncio
async def test_connection_pool_is_reused_across_topics():
    """Two topics must not create two clients.

    Creating a client per call means a fresh TLS handshake per topic. This test
    pins the pooling behaviour so a future refactor cannot silently regress it.
    """
    service, transport = build_service([llm_response(VALID), llm_response(VALID)])

    await service.draft_topic("Topic one", depth=Depth.HIGH_LEVEL)
    pooled = service._client
    await service.draft_topic("Topic two", depth=Depth.HIGH_LEVEL)

    assert service._client is pooled, "the HTTP client was rebuilt between calls"
    assert pooled is not None and not pooled.is_closed
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_aclose_is_safe_for_injected_clients():
    """A test-injected client is not owned by the service, so aclose must not close it."""
    service, _ = build_service([llm_response(VALID)])
    await service.aclose()
    assert service._client is not None and not service._client.is_closed
