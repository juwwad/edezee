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

from run_eval import is_specific  # noqa: E402


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
