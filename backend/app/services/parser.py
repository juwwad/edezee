"""Split raw syllabus text into an ordered, de-duplicated list of topics.

Syllabus formatting is wildly inconsistent: numbered lists, bullets, week
headers, and plain paragraphs all appear in the wild. The parser is deliberately
forgiving, but it must never invent topics or silently drop content, because a
missing topic means a missing slide.
"""

from __future__ import annotations

import re

# Lines that are structural noise rather than teachable topics.
_NOISE_PATTERNS = [
    re.compile(r"^(week|module|unit|lesson|session|day|class|part|section)\s*\d*\s*[:.\-–]?\s*$", re.I),
    re.compile(r"^(syllabus|course|outline|schedule|topics?|contents?|overview)\s*[:.\-–]?\s*$", re.I),
    re.compile(r"^[\s\-–—=*_#|]+$"),
]

# Leading enumerators: "1.", "1)", "1.1", "Week 3:", "a)".
_ENUMERATOR = re.compile(
    r"^\s*(?:"
    r"(?:week|module|unit|lesson|session|day|class|part|topic)\s*\d+"
    r"|\d+(?:\.\d+)*"
    r"|[a-zA-Z]"
    r")\s*[.):\-–—]\s*",
    re.I,
)

_BULLET = re.compile(r"^\s*[-•*·‣▪]\s+")


def _is_noise(line: str) -> bool:
    return any(pattern.match(line) for pattern in _NOISE_PATTERNS)


def _strip_enumerator(line: str) -> str:
    cleaned = _BULLET.sub("", line)
    cleaned = _ENUMERATOR.sub("", cleaned)
    return cleaned.strip(" \t-–—:.")


def parse_topics(raw_text: str, *, max_topics: int = 40) -> list[str]:
    """Return the ordered list of unique topics found in ``raw_text``.

    Empty input yields an empty list so the caller can return a clear 422.
    Lines that are only structural noise are dropped. Topics are de-duplicated
    case-insensitively while preserving first-seen order. The ``max_topics`` cap
    is applied last so the caller controls truncation explicitly.
    """

    if not raw_text or not raw_text.strip():
        return []

    candidates: list[str] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or _is_noise(line):
            continue

        # A single line can hold several bulleted topics separated by ';' or '|'.
        chunks = re.split(r"\s*[;|]\s*", line) if len(line) < 400 else [line]
        for chunk in chunks:
            topic = _strip_enumerator(chunk)
            topic = re.sub(r"\s{2,}", " ", topic).strip()
            if len(topic) < 2 or _is_noise(topic):
                continue
            candidates.append(topic)

    seen: set[str] = set()
    topics: list[str] = []
    for candidate in candidates:
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        topics.append(candidate)
        if len(topics) >= max_topics:
            break

    return topics
