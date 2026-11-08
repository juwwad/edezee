# QA log

Newest entry first. One entry per daily run.

## 2026-11-08 — demo provider matched keywords mid-word

- Baseline: `make test` 87 backend + 35 harness passed, `make mock-eval` 12/12, typecheck+build OK; after the fix 89 backend + 35 harness
- QA: 9 checks run, 9 passed, 0 failed
- Found: the demo provider's keyword match was a bare substring test, so `rag` matched inside "sto**rag**e", "ave**rag**e", and "pa**rag**raph" and served the RAG slide for topics about neither. Repro: `DEMO_MODE=true` server, then `curl -s -X POST localhost:8021/api/v1/generate/plan -H 'Content-Type: application/json' -d '{"syllabus_text":"1. Storage and memory"}'` → first bullet "RAG lets a language model answer from documents it was never trained on". Also affected "average", "paragraph", "fragmentation", and the `chunk`/`prompt`/`lora` stems.
- Fixed: `_match` in `backend/app/services/demo.py` now anchors each keyword at a word start (`\b`), so stems still match ("chunk" → "chunking") but mid-word hits do not. Added 2 tests.
- Could not verify: `make eval` (live) — no `OPENROUTER_API_KEY` in the environment or `backend/.env`; issue #6 records the managed proxy returning 403.
- Note: live-mode TC-11 fails against the demo provider (injection detector scans the topic title); open PR #20 already fixes it, so it is not repeated here.

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
