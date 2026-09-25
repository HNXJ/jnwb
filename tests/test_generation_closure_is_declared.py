"""A write set can be complete, correct and disjoint and still invalidate a file outside it.

06-47 added `stagger_tolerance_um` to `probe_geometry`'s signature. `docs/api.md` records
signatures and is generated from the live objects, so it went stale the moment that parameter
landed -- and it was in no lane's write set, because no lane edits that page by hand. The
integrated suite went 25 failed, of which 18 were `test_every_gate_runs.py` cascading from one
real gate-9 failure. The 25 were one defect wearing 25 masks: a count of failures is not a
count of causes, and reading it as one sends the repair at the gate-count assertions instead of
at the generator (P-173).

P-162 established that write sets must be compared by resolved path rather than by string.
This is the next layer: they must also be closed under generation. `GENERATED_FROM` is that
closure, written down.

The obligation sits on the integrator rather than on the write sets, and that was measured, not
assumed: 7 of 52 live items name a path under `jnwb/` and none names `docs/api.md`, so
requiring them all to name it would make those 7 mutually exclusive with one another and
declare a maximum parallelism of one across every item touching the package -- P-108's defect
in a new spelling. The test below pins that measurement, so a future change to the rule has to
confront the number rather than rediscover it.

A declaration that points at other files goes stale without erroring, which is why the gate
resolves every entry against disk and why these tests exercise the gate rather than the
constant.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# append, never insert(0): the wheel leg must keep resolving the installed copy.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.harness_gate import (  # noqa: E402
    GENERATED_FROM,
    _writes_fields,
    check_stack_form_consistency,
)


def test_the_closure_declares_something():
    """An empty closure would make every check below pass vacuously."""
    assert GENERATED_FROM
    derived = {entry["derived"] for entry in GENERATED_FROM}
    assert "docs/api.md" in derived, (
        "docs/api.md is the instance P-173 was raised on and must be declared"
    )


def test_every_entry_resolves_against_the_tree():
    """The gate's own check, run on the real tree rather than a fixture."""
    violations = [v for v in check_stack_form_consistency(REPO_ROOT)
                  if "GENERATED_FROM" in v]
    assert violations == []


def test_each_generator_exists_and_each_tracked_derived_file_exists():
    """Stated separately from the gate so a gate that stopped checking is still caught here."""
    for entry in GENERATED_FROM:
        assert (REPO_ROOT / entry["generator"]).is_file(), entry["generator"]
        if entry["tracked"]:
            assert (REPO_ROOT / entry["derived"]).is_file(), entry["derived"]


def test_an_untracked_derived_file_is_not_required_to_exist():
    """`artifacts/state.md` is generated per tree and gitignored.

    Requiring it would fail every fresh worktree, so "declared derived" and "must be committed
    in step" are deliberately different properties. If this entry were ever marked tracked, a
    clean checkout would fail the gate for a file it is correct not to have.
    """
    untracked = [e for e in GENERATED_FROM if not e["tracked"]]
    assert untracked, "the distinction is unexercised if every entry is tracked"
    for entry in untracked:
        # The gate must not complain about it whether or not it happens to be present.
        violations = [v for v in check_stack_form_consistency(REPO_ROOT)
                      if entry["derived"] in v and "not in the tree" in v]
        assert violations == []


def test_the_gate_catches_a_generator_that_has_been_renamed(monkeypatch):
    """The failure mode a declaration has: it keeps reading as true after the file moves."""
    import scripts.harness_gate as hg

    broken = ({
        "derived": "docs/api.md",
        "sources": ("jnwb/",),
        "generator": "scripts/generate_api_md_RENAMED.py",
        "verified_by": "nothing, which is the point",
        "tracked": True,
    },)
    monkeypatch.setattr(hg, "GENERATED_FROM", broken)
    violations = hg.check_stack_form_consistency(REPO_ROOT)
    assert any("generate_api_md_RENAMED.py" in v for v in violations), violations
    assert any("missing generator" in v for v in violations), violations


def test_the_gate_catches_a_source_that_no_longer_exists(monkeypatch):
    import scripts.harness_gate as hg

    broken = ({
        "derived": "docs/api.md",
        "sources": ("jnwb_OLD_NAME/",),
        "generator": "scripts/generate_api_md.py",
        "verified_by": "nothing",
        "tracked": True,
    },)
    monkeypatch.setattr(hg, "GENERATED_FROM", broken)
    violations = hg.check_stack_form_consistency(REPO_ROOT)
    assert any("jnwb_OLD_NAME/" in v for v in violations), violations


def test_the_gate_catches_an_empty_closure(monkeypatch):
    """Without this, deleting the constant's contents would silence every check above."""
    import scripts.harness_gate as hg

    monkeypatch.setattr(hg, "GENERATED_FROM", ())
    violations = hg.check_stack_form_consistency(REPO_ROOT)
    assert any("passes vacuously" in v for v in violations), violations


def test_a_described_trigger_is_not_resolved_as_a_path():
    """`<any HEAD move>` is a trigger, not a file, and must not be looked up on disk."""
    triggers = [s for e in GENERATED_FROM for s in e["sources"] if s.startswith("<")]
    assert triggers, "the angle-bracket convention is unexercised"
    violations = [v for v in check_stack_form_consistency(REPO_ROOT) if "<" in v]
    assert violations == []


def test_the_measurement_that_chose_the_integrator_over_the_write_sets():
    """Pins why derived files are not required in `Writes:` sets.

    If this count changes materially, the trade-off behind the rule has changed and should be
    re-decided rather than inherited. The count of items writing under `jnwb/` is not held to
    a floor: the stack drains to empty at every release, so a floor fails on a healthy stack.
    What stays held is the arrangement the rule rejected -- a write set naming `docs/api.md`.
    """
    todo = (REPO_ROOT / "artifacts" / "todo_stack.md").read_text(encoding="utf-8")
    fields = _writes_fields(todo)
    assert fields, "the sweep is broken, not the stack"

    naming = 0
    for _lineno, field in fields:
        spans = re.findall(r"`([^`\n]*)`", field)
        if any(s.startswith("jnwb/") for s in spans) and "docs/api.md" in spans:
            naming += 1

    assert naming == 0, (
        f"{naming} item(s) now name docs/api.md in a write set. That is the serializing "
        "arrangement this rule rejected on measurement -- revisit the rule deliberately "
        "rather than drifting into it"
    )


def test_the_contract_requires_the_canonical_mutation_harness():
    """P-87 and P-134: the mechanism existed and no document told anyone to use it.

    `scripts/mutation_harness.py` derives its state directory from the worktree, refuses a path
    outside it, and locks one session per worktree -- and for three collisions across two
    batches every lane still hand-rolled a harness into the shared scratchpad, because nothing
    in the contract said otherwise. The repair is the sentence, so the sentence is what is
    pinned here.
    """
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "scripts/mutation_harness.py" in contributing, (
        "CONTRIBUTING.md must name the canonical mutation harness; an unmentioned mechanism "
        "is one every lane reimplements in the shared scratchpad"
    )
    assert "restore" in contributing.lower(), (
        "the reason must travel with the rule: the danger is the restore targeting a tree the "
        "session does not own, not the lost file"
    )


def test_the_harness_the_contract_names_actually_isolates_by_worktree():
    """The sentence is only worth pinning if what it points at does the thing."""
    from scripts.mutation_harness import state_dir_for

    a = state_dir_for(pathlib.Path("/tmp/worktree-alpha"))
    b = state_dir_for(pathlib.Path("/tmp/worktree-beta"))
    assert a != b, "two worktrees must not share a state directory"


@pytest.mark.parametrize("outside", ["..", "../sibling/file.py"])
def test_the_harness_refuses_a_path_outside_the_worktree(outside):
    from scripts.mutation_harness import OutsideWorktree, ensure_inside_worktree

    with pytest.raises(OutsideWorktree):
        ensure_inside_worktree(REPO_ROOT / outside, REPO_ROOT)
