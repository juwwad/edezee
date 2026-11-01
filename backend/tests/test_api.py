"""HTTP contract tests for the FastAPI surface.

These assert the shapes a non-developer's browser depends on: the file download
headers, the JSON plan envelope, the SSE event sequence, and the plain-English
error bodies for bad input.
"""

from __future__ import annotations

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
    assert "tbd" not in bullets and "lorem ipsum" not in bullets
