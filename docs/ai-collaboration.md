# AI Collaboration Note

This project was built in a five-day sprint with an AI agent doing most of the
implementation. This note records what that means in practice: what the AI did,
how its output was verified, what was rejected, and which decisions were mine.

## Tools and their roles

| Tool | Role |
| --- | --- |
| OpenHands agent (Claude-based) | Wrote the backend, frontend, tests, evaluation harness, and documentation from my specifications. Ran every command and reported results. |
| OpenRouter (`deepseek-v4.1-flash`) | The model Edezee itself calls. Also the model the baseline comparison runs against. |
| Tavily | Web research for grounding slides. Optional by design. |
| GitHub | Repository, issues, pull requests. |

The AI agent had shell, file-editing, and browser access. It ran the backend,
drove the UI in a real browser, and read the output. I reviewed the diffs and the
evidence rather than trusting summaries.

## What was delegated

- **Implementation.** All application code: parser, research client, LLM client,
  pipeline, PPTX compiler, FastAPI routes, Next.js UI.
- **Test authoring.** The 45 backend tests and the 12-case evaluation set.
- **Measurement.** Running the evaluation harness and reporting raw numbers.
- **Documentation drafts.** README, architecture, runbook, this note.

## What was retained

- **Scope.** Which of the many possible features to build, and — more importantly —
  which to refuse. The non-goals list in `requirements.md` is mine.
- **The core architectural bet.** One model call per topic, sequential, with
  per-topic failure isolation. The agent's first instinct was to batch the whole
  syllabus into one prompt, which is faster and cheaper. I rejected it, and the
  baseline comparison is what settles the argument.
- **Evaluation design.** What "better" means, which proxies are measurable, and
  which claims are not worth making.
- **Every number in the case study.** Rejected AI-reported figures until I had the
  raw command output behind them.

## How AI output was verified

Nothing was accepted on the agent's word. The verification pattern was the same
every time:

1. **Read the diff, not the summary.** Summaries were consistently more confident
   than the code.
2. **Run the command myself** and read the raw output, including exit codes.
3. **Check the claim against an artifact.** "Tests pass" meant the pytest output.
   "Works end to end" meant a `.pptx` opened with `python-pptx` and its slide text
   printed.
4. **Try to falsify.** Ask what would have to be true for the claim to be wrong,
   then test that.

The agent drove the UI in a real browser during development. That surfaced
something no unit test would have: the result panel rendered zero slides after a
successful run, because the stream's `done` event carried a slide *count* but not
the slide *content*. The fix was to add the slide plan to the event. That is
recorded in the failure analysis in `evaluation.md`.

## Results that were rejected or corrected

Four concrete cases where the first AI output was wrong and I caught it:

**1. A parser that returned nothing.** The first `parser.py` assigned its result
before computing it, so every call returned an empty list. It passed no test
because the test was written to match the buggy behaviour. Fixed by rewriting the
parser and writing the test against the documented contract instead.

**2. A bullet limit that rejected instead of trimming.** The Pydantic model had
`max_length=5` on `bullet_points`. When the model returned six bullets, validation
failed and the whole topic was thrown away — a legitimate slide lost to a cosmetic
problem. The fix moves the limit into a validator that trims. The system now
degrades in the direction the user prefers.

**3. Silent research failures.** Research errors were caught and logged, but not
counted. A deck where every search failed looked identical to a deck where none
were attempted. The pipeline now counts `research_failures` and raises a warning
that reaches the user.

**4. A false-positive in my own evaluation.** The harness flagged TC-12 as failing
because it found the word "placeholder" in the output. But TC-12 deliberately
forces a provider outage, and a placeholder slide is the *correct* result. The
check was wrong, not the system. Scoped the specificity check to non-degraded
slides. This one is worth calling out: an evaluation bug that produces a
believable failure is more dangerous than no evaluation.

A fifth, smaller one: the first version of the JSON extraction had no
`reasoning_content` fallback. A live run failed with "model output contained no
JSON object" on attempt one. Reasoning models sometimes leave `content` empty and
put everything in `reasoning_content`; the JSON was there the whole time. That is
now a recovery path with a test, instead of a wasted retry.

## Where AI was wrong in a way that mattered

The agent's initial proposal for the research layer treated Tavily as a hard
dependency: if search failed, the request failed. That contradicts the
requirements, which ask for graceful fallback. It was caught by reading the
requirements against the design, not by testing — the tests all passed, because
the tests were written to the wrong contract.

The general lesson: **AI-written tests validate the implementation against the
implementation's assumptions.** They do not catch a wrong assumption. Only
reading the spec against the design catches that.

## Decisions I owned personally

1. **Per-topic sequential processing** over one batched prompt, accepting higher
   latency and cost for measurable gains in specificity and a bounded failure
   surface.
2. **Refusing accounts, history, and a database.** The requirements name these as
   non-goals, and a queue plus storage would have added infrastructure for a flow
   a teacher runs a few times a term.
3. **Refusing layout and theme options.** A single template with a 24pt body floor
   guarantees classroom legibility and removes a class of bugs.
4. **Treating provenance as a first-class feature.** Every slide is tagged
   researched / model-knowledge / needs-review, and the UI leads with the ones
   needing attention. The system does not pretend to be more reliable than it is.
5. **Making the mock evaluation the gate.** `--mode mock` runs in-process with a
   scripted provider, so reliability is reproducible by anyone with no API key.
   A quality gate that needs a paid key is a gate nobody runs.

## Honest limitations of this collaboration

- The AI agent cannot tell whether generated slide content is *educationally*
  sound. It can verify structure, schema, and grounding; it cannot verify that a
  bullet is true. That is why the deck ships with provenance tags and a
  review-before-teaching instruction rather than a "verified" claim.
- The agent's self-reports were unreliable at the margins. Several "done" claims
  did not survive a direct check. Everything in the results section of the case
  study is traceable to a command I ran.
- The five-day constraint shaped the design as much as the requirements did. The
  limitations section of the case study is a list of things time, not skill,
  excluded.
