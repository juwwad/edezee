#!/usr/bin/env python3
"""Baseline comparison: naive single-prompt ChatGPT use vs the Edezee pipeline.

The problem statement asks for a baseline "under the manual process or simple
ChatGPT use". This script measures the *simple ChatGPT use* case honestly.

Baseline A ("naive one-shot"): paste the whole syllabus into one prompt and ask
for a JSON deck. This is exactly what a teacher does today in a chat window.
Baseline B ("Edezee"): the sequential research + draft pipeline.

Both are scored with the same rubric so the comparison is apples to apples.
Quality is scored on four measurable proxies, because a human "looks nicer"
rating is not reproducible:

* coverage   - did every syllabus topic become a slide?
* specificity- does any slide contain generic filler (TBD, "this topic", ...)?
* anchoring  - how much of each slide's vocabulary actually comes from its topic?
* notes      - do slides carry usable speaker notes?

Run:
  python evaluation/baseline.py --topics 3 --out evaluation/results/baseline.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

RESULTS_DIR = Path(__file__).resolve().parent / "results"

GENERIC_MARKERS = [
    "tbd", "n/a", "lorem ipsum", "this topic", "placeholder", "todo",
    "important concept", "various aspects", "and more", "etc.", "discussed below",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "as", "by", "at", "from", "that", "this", "it", "be", "can", "how",
    "what", "why", "when", "which", "into", "between", "vs", "using", "use",
    "overview", "introduction", "basics", "concept", "concepts", "part", "chapter",
}

BASELINE_SYSTEM = """You are a curriculum assistant. The user gives you a whole course \
syllabus. Return a single JSON object:
{"deck_title": str, "slides": [{"slide_title": str, "bullet_points": [str], "speaker_notes": str}]}
Return one slide per syllabus topic, in order. Return JSON only, no prose."""


@dataclass
class QualityScore:
    coverage: float
    specificity: float
    anchoring: float
    notes: float
    slides: int
    topics: int
    latency_ms: int
    llm_calls: int
    schema_valid: bool
    overall: float = 0.0
    notes_detail: list[str] = field(default_factory=list)


def terms(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def score_deck(slides: list[dict], topics: list[str], latency_ms: int, llm_calls: int) -> QualityScore:
    """Score a deck against the topics it was supposed to cover."""

    from app.services.parser import parse_topics  # noqa: PLC0415

    parsed_topics = parse_topics("\n".join(topics))
    n_topics = len(parsed_topics)
    n_slides = len(slides)
    detail: list[str] = []

    coverage = min(n_slides / n_topics, 1.0) if n_topics else 0.0
    if n_slides != n_topics:
        detail.append(f"coverage: {n_slides} slides for {n_topics} topics")

    schema_valid = True
    for index, slide in enumerate(slides, start=1):
        bullets = slide.get("bullet_points") or []
        if not isinstance(bullets, list) or not (1 <= len(bullets) <= 5):
            schema_valid = False
            detail.append(f"slide {index}: {len(bullets) if isinstance(bullets, list) else 'no'} bullets")
        if not str(slide.get("slide_title", "")).strip():
            schema_valid = False
            detail.append(f"slide {index}: empty title")

    body = " ".join(
        " ".join([str(s.get("slide_title", "")), *[str(b) for b in (s.get("bullet_points") or [])]])
        for s in slides
    ).lower()
    generic_hits = [marker for marker in GENERIC_MARKERS if marker in body]
    specificity = 1.0 - min(len(generic_hits) / 3.0, 1.0)
    if generic_hits:
        detail.append(f"generic filler: {generic_hits}")

    # Anchoring: does each slide's vocabulary overlap the topic it covers?
    overlaps: list[float] = []
    for slide, topic in zip(slides, parsed_topics):
        topic_terms = terms(topic)
        if not topic_terms:
            continue
        slide_terms = terms(
            " ".join([str(slide.get("slide_title", "")), *[str(b) for b in (slide.get("bullet_points") or [])]])
        )
        overlaps.append(len(topic_terms & slide_terms) / len(topic_terms))
    anchoring = statistics.mean(overlaps) if overlaps else 0.0

    note_lengths = [len(str(s.get("speaker_notes", ""))) for s in slides]
    notes = (
        sum(1 for length in note_lengths if length >= 40) / len(note_lengths)
        if note_lengths
        else 0.0
    )
    if notes < 1.0:
        detail.append(f"notes: {sum(1 for x in note_lengths if x >= 40)}/{len(note_lengths)} slides")

    overall = round(
        0.35 * coverage + 0.20 * specificity + 0.25 * anchoring + 0.20 * notes, 4
    )

    return QualityScore(
        coverage=round(coverage, 4),
        specificity=round(specificity, 4),
        anchoring=round(anchoring, 4),
        notes=round(notes, 4),
        slides=n_slides,
        topics=n_topics,
        latency_ms=latency_ms,
        llm_calls=llm_calls,
        schema_valid=schema_valid,
        overall=overall,
        notes_detail=detail,
    )


async def run_naive(syllabus: str, settings) -> tuple[list[dict], int, int]:
    """Baseline A: one prompt for the entire syllabus."""

    import httpx

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": BASELINE_SYSTEM},
            {"role": "user", "content": f"Syllabus:\n{syllabus}"},
        ],
        "temperature": 0.3,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.openrouter_site_url,
        "X-Title": settings.openrouter_app_name,
    }

    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds * 3) as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"].get("content") or ""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        parsed = json.loads(match.group(0)) if match else {}
    return list(parsed.get("slides") or []), 1, 1


async def run_edezee(syllabus: str, settings):
    from app.models import Depth
    from app.services.pipeline import Pipeline

    pipeline = Pipeline(settings)
    _, slides, diagnostics = await pipeline.generate(syllabus, depth=Depth.HIGH_LEVEL)
    as_dicts = [
        {
            "slide_title": s.slide_title,
            "bullet_points": s.bullet_points,
            "speaker_notes": s.speaker_notes,
        }
        for s in slides
    ]
    return as_dicts, diagnostics.llm_calls, diagnostics.research_calls


async def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline vs Edezee comparison.")
    parser.add_argument("--topics", type=int, default=3, help="topics per syllabus")
    parser.add_argument("--repeats", type=int, default=3, help="syllabi to test")
    parser.add_argument("--out", default=str(RESULTS_DIR / "baseline.json"))
    args = parser.parse_args()

    from app.config import Settings  # noqa: PLC0415

    settings = Settings()
    if not settings.llm_configured:
        print("OPENROUTER_API_KEY is not set. Configure backend/.env first.")
        return 1

    syllabi = [
        [
            "What is retrieval-augmented generation (RAG)?",
            "Vector embeddings and similarity search",
            "Chunking strategies for documents",
            "Evaluating answer faithfulness",
        ],
        [
            "Photosynthesis",
            "Light-dependent reactions",
            "The Calvin cycle",
            "Cellular respiration",
        ],
        [
            "Spectral decomposition of compact self-adjoint operators",
            "Gauge invariance in non-abelian Yang-Mills theory",
            "Kolmogorov complexity and incompressibility",
        ],
    ][: args.repeats]
    syllabi = ["\n".join(f"{i}. {t}" for i, t in enumerate(topics, 1)) for topics in syllabi]

    results: dict[str, list[dict]] = {"naive": [], "edezee": []}

    for index, syllabus in enumerate(syllabi, start=1):
        topic_lines = syllabus.splitlines()
        print(f"\nSyllabus {index}: {len(topic_lines)} topics")

        started = time.perf_counter()
        naive_slides, naive_calls, _ = await run_naive(syllabus, settings)
        naive_ms = int((time.perf_counter() - started) * 1000)
        naive_score = score_deck(naive_slides, topic_lines, naive_ms, naive_calls)
        results["naive"].append(asdict(naive_score))
        print(f"  naive  : overall={naive_score.overall} slides={naive_score.slides} "
              f"latency={naive_ms}ms")

        started = time.perf_counter()
        edezee_slides, edezee_calls, research_calls = await run_edezee(syllabus, settings)
        edezee_ms = int((time.perf_counter() - started) * 1000)
        edezee_score = score_deck(edezee_slides, topic_lines, edezee_ms, edezee_calls)
        results["edezee"].append(asdict(edezee_score))
        print(f"  edezee : overall={edezee_score.overall} slides={edezee_score.slides} "
              f"latency={edezee_ms}ms research_calls={research_calls}")

    summary = {}
    for label, rows in results.items():
        summary[label] = {
            "mean_overall": round(statistics.mean(r["overall"] for r in rows), 4),
            "mean_coverage": round(statistics.mean(r["coverage"] for r in rows), 4),
            "mean_anchoring": round(statistics.mean(r["anchoring"] for r in rows), 4),
            "mean_specificity": round(statistics.mean(r["specificity"] for r in rows), 4),
            "mean_notes": round(statistics.mean(r["notes"] for r in rows), 4),
            "schema_valid_all": all(r["schema_valid"] for r in rows),
            "mean_latency_ms": int(statistics.mean(r["latency_ms"] for r in rows)),
            "mean_llm_calls": round(statistics.mean(r["llm_calls"] for r in rows), 2),
        }

    payload = {
        "model": settings.openrouter_model,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "syllabi_tested": len(syllabi),
        "summary": summary,
        "per_syllabus": results,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")

    print("\n" + "=" * 62)
    print("Baseline comparison")
    print("=" * 62)
    header = f"{'metric':<22}{'naive':>12}{'edezee':>12}"
    print(header)
    print("-" * len(header))
    for metric in ["mean_overall", "mean_coverage", "mean_anchoring", "mean_specificity",
                   "mean_notes", "mean_latency_ms", "mean_llm_calls"]:
        print(f"{metric:<22}{summary['naive'][metric]:>12}{summary['edezee'][metric]:>12}")
    print(f"{'schema_valid_all':<22}{str(summary['naive']['schema_valid_all']):>12}"
          f"{str(summary['edezee']['schema_valid_all']):>12}")
    print("=" * 62)
    print(f"Written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
