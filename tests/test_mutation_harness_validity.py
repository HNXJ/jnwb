"""Discriminators for the mutation harness: the guards that stop it reporting a false kill.

Each test here drives a scenario the harness must refuse and asserts *which* guard refused it,
by ``ConditionFailed.condition`` rather than by message text. Asserting the condition name is
what makes each guard individually killable: if a guard is deleted, the scenario usually still
raises something, so a test that only checked "it raised" would pass over the hole.

What would make these pass while the rule they name is violated, and what is done about it:

* A fixture repository without a real class-based test method would make the six-false-kills
  probe vacuous -- an unqualified selector would collect nothing for the boring reason that the
  test does not exist. :func:`_write_fixture_repo` builds ``TestScale`` with two real methods,
  and :func:`test_the_fixture_really_has_a_class_based_test_method` asserts the shape the probe
  depends on before any probe relies on it. A ``nested-clone`` fixture that built an empty
  ``.git`` once agreed with the defect it was named after and passed as a discriminator.
* A fixture repository that was not a git worktree would make the containment and
  already-modified guards untestable, and they would silently never fire. The fixture runs
  ``git init`` and commits, and :func:`test_the_fixture_is_a_real_git_worktree` asserts git
  itself reports the root.
* A run that merely went red would let a mutation be credited to a test that never observed it.
  :func:`test_a_red_run_whose_named_test_passed_is_not_a_kill` drives exactly that.
* Two guards for one condition would leave each individually unkillable, so each condition has
  exactly one enforcement site; :func:`test_every_declared_condition_has_an_enforcement_site`
  checks that against the source rather than against this docstring.
* A probe planting a mutant the suite can see would prove the suite works, not that the tree
  statement catches what the suite cannot. The P-174 mutant broke nothing, so
  :func:`test_the_planted_mutant_really_is_the_silent_shape` runs the fixture's own tests with
  the mutant in place and requires them to still pass before the refusal is probed at all.
* Asserting that a missing journal is "unknown" and an empty one is "empty" could both pass while
  the two still gave the same answer, so
  :func:`test_a_missing_and_an_empty_journal_do_not_give_the_same_answer` compares them directly.
* ``expected_survivor`` could be satisfied by making every survivor acceptable, so each of the
  three outcomes -- declared gap still open, declared gap closed, undeclared survivor -- has its
  own test and the middle one is a *failure*.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended: prepending would put this checkout's packages ahead of an installed
# copy and silently redirect a wheel-qualification run back to the source tree.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.mutation_harness import (  # noqa: E402
    CONDITIONS,
    JOURNAL_ABSENT,
    JOURNAL_PRESENT,
    JOURNAL_UNREADABLE,
    KNOWN_GAPS,
    ConditionFailed,
    HarnessBusy,
    JournalState,
    JournalUnreadable,
    MutationCase,
    MutationHarnessError,
    MutationSession,
    NotAWorktree,
    OutsideWorktree,
    SelectorProof,
    TreeNotPristine,
    Verdict,
    apply_mutation,
    default_state_root,
    parse_porcelain,
    resolve_worktree,
    restore_and_verify,
    sha256_bytes,
    sha256_file,
    state_dir_for,
)

HARNESS_SOURCE = REPO_ROOT / "scripts" / "mutation_harness.py"

CALC_SOURCE = """def mean(values):
    return sum(values) / len(values)


def scale(values, factor):
    return [v * factor for v in values]
"""

CALC_TESTS = '''import pytest

from pkg.calc import mean, scale


def test_mean_is_the_average():
    assert mean([1, 2, 3]) == 2


@pytest.fixture
def scaled():
    return scale([1, 2], 2)


def test_scaled_fixture(scaled):
    assert scaled == [2, 4]


class TestScale:
    def test_scale_multiplies(self):
        assert scale([1, 2], 3) == [3, 6]

    def test_scale_by_one_is_identity(self):
        assert scale([4, 5], 1) == [4, 5]
'''

BROKEN_TESTS = '''def test_broken_is_red_on_purpose():
    assert False, "exists so that pristine-passes has something real to refuse"
'''

PYTEST_INI = """[pytest]
pythonpath = .
testpaths = tests
"""

#: The mean's body, once, in :data:`CALC_SOURCE`.
MEAN_BODY = "return sum(values) / len(values)"
#: The scale's body, once, in :data:`CALC_SOURCE`.
SCALE_BODY = "return [v * factor for v in values]"

CALC_REL = "pkg/calc.py"
T_MEAN = "tests/test_calc.py::test_mean_is_the_average"
T_FIXTURE = "tests/test_calc.py::test_scaled_fixture"
T_MULTIPLIES = "tests/test_calc.py::TestScale::test_scale_multiplies"
T_IDENTITY = "tests/test_calc.py::TestScale::test_scale_by_one_is_identity"
T_BROKEN = "tests/test_broken.py::test_broken_is_red_on_purpose"
#: The same method named without its class: collects nothing, exits non-zero, reads as a kill.
T_MULTIPLIES_UNQUALIFIED = "tests/test_calc.py::test_scale_multiplies"


def _write(path: Path, text: str) -> None:
    """Write LF bytes. Text mode would rewrite line endings and move every byte anchor."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _write_fixture_repo(root: Path) -> Path:
    """Build a real git worktree holding a real package and real class-based tests.

    Every guard under test reads this tree through git or through pytest, so a fixture that only
    looked like a repository would make the guards pass by never firing.
    """
    _write(root / "pytest.ini", PYTEST_INI)
    _write(root / CALC_REL, CALC_SOURCE)
    _write(root / "tests" / "test_calc.py", CALC_TESTS)
    _write(root / "tests" / "test_broken.py", BROKEN_TESTS)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, timeout=120)
    for key, value in (("user.email", "harness@example.invalid"), ("user.name", "Harness")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True, timeout=120)
    # Exact paths, never `git add -A`: the habit is the point even in a throwaway tree.
    subprocess.run(
        ["git", "add", "pytest.ini", CALC_REL, "tests/test_calc.py", "tests/test_broken.py"],
        cwd=root,
        check=True,
        timeout=120,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"], cwd=root, check=True, timeout=120
    )
    return resolve_worktree(root)


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One built tree for the whole module. Every case restores it, and each case re-checks."""
    return _write_fixture_repo(tmp_path_factory.mktemp("harness_fixture"))


@pytest.fixture
def session(fixture_repo: Path, tmp_path: Path):
    """A session over the fixture tree with state in this test's own directory."""
    with MutationSession(fixture_repo, state_root=tmp_path / "state") as active:
        yield active


def _case(**overrides) -> MutationCase:
    base = dict(
        name="mean-becomes-sum",
        path=CALC_REL,
        original=MEAN_BODY,
        replacement="return sum(values)",
        selector=(T_MEAN,),
        must_fail=(T_MEAN,),
        semantic_property="the mean of a sample is its sum divided by its count",
    )
    base.update(overrides)
    return MutationCase(**base)


# ---------------------------------------------------------------------------------------------
# The fixture builds the case it is named after
# ---------------------------------------------------------------------------------------------


def test_the_fixture_really_has_a_class_based_test_method(fixture_repo: Path) -> None:
    """The six-false-kills probe is vacuous unless the method really lives inside a class."""
    tree = ast.parse((fixture_repo / "tests" / "test_calc.py").read_text(encoding="utf-8"))
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    assert "TestScale" in classes, f"fixture has no test class: {sorted(classes)}"
    methods = {
        n.name for n in classes["TestScale"].body if isinstance(n, ast.FunctionDef)
    }
    assert "test_scale_multiplies" in methods, methods
    module_level = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "test_scale_multiplies" not in module_level, (
        "the method must NOT also exist at module level, or the unqualified selector would "
        "collect it and the probe would prove nothing"
    )


def test_the_fixture_is_a_real_git_worktree(fixture_repo: Path) -> None:
    """A tree that is not a worktree makes every git-backed guard pass by never firing."""
    assert (fixture_repo / ".git").exists()
    assert resolve_worktree(fixture_repo / CALC_REL) == fixture_repo
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=fixture_repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert status.returncode == 0 and status.stdout.strip() == "", status.stdout


# ---------------------------------------------------------------------------------------------
# 1. pristine-collects -- the six false kills
# ---------------------------------------------------------------------------------------------


def test_an_unqualified_method_selector_is_refused_before_any_verdict(session) -> None:
    """The 0.2.5 defect, exactly: a bare method name collects nothing and reads as a kill."""
    with pytest.raises(ConditionFailed) as caught:
        session.run_case(_case(selector=(T_MULTIPLIES_UNQUALIFIED,), must_fail=(T_MULTIPLIES,)))
    assert caught.value.condition == "pristine-collects"
    assert caught.value.suggested == (T_MULTIPLIES,), (
        "the harness must name the class-qualified node id, not merely say 'no tests'; "
        f"got {caught.value.suggested}"
    )
    assert session.report.verdicts == [], "a refused selector must not produce a verdict"


def test_a_selector_naming_no_test_at_all_is_refused(session) -> None:
    """A typo'd node id is the same failure without the class hint to explain it."""
    with pytest.raises(ConditionFailed) as caught:
        session.run_case(
            _case(
                selector=("tests/test_calc.py::test_does_not_exist",),
                must_fail=("tests/test_calc.py::test_does_not_exist",),
            )
        )
    assert caught.value.condition == "pristine-collects"
    assert caught.value.suggested == ()


def test_the_unmutated_tree_is_untouched_when_a_selector_is_refused(
    session, fixture_repo: Path
) -> None:
    """The refusal happens before the write, so the file is not merely restored -- never written."""
    before = sha256_file(fixture_repo / CALC_REL)
    with pytest.raises(ConditionFailed):
        session.run_case(_case(selector=(T_MULTIPLIES_UNQUALIFIED,), must_fail=(T_MULTIPLIES,)))
    assert sha256_file(fixture_repo / CALC_REL) == before


# ---------------------------------------------------------------------------------------------
# 2. pristine-passes
# ---------------------------------------------------------------------------------------------


def test_a_selector_that_is_already_red_is_refused(session) -> None:
    """A selector failing before the mutation would be 'killed' by any mutation at all."""
    with pytest.raises(ConditionFailed) as caught:
        session.run_case(_case(selector=(T_BROKEN,), must_fail=(T_BROKEN,)))
    assert caught.value.condition == "pristine-passes"
    assert session.report.verdicts == []


# ---------------------------------------------------------------------------------------------
# 3 and 4. lands-once, source-differs
# ---------------------------------------------------------------------------------------------


def test_an_anchor_that_matches_nothing_is_refused() -> None:
    """A substitution that lands zero times silently applies nothing."""
    with pytest.raises(ConditionFailed) as caught:
        apply_mutation(CALC_SOURCE.encode("utf-8"), _case(original="def median(", replacement="x"))
    assert caught.value.condition == "lands-once"


def test_an_anchor_that_matches_twice_is_refused() -> None:
    """A substitution landing several times mutates more than the case describes."""
    with pytest.raises(ConditionFailed) as caught:
        apply_mutation(CALC_SOURCE.encode("utf-8"), _case(original="values", replacement="xs"))
    assert caught.value.condition == "lands-once"


def test_a_replacement_identical_to_the_anchor_is_refused() -> None:
    """A byte-identical 'mutant' is the pristine tree, and any verdict about it is about nothing."""
    with pytest.raises(ConditionFailed) as caught:
        apply_mutation(
            CALC_SOURCE.encode("utf-8"),
            _case(original=MEAN_BODY, replacement=MEAN_BODY),
        )
    assert caught.value.condition == "source-differs"


def test_a_crlf_tree_is_diagnosed_rather_than_reported_as_a_missing_anchor() -> None:
    """The anchor is bytes, so a CRLF file must say so instead of 'the text is not there'."""
    crlf = CALC_SOURCE.replace("\n", "\r\n").encode("utf-8")
    with pytest.raises(ConditionFailed) as caught:
        apply_mutation(crlf, _case(original="values):\n    return sum", replacement="x"))
    assert caught.value.condition == "lands-once"
    assert "CRLF" in caught.value.detail


# ---------------------------------------------------------------------------------------------
# 5. mutant-collects
# ---------------------------------------------------------------------------------------------


def test_a_mutant_that_breaks_collection_is_not_a_kill(session) -> None:
    """Red because the module stopped importing is not red because the mutant is wrong."""
    with pytest.raises(ConditionFailed) as caught:
        session.run_case(
            _case(
                name="syntax-break",
                original="def mean(values):",
                replacement="def mean(values]:",
            )
        )
    assert caught.value.condition == "mutant-collects"
    assert session.report.verdicts == []


def test_the_tree_is_restored_after_a_mutant_that_was_refused_mid_run(
    session, fixture_repo: Path
) -> None:
    """The restore is in a ``finally``; a harness that restored at the end left live mutants."""
    target = fixture_repo / CALC_REL
    before = sha256_file(target)
    with pytest.raises(ConditionFailed):
        session.run_case(
            _case(
                name="syntax-break",
                original="def mean(values):",
                replacement="def mean(values]:",
            )
        )
    assert sha256_file(target) == before, "a refused case left the mutant on disk"
    assert target.read_bytes() == CALC_SOURCE.encode("utf-8")


# ---------------------------------------------------------------------------------------------
# 6. mutant-observed -- red, but not for the reason claimed
# ---------------------------------------------------------------------------------------------


def test_a_red_run_whose_named_test_passed_is_not_a_kill(session) -> None:
    """The run goes red on ``test_mean``, but the case credited ``test_scale_multiplies``.

    This is the shape that let a fixture agree with the bug it was named after: the exit code
    was non-zero and nothing checked *which* test produced it.
    """
    with pytest.raises(ConditionFailed) as caught:
        session.run_case(
            _case(
                name="credited-to-the-wrong-test",
                selector=("tests/test_calc.py",),
                must_fail=(T_MULTIPLIES,),
            )
        )
    assert caught.value.condition == "mutant-observed"
    assert session.report.verdicts == []


def test_a_named_test_that_errored_is_not_an_observation(session) -> None:
    """An ERROR means the body never ran, so nothing observed the semantic property."""
    with pytest.raises(ConditionFailed) as caught:
        session.run_case(
            _case(
                name="fixture-raises",
                original=SCALE_BODY,
                replacement='raise ValueError("harness probe")',
                selector=(T_FIXTURE,),
                must_fail=(T_FIXTURE,),
                semantic_property="scaling returns a list rather than raising",
            )
        )
    assert caught.value.condition == "mutant-observed"
    # The distinctive phrase, not merely "ERROR": the generic wrong-test refusal also carries a
    # tail of pytest output in which the word ERROR can appear, so the looser assertion would
    # survive a mutant that folded ERRORs in with FAILEDs -- which is the false kill itself.
    assert "ERRORed rather than FAILED" in caught.value.detail
    assert T_FIXTURE in caught.value.detail


# ---------------------------------------------------------------------------------------------
# A real kill, and a real survivor
# ---------------------------------------------------------------------------------------------


def test_a_genuine_mutant_is_killed_and_the_kill_names_the_test_that_saw_it(session) -> None:
    """The positive case. Without it, every guard above could be satisfied by refusing always."""
    verdict = session.run_case(_case())
    assert verdict.killed is True
    assert verdict.observed_failures == (T_MEAN,)
    assert verdict.pristine_digest == verdict.restored_digest
    assert verdict.mutant_digest != verdict.pristine_digest
    assert type(verdict.proof) is SelectorProof
    assert verdict.proof.collected == (T_MEAN,)


def test_a_mutant_no_test_distinguishes_is_reported_as_survived_not_killed(session) -> None:
    """Commuting the multiplication changes the source and nothing else. That is a survivor."""
    verdict = session.run_case(
        _case(
            name="commuted-product",
            original=SCALE_BODY,
            replacement="return [factor * v for v in values]",
            selector=(T_MULTIPLIES,),
            must_fail=(T_MULTIPLIES,),
            semantic_property="scaling multiplies each element by the factor",
        )
    )
    assert verdict.killed is False
    assert verdict.observed_failures == ()
    assert session.report.survived == [verdict]
    assert session.report.clean() is False


# ---------------------------------------------------------------------------------------------
# 7. restore-byte-exact
# ---------------------------------------------------------------------------------------------


def test_a_restore_that_does_not_match_its_digest_is_refused(tmp_path: Path) -> None:
    """Verified in bytes. A text-mode restore rewrites line endings and still 'looks' right."""
    path = tmp_path / "f.py"
    path.write_bytes(b"original\n")
    with pytest.raises(ConditionFailed) as caught:
        restore_and_verify(path, b"different\n", sha256_bytes(b"original\n"))
    assert caught.value.condition == "restore-byte-exact"


def test_a_restore_that_matches_returns_the_digest(tmp_path: Path) -> None:
    path = tmp_path / "f.py"
    path.write_bytes(b"mutated\n")
    digest = sha256_bytes(b"original\n")
    assert restore_and_verify(path, b"original\n", digest) == digest
    assert path.read_bytes() == b"original\n"


# ---------------------------------------------------------------------------------------------
# 8. run-digest-clean -- two sub-checks, each proven load-bearing on its own
# ---------------------------------------------------------------------------------------------


def test_a_touched_file_changed_behind_the_session_is_caught_by_the_digests(
    fixture_repo: Path, tmp_path: Path
) -> None:
    """The status snapshot is disabled here, so only the digest map can catch this."""
    with MutationSession(fixture_repo, state_root=tmp_path / "state") as active:
        active.run_case(_case())
        active.entry_status = None  # isolate the digest check from the status check
        (fixture_repo / CALC_REL).write_bytes(CALC_SOURCE.encode("utf-8") + b"# drift\n")
        with pytest.raises(ConditionFailed) as caught:
            active.verify_run_state()
        assert caught.value.condition == "run-digest-clean"
        (fixture_repo / CALC_REL).write_bytes(CALC_SOURCE.encode("utf-8"))


def test_a_new_untracked_file_is_caught_by_the_status_snapshot(
    fixture_repo: Path, tmp_path: Path
) -> None:
    """The digests cannot catch this: they do not know the file exists."""
    stray = fixture_repo / "stray_left_behind.txt"
    with pytest.raises(ConditionFailed) as caught:
        with MutationSession(fixture_repo, state_root=tmp_path / "state") as active:
            active.run_case(_case())
            stray.write_bytes(b"left behind\n")
    assert caught.value.condition == "run-digest-clean"
    stray.unlink()


def test_a_clean_run_exits_without_complaint(fixture_repo: Path, tmp_path: Path) -> None:
    """The negative control: the guard must not fire on a run that behaved."""
    with MutationSession(fixture_repo, state_root=tmp_path / "state") as active:
        verdict = active.run_case(_case())
    assert verdict.killed is True


# ---------------------------------------------------------------------------------------------
# Crash safety: a process killed mid-mutation must not leave a live mutant unannounced
# ---------------------------------------------------------------------------------------------


def _stage_a_crashed_mutation(repo: Path, state_root: Path, write_backup: bool = True) -> bytes:
    """Leave the tree exactly as a process killed between the write and the restore would.

    The journal records the open mutation, the content-addressed backup holds the pristine
    bytes, and the file on disk is the mutant. Building this by hand rather than by killing a
    subprocess keeps the probe deterministic, and the shape is asserted before it is relied on.
    """
    target = repo / CALC_REL
    pristine = target.read_bytes()
    digest = sha256_bytes(pristine)
    state_dir = state_dir_for(repo, state_root)
    backups = state_dir / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / f"{digest}.bin"
    if write_backup:
        backup.write_bytes(pristine)
    (state_dir / "journal.json").write_text(
        json.dumps([{"path": str(target), "digest": digest, "backup": str(backup)}]),
        encoding="utf-8",
    )
    target.write_bytes(pristine + b"# live mutant left by a killed process\n")
    assert sha256_file(target) != digest, "the staged crash did not actually leave a mutant"
    return pristine


def test_a_session_killed_mid_mutation_is_restored_by_the_next_one(tmp_path: Path) -> None:
    """Condition 8 has to survive an abrupt death, not only an orderly exit.

    A harness that cannot tell you after a crash whether it left a mutant behind has not met
    the whole-run digest condition; it has only met it when nothing went wrong.
    """
    repo = _write_fixture_repo(tmp_path / "crashed")
    state_root = tmp_path / "state"
    pristine = _stage_a_crashed_mutation(repo, state_root)

    with MutationSession(repo, state_root=state_root):
        pass

    assert (repo / CALC_REL).read_bytes() == pristine, "the next session left the mutant live"
    assert sha256_file(repo / CALC_REL) == sha256_bytes(pristine)


def test_a_crash_whose_backup_is_gone_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    """An unrestorable mutant must stop the run loudly, not be skipped into a clean-looking one."""
    repo = _write_fixture_repo(tmp_path / "lost_backup")
    state_root = tmp_path / "state"
    _stage_a_crashed_mutation(repo, state_root, write_backup=False)

    with pytest.raises(ConditionFailed) as caught:
        with MutationSession(repo, state_root=state_root):
            pass
    assert caught.value.condition == "restore-byte-exact"


# ---------------------------------------------------------------------------------------------
# Worktree derivation and containment (P-134)
# ---------------------------------------------------------------------------------------------


def test_the_session_has_no_default_worktree() -> None:
    """A default is the defect: a draft defaulted to the checkout it was imported from.

    ``Path(__file__).resolve().parents[1]`` resolves to whichever tree the *module* lives in,
    which is the main tree whenever a linked worktree imports an installed or shared copy.
    """
    parameter = inspect.signature(MutationSession.__init__).parameters["worktree"]
    assert parameter.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        MutationSession()  # type: ignore[call-arg]


def test_the_harness_never_derives_its_root_from_its_own_file_location() -> None:
    """Asserted against the source, because the defect is a single line that looks harmless.

    Over the AST, not the text. A line-level scan also matches the docstring that *names* the
    banned idiom in order to warn about it -- a check that fires on its own explanation is the
    proxy defect this repository keeps measuring, and it fired here on the first run.
    """
    tree = ast.parse(HARNESS_SOURCE.read_text(encoding="utf-8"))
    offenders = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id == "__file__")
        or (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "parents"
        )
    ]
    assert offenders == [], (
        f"the harness must derive the worktree from git, not from its own location: {offenders}"
    )


def test_a_path_outside_the_worktree_is_refused_and_left_alone(session, tmp_path: Path) -> None:
    """P-134: a restore driven by another lane's state writes into another lane's tree."""
    outsider = tmp_path / "outside.py"
    outsider.write_bytes(b"untouched\n")
    with pytest.raises(OutsideWorktree):
        session.run_case(_case(path=str(outsider)))
    assert outsider.read_bytes() == b"untouched\n"


def test_a_relative_escape_is_refused(session) -> None:
    """``..`` must be refused on the resolved path, not normalised into acceptance."""
    with pytest.raises(OutsideWorktree):
        session.run_case(_case(path="../escape.py"))


def test_state_for_two_worktrees_never_collides_even_with_the_same_leaf_name(
    tmp_path: Path,
) -> None:
    """Two lanes overwrote each other's state in a shared scratchpad. Leaf names repeat."""
    a = tmp_path / "a" / "jnwb"
    b = tmp_path / "b" / "jnwb"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    assert a.name == b.name
    assert state_dir_for(a) != state_dir_for(b)


def test_harness_state_lives_outside_the_tree_it_mutates(fixture_repo: Path) -> None:
    """State inside the tree would be reported forever by the guard that looks for leftovers."""
    state = state_dir_for(fixture_repo)
    assert default_state_root() in state.parents
    with pytest.raises(ValueError):
        state.relative_to(fixture_repo)


def test_one_worktree_admits_one_session_at_a_time(fixture_repo: Path, tmp_path: Path) -> None:
    """Two sessions restore over each other's backups and leave a mutant behind."""
    with MutationSession(fixture_repo, state_root=tmp_path / "state"):
        with pytest.raises(HarnessBusy):
            with MutationSession(fixture_repo, state_root=tmp_path / "state"):
                pass


def test_a_directory_that_is_not_a_worktree_is_refused(tmp_path: Path) -> None:
    plain = tmp_path / "not_a_repo"
    plain.mkdir()
    with pytest.raises(NotAWorktree):
        resolve_worktree(plain)


def test_an_already_modified_target_is_refused_before_it_is_read_as_pristine(
    tmp_path: Path,
) -> None:
    """Otherwise the harness backs up the *mutant* and faithfully restores the tree to it."""
    repo = _write_fixture_repo(tmp_path / "own")
    (repo / CALC_REL).write_bytes(CALC_SOURCE.encode("utf-8") + b"# another writer\n")
    # Declared, so ``tree-declared`` lets the run start: this test is about the *next* guard,
    # the one that refuses to read an already-modified target as the pristine bytes.
    with MutationSession(
        repo, state_root=tmp_path / "state", declared_modifications=[CALC_REL]
    ) as active:
        with pytest.raises(TreeNotPristine):
            active.run_case(_case())
        active.entry_status = None  # the tree was dirty on purpose; do not re-report it on exit


# ---------------------------------------------------------------------------------------------
# No verdict without a proof
# ---------------------------------------------------------------------------------------------


def test_a_proof_cannot_be_constructed_without_the_private_token() -> None:
    """Otherwise a caller that skipped the proof could mint one and get a verdict."""
    with pytest.raises(MutationHarnessError):
        SelectorProof(selector=("x.py::t",), collected=("x.py::t",), pristine_exit=0)


def test_a_verdict_cannot_be_constructed_without_a_proof() -> None:
    """The accept clause, as a type constraint rather than as a convention."""
    with pytest.raises(MutationHarnessError):
        Verdict(
            case="forged",
            killed=True,
            proof=object(),  # type: ignore[arg-type]
            mutant_collected=(),
            observed_failures=(),
            collateral_failures=(),
            pristine_digest="a",
            mutant_digest="b",
            restored_digest="a",
        )


# ---------------------------------------------------------------------------------------------
# Case declaration
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"selector": ()}, "no selector"),
        ({"must_fail": ()}, "must_fail is empty"),
        ({"semantic_property": ""}, "semantic property"),
        ({"selector": ("test_scale_multiplies",)}, "not a pytest node id"),
        ({"must_fail": ("test_scale_multiplies",)}, "not a pytest node id"),
        ({"expected_survivor": True}, "must say why the gap is tolerated"),
        ({"survivor_reason": "because"}, "expected_survivor is False"),
    ],
)
def test_an_underspecified_case_cannot_be_constructed(overrides, fragment) -> None:
    """A case that cannot say what must fail can only assert that the run went red."""
    with pytest.raises(MutationHarnessError) as caught:
        _case(**overrides)
    assert fragment in str(caught.value)


# ---------------------------------------------------------------------------------------------
# One refused case must not hide the others
# ---------------------------------------------------------------------------------------------


def test_a_refused_case_does_not_stop_the_rest_of_the_suite(session) -> None:
    """A gate that aborts leaves every later gate unrun and looking fine."""
    report = session.run_suite(
        [
            _case(name="refused", selector=(T_MULTIPLIES_UNQUALIFIED,), must_fail=(T_MULTIPLIES,)),
            _case(name="real"),
        ]
    )
    assert [r.case for r in report.rejections] == ["refused"]
    assert [v.case for v in report.verdicts] == ["real"]
    assert report.rejections[0].condition == "pristine-collects"
    assert report.clean() is False


# ---------------------------------------------------------------------------------------------
# The declared conditions are the enforced conditions
# ---------------------------------------------------------------------------------------------


def test_every_declared_condition_has_an_enforcement_site() -> None:
    """A condition in the list with no ``raise`` behind it is a documented convention.

    Read off the source, so a condition that is renamed, dropped, or never raised is caught
    rather than believed. The re-raise in ``prove_selector`` passes ``exc.condition`` and is not
    a literal, so it does not count as a site.
    """
    tree = ast.parse(HARNESS_SOURCE.read_text(encoding="utf-8"))
    raised: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "ConditionFailed"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            raised.append(node.args[0].value)
    assert set(raised) == set(CONDITIONS), (
        f"declared but never raised: {sorted(set(CONDITIONS) - set(raised))}; "
        f"raised but not declared: {sorted(set(raised) - set(CONDITIONS))}"
    )
    assert len(CONDITIONS) == 9


def test_an_undeclared_condition_cannot_be_raised() -> None:
    """The condition name is the contract these tests assert on; typos must not pass silently."""
    with pytest.raises(MutationHarnessError):
        ConditionFailed("not-a-condition", "x")


# ---------------------------------------------------------------------------------------------
# P-174, half one: a journal that cannot answer says so, instead of saying "empty"
# ---------------------------------------------------------------------------------------------


def test_a_missing_journal_is_unknown_rather_than_empty(tmp_path: Path) -> None:
    """The defect verbatim: "no record exists" and "nothing is outstanding" were one answer.

    A lane reported "all four harness journals on this machine read ``[]``" -- true, and empty
    of meaning, while a live mutant sat in the tree for three days.
    """
    repo = _write_fixture_repo(tmp_path / "no_journal")
    session = MutationSession(repo, state_root=tmp_path / "state")
    assert not session.journal.exists()

    state = session.read_journal()
    assert state.status == JOURNAL_ABSENT
    assert state.is_known is False, "an absent journal must not claim to know anything"
    assert state.entries == ()
    assert "UNKNOWN" in state.describe()


def test_an_empty_journal_is_known_and_says_nothing_is_outstanding(tmp_path: Path) -> None:
    """The other side of the same coin. Without this, 'unknown' could be the only answer."""
    repo = _write_fixture_repo(tmp_path / "empty_journal")
    session = MutationSession(repo, state_root=tmp_path / "state")
    session.journal.parent.mkdir(parents=True, exist_ok=True)
    session.journal.write_text("[]", encoding="utf-8")

    state = session.read_journal()
    assert state.status == JOURNAL_PRESENT
    assert state.is_known is True
    assert state.entries == ()
    assert "UNKNOWN" not in state.describe()


def test_a_missing_and_an_empty_journal_do_not_give_the_same_answer(tmp_path: Path) -> None:
    """The discriminator for the defect itself, stated as the one comparison that must differ.

    Both of the tests above would still pass if ``read_journal`` returned the same status for
    both cases and the two assertions happened to be written loosely. This one cannot.
    """
    repo = _write_fixture_repo(tmp_path / "both")
    absent = MutationSession(repo, state_root=tmp_path / "absent").read_journal()
    present = MutationSession(repo, state_root=tmp_path / "present")
    present.journal.parent.mkdir(parents=True, exist_ok=True)
    present.journal.write_text("[]", encoding="utf-8")

    assert absent.entries == present.read_journal().entries == ()
    assert absent.status != present.read_journal().status, (
        "a missing journal and a journal recording nothing outstanding give the same answer "
        "again. That is P-174: an absence of records read as an absence of mutants."
    )
    assert absent.is_known is not present.read_journal().is_known


@pytest.mark.parametrize(
    "contents", ["{not json", '{"path": "x"}', '["a string, not an object"]']
)
def test_an_unparseable_journal_refuses_the_run_rather_than_reading_as_empty(
    tmp_path: Path, contents: str
) -> None:
    """A corrupted journal may record a live mutant. Treating it as empty is the defect."""
    repo = _write_fixture_repo(tmp_path / f"corrupt_{abs(hash(contents))}")
    state_root = tmp_path / "state"
    session = MutationSession(repo, state_root=state_root)
    session.journal.parent.mkdir(parents=True, exist_ok=True)
    session.journal.write_text(contents, encoding="utf-8")

    assert session.read_journal().status == JOURNAL_UNREADABLE
    with pytest.raises(JournalUnreadable):
        with MutationSession(repo, state_root=state_root):
            pass


def test_a_journal_state_that_is_not_known_cannot_carry_entries() -> None:
    """Otherwise an 'unknown' journal could still hand back records, which is a third meaning."""
    with pytest.raises(MutationHarnessError):
        JournalState(JOURNAL_ABSENT, entries=({"path": "x"},))
    with pytest.raises(MutationHarnessError):
        JournalState("invented-status")


# ---------------------------------------------------------------------------------------------
# P-174, half two: a run states the tree it ran against
# ---------------------------------------------------------------------------------------------

#: The exact shape of the mutant that survived three days and four green suite runs: it disables
#: a check and breaks nothing, so no run of the suite can see it. ``if False and`` in the original
#: defect; ``assert True or`` here, because the fixture's check is an assert.
SILENT_MUTANT_PATH = "tests/test_calc.py"
SILENT_ANCHOR = b"    assert mean([1, 2, 3]) == 2\n"
SILENT_MUTANT = b"    assert True or mean([1, 2, 3]) == 2\n"


def _plant_the_silent_mutant(repo: Path) -> bytes:
    target = repo / SILENT_MUTANT_PATH
    pristine = target.read_bytes()
    assert pristine.count(SILENT_ANCHOR) == 1, "the silent-mutant anchor moved"
    target.write_bytes(pristine.replace(SILENT_ANCHOR, SILENT_MUTANT, 1))
    return pristine


def _suite_is_green(repo: Path) -> bool:
    """Run the tests that hold the suppressed check, and say whether they passed.

    ``tests/test_broken.py`` is red by design -- it exists so ``pristine-passes`` has something
    real to refuse -- so the fixture's whole suite is never green and asking about it would make
    this probe answer False for a reason that has nothing to do with the mutant. The question is
    narrower and it is the right one: does running the file whose check the mutant disables still
    pass?
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", SILENT_MUTANT_PATH],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=600,
    )
    return proc.returncode == 0


def test_the_planted_mutant_really_is_the_silent_shape(tmp_path: Path) -> None:
    """The discriminator is vacuous unless the mutant is one no test run can see.

    06-113 says so explicitly: the 0.2.5 D13 mutant narrowed a glob, broke something, and the
    full suite caught it. This one disables an ``if`` and breaks nothing, and the suite did not.
    A probe planting a *noisy* mutant would prove the suite works, not that the tree statement
    catches what the suite cannot.
    """
    repo = _write_fixture_repo(tmp_path / "silent_shape")
    assert _suite_is_green(repo), "the fixture suite is not green before the mutant"
    pristine = _plant_the_silent_mutant(repo)
    try:
        assert (repo / SILENT_MUTANT_PATH).read_bytes() != pristine
        assert _suite_is_green(repo), (
            "the planted mutant breaks a test, so it is the D13 shape and not the P-174 shape. "
            "A mutant the suite catches proves nothing about a check the suite cannot catch."
        )
    finally:
        (repo / SILENT_MUTANT_PATH).write_bytes(pristine)


def test_an_undeclared_modification_refuses_the_run_and_names_the_path(tmp_path: Path) -> None:
    """P-174, as a gate: the silent mutant is invisible to the suite and to the journal alike."""
    repo = _write_fixture_repo(tmp_path / "surprise")
    pristine = _plant_the_silent_mutant(repo)
    try:
        with pytest.raises(ConditionFailed) as caught:
            with MutationSession(repo, state_root=tmp_path / "state"):
                pass
        assert caught.value.condition == "tree-declared"
        assert SILENT_MUTANT_PATH in caught.value.detail, (
            "the refusal must name the offending path, not merely say the tree is dirty; "
            f"got {caught.value.detail!r}"
        )
    finally:
        (repo / SILENT_MUTANT_PATH).write_bytes(pristine)


def test_the_same_tree_proceeds_once_the_modification_is_restored(tmp_path: Path) -> None:
    """The other half of the discriminator: refusing always would satisfy the test above."""
    repo = _write_fixture_repo(tmp_path / "restored")
    pristine = _plant_the_silent_mutant(repo)
    (repo / SILENT_MUTANT_PATH).write_bytes(pristine)

    with MutationSession(repo, state_root=tmp_path / "state") as active:
        assert active.tree_statement is not None
        assert active.tree_statement.tracked_modifications == ()
        assert active.tree_statement.undeclared == ()


def test_a_declared_modification_is_allowed_through(tmp_path: Path) -> None:
    """A caller that says what it meant to change is not blocked by its own edit."""
    repo = _write_fixture_repo(tmp_path / "declared")
    pristine = _plant_the_silent_mutant(repo)
    try:
        with MutationSession(
            repo, state_root=tmp_path / "state", declared_modifications=[SILENT_MUTANT_PATH]
        ) as active:
            assert active.tree_statement is not None
            assert active.tree_statement.tracked_modifications == (SILENT_MUTANT_PATH,)
            assert active.tree_statement.undeclared == ()
            active.entry_status = None  # dirty on purpose; not drift this session caused
    finally:
        (repo / SILENT_MUTANT_PATH).write_bytes(pristine)


def test_an_untracked_file_does_not_refuse_the_run(tmp_path: Path) -> None:
    """A gate that must be handed an ignore list is a gate nobody runs -- 06-113's stop clause.

    Scratch files are the normal state of a working tree. Only *tracked* modifications refuse;
    a stray untracked file is still caught, on the way out, by the entry/exit status comparison.
    """
    repo = _write_fixture_repo(tmp_path / "untracked")
    stray = repo / "scratch_note.txt"
    stray.write_bytes(b"not a mutant\n")
    try:
        with MutationSession(repo, state_root=tmp_path / "state") as active:
            assert active.tree_statement is not None
            assert active.tree_statement.tracked_modifications == ()
    finally:
        stray.unlink()


def test_the_tree_statement_names_the_commit_and_the_journal(tmp_path: Path) -> None:
    """'A run states the tree it ran against' has to be a statement, not just a refusal."""
    repo = _write_fixture_repo(tmp_path / "statement")
    with MutationSession(repo, state_root=tmp_path / "state") as active:
        statement = active.tree_statement
        assert statement is not None
        assert len(statement.head) == 40 and all(c in "0123456789abcdef" for c in statement.head)
        assert statement.journal is not None
        described = statement.describe()
        assert statement.head in described
        assert "journal:" in described


def test_a_crashed_session_is_replayed_before_the_tree_is_judged(tmp_path: Path) -> None:
    """Order is load-bearing: this harness's own open mutant is not somebody else's surprise.

    If the tree were judged first, every crash recovery would be refused as an undeclared
    modification and the replay would never run -- turning the repair into a deadlock.
    """
    repo = _write_fixture_repo(tmp_path / "replay_order")
    state_root = tmp_path / "state"
    pristine = _stage_a_crashed_mutation(repo, state_root)

    with MutationSession(repo, state_root=state_root) as active:
        assert active.tree_statement is not None
        assert active.tree_statement.undeclared == ()
    assert (repo / CALC_REL).read_bytes() == pristine


@pytest.mark.parametrize(
    "porcelain, tracked, untracked",
    [
        (" M jnwb/spectral.py\n", ("jnwb/spectral.py",), ()),
        ("?? scratch.txt\n", (), ("scratch.txt",)),
        ("M  a.py\n?? b.txt\n", ("a.py",), ("b.txt",)),
        ("R  old.py -> new.py\n", ("new.py",), ()),
        ('?? "with space.txt"\n', (), ("with space.txt",)),
        ("", (), ()),
        # A dotfile keeps its dot. ``lstrip("./")`` strips a character class, not a prefix, and
        # turned ``.github/workflows/ci.yml`` into ``github/workflows/ci.yml``. Both sides of the
        # comparison normalise through the same function, so the check went on agreeing with
        # itself and only the path named in a refusal was wrong.
        (" M .github/workflows/ci.yml\n", (".github/workflows/ci.yml",), ()),
        ("?? .claude/settings.json\n", (), (".claude/settings.json",)),
        (" M ./jnwb/spectral.py\n", ("jnwb/spectral.py",), ()),
    ],
)
def test_porcelain_is_split_into_tracked_and_untracked(porcelain, tracked, untracked) -> None:
    """Parsed, not grepped. A rename prints two paths and only the new one is modified."""
    assert parse_porcelain(porcelain) == (tracked, untracked)


def test_a_declared_dotfile_path_is_matched_rather_than_mangled() -> None:
    """A declaration and git's own spelling must normalise to the same string.

    This is the side a caller controls: declaring ``.github/workflows/ci.yml`` has to match what
    git reports for it, or the declaration silently fails to cover the file it names.
    """
    from scripts.mutation_harness import _posix_relative

    for path in (".github/workflows/ci.yml", ".claude/settings.json", ".gitignore"):
        assert _posix_relative(path) == path, f"{path} was mangled to {_posix_relative(path)!r}"
    assert _posix_relative("./jnwb/spectral.py") == "jnwb/spectral.py"
    assert _posix_relative("jnwb\\spectral.py") == "jnwb/spectral.py"


# ---------------------------------------------------------------------------------------------
# P-172: a measured gap can be recorded, and stops being a gap loudly
# ---------------------------------------------------------------------------------------------


def _expected_survivor_case(**overrides) -> MutationCase:
    base = dict(
        name="commuted-product-is-a-known-gap",
        original=SCALE_BODY,
        replacement="return [factor * v for v in values]",
        selector=(T_MULTIPLIES,),
        must_fail=(T_MULTIPLIES,),
        semantic_property="scaling multiplies each element by the factor",
        expected_survivor=True,
        survivor_reason="commuting the product is an identity over the reals; recorded as P-XXX",
    )
    base.update(overrides)
    return _case(**base)


def test_a_declared_gap_that_is_still_a_gap_does_not_fail_the_run(session) -> None:
    """The whole point: a measured hole can live in the suite instead of in a lane report."""
    verdict = session.run_case(_expected_survivor_case())
    assert verdict.killed is False
    assert verdict.expected_survivor is True
    assert session.report.expected_survivors == [verdict]
    assert session.report.survived == [], "a declared gap must not be reported as a failure"
    assert session.report.clean() is True
    assert "EXPECTED-SURVIVOR" in session.report.summary()


def test_a_declared_gap_that_has_closed_fails_the_run(session) -> None:
    """The discriminator the item names: an expected survivor that starts being killed fails.

    Without this the record rots in the other direction -- somebody adds the missing assertion,
    the gap closes, and the note saying it is open goes on saying so forever.
    """
    verdict = session.run_case(
        _expected_survivor_case(
            name="mean-becomes-sum-wrongly-recorded-as-a-gap",
            original=MEAN_BODY,
            replacement="return sum(values)",
            selector=(T_MEAN,),
            must_fail=(T_MEAN,),
            semantic_property="the mean of a sample is its sum divided by its count",
            survivor_reason="recorded as a gap, but the suite does catch it",
        )
    )
    assert verdict.killed is True
    assert verdict.expected_survivor is True
    assert session.report.unexpected_kills == [verdict]
    assert session.report.killed == [], "a declared gap that closed is not an ordinary kill"
    assert session.report.clean() is False, (
        "closing a recorded gap without updating the record must fail the run"
    )
    assert "UNEXPECTED-KILL" in session.report.summary()


def test_an_undeclared_survivor_is_still_a_failure(session) -> None:
    """The negative control. ``expected_survivor`` must not turn every survivor into a pass."""
    verdict = session.run_case(
        _case(
            name="commuted-product-nobody-declared",
            original=SCALE_BODY,
            replacement="return [factor * v for v in values]",
            selector=(T_MULTIPLIES,),
            must_fail=(T_MULTIPLIES,),
            semantic_property="scaling multiplies each element by the factor",
        )
    )
    assert verdict.expected_survivor is False
    assert session.report.survived == [verdict]
    assert session.report.expected_survivors == []
    assert session.report.clean() is False


# ---------------------------------------------------------------------------------------------
# The two gaps 06-27 measured, held to the checkout rather than to prose
# ---------------------------------------------------------------------------------------------


def _resolve_node_id(node_id: str) -> bool:
    """True when every ``::`` segment of a pytest node id exists in the file it names.

    Over the AST, not by running pytest: collecting ``tests/test_spectral.py`` costs a
    subprocess and a full ``jnwb`` import, and this file is one of the fast ones. The limit is
    stated rather than hidden -- this resolves classes and functions, so it would not notice a
    parametrisation change. Neither gap names a parametrised node.
    """
    parts = node_id.replace("\\", "/").split("::")
    source = REPO_ROOT / parts[0]
    if not source.is_file():
        return False
    body = ast.parse(source.read_text(encoding="utf-8")).body
    for segment in parts[1:]:
        match = next(
            (
                n
                for n in body
                if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == segment.split("[")[0]
            ),
            None,
        )
        if match is None:
            return False
        body = match.body
    return True


def test_the_measured_gaps_are_recorded_as_expected_survivors() -> None:
    """06-27 measured P-170 and P-171 and could only narrate them. P-170 is now killed by
    `test_the_returned_spectrum_carries_the_same_sign_as_net`; P-171 stays declared."""
    assert len(KNOWN_GAPS) == 1
    recorded = {gap.name.split(" | ")[0] for gap in KNOWN_GAPS}
    assert recorded == {"P-171"}, recorded
    for gap in KNOWN_GAPS:
        assert gap.expected_survivor is True
        assert len(gap.survivor_reason.split()) >= 15, (
            f"{gap.name}: the reason does not say why the gap is tolerated"
        )


def test_every_recorded_gap_still_lands_on_this_checkout() -> None:
    """A gap whose anchor has moved is not a gap on the record, it is a stale sentence.

    This is the cheap half of holding the record honest, and the half that runs in the fast
    suite: the anchor must still occur exactly once, in bytes, and every node id the gap names
    must still exist. Whether the mutant still survives is measured by an isolated-clone run,
    because a mutation of ``jnwb/`` in this checkout is visible to every other ``-n auto`` worker.
    """
    problems: list[str] = []
    for gap in KNOWN_GAPS:
        target = REPO_ROOT / gap.path
        if not target.is_file():
            problems.append(f"{gap.name}: {gap.path} does not exist")
            continue
        count = target.read_bytes().count(gap.original.encode("utf-8"))
        if count != 1:
            problems.append(f"{gap.name}: the anchor occurs {count} times in {gap.path}, not once")
        if gap.original == gap.replacement:
            problems.append(f"{gap.name}: the replacement is byte-identical to the anchor")
        for node in {*gap.selector, *gap.must_fail}:
            if not _resolve_node_id(node):
                problems.append(f"{gap.name}: {node} does not resolve in this checkout")
    assert not problems, (
        "recorded gaps no longer describe this checkout:\n  " + "\n  ".join(problems)
    )


def test_the_conditions_are_declared_in_enforcement_order() -> None:
    """The order is load-bearing: a later guard must not be reachable before an earlier one."""
    assert CONDITIONS == (
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


def test_main_reports_a_missing_journal_as_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Through the command line, not the session object: the replay rewrote the journal as
    ``[]`` before the tree was stated, so a first run printed "present, nothing outstanding"."""
    import scripts.mutation_harness as harness

    repo = _write_fixture_repo(tmp_path / "first_run")
    monkeypatch.setattr(harness, "default_state_root", lambda: tmp_path / "state")
    assert not state_dir_for(repo, tmp_path / "state").exists()
    case = _case()
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{
        "name": case.name, "path": case.path, "original": case.original,
        "replacement": case.replacement, "selector": list(case.selector),
        "must_fail": list(case.must_fail), "semantic_property": case.semantic_property,
    }]), encoding="utf-8")

    assert harness.main([str(cases), "--worktree", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "journal: UNKNOWN (no journal file)" in out, out
    assert "present, nothing outstanding" not in out, out


def test_the_release_step_fails_when_the_gap_run_fails(tmp_path: Path) -> None:
    """The recorded gaps are run by the release, so a gap that closed stops it (06-113)."""
    from scripts.release_gate import check_known_gaps_hold

    calls: list[list[str]] = []

    def runner(harness_rc: int):
        def run(cmd, **_kwargs):
            calls.append(list(cmd))
            rc = harness_rc if "--known-gaps" in cmd else 0
            if cmd[:3] == ["git", "worktree", "add"]:
                Path(cmd[4]).mkdir(parents=True)
            return subprocess.CompletedProcess(cmd, rc, "UNEXPECTED-KILL x" if rc else "", "")
        return run

    ok, report = check_known_gaps_hold(tmp_path, runner=runner(1))
    assert ok is False and "UNEXPECTED-KILL" in report
    assert any("--known-gaps" in c and "--worktree" in c for c in calls)
    assert calls[-1] == ["git", "worktree", "prune"], "the throwaway worktree must be pruned"
    calls.clear()
    assert check_known_gaps_hold(tmp_path, runner=runner(0))[0] is True


def test_the_known_gaps_mode_needs_no_case_file() -> None:
    """``--known-gaps`` and a case file are exclusive, so the release cannot run neither."""
    import scripts.mutation_harness as harness

    with pytest.raises(SystemExit):
        harness.main(["--worktree", str(REPO_ROOT)])
