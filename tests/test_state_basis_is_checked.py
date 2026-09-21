"""``artifacts/state.md`` said a gate kept it fresh, and no gate ever read it.

P-65. The sentence was emitted by ``scripts/reconstruct_state.py``, so every regeneration
re-asserted the protection, and ``scripts/harness_gate.py`` has never mentioned the file --
the gate reported 13 of 13 while the basis on disk was stale. The one test that invoked
``--check`` asserted ``"PASS" in out or "ERROR" in out``, and both outcomes satisfy that, so
it would have passed against a ``--check`` that could only ever print one of them.

Two things are tested here. ``--check`` must separate a current basis from a stale one by exit
code and by which word it prints, and the sentence the generator emits must agree with whether
a harness gate reads the file. The second is what stops the claim drifting back: a gate wired
in later flips the scan and the prose has to follow it.

The discriminator runs against a copy of the generator in a scratch repository. ``--check``
resolves both the state file and the repository from the script's own location, so the copy
exercises the same code against a HEAD these tests own, and an interrupted run leaves no
half-restored ``artifacts/state.md`` in the working tree.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "reconstruct_state.py"
HARNESS_GATE = ROOT / "scripts" / "harness_gate.py"
STATE_FILE = ROOT / "artifacts" / "state.md"

#: The HEAD row, written out rather than imported from the generator. Importing its own regex
#: would make the oracle a restatement of the thing under test.
HEAD_ROW = re.compile(r"^\| HEAD \| `([0-9a-f]{40})` \|$", re.MULTILINE)

#: The sentence the generator emits while no harness gate reads the file.
NO_GATE_SENTENCE = "No harness gate reads this file"

#: The P-65 claim. Absence of this exact string proves nothing on its own; it is asserted
#: alongside the positive check below so the sentence cannot be reinstated verbatim.
RETRACTED_CLAIM = "a gate fails when this file no longer matches the tree"

ZERO_SHA = "0" * 40


def _state_text(head: str) -> str:
    return f"# State\n\n| Quantity | Value |\n|---|---|\n| HEAD | `{head}` |\n"


def _git(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    # Identity is supplied per invocation, and signing is disabled for this throwaway fixture
    # repository only: a contributor with `commit.gpgsign = true` would otherwise block on a
    # passphrase prompt inside a test.
    command = [
        "git",
        "-c", "user.name=state basis fixture",
        "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false",
        *args,
    ]
    proc = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"{' '.join(args)} failed: {proc.stderr.strip()}"
    return proc


def _check(root: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "reconstruct_state.py"), "--check"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """A scratch repository with one commit and a byte-identical copy of the generator."""
    root = tmp_path_factory.mktemp("state_basis")
    (root / "scripts").mkdir()
    (root / "artifacts").mkdir()
    shutil.copy2(GENERATOR, root / "scripts" / GENERATOR.name)
    assert (root / "scripts" / GENERATOR.name).read_bytes() == GENERATOR.read_bytes(), (
        "the copied generator differs from the one in the tree, so this fixture would test "
        "something other than the shipped script"
    )
    _git(root, "init", "-q")
    (root / "README").write_text("state basis fixture\n", encoding="utf-8", newline="\n")
    _git(root, "add", "README")
    _git(root, "commit", "-qm", "fixture")
    return root


@pytest.fixture(scope="module")
def sandbox_head(sandbox: pathlib.Path) -> str:
    head = _git(sandbox, "rev-parse", "HEAD").stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", head), head
    assert head != ZERO_SHA
    return head


@pytest.fixture(scope="module")
def current_outcome(sandbox: pathlib.Path, sandbox_head: str) -> subprocess.CompletedProcess:
    """``--check`` against a basis recorded at the live HEAD.

    This runs first and is asserted to pass. A selector that cannot pass on a pristine input
    exits non-zero for a reason unrelated to staleness, and every failure below would then be
    indistinguishable from a kill.
    """
    (sandbox / "artifacts" / "state.md").write_text(
        _state_text(sandbox_head), encoding="utf-8", newline="\n"
    )
    return _check(sandbox)


@pytest.fixture(scope="module")
def stale_outcome(
    sandbox: pathlib.Path, sandbox_head: str, current_outcome: subprocess.CompletedProcess
) -> subprocess.CompletedProcess:
    """``--check`` against the same basis with its HEAD row moved off the live commit."""
    assert current_outcome.returncode == 0, "the pristine case must pass before a kill counts"
    state = sandbox / "artifacts" / "state.md"
    staled = HEAD_ROW.sub(f"| HEAD | `{ZERO_SHA}` |", _state_text(sandbox_head))
    assert ZERO_SHA in staled and sandbox_head not in staled, (
        "the HEAD row was not substituted, so the file is not stale and a pass here would "
        "mean nothing"
    )
    state.write_text(staled, encoding="utf-8", newline="\n")
    outcome = _check(sandbox)
    state.write_text(_state_text(sandbox_head), encoding="utf-8", newline="\n")
    assert _check(sandbox).returncode == 0, "the fixture repository was left stale"
    return outcome


def test_a_basis_recorded_at_the_live_head_passes(
    current_outcome: subprocess.CompletedProcess,
) -> None:
    assert current_outcome.returncode == 0, current_outcome.stdout + current_outcome.stderr
    assert current_outcome.stdout.startswith("PASS:"), current_outcome.stdout


def test_a_moved_head_fails(
    stale_outcome: subprocess.CompletedProcess, sandbox_head: str
) -> None:
    assert stale_outcome.returncode == 1, stale_outcome.stdout + stale_outcome.stderr
    assert stale_outcome.stdout.startswith("ERROR:"), stale_outcome.stdout
    assert ZERO_SHA[:12] in stale_outcome.stdout, (
        "the message does not say which commit the file was built at, so a reader cannot "
        f"tell how far behind it is: {stale_outcome.stdout}"
    )
    assert sandbox_head[:12] in stale_outcome.stdout, stale_outcome.stdout


def test_an_absent_file_fails(sandbox: pathlib.Path, sandbox_head: str) -> None:
    """Absence must not read as freshness, and it is the state of every fresh checkout."""
    state = sandbox / "artifacts" / "state.md"
    state.unlink()
    outcome = _check(sandbox)
    state.write_text(_state_text(sandbox_head), encoding="utf-8", newline="\n")
    assert _check(sandbox).returncode == 0, "the fixture repository was left without a basis"
    assert outcome.returncode == 1, outcome.stdout + outcome.stderr
    assert outcome.stdout.startswith("ERROR:"), outcome.stdout


def test_a_file_with_no_head_row_fails(sandbox: pathlib.Path, sandbox_head: str) -> None:
    """A basis that records no commit cannot be compared, and unknown is not current."""
    state = sandbox / "artifacts" / "state.md"
    state.write_text("# State\n\nno head row here\n", encoding="utf-8", newline="\n")
    outcome = _check(sandbox)
    state.write_text(_state_text(sandbox_head), encoding="utf-8", newline="\n")
    assert _check(sandbox).returncode == 0, "the fixture repository was left unreadable"
    assert outcome.returncode == 1, outcome.stdout + outcome.stderr
    assert outcome.stdout.startswith("ERROR:"), outcome.stdout


def test_the_old_predicate_cannot_tell_the_two_outcomes_apart(
    current_outcome: subprocess.CompletedProcess,
    stale_outcome: subprocess.CompletedProcess,
) -> None:
    """The assertion this module replaces, run against both outcomes it was meant to separate.

    ``tests/test_state_reconstruction.py`` asserted ``"PASS" in out or "ERROR" in out``. Held
    against the two real outputs it is true for both, so it reports the same verdict whichever
    one ``--check`` produces. What follows it here is the assertion that does separate them.
    """
    def old(out: str) -> bool:
        return ("PASS" in out) or ("ERROR" in out)

    assert old(current_outcome.stdout) and old(stale_outcome.stdout), (
        "the old predicate no longer matches either outcome, so this test is measuring "
        "something other than the tautology it was written for"
    )
    assert (current_outcome.returncode, current_outcome.stdout[:5]) != (
        stale_outcome.returncode,
        stale_outcome.stdout[:5],
    ), "the two outcomes are identical in exit code and first word; nothing can separate them"


def test_a_state_file_in_this_tree_is_current() -> None:
    """The suite-level half of what ``artifacts/state.md`` now claims about itself.

    Absence is covered by ``test_an_absent_file_fails`` against the fixture repository, where
    it is asserted rather than skipped. Here absence is the ordinary state of a fresh checkout:
    the file is generated and gitignored.
    """
    if not STATE_FILE.exists():
        pytest.skip("artifacts/state.md has not been generated in this working tree")
    recorded = HEAD_ROW.search(STATE_FILE.read_text(encoding="utf-8"))
    assert recorded is not None, (
        "artifacts/state.md records no HEAD, so nothing can say whether it is current; "
        "run python scripts/reconstruct_state.py"
    )
    live = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=60
    )
    assert live.returncode == 0, live.stderr
    assert recorded.group(1) == live.stdout.strip(), (
        f"artifacts/state.md was generated at {recorded.group(1)[:12]} and HEAD is now "
        f"{live.stdout.strip()[:12]}; run python scripts/reconstruct_state.py"
    )


def _harness_gate_reads_the_state_file(text: str) -> bool:
    """Whether ``scripts/harness_gate.py`` names the state file or its generator.

    Naming is necessary to read it, so a gate that reads the file cannot escape this. A gate
    that names it without reading it trips it and costs one sentence of prose, which is the
    cheap direction to be wrong in.
    """
    return "reconstruct_state" in text or "state.md" in text


def test_the_gate_scan_separates_a_gate_that_names_the_file_from_one_that_does_not() -> None:
    """Both branches of the scan, so the test below cannot pass on a scan that never fires."""
    assert not _harness_gate_reads_the_state_file("def gate_1():\n    return []\n")
    assert _harness_gate_reads_the_state_file('run("scripts/reconstruct_state.py", "--check")')
    assert _harness_gate_reads_the_state_file('path = ROOT / "artifacts" / "state.md"')


def test_the_generated_prose_agrees_with_whether_a_gate_reads_the_file() -> None:
    """The durable half: the claim and the mechanism cannot drift apart again.

    Asserted against the text ``build()`` returns, not against the f-string in the source. A
    source-level check would pass on a generator that had stopped using the template.
    """
    try:
        import scripts.reconstruct_state as generator
    except ModuleNotFoundError:  # pragma: no cover - only on an installed-copy run
        pytest.skip(
            "scripts/ is not importable, so this run qualifies an installed copy and the "
            "generator is a checkout-only script; the discriminator above needs no import "
            "and has already run"
        )
    imported = pathlib.Path(generator.__file__).resolve()
    assert imported == GENERATOR, f"imported {imported}, not the checkout's {GENERATOR}"

    generated = generator.build()
    reads = _harness_gate_reads_the_state_file(HARNESS_GATE.read_text(encoding="utf-8"))

    if reads:
        assert NO_GATE_SENTENCE not in generated, (
            "scripts/harness_gate.py now names artifacts/state.md, and the sentence the "
            f"generator emits still says {NO_GATE_SENTENCE!r}. Say what the gate does instead."
        )
    else:
        assert NO_GATE_SENTENCE in generated, (
            "no harness gate reads artifacts/state.md and the generated file no longer says "
            "so. P-65 is this sentence overstating its protection; a reader who believes the "
            "basis is held fresh does not run --check."
        )
        assert RETRACTED_CLAIM not in generated, (
            "the P-65 sentence is back in the generated file verbatim"
        )
