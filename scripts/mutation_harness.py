"""Mutation harness that proves its own selectors before it is allowed to report a kill.

A mutation run is only evidence if a red run is red for the reason claimed. Every failure this
module exists to prevent was measured in this repository, and each produced a *confident wrong
answer* rather than an error:

* **Six false kills in 0.2.5.** A selector named a bare test method (``tests/t.py::test_x``)
  where the test is a method of a class. pytest collects nothing and exits non-zero, and that
  exit code is indistinguishable from a kill. Six mutants were reported dead and a real gap hid
  behind them. Nothing here emits a verdict until the selector has been shown to collect *and*
  to pass on the pristine tree, and an empty collection names the class-qualified node id the
  selector should have used.
* **A write-restore harness left live mutants**, because the restore was verified once at the
  end of the run instead of after each mutant. Every restore is verified by sha256, per mutant,
  in a ``finally``.
* **Two lanes overwrote each other's harness state** in a shared session scratchpad (P-134). A
  worktree isolates the repository, not the scratchpad. State lives under a path derived from
  the worktree being operated on, a path outside that worktree is never written or restored,
  and one worktree admits one session at a time under an OS-level lock.
* **A fixture that did not build the case it was named after.** A ``nested-clone`` fixture built
  an empty ``.git``, agreed with the defect, and passed as a discriminator. So a mutant must be
  *observed*: the specific node id named in ``must_fail`` has to appear as a ``FAILED``. A run
  that merely went red is a :class:`ConditionFailed`, not a kill -- and a node that ``ERROR``\\ ed
  is not an observation either, because the test body never ran.

* **A mutant that breaks nothing, left live for three days** (P-174). ``test_no_broken_links``
  ran with ``if False and`` wired into its own check and passed vacuously through four green
  suite runs. The suite could not catch it: *a mutant that suppresses a check cannot be caught
  by the check it suppresses.* Neither could the journal, which predates the mutant and answers
  ``[]`` to "what is outstanding?" whether it has no records or no file. So a session now
  **states the tree it ran against**: every tracked modification at entry is compared against the
  set the caller declares it meant to make, and an undeclared one refuses the run by name. And a
  journal that is missing or unparseable reports *unknown*, never *empty*.

The nine conditions in :data:`CONDITIONS` are enforced here, each at exactly one site, and each
raises a :class:`ConditionFailed` carrying its own ``condition`` name. A discriminator can drive a
scenario and assert *which* guard stopped it, which is what makes each guard individually
killable by mutation. A guard duplicated for safety is a guard that no test can prove is
load-bearing.

A case may also declare itself an **expected survivor** (:attr:`MutationCase.expected_survivor`).
A ``Verdict`` with ``killed=False`` was otherwise only ever a failure, so a *measured* coverage
gap had nowhere to live but a lane report, and a measured hole becomes a forgotten one (P-172).
An expected survivor inverts the assertion: the gap is asserted to still be a gap, and the run
fails when the mutant starts being killed and nobody updated the record.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

#: The conditions, in the order they are enforced. ``tree-declared`` is enforced once at session
#: entry and the rest per case; a verdict exists only if all nine held. These are not labels: each
#: is the ``condition`` attribute of a real :class:`ConditionFailed`, so "every condition is
#: reachable" is a checkable statement about behaviour rather than a claim about a docstring.
CONDITIONS: tuple[str, ...] = (
    "tree-declared",
    "pristine-collects",
    "pristine-passes",
    "lands-once",
    "source-differs",
    "mutant-collects",
    "mutant-observed",
    "restore-byte-exact",
    "run-digest-clean",
)

#: How long any single pytest invocation may take. A hung child would otherwise hold a mutant on
#: disk indefinitely, which is the one state this module must never leave behind.
PYTEST_TIMEOUT_S = 900

#: How long any single git invocation may take.
GIT_TIMEOUT_S = 120


class MutationHarnessError(RuntimeError):
    """Base class. Every refusal this module makes is one of these."""


class ConditionFailed(MutationHarnessError):
    """One of the eight per-case conditions did not hold.

    Carries the condition's name, so a caller can tell which guard stopped it apart from the
    message text, which is prose and may be reworded.
    """

    def __init__(
        self,
        condition: str,
        message: str,
        suggested: Sequence[str] = (),
    ) -> None:
        if condition not in CONDITIONS:
            raise MutationHarnessError(
                f"{condition!r} is not one of the declared conditions {CONDITIONS}"
            )
        super().__init__(f"[{condition}] {message}")
        self.condition = condition
        #: The message without the condition prefix, so a caller can re-raise the same condition
        #: with more detail instead of nesting the prefix.
        self.detail = message
        #: Class-qualified node ids the selector should have used. Non-empty only for the
        #: unqualified-method case that produced six false kills; asserting on it is how that
        #: diagnostic is held to a contract instead of to its wording.
        self.suggested: tuple[str, ...] = tuple(suggested)


class OutsideWorktree(MutationHarnessError):
    """A path the session was asked to touch does not live under its worktree (P-134)."""


class HarnessBusy(MutationHarnessError):
    """Another session already holds this worktree's lock."""


class NotAWorktree(MutationHarnessError):
    """The path given is not inside a git worktree, so no worktree root can be derived."""


class JournalUnreadable(MutationHarnessError):
    """The journal file exists but cannot be read as a list of entries.

    Distinct from "there is no journal", and from "the journal lists nothing outstanding". All
    three used to be spelled ``[]`` (P-174), so a corrupted journal read as a clean bill of
    health -- the one answer it must never give.
    """


class TreeNotPristine(MutationHarnessError):
    """The target file is already modified before the harness touched it.

    Reading a file that another writer has already mutated would back up *the mutant* as the
    pristine bytes and then faithfully "restore" the tree to it. This is the precondition that
    makes the backup mean what it says.
    """


# --------------------------------------------------------------------------------------------
# digests
# --------------------------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    """Digest of exact bytes. Nothing in this module compares text."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Digest of a file's bytes, read binary so no line ending is rewritten under us."""
    return sha256_bytes(Path(path).read_bytes())


# --------------------------------------------------------------------------------------------
# worktree derivation and containment
# --------------------------------------------------------------------------------------------


def _git(worktree: Path, args: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
    )


def resolve_worktree(start: Path) -> Path:
    """The git worktree root containing ``start``, from git itself.

    Deliberately *not* ``Path(__file__).resolve().parents[1]``. A draft of this module used that
    and so defaulted its target to whichever checkout the module happened to be imported from --
    the main tree, while the session owning the run was a linked worktree. ``--show-toplevel``
    returns the *linked worktree's* root, which is the tree the caller is actually in.

    There is no default: every entry point requires the worktree explicitly, because the failure
    this prevents is exactly an implicit one.
    """
    start = Path(start)
    probe = start if start.is_dir() else start.parent
    if not probe.is_dir():
        raise NotAWorktree(f"{start} does not exist, so no worktree can be derived from it")
    proc = _git(probe, ["rev-parse", "--show-toplevel"])
    if proc.returncode != 0:
        raise NotAWorktree(
            f"{probe} is not inside a git worktree: {proc.stderr.strip() or 'git failed'}"
        )
    return Path(proc.stdout.strip()).resolve()


def default_state_root() -> Path:
    """The parent directory session state sits under, before worktree derivation."""
    return Path(tempfile.gettempdir()) / "jnwb-mutation-harness"


def state_dir_for(worktree: Path, state_root: Path | None = None) -> Path:
    """The state directory for one worktree, derived from that worktree (P-134).

    Two worktrees must never share a directory: a backup written by one lane and restored by
    another is how a mutant reaches a commit. The resolved path is hashed as well as named, so
    two checkouts whose leaf directory happens to match still separate.

    Derived from the worktree but placed *outside* it. State inside the tree would show up as
    untracked files and make :meth:`MutationSession.verify_run_state` -- whose whole job is to
    notice a file the run left behind -- report the harness's own backups forever.
    """
    resolved = Path(worktree).resolve()
    tag = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:16]
    root = Path(state_root) if state_root is not None else default_state_root()
    return root / f"{resolved.name}-{tag}"


def ensure_inside_worktree(path: Path, worktree: Path) -> Path:
    """Resolve ``path`` and refuse it unless it is a path strictly inside ``worktree``.

    The guard is on the *resolved* paths, so ``..`` traversal and a symlink pointing out of the
    tree are refused rather than normalised into acceptance.
    """
    root = Path(worktree).resolve()
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = root / resolved
    resolved = resolved.resolve()
    if resolved == root:
        raise OutsideWorktree(f"{resolved} is the worktree root, not a file inside it")
    try:
        resolved.relative_to(root)
    except ValueError:
        raise OutsideWorktree(
            f"{resolved} is outside the worktree {root} this session owns. P-134: a restore "
            "driven by another lane's state writes into another lane's tree."
        ) from None
    return resolved


# --------------------------------------------------------------------------------------------
# node ids
# --------------------------------------------------------------------------------------------


def _normalize(node_id: str) -> str:
    """pytest prints node ids with the platform separator; comparisons use forward slashes."""
    return node_id.replace("\\", "/").strip()


def _posix_relative(path: str | Path) -> str:
    """A repository-relative path spelled the way ``git status --porcelain`` spells it.

    The ``./`` prefix is stripped as a prefix, not as a character class. ``lstrip("./")`` also
    eats the leading dot of a dotfile, so ``.github/workflows/ci.yml`` came back as
    ``github/workflows/ci.yml``; because both sides of the comparison pass through here the check
    still agreed with itself, and only the path it *named* in a refusal was wrong. A guard that
    reports the wrong path is a guard the next reader does not believe.
    """
    text = str(path).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text


def parse_porcelain(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split ``git status --porcelain`` into (tracked modifications, untracked paths).

    Only tracked paths feed the ``tree-declared`` refusal. An untracked file is caught by the
    entry/exit status comparison instead, and refusing one at entry would reject every tree that
    happens to hold a scratch file -- the gate nobody runs.
    """
    tracked: list[str] = []
    untracked: list[str] = []
    for raw in text.splitlines():
        if len(raw) < 4:
            continue
        code, rest = raw[:2], raw[3:].strip()
        # A rename prints "old -> new"; the new path is the one that is modified here.
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip('"')
        (untracked if code == "??" else tracked).append(_posix_relative(rest))
    return tuple(sorted(tracked)), tuple(sorted(untracked))


def _looks_like_node_id(token: str) -> bool:
    return ".py::" in token or token.endswith(".py")


def class_qualified_suggestions(worktree: Path, selector: Sequence[str]) -> tuple[str, ...]:
    """Rewrite ``file.py::name`` as ``file.py::Class::name`` where ``name`` is a method.

    This is the six-false-kills diagnostic. ``tests/t.py::test_m`` where ``test_m`` is a method
    of ``TestC`` collects nothing, and the resulting non-zero exit reads exactly like a kill.
    Parsing the file back is the difference between "collected no test" and "you meant
    ``tests/t.py::TestC::test_m``". It is returned as structured data on the exception rather
    than folded into the message, so a discriminator can assert the suggestion instead of its
    wording.
    """
    suggestions: list[str] = []
    for node in selector:
        parts = _normalize(node).split("::")
        if len(parts) != 2:
            continue
        rel, name = parts
        source_path = Path(worktree) / rel
        if not source_path.is_file():
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for klass in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            for method in klass.body:
                if isinstance(
                    method, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and method.name == name:
                    suggestions.append(f"{rel}::{klass.name}::{name}")
    return tuple(suggestions)


# --------------------------------------------------------------------------------------------
# the case
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MutationCase:
    """One mutation, the selector expected to catch it, and what makes the mutant wrong."""

    name: str
    path: str
    original: str
    replacement: str
    selector: tuple[str, ...]
    must_fail: tuple[str, ...]
    semantic_property: str
    #: True when this mutant is *known* not to be caught and the gap is on the record. The run
    #: then fails if the mutant is killed, which is the only way a measured hole stops being a
    #: narrated one (P-172).
    expected_survivor: bool = False
    #: Why the gap is tolerated, and where it is recorded. Required with ``expected_survivor``,
    #: refused without it: a reason attached to a case nobody expects to survive is a note that
    #: nothing checks.
    survivor_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "selector", tuple(self.selector))
        object.__setattr__(self, "must_fail", tuple(self.must_fail))
        if not self.name:
            raise MutationHarnessError("a case needs a name to report under")
        if not self.selector:
            raise MutationHarnessError(f"{self.name}: no selector, so nothing can be proven")
        if not self.must_fail:
            raise MutationHarnessError(
                f"{self.name}: must_fail is empty. A case that does not say which test has to "
                "fail can only assert that the run went red, which is how a fixture came to "
                "agree with the bug it was named after."
            )
        if not self.semantic_property:
            raise MutationHarnessError(
                f"{self.name}: state the semantic property the mutant breaks; "
                "'the tests go red' is not one."
            )
        if self.expected_survivor and not self.survivor_reason.strip():
            raise MutationHarnessError(
                f"{self.name}: an expected survivor must say why the gap is tolerated and where "
                "it is recorded. A survivor with no reason is the narration this field replaces."
            )
        if self.survivor_reason.strip() and not self.expected_survivor:
            raise MutationHarnessError(
                f"{self.name}: survivor_reason is set but expected_survivor is False, so the "
                "reason is a comment nothing asserts. Declare the expectation or drop the reason."
            )
        for token in (*self.selector, *self.must_fail):
            if not _looks_like_node_id(token):
                raise MutationHarnessError(
                    f"{self.name}: {token!r} is not a pytest node id. A bare test name collects "
                    "nothing, exits non-zero, and reads exactly like a kill -- six were reported "
                    "that way in 0.2.5. Write 'tests/test_x.py::TestClass::test_method'."
                )


#: Only :func:`prove_selector` holds this, so a :class:`SelectorProof` cannot be fabricated by a
#: caller that skipped the proof and wants a verdict anyway.
_PROOF_TOKEN = object()


@dataclass(frozen=True)
class SelectorProof:
    """Evidence that a selector names real tests and that they pass before anything is mutated.

    Constructing one requires the module-private token. ``pristine-collects`` is *not* re-checked
    here: :func:`prove_selector` is the single site for it, and a second copy here would be
    unreachable and so individually unkillable by mutation.
    """

    selector: tuple[str, ...]
    collected: tuple[str, ...]
    pristine_exit: int
    token: object = None

    def __post_init__(self) -> None:
        if self.token is not _PROOF_TOKEN:
            raise MutationHarnessError(
                "SelectorProof is produced by prove_selector() and nowhere else"
            )
        object.__setattr__(self, "selector", tuple(self.selector))
        object.__setattr__(self, "collected", tuple(self.collected))
        if self.pristine_exit != 0:
            raise ConditionFailed(
                "pristine-passes",
                f"{list(self.selector)} does not pass on the pristine tree (exit "
                f"{self.pristine_exit}); a later red run would prove nothing about the mutant.",
            )


@dataclass(frozen=True)
class Verdict:
    """The only object this module will call a result. It cannot exist without a proof."""

    case: str
    killed: bool
    proof: SelectorProof
    mutant_collected: tuple[str, ...]
    observed_failures: tuple[str, ...]
    collateral_failures: tuple[str, ...]
    pristine_digest: str
    mutant_digest: str
    restored_digest: str
    #: Carried from the case, so a report can be partitioned without holding the cases too.
    expected_survivor: bool = False
    survivor_reason: str = ""

    def __post_init__(self) -> None:
        if type(self.proof) is not SelectorProof:
            raise MutationHarnessError(
                f"{self.case}: a verdict requires a SelectorProof, got {type(self.proof)!r}. "
                "No verdict is emitted by a harness that has not first proven its own selectors."
            )
        object.__setattr__(self, "mutant_collected", tuple(self.mutant_collected))
        object.__setattr__(self, "observed_failures", tuple(self.observed_failures))
        object.__setattr__(self, "collateral_failures", tuple(self.collateral_failures))


@dataclass(frozen=True)
class Rejection:
    """A case that never reached a verdict, and why. Never counted as a kill."""

    case: str
    condition: str | None
    reason: str


#: The journal exists and parses. Its entry list means what it says.
JOURNAL_PRESENT = "present"
#: There is no journal file. Nothing is known about what a previous run left behind.
JOURNAL_ABSENT = "absent"
#: A journal file exists and does not parse. Nothing is known, and something is wrong.
JOURNAL_UNREADABLE = "unreadable"

JOURNAL_STATUSES: tuple[str, ...] = (JOURNAL_PRESENT, JOURNAL_ABSENT, JOURNAL_UNREADABLE)


@dataclass(frozen=True)
class JournalState:
    """What the journal says, and whether it is in a position to say anything (P-174).

    The defect this replaces: ``_read_journal`` answered ``[]`` for a missing file, an
    unparseable file, and a file recording nothing outstanding. "No mutant is open" and "I have
    no idea" were the same sentence, so a report that the journal was empty carried no
    information about the tree at all -- and a live mutant sat behind exactly that sentence for
    three days.
    """

    status: str
    entries: tuple[dict, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status not in JOURNAL_STATUSES:
            raise MutationHarnessError(
                f"{self.status!r} is not one of the journal statuses {JOURNAL_STATUSES}"
            )
        object.__setattr__(self, "entries", tuple(self.entries))
        if self.status != JOURNAL_PRESENT and self.entries:
            raise MutationHarnessError(
                f"a {self.status} journal cannot carry entries; it is the absence of an answer"
            )

    @property
    def is_known(self) -> bool:
        """True only when the journal is in a position to answer. Never true for an absence."""
        return self.status == JOURNAL_PRESENT

    def describe(self) -> str:
        if self.status == JOURNAL_ABSENT:
            return (
                "journal: UNKNOWN (no journal file). This says nothing about whether a mutant is "
                "live -- a harness that predates the journal leaves no record to be empty."
            )
        if self.status == JOURNAL_UNREADABLE:
            return f"journal: UNKNOWN (unreadable: {self.detail})"
        if not self.entries:
            return "journal: present, nothing outstanding"
        return f"journal: present, {len(self.entries)} mutation(s) outstanding"


@dataclass(frozen=True)
class TreeStatement:
    """What the worktree looked like at session entry, and what the caller said to expect.

    A run that cannot say which tree it ran against is not evidence about a tree. This is the
    second half of the P-174 repair: the journal says what *this* harness opened, and this says
    what is actually modified, so a mutant left by something else -- an older harness, a killed
    editor, a hand edit -- is named rather than inherited.
    """

    head: str
    tracked_modifications: tuple[str, ...] = ()
    declared: tuple[str, ...] = ()
    journal: JournalState | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracked_modifications", tuple(self.tracked_modifications))
        object.__setattr__(self, "declared", tuple(self.declared))

    @property
    def undeclared(self) -> tuple[str, ...]:
        return tuple(p for p in self.tracked_modifications if p not in self.declared)

    def describe(self) -> str:
        lines = [
            f"tree: {self.head}",
            f"tracked modifications: {list(self.tracked_modifications) or 'none'}",
            f"declared: {list(self.declared) or 'none'}",
        ]
        if self.journal is not None:
            lines.append(self.journal.describe())
        return "\n".join(lines)


@dataclass
class SuiteReport:
    verdicts: list[Verdict] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def killed(self) -> list[Verdict]:
        """Mutants caught that were meant to be caught."""
        return [v for v in self.verdicts if v.killed and not v.expected_survivor]

    @property
    def survived(self) -> list[Verdict]:
        """Mutants nothing caught, and nobody said so in advance. Failures."""
        return [v for v in self.verdicts if not v.killed and not v.expected_survivor]

    @property
    def expected_survivors(self) -> list[Verdict]:
        """Declared gaps that are still gaps. The record agrees with the measurement."""
        return [v for v in self.verdicts if not v.killed and v.expected_survivor]

    @property
    def unexpected_kills(self) -> list[Verdict]:
        """Declared gaps that have closed. A failure, and the only kind that is good news.

        Without this the record rots silently: someone adds the missing assertion, the gap is
        gone, and the note saying it exists goes on saying so forever.
        """
        return [v for v in self.verdicts if v.killed and v.expected_survivor]

    def summary(self) -> str:
        lines = [
            f"killed:            {len(self.killed)}",
            f"survived:          {len(self.survived)}",
            f"expected survivor: {len(self.expected_survivors)}  (declared gaps, still open)",
            f"unexpected kill:   {len(self.unexpected_kills)}  (declared gaps that closed)",
            f"rejected:          {len(self.rejections)}  (never reached a verdict)",
        ]
        for v in self.survived:
            lines.append(f"  SURVIVED {v.case}")
        for v in self.expected_survivors:
            lines.append(f"  EXPECTED-SURVIVOR {v.case}: {v.survivor_reason}")
        for v in self.unexpected_kills:
            lines.append(
                f"  UNEXPECTED-KILL {v.case}: recorded as a gap, but "
                f"{list(v.observed_failures)} caught it. Update the record: {v.survivor_reason}"
            )
        for r in self.rejections:
            lines.append(f"  REJECTED {r.case}: [{r.condition}] {r.reason}")
        return "\n".join(lines)

    def clean(self) -> bool:
        return not self.survived and not self.rejections and not self.unexpected_kills


# --------------------------------------------------------------------------------------------
# mutation and restore
# --------------------------------------------------------------------------------------------


def apply_mutation(data: bytes, case: MutationCase) -> bytes:
    """Apply the case's substitution to ``data``, enforcing ``lands-once`` and ``source-differs``.

    Pure, and on bytes. A text-mode round trip rewrites line endings on Windows, which both
    corrupts the file and makes an anchor that should match miss -- and the failure then reads as
    "the text is not there" rather than "the harness is broken".
    """
    original = case.original.encode("utf-8")
    replacement = case.replacement.encode("utf-8")
    count = data.count(original)
    if count != 1:
        hint = ""
        if count == 0 and b"\r\n" in data:
            hint = (
                " The file is CRLF and the anchor is not; an anchor spanning a line break will "
                "never match. Compare bytes."
            )
        raise ConditionFailed(
            "lands-once",
            f"{case.name}: the anchor occurs {count} times in {case.path}, not once. A "
            "substitution that lands zero times silently applies nothing, and one that lands "
            f"several times mutates more than the case describes.{hint}",
        )
    mutated = data.replace(original, replacement, 1)
    if mutated == data:
        raise ConditionFailed(
            "source-differs",
            f"{case.name}: the replacement leaves {case.path} byte-identical, so the 'mutant' is "
            "the pristine tree and any verdict about it is a verdict about nothing.",
        )
    return mutated


def restore_and_verify(path: Path, pristine: bytes, pristine_digest: str) -> str:
    """Write ``pristine`` back and prove in bytes that the file is what it was.

    Called after *every* mutant, from a ``finally``. A harness that verified once at the end has
    already left live mutants behind in this repository.
    """
    path = Path(path)
    path.write_bytes(pristine)
    restored = sha256_file(path)
    if restored != pristine_digest:
        raise ConditionFailed(
            "restore-byte-exact",
            f"{path} hashes to {restored} after restore, expected {pristine_digest}. The tree is "
            "still modified; do not trust any verdict from this run.",
        )
    return restored


# --------------------------------------------------------------------------------------------
# pytest
# --------------------------------------------------------------------------------------------


def _pytest(worktree: Path, args: Sequence[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # No .pyc and no .pytest_cache: the harness must not leave a file behind in a tree it
    # promised to return byte-identical.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        timeout=PYTEST_TIMEOUT_S,
        env=env,
    )


def collect_selector(worktree: Path, selector: Sequence[str]) -> tuple[tuple[str, ...], str]:
    """Node ids the selector actually collects, plus the raw output for a diagnostic."""
    proc = _pytest(worktree, ["--collect-only", "-q", *selector])
    output = proc.stdout + proc.stderr
    collected = []
    for raw in proc.stdout.splitlines():
        line = _normalize(raw)
        if not line or line.startswith(("ERROR", "FAILED", "E ", "!!!")):
            continue
        if ".py::" in line and " " not in line:
            collected.append(line)
    return tuple(collected), output


def run_selector(
    worktree: Path, selector: Sequence[str]
) -> tuple[int, tuple[str, ...], tuple[str, ...], str]:
    """Run the selector; return (exit code, FAILED node ids, ERROR node ids, output).

    ``FAILED`` and ``ERROR`` are kept apart on purpose. An ``ERROR`` means collection, setup or
    teardown blew up and the test body never executed, so it is not an observation of the
    semantic property -- it is the "red for the wrong reason" defect wearing a red hat.
    """
    proc = _pytest(worktree, ["-q", "--tb=no", "-rfE", *selector])
    failed: list[str] = []
    errored: list[str] = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        for prefix, bucket in (("FAILED ", failed), ("ERROR ", errored)):
            if line.startswith(prefix):
                bucket.append(_normalize(line[len(prefix):].split(" - ", 1)[0]))
    return proc.returncode, tuple(failed), tuple(errored), proc.stdout + proc.stderr


def prove_selector(worktree: Path, selector: Sequence[str]) -> SelectorProof:
    """Prove a selector collects and passes on the pristine tree, before anything is mutated.

    This is the whole accept clause. A harness that has not done this cannot tell a kill from a
    typo, because an exit code is the only thing it has to go on.
    """
    selector = tuple(selector)
    collected, collect_output = collect_selector(worktree, selector)
    if not collected:
        suggested = class_qualified_suggestions(worktree, selector)
        raise ConditionFailed(
            "pristine-collects",
            f"{list(selector)} collected no test under {worktree}. "
            + (f"Did you mean {list(suggested)}? " if suggested else "")
            + "pytest exits non-zero on an empty selection, so this would have been counted as a "
            "kill. Collector said: " + " | ".join(collect_output.splitlines()[-3:]),
            suggested=suggested,
        )
    exit_code, failed, errored, run_output = run_selector(worktree, selector)
    try:
        return SelectorProof(
            selector=selector,
            collected=collected,
            pristine_exit=exit_code,
            token=_PROOF_TOKEN,
        )
    except ConditionFailed as exc:
        raise ConditionFailed(
            exc.condition,
            f"{exc.detail} Failed {list(failed)}; errored {list(errored)}; tail: "
            + " | ".join(run_output.splitlines()[-3:]),
        ) from exc


# --------------------------------------------------------------------------------------------
# the session
# --------------------------------------------------------------------------------------------


class MutationSession:
    """One worktree, one lock, one journal, one set of digests verified on the way out.

    ``worktree`` is required. A default would be the very defect this class exists to prevent:
    a draft defaulted to the checkout the module was imported from and pointed a linked
    worktree's run at the main tree.
    """

    def __init__(
        self,
        worktree: Path,
        state_root: Path | None = None,
        declared_modifications: Sequence[str] = (),
    ) -> None:
        self.worktree = Path(worktree).resolve()
        self.state_dir = state_dir_for(self.worktree, state_root)
        self.backups = self.state_dir / "backups"
        self.journal = self.state_dir / "journal.json"
        self.digests: dict[Path, str] = {}
        self.report = SuiteReport()
        self.entry_status: str | None = None
        #: Tracked paths the caller says it meant to have modified before the run. Empty by
        #: default, which requires a clean tree -- the check has to be told nothing to be usable,
        #: so it does not become the gate that must be handed an ignore list.
        self.declared_modifications: tuple[str, ...] = tuple(
            _posix_relative(p) for p in declared_modifications
        )
        self.tree_statement: TreeStatement | None = None
        #: The journal as the session found it. Read before the replay, because the replay
        #: rewrites the journal as ``[]`` and would turn "there was no journal" into "present,
        #: nothing outstanding" in the statement of the tree.
        self.journal_at_entry: JournalState | None = None
        self._lock_handle = None

    # -- lifecycle -------------------------------------------------------------------------

    def __enter__(self) -> "MutationSession":
        self.backups.mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        try:
            # Replay first: a mutant this harness opened and was killed holding is *this*
            # session's to restore, and would otherwise be reported as somebody's surprise.
            self.journal_at_entry = self.read_journal()
            self.replay_journal()
            self.tree_statement = self.state_tree()
            self.entry_status = self._porcelain()
        except BaseException:
            self._release_lock()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.verify_run_state()
        finally:
            self._release_lock()
        return False

    def _acquire_lock(self) -> None:
        """An OS-level lock, so a killed process releases it and no staleness heuristic is needed."""
        path = self.state_dir / "lock"
        handle = open(path, "a+b")
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise HarnessBusy(
                f"another mutation session holds {path}. Two sessions in one worktree restore "
                "over each other's backups and leave a mutant behind."
            ) from None
        self._lock_handle = handle

    def _release_lock(self) -> None:
        handle, self._lock_handle = self._lock_handle, None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            handle.close()

    # -- git ------------------------------------------------------------------------------

    def _porcelain(self) -> str:
        proc = _git(self.worktree, ["status", "--porcelain", "--untracked-files=all"])
        if proc.returncode != 0:
            raise NotAWorktree(
                f"git status failed in {self.worktree}: {proc.stderr.strip() or 'git failed'}"
            )
        return "\n".join(sorted(proc.stdout.splitlines()))

    def require_pristine(self, target: Path) -> None:
        """Refuse a target another writer has already modified.

        Without this, the harness reads a mutant, records it as the pristine bytes, and restores
        the tree to the mutant -- with a byte-exact receipt saying it did the right thing.
        """
        rel = target.relative_to(self.worktree).as_posix()
        proc = _git(self.worktree, ["status", "--porcelain", "--", rel])
        if proc.returncode != 0:
            raise NotAWorktree(
                f"git status failed for {rel} in {self.worktree}: "
                f"{proc.stderr.strip() or 'git failed'}"
            )
        if proc.stdout.strip():
            raise TreeNotPristine(
                f"{rel} is already modified ({proc.stdout.strip()!r}) before this session touched "
                "it. Its current bytes would be recorded as pristine and restored as such. "
                "Commit, revert, or hand the harness a clean tree."
            )

    # -- journal ---------------------------------------------------------------------------

    def read_journal(self) -> JournalState:
        """What the journal is able to say -- which may be nothing, and says so (P-174).

        Three answers, never one. An absent journal is *unknown*, not empty: the 0.2.5 harness
        predates this file and journals nothing, so "all four journals read ``[]``" was true and
        carried no information. An unparseable journal is unknown too, and additionally wrong.
        """
        if not self.journal.is_file():
            return JournalState(JOURNAL_ABSENT, detail=f"{self.journal} does not exist")
        try:
            loaded = json.loads(self.journal.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            return JournalState(JOURNAL_UNREADABLE, detail=f"{type(exc).__name__}: {exc}")
        if not isinstance(loaded, list) or not all(isinstance(e, dict) for e in loaded):
            return JournalState(
                JOURNAL_UNREADABLE,
                detail=f"expected a list of objects, got {type(loaded).__name__}",
            )
        return JournalState(JOURNAL_PRESENT, entries=tuple(loaded))

    def _journal_entries(self) -> list[dict]:
        """The outstanding entries, refusing to invent an empty list for an unknown journal."""
        state = self.read_journal()
        if state.status == JOURNAL_UNREADABLE:
            raise JournalUnreadable(
                f"{self.journal} exists and cannot be read ({state.detail}). It may record a live "
                "mutant. Treating it as empty is the P-174 defect: restore the tree from version "
                "control and delete the journal deliberately."
            )
        return list(state.entries)

    def _write_journal(self, entries: list[dict]) -> None:
        self.journal.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _open_entry(self, path: Path, digest: str, pristine: bytes) -> None:
        backup = self.backups / f"{digest}.bin"
        if not backup.is_file():
            backup.write_bytes(pristine)
        entries = self._journal_entries()
        entries.append({"path": str(path), "digest": digest, "backup": str(backup)})
        self._write_journal(entries)

    def _close_entry(self, path: Path, digest: str) -> None:
        entries = [
            e
            for e in self._journal_entries()
            if not (e.get("path") == str(path) and e.get("digest") == digest)
        ]
        self._write_journal(entries)

    def replay_journal(self) -> list[str]:
        """Restore anything a previous session was killed in the middle of mutating.

        The backups are content-addressed, so the replay proves itself: the bytes written back
        must hash to the name they were stored under.
        """
        restored = []
        for entry in self._journal_entries():
            path = ensure_inside_worktree(Path(entry["path"]), self.worktree)
            backup = Path(entry["backup"])
            digest = entry["digest"]
            if not backup.is_file():
                raise ConditionFailed(
                    "restore-byte-exact",
                    f"the journal says {path} was left mutated and its backup {backup} is gone; "
                    "restore it from version control before running again",
                )
            pristine = backup.read_bytes()
            if sha256_bytes(pristine) != digest:
                raise ConditionFailed(
                    "restore-byte-exact",
                    f"backup {backup} does not hash to {digest}; it is not the pristine bytes",
                )
            if sha256_file(path) != digest:
                restore_and_verify(path, pristine, digest)
                restored.append(str(path))
        self._write_journal([])
        return restored

    # -- the tree this run ran against -------------------------------------------------------

    def state_tree(self) -> TreeStatement:
        """Say which tree the run is about, and refuse an undeclared modification (P-174).

        The journal can only speak for mutations *this* harness opened. A mutant left by a
        different harness, an interrupted editor or a hand edit is outside its knowledge, and the
        one that mattered suppressed the very check that would have failed on it -- so the suite
        could not speak for it either. ``git status`` can, in one second, and it is the only
        reader here that does not depend on the mutant leaving something broken.

        Only *tracked* modifications refuse. The declared set is empty by default: a clean tree
        needs to declare nothing, so this does not become a gate that must be handed a list of
        things to ignore.
        """
        head = _git(self.worktree, ["rev-parse", "HEAD"])
        proc = _git(self.worktree, ["status", "--porcelain", "--untracked-files=all"])
        if proc.returncode != 0:
            raise NotAWorktree(
                f"git status failed in {self.worktree}: {proc.stderr.strip() or 'git failed'}"
            )
        tracked, _untracked = parse_porcelain(proc.stdout)
        statement = TreeStatement(
            head=head.stdout.strip() if head.returncode == 0 else "unknown",
            tracked_modifications=tracked,
            declared=self.declared_modifications,
            journal=(
                self.journal_at_entry if self.journal_at_entry is not None else self.read_journal()
            ),
        )
        if statement.undeclared:
            raise ConditionFailed(
                "tree-declared",
                "this run cannot say which tree it ran against: "
                f"{list(statement.undeclared)} are modified in {self.worktree} and the caller did "
                f"not declare them. Declared: {list(statement.declared) or 'none'}. A mutant that "
                "suppresses a check cannot be caught by the check it suppresses, so a surprise "
                "here is refused rather than run over.\n" + statement.describe(),
            )
        return statement

    # -- whole-run digest --------------------------------------------------------------------

    def verify_run_state(self) -> None:
        """Prove the run left nothing behind: every touched file, and the tree as a whole.

        Two sub-checks, each individually killable. A file already dirty at entry and changed
        again is caught only by the digests; a *new* untracked file is caught only by the status
        comparison, because the digests do not know it exists.
        """
        drifted = [
            f"{path}: {sha256_file(path)} != {digest}"
            for path, digest in self.digests.items()
            if sha256_file(path) != digest
        ]
        if drifted:
            raise ConditionFailed(
                "run-digest-clean",
                "files this session touched do not match their pristine digests: "
                + "; ".join(drifted),
            )
        if self.entry_status is not None:
            exit_status = self._porcelain()
            if exit_status != self.entry_status:
                raise ConditionFailed(
                    "run-digest-clean",
                    "the worktree is not as the session found it. Entry:\n"
                    f"{self.entry_status or '(clean)'}\nExit:\n{exit_status or '(clean)'}",
                )

    # -- the case ----------------------------------------------------------------------------

    def run_case(self, case: MutationCase) -> Verdict:
        """Enforce all eight conditions, in order, and return the only kind of result there is."""
        target = ensure_inside_worktree(Path(case.path), self.worktree)
        self.require_pristine(target)
        pristine = target.read_bytes()
        pristine_digest = sha256_bytes(pristine)
        self.digests.setdefault(target, pristine_digest)

        # 1 and 2, before anything is written: an unproven selector is rejected here, so no
        # Verdict for this case is ever constructed and the tree is never touched.
        proof = prove_selector(self.worktree, case.selector)

        # 3 and 4, in memory, before the write.
        mutated = apply_mutation(pristine, case)
        mutant_digest = sha256_bytes(mutated)

        self._open_entry(target, pristine_digest, pristine)
        try:
            target.write_bytes(mutated)

            # 5. Red because the module stopped importing is not red because the mutant is wrong.
            mutant_collected, collect_output = collect_selector(self.worktree, case.selector)
            missing = [n for n in case.must_fail if n not in mutant_collected]
            if missing:
                raise ConditionFailed(
                    "mutant-collects",
                    f"{case.name}: {missing} are not collected with the mutant in place, so the "
                    "run cannot observe the mutant at all. Collector said: "
                    + " | ".join(collect_output.splitlines()[-3:]),
                )

            # 6. Observed, not merely red.
            exit_code, failed, errored, run_output = run_selector(self.worktree, case.selector)
            observed = [n for n in case.must_fail if n in failed]
            unobserved = [n for n in case.must_fail if n not in failed]
            # Errored *and not also failed*: a test can fail in its body and then error again in
            # teardown, and that first failure is a real observation of the mutant.
            bad_errors = [n for n in case.must_fail if n in errored and n not in failed]
            if bad_errors:
                raise ConditionFailed(
                    "mutant-observed",
                    f"{case.name}: {bad_errors} ERRORed rather than FAILED, so the test body "
                    "never ran and nothing observed the mutant. An error is not a kill. Tail: "
                    + " | ".join(run_output.splitlines()[-3:]),
                )
            if exit_code != 0 and unobserved:
                raise ConditionFailed(
                    "mutant-observed",
                    f"{case.name}: the run went red but {unobserved} passed. Something else "
                    f"failed ({list(failed)}), so this is not evidence that the selector catches "
                    "the mutant. Tail: " + " | ".join(run_output.splitlines()[-3:]),
                )
            killed = not unobserved
            collateral = [n for n in failed if n not in case.must_fail]
        finally:
            # 7. After every mutant, not once at the end.
            restored_digest = restore_and_verify(target, pristine, pristine_digest)
            self._close_entry(target, pristine_digest)

        verdict = Verdict(
            case=case.name,
            killed=killed,
            proof=proof,
            mutant_collected=mutant_collected,
            observed_failures=tuple(observed),
            collateral_failures=tuple(collateral),
            pristine_digest=pristine_digest,
            mutant_digest=mutant_digest,
            restored_digest=restored_digest,
            expected_survivor=case.expected_survivor,
            survivor_reason=case.survivor_reason,
        )
        self.report.verdicts.append(verdict)
        return verdict

    def run_suite(self, cases: Sequence[MutationCase]) -> SuiteReport:
        """Run every case. One refused case does not hide the others.

        A gate that aborts leaves every later gate unrun and looking fine; that was measured on
        the harness gate, and it would be the same mistake here.
        """
        for case in cases:
            try:
                self.run_case(case)
            except MutationHarnessError as exc:
                self.report.rejections.append(
                    Rejection(
                        case=case.name,
                        condition=getattr(exc, "condition", None),
                        reason=str(exc),
                    )
                )
        return self.report


def run_cases(
    cases: Sequence[MutationCase],
    worktree: Path,
    state_root: Path | None = None,
    declared_modifications: Sequence[str] = (),
) -> SuiteReport:
    """One session, every case, digests verified on the way out. ``worktree`` is required."""
    with MutationSession(worktree, state_root, declared_modifications) as session:
        return session.run_suite(cases)


def load_cases(path: Path) -> list[MutationCase]:
    """Read cases from JSON. Each object carries exactly the fields of :class:`MutationCase`."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        MutationCase(
            name=item["name"],
            path=item["path"],
            original=item["original"],
            replacement=item["replacement"],
            selector=tuple(item["selector"]),
            must_fail=tuple(item["must_fail"]),
            semantic_property=item["semantic_property"],
            expected_survivor=bool(item.get("expected_survivor", False)),
            survivor_reason=item.get("survivor_reason", ""),
        )
        for item in raw
    ]


# --------------------------------------------------------------------------------------------
# the recorded gaps
# --------------------------------------------------------------------------------------------

#: Coverage gaps that were **measured**, not guessed, and are on the record rather than in prose.
#:
#: Each is a real mutation of library source that the test *named for the property* does not
#: catch. Declaring them here is what P-172 asks for: the gap is asserted to still be a gap, so
#: closing one without updating the record fails the run as an ``UNEXPECTED-KILL`` instead of
#: leaving a note that quietly stops being true.
#:
#: These are not run by the fast suite -- a mutation of ``jnwb/`` has to happen in an isolated
#: clone, because the suite runs under ``-n auto`` and a mutant in the shared checkout is visible
#: to every other worker. ``tests/test_mutation_harness_validity.py`` holds them to what can be
#: checked without mutating anything: the anchor still lands exactly once, and every node id they
#: name still exists in the file it names.
KNOWN_GAPS: tuple[MutationCase, ...] = (
    MutationCase(
        name="P-171 | density-versus-power is named by a test that measures a ratio",
        path="jnwb/spectral.py",
        original="        return signal.welch(trace, fs=fs, nperseg=nperseg)\n",
        replacement=(
            '        return signal.welch(trace, fs=fs, nperseg=nperseg, scaling="spectrum")\n'
        ),
        selector=(
            "tests/test_spectral.py::TestBandPowerEstimandIsDocumented"
            "::test_the_value_is_a_density_not_an_integrated_power",
        ),
        must_fail=(
            "tests/test_spectral.py::TestBandPowerEstimandIsDocumented"
            "::test_the_value_is_a_density_not_an_integrated_power",
        ),
        semantic_property=(
            "band_power returns a spectral density in units^2/Hz, not an integrated power in "
            "units^2 per bin"
        ),
        expected_survivor=True,
        survivor_reason=(
            "P-171. The test compares narrow/wide, a *ratio* of two means, and Welch's scaling "
            "enters both sides as the same constant factor -- so it detects the bandwidth error "
            "it is named for and not the scaling error. A P-37 proxy inside an existing test, "
            "found by measurement. The mutation class itself is covered: "
            "tests/test_semantic_mutation_classes.py kills it via "
            "test_band_power_is_the_mean_psd_over_the_band. The naming is what is not covered."
        ),
    ),
)


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("cases", type=Path, nargs="?", help="JSON file of mutation cases")
    parser.add_argument(
        "--known-gaps",
        action="store_true",
        help="run the recorded KNOWN_GAPS instead of a case file. A gap that has closed is an "
        "UNEXPECTED-KILL and fails the run, so the record cannot go on claiming a gap that is gone.",
    )
    parser.add_argument(
        "--worktree",
        type=Path,
        required=True,
        help="the worktree to mutate. Required: there is no default, because defaulting to the "
        "checkout this module was imported from is the defect this harness exists to prevent.",
    )
    parser.add_argument(
        "--declare-modified",
        action="append",
        default=[],
        metavar="PATH",
        help="a tracked path you meant to have modified before the run. Anything else modified "
        "refuses the run: a mutant that suppresses a check cannot be caught by that check.",
    )
    args = parser.parse_args(argv)
    if args.known_gaps == (args.cases is not None):
        parser.error("give exactly one of a case file or --known-gaps")
    cases = list(KNOWN_GAPS) if args.known_gaps else load_cases(args.cases)

    worktree = resolve_worktree(args.worktree)
    try:
        with MutationSession(worktree, declared_modifications=args.declare_modified) as session:
            # Stated before the cases run, so a refusal further down is still attributable to a
            # named tree rather than to whatever the checkout happened to hold.
            print(session.tree_statement.describe() if session.tree_statement else "tree: unknown")
            report = session.run_suite(cases)
    except MutationHarnessError as exc:
        print(f"REFUSED: {exc}")
        return 2
    print(report.summary())
    return 0 if report.clean() else 1


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess, not in-process
    raise SystemExit(main())
