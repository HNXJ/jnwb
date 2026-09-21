"""Regenerate `artifacts/state.md`, the canonical verified mutable truth about this tree.

`X = {goal, state, fact, problem, todo}`. The `state` slot was the one with no artifact: every
cycle reconstructed the same basis into an agent transcript, where the next packet could not
read it, and reconstructed it again. Two runs of the same reconstruction on one day is the
recurring correction that made this a script rather than a procedure.

Every line it writes is a command and its output. Nothing is transcribed and nothing is carried
forward from a previous run: the file is overwritten whole, so a value that stops being true
disappears rather than lingering.

    python scripts/reconstruct_state.py            # write artifacts/state.md
    python scripts/reconstruct_state.py --check     # exit 1 if the file is stale

`--check` is what `AGENTS.md` section 3 Prepare runs before reading the file, and what
`tests/test_state_basis_is_checked.py` runs on every suite run. No harness gate calls it, and
the prose this script emits must keep saying so: P-65 is what happened when it claimed
otherwise. Staleness is HEAD having moved since the file was written, so that is all it
compares: a full-text comparison would fail on every uncommitted edit, and a check that fails
all day is one people stop running. It runs no probes and no gate.
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "artifacts" / "state.md"
HEAD_ROW_RE = re.compile(r"^\| HEAD \| `([0-9a-f]{40})` \|$", re.MULTILINE)


def recorded_head(text: str) -> str | None:
    """The HEAD this file was generated at, or None if it records none.

    Staleness is HEAD having moved, not any byte differing. A full-text comparison would fail on
    every uncommitted edit, and a check that fails all day is one people stop running."""
    match = HEAD_ROW_RE.search(text)
    return match.group(1) if match else None


def run(*cmd: str) -> str:
    """Run a command in the repository and return its stripped stdout, or an error marker."""
    try:
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover - environment
        return f"UNRESOLVED ({type(exc).__name__})"
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 and not out:
        err = (proc.stderr or "").strip().splitlines()
        return f"UNRESOLVED (exit {proc.returncode}: {err[0] if err else 'no output'})"
    return out


def package_facts() -> dict[str, str]:
    """Import the checkout and read its own metadata, never a copy in site-packages."""
    probe = (
        "import pathlib, sys, jnwb;"
        "root = pathlib.Path(r'" + str(REPO_ROOT) + "');"
        "assert root in pathlib.Path(jnwb.__file__).resolve().parents, jnwb.__file__;"
        "print(jnwb.__version__);"
        "print(len(jnwb.__all__));"
        "print(len(set(jnwb.__all__)));"
        "print(sum(1 for n in jnwb.__all__ if not hasattr(jnwb, n)))"
    )
    out = run(sys.executable, "-c", probe)
    if out.startswith("UNRESOLVED"):
        return {k: out for k in ("version", "exports", "unique", "unresolved")}
    version, exports, unique, unresolved = out.splitlines()[:4]
    return {
        "version": version,
        "exports": exports,
        "unique": unique,
        "unresolved": unresolved,
    }


def count_lines(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def build() -> str:
    pkg = package_facts()
    gate_output = run(sys.executable, "scripts/harness_gate.py")
    gate_pass = len(re.findall(r"^PASS:", gate_output, re.MULTILINE))
    gate_verdict = (
        "ALL HARNESS GATES PASSED"
        if "ALL HARNESS GATES PASSED" in gate_output
        else "FAILED -- run the gate and read its output"
    )

    skills = sorted(p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md"))
    roles = sorted(p.stem for p in (REPO_ROOT / "artifacts" / "agents").glob("*.md"))

    todo_path = REPO_ROOT / "artifacts" / "todo_stack.md"
    todo_items = (
        len(re.findall(r"^### \d\d-\d\d ", todo_path.read_text(encoding="utf-8"), re.MULTILINE))
        if todo_path.exists()
        else "UNRESOLVED (file absent)"
    )

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.release_gate import open_problems

        problems = len(open_problems(REPO_ROOT))
    except Exception as exc:  # pragma: no cover - defensive
        problems = f"UNRESOLVED ({type(exc).__name__})"

    matrix = run("git", "grep", "-h", "-m1", "python-version:", "--", ".github/workflows")
    upstream = run("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    tracking = run("git", "rev-list", "--left-right", "--count", "HEAD...@{u}")
    head = run("git", "rev-parse", "HEAD")
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    return f"""# State

The `state` slot of `X = {{goal, state, fact, problem, todo}}`: verified mutable truth about
this working tree. Regenerate with `python scripts/reconstruct_state.py`; `--check` compares the
HEAD recorded below against the live one and exits 1 when they differ, and the suite runs that
same comparison whenever this file is present. No harness gate reads this file, so a copy nobody
has checked since HEAD moved reads like a current one.

Every value here is `observed` -- a command and its output, re-resolved on each run. Nothing is
transcribed and nothing survives a regeneration that stops being true. This file is not
authority: the goal and fact slots named in `AGENTS.md` section 2 are. It is what the tree
currently is, which is the thing that goes stale.

This script names neither of those files anywhere, deliberately. `tests/test_skills_validation.py`
treats any file under `scripts/` that mentions the fact stack and can write as able to rewrite it,
and that heuristic is conservative on purpose: the rule that only a human edits durable facts is
a rule only while no code path could. A generator is not worth weakening it for.

Regenerated {stamp}

## Revision

| Quantity | Value |
|---|---|
| Branch | `{run("git", "rev-parse", "--abbrev-ref", "HEAD")}` |
| HEAD | `{head}` |
| Upstream | `{upstream}` |
| Ahead / behind upstream | `{tracking}` |
| Uncommitted paths | {count_lines(run("git", "status", "--porcelain=v1"))} |

## Package

| Quantity | Value |
|---|---|
| `jnwb.__version__` | `{pkg["version"]}` |
| `len(jnwb.__all__)` | {pkg["exports"]} |
| Duplicate exports | {int(pkg["exports"]) - int(pkg["unique"]) if pkg["exports"].isdigit() else pkg["exports"]} |
| Exports that do not resolve | {pkg["unresolved"]} |
| `requires-python` | `{run("git", "grep", "-h", "-m1", "requires-python", "--", "pyproject.toml")}` |
| CI matrix | `{matrix}` |

Measured by importing the checkout with a provenance assertion. A bare interpreter on a machine
that also has jnwb installed imports the installed copy; the probe fails rather than measuring it.

## Surfaces

| Surface | Count | Members |
|---|---|---|
| Skills | {len(skills)} | {", ".join(f"`{s}`" for s in skills)} |
| Agent roles | {len(roles)} | {", ".join(f"`{r}`" for r in roles)} |

## Gates

| Quantity | Value |
|---|---|
| `scripts/harness_gate.py` | {gate_verdict} |
| PASS lines | {gate_pass} |

## Release readiness

`AGENTS.md` section 11 requires both stacks empty. Neither is, which is the expected state of an
open cycle.

| Stack | Remaining |
|---|---|
| `artifacts/todo_stack.md` | {todo_items} items |
| `artifacts/problem_stack.md` | {problems} open problems |
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if artifacts/state.md is stale"
    )
    args = parser.parse_args()

    if not args.check:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(build(), encoding="utf-8", newline="\n")
        print(f"wrote {STATE_PATH.relative_to(REPO_ROOT)}")
        return 0

    if not STATE_PATH.exists():
        print(f"ERROR: {STATE_PATH} is missing; run scripts/reconstruct_state.py")
        return 1
    recorded = recorded_head(STATE_PATH.read_text(encoding="utf-8"))
    live = run("git", "rev-parse", "HEAD")
    if recorded is None:
        print("ERROR: artifacts/state.md records no HEAD; run scripts/reconstruct_state.py")
        return 1
    if recorded != live:
        print(
            f"ERROR: artifacts/state.md was generated at {recorded[:12]} and HEAD is now "
            f"{live[:12]}. Run: python scripts/reconstruct_state.py"
        )
        return 1
    print(f"PASS: artifacts/state.md was generated at the current HEAD {live[:12]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
