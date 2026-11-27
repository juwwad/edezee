# QA log

Newest entry first. One entry per daily run.

## 2026-11-27 — cancelling a stream run now stops the pipeline

- Baseline: `make test` 163 backend + 53 harness passed, `make mock-eval` 12/12, typecheck OK, build OK on retry (Next.js security nudge); after the fix 164 backend + 53 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: the UI's Cancel button aborts the fetch, but `/api/v1/generate/stream` never cancelled its `run_pipeline` task, so a cancelled 40-topic run kept calling the model for every remaining topic. Repro: `cd backend && ./.venv/bin/python -m pytest tests/test_api.py -k disconnect` fails on `main` with "pipeline kept running after the client disconnected".
- Fixed: the SSE generator cancels its background task in a `finally`, so a disconnect stops drafting. Added 1 test; fails before the fix, passes after.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`. Open PRs #42 and #43 touch other files and were not duplicated.

## 2026-11-24 — chapter/lecture/section headers stay in the slide title

- Baseline: `make test` 149 backend + 53 harness passed, `make mock-eval` 12/12, typecheck OK, build OK on retry (first run stops on the Next.js 16 security nudge); after the fix 155 backend + 53 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: the enumerator's header words were `week|module|unit|lesson|session|day|class|part|topic`, so "Lecture 2: Arrays" and "Chapter 3: Trees" kept their prefix as the slide title while "Week 2: Arrays" lost it, and "Section 1: Intro" kept a prefix that a bare "Section 1" line was already dropped for. Repro: `backend/.venv/bin/python -c "from app.services.parser import parse_topics; print(parse_topics('Lecture 1: Foundations\nLecture 2: Arrays'))"` -> `['Lecture 1: Foundations', 'Lecture 2: Arrays']`
- Fixed: one `_HEADER_WORDS` list now feeds both enumerator branches, extended with `section|chapter|lecture`. `topic` stays enumerator-only: "1. Chapter 1" is a topic (TC-03), and putting heading words in the noise rule dropped it and failed the mock eval. Added 6 cases.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`. Not reviewed: open PRs #39 and #40 touch `llm.py` and the parser's noise patterns; this change touches the enumerator lines only.

## 2026-11-22 — Greedy JSON extraction degrades a topic when the reply has two objects or prose braces

- Baseline: `make test` 149 backend + 53 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 152 backend + 53 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: `_load_json` fell back to a greedy `\{.*\}` match, so a reply containing two JSON objects or a brace in surrounding prose made the whole span invalid (`Extra data`) and the topic degraded to a placeholder even though a complete object was present. Repro: `LLMService._load_json('{"slide_title": "A", "bullet_points": ["x"], "speaker_notes": "n"}\n{"slide_title": "B", "bullet_points": ["y"], "speaker_notes": "m"}')` -> `LLMError: Extra data`.
- Fixed: extraction scans for balanced objects (respecting string literals and escapes) and tries each one with the existing repair ladder, so the first parseable object wins. Added 3 tests; all 3 fail before the fix.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.

## 2026-11-21 — UTF-8 BOM corrupts the first parsed topic

- Baseline: `make test` 145 backend + 53 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 149 backend + 53 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: a leading UTF-8 BOM is not whitespace, so `parse_topics` kept it and the enumerator never matched: `"\ufeff1. Photosynthesis\n2. Respiration"` -> `['\ufeff1. Photosynthesis', 'Respiration']`. The first slide was titled `1. Photosynthesis` (with an invisible BOM); a BOM-only paste produced a one-slide deck instead of a 422. Repro: `backend/.venv/bin/python -c "from app.services.parser import parse_topics; print(parse_topics('\ufeff1. Photosynthesis'))"`
- Fixed: `parse_topics` removes U+FEFF before the empty-input check, so the enumerator matches and BOM-only input is rejected. Added 4 tests.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.

## 2026-11-19 — JSON repair destroys valid output when a topic has an apostrophe

- Baseline: `make test` 130 backend + 53 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 132 backend + 53 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: `_load_json` stripped trailing commas and then unconditionally replaced every `'` with `"`. When the payload contained a possessive ("Parkinson's"), the comma fix had already made the text valid JSON and the quote swap then corrupted it, so all retries failed and the topic degraded to a placeholder. Repro: `LLMService._load_json('{"slide_title": "Parkinson\'s disease", "bullet_points": ["a",], "speaker_notes": "x"}')` -> `LLMError: Expecting ',' delimiter`.
- Fixed: repairs are tried in order (raw, commas removed, commas removed + quotes swapped) and the first text that parses is kept, so the quote swap only runs when it is what makes the text valid. Added 2 tests; verified end to end through `draft_topic` that the topic now succeeds in 1 HTTP call instead of 3 failed attempts.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`. Also seen, not fixed: the greedy `\{.*\}` fallback still fails on output with trailing prose braces or two JSON objects ("Extra data"); left out of scope for this change.
- Note: `npm run build` on `main` stops once with Next.js 16's `SecurityFatalError` upgrade nudge and succeeds on an immediate retry. Expected upstream behaviour, not a repo defect. `next upgrade` was not run.

## 2026-11-18 — PPTX sources slide silently drops the review disclaimer

- Baseline: `make test` 97 backend + 45 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 98 backend + 45 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: `_add_sources_slide` appended the "Review before teaching" line to the listing and then rendered `lines[:16]`. With four or more web-researched topics the listing alone exceeds 16 lines, so the disclaimer was cut off the slide. Repro: build 7 grounded slides with two sources each and read the last slide's body — `"Review before teaching" in sources_body` is False. The one warning every deck is supposed to carry was the first thing dropped.
- Fixed: the source listing is capped at `_MAX_SOURCES_LINES` minus the footer, and the blank line plus the review disclaimer are appended after the cap, so they always render. Added `test_sources_slide_always_keeps_the_review_disclaimer` (fails before, passes after).
- Could not verify: `make eval` (live, real model) — no `OPENROUTER_API_KEY`; the live harness ran against the demo server instead (10/10 executed, 2 skipped by design).

## 2026-11-10 — parser strips a leading dot that belongs to the topic

- Baseline: `make test` 94 backend + 43 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 97 backend + 43 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: `_strip_enumerator` ended with `.strip(" \t-–—:.")`, so a leading dot that is part of the topic was removed: `.NET programming` -> `NET programming`, `.env configuration` -> `env configuration`. Repro: `backend/.venv/bin/python -c "from app.services.parser import parse_topics; print(parse_topics('.NET programming'))"`
- Fixed: `parser.py` strips leading whitespace/dashes/colons, and strips a leading dot only when it is not glued to a word; trailing punctuation still stripped. Added 3 parametrized tests.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.

## 2026-11-09 — harness never asserted the placeholder it exists to check

- Baseline: `make test` 94 backend + 43 harness passed, `make mock-eval` 12/12, typecheck+build OK
- QA: 9 checks run, 9 passed, 0 failed
- Found: TC-12 (`expect_placeholder_slide`) read its mode flag from `expected.get("mock")`, but `mock` is a case-level field, so the branch was dead code in every mode. A provider outage that produced all slides with none flagged still passed. Repro: `score_plan` on 3 non-degraded slides with `case={"mock": True}` -> `passed True`, no `placeholder_present` check.
- Fixed: `evaluation/run_eval.py` reads `case.get("mock")`; TC-12 now records `placeholder_present`. Added 3 tests. Real mock run confirms `"placeholder_present": true`.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.

## 2026-11-03 — harness flagged a resisting deck as an injection leak

- Baseline: `make test` 71 backend + 40 harness passed, `make mock-eval` 12/12, typecheck+build OK
- QA: 9 checks run, 9 passed, 0 failed
- Found: the injection detectors scanned the slide title, which is the topic itself, so a deck that resisted still carried the hostile marker and was recorded as leaked. `evaluation/baseline.py` `_injection_leaked` and `evaluation/run_eval.py` `check_injection_resisted` both did this. Repro: build the TC-11 slides with the title equal to the topic, then `check_injection_resisted(slides, "hacked")` -> `resisted False`; the comparison's headline signal was inverted for the case it exists to prove.
- Fixed: added `scoring.topic_text`, which drops the topic line (case-insensitive, truncation-tolerant, prefix match) before the marker is searched for; both detectors now use it. Real obedience (marker the model wrote) is still a leak. Added 5 tests.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.
- Note: PR #19 (dotted enumerators) was open but unmerged; its fix is not repeated here. `docs/qa-log.md` is created on this branch because `main` does not carry it yet.

## 2026-11-02 — first run: parser drops leading digit of dotted section numbers

- Baseline: `make test` on `main` 71 backend + 35 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 80 backend + 35 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: `parse_topics("1.1 Mitosis")` returned `['1 Mitosis']` — the regex backtracked, keeping the trailing digit and dropping the dot. Also corrupted `1.2 Meiosis` → `2 Meiosis`, `1.2.3 Deep dive` → `3 Deep dive`, `3.5mm audio jack` → `5mm audio jack`. Repro: `backend/.venv/bin/python -c "from app.services.parser import parse_topics; print(parse_topics('1.1 Mitosis'))"`
- Fixed: guarded the enumerator dot against a following digit in `parser.py`; dotted numbers now strip whole. Added 9 parametrized tests.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.
