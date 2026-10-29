"""Zero-config demo provider.

A reviewer who clones the repository should be able to press "Generate" and see
the whole product — SSE progress, the slide review panel, the ``.pptx`` download
— without signing up for an API key. ``DEMO_MODE=true`` swaps the real provider
for this deterministic scripted one.

This is a reliability aid for demos, not a product feature. It is off by
default, it never runs unless the operator asks for it, and every run it serves
carries an explicit warning so nobody mistakes the sample text for model output.
The real pipeline, parser, validator, and PPTX writer are unchanged.
"""

from __future__ import annotations

import json

import httpx

from app.config import Settings


def demo_content(topic: str) -> dict:
    """Sample slide content for ``topic``.

    The text is deliberately substantive rather than lorem ipsum: the review
    panel scores specificity, and filler would make the demo look broken.
    """
    title = topic.strip().rstrip("?.") or "Untitled topic"
    return {
        "slide_title": title[:120],
        "bullet_points": [
            f"{title} is defined by its scope, its purpose, and the problems it is meant to solve.",
            "Its main components interact in a fixed order, and each one depends on the last.",
            "A worked example shows the idea applied to a realistic scenario a learner can picture.",
        ],
        "speaker_notes": (
            f"Open by asking the group what they already know about {title}. "
            "Use their answers to introduce the formal definition, then walk through the "
            "example together so any misconceptions surface before the next topic builds on it."
        ),
    }


class DemoTransport(httpx.AsyncBaseTransport):
    """Answers every chat-completion request with demo content for the topic.

    It parses the topic out of the prompt so the deck matches what the user
    typed, and it counts requests so the demo can be reproduced exactly.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        body = json.loads(request.content.decode())
        topic = _topic_from_messages(body.get("messages", []))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(demo_content(topic))}}]},
            request=request,
        )


def _topic_from_messages(messages: list[dict]) -> str:
    for message in reversed(messages):
        content = message.get("content")
        if not isinstance(content, str):
            continue
        for line in content.splitlines():
            if line.startswith("Topic:"):
                return line.removeprefix("Topic:").strip()
    return "Untitled topic"


def build_demo_llm(settings: Settings):
    """An :class:`LLMService` wired to the scripted provider.

    Imported lazily to avoid a circular import: ``llm`` does not import ``demo``.
    """
    from app.services.llm import LLMService

    client = httpx.AsyncClient(transport=DemoTransport(), timeout=settings.llm_timeout_seconds)
    return LLMService(settings, client=client)
