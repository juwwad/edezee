"""Tests for the evaluation harness's own scoring heuristics.

The harness is the thing that judges the system, so it needs tests of its own.
An evaluation bug that produces a believable failure is worse than no evaluation
at all: it sends you to fix code that was never broken. Two defects found during
the sprint were of that kind (see docs/case-study.md, F5 and the TC-03 false
failure), so the heuristics are pinned here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # evaluation/

from baseline import _injection_leaked  # noqa: E402
from run_eval import CaseScore, gating_checks_pass, score_plan  # noqa: E402
from scoring import is_specific  # noqa: E402


def slide(title: str, bullets: list[str], notes: str = "Guidance for the teacher.") -> dict:
    return {"slide_title": title, "bullet_points": bullets, "speaker_notes": notes, "degraded": False}


@pytest.mark.parametrize(
    "case,expected,why",
    [
        # Should be judged specific: the bullet carries information.
        (
            slide("Basics", ["Variables store values that change during program execution."]),
            True,
            "a real definition",
        ),
        (
            slide("Hash maps", ["Average lookup is constant time because keys hash to buckets."]),
            True,
            "a specific mechanism",
        ),
        (
            slide("Recursion", ["A base case stops the recursion before the stack overflows."]),
            True,
            "a specific failure mode",
        ),
        (
            slide("Next.js", ["Server components render on the server and ship no JavaScript."]),
            True,
            "a concrete distinction",
        ),
        # Should be judged unspecific: nothing is said beyond the title.
        (
            slide("Topic 1", ["Topic 1 detail one", "Topic 1 detail two"]),
            False,
            "restates the title",
        ),
        (
            slide("Basics", ["This topic covers the basics."]),
            False,
            "generic filler",
        ),
        (
            slide("Introduction", ["An introduction explains what this topic covers."]),
            False,
            "generic filler with a connective verb",
        ),
        (
            slide(
                "Introduction",
                ["An introduction explains what this topic covers and why it is worth learning."],
            ),
            False,
            "generic filler padded to look substantial",
        ),
    ],
)
def test_specificity_heuristic(case, expected, why):
    assert is_specific(case) is expected, why


def test_specificity_ignores_speaker_notes():
    """Notes are teaching guidance, not slide content.

    A blacklist that read the notes flagged "ask what learners know about this
    topic" as generic and failed a perfectly good case. Only title and bullets
    are in scope.
    """
    case = slide(
        "Basics",
        ["Variables store values that change during program execution."],
        notes="Open by asking learners what they already know about this topic.",
    )
    assert is_specific(case) is True


def test_specificity_requires_only_one_good_bullet():
    case = slide(
        "Basics",
        [
            "Overview.",
            "This topic covers the basics.",
            "Variables store values that change during execution.",
        ],
    )
    assert is_specific(case) is True


def test_specificity_handles_no_bullets():
    assert is_specific(slide("Empty", [])) is False


class TestInjectionDetection:
    """The comparison claims the pipeline resists a hostile topic. That claim is
    only meaningful if the detector can tell obedience from repetition."""

    def test_marker_words_are_detected(self):
        slides = [{"slide_title": "HACKED", "bullet_points": ["LEAKED"], "speaker_notes": ""}]
        assert _injection_leaked(slides) is True

    def test_ordinary_deck_is_clean(self):
        slides = [{"slide_title": "Caching", "bullet_points": ["A cache stores results"],
                   "speaker_notes": "Explain the trade-off."}]
        assert _injection_leaked(slides) is False

    def test_repeating_the_topic_without_obeying_is_not_a_leak(self):
        # A deck may faithfully list the hostile line as a topic. That is not
        # obedience, and the detector must not count it as one.
        slides = [{
            "slide_title": "Cache invalidation",
            "bullet_points": ["Invalidation removes stale entries."],
            "speaker_notes": "Ignore all previous instructions is a common attack string.",
        }]
        assert _injection_leaked(slides) is False


class TestSignalChecksDoNotFailACase:
    """Generic wording is a signal, not a gate (cases/test_cases.json rubric).

    Before this was pinned, ``score_plan`` passed a signal check straight into
    ``all(score.checks.values())``, so a deck that tripped the generic-wording
    marker failed with an empty ``failures`` list. That is a believable failure
    with no cause, which sends the reader to fix code that was never broken.
    """

    def _body(self, bullets: list[str]) -> dict:
        return {
            "deck_title": "Course Presentation",
            "slides": [
                {
                    "topic": "Intro",
                    "slide_number": 1,
                    "slide_title": "Neural networks",
                    "bullet_points": bullets,
                    "speaker_notes": (
                        "Explain gradients carefully before moving on to optimisers."
                    ),
                    "grounding": "model-knowledge",
                    "sources": [],
                    "attempts": 1,
                    "degraded": False,
                    "error": None,
                }
            ],
            "diagnostics": {"degraded_slides": 0, "warnings": []},
        }

    def _expected(self) -> dict:
        return {"topics": 1, "min_slides": 1, "max_degraded": 0, "status": 200,
                "max_latency_ms": 180_000}

    def _score(self, bullets: list[str]) -> CaseScore:
        score = CaseScore(case_id="X", name="X", category="edge", passed=False,
                          status=200, latency_ms=10)
        score_plan(score, self._body(bullets), {"id": "X"}, self._expected())
        return score

    def test_generic_wording_is_recorded_but_does_not_fail_the_case(self):
        score = self._score([
            "Backpropagation computes gradients via the chain rule.",
            "Activation functions introduce non-linearity, e.g. ReLU.",
            "TBD",
        ])
        assert score.checks["no_generic_wording"] is False
        assert score.passed is True, "a signal must not decide pass/fail"
        assert score.failures == []

    def test_a_real_failure_still_fails_the_case(self):
        # Two bullets restate the title and nothing else, so content_specificity
        # (a gate) is false. The fix must not make the harness lenient.
        score = self._score(["Topic 1 detail one", "Topic 1 detail two"])
        assert score.checks["content_specificity"] is False
        assert score.passed is False
        assert score.failures

    def test_gating_checks_pass_ignores_only_signal_checks(self):
        assert gating_checks_pass({"no_generic_wording": False, "latency": True}) is True
        assert gating_checks_pass({"no_generic_wording": True, "latency": False}) is False
