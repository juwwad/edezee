# QA log

Newest entry first. One entry per daily run.

## 2026-11-03 — parser eats first letter of a leading initialism

- Baseline: `make test` on `main` 80 backend + 35 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 87 backend + 35 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: `parse_topics("U.S. history")` returned `['S. history']` — the single-letter enumerator rule matched the "U" and its dot. Also corrupted `U.K. constitutional law` → `K. constitutional law`, `e.g. how TCP works` → `g. how TCP works`, `A.I. ethics` → `I. ethics`. Repro: `backend/.venv/bin/python -c "from app.services.parser import parse_topics; print(parse_topics('U.S. history'))"`
- Fixed: a single letter is only an enumerator when its dot is not followed by another letter, so `A. Introduction` still strips while `U.S.` stays whole. Added 5 initialism cases and 2 letter-enumerator cases.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.
- Note: open PR #20 (injection-detector scope) touches unrelated code; not duplicated here.

## 2026-11-02 — first run: parser drops leading digit of dotted section numbers

- Baseline: `make test` on `main` 71 backend + 35 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 80 backend + 35 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: `parse_topics("1.1 Mitosis")` returned `['1 Mitosis']` — the regex backtracked, keeping the trailing digit and dropping the dot. Also corrupted `1.2 Meiosis` → `2 Meiosis`, `1.2.3 Deep dive` → `3 Deep dive`, `3.5mm audio jack` → `5mm audio jack`. Repro: `backend/.venv/bin/python -c "from app.services.parser import parse_topics; print(parse_topics('1.1 Mitosis'))"`
- Fixed: guarded the enumerator dot against a following digit in `parser.py`; dotted numbers now strip whole. Added 9 parametrized tests.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`.
