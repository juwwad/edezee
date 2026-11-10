# QA log

Newest entry first. One entry per daily run.

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
