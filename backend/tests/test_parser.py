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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("\ufeff1. Photosynthesis\n2. Respiration", ["Photosynthesis", "Respiration"]),
        ("1. Photosynthesis\n\ufeff2. Respiration", ["Photosynthesis", "Respiration"]),
        ("\ufeffWeek 1: Foundations", ["Foundations"]),
    ],
)
def test_byte_order_mark_does_not_corrupt_topics(raw, expected):
    # A syllabus pasted from a UTF-8 file with a BOM used to keep the marker,
    # which blocked the enumerator match and titled the first slide
    # "\ufeff1. Photosynthesis".
    assert parse_topics(raw) == expected


def test_byte_order_mark_only_input_is_not_a_topic():
    assert parse_topics("\ufeff") == []
    assert parse_topics("\ufeff\n\ufeff") == []


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
        ("A. Introduction", "Introduction"),
        ("b. Vectors", "Vectors"),
        ("Module 4 - Neural networks", "Neural networks"),
        ("1.1) Limits and continuity", "Limits and continuity"),
        ("A - Introduction", "Introduction"),
        ("1 - Foundations", "Foundations"),
        # The "1.)" style (dot then parenthesis) used to leave a stray ")".
        ("1.) Cell biology", "Cell biology"),
        ("2.) Vectors", "Vectors"),
        ("10.) Neural networks", "Neural networks"),
        ("a.) Vectors", "Vectors"),
        ("1.1.) Limits and continuity", "Limits and continuity"),
    ],
)
def test_enumerator_variants(raw, expected_first):
    assert parse_topics(raw)[0] == expected_first


@pytest.mark.parametrize(
    "topic",
    [
        "U.S. history",
        "U.K. constitutional law",
        "e.g. how TCP works",
        "i.e. the difference between TCP and UDP",
        "A.I. ethics",
    ],
)
def test_keeps_single_letter_initialisms_intact(topic):
    # The dot in "U.S." is followed by a letter, so it is part of the word, not a
    # single-letter enumerator. The parser used to eat the first letter and
    # return "S. history".
    assert parse_topics(topic) == [topic]
    assert parse_topics(f"1. {topic}") == [topic]


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
    "raw,expected",
    [
        ("1. C\n2. Python\n3. R", ["C", "Python", "R"]),
        ("1. R", ["R"]),
        ("a", ["a"]),
        ("X", ["X"]),
    ],
)
def test_keeps_single_character_topics(raw, expected):
    # A one-character topic is a real topic ("C", "R", and "X" are course
    # languages and subjects). The parser used to drop anything shorter than
    # two characters, silently removing a slide.
    assert parse_topics(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "1. )",
        "1.)",
        "-)",
        ".",
        ":",
        "1.2.3.",
    ],
)
def test_punctuation_only_lines_are_not_topics(raw):
    # Enumerator residue that strips to pure punctuation must not become a
    # topic once the one-character floor is removed.
    assert parse_topics(raw) == []


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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Unit 1.1 Foundations", ["Foundations"]),
        ("Module 2.3 Cells", ["Cells"]),
        ("Lesson 3.2 Photosynthesis", ["Photosynthesis"]),
        ("Session 4.1 Review", ["Review"]),
        ("Week 2.1 Recap", ["Recap"]),
        ("Day 1.2 Lab", ["Lab"]),
        ("Unit 12.34 Advanced", ["Advanced"]),
        ("Unit 1.1. Foundations", ["Foundations"]),
        ("Module 2.3. Cells", ["Cells"]),
    ],
)
def test_strips_dotted_numbers_after_a_header_word(raw, expected):
    # "Unit 1.1 Foundations" is a header word plus a dotted section number. The
    # header branch required an explicit terminator, so it backtracked to the
    # plain-number form, matched only "Unit 1.", and left the trailing digit as
    # the topic: "1 Foundations". The dotted-number form now takes the same
    # whitespace terminator as the bare "1.1 Mitosis" case.
    assert parse_topics(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # A heading that carries a topic loses its prefix, as "Week 2: Arrays"
        # already did.
        ("Chapter 2: Methods\n1. PCR", ["Methods", "PCR"]),
        ("Lecture 1: Foundations\nLecture 2: Arrays", ["Foundations", "Arrays"]),
        ("Section 1: Intro\n1. Mitosis", ["Intro", "Mitosis"]),
        # "Topic" is an enumerator word, not a heading: "Topic 1" is a topic.
        ("Topic 1\nTopic 2", ["Topic 1", "Topic 2"]),
        ("Topic 1: Mitosis", ["Mitosis"]),
        # A numbered "Chapter 1" is a topic, not a heading (TC-03). Adding
        # "chapter" to the noise rule dropped it and failed the mock eval.
        ("1. Chapter 1\n2. Introduction\n3. Basics", ["Chapter 1", "Introduction", "Basics"]),
    ],
)
def test_chapter_and_lecture_headers_are_handled_like_week(raw, expected):
    # The enumerator's header words were week|module|unit|lesson|session|day|
    # class|part|topic. "Chapter" and "Lecture" were missing, so those titles
    # kept their prefix, and "Section" was in the heading rule but not here.
    assert parse_topics(raw) == expected


@pytest.mark.parametrize(
    "topic",
    [
        "E. coli",
        "C. elegans",
        "H. pylori",
        "S. aureus",
        "T. rex",
        "X.509 certificates",
    ],
)
def test_keeps_single_letter_genus_abbreviations_intact(topic):
    # "E. coli" and "C. elegans" are genus abbreviations, not enumerators. The
    # capital-letter branch matched the leading letter, dropped the dot, and
    # returned "coli" / "elegans", silently corrupting the topic and its slide
    # title. A lowercase word after the dot is the signal that the letter
    # belongs to the word.
    assert parse_topics(topic) == [topic]
    assert parse_topics(f"1. {topic}") == [topic]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("A. Introduction", "Introduction"),
        ("B. Methods", "Methods"),
        ("a. vectors", "vectors"),
        ("b. Vectors", "Vectors"),
    ],
)
def test_still_strips_single_letter_enumerators(raw, expected):
    # A single letter followed by a dot and a capitalised word is a real
    # enumerator ("A. Introduction"). The genus fix must not stop these from
    # being stripped.
    assert parse_topics(raw)[0] == expected

@pytest.mark.parametrize(
    "topic",
    [
        ".NET programming",
        ".env configuration",
        "Introduction to .NET Core",
    ],
)
def test_keeps_leading_dot_topics_intact(topic):
    # A leading dot can be part of the topic itself (".NET", ".env"). The final
    # punctuation strip removed it, turning ".NET programming" into
    # "NET programming" and ".env configuration" into "env configuration".
    assert parse_topics(topic) == [topic]
    assert parse_topics(f"1. {topic}") == [topic]


def test_strips_roman_numeral_enumerators_from_every_line():
    # Only the one-character form matched the single-letter rule, so a Roman
    # list stripped its first topic and left the numeral on the rest:
    # ['Introduction', 'II. Methods', 'III. Results', 'IV. Discussion'].
    text = "I. Introduction\nII. Methods\nIII. Results\nIV. Discussion"
    assert parse_topics(text) == ["Introduction", "Methods", "Results", "Discussion"]


@pytest.mark.parametrize(
    "raw,expected_first",
    [
        ("II. The cell membrane", "The cell membrane"),
        ("iii. Mitosis", "Mitosis"),
        ("IV) Osmosis", "Osmosis"),
        ("VII. Cell signalling", "Cell signalling"),
        ("IX. The Krebs cycle", "The Krebs cycle"),
        ("ii.) Diffusion", "Diffusion"),
    ],
)
def test_roman_numeral_enumerator_variants(raw, expected_first):
    assert parse_topics(raw)[0] == expected_first


@pytest.mark.parametrize(
    "topic",
    [
        "CIVIL. law",
        "MIX. audio",
        "MILD. weather",
        "CIV. law",
        "DID. it work",
    ],
)
def test_keeps_roman_looking_abbreviations_intact(topic):
    # A run of Roman-numeral letters followed by a dot and a lowercase word is
    # an abbreviation, not an enumerator -- the same signal that protects
    # "E. coli" and "U.S. history". "CIVIL. law" must not become "law".
    assert parse_topics(topic) == [topic]


def test_keeps_roman_numeral_standards_intact():
    # "X.509" is a standard name, not an enumerator: the dot is followed by a
    # digit, not a space and a capitalised word.
    assert parse_topics("X.509 certificates") == ["X.509 certificates"]
