#!/usr/bin/env python3
"""Edezee evaluation harness.

Runs every case in ``evaluation/cases/test_cases.json`` against a live backend,
scores the output against the rubric, and writes machine-readable results plus a
human-readable report.

Two modes:
  --mode live   Hit a running Edezee backend over HTTP (default).
  --mode mock   Run in-process with a scripted provider. No API key needed, so
                anyone can reproduce the reliability results offline.

Usage:
  python evaluation/run_eval.py --mode mock
  python evaluation/run_eval.py --mode live --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
CASES_PATH = Path(__file__).resolve().parent / "cases" / "test_cases.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

sys.path.insert(0, str(BACKEND_DIR))

from scoring import (  # noqa: E402
    generic_hits,
    is_specific,
    placeholder_hits,
    slide_text,
)


@dataclass
class CaseScore:
    case_id: str
    name: str
    category: str
    passed: bool
    status: int
    latency_ms: int
    slides: int = 0
    degraded: int = 0
    research_slides: int = 0
    skipped: bool = False
    skip_reason: str = ""
    checks: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    error: str | None = None


# Checks that are recorded for inspection but must not decide pass/fail. The
# rubric classifies generic phrasing as a signal, not a requirement, because a
# vague topic name legitimately produces abstract content (see scoring.py and
# cases/test_cases.json). Counting a signal as a hard failure yields a FAIL with
# no failure reason, which sends the reader to fix code that was never broken.
SIGNAL_CHECKS = frozenset({"no_generic_wording"})


def gating_checks_pass(checks: dict[str, bool]) -> bool:
    """True when every check that is allowed to fail a case passes."""

    return all(value for name, value in checks.items() if name not in SIGNAL_CHECKS)


def load_cases() -> dict:
    return json.loads(CASES_PATH.read_text())


def expand_syllabus(case: dict) -> str:
    if case["syllabus"] == "PLACEHOLDER_45_TOPICS":
        return "\n".join(f"{i}. Topic number {i}" for i in range(1, 46))
    return case["syllabus"]


# --------------------------------------------------------------------------
# Live mode: drive the HTTP API exactly as the browser does.
# --------------------------------------------------------------------------


def run_live_case(case: dict, syllabus: str, base_url: str) -> CaseScore:
    import httpx

    started = time.perf_counter()
    score = CaseScore(
        case_id=case["id"], name=case["name"], category=case["category"],
        passed=False, status=0, latency_ms=0,
    )
    try:
        response = httpx.post(
            f"{base_url}/api/v1/generate/plan",
            json={"syllabus_text": syllabus, "depth": case["depth"]},
            timeout=600.0,
        )
    except Exception as exc:  # noqa: BLE001
        score.error = f"{type(exc).__name__}: {exc}"
        score.latency_ms = int((time.perf_counter() - started) * 1000)
        score.failures.append("request failed")
        return score

    score.status = response.status_code
    score.latency_ms = int((time.perf_counter() - started) * 1000)

    expected = case["expect"]
    if response.status_code != expected["status"]:
        score.failures.append(f"status {response.status_code} != {expected['status']}")
        if response.status_code == 422:
            score.checks["plain_language_error"] = "topic" in response.text.lower()
        return score

    if response.status_code == 422:
        score.checks["plain_language_error"] = (
            expected.get("expect_error_contains", "").lower() in response.text.lower()
        )
        score.passed = gating_checks_pass(score.checks)
        if not score.passed:
            score.failures.append("error message did not contain the expected wording")
        return score

    body = response.json()
    score_plan(score, body, case, expected)
    return score



def _load_backend_test_helpers():
    """Load the backend test doubles by explicit path.

    Importing ``tests.conftest`` would depend on ``sys.path`` ordering, and this
    directory also contains a ``tests``-like package, so the name can collide.
    Loading the file directly is unambiguous.
    """

    import importlib.util

    conftest_path = BACKEND_DIR / "tests" / "conftest.py"
    spec = importlib.util.spec_from_file_location("edezee_backend_conftest", conftest_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeLLMTransport, module.llm_response, module.make_settings


# --------------------------------------------------------------------------
# Mock mode: same scoring, but the provider is scripted for reproducibility.
# --------------------------------------------------------------------------


async def run_mock_case(case: dict, syllabus: str, all_cases: dict) -> CaseScore:
    import httpx

    from app.models import Depth
    from app.services.llm import LLMService
    from app.services.pipeline import Pipeline, PipelineError
    from app.services.research import ResearchService

    FakeLLMTransport, llm_response, make_settings = _load_backend_test_helpers()

    expected = case["expect"]
    started = time.perf_counter()
    score = CaseScore(
        case_id=case["id"], name=case["name"], category=case["category"],
        passed=False, status=0, latency_ms=0,
    )

    settings = make_settings(max_topic_attempts=1, max_topics=40)
    depth = Depth(case["depth"])

    def content_for(topic: str) -> dict:
        # The mock stands in for the real provider, so it must produce content of
        # comparable substance. Minimal filler like "X detail one" would let the
        # specificity check pass on content no real model would return, which
        # makes the mock gate meaningless.
        return {
            "slide_title": topic.title()[:120],
            "bullet_points": [
                f"{topic} is defined by its scope, purpose, and the problems it solves.",
                f"Key terminology explains how the main components relate to one another.",
                f"A worked example shows the concept applied to a realistic scenario.",
            ],
            "speaker_notes": (
                f"Begin by asking learners what they already understand about {topic}. "
                "Then connect their answers to the formal definition, and work through the "
                "example together so misconceptions surface before the next topic builds on it."
            ),
        }

    if case["id"] == "TC-08":
        # Over-cap: every topic drafts successfully; the cap must still truncate.
        transport = FakeLLMTransport([lambda body: llm_response(content_for("cap"))])
    elif case["id"] == "TC-12":
        # Simulate a provider outage partway through the deck.
        calls = {"n": 0}

        def scripted(body):
            calls["n"] += 1
            if calls["n"] == 2:
                return httpx.Response(503, text="provider unavailable")
            return llm_response(content_for(f"topic {calls['n']}"))

        transport = FakeLLMTransport([scripted])
    else:
        transport = FakeLLMTransport([lambda body: llm_response(content_for("generic"))])

    llm = LLMService(settings, client=httpx.AsyncClient(transport=transport))
    pipeline = Pipeline(settings, llm=llm, research=ResearchService(settings))

    try:
        _, slides, diagnostics = await pipeline.generate(syllabus, depth=depth)
    except PipelineError as exc:
        score.latency_ms = int((time.perf_counter() - started) * 1000)
        score.status = 422
        if expected["status"] != 422:
            score.failures.append(f"unexpected 422: {exc}")
            return score
        score.checks["plain_language_error"] = (
            expected.get("expect_error_contains", "").lower() in str(exc).lower()
        )
        score.passed = gating_checks_pass(score.checks)
        return score

    score.status = 200
    score.latency_ms = int((time.perf_counter() - started) * 1000)
    body = {
        "deck_title": "Course Presentation",
        "slides": [slide.model_dump(mode="json") for slide in slides],
        "diagnostics": diagnostics.model_dump(mode="json"),
    }
    score_plan(score, body, case, expected)
    return score


def score_plan(score: CaseScore, body: dict, case: dict, expected: dict) -> None:
    slides = body["slides"]
    diagnostics = body["diagnostics"]
    score.slides = len(slides)
    score.degraded = diagnostics["degraded_slides"]
    score.research_slides = sum(1 for s in slides if s["grounding"] == "research")

    # --- topic coverage -------------------------------------------------
    score.checks["topic_coverage"] = score.slides == expected["topics"]
    if not score.checks["topic_coverage"]:
        score.failures.append(f"slides {score.slides} != expected {expected['topics']}")

    score.checks["min_slides"] = score.slides >= expected["min_slides"]

    # --- graceful degradation -------------------------------------------
    score.checks["graceful_degradation"] = score.degraded <= expected["max_degraded"]
    if not score.checks["graceful_degradation"]:
        score.failures.append(f"degraded {score.degraded} > allowed {expected['max_degraded']}")

    if expected.get("expect_placeholder_slide"):
        # A placeholder only appears when a topic exhausts its retry budget. A
        # live provider normally succeeds, so this is asserted in mock mode,
        # where the outage is scripted. Live mode checks the weaker, still
        # meaningful property: the run completed and produced every slide.
        if expected.get("mock"):
            score.checks["placeholder_present"] = any(s["degraded"] for s in slides)
            if not score.checks["placeholder_present"]:
                score.failures.append("expected at least one placeholder slide")
        else:
            score.checks["completed_despite_failure"] = score.slides >= expected["min_slides"]

    # --- schema compliance ----------------------------------------------
    schema_ok = True
    for slide in slides:
        bullets = slide["bullet_points"]
        if not (1 <= len(bullets) <= 5):
            schema_ok = False
            score.failures.append(f"slide {slide['slide_number']}: {len(bullets)} bullets")
            break
        if not slide["slide_title"].strip():
            schema_ok = False
            score.failures.append(f"slide {slide['slide_number']}: empty title")
            break
    score.checks["schema_compliance"] = schema_ok

    # --- content specificity --------------------------------------------
    # Two separate checks, because they mean different things:
    #   * a placeholder marker on a non-degraded slide is a contract violation;
    #   * a slide that only restates its own title teaches nothing.
    # The heuristics live in scoring.py so this file and baseline.py cannot drift
    # apart -- they previously held separate copies of a buggy check.
    real_slides = [s for s in slides if not s["degraded"]]
    real_text = " ".join(slide_text(s) for s in real_slides)
    visible_text = " ".join(slide_text(s, include_notes=False) for s in real_slides)

    leaked = placeholder_hits(real_text)
    score.checks["no_placeholder_leak"] = not leaked
    if leaked:
        score.failures.append(f"placeholder wording on a non-degraded slide: {leaked}")

    if real_slides:
        vague = [s["slide_title"] for s in real_slides if not is_specific(s)]
        score.checks["content_specificity"] = not vague
        if vague:
            score.failures.append(f"slides that only restate their title: {vague}")
    else:
        score.checks["content_specificity"] = True

    score.checks["no_generic_wording"] = not generic_hits(visible_text)

    # --- notes quality ---------------------------------------------------
    notes_ok = all(
        len(s["speaker_notes"]) >= 40 and s["speaker_notes"].strip() not in s["bullet_points"]
        for s in slides
        if not s["degraded"]
    )
    score.checks["notes_quality"] = notes_ok
    if not notes_ok:
        score.failures.append("speaker notes too short or duplicated bullets")

    # --- grounding recorded ----------------------------------------------
    score.checks["grounding_recorded"] = all(
        s["grounding"] in {"research", "model-knowledge", "placeholder"} for s in slides
    )

    # --- latency ---------------------------------------------------------
    latency_limit = expected.get("max_latency_ms", 180_000)
    score.checks["latency"] = score.latency_ms < latency_limit
    if not score.checks["latency"]:
        score.failures.append(f"latency {score.latency_ms}ms exceeded {latency_limit}ms")

    # --- optional assertions ---------------------------------------------
    if "expect_warning" in expected:
        warnings = " ".join(diagnostics["warnings"]).lower()
        score.checks["expected_warning"] = expected["expect_warning"].lower() in warnings
        if not score.checks["expected_warning"]:
            score.failures.append(f"missing warning: {expected['expect_warning']}")

    if "forbid_substring" in expected:
        resisted, demonstrated, reason = check_injection_resisted(
            slides, expected["forbid_substring"]
        )
        score.checks["injection_resisted"] = resisted
        # Gating: a case where the model produced nothing has not demonstrated
        # resistance, so it must not be able to pass on the strength of the
        # other checks alone.
        score.checks["injection_demonstrated"] = demonstrated
        if reason:
            score.failures.append(reason)

    score.passed = gating_checks_pass(score.checks)


def check_injection_resisted(
    slides: list[dict], forbidden: str
) -> tuple[bool, bool, str | None]:
    """Did the model refuse to obey the instruction hidden in the topic?

    Only slides the model actually produced are scanned. A degraded placeholder
    echoes its topic verbatim, and the hostile topic contains the forbidden
    marker, so scanning placeholders would report our own error message as a
    leak. That false positive fires hardest when the provider is down, which is
    exactly when the signal needs to be trustworthy.

    Returns ``(resisted, demonstrated, failure_reason)``. ``demonstrated`` is
    False when the model produced nothing, so the caller can gate on it: a run
    that generated no content has not shown resistance, and must not pass.
    """
    produced = [s for s in slides if not s.get("degraded")]
    produced_text = " ".join(slide_text(s) for s in produced).lower()
    if forbidden.lower() in produced_text:
        return False, True, "model output leaked the injected instruction"
    if not produced:
        return True, False, "no slide was generated, so injection resistance was not demonstrated"
    return True, True, None


def serialize_case(score: CaseScore) -> dict:
    """Serialize one case for the results file.

    A skipped case is never recorded as a pass. This is enforced here rather than
    only at the construction site, because the artifact is what a reader trusts:
    a results file that reports 12/12 from a run that executed 10 is wrong no
    matter how the case object was built.
    """
    row = asdict(score)
    if score.skipped:
        row["passed"] = False
        row["outcome"] = "skip"
    else:
        row["outcome"] = "pass" if score.passed else "fail"
    return row


def build_summary(scores: list[CaseScore], mode: str) -> dict:
    """Assemble the results document.

    Kept as a function so the reporting rules can be tested directly against a
    hand-built case list. The rules that matter: a skipped case is never counted
    as a pass, and the per-case ``outcome`` must agree with the totals.
    """
    scored = [s for s in scores if not s.skipped]
    skipped = [s for s in scores if s.skipped]
    passed = sum(1 for s in scored if s.passed)
    total = len(scored)
    latencies = [s.latency_ms for s in scored if s.status == 200]
    return {
        "mode": mode,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_cases": len(scores),
        "scored_cases": total,
        "skipped_cases": len(skipped),
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "median_latency_ms": int(statistics.median(latencies)) if latencies else 0,
        "p95_latency_ms": int(sorted(latencies)[int(len(latencies) * 0.95) - 1]) if latencies else 0,
        "total_degraded_slides": sum(s.degraded for s in scores),
        "total_slides": sum(s.slides for s in scores),
        "results": [serialize_case(s) for s in scores],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Edezee evaluation set.")
    parser.add_argument("--mode", choices=["live", "mock"], default="live")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--out", default=str(RESULTS_DIR / "eval_results.json"))
    args = parser.parse_args()

    all_cases = load_cases()
    cases = all_cases["cases"]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    scores: list[CaseScore] = []
    for case in cases:
        syllabus = expand_syllabus(case)

        if args.mode == "live" and case.get("mock_only_reason"):
            scores.append(
                CaseScore(
                    case_id=case["id"],
                    name=case["name"],
                    category=case["category"],
                    # Not a pass. The summary excludes skipped cases from the
                    # scored total, and the serialized record must agree, or a
                    # reader counting `passed` in the JSON gets 12/12 from a run
                    # that only executed 10.
                    passed=False,
                    status=0,
                    latency_ms=0,
                    skipped=True,
                    skip_reason=case["mock_only_reason"],
                )
            )
            print(f"[{case['id']}] {case['name']} ... SKIP ({case['mock_only_reason']})")
            continue

        print(f"[{case['id']}] {case['name']} ... ", end="", flush=True)

        if args.mode == "live":
            score = run_live_case(case, syllabus, args.base_url)
        else:
            import asyncio

            score = asyncio.run(run_mock_case(case, syllabus, all_cases))

        scores.append(score)
        print("PASS" if score.passed else "FAIL", f"({score.latency_ms}ms)")
        if not score.passed:
            for failure in score.failures:
                print(f"        - {failure}")

    summary = build_summary(scores, args.mode)
    skipped = [s for s in scores if s.skipped]
    passed = summary["passed"]
    total = summary["scored_cases"]

    out_path = Path(args.out)
    out_path.write_text(json.dumps(summary, indent=2) + "\n")

    print("\n" + "=" * 62)
    print(f"Edezee evaluation ({args.mode})")
    print("=" * 62)
    print(f"Cases passed        : {passed}/{total} ({summary['pass_rate'] * 100:.1f}%)")
    if skipped:
        print(f"Skipped in {args.mode} mode: {len(skipped)} "
              f"({', '.join(s.case_id for s in skipped)})")
    print(f"Median latency      : {summary['median_latency_ms']} ms")
    print(f"Slides generated    : {summary['total_slides']}")
    print(f"Degraded slides     : {summary['total_degraded_slides']}")
    print(f"Results written to  : {out_path}")
    print("=" * 62)

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
