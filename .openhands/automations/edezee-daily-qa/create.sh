#!/usr/bin/env bash
# Deploy the daily QA automation for Edezee.
#
# Runs once a day, after the Daily Audit automation (13:00 UTC), so it audits
# the state the audit left behind rather than racing it.
#
# Requires OPENHANDS_API_KEY in the environment. Safe to re-run, but it creates
# a new automation each time -- delete the old one first if you are replacing it:
#   curl -X DELETE "$HOST/api/automation/v1/<id>" -H "Authorization: Bearer $OPENHANDS_API_KEY"
set -euo pipefail

PROMPT_FILE="$(cd "$(dirname "$0")" && pwd)/prompt.md"
export PROMPT_FILE

python3 - <<'PY'
import json
import os
import urllib.request

HOST = os.environ.get("OPENHANDS_HOST", "https://app.all-hands.dev").rstrip("/")
with open(os.environ["PROMPT_FILE"], encoding="utf-8") as fh:
    prompt = fh.read()

body = {
    "name": "Daily QA + Fix + PR - Edezee",
    "prompt": prompt,
    # 14:00 UTC daily, an hour after the Daily Audit run so the two do not
    # overlap in the sandbox or fight over the same branch namespace.
    "trigger": {"type": "cron", "schedule": "0 14 * * *", "timezone": "UTC"},
    # 1800s is the service maximum; the prompt budgets against a 30-minute wall.
    "timeout": 1800,
    "repos": [{"url": "https://github.com/juwwad/edezee", "ref": "main"}],
}

req = urllib.request.Request(
    f"{HOST}/api/automation/v1/preset/prompt",
    data=json.dumps(body).encode(),
    headers={
        "Authorization": f"Bearer {os.environ['OPENHANDS_API_KEY']}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(req) as response:
    print(response.status)
    print(json.dumps(json.loads(response.read()), indent=2))
PY
