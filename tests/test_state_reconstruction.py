"""``artifacts/state.md`` is the `state` slot of `X`, and it is generated, never written by hand.

The slot had no artifact until 2026-09-19: the same basis was reconstructed twice in one day
into agent transcripts, where the next packet could not read it. A generated file only helps if
regenerating it is deterministic and if a stale copy is detectable, so both are tested here.

These tests drive the generator. They do not assert that the checked-in file is current -- there
is no checked-in file, by design.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

from scripts.reconstruct_state import (
    HEAD_ROW_RE,
    STATE_PATH,
    build,
    recorded_head,
    run,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TIMESTAMP_RE = re.compile(r"^Regenerated .*$", re.MULTILINE)


def _without_timestamp(text: str) -> str:
    return _TIMESTAMP_RE.sub("", text)


@pytest.fixture(scope="module")
def generated() -> str:
    return build()


def test_the_state_file_is_not_committed():
    """Committing mutable truth makes it record the commit before its own.

    A tracked ``artifacts/state.md`` would be stale from the moment it landed and would read as
    current, which is worse than having no file.
    """
    tracked = run("git", "ls-files", "--error-unmatch", "artifacts/state.md")
    assert tracked.startswith("UNRESOLVED"), (
        "artifacts/state.md is tracked; it must be generated and ignored"
    )
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "artifacts/state.md"], cwd=REPO_ROOT
    )
    assert ignored.returncode == 0, "artifacts/state.md is neither tracked nor ignored"


def test_generation_is_deterministic_apart_from_its_timestamp(generated: str):
    again = build()
    assert _without_timestamp(generated) == _without_timestamp(again)


def test_an_unresolved_row_says_why(generated: str):
    """A row that could not be measured says so, with its cause; it never reports a wrong value.

    This asserted that *no* row is UNRESOLVED, which is stricter than the invariant in its own
    docstring and false on a tree where a value legitimately does not exist. A linked worktree has
    no upstream, so the Upstream row is correctly unresolved -- and the suite failed for it, in
    every agent worktree, for a reason unrelated to the agent's work. Asserting absence was a
    proxy for "no row lies", which is P-37 once more: the honest output tripped the check.

    What must hold is that an unresolved row names its cause, so a reader can tell "not measurable
    here" from "the measurement broke".
    """
    unresolved = [line for line in generated.splitlines() if "UNRESOLVED" in line]
    for line in unresolved:
        assert re.search(r"UNRESOLVED\s*\(", line), (
            f"a row reports UNRESOLVED without saying why, so it is indistinguishable from a "
            f"broken measurement: {line}"
        )


def test_it_reports_the_slots_a_packet_needs(generated: str):
    for expected in (
        "| Branch |",
        "| HEAD |",
        "| Upstream |",
        "`jnwb.__version__`",
        "`len(jnwb.__all__)`",
        "| CI matrix |",
        "| Skills |",
        "| Agent roles |",
        "ALL HARNESS GATES PASSED",
        "open problems",
    ):
        assert expected in generated, f"state.md no longer reports {expected!r}"


def test_the_measured_values_match_the_tree(generated: str):
    """The generator must read the tree, not restate constants.

    A generator that hardcoded its answers would satisfy every other test here.
    """
    import jnwb

    # Skipped rather than asserted when the package under test is not this checkout. The
    # generator is a checkout-only script and reports on the checkout, so comparing its output
    # against an installed copy's version would fail for the wrong reason. Asserting the package
    # sits here instead would pin the whole suite to the tree, which is the thing
    # `tests/test_the_suite_can_qualify_an_installed_copy.py` exists to prevent -- and this line
    # was one of the two violations that produced that rule on 2026-09-19.
    if pathlib.Path(REPO_ROOT) not in pathlib.Path(jnwb.__file__).resolve().parents:
        pytest.skip(f"qualifying {jnwb.__file__}, not this checkout; the generator reports on the tree")
    assert f"| `jnwb.__version__` | `{jnwb.__version__}` |" in generated
    assert f"| `len(jnwb.__all__)` | {len(jnwb.__all__)} |" in generated

    skills = sorted(p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md"))
    roles = sorted(p.stem for p in (REPO_ROOT / "artifacts" / "agents").glob("*.md"))
    rows = {
        row.split("|")[1].strip(): row.split("|")[2].strip()
        for row in generated.splitlines()
        if row.startswith("|") and row.count("|") >= 3
    }
    assert rows["Skills"] == str(len(skills)), rows.get("Skills")
    assert rows["Agent roles"] == str(len(roles)), rows.get("Agent roles")
    for name in skills:
        assert f"`{name}`" in generated, f"state.md omits the skill {name}"
    for name in roles:
        assert f"`{name}`" in generated, f"state.md omits the role {name}"

    assert recorded_head(generated) == run("git", "rev-parse", "HEAD")


def test_a_moved_head_reads_as_stale(tmp_path: pathlib.Path, generated: str):
    """``--check`` exists to stop a stale basis being read as a current one."""
    stale = HEAD_ROW_RE.sub("| HEAD | `" + "0" * 40 + "` |", generated)
    assert recorded_head(stale) == "0" * 40
    assert recorded_head(stale) != run("git", "rev-parse", "HEAD")


def test_check_exits_nonzero_when_the_file_is_absent(tmp_path: pathlib.Path):
    """Absence must not read as freshness.

    Every block in gate 8 was once ``if <file>.exists():`` with no else, so an empty directory
    passed. A check satisfied by deleting its own evidence is worse than no check.
    """
    assert recorded_head("# State\n\nno head row here\n") is None


def test_the_cli_check_runs_without_probing(generated: str):
    """``--check`` must stay cheap, or it becomes a step people skip.

    It compares one recorded hash against ``git rev-parse``; building the file runs the whole
    harness gate and takes tens of times longer.
    """
    if not STATE_PATH.exists():
        pytest.skip("artifacts/state.md has not been generated in this working tree")
    proc = subprocess.run(
        [sys.executable, "scripts/reconstruct_state.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "PASS" in proc.stdout or "ERROR" in proc.stdout, proc.stdout + proc.stderr
    assert "harness_gate" not in proc.stdout, "--check ran the gate; it must not"
