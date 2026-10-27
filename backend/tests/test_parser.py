"""Unit tests for the syllabus parser.

The parser is the first place a teacher's real input can go wrong, so it is
tested against the formats that actually appear in course outlines.
"""

from __future__ import annotations

import pytest

from app.services.parser import parse_topics


def test_numbered_list():
    text = "1. Introduction to Next.js\n2. Routing\n3. Data fetching"
    assert parse_topics(text) == ["Introduction to Next.js", "Routing", "Data fetching"]


def test_bullets_and_week_headers():
    text = """
    Week 1: Foundations
    - Variables and types
    - Control flow
    Week 2: Data structures
    • Arrays and lists
    """
    assert parse_topics(text) == [
        "Foundations",
        "Variables and types",
        "Control flow",
        "Data structures",
        "Arrays and lists",
    ]


def test_ignores_structural_noise():
    text = "Syllabus\n\nTopics:\n1. Algebra\n---\n2. Geometry"
    assert parse_topics(text) == ["Algebra", "Geometry"]


def test_deduplicates_case_insensitively():
    text = "1. Photosynthesis\n2. photosynthesis\n3. Respiration"
    assert parse_topics(text) == ["Photosynthesis", "Respiration"]


def test_empty_input_returns_empty_list():
    assert parse_topics("") == []
    assert parse_topics("   \n\n  ") == []


def test_splits_semicolon_separated_line():
    text = "Causes of inflation; Effects of inflation; Remedies"
    assert parse_topics(text) == ["Causes of inflation", "Effects of inflation", "Remedies"]


def test_respects_max_topics_cap():
    text = "\n".join(f"{i}. Topic number {i}" for i in range(1, 101))
    assert len(parse_topics(text, max_topics=10)) == 10


def test_keeps_long_prose_line_intact():
    topic = "Explain the difference between symmetric and asymmetric encryption in distributed systems"
    assert parse_topics(topic) == [topic]


@pytest.mark.parametrize(
    "raw,expected_first",
    [
        ("1) Cell biology", "Cell biology"),
        ("a) Vectors", "Vectors"),
        ("Module 4 - Neural networks", "Neural networks"),
        ("1.1) Limits and continuity", "Limits and continuity"),
    ],
)
def test_enumerator_variants(raw, expected_first):
    assert parse_topics(raw)[0] == expected_first
