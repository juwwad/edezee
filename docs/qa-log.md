# QA log

Newest entry first. One entry per daily run.

## 2026-11-14 — a provider 200 with a non-JSON body crashed the whole deck

- Baseline: `make test` 94 backend + 43 harness passed, `make mock-eval` 12/12, typecheck+build OK
- QA: 9 checks run, 9 passed, 0 failed. Also ran the harness live against the demo server (10/10 scored, TC-08/TC-12 skipped by design).
- Found: `LLMService._call_model` called `response.json()` without guarding it, so a provider (or a gateway in front of it) returning HTTP 200 with an HTML body raised `JSONDecodeError`, which escaped the retry loop and turned the request into HTTP 500 — the opposite of "a deck always finishes". Repro: a transport returning `httpx.Response(200, text="<html>502 Bad Gateway</html>")` -> `POST /api/v1/generate` returned 500 instead of a deck with flagged placeholders.
- Fixed: `backend/app/services/llm.py` now catches the JSON decode failure and raises `LLMError`, so the topic degrades to a placeholder like any other provider failure. Added 3 tests (llm, pipeline, API); all 3 fail on the old code.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`; the proxy 403 recorded in `docs/evaluation.md` still stands.

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
