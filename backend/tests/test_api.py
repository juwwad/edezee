"""HTTP contract tests for the FastAPI surface.

These assert the shapes a non-developer's browser depends on: the file download
headers, the JSON plan envelope, the SSE event sequence, and the plain-English
error bodies for bad input.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.llm import LLMService
from app.services.pipeline import Pipeline
from app.services.research import ResearchService
from tests.conftest import FakeLLMTransport, llm_response, make_settings

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def content_for(topic: str) -> dict:
    return {
        "slide_title": topic,
        "bullet_points": [f"{topic} one", f"{topic} two", f"{topic} three"],
        "speaker_notes": f"Notes for {topic}.",
    }


@pytest.fixture
def client():
    settings = make_settings()
    responses = [llm_response(content_for(f"Topic {i}")) for i in range(1, 6)]
    llm = LLMService(settings, client=httpx.AsyncClient(transport=FakeLLMTransport(responses)))
    app = create_app(settings)
    app.state.pipeline = Pipeline(settings, llm=llm, research=ResearchService(settings))
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_configuration(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is True
    assert body["research_configured"] is False


def test_generate_returns_pptx_attachment(client):
    response = client.post(
        "/api/v1/generate",
        json={"syllabus_text": "1. Topic 1\n2. Topic 2", "depth": "High-Level"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == PPTX_MIME
    assert ".pptx" in response.headers["content-disposition"]
    assert response.content[:2] == b"PK"
    diagnostics = json.loads(response.headers["x-edezee-diagnostics"])
    assert diagnostics["slides_generated"] == 2
    assert diagnostics["degraded_slides"] == 0


def test_non_latin_deck_title_still_returns_a_downloadable_deck(client):
    """A non-Latin title must not crash the download.

    ``Content-Disposition`` is encoded as latin-1, so a filename containing CJK
    or other non-latin-1 characters raised UnicodeEncodeError and turned a valid
    request into HTTP 500.
    """
    response = client.post(
        "/api/v1/generate",
        json={
            "syllabus_text": "1. Topic 1\n2. Topic 2",
            "deck_title": "课程演示",
        },
    )
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.encode("latin-1")  # the header itself must be encodable
    assert disposition.endswith('.pptx"')


def test_accented_deck_title_produces_an_ascii_filename(client):
    response = client.post(
        "/api/v1/generate",
        json={"syllabus_text": "1. Topic 1\n2. Topic 2", "deck_title": "Überblick über KI"},
    )
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.isascii(), disposition


def test_generate_plan_returns_structured_json(client):
    response = client.post(
        "/api/v1/generate/plan",
        json={"syllabus_text": "1. Topic 1\n2. Topic 2\n3. Topic 3", "depth": "In-Depth"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["deck_title"] == "Course Presentation"
    assert len(body["slides"]) == 3
    assert body["slides"][0]["slide_number"] == 1
    assert body["slides"][0]["grounding"] in {"research", "model-knowledge", "placeholder"}
    assert body["diagnostics"]["depth"] == "In-Depth"


def test_empty_syllabus_returns_422_with_plain_message(client):
    response = client.post("/api/v1/generate", json={"syllabus_text": "   "})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str), "the UI reads detail as a string, not an error array"
    assert "topic" in detail.lower()


def test_empty_string_syllabus_gets_the_same_plain_message(client):
    """An empty string must not fall through to a developer-facing Pydantic message."""
    response = client.post("/api/v1/generate", json={"syllabus_text": ""})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "topic" in detail.lower()
    assert "at least 1 character" not in detail


def test_missing_syllabus_field_gets_a_plain_message(client):
    response = client.post("/api/v1/generate", json={})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "topic" in detail.lower()


def test_unknown_depth_is_rejected_with_a_string_detail(client):
    response = client.post(
        "/api/v1/generate", json={"syllabus_text": "1. Real topic", "depth": "Extreme"}
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_unknown_depth_does_not_leak_the_pydantic_enum_message(client):
    response = client.post(
        "/api/v1/generate", json={"syllabus_text": "1. Real topic", "depth": "Extreme"}
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Input should be" not in detail
    assert "High-level" in detail or "options" in detail.lower()


def test_oversized_syllabus_does_not_leak_the_pydantic_length_message(client):
    response = client.post(
        "/api/v1/generate", json={"syllabus_text": "x" * 20_001}
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "at most" not in detail
    assert "too long" in detail.lower()


def test_oversized_deck_title_does_not_leak_the_pydantic_length_message(client):
    response = client.post(
        "/api/v1/generate",
        json={"syllabus_text": "1. Real topic", "deck_title": "t" * 201},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "at most" not in detail
    assert "title" in detail.lower()


def test_malformed_json_body_returns_a_plain_message(client):
    response = client.post(
        "/api/v1/generate",
        content="{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "JSON decode error" not in detail


def test_unparseable_syllabus_returns_plain_language_error(client):
    response = client.post("/api/v1/generate", json={"syllabus_text": "---\n===\n#\n"})
    assert response.status_code == 422
    assert "topic" in response.json()["detail"].lower()


def test_stream_emits_progress_then_done(client):
    with client.stream(
        "POST",
        "/api/v1/generate/stream",
        json={"syllabus_text": "1. Topic 1\n2. Topic 2", "depth": "High-Level"},
    ) as response:
        assert response.status_code == 200
        events = [
            json.loads(line[len("data: "):])
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]

    types = [event["type"] for event in events]
    assert types[0] == "progress"
    assert types[-1] == "done"
    assert any(event.get("stage") == "drafting" for event in events if event["type"] == "progress")

    done = events[-1]
    assert done["slides"] == 2
    assert done["filename"].endswith(".pptx")
    assert done["deck_base64"]


def test_non_json_provider_response_does_not_500():
    """A provider 200 with an HTML body must not become an HTTP 500.

    Gateways and CDNs in front of the model sometimes return an HTML error page
    with a 200 status. The deck must still finish: every topic degrades to a
    flagged placeholder rather than the request failing outright.
    """
    settings = make_settings(max_topic_attempts=1)

    class HtmlTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, text="<html>502 Bad Gateway</html>", request=request)

    llm = LLMService(settings, client=httpx.AsyncClient(transport=HtmlTransport()))
    app = create_app(settings)
    app.state.pipeline = Pipeline(settings, llm=llm, research=ResearchService(settings))
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/api/v1/generate",
            json={"syllabus_text": "1. Topic 1\n2. Topic 2", "depth": "High-Level"},
        )

    assert response.status_code == 200, response.text
    assert response.content[:2] == b"PK"
    diagnostics = json.loads(response.headers["x-edezee-diagnostics"])
    assert diagnostics["degraded_slides"] == 2


def test_stream_reports_pipeline_error_as_event():
    settings = make_settings()
    app = create_app(settings)
    app.state.pipeline = Pipeline(settings, llm=LLMService(settings), research=ResearchService(settings))
    with TestClient(app) as test_client:
        with test_client.stream(
            "POST", "/api/v1/generate/stream", json={"syllabus_text": "---"}
        ) as response:
            events = [
                json.loads(line[len("data: "):])
                for line in response.iter_lines()
                if line.startswith("data: ")
            ]
    assert events[-1]["type"] == "error"
    assert "topic" in events[-1]["message"].lower()


def test_missing_api_key_returns_actionable_error():
    settings = make_settings(openrouter_api_key="")
    app = create_app(settings)
    app.state.pipeline = Pipeline(settings, llm=LLMService(settings), research=ResearchService(settings))
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/generate", json={"syllabus_text": "1. Real topic"})
    assert response.status_code == 422
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_demo_mode_generates_a_deck_with_no_api_key():
    """DEMO_MODE must let a reviewer exercise the full flow without a secret."""
    settings = make_settings(openrouter_api_key="", demo_mode=True)
    app = create_app(settings)
    with TestClient(app) as test_client:
        health = test_client.get("/api/v1/health").json()
        assert health["llm_configured"] is True

        response = test_client.post(
            "/api/v1/generate",
            json={"syllabus_text": "1. Vector databases\n2. Chunking strategies", "depth": "High-Level"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == PPTX_MIME
    assert response.content[:2] == b"PK", "the response must be a real .pptx (zip) payload"


def test_demo_mode_slides_carry_a_sample_content_warning():
    settings = make_settings(openrouter_api_key="", demo_mode=True)
    app = create_app(settings)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/generate/plan", json={"syllabus_text": "1. Real topic"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["diagnostics"]["slides_generated"] == 1
    assert any("sample content" in w.lower() for w in body["diagnostics"]["warnings"])
    assert body["slides"][0]["slide_title"]


def test_demo_mode_off_by_default_keeps_the_missing_key_error():
    settings = make_settings(openrouter_api_key="")
    assert settings.llm_configured is False


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/api/v1/generate",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


# --- Demo provider -------------------------------------------------------
#
# The demo provider is what a reviewer without an API key sees first, so its
# output is part of the product surface. These tests pin the properties that
# make it usable in a recording: known topics get distinct real content, the
# depth toggle changes the deck, and the same input always replays the same way.


def _demo_plan(syllabus_text: str, depth: str = "High-Level"):
    settings = make_settings(openrouter_api_key="", demo_mode=True)
    app = create_app(settings)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/generate/plan",
            json={"syllabus_text": syllabus_text, "depth": depth},
        )
    assert response.status_code == 200
    return response.json()


def test_demo_gives_each_sample_topic_distinct_content():
    """The bundled sample syllabus must not collapse to one template.

    Regression guard: the original provider substituted the topic into a single
    fixed sentence triple, so every slide in the demo read identically.
    """
    body = _demo_plan(
        "1. What is retrieval-augmented generation (RAG)?\n"
        "2. Vector embeddings and similarity search\n"
        "3. Chunking strategies for documents\n"
        "4. Evaluating answer faithfulness"
    )
    slides = body["slides"]
    assert len(slides) == 4

    bullet_sets = {tuple(s["bullet_points"]) for s in slides}
    assert len(bullet_sets) == 4, "each topic must get its own bullets"

    notes = [s["speaker_notes"] for s in slides]
    assert len(set(notes)) == 4, "each topic must get its own speaker notes"


def test_demo_content_is_specific_to_its_topic():
    """Bullets must talk about the topic, not about 'this topic'."""
    body = _demo_plan("1. Chunking strategies for documents")
    bullets = " ".join(body["slides"][0]["bullet_points"]).lower()
    assert "chunk" in bullets
    assert "this topic" not in bullets


def test_demo_depth_toggle_changes_the_deck():
    """High-level and in-depth must not return identical content."""
    syllabus = "1. What is retrieval-augmented generation (RAG)?"
    high = _demo_plan(syllabus, depth="High-Level")["slides"][0]
    deep = _demo_plan(syllabus, depth="In-Depth")["slides"][0]

    assert high["bullet_points"] != deep["bullet_points"]
    assert len(deep["bullet_points"]) >= len(high["bullet_points"])


def test_demo_is_deterministic():
    """A recorded demo must replay exactly, so output is a pure function."""
    syllabus = "1. Vector embeddings and similarity search"
    first = _demo_plan(syllabus, depth="In-Depth")
    second = _demo_plan(syllabus, depth="In-Depth")
    assert first["slides"] == second["slides"]


def test_demo_unknown_topic_falls_back_without_filler():
    """A topic outside the library still gets anchored, non-placeholder text."""
    body = _demo_plan("1. Llama grooming techniques")
    slide = body["slides"][0]
    bullets = " ".join(slide["bullet_points"]).lower()
    assert "llama grooming" in bullets
    assert "tbd" not in bullets
    assert "lorem ipsum" not in bullets


def test_demo_keyword_match_does_not_fire_mid_word():
    """A keyword must match a whole word, not a substring inside another word.

    The "rag" keyword matched the "rag" inside "storage", "average", and
    "paragraph", so a topic unrelated to retrieval-augmented generation was
    served the RAG slide instead of its own anchored fallback.
    """
    body = _demo_plan("1. Storage and memory\n2. Average speed and velocity")
    for slide in body["slides"]:
        bullets = " ".join(slide["bullet_points"]).lower()
        assert "rag lets a language model" not in bullets, slide["slide_title"]
        assert slide["slide_title"].lower().split()[0] in bullets


def test_demo_known_topic_still_matches():
    """The word-boundary rule must not stop a real keyword from matching."""
    body = _demo_plan("1. What is retrieval-augmented generation (RAG)?")
    bullets = " ".join(body["slides"][0]["bullet_points"]).lower()
    assert "retrieval" in bullets or "rag" in bullets

class _SlowPipeline:
    """A pipeline that never finishes on its own, so cancellation is observable."""

    def __init__(self) -> None:
        self.progress_sent = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def generate(self, syllabus_text, *, depth=None, deck_title="", on_progress=None):
        if on_progress is not None:
            await on_progress("parsing", "Parsing 1 topics...", 0, 1)
        self.progress_sent.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        return "Deck", [], None


async def _stream_then_disconnect(app, pipeline: _SlowPipeline) -> tuple[bool, bool]:
    """Run one stream request over ASGI, then drop the connection mid-run.

    Returns ``(reached_pipeline, stopped)``. ``stopped`` is read while the loop is
    still running: ``asyncio.run`` cancels leftover tasks on exit, so asserting
    afterwards would report a pipeline that was never cancelled as stopped.
    """

    body = json.dumps({"syllabus_text": "1. Real topic"}).encode()
    body_read = False

    async def receive():
        nonlocal body_read
        if not body_read:
            body_read = True
            return {"type": "http.request", "body": body, "more_body": False}
        await pipeline.progress_sent.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        return None

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/generate/stream",
        "raw_path": b"/api/v1/generate/stream",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json"), (b"host", b"test")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }

    await asyncio.wait_for(app(scope, receive, send), timeout=10)
    try:
        await asyncio.wait_for(pipeline.cancelled.wait(), timeout=2)
    except asyncio.TimeoutError:
        return pipeline.progress_sent.is_set(), False
    return True, True


def test_client_disconnect_cancels_the_running_pipeline():
    """The Cancel button aborts the fetch, so the server must stop drafting.

    Without cancelling the background task, a cancelled run kept calling the
    model for every remaining topic after the browser had already gone away.
    """

    app = create_app(make_settings())
    pipeline = _SlowPipeline()
    app.state.pipeline = pipeline

    reached, stopped = asyncio.run(_stream_then_disconnect(app, pipeline))

    assert reached, "the stream never reached the pipeline"
    assert stopped, "pipeline kept running after the client disconnected"
