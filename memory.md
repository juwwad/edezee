# Edezee - Project State & Memory

## Current Status
- **Phase:** Phase 6 (Handoff & Documentation) — the build is complete; the
  remaining work is the demo video and the final submission.
- **Overall State:** The system runs end to end. 48 backend tests and 11
  evaluation-harness tests pass. The offline evaluation gate passes 12/12.
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

## Next Immediate Steps
1. Record the five-minute demo (problem, baseline, live flow, failure handling,
   results, limitation).
2. Confirm the live evaluation numbers against the submitted artifact.
3. Submit.

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
