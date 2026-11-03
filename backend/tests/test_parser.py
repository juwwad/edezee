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
        ("A - Introduction", "Introduction"),
        ("1 - Foundations", "Foundations"),
    ],
)
def test_enumerator_variants(raw, expected_first):
    assert parse_topics(raw)[0] == expected_first


@pytest.mark.parametrize(
    "topic",
    [
        "X-ray crystallography",
        "e-learning platforms",
        "A-level physics",
        "T-shirt design",
        "B-tree indexes",
        "3-D printing",
        "2-factor authentication",
    ],
)
def test_keeps_hyphenated_topics_intact(topic):
    # A hyphen inside a word is part of the topic, not an enumerator separator.
    assert parse_topics(topic) == [topic]
    assert parse_topics(f"1. {topic}") == [topic]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.1 Mitosis", ["Mitosis"]),
        ("1.2 Meiosis", ["Meiosis"]),
        ("1.2.3 Deep dive", ["Deep dive"]),
        ("2.3 Data structures", ["Data structures"]),
        ("3.11 Routing", ["Routing"]),
        ("1.1) Limits and continuity", ["Limits and continuity"]),
        ("1.1. Mitosis", ["Mitosis"]),
    ],
)
def test_strips_dotted_section_numbers(raw, expected):
    # Nested section numbers ("1.1") are enumerators. The parser used to keep
    # the trailing digit and drop the dot, turning "1.1 Mitosis" into
    # "1 Mitosis" and corrupting the slide title.
    assert parse_topics(raw) == expected


@pytest.mark.parametrize(
    "topic",
    [
        "3.5mm audio jack",
        "2.5D animation",
    ],
)
def test_keeps_numeric_prefixes_that_are_part_of_the_topic(topic):
    # A decimal glued to a unit ("3.5mm") is part of the topic. The whitespace
    # terminator below is only reachable when the number is followed by a space,
    # so a unit suffix protects it.
    assert parse_topics(topic) == [topic]
