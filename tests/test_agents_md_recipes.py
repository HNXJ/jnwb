"""`AGENTS.md` says "Each call below runs as written on synthetic arrays". Now it does.

Section 10 defined a generator and then called eight functions on names no block bound --
`spike_times`, `lfp`, `x`, `g1` -- so nothing in it ran as written. One call was wrong even
given its inputs: `aggregate_to_db(beta_raw, baseline_raw, how="mean_of_ratios",
aggregate_over=0)` raises `AxisError: axis 0 is out of bounds for array of dimension 0`,
because `band_power` returns a float and there is no axis 0 to aggregate over. That is the
canonical demonstration of the rule this repository repeats most often -- take the logarithm
last -- and it did not run.

The file also cited a todo item that does not exist, and named a comparison entry point the
statistics skill did not route to.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS = REPO_ROOT / "AGENTS.md"


def _python_blocks(text: str) -> list[str]:
    return re.findall(r"^```python\n(.*?)^```", text, re.M | re.S)


def test_the_sweep_finds_the_recipe_block():
    blocks = _python_blocks(AGENTS.read_text(encoding="utf-8"))
    assert blocks, "AGENTS.md has no ```python block; this file checks nothing"


@pytest.mark.parametrize("index", range(len(_python_blocks(AGENTS.read_text(encoding="utf-8")))))
def test_every_python_block_in_agents_md_runs_as_written(index, tmp_path, monkeypatch):
    """Executed outside the checkout, so a block reaching for a relative path fails here."""
    block = _python_blocks(AGENTS.read_text(encoding="utf-8"))[index]
    monkeypatch.chdir(tmp_path)
    exec(compile(block, "AGENTS.md", "exec"), {"__name__": "__agents__"})  # noqa: S102


def test_every_repository_path_agents_md_cites_exists():
    """A pointer to a file that is not there is the same defect as a stale signature."""
    # A line that says what a path would be *elsewhere* is not a claim about this repository:
    # AGENTS.md is copied into repositories without an artifacts/ tree, and names the fallback.
    lines = [ln for ln in AGENTS.read_text(encoding="utf-8").splitlines()
             if "when the repository has no" not in ln]
    cited = set(re.findall(r"`((?:jnwb|tests|docs|skills|scripts|examples|artifacts)/[\w./-]+)`",
                           "\n".join(lines)))
    assert len(cited) >= 10, f"only {len(cited)} paths matched; the sweep has stopped working"
    missing = sorted(p for p in cited if not (REPO_ROOT / p).exists())
    # A generated, git-ignored file is absent until its generator runs, which is the normal state
    # of every fresh checkout and every agent worktree. `artifacts/state.md` is the case: the
    # suite failed in each fan-out worktree for a pointer that is correct and simply not yet
    # materialised. The pointer does resolve for a reader -- after one command.
    # The exemption is deliberately narrow: ignored by git AND named by a script that writes it.
    # A path that is merely missing is still the defect this test exists for.
    missing = [p for p in missing if not _is_generated_by_a_script(p)]
    assert not missing, f"AGENTS.md cites paths that do not exist: {missing}"


def _is_generated_by_a_script(rel_path: str) -> bool:
    """True only for a git-ignored path that some `scripts/*.py` names as an output."""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", rel_path], cwd=REPO_ROOT, capture_output=True
    )
    if ignored.returncode != 0:
        return False
    name = Path(rel_path).name
    return any(
        name in script.read_text(encoding="utf-8", errors="replace")
        for script in (REPO_ROOT / "scripts").glob("*.py")
    )


def test_the_generated_path_exemption_does_not_excuse_an_ordinary_missing_file():
    """The discriminator for the carve-out above, so it cannot widen into a blanket excuse."""
    assert not _is_generated_by_a_script("artifacts/not_a_real_artifact.md"), (
        "a path no script writes was treated as generated"
    )
    assert not _is_generated_by_a_script("jnwb/__init__.py"), (
        "a tracked file was treated as generated"
    )
    assert _is_generated_by_a_script("artifacts/state.md"), (
        "the one path the carve-out exists for is no longer recognised by it; if state.md became "
        "tracked, delete the carve-out rather than loosening it"
    )


def test_agents_md_does_not_point_at_a_todo_item_that_is_not_there():
    text = AGENTS.read_text(encoding="utf-8")
    assert "non-blocking scan item in the todo stack" not in text
    for match in re.finditer(r"the (\S+) item in the todo stack", text):
        stack = (REPO_ROOT / "artifacts" / "todo_stack.md").read_text(encoding="utf-8")
        assert match.group(1) in stack, (
            f"AGENTS.md points at the {match.group(1)!r} item, which is not in the stack"
        )


def test_agents_md_and_the_statistics_skill_route_to_one_comparison_entry_point():
    """Both entry points exist and their return keys differ.

    `AGENTS.md` §10 used `exploratory_compare` while the statistics skill routed to
    `compare_groups`, which also returns `multiple_comparison` and takes an `rng`. An agent
    reading one and calling the other reads keys that are not there. A signature check cannot
    see this: both rows are valid calls.
    """
    recipes = AGENTS.read_text(encoding="utf-8").split("## 10. Recipes", 1)[1]
    skill = (REPO_ROOT / "skills" / "jnwb-statistics" / "SKILL.md").read_text(encoding="utf-8")
    # Calls, not mentions: the skill names the other function in prose to say what it is,
    # which is explanation rather than a route.
    called = re.compile(r"StatisticalAnalysis\.(\w+)\(")
    in_recipes = set(called.findall(recipes))
    in_skill = set(called.findall(skill))
    for name in ("exploratory_compare", "compare_groups"):
        assert (name in in_recipes) == (name in in_skill), (
            f"{name} is in one of AGENTS.md §10 and skills/jnwb-statistics and not the other; "
            "their returned keys differ, so an agent reading one and calling the other reads "
            "keys that are not there"
        )


def test_the_change_rule_requires_the_skills_to_move_with_the_api():
    """The gap that produced every defect in the routing matrices.

    Section 8 required a public API change to reach `CHANGELOG.md` with a deprecation path,
    and said nothing about the 65 routing rows that hardcode signatures.
    """
    section = AGENTS.read_text(encoding="utf-8").split("## 8. Changes", 1)[1].split("\n## ", 1)[0]
    assert "skills/" in section and "same commit" in section, (
        "section 8 does not require a public API change to update the routing rows"
    )
