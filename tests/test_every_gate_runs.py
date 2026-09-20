"""The harness reports every gate's state, and PASS means every gate ran and passed.

Recorded as the second of three repairs ruled on 2026-09-19. The runner returned at the first
failing gate. Agent worktrees inside the repository tripped gate 2, the runner stopped, and gates
3 through 13 did not execute -- including gate 4, which held a second and genuine instance of the
same defect and became visible only once gate 2 was fixed. One PASS line where thirteen were
expected, and three packets reported the resulting red suite as unrelated to their work without
anyone establishing that the later gates had run.

The invariant is not "print more lines". It is:

    harness PASS  <=>  every gate executed and every gate passed

A first failure makes every later gate *unknown*. The defect was treating unknown as observed.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts import harness_gate  # noqa: E402


def _seed_one_failing_gate(monkeypatch, number: int) -> None:
    """Replace one gate's runner with a guaranteed failure, leaving the others alone."""
    seeded = []
    for gate_number, run, pass_line in harness_gate.GATES:
        if gate_number == number:
            seeded.append(
                (gate_number, lambda: [("FAIL: seeded.", ["SEEDED_VIOLATION"])], pass_line)
            )
        else:
            seeded.append((gate_number, run, pass_line))
    monkeypatch.setattr(harness_gate, "GATES", seeded)


def test_the_live_repository_passes_every_gate(capsys):
    assert harness_gate.run_full_preflight() is True
    out = capsys.readouterr().out
    assert out.count("PASS:") == len(harness_gate.GATES)
    assert "ALL HARNESS GATES PASSED." in out


def test_a_failure_at_gate_2_does_not_stop_the_gates_after_it(capsys):
    """The exact shape of the incident: gate 2 failed and gate 4's defect stayed invisible."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        _seed_one_failing_gate(monkeypatch, 2)
        assert harness_gate.run_full_preflight() is False
        out = capsys.readouterr().out

    assert "SEEDED_VIOLATION" in out
    # Twelve gates still had something to say, and gate 13 is the proof the runner reached the end.
    assert out.count("PASS:") == len(harness_gate.GATES) - 1
    assert "NWB onboarding workflow aligned" in out
    assert "OVERALL: FAIL" in out
    assert "13 of 13 gates executed" in out


@pytest.mark.parametrize("number", [n for n, _, _ in harness_gate.GATES])
def test_any_single_gate_failing_still_runs_all_thirteen(capsys, number):
    """Not just gate 2. No gate may be positioned such that its failure hides another."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        _seed_one_failing_gate(monkeypatch, number)
        assert harness_gate.run_full_preflight() is False
        out = capsys.readouterr().out

    assert out.count("PASS:") == len(harness_gate.GATES) - 1, out
    assert f"{len(harness_gate.GATES)} of {len(harness_gate.GATES)} gates executed" in out


def test_a_gate_that_raises_is_reported_and_does_not_stop_the_rest(capsys):
    """A broken gate is a failure of that gate, not a licence to skip the others."""

    def explode():
        raise RuntimeError("gate is broken")

    with pytest.MonkeyPatch.context() as monkeypatch:
        seeded = [
            (n, explode if n == 5 else run, pass_line)
            for n, run, pass_line in harness_gate.GATES
        ]
        monkeypatch.setattr(harness_gate, "GATES", seeded)
        assert harness_gate.run_full_preflight() is False
        out = capsys.readouterr().out

    assert "ERROR: gate 5 raised RuntimeError: gate is broken" in out
    assert out.count("PASS:") == len(harness_gate.GATES) - 1
    assert "13 of 13 gates executed" in out


def test_a_gate_that_does_not_execute_is_named_not_passing(capsys):
    """A gate that vanishes from the output looks exactly like a gate with nothing to say.

    This asserted nothing of the kind. Its second `monkeypatch.setattr` rebuilt the list from
    `harness_gate.GATES`, which was already the truncated three-element list, so the only live
    assertion was `run_full_preflight() is True` on a passing tree. 06-64 deleted the entire
    NOT RUN block and this test -- and the whole suite -- stayed green.

    An interrupt is the one thing that genuinely abandons a gate, so that is what is simulated.
    """
    def interrupts() -> list:
        raise KeyboardInterrupt("simulated interrupt part-way through the run")

    with pytest.MonkeyPatch.context() as monkeypatch:
        gates = list(harness_gate.GATES)
        # Gate 2 of 3 is abandoned; gate 3 therefore never runs.
        monkeypatch.setattr(
            harness_gate,
            "GATES",
            [gates[0], (gates[1][0], interrupts, gates[1][2]), gates[2]],
        )
        with pytest.raises(KeyboardInterrupt):
            harness_gate.run_full_preflight()
        out = capsys.readouterr().out

    abandoned, never_reached = gates[1][0], gates[2][0]
    assert f"NOT RUN: gate {abandoned}" in out, (
        f"the abandoned gate {abandoned} is absent from the report:\n{out}"
    )
    assert f"NOT RUN: gate {never_reached}" in out, (
        f"gate {never_reached} never ran and was not named:\n{out}"
    )
    assert "OVERALL: FAIL." in out, f"an interrupted run did not report FAIL:\n{out}"
    assert "1 of 3 gates executed" in out, f"the executed count is wrong:\n{out}"


def test_the_not_run_branch_is_reachable_at_all(capsys):
    """The discriminator for the branch itself: delete it and this must fail.

    `not_run` was unreachable before 2026-09-20 -- every path through the loop appended to
    `executed`, so the list was always empty and the block was dead code that read as a safeguard.
    """
    def interrupts() -> list:
        raise SystemExit(2)

    with pytest.MonkeyPatch.context() as monkeypatch:
        gates = list(harness_gate.GATES)
        monkeypatch.setattr(harness_gate, "GATES", [(gates[0][0], interrupts, gates[0][2])])
        with pytest.raises(SystemExit):
            harness_gate.run_full_preflight()
        out = capsys.readouterr().out

    assert "NOT RUN" in out, (
        "a run abandoned at its first gate produced no NOT RUN line, so the branch is dead "
        f"code again:\n{out}"
    )


def test_a_failing_pass_line_does_not_abort_the_run(capsys):
    """`pass_line()` sat outside the try, so a broken formatter killed every later gate."""
    def explodes() -> str:
        raise RuntimeError("formatter is broken")

    with pytest.MonkeyPatch.context() as monkeypatch:
        gates = list(harness_gate.GATES)
        monkeypatch.setattr(
            harness_gate,
            "GATES",
            [(gates[0][0], gates[0][1], explodes), gates[1], gates[2]],
        )
        verdict = harness_gate.run_full_preflight()
        out = capsys.readouterr().out

    assert verdict is False, "a gate whose pass line raised was reported as passing"
    assert "3 of 3 gates executed" in out, (
        f"a broken formatter stopped the run instead of failing one gate:\n{out}"
    )
    assert "NOT RUN" not in out, f"gates were skipped by a formatter error:\n{out}"


def test_pass_requires_every_gate_and_not_merely_no_failures(capsys):
    """Pins the contract itself, so a later refactor cannot make PASS mean 'nothing complained'."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(harness_gate, "GATES", [])
        assert harness_gate.run_full_preflight() is True
        assert "ALL HARNESS GATES PASSED." in capsys.readouterr().out

    # An empty gate list trivially passes, which is why the count is asserted separately here and
    # in test_the_live_repository_passes_every_gate rather than inferred from the verdict line.
    assert len(harness_gate.GATES) == 13
