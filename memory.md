# Edezee - Project State & Memory

## Current Status
- **Phase:** Phase 6 (Handoff & Documentation) — the build is complete; the
  remaining work is the demo video and the final submission.
- **Overall State:** The system runs end to end. 57 backend tests and 31
  evaluation-harness tests pass. The offline evaluation gate passes 12/12;
  the live gate passes 10/10 executed cases (2 skipped by design).
- **Submission deadline:** Friday 30 October 2026.

## Completed Tasks
- [x] Define Project Requirements (`requirements.md`)
- [x] Define Technical Architecture (`architecture.md`)
- [x] Define Design Tokens & UI/UX (`design.md`)
- [x] Define Contribution Rules (`rules.md`)
- [x] Define Build Phases (`phases.md`)
- [x] Phase 1 — Scaffolding: FastAPI backend + Next.js frontend in a monorepo
- [x] Phase 2 — LLM pipeline with a strict JSON contract and repair paths
- [x] Phase 3 — PPTX compiler (16:9, Arial, 24pt body floor, max 5 bullets)
- [x] Phase 4 — UI integration with SSE streaming and file download
- [x] Phase 5 — Hardening: per-topic fallback, provenance tags, plain-language errors
- [x] Phase 6 — Documentation: README, architecture, runbook, case study,
      AI collaboration note
- [x] Evaluation package: 12 cases, baseline comparison, failure analysis
      (`docs/evaluation.md`)
- [x] Baseline harness hardened: records hard failures, injection leaks, and
      runs at multiple syllabus sizes (`--topics`, `--arm`)

## Next Immediate Steps
1. Record the five-minute demo (problem, baseline, live flow, failure handling,
   results, limitation).
2. Submit.

## Measured Results (2026-10-27)

Baseline comparison, same model, same syllabi, one injected topic each
(`evaluation/results/baseline.json`):

| Metric | Naive one prompt | Edezee |
| --- | --- | --- |
| Mean overall | 0.9462 | 0.9504 |
| Mean coverage | 0.9744 | 1.0000 |
| Mean latency | 28.3 s | 81.7 s |
| Mean model calls | 1 | 8 |
| Injection leaks (3 runs) | 1 | 0 |

- Quality is roughly tied at small sizes; the naive prompt scored *higher* at 6
  topics on anchoring. The real differences are coverage at scale, injection
  resistance, and hard failure (truncated JSON at 101 topics).
- Do not claim Edezee writes better content. Both arms use the same model. The
  claim is structural reliability and bounded failure.

## Active Context & Hand-off Notes
- **Core Directive:** Edezee is a sequential pipeline, NOT a chatbot. Do not
  build chat UI elements.
- **Architectural Boundary:** The Next.js frontend handles state and UX; the
  FastAPI backend does all heavy lifting (LLM orchestration, file generation).
- **Agent Instruction:** Update this file whenever a phase from `phases.md`
  completes, so context is never lost between sessions or hand-offs.
- **Authoritative docs:** `requirements.md` §5 lists the non-goals. `design.md`
  fixes the slide geometry and font sizes. `AGENTS.md` lists the architecture
  invariants and the commands to verify a change.
