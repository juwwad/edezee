# QA log

Newest entry first. One entry per daily run.

## 2026-11-02 — first run: parser drops leading digit of dotted section numbers

- Baseline: `make test` 80 passed + 35 harness passed, `make mock-eval` 12/12, typecheck+build OK
- QA: 9 checks run, 9 passed, 0 failed
- Found: `parse_topics("1.1 Mitosis")` returned `['1 Mitosis']` — the regex backtracked, keeping the trailing digit and dropping the dot. Also corrupted `1.2 Meiosis` → `2 Meiosis`, `1.2.3 Deep dive` → `3 Deep dive`, `3.5mm audio jack` → `5mm audio jack`. Repro: `backend/.venv/bin/python -c "from app.services.parser import parse_topics; print(parse_topics('1.1 Mitosis'))"`
- Fixed: guarded the enumerator dot against a following digit in `parser.py`; dotted numbers now strip whole. Added 9 parametrized tests.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.
