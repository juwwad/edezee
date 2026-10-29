# Edezee Operator Runbook

This is the document to read when you are running Edezee, not changing it. Every
procedure here has been executed at least once.

## 1. What "healthy" looks like

```bash
curl -s http://localhost:8000/api/v1/health | jq
```

```json
{
  "status": "ok",
  "llm_configured": true,
  "research_configured": true,
  "model": "anthropic/claude-3.5-sonnet"
}
```

- `llm_configured: false` — no model key. Every generation will fail. Fix first.
- `research_configured: false` — decks still generate; slides are tagged
  **Model knowledge** instead of **Web-researched**.

## 2. Start, stop, restart

```bash
# Start both services (Ctrl-C stops both)
make dev

# Or individually
cd backend && ./run.sh        # :8000
cd frontend && npm run dev    # :3000

# Stop a service started in the background
pkill -f "uvicorn app.main:app"
pkill -f "next"
```

To run the UI on a different machine than the API, set
`NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` and add the UI's origin to
`ALLOWED_ORIGINS` in `backend/.env`, then restart the backend.

### Run it as containers

```bash
# Demo, no API key needed. Open http://localhost:3000
DEMO_MODE=true docker compose up --build

# Real run
OPENROUTER_API_KEY=sk-... docker compose up --build
```

The two images build from `backend/Dockerfile` and `frontend/Dockerfile`. To
host them separately, build the frontend with the public API URL
(`--build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com`) and set the
backend's `ALLOWED_ORIGINS` to the UI's public origin. Those two values must
agree, or the browser blocks every request (see §4, "Not allowed by CORS").

## 3. Daily checks (two minutes)

```bash
curl -s localhost:8000/api/v1/health | jq -c '.status, .llm_configured'
(cd backend && ./.venv/bin/python -m pytest)
backend/.venv/bin/python evaluation/run_eval.py --mode mock
```

A green health check plus 64 passing tests plus 12/12 mock cases means the
pipeline, the validation logic, and the failure handling are all intact.

## 4. Common problems

### "The slide generator is not configured on the server"

`OPENROUTER_API_KEY` is empty or unread. The backend reads `.env` from its own
working directory, so start it from `backend/`.

```bash
cd backend && grep OPENROUTER_API_KEY .env
```

### Every slide says "Needs review"

The model is unreachable or the key is rejected. Check the backend log:

```bash
tail -50 /tmp/edezee-backend.log        # or wherever you redirected output
```

Look for `HTTP 401` (bad key), `HTTP 402` (no credit), or `timed out`. All three
produce a placeholder slide per topic rather than a failed request.

### Decks take too long

A 12-topic deck takes 1.5–3 minutes because each topic is one research call plus
one drafting call, run in sequence. To shorten it:

- Use a faster model: set `OPENROUTER_MODEL` to a smaller model.
- Disable research by clearing `TAVILY_API_KEY`; saves one call per topic.
- Raise `MAX_TOPIC_ATTEMPTS` only if you are seeing genuine transient failures —
  it lengthens the worst case, not the common case.

Do not reduce `MAX_TOPIC_ATTEMPTS` to 1 in production. It removes the retry that
absorbs normal provider flakiness.

### "We couldn't find any topics in that text"

The parser found nothing usable. Usually the paste is prose rather than a list.
Ask for one topic per line. Confirm what the parser sees without calling a model:

```bash
cd backend && ./.venv/bin/python -c "
from app.services.parser import parse_topics
print(parse_topics('your pasted text here'))
"
```

### Slides are generic or too short

Check whether research is on. Ungrounded decks are noticeably thinner. If research
is on, the provider may be rate limiting; the run report's `warnings` will say
`Web research failed for N of M topic(s)`.

### "Not allowed by CORS" in the browser console

The UI's origin is not in `ALLOWED_ORIGINS`. Add it, comma-separated, and restart
the backend. CORS is read at startup, not per request.

### The download never starts

Check that the browser is not blocking the download and that the request was not
cancelled. If the stream was cut, the UI shows `Generation cancelled.` and the
form returns; press Generate again.

## 5. Changing the model

Edit `backend/.env` and restart:

```bash
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

The system prompt, JSON schema, and validation are model-agnostic. After a model
change, re-run the evaluation set:

```bash
python evaluation/run_eval.py --mode live
```

Compare pass rate and median latency against the previous run before keeping the
change. `evaluation/results/` keeps the history.

## 6. Tuning knobs

| Setting | Default | Raise it when | Lower it when |
| --- | --- | --- | --- |
| `MAX_TOPIC_ATTEMPTS` | 3 | Providers are flaky | You are burning budget on a bad model |
| `MAX_TOPICS` | 40 | Courses genuinely exceed 40 topics | You want to cap spend per request |
| `LLM_TIMEOUT_SECONDS` | 90 | Slow reasoning models are in use | Requests are hanging |
| `TAVILY_MAX_RESULTS` | 4 | Slides lack depth | Prompts are getting long |
| `INTER_TOPIC_DELAY_SECONDS` | 0 | You hit rate limits on a free tier | Never; 0 is right on paid tiers |

## 7. Adding a new topic format to the parser

The parser handles formats by pattern, and every pattern is covered by a test.
To support a new one:

1. Add the format to `backend/tests/test_parser.py` as a failing test.
2. Update `_ENUMERATOR` or `_NOISE_PATTERNS` in
   `backend/app/services/parser.py`.
3. Run `./.venv/bin/python -m pytest tests/test_parser.py`.

Change the parser before changing prompts. A parsing bug looks like a model
quality problem from the outside.

## 8. Cost and latency expectations

Measured on a 4-topic deck:

| Configuration | Model calls | Wall clock |
| --- | --- | --- |
| Research on | 8 (4 search + 4 draft) | ~60–90 s |
| Research off | 4 | ~25–40 s |

With `MAX_TOPIC_ATTEMPTS=3`, the worst case per topic is 3 calls. A full 40-topic
deck is the most expensive thing the system can be asked to do; cap `MAX_TOPICS`
if you need a hard budget ceiling.

## 9. Rolling back

```bash
git log --oneline -10
git revert <commit>
```

The frontend and backend deploy independently. A backend-only rollback does not
require rebuilding the UI unless the API contract changed.

## 10. Escalation checklist

Before reporting a problem, collect:

1. `curl -s localhost:8000/api/v1/health | jq` output.
2. The backend log lines around the failure.
3. The request's `X-Edezee-Diagnostics` header, or the run report from the UI.
4. The result of `python evaluation/run_eval.py --mode mock`.

Those four things distinguish a code defect from a configuration or provider
problem in almost every case.
