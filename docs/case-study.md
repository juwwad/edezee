# Edezee — Case Study

**Whose workflow changed:** A course instructor preparing a slide deck from a syllabus they did not write.

**What was built:** A web tool that turns pasted syllabus topics into a researched, formatted PowerPoint deck with speaker notes.

**How it was proven better:** A controlled comparison against the naive "paste the whole syllabus into ChatGPT" baseline, scored on coverage, specificity, topic anchoring, and speaker notes — with the raw results in `evaluation/results/`.

---

## 1. The user and the problem

### Persona

A university lecturer or teaching assistant, competent in their subject, not a
developer. They have been handed a syllabus and asked to produce slides. They have
between one and three hours, and they have done this before.

### The job to be done

> "Produce a deck I can teach from, where every syllabus topic is covered, the
> content is accurate enough that I only have to correct emphasis rather than
> rewrite, and I do not spend the afternoon on formatting."

### Evidence of pain

The pain is not hypothetical, and it is not that the content is hard — the
instructor knows the material. The pain is the mechanical loop between knowing and
teaching:

| Step | What it costs |
| --- | --- |
| Read the syllabus, decide what each topic means | 10–20 min |
| Research or recall specifics per topic | 20–60 min |
| Write 3–5 bullets per topic | 30–60 min |
| Write speaker notes | 20–40 min |
| Format consistently in PowerPoint | 30–60 min |
| **Total for 12 topics** | **~2–4 hours** |

The failure mode is familiar: the formatting tail eats the time, and the last
three topics get noticeably thinner than the first three because attention runs
out. The deck is *uneven*, and unevenness is what makes a deck feel unprofessional.

### Why the obvious fix does not work

The instructor already tried ChatGPT. It produces plausible slides, and it fails
in three specific ways that matter:

1. **Batching.** One prompt for 12 topics produces a deck where slides drift from
   their own topics and converge on generic phrasing. It is also the shape of
   request most likely to hit an output-token ceiling, truncating the deck.
2. **No file.** A chat window returns Markdown. Someone still has to build the
   deck.
3. **All-or-nothing.** If the response is malformed, or one topic is awkward, the
   user starts over rather than losing one slide.

---

## 2. Current workflow, and the bottleneck

```text
Trigger:    "I need slides for this course."
Input:      Syllabus (topics, weeks, or a reading list).
Judgment:   What does each topic mean? What belongs on a slide?
Tools:      Browser tabs, ChatGPT, PowerPoint.
Approval:   None — the instructor is the only reviewer.
Output:     A .pptx, assembled by hand.
Exception:  A topic that is too vague or too niche to research quickly.
```

**The bottleneck is the loop, not any single step.** Research, drafting, and
formatting are interleaved and repeated per topic, and each iteration carries
fixed switching costs. Removing any one step helps a little; removing the loop
helps a lot.

**Where the loop breaks:** the instructor cannot tell, partway through, whether the
deck is going to be good. There is no signal. That is why the last topics get
thinner — the work is front-loaded with no feedback.

---

## 3. What was built

```text
Syllabus text
     │
     ▼
 parse_topics()          ordered, de-duplicated, noise-filtered
     │
     ▼
 ┌──────────────── per topic, in sequence ────────────────┐
 │  Tavily search  ──►  snippets + source URLs            │
 │       │                                                │
 │       ▼                                                │
 │  LLM draft      ──►  strict JSON, validated, repaired  │
 └────────────────────────────────────────────────────────┘
     │
     ▼
 build_presentation()    title + content slides + sources
     │
     ▼
 .pptx download  +  per-slide provenance tags  +  run report
```

### The three design decisions that matter

**1. One model call per topic, not one per deck.** This is the central bet.
Batching is cheaper and faster, and it produces worse decks. Per-topic calls give
each slide a tight context window, so the output stays anchored to its topic, and
they make failure per-topic rather than per-deck.

**2. Research is an upgrade, not a dependency.** If Tavily is unreachable, the
deck still generates and each slide is honestly tagged *Model knowledge* instead
of *Web-researched*. A missing API key degrades quality; it does not break the
product.

**3. Provenance is a feature.** Every slide declares where its content came from.
The UI leads with slides that need attention. The system never claims more
reliability than it has — which is the only honest way to hand an LLM-generated
artifact to someone who will teach from it.

### Human approval

The system has no publish, send, or share path. Its only output is a file the
instructor chooses to download, and the UI's job is to make review efficient:
provenance tags, speaker notes visible, failure reasons stated. There is no
irreversible action to gate.

---

## 4. Scope decisions and non-goals

**In scope:** paste topics → download `.pptx`. Depth toggle. Live progress.
Per-slide provenance. Graceful per-topic failure.

**Explicitly out of scope:**

| Non-goal | Why |
| --- | --- |
| User accounts, login | No multi-user need in a 5-day single-instructor flow |
| Deck history, database | Adds storage, migration, and cleanup for a tool run a few times a term |
| Layout, theme, font options | A single template with a 24pt body floor guarantees legibility; options invite "it looks broken" bugs |
| Editing slides in the browser | The instructor's existing PowerPoint is better than anything buildable in five days |
| Parallel drafting | Faster, but measurably less anchored, and harder to reason about under rate limits |
| Export to Google Slides, PDF | `.pptx` opens in all of them; more exporters means more surface area |

Each refusal traded capability for a reliable, explainable core. The measure of
success was not how much the tool does, but whether the part it does can be
trusted.

---

## 5. Results

### Headline

| Metric | Naive one-prompt baseline | Edezee |
| --- | --- | --- |
| Pass rate on the 12-case set | not applicable (no test set) | see `evaluation/results/` |
| Coverage of syllabus topics | incomplete on long decks | 100% on every case |
| Schema compliance | intermittent | 100% |
| Failure mode | whole deck lost | one flagged slide |
| Manual steps after generation | open chat, copy, build deck | open the file |

Full numbers, per case and per metric, are in `docs/evaluation.md` and
`evaluation/results/eval_results.json`.

### What improved, and by how much

The baseline comparison (`evaluation/baseline.py`) scores both approaches with the
same rubric. It reports four quality proxies plus latency and call count. The
comparison is deliberately run on the *same* syllabi with the *same* model, so the
only variable is the architecture.

The measured result: Edezee scores higher on **coverage** and **schema
compliance**, and the gap widens as the syllabus grows. On a 3-topic deck the
difference is modest — a single prompt handles three topics acceptably. On a
12-topic deck the baseline starts dropping and merging topics while Edezee does
not. That scaling behaviour, not the absolute score, is the finding.

### What did *not* improve

Honest reporting requires this section.

- **Latency.** Edezee is several times slower. A 12-topic deck takes 1.5–3
  minutes against roughly 30 seconds for a single prompt. This is the price of the
  per-topic loop and it is paid deliberately.
- **Cost.** More model calls per deck. Roughly one call per topic plus retries.
- **Absolute quality.** Edezee does not make the *content* smarter. Both use the
  same model. Edezee makes the *structure* reliable and the *failure* bounded.
  Any claim beyond that would be unsupported.

---

## 6. Failures found and fixed

Five real defects, each found by testing rather than by inspection.

### F1 — Parser returned nothing

**Symptom:** every request returned "no topics found".
**Root cause:** the topic list was read before it was assigned.
**Why tests missed it:** the test asserted the buggy behaviour, not the contract.
**Fix:** rewrote the parser; rewrote the test against the documented contract.
**Lesson:** AI-written tests validate the implementation against its own
assumptions. Only the spec catches a wrong assumption.

### F2 — Six bullets destroyed a slide

**Symptom:** occasional slides silently replaced by placeholders.
**Root cause:** `max_length=5` on the bullet list made Pydantic *reject* a
6-bullet response, discarding a good slide over a cosmetic overflow.
**Fix:** moved the limit into a validator that trims. The system now degrades in
the direction the user wants — a slightly tight slide, not a missing one.

### F3 — Silent research failures

**Symptom:** a deck where every search failed was indistinguishable from a deck
with no search configured.
**Root cause:** research errors were logged but not counted or surfaced.
**Fix:** the pipeline counts failures, raises a warning, and the UI shows
"Web research failed for N of M topic(s)".

### F4 — Reasoning model returned empty `content`

**Symptom:** live run failed with "model output contained no JSON object" on
attempt one, then succeeded on retry.
**Root cause:** reasoning models sometimes put the entire response in
`reasoning_content` and leave `content` empty. The JSON was present the whole time.
**Fix:** recover from `reasoning_content` before spending a retry. Covered by a
test.

### F5 — UI rendered zero slides after a successful run

**Symptom:** generation completed, the deck downloaded fine, but the review panel
was empty.
**Root cause:** the stream's `done` event carried a slide *count* but not the
slide *content*, so the review list had nothing to render.
**Fix:** the event now carries the slide plan.
**How it was found:** by driving the real UI in a browser, not by unit tests. No
unit test would have caught a contract gap between two components that each passed
their own tests.

---

## 7. Limitations

1. **Content accuracy is not verified.** The system validates structure, schema,
   and grounding. It cannot tell whether a bullet is true. This is why every slide
   carries a provenance tag and the README says to review before teaching.
2. **Latency is inherent to the design.** Per-topic sequencing is the source of
   the quality gain and the source of the wait.
3. **No persistence.** Refresh and the deck is gone. Deliberate, but a real
   limitation if someone wants to regenerate last week's deck.
4. **The evaluation is a proxy.** Coverage, specificity, and anchoring are
   measurable and reproducible. "Would a teacher use this slide?" is not, and no
   claim here rests on it.
5. **Single template.** Correct for legibility, restrictive for someone who wants
   a branded deck.
6. **One deck per request, in memory.** A 40-topic deck is the practical ceiling.

---

## 8. Next two weeks

**Week 1 — close the feedback loop**

1. **Get the deck in front of three real instructors.** The biggest unknown is
   whether the provenance tags actually help a teacher triage. That is answerable
   only by watching someone use it.
2. **Instrument review behaviour.** Log which tagged slides get edited first. If
   *Needs review* slides are always rewritten from scratch, the placeholder
   strategy is wrong and should fail louder instead.
3. **Add a regenerate-one-slide action.** The most likely request after the first
   review pass. Currently the whole deck must be rebuilt.

**Week 2 — close the quality loop**

4. **Feed the instructor's edits back as style examples.** A few edited slides
   per course would let the drafter match house style without a fine-tune.
5. **Add a claim-level grounding check.** For slides tagged *Web-researched*,
   verify each bullet's key noun phrases appear in the retrieved snippets, and
   downgrade the tag when they do not. This turns a soft claim into a checkable one.
6. **Cache research by topic.** Repeated topics across courses are common. Caching
   would cut latency and cost on exactly the workloads that are slowest today.

**Adoption metrics to watch**

| Metric | Target | Why |
| --- | --- | --- |
| Decks generated per active instructor per term | ≥ 3 | Below that, the tool is a novelty |
| Share of slides edited before teaching | < 30% | Above that, the draft is not saving work |
| Slides tagged *Needs review* | < 5% | Above that, reliability is the problem, not quality |
| Median time from paste to download | < 3 min | Bounds the perceived wait |

---

## 9. What I would do differently

**Write the evaluation set on day one, before the code.** It was written on day
two. Every subsequent design argument was settled by pointing at a test case,
which is exactly what should have been available from the start.

**Do not let the implementation define the contract.** Defects F1 and F2 both
came from tests that encoded the implementation's behaviour. The fix in both cases
was to write the test from the spec and watch it fail first.

**Drive the real UI earlier.** F5 was invisible to every unit test and obvious in
ten seconds in a browser.
