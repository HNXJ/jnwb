"""``artifacts/state.md`` is the `state` slot of `X`, and it is generated, never written by hand.

The slot had no artifact until 2026-09-19: the same basis was reconstructed twice in one day
into agent transcripts, where the next packet could not read it. A generated file only helps if
regenerating it is deterministic and if a stale copy is detectable, so both are tested here.

These tests drive the generator. They do not assert that the checked-in file is current -- there
is no checked-in file, by design.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request
from unittest import mock

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# `scripts/` is deliberately excluded from the wheel (`pyproject.toml`
# `[tool.setuptools.packages.find] exclude`), and the leg that qualifies the built artifact runs
# this suite from outside the repository with `-o pythonpath=` and `--import-mode=importlib`, so
# nothing puts the checkout on `sys.path`. A module-scope `from scripts...` therefore raised
# `ModuleNotFoundError` there -- a collection *error*, which pytest reports as `Interrupted` and
# which can take unrelated modules down with it. It was masked in the full run only because
# `tests/test_dependency_floors_are_installable.py` sorts earlier and appends the root as a side
# effect, so the defect was invisible and one filename rename away from firing.
#
# `append`, never `insert`: the generator under test lives in the checkout and is read from disk
# there, but the *package* under test must stay the installed copy.
# `tests/test_the_suite_can_qualify_an_installed_copy.py` exists because
# `sys.path.insert(0, REPO_ROOT)` re-shadows it for the whole session.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.reconstruct_state import (  # noqa: E402
    HEAD_ROW_RE,
    STATE_PATH,
    build,
    recorded_head,
    run,
)

# The CI row reads the network, where a run can finish between two builds.
_TIMESTAMP_RE = re.compile(r"^(Regenerated .*|\| Newest CI run on `dev` \|.*)$", re.MULTILINE)


def _without_timestamp(text: str) -> str:
    return _TIMESTAMP_RE.sub("", text)


def _offline():
    """The dev-run row reads the runs API; a test never reaches it, so the row reads unknown."""
    return mock.patch.object(urllib.request, "urlopen",
                             side_effect=urllib.error.URLError("tests do not reach the network"))


@pytest.fixture(scope="module")
def generated() -> str:
    with _offline():
        return build()


def test_package_facts_survive_an_absent_optional_extra(tmp_path, monkeypatch):
    """A lazy export whose extra is not installed raises ImportError on access, as on the build
    job, which installs neither `vis` nor `wavemap`; the probe counts it as no unresolved name."""
    from scripts import reconstruct_state

    (tmp_path / "plotly.py").write_text('raise ImportError("plotly absent")\n', encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    facts = reconstruct_state.package_facts()
    assert not facts["version"].startswith("UNRESOLVED"), facts
    assert facts["unresolved"] == "0", facts


@pytest.mark.requires_git_checkout
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
    with _offline():
        again = build()
    assert _without_timestamp(generated) == _without_timestamp(again)


def test_a_harness_that_times_out_is_unresolved_not_failed(monkeypatch: pytest.MonkeyPatch):
    """Under load the harness outran the old 120 s cap and the file recorded the gates FAILED.

    A timeout says nothing about the gates. With the cap shortened until every command times out,
    the gates row must read unresolved and name the cause.
    """
    import scripts.reconstruct_state as reconstruct_state

    monkeypatch.setattr(reconstruct_state, "COMMAND_TIMEOUT_S", 0.001)
    with _offline():
        text = reconstruct_state.build()
    row = next(line for line in text.splitlines() if line.startswith("| `scripts/harness_gate.py` |"))
    assert "UNRESOLVED (TimeoutExpired)" in row, row
    assert "FAILED" not in row, row


def test_a_harness_that_crashes_is_failed_not_unresolved(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    """A harness that ran and died without printing a verdict failed; it was not unmeasurable.

    The stand-in exits 3 with nothing on stdout, the shape `run` marks as unresolved elsewhere.
    """
    import scripts.reconstruct_state as reconstruct_state

    crash = tmp_path / "crashing_harness.py"
    crash.write_text("import sys\nsys.stderr.write('Traceback: boom\\n')\nsys.exit(3)\n",
                     encoding="utf-8")
    monkeypatch.setattr(reconstruct_state, "HARNESS_COMMAND", (sys.executable, str(crash)))
    out, verdict = reconstruct_state.harness_verdict()
    assert out == "" and verdict.startswith("FAILED (exit 3)"), verdict
    assert "UNRESOLVED" not in verdict, verdict


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


@pytest.mark.requires_git_checkout
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
        "table rows",
    ):
        assert expected in generated, f"state.md no longer reports {expected!r}"


@pytest.mark.requires_git_checkout
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


def _run_check(monkeypatch: pytest.MonkeyPatch, state_path: pathlib.Path) -> int:
    """``reconstruct_state.py --check`` against ``state_path`` instead of the tree's file."""
    import scripts.reconstruct_state as reconstruct_state

    monkeypatch.setattr(reconstruct_state, "STATE_PATH", state_path)
    monkeypatch.setattr(sys, "argv", ["reconstruct_state.py", "--check"])
    return reconstruct_state.main()


@pytest.mark.requires_git_checkout
def test_a_moved_head_reads_as_stale(
    tmp_path: pathlib.Path, generated: str, monkeypatch: pytest.MonkeyPatch, capsys
):
    """``--check`` exists to stop a stale basis being read as a current one."""
    state = tmp_path / "state.md"
    state.write_text(generated, encoding="utf-8")
    assert _run_check(monkeypatch, state) == 0, capsys.readouterr().out
    assert "PASS" in capsys.readouterr().out

    stale = HEAD_ROW_RE.sub("| HEAD | `" + "0" * 40 + "` |", generated)
    assert recorded_head(stale) == "0" * 40
    state.write_text(stale, encoding="utf-8")
    assert _run_check(monkeypatch, state) == 1
    assert "generated at 000000000000" in capsys.readouterr().out


def test_check_exits_nonzero_when_the_file_is_absent(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """Absence must not read as freshness.

    Every block in gate 8 was once ``if <file>.exists():`` with no else, so an empty directory
    passed. A check satisfied by deleting its own evidence is worse than no check.
    """
    state = tmp_path / "state.md"
    assert not state.exists()
    assert _run_check(monkeypatch, state) == 1
    assert "is missing" in capsys.readouterr().out

    state.write_text("# State\n\nno head row here\n", encoding="utf-8")
    assert _run_check(monkeypatch, state) == 1
    assert "records no HEAD" in capsys.readouterr().out


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


@pytest.mark.requires_git_checkout
def test_it_reports_worktrees_branches_the_dev_run_and_open_defect_classes(generated: str):
    assert "## Awareness" in generated
    assert f"| `{REPO_ROOT.as_posix()}` |" in generated, "the main worktree must be listed"
    # The checked-out branch, not `dev`: CI on `main` checks out `main`, the only local branch.
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    assert f"| `{branch}` |" in generated or "(detached)" in generated
    assert "| Newest CI run on `dev` |" in generated
    assert "| Open defect classes |" in generated


DEV_RUNS_URL = "https://api.github.com/repos/hnxj/jnwb/actions/runs?branch=dev&per_page=1"


class _Reply:
    """One reply from the runs API: a context manager whose body is read."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _runs_api_answers(monkeypatch: pytest.MonkeyPatch, body: object) -> dict:
    """Replace the network with one reply; the returned dict records the request it was asked."""
    seen: dict = {}
    payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def urlopen(request, timeout=None):
        seen.update(url=request.full_url, timeout=timeout)
        return _Reply(payload)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return seen


def _newest_run(conclusion: object, sha: str = "a" * 40) -> dict:
    return {"workflow_runs": [{"head_sha": sha, "conclusion": conclusion}]}


def test_a_failed_dev_run_reads_red_with_its_head_sha(monkeypatch: pytest.MonkeyPatch):
    from scripts import reconstruct_state

    seen = _runs_api_answers(monkeypatch, _newest_run("failure"))
    assert reconstruct_state.newest_dev_run() == "RED: `aaaaaaaaaaaa` failure"
    assert seen == {"url": DEV_RUNS_URL, "timeout": 10}, seen


def test_a_passing_dev_run_reads_its_sha_and_conclusion(monkeypatch: pytest.MonkeyPatch):
    from scripts import reconstruct_state

    _runs_api_answers(monkeypatch, _newest_run("success"))
    assert reconstruct_state.newest_dev_run() == "`aaaaaaaaaaaa` success"


def test_a_timed_out_dev_run_still_reads_red(monkeypatch: pytest.MonkeyPatch):
    from scripts import reconstruct_state

    _runs_api_answers(monkeypatch, _newest_run("timed_out"))
    assert reconstruct_state.newest_dev_run() == "RED: `aaaaaaaaaaaa` timed_out"


def test_an_unreachable_runs_api_reads_unknown_never_a_pass(monkeypatch: pytest.MonkeyPatch):
    from scripts import reconstruct_state

    def unreachable(request, timeout=None):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    assert reconstruct_state.newest_dev_run() == "unknown"


@pytest.mark.parametrize("body", [
    {"message": "API rate limit exceeded"},
    {"workflow_runs": []},
    b"<html>not the runs API</html>",
    _newest_run(None),
])
def test_a_body_without_a_concluded_run_reads_unknown(monkeypatch: pytest.MonkeyPatch, body):
    from scripts import reconstruct_state

    _runs_api_answers(monkeypatch, body)
    assert reconstruct_state.newest_dev_run() == "unknown"


def test_a_prunable_worktree_and_a_merged_branch_are_named(monkeypatch: pytest.MonkeyPatch):
    from scripts import reconstruct_state

    outputs = {
        ("git", "worktree", "list", "--porcelain"):
            "worktree C:/a\nHEAD " + "1" * 40 + "\nbranch refs/heads/dev\n\n"
            "worktree C:/gone\nHEAD " + "2" * 40 + "\ndetached\nprunable gitdir file missing",
        ("git", "for-each-ref", "refs/heads", "--format=%(refname:short) %(objectname)"):
            "dev " + "1" * 40 + "\nlane-done " + "3" * 40 + "\nlane-open " + "4" * 40,
        ("git", "cherry", "dev", "lane-done"): "- " + "3" * 40,
        ("git", "cherry", "dev", "lane-open"): "- " + "5" * 40 + "\n+ " + "4" * 40,
    }
    monkeypatch.setattr(reconstruct_state, "run", lambda *cmd, **kw: outputs[cmd])
    worktrees = reconstruct_state.worktree_rows()
    assert worktrees == ["| `C:/a` | `111111111111` | `dev` |  |",
                         "| `C:/gone` | `222222222222` | `(detached)` | prunable |"]
    branches = {row.split("`")[1]: row for row in reconstruct_state.branch_rows()}
    assert set(branches) == {"dev", "lane-done", "lane-open"}
    assert "stale" in branches["lane-done"]
    assert "stale" not in branches["lane-open"] and "stale" not in branches["dev"]


def test_open_defect_classes_are_the_rows_with_no_landed_check(tmp_path: pathlib.Path):
    from scripts import reconstruct_state

    ledger = tmp_path / "defect_classes.md"
    ledger.write_text(
        "| Class | Seen | Instances | Caught by | Repair | Status |\n|---|---|---|---|---|---|\n"
        "| once-seen: a | 1 | x | y | z | watch |\n"
        "| twice-seen: b | 2 | x | y | z | gate proposed |\n"
        "| checked: c | 3 | x | y | z | check landed: a test |\n"
        "| ruled: d | 2 | x | y | z | rule: a line |\n", encoding="utf-8")
    assert reconstruct_state.open_defect_classes(ledger) == "twice-seen (seen 2); once-seen (seen 1)"
    assert reconstruct_state.open_defect_classes(tmp_path / "absent.md").startswith("UNRESOLVED (")


def test_growth_rows_count_the_scripts_and_each_process_test(generated: str):
    assert "## Growth" in generated, "the state file records no line counts"
    from scripts.reconstruct_state import PROCESS_TESTS

    scripts = sorted((REPO_ROOT / "scripts").glob("*.py"))
    total = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in scripts)
    assert f"| `scripts/` | {total} |" in generated, total
    for rel in PROCESS_TESTS:
        path = REPO_ROOT / rel
        if path.is_file():
            lines = len(path.read_text(encoding="utf-8").splitlines())
            assert f"| `{rel}` | {lines} |" in generated, rel
