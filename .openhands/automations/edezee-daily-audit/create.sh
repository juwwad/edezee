#!/usr/bin/env bash
# Deploy the daily audit/fix/PR automation for Edezee.
# Requires OPENHANDS_API_KEY in the environment. Safe to re-run: it creates a new
# automation each time, so delete the old one first if you are replacing it.
set -euo pipefail

HOST="${OPENHANDS_HOST:-https://app.all-hands.dev}"

python3 - <<'PY'
import json, os, urllib.request

prompt = open(os.path.join(os.path.dirname(__file__), "prompt.md")).read()
body = {
    "name": "Daily Audit / Fix / PR - Edezee",
    "prompt": prompt,
    # 13:00 UTC daily. Three runs land before the 2026-10-30 deadline.
    "trigger": {"type": "cron", "schedule": "0 13 * * *", "timezone": "UTC"},
    # 30 minutes is the service maximum.
    "timeout": 1800,
    "repos": [{"url": "https://github.com/juwwad/edezee", "ref": "main"}],
}
req = urllib.request.Request(
    f"{os.environ.get('OPENHANDS_HOST', 'https://app.all-hands.dev')}"
    "/api/automation/v1/preset/prompt",
    data=json.dumps(body).encode(),
    headers={
        "Authorization": f"Bearer {os.environ['OPENHANDS_API_KEY']}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(req) as r:
    print(r.status)
    print(json.dumps(json.loads(r.read()), indent=2))
PY
