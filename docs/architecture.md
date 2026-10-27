# Edezee Architecture

## 1. What the system has to do

Turn a block of syllabus text into a `.pptx` deck a teacher can open and use,
without the teacher making any design or prompting decisions. The system must
survive a bad model response, a search outage, and a single topic that cannot be
drafted, and it must tell the teacher which slides to look at first.

## 2. Component map

```text
┌──────────────────────────────┐
│  Next.js UI  (:3000)         │
│  SyllabusForm                │  paste topics, choose depth
│  ProgressPanel               │  live SSE stage updates
│  ResultPanel                 │  per-slide review + download
└───────────────┬──────────────┘
                │  POST /api/v1/generate/stream  (Server-Sent Events)
                ▼
┌──────────────────────────────────────────────────────────┐
│  FastAPI  (:8000)                                        │
│                                                          │
│  main.py ── routes, CORS, streaming, error mapping        │
│      │                                                   │
│      ▼                                                   │
│  pipeline.py ── orchestration, per-topic timing, warnings │
│      │                                                   │
│      ├─► parser.py     syllabus text -> ordered topics     │
│      ├─► research.py   Tavily search  ──► snippets+sources │
│      └─► llm.py        draft one topic ──► SlideContent    │
│                                                          │
│  pptx_service.py ── slides -> .pptx bytes (in memory)     │
└──────────────────────────────────────────────────────────┘
                │
                ▼
     HTTP response: SSE events, then a base64 .pptx payload
```

## 3. End-to-end data flow

1. **Trigger.** The teacher pastes topics and presses *Generate presentation*.
2. **Transport.** The browser opens `POST /api/v1/generate/stream`. It reads
   Server-Sent Events so the UI can narrate progress instead of freezing.
3. **Parse.** `parser.py` splits the text into an ordered, de-duplicated topic
   list. Numbering, bullets, `Week N:` headers, and `;`-separated lines are all
   handled. Structural noise (`Syllabus`, `---`, `==`) is dropped. If nothing
   parses, the API returns 422 with a plain-language message.
4. **Research (per topic).** `research.py` calls Tavily and returns an answer
   snippet plus source URLs. This is a quality upgrade, not a dependency: a
   failure marks the topic ungrounded and the pipeline continues.
5. **Draft (per topic).** `llm.py` sends one request per topic with a strict
   system prompt and `response_format: json_object`. The response is parsed,
   repaired if needed, and validated against the `SlideContent` schema.
6. **Assemble.** `pptx_service.py` builds the deck in memory: title slide, one
   content slide per topic, then a sources slide. Speaker notes go into the notes
   pane.
7. **Return.** The stream's final event carries the deck as base64 plus the
   diagnostics. The UI renders the slide review and offers the download.

### Why one request per topic

Sending a whole syllabus in one prompt is the obvious shortcut, and it is
measurably worse. In the baseline comparison, the one-shot prompt produced decks
with lower per-slide anchoring to their own topic and a higher rate of generic
filler. It also risks output-token truncation on long decks. Per-topic requests
cost more wall-clock time and more calls, and buy specificity and a bounded
failure surface. Latency was not the bottleneck this project set out to remove.

## 4. Data contracts

**Request** (`GenerateRequest`)

```json
{
  "syllabus_text": "1. Introduction to Next.js\n2. Routing",
  "depth": "High-Level",
  "deck_title": "Intro to Next.js"
}
```

**Model output per topic** (`SlideContent`, validated)

```json
{
  "slide_title": "Introduction to Next.js",
  "bullet_points": ["A React framework.", "Supports SSR.", "Has file routing."],
  "speaker_notes": "Emphasise that routing is file based."
}
```

**Compiled slide** (`Slide`) adds provenance the UI displays:

```json
{
  "topic": "Introduction to Next.js",
  "slide_number": 1,
  "grounding": "research",
  "sources": ["https://nextjs.org/docs"],
  "attempts": 1,
  "degraded": false,
  "error": null
}
```

**Run report** (`PipelineDiagnostics`)

```json
{
  "request_id": "a1b2c3d4e5f6",
  "topic_count": 4,
  "slides_generated": 4,
  "degraded_slides": 1,
  "failed_topics": ["Chunking strategies"],
  "total_latency_ms": 74000,
  "llm_calls": 5,
  "research_used": true,
  "model": "deepseek-v4.1-flash",
  "warnings": ["Web research failed for 1 of 4 topic(s)."]
}
```

## 5. Interfaces

| Endpoint | Returns | Used by |
| --- | --- | --- |
| `GET /api/v1/health` | Configuration status | The UI's setup warning |
| `POST /api/v1/generate` | `.pptx` file | Simple integrations, scripts |
| `POST /api/v1/generate/plan` | JSON deck + diagnostics | Tests, evaluation harness |
| `POST /api/v1/generate/stream` | SSE progress, then the deck | The browser UI |

`/generate/plan` exists so the evaluation harness can score content without
unzipping a `.pptx`. It is the same pipeline; only the response shape differs.

## 6. Reliability design

| Failure | Detection | Response | What the user sees |
| --- | --- | --- | --- |
| JSON wrapped in prose or fences | Regex fence/object extraction | Recover the object | Nothing; slide is normal |
| Trailing commas, single quotes | Strict parse fails | Repair and re-parse | Nothing |
| Renamed keys (`title`/`bullets`) | Schema validation fails | Coerce to the contract | Nothing |
| Empty `content`, JSON in `reasoning_content` | Empty message check | Recover from reasoning text | Nothing |
| 6+ bullets returned | Schema validation | Trim to 5 | Nothing |
| Transient HTTP error / timeout | Status or timeout | Retry with backoff, up to `MAX_TOPIC_ATTEMPTS` | Nothing if a retry succeeds |
| Topic fails all attempts | Retry budget exhausted | Placeholder slide, flagged, run continues | Red banner naming the topic |
| Search provider down | Non-2xx from Tavily | Continue ungrounded, record a warning | "Model knowledge" tag |
| Model key missing | Config check | Refuse before spending calls | Plain-English setup message |
| Nothing parses from input | Parser returns empty | HTTP 422 | "We couldn't find any topics…" |
| Injection attempt inside a topic | Content is treated as data, never as instructions | Drafting proceeds normally | Nothing unusual |

## 7. Human approval points

The system does not publish, send, or teach anything. Its only output is a file
the teacher chooses to download. Approval is therefore structural rather than a
gate inside the flow:

1. The teacher reviews the slide list in the UI, with a provenance tag per slide.
2. Slides tagged **Needs review** are surfaced first, with the failure reason.
3. The teacher edits the deck in their own presentation software.

There is no auto-send path, so there is no irreversible action to gate.

## 8. Privacy and permissions

- **Stateless.** No database, no deck history, no accounts. The `.pptx` is built
  in memory and streamed; nothing is written to disk.
- **Secrets.** Keys live in environment variables only. `.env` files are
  gitignored and `.env.example` ships with empty values.
- **Data egress.** Syllabus text and research queries are sent to the configured
  model and search providers. That is inherent to the task and is stated in the
  README so an operator can make an informed call.
- **Prompt injection.** Topic text reaches the model inside a user message with
  an explicit instruction to return a single JSON object. Output is schema
  validated, so an injected instruction cannot change the response shape. TC-11
  tests this and the injected marker never appears in output.

## 9. Trade-offs and why

**Python/FastAPI backend over Next.js API routes.** `python-pptx` produces
reliable Office files; the Node equivalents are far weaker. Keeping generation in
Python also means the evaluation harness imports the exact production pipeline
rather than reimplementing it.

**In-memory generation over a job queue.** A 12-topic deck takes 1.5–3 minutes.
A queue would add infrastructure, storage, and cleanup for a flow a teacher runs
a few times a term. Streaming progress solves the actual problem (perceived
waiting) without the machinery.

**Sequential over parallel drafting.** Parallel calls would cut wall-clock time
roughly proportionally, but cost more in rate-limit failures and produce less
anchored slides. The design deliberately trades latency for quality and for a
bounded failure surface — one topic failing never affects another.

**One template, no layout options.** Teachers want a deck that looks correct, not
a theme editor. A fixed 16:9 template with a 24pt body floor guarantees classroom
legibility and removes a whole class of "it looks broken" bugs.

**Hand-written TypeScript types.** Generating them from the OpenAPI schema is
tidier in a large codebase. Here the API surface is small, and a non-developer
handing the project on can read one 220-line file to see every field in play.
