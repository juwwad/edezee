"""The commands the docs tell a reader to run must actually exist.

`docs/evaluation.md` is the operator's entry point for reproducing the
evaluation, so a target it names that the Makefile does not define is a dead
end: the reader copies the command, gets `No rule to make target`, and has no
way to tell whether the docs or their checkout is wrong. The doc also labels
which target produces which results file, and a live run that silently
overwrites the offline artifact is the same class of failure in reverse.

These tests pin the docs to the Makefile, which is the single source of truth
(`make help` lists the same tasks).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
EVALUATION_DOC = REPO_ROOT / "docs" / "evaluation.md"


def makefile_targets() -> set[str]:
    return set(re.findall(r"^([a-zA-Z][\w-]*):", MAKEFILE.read_text(), re.M))


def makefile_recipe(target: str) -> str:
    """The recipe body for ``target``, stopping at the next target or the end."""
    text = MAKEFILE.read_text()
    match = re.search(rf"^{re.escape(target)}:\n((?:\t.*\n)+)", text, re.M)
    return match.group(1) if match else ""


def documented_targets(text: str) -> set[str]:
    """Every ``make <target>`` the doc names, in backticks or at line start."""
    return set(re.findall(r"`make ([a-z][\w-]*)`", text)) | set(
        re.findall(r"^make ([a-z][\w-]*)", text, re.M)
    )


def test_every_documented_make_target_exists():
    """A command the docs tell the reader to run must resolve.

    Regression guard: the doc named `make eval-live`, which the Makefile never
    defined, so the documented command failed with `No rule to make target`.
    """
    targets = makefile_targets()
    referenced = documented_targets(EVALUATION_DOC.read_text())
    missing = sorted(referenced - targets)
    assert missing == [], f"docs/evaluation.md names targets the Makefile lacks: {missing}"


def test_mock_and_live_eval_write_distinct_result_files():
    """The offline and live runs must not share an output path.

    `make eval` (live) previously wrote the same `eval_results.json` as
    `make mock-eval`, so a live run silently replaced the tracked offline
    artifact with live numbers.
    """
    mock = makefile_recipe("mock-eval")
    live = makefile_recipe("eval")
    assert "--mode mock" in mock
    assert "--mode live" in live
    assert "eval_results.json" in mock
    assert "eval_results_live.json" in live
