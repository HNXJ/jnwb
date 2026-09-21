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

The eight conditions in :data:`CONDITIONS` are enforced here, each at exactly one site, and each
raises a :class:`ConditionFailed` carrying its own ``condition`` name. A discriminator can drive a
scenario and assert *which* guard stopped it, which is what makes each guard individually
killable by mutation. A guard duplicated for safety is a guard that no test can prove is
load-bearing.
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

#: The per-case conditions, in the order they are enforced. A verdict exists only if all eight
#: held. These are not labels: each is the ``condition`` attribute of a real
#: :class:`ConditionFailed`, so "every condition is reachable" is a checkable statement about
#: behaviour rather than a claim about a docstring.
CONDITIONS: tuple[str, ...] = (
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


@dataclass
class SuiteReport:
    verdicts: list[Verdict] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def killed(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.killed]

    @property
    def survived(self) -> list[Verdict]:
        return [v for v in self.verdicts if not v.killed]

    def summary(self) -> str:
        lines = [
            f"killed:    {len(self.killed)}",
            f"survived:  {len(self.survived)}",
            f"rejected:  {len(self.rejections)}  (never reached a verdict)",
        ]
        for v in self.survived:
            lines.append(f"  SURVIVED {v.case}")
        for r in self.rejections:
            lines.append(f"  REJECTED {r.case}: [{r.condition}] {r.reason}")
        return "\n".join(lines)

    def clean(self) -> bool:
        return not self.survived and not self.rejections


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

    def __init__(self, worktree: Path, state_root: Path | None = None) -> None:
        self.worktree = Path(worktree).resolve()
        self.state_dir = state_dir_for(self.worktree, state_root)
        self.backups = self.state_dir / "backups"
        self.journal = self.state_dir / "journal.json"
        self.digests: dict[Path, str] = {}
        self.report = SuiteReport()
        self.entry_status: str | None = None
        self._lock_handle = None

    # -- lifecycle -------------------------------------------------------------------------

    def __enter__(self) -> "MutationSession":
        self.backups.mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        try:
            self.replay_journal()
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

    def _read_journal(self) -> list[dict]:
        if not self.journal.is_file():
            return []
        try:
            return json.loads(self.journal.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return []

    def _write_journal(self, entries: list[dict]) -> None:
        self.journal.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _open_entry(self, path: Path, digest: str, pristine: bytes) -> None:
        backup = self.backups / f"{digest}.bin"
        if not backup.is_file():
            backup.write_bytes(pristine)
        entries = self._read_journal()
        entries.append({"path": str(path), "digest": digest, "backup": str(backup)})
        self._write_journal(entries)

    def _close_entry(self, path: Path, digest: str) -> None:
        entries = [
            e
            for e in self._read_journal()
            if not (e.get("path") == str(path) and e.get("digest") == digest)
        ]
        self._write_journal(entries)

    def replay_journal(self) -> list[str]:
        """Restore anything a previous session was killed in the middle of mutating.

        The backups are content-addressed, so the replay proves itself: the bytes written back
        must hash to the name they were stored under.
        """
        restored = []
        for entry in self._read_journal():
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
) -> SuiteReport:
    """One session, every case, digests verified on the way out. ``worktree`` is required."""
    with MutationSession(worktree, state_root) as session:
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
        )
        for item in raw
    ]


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("cases", type=Path, help="JSON file of mutation cases")
    parser.add_argument(
        "--worktree",
        type=Path,
        required=True,
        help="the worktree to mutate. Required: there is no default, because defaulting to the "
        "checkout this module was imported from is the defect this harness exists to prevent.",
    )
    args = parser.parse_args(argv)

    worktree = resolve_worktree(args.worktree)
    report = run_cases(load_cases(args.cases), worktree=worktree)
    print(report.summary())
    return 0 if report.clean() else 1


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess, not in-process
    raise SystemExit(main())
