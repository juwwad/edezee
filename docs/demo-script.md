# Demo Video Script

A five-minute screen recording for the Applied AI Engineer / AI OS Sprint
submission. Every command and number below was run and verified in this
repository.

The target is a video that shows **one honest thing working end to end**, plus
the evidence behind it. Reviewers have seen a hundred "and then the AI did it"
demos. The part that stands out is the failure handling and the baseline
comparison, because those are what a senior engineer looks for.

---

## Before you record

### 1. Start the backend (demo mode, paced)

Demo mode needs no API key. `INTER_TOPIC_DELAY_SECONDS` slows the pipeline so the
progress panel is visible on camera instead of flashing past in 40 ms.

**PowerShell:**

```powershell
cd backend
$env:DEMO_MODE = "true"
$env:INTER_TOPIC_DELAY_SECONDS = "2.5"
.\run.ps1
```

**macOS / Linux:**

```bash
cd backend
DEMO_MODE=true INTER_TOPIC_DELAY_SECONDS=2.5 ./run.sh
```

Wait for `Application startup complete`, then check:

```bash
curl localhost:8000/api/v1/health
# {"status":"ok","llm_configured":true,...}
```

### 2. Start the frontend

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:3000. Confirm you see the form with **no red banner**. A
red banner means the backend is not reachable — fix that before recording.

### 3. Recording setup

- OBS Studio or Windows Game Bar (`Win+G`), 1080p, 30 fps.
- Test the microphone. Silence is the most common way a demo is wasted.
- Close Slack, mail, and every other browser tab.
- Zoom the browser to ~110% (`Ctrl` + `+`) so body text is legible.
- Bump the terminal font size.
- Do one full rehearsal run. Then clear the form and record.

### 4. Have these ready

- The syllabus is loaded by the **Use a sample syllabus** button. Click it, do
  not type live.
- `docs/evaluation.md` open in a browser tab for the evidence segment.
- The `.pptx` opens in PowerPoint — test that before recording.

---

## The five-minute shot list

### 0:00 – 0:25 — The problem

**On screen:** the app, idle, form visible.

**Say:**

> "Turning a syllabus into slides is a loop. For each topic you research it,
> draft it, format it, and repeat. The bottleneck isn't any one step — it's the
> loop, and the switching cost between each pass.
>
> Edezee removes the loop. You paste topics, you get a PowerPoint deck with
> speaker notes."

**Why:** name the bottleneck in the first twenty seconds. It signals that you
thought about the workflow, not just the code.

### 0:25 – 1:00 — The baseline

**On screen:** `docs/evaluation.md`, the baseline comparison table.

**Say:**

> "Before building it, I checked the obvious alternative: one prompt with the
> whole syllabus. That's what a person does in a chat window.
>
> Quality came out roughly tied — 0.95 against 0.95. I'm not going to claim
> otherwise. But three differences are real. Coverage: Edezee covered every
> topic at every size; the single prompt dropped one at twelve topics, and at a
> hundred and one topics it returned truncated JSON and produced nothing at all.
> Injection: one hostile topic per syllabus — the single prompt leaked it once
> in three runs, Edezee leaked it zero times. And failure is per-topic here
> rather than per-deck.
>
> The cost is latency — roughly three times slower. That's the trade I chose
> deliberately."

**Why:** leading with "quality is tied" is disarming and true. It tells the
reviewer you measure rather than assert. Do not skip the latency admission.

### 1:00 – 2:30 — The live flow

**On screen:** browser at localhost:3000.

1. Click **Use a sample syllabus**.
2. Click **In-depth technical**.
3. Click **Generate presentation**.
4. **Let the progress panel run.** Do not narrate over it silently — talk through
   what each stage does.

**Say, while it runs:**

> "It parses the syllabus into topics first — ordered, de-duplicated, with the
> 'Week 1' headers stripped. Then it works one topic at a time. That's the
> central design decision: one model call per topic, not one per deck. It's
> slower, but each slide stays anchored to its own topic, and a failure is
> contained to one slide."

**When it finishes, on screen:** the review panel.

5. Expand **Speaker notes** on slide one. Read a line or two aloud.
6. Scroll to show the grounding tags.
7. Click **Download .pptx**, then open the file in PowerPoint.

**Say:**

> "Every slide carries where its content came from — web-researched, model
> knowledge, or flagged for review. The system never claims more reliability
> than it has. That matters when you're handing generated content to someone who
> will teach from it."

**Why this is the strongest segment:** the deck is real, it opens, and the
speaker notes are visible. "The deck generated" must mean the file opens and its
text is legible, not that a request returned 200.

### 2:30 – 3:30 — Failure handling

This is the segment most candidates skip. Do not skip it.

**On screen:** stop the backend (`Ctrl+C` in its terminal). Then **open a new
terminal window** — a fresh shell, so no leftover environment variables. Start
the backend with a deliberately invalid key:

**PowerShell:**

```powershell
cd backend
$env:OPENROUTER_API_KEY = "sk-or-invalid-demo-key"
.\run.ps1
```

**macOS / Linux:**

```bash
cd backend
OPENROUTER_API_KEY=sk-or-invalid-demo-key ./run.sh
```

> **Do not set `DEMO_MODE=""` to turn demo mode off.** An empty string is not a
> valid boolean and Pydantic rejects it, so the backend exits with a
> `ValidationError` at startup. A fresh terminal is the reliable way to clear it.
> If you must reuse the same shell, `Remove-Item Env:\DEMO_MODE` (PowerShell) or
> `unset DEMO_MODE` (bash) removes it outright.

Reload the page, paste two topics, generate.

**On screen:** each topic retries three times, then the deck **still finishes**,
with the topics rendered as flagged placeholders. Open the `.pptx` and show the
placeholder slide text.

**Say:**

> "The key is deliberately wrong here. Watch what happens: each topic retries
> three times, then gives up — and the deck still finishes. You get a slide that
> says the content couldn't be generated and needs review.
>
> A failure the user can't see is a bug. So nothing fails silently: the retries
> are counted, the slide is flagged, and the run reports how many slides were
> degraded. The alternative — one bad topic killing the whole deck — is worse
> for a teacher than a slightly incomplete deck."

**Why:** this is the design claim that separates an engineered system from a
demo. It is also the one an interviewer will probe.

### 3:30 – 4:30 — The evidence

**On screen:** `docs/evaluation.md`, then `evaluation/` in the editor.

**Say:**

> "The evaluation is a twelve-case set — happy path, edge cases, and failures,
> including a provider outage and a prompt injection inside a topic. Each case
> is scored against a rubric: topic coverage, schema compliance, whether the
> notes are actually notes, and whether grounding is recorded.
>
> It runs in two modes. Mock mode is deterministic, needs no API key, and is the
> regression gate — twelve of twelve. Live mode runs against the real model.
>
> And the harness has its own tests, because an evaluation bug that produces a
> believable failure is worse than no evaluation at all. I found two of those
> during the sprint and both are written up here."

**Why:** this shows you can measure your own work, including your own
measurement. Mention that the evaluation is documented with its failure
analyses.

### 4:30 – 5:00 — Limitations and close

**On screen:** the limitations section of `docs/evaluation.md`.

**Say:**

> "What doesn't work: it's roughly three times slower than a single prompt, it
> can't tell whether a bullet is true — only whether the structure is sound —
> and there's no persistence, so refreshing loses the deck. Those are deliberate
> trades, and they're written down rather than hidden.
>
> The thing I'd fix first is the latency, by caching research per topic. The
> thing I'd want next is putting it in front of real instructors, because
> whether the provenance tags actually help someone triage is the one question
> the evaluation can't answer."

**Why:** ending on what you'd do next, grounded in what you learned, reads as
senior. Ending on "and that's my project" does not.

---

## If something goes wrong

| Problem | Fix |
| --- | --- |
| Red "not configured" banner | Backend isn't running or `DEMO_MODE` isn't set. Restart the backend and reload. |
| Progress panel flashes instantly | `INTER_TOPIC_DELAY_SECONDS` wasn't picked up. Restart the backend with it set. |
| Frontend blank or error | Backend is down. Check the health endpoint. |
| Port 8000 already in use | Set `$env:PORT = "8123"` and `NEXT_PUBLIC_API_BASE_URL=http://localhost:8123` in the frontend. |
| Deck downloads but won't open | Do not show it. Re-record. A corrupt artifact is worse than a shorter video. |

**If a take goes wrong, keep recording and redo just that segment.** Cut them
together afterward. Do not try to do the whole thing in one flawless take.

---

## Honesty rules for this recording

These are not optional. Each one is a place where a careless demo becomes a
credibility problem.

1. **Say it's demo mode.** The review panel carries the warning: *"Demo mode is
   on: these slides are curated sample content, not model output."* Do not hide
   it. Say: *"This is demo mode, so the content is curated rather than
   model-generated — it's how a reviewer can run the whole flow without a key."*
   The depth toggle and the failure handling are both real; only the drafting
   provider is scripted.
2. **Do not claim the content is good.** The evaluation says quality is roughly
   tied with a single prompt. Say that.
3. **Say the live model path is currently blocked.** The managed proxy returns
   403 for both permitted models — an access-policy change outside the
   repository. `docs/case-study.md` §7 records it. Mention it before you're
   asked.
4. **Do not read numbers off a slide.** If you quote a figure, have the raw
   output behind it.

---

## After recording

- Export as MP4, 1080p. Aim for under 5:00 — over-length is a common way to lose
  a reviewer's attention.
- Watch it once at 2× and check the audio is audible throughout.
- Upload to YouTube (unlisted is fine) or attach to the submission form.
- Add the link to `README.md` under a **Demo** heading, and to the submission
  form's demo field.
