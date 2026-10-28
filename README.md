# Edezee

Turn a course syllabus into a researched, ready-to-teach PowerPoint deck.

Paste your topics. Edezee researches each one, drafts slide content with speaker
notes, and hands back a `.pptx` file you can open in PowerPoint, Keynote, or
Google Slides. No design work, no prompt engineering, no copy-paste between a
chat window and a slide editor.

```
Syllabus topics  ->  research  ->  draft per topic  ->  .pptx with speaker notes
```

---

## Who this is for

A teacher or instructional designer who has to produce a slide deck for a course
they did not write, or who is rebuilding an old deck for a new term. They know
their subject. They do not want to spend an afternoon on formatting.

## The problem it removes

Producing a 12-topic deck by hand means roughly: read the syllabus, research each
topic, decide what belongs on a slide, write bullets, write speaker notes, then
format everything consistently. That is the work Edezee does. The teacher keeps
the judgement: reviewing content, correcting emphasis, and deciding what to teach.

---

## Run it in three steps

You need Python 3.10+, Node.js 18+, and an OpenRouter API key
(https://openrouter.ai/keys). A Tavily key (https://tavily.com) is optional and
improves grounding.

### 1. Start the backend

```bash
cd backend
cp .env.example .env          # then edit .env and set OPENROUTER_API_KEY
./run.sh                      # creates a venv, installs deps, serves on :8000
```

### 2. Start the frontend

In a second terminal:

```bash
cd frontend
cp .env.example .env.local    # defaults already point at http://localhost:8000
npm install
npm run dev                   # serves on :3000
```

### 3. Open it

Go to http://localhost:3000, paste your topics, and press **Generate presentation**.
When the deck is ready, press **Download .pptx**.

> First run of `./run.sh` takes a minute while it installs dependencies. After
> that it starts in about two seconds.

### One-command start (optional)

```bash
make dev        # starts both services; Ctrl-C stops both
```

---

## What you get

| Output | Detail |
| --- | --- |
| Title slide | Deck title, 44pt, plus the depth you chose |
| Content slides | One per topic, 3–5 bullets, 24pt minimum body text |
| Speaker notes | 2–4 sentences of teaching guidance per slide |
| Sources slide | Links for every web-researched slide |
| Run report | Slides generated, degraded slides, latency, warnings |

Slide geometry is fixed at 16:9 with Arial and a 24pt floor for body text so the
deck is readable in a lecture hall. Layout options are deliberately not exposed —
one reliable template beats a settings panel nobody wants to learn.

## How to tell whether to trust a slide

Every slide in the web UI is tagged:

| Tag | Meaning |
| --- | --- |
| **Web-researched** | Content came from live search results. Sources are listed. |
| **Model knowledge** | No search was used or it failed. Content is the model's own. |
| **Needs review** | Generation failed for that topic. The slide is a flagged placeholder. |

A deck always finishes. If one topic fails, you get a placeholder slide and a
warning — not a failed run.

---

## Project layout

```text
edezee/
├── backend/                 FastAPI service: research, drafting, PPTX assembly
│   ├── app/
│   │   ├── config.py        Every tunable, read from the environment
│   │   ├── models.py        Pydantic contracts for each boundary
│   │   ├── main.py          HTTP routes (file, JSON plan, SSE progress)
│   │   └── services/
│   │       ├── parser.py    Syllabus text -> ordered topic list
│   │       ├── research.py  Tavily search with graceful degradation
│   │       ├── llm.py       Drafting with JSON repair and retries
│   │       ├── pipeline.py  Stage orchestration and diagnostics
│   │       └── pptx_service.py  Structured slides -> .pptx bytes
│   └── tests/               57 tests: unit, pipeline, HTTP contract
├── frontend/                Next.js UI: input form, live progress, review
├── evaluation/              12 test cases, harness, baseline comparison
└── docs/                    Architecture, runbook, case study
```

## Configuration

All configuration is environment-driven. Nothing is hardcoded and `.env` files
are gitignored. See `backend/.env.example` for the full list.

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Yes | Model access |
| `OPENROUTER_MODEL` | Yes | Any OpenRouter model id |
| `TAVILY_API_KEY` | No | Enables web research; without it slides use model knowledge |
| `MAX_TOPIC_ATTEMPTS` | No | Retries per topic (default 3) |
| `MAX_TOPICS` | No | Hard cap per request (default 40) |
| `ALLOWED_ORIGINS` | No | CORS allowlist for the frontend |

## Verify it works

```bash
cd backend && ./.venv/bin/python -m pytest        # 57 tests
python evaluation/run_eval.py --mode mock          # 12 cases, no API key needed
python evaluation/run_eval.py --mode live          # 12 cases against a running server
```

## Documentation

| Document | Read it when |
| --- | --- |
| `docs/architecture.md` | You want the data flow, contracts, and trade-offs |
| `docs/runbook.md` | You are operating or debugging the system |
| `docs/case-study.md` | You want the problem, results, and limitations |
| `docs/evaluation.md` | You want the test set, rubric, and failure analysis |
| `docs/ai-collaboration.md` | You want to know what AI did and what I verified |

## Limits

- Generated content can be wrong. Review before teaching; the tags tell you where
  to look first.
- One deck per request, held in memory. There is no history and no accounts.
- A 12-topic deck takes roughly 1.5–3 minutes and 12–20 model calls.
- The pipeline is sequential by design. Parallel drafting is faster but measurably
  less specific, and speed was not the bottleneck being removed.
