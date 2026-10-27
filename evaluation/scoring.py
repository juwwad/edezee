"""Shared quality heuristics for the evaluation harness and the baseline.

Both scripts judge deck quality, and both previously carried their own copy of
the specificity logic. When one copy turned out to flag good prose as generic,
the other kept the bug. The heuristics live here so there is one definition to
fix and one to test (`harness_tests/test_heuristics.py`).

None of these measures claim to judge whether content is *true*. They measure
structure and specificity, which are reproducible. The limits of that are
documented in docs/evaluation.md.
"""

from __future__ import annotations

import re

# Wording the pipeline emits when a topic exhausts its retries. Unambiguous: if
# any of these appears in a slide that is not flagged as degraded, the flag is
# wrong.
PLACEHOLDER_MARKERS = [
    "automatic generation failed",
    "lorem ipsum",
    "placeholder",
]

# Phrasing that suggests the model wrote around the topic instead of about it.
# Reported as a signal, never as a hard failure: a vague topic name legitimately
# produces abstract content, and that is a property of the input.
GENERIC_MARKERS = [
    "tbd",
    "todo",
    "n/a",
    "lorem ipsum",
    "this topic",
    "the topic",
    "important concept",
    "various aspects",
    "and more",
    "discussed below",
]

# Words that carry no topic-specific information. A bullet built from these
# alone ("An introduction explains what this topic covers") teaches nothing, so
# they are excluded when counting content words.
EMPTY_WORDS = {
    "about", "above", "after", "again", "allows", "along", "also", "although",
    "among", "another", "applied", "around", "because", "before", "being",
    "below", "between", "both", "covers", "defined", "definition", "describes",
    "during", "each", "either", "example", "explains", "further", "given",
    "helps", "however", "includes", "including", "involves", "itself", "known",
    "means", "might", "more", "most", "much", "must", "needs", "often", "other",
    "others", "over", "particular", "provides", "rather", "refers", "relates",
    "represents", "requires", "same", "several", "should", "shows", "since",
    "some", "such", "than", "that", "their", "them", "then", "there", "these",
    "they", "thing", "things", "this", "those", "through", "thus", "together",
    "topic", "topics", "under", "understand", "until", "used", "using",
    "various", "very", "what", "when", "where", "which", "while", "with",
    "within", "without", "would",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "as", "by", "at", "from", "that", "this", "it", "be", "can", "how",
    "what", "why", "when", "which", "into", "between", "vs", "using", "use",
    "overview", "introduction", "basics", "concept", "concepts", "part", "chapter",
}


def is_specific(slide: dict) -> bool:
    """True when a bullet contributes real information beyond its own title.

    A slide that only restates its title, or that is built entirely from generic
    connectives ("An introduction explains what this topic covers"), teaches
    nothing. Requiring one bullet to contribute three content words that appear
    in neither the title nor :data:`EMPTY_WORDS` is a simple, measurable proxy.

    This replaced a blacklist of phrases. A blacklist cannot catch phrasing it
    has not seen, and the earlier version produced false failures on good
    speaker notes. Only the title and the bullets are in scope: notes are
    teaching guidance, where "ask what learners know about this topic" is
    correct prose, not filler.
    """

    title_words = set(re.findall(r"[a-z]+", str(slide.get("slide_title", "")).lower()))
    for bullet in slide.get("bullet_points") or []:
        words = set(re.findall(r"[a-z]{4,}", str(bullet).lower()))
        if len(words - title_words - EMPTY_WORDS) >= 3:
            return True
    return False


def terms(text: str) -> set[str]:
    """Significant words in ``text``, used for topic-anchoring overlap."""

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def generic_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in GENERIC_MARKERS if marker in lowered]


def placeholder_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in PLACEHOLDER_MARKERS if marker in lowered]


def slide_text(slide: dict, *, include_notes: bool = True) -> str:
    parts = [str(slide.get("slide_title", ""))]
    parts.extend(str(b) for b in (slide.get("bullet_points") or []))
    if include_notes:
        parts.append(str(slide.get("speaker_notes", "")))
    return " ".join(parts)
