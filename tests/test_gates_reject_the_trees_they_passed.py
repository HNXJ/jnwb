"""One constructed tree per repaired gate: the tree the gate used to accept.

Nine of the thirteen preflight gates were presence or substring checks standing in for
behaviour, and each was confirmed by building the tree it should reject and watching it pass.
The trees are rebuilt here so the repairs cannot quietly come undone.

Each test asserts both directions -- the adversarial tree is rejected and a well-formed one is
accepted -- because a gate that rejects everything is as useless as one that rejects nothing.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from tests.test_docs_links import broken_links  # noqa: E402

from scripts.harness_gate import (  # noqa: E402
    ALLOWED_ROOT_FILES,
    EPHEMERAL_ROOT_DIRS,
    INTERNAL_ROOT_PACKAGES,
    NWB_ONBOARDING_SYMBOLS,
    PYTHON_CI_REQUIRED,
    PYTHON_SUPPORTED,
    check_docs_version_matches_package,
    check_no_hardcoded_test_paths,
    check_no_shadow_packages,
    check_nwb_onboarding_alignment,
    check_public_symbols_documented,
    check_python_floor_consistency,
    check_skill_tree_uniqueness,
    check_version_consistency,
)


# --------------------------------------------------------------------------- Gate 11
class TestGate11SeesNamespacePackages:
    """`__init__.py` is not what makes a directory importable; PEP 420 is.

    JNWB-002 -- 88 of 190 importing files taking the wrong copy of a user project -- is
    reproduced by a directory with `.py` files and no `__init__.py`, and the gate passed it.
    """

    def test_a_directory_with_py_files_and_no_init_is_rejected(self, tmp_path: Path):
        (tmp_path / "otherproject").mkdir()
        (tmp_path / "otherproject" / "module.py").write_text("X = 1\n", encoding="utf-8")
        violations = check_no_shadow_packages(tmp_path)
        assert violations, "a PEP 420 namespace package at the root was accepted"
        assert "namespace package" in violations[0]

    def test_that_directory_really_is_importable(self, tmp_path: Path):
        """The premise, checked rather than asserted."""
        (tmp_path / "otherproject").mkdir()
        (tmp_path / "otherproject" / "module.py").write_text("X = 1\n", encoding="utf-8")
        # Appended, not prepended: sys.path[0] shadows the package under test for the
        # rest of the session, which is what tests/test_the_suite_can_qualify_an_installed_copy.py
        # forbids. "otherproject" exists nowhere else, so the tail of the path finds it.
        sys.path.append(str(tmp_path))
        try:
            spec = importlib.util.find_spec("otherproject")
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("otherproject", None)
        assert spec is not None and spec.origin is None, (
            "the directory is not importable as a namespace package, so this gate's premise "
            "has changed"
        )

    def test_a_directory_with_no_python_at_all_is_accepted(self, tmp_path: Path):
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "README.md").write_text("text\n", encoding="utf-8")
        assert check_no_shadow_packages(tmp_path) == []

    def test_an_ephemeral_directory_is_not_a_shadow(self, tmp_path: Path):
        """A `.venv` full of other packages is not this repository's problem."""
        venv = tmp_path / "dist"
        assert "dist" in EPHEMERAL_ROOT_DIRS
        venv.mkdir()
        (venv / "setup.py").write_text("X = 1\n", encoding="utf-8")
        assert check_no_shadow_packages(tmp_path) == []

    def test_the_repositorys_own_directories_are_named_rather_than_pattern_matched(self):
        assert {"docs", "examples", "scripts", "tests"} <= INTERNAL_ROOT_PACKAGES


# ---------------------------------------------------------------------------- Gate 2
class TestGate2SeesAnySecondSkillTree:
    """It checked one hardcoded path, `.agents/skills`, and nothing else."""

    @pytest.mark.parametrize("where", ["jnwb/skills/dup", "docs/skills/dup", ".agents/skills/dup"])
    def test_a_duplicate_tree_anywhere_is_rejected(self, tmp_path: Path, where: str):
        target = tmp_path / where
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("# duplicate\n", encoding="utf-8")
        violations = check_skill_tree_uniqueness(tmp_path)
        assert violations, f"a second skill tree at {where} was accepted"
        assert "DUPLICATE_SKILL_TREE" in violations[0]

    def test_the_canonical_tree_is_accepted(self, tmp_path: Path):
        target = tmp_path / "skills" / "jnwb"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("# canonical\n", encoding="utf-8")
        assert check_skill_tree_uniqueness(tmp_path) == []

    def test_a_process_skill_under_artifacts_is_accepted(self, tmp_path: Path):
        for where in ("skills/jnwb", "artifacts/skills/process"):
            (tmp_path / where).mkdir(parents=True)
            (tmp_path / where / "SKILL.md").write_text("# one home\n", encoding="utf-8")
        assert check_skill_tree_uniqueness(tmp_path) == []

    @pytest.mark.parametrize("where", ["artifacts/skills/jnwb", "artifacts/skills/nested/deeper"])
    def test_a_shipped_skill_repeated_or_nested_under_artifacts_is_rejected(
        self, tmp_path: Path, where: str
    ):
        for path in ("skills/jnwb", where):
            (tmp_path / path).mkdir(parents=True)
            (tmp_path / path / "SKILL.md").write_text("# copy\n", encoding="utf-8")
        violations = check_skill_tree_uniqueness(tmp_path)
        assert violations and "DUPLICATE_SKILL_TREE" in violations[0], where

    def test_another_packages_skills_inside_an_ephemeral_directory_are_ignored(self, tmp_path):
        target = tmp_path / ".venv" / "Lib" / "site-packages" / "other" / ".agents" / "skills"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("# not ours\n", encoding="utf-8")
        assert ".venv" in EPHEMERAL_ROOT_DIRS
        assert check_skill_tree_uniqueness(tmp_path) == []

    def test_this_repository_still_passes(self):
        assert check_skill_tree_uniqueness(REPO_ROOT) == []


# ---------------------------------------------------------------------------- Gate 3
class TestGate3SeesEveryDriveLetter:
    """The pattern matched `C:` and `D:`. This machine keeps its analysis data on `E:`."""

    @pytest.mark.parametrize("drive", ["C", "D", "E", "Z"])
    def test_a_machine_local_path_on_any_drive_is_rejected(self, tmp_path: Path, drive: str):
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_x.py").write_text(
            f'PATH = "{drive}:/analysis/derived/session.nwb"\n', encoding="utf-8"
        )
        violations = check_no_hardcoded_test_paths(tmp_path)
        assert violations, f"a hardcoded {drive}:/ path was accepted"

    def test_a_path_marked_synthetic_is_still_allowed(self, tmp_path: Path):
        """Fixtures that compose paths from a fabricated root are machine-independent."""
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_x.py").write_text(
            'ROOT = "Z:/synthetic_data"\n', encoding="utf-8"
        )
        assert check_no_hardcoded_test_paths(tmp_path) == []


# ---------------------------------------------------------------------------- Gate 7
class TestGate7ParsesPyprojectRatherThanSearchingIt:
    """The binding was matched as a substring, so a commented-out binding satisfied it."""

    def test_a_commented_binding_with_a_wrong_version_is_rejected(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "jnwb"\n'
            'version = "0.0.1"\n'
            '# version = { attr = "jnwb.__version__" }\n',
            encoding="utf-8",
        )
        violations = check_version_consistency(tmp_path)
        assert violations, "a pyproject declaring 0.0.1 passed because a comment mentioned attr"
        assert "0.0.1" in violations[0]

    def test_a_matching_static_version_is_accepted(self, tmp_path: Path):
        import jnwb

        (tmp_path / "pyproject.toml").write_text(
            f'[project]\nname = "jnwb"\nversion = "{jnwb.__version__}"\n', encoding="utf-8"
        )
        assert check_version_consistency(tmp_path) == []

    def test_a_dynamic_version_is_accepted(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "jnwb"\ndynamic = ["version"]\n', encoding="utf-8"
        )
        assert check_version_consistency(tmp_path) == []

    def test_a_file_that_declares_no_version_at_all_is_rejected(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "jnwb"\n', encoding="utf-8"
        )
        assert check_version_consistency(tmp_path)


# ---------------------------------------------------------------------------- Gate 8
class TestGate8FailsOnAbsenceRatherThanSkipping:
    """Every block was `if <file>.exists():` with no else, so an empty directory passed."""

    def test_an_empty_tree_is_rejected(self, tmp_path: Path):
        violations = check_python_floor_consistency(tmp_path)
        assert len(violations) >= 3, (
            f"a tree with no pyproject, no readthedocs config and no workflow produced "
            f"{len(violations)} violations: {violations}"
        )

    @pytest.mark.parametrize("missing", ["pyproject.toml", ".readthedocs.yaml", "workflow.yml"])
    def test_each_missing_file_is_named(self, tmp_path: Path, missing: str):
        violations = check_python_floor_consistency(tmp_path)
        assert any(missing in v for v in violations), (
            f"nothing reported the absence of {missing}: {violations}"
        )

    def test_this_repository_still_passes(self):
        assert check_python_floor_consistency(REPO_ROOT) == []

    def test_the_pass_line_does_not_claim_more_coverage_than_the_matrix_has(self):
        """The report must name the CI set separately from the declared set.

        Written when 3.13 was declared and untested, this pinned that specific gap. The gap
        was closed on 2026-09-19 by adding 3.13 to the matrix, which made the premise false
        and this test fail -- correctly. What is worth keeping is not the gap but the
        wording: a PASS line that prints only the declared set reads as a coverage claim on
        any future tree where the two sets drift apart again.
        """
        assert set(PYTHON_CI_REQUIRED) <= set(PYTHON_SUPPORTED), (
            "CI cannot require a version that is not declared supported"
        )
        report = (REPO_ROOT / "scripts" / "harness_gate.py").read_text(encoding="utf-8")
        assert "classifiers {list(PYTHON_SUPPORTED)}" in report, (
            "the PASS line no longer names the declared set"
        )
        assert "CI covering {list(PYTHON_CI_REQUIRED)}" in report, (
            "the PASS line no longer names the CI set separately from the declared set, so it "
            "reads as though every supported version is tested"
        )


class TestGate8ComparesTheClassifiersAgainstTheMatrixItself:
    """A version the classifiers claim and no CI leg runs must fail, whatever the constants say.

    Every other gate-8 assertion routes through PYTHON_SUPPORTED or PYTHON_CI_REQUIRED, and
    every one of them is a containment or a membership. Shrinking both constants together
    therefore satisfies all of them at once: reverting PYTHON_CI_REQUIRED to
    ("3.12", "3.14") and shrinking the matrix to match made the gate print "all agree" over
    a declared 3.13 that no leg exercised, and left the suite green. The constants are the
    thing an editor changes to make the check agree with a wrong tree, so this check reads
    pyproject.toml and workflow.yml and compares them to each other.
    """

    @staticmethod
    def _write_tree(root: Path, classifiers: tuple[str, ...], matrix: tuple[str, ...]) -> None:
        """A tree that is well formed apart from the relation under test."""
        classifier_lines = "".join(
            f'    "Programming Language :: Python :: {v}",\n' for v in classifiers
        )
        (root / "pyproject.toml").write_text(
            "[project]\n"
            'name = "jnwb"\n'
            'requires-python = ">=3.12"\n'
            f"classifiers = [\n{classifier_lines}]\n",
            encoding="utf-8",
        )
        (root / ".readthedocs.yaml").write_text(
            'build:\n  tools:\n    python: "3.12"\n', encoding="utf-8"
        )
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True, exist_ok=True)
        matrix_entry = ", ".join(f'"{v}"' for v in matrix)
        (workflows / "workflow.yml").write_text(
            "jobs:\n  test:\n    strategy:\n      matrix:\n"
            f"        python-version: [ {matrix_entry} ]\n",
            encoding="utf-8",
        )

    def test_a_classifier_no_leg_runs_is_rejected(self, tmp_path: Path):
        self._write_tree(tmp_path, ("3.12", "3.13", "3.14"), ("3.12", "3.14"))
        violations = check_python_floor_consistency(tmp_path)
        assert any("PYTHON_CLASSIFIER_UNTESTED" in v and "3.13" in v for v in violations), (
            f"a tree declaring 3.13 whose matrix runs only 3.12 and 3.14 was accepted: {violations}"
        )

    def test_the_rejection_does_not_depend_on_the_constants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The reproduction: shrink both constants to the matrix and the defect must still fail.

        With PYTHON_CI_REQUIRED reverted, the matrix covers everything it requires and the
        classifier set still equals PYTHON_SUPPORTED, so checks 2 and 3 are both satisfied.
        Only a file-to-file comparison survives this.
        """
        import scripts.harness_gate as harness_gate

        monkeypatch.setattr(harness_gate, "PYTHON_CI_REQUIRED", ("3.12", "3.14"))
        self._write_tree(tmp_path, ("3.12", "3.13", "3.14"), ("3.12", "3.14"))
        violations = harness_gate.check_python_floor_consistency(tmp_path)
        assert any("PYTHON_CLASSIFIER_UNTESTED" in v and "3.13" in v for v in violations), (
            "shrinking PYTHON_CI_REQUIRED to match the shrunken matrix silenced the gate, "
            f"which is the defect this check exists to prevent: {violations}"
        )

    def test_a_matrix_that_runs_every_classifier_is_accepted(self, tmp_path: Path):
        self._write_tree(tmp_path, ("3.12", "3.13", "3.14"), ("3.12", "3.13", "3.14"))
        violations = check_python_floor_consistency(tmp_path)
        assert not any("PYTHON_CLASSIFIER_UNTESTED" in v for v in violations), (
            f"a matrix running every declared version was rejected: {violations}"
        )

    def test_this_repository_declares_nothing_it_does_not_run(self):
        violations = check_python_floor_consistency(REPO_ROOT)
        assert not any("PYTHON_CLASSIFIER_UNTESTED" in v for v in violations), violations


# --------------------------------------------------------------------- Gates 5 and 10
class TestGates5And10ReadEveryPage:
    """Both used `glob('*.md')`, so the nine pages under `docs/tutorials/` were never read."""

    def test_a_wrong_pin_under_a_subdirectory_is_rejected(self, tmp_path: Path):
        docs = tmp_path / "docs" / "tutorials"
        docs.mkdir(parents=True)
        (docs / "01_nwb_basics.md").write_text("pip install jnwb==0.0.9\n", encoding="utf-8")
        violations = check_docs_version_matches_package(tmp_path)
        assert violations, "a wrong version pin in docs/tutorials/ was never read"
        assert "0.0.9" in violations[0]

    def test_a_correct_pin_under_a_subdirectory_is_accepted(self, tmp_path: Path):
        import jnwb

        docs = tmp_path / "docs" / "tutorials"
        docs.mkdir(parents=True)
        (docs / "01_nwb_basics.md").write_text(
            f"pip install jnwb=={jnwb.__version__}\n", encoding="utf-8"
        )
        assert check_docs_version_matches_package(tmp_path) == []

    def test_a_symbol_documented_only_in_a_subdirectory_now_counts(self, tmp_path: Path):
        """The same blind spot in Gate 5 made it stricter, not weaker -- also wrong."""
        import jnwb

        docs = tmp_path / "docs"
        (docs / "tutorials").mkdir(parents=True)
        (docs / "tutorials" / "all.md").write_text(
            "\n".join(f"`jnwb.{name}`" for name in jnwb.__all__), encoding="utf-8"
        )
        assert check_public_symbols_documented(tmp_path) == []

    def test_the_repository_has_pages_that_only_rglob_reaches(self):
        flat = {p.name for p in (REPO_ROOT / "docs").glob("*.md")}
        nested = [
            p.relative_to(REPO_ROOT / "docs").as_posix()
            for p in (REPO_ROOT / "docs").rglob("*.md")
            if p.name not in flat or p.parent != REPO_ROOT / "docs"
        ]
        assert len(nested) >= 9, (
            f"only {len(nested)} nested pages; this test documented nine under docs/tutorials/"
        )


# --------------------------------------------------------------------------- Gate 13
class TestGate13ChecksBehaviourNotPresence:
    """A README saying REMOVED, tutorials that only raise, and a commented-out nav all passed."""

    @staticmethod
    def _tree(tmp_path: Path) -> Path:
        root = tmp_path / "tree"
        root.mkdir()
        shutil.copytree(REPO_ROOT / "examples", root / "examples")
        shutil.copytree(REPO_ROOT / "docs", root / "docs")
        shutil.copytree(REPO_ROOT / "skills", root / "skills")
        shutil.copy(REPO_ROOT / "README.md", root / "README.md")
        shutil.copy(REPO_ROOT / "mkdocs.yml", root / "mkdocs.yml")
        return root

    def test_the_unmodified_copy_passes(self, tmp_path: Path):
        """The control. Without it every assertion below could pass for the wrong reason."""
        assert check_nwb_onboarding_alignment(self._tree(tmp_path)) == []

    def test_a_readme_that_only_names_the_symbols_is_rejected(self, tmp_path: Path):
        root = self._tree(tmp_path)
        (root / "README.md").write_text(
            f"{', '.join(NWB_ONBOARDING_SYMBOLS)} are REMOVED in this release.\n",
            encoding="utf-8",
        )
        violations = check_nwb_onboarding_alignment(root)
        assert any("never calls" in v for v in violations), violations

    def test_tutorials_that_refuse_to_run_are_rejected(self, tmp_path: Path):
        root = self._tree(tmp_path)
        for script in (root / "examples" / "tutorials").glob("*.py"):
            script.write_text("raise SystemExit('nope')\n", encoding="utf-8")
        violations = check_nwb_onboarding_alignment(root)
        assert len([v for v in violations if "raises at module level" in v]) == 9, violations

    def test_a_tutorial_that_does_not_parse_is_rejected(self, tmp_path: Path):
        root = self._tree(tmp_path)
        (root / "examples" / "tutorials" / "03_spiking.py").write_text(
            "def main(:\n", encoding="utf-8"
        )
        violations = check_nwb_onboarding_alignment(root)
        assert any("does not parse" in v for v in violations), violations

    def test_a_commented_out_nav_entry_is_rejected(self, tmp_path: Path):
        root = self._tree(tmp_path)
        text = (root / "mkdocs.yml").read_text(encoding="utf-8")
        (root / "mkdocs.yml").write_text(
            text.replace(
                "tutorials/01_nwb_basics.md", "# tutorials/01_nwb_basics.md"
            ),
            encoding="utf-8",
        )
        violations = check_nwb_onboarding_alignment(root)
        assert any("not in the mkdocs nav" in v for v in violations), violations

    def test_the_nav_is_read_as_yaml(self, tmp_path: Path):
        """The premise: the nav really is a parseable structure, not just text."""
        config = yaml.safe_load((REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
        assert isinstance(config.get("nav"), list) and config["nav"]

    def test_a_skill_that_names_the_symbols_without_routing_them_is_rejected(self, tmp_path):
        root = self._tree(tmp_path)
        skill = root / "skills" / "jnwb-nwb-data" / "SKILL.md"
        skill.write_text(
            "This skill knows about " + ", ".join(NWB_ONBOARDING_SYMBOLS) + ".\n",
            encoding="utf-8",
        )
        violations = check_nwb_onboarding_alignment(root)
        assert any("never routes a call" in v for v in violations), violations


# ---------------------------------------------------------------------------- Gate 4
class TestGate4AllowlistCarriesNoDeadEntries:
    """Three one-off audit directories outlived the audit that made them."""

    def test_the_audit_scratch_directories_are_gone(self):
        for stale in ["_audit_dist", "_audit_dist2", "_audit_dist_build"]:
            assert stale not in EPHEMERAL_ROOT_DIRS, f"{stale} is still allowlisted"

    def test_every_allowlisted_file_is_tracked_or_deliberately_ignored(self):
        """Two entries are intentionally untracked, and the reason is written where they live.

        Tracked, not present: the first form of this test asked whether the file exists, so
        it passed on any machine carrying a leftover -- a `.coverage` from before 05-78
        removed `pytest-cov` -- and failed on all four CI cells, which check out clean. What
        the allowlist is claiming is that the entry corresponds to something the repository
        has, and a working tree's untracked residue is not that.
        """
        lines = (REPO_ROOT / "scripts" / "harness_gate.py").read_text(encoding="utf-8").splitlines()
        comments = [ln for ln in lines if ln.lstrip().startswith("#")]
        tracked = set(
            subprocess.run(
                ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
            ).stdout.split()
        )
        assert len(tracked) > 100, f"git ls-files returned {len(tracked)} paths"
        unexplained = sorted(
            name
            for name in ALLOWED_ROOT_FILES
            if name not in tracked
            and not any(name in ln and "git-ignored" in ln for ln in comments)
        )
        assert not unexplained, (
            f"allowlisted, untracked and unexplained -- prune these or say why: {unexplained}"
        )


# ------------------------------------------------- the docs link check (not a gate)
class TestTheDocsLinkScanReadsSubdirectories:
    """Same blind spot as Gates 5 and 10, in the test that guards the doc corpus.

    tests/test_docs_links.py globbed docs/*.md, so none of the nine pages under
    docs/tutorials/ had their links checked at all. Nothing could observe the repair:
    the scan was its own only caller, over a corpus that happens to have no broken link.
    """

    @staticmethod
    def _corpus(tmp_path: Path) -> Path:
        docs = tmp_path / "docs"
        (docs / "tutorials").mkdir(parents=True)
        (docs / "index.md").write_text("[api](api.md)\n", encoding="utf-8")
        (docs / "api.md").write_text("# API\n", encoding="utf-8")
        return docs

    def test_an_intact_corpus_reports_nothing(self, tmp_path: Path):
        docs = self._corpus(tmp_path)
        (docs / "tutorials" / "01_basics.md").write_text(
            "[back](../index.md)\n", encoding="utf-8"
        )
        assert broken_links(docs) == []

    def test_a_broken_link_in_a_subdirectory_is_reported(self, tmp_path: Path):
        docs = self._corpus(tmp_path)
        (docs / "tutorials" / "01_basics.md").write_text(
            "[gone](../deleted_page.md)\n", encoding="utf-8"
        )
        offenders = broken_links(docs)
        assert offenders == ["tutorials/01_basics.md -> ../deleted_page.md"], offenders

    def test_an_external_link_is_not_resolved(self, tmp_path: Path):
        docs = self._corpus(tmp_path)
        (docs / "tutorials" / "01_basics.md").write_text(
            "[site](https://example.invalid/nope.md)\n", encoding="utf-8"
        )
        assert broken_links(docs) == []

    def test_the_real_tutorial_pages_are_inside_the_scanned_corpus(self):
        """The subdirectory this was blind to is populated, so the coverage matters."""
        pages = sorted((REPO_ROOT / "docs" / "tutorials").glob("*.md"))
        assert len(pages) >= 9, [p.name for p in pages]
