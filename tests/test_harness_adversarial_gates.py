"""Adversarial Verification Probes for Harness Gates.

Tests that previously possible agent / subagent failure modes are now
mechanically caught and rejected by the harness gate.
"""
from __future__ import annotations

import ast
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended: prepending would also put the checkout's jnwb/ ahead of an
# installed copy and silently redirect a wheel-qualification run back to the source tree.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

import pytest

from scripts.harness_gate import (
    check_dataset_leakage,
    check_documented_api_matches_all,
    check_docs_version_matches_package,
    check_frozen_boundary,
    check_logarithm_last_rule,
    check_modality_isolation,
    validate_receipt_provenance,
)


class TestHarnessAdversarialProbes:
    def test_adversarial_probe_unauthorized_jnwb_import_rejected(self, tmp_path: Path):
        """Adversarial Probe 1: An unauthorized import from omission into jnwb must be rejected."""
        fake_jnwb = tmp_path / "jnwb"
        fake_jnwb.mkdir()
        # Create a clean file
        (fake_jnwb / "clean.py").write_text("import numpy as np\n", encoding="utf-8")
        assert len(check_frozen_boundary(fake_jnwb)) == 0
        
        # Inject an adversarial unauthorized import from omission
        bad_file = fake_jnwb / "leaked_feature.py"
        bad_file.write_text("import omission.jnwb_ext.trial_ontology as onto\n", encoding="utf-8")
        
        violations = check_frozen_boundary(fake_jnwb)
        assert len(violations) > 0, "Gate failed to catch unauthorized omission import!"
        assert "UNAUTHORIZED_IMPORT" in violations[0]
        assert "omission.jnwb_ext.trial_ontology" in violations[0]

    def test_adversarial_probe_missing_receipt_rejected(self, tmp_path: Path):
        """Adversarial Probe 2: A claim without an observed empirical receipt must be rejected."""
        # Non-existent receipt
        ok, msg = validate_receipt_provenance("Hypothetical Effect", tmp_path / "non_existent.csv")
        assert not ok
        assert "MISSING_RECEIPT" in msg

        # Zero-byte dummy receipt
        empty_file = tmp_path / "empty.csv"
        empty_file.touch()
        ok, msg = validate_receipt_provenance("Empty File Effect", empty_file)
        assert not ok
        assert "EMPTY_RECEIPT" in msg

    def test_adversarial_probe_logarithm_before_average_rejected(self):
        """Adversarial Probe 3: Averaging decibels when estimand is raw power must be caught."""
        # Bad code declaring raw power estimand but averaging dB
        bad_code = """
# estimand: raw_power_average
import numpy as np
def compute_site_power(raw_power):
    db = to_db(raw_power)
    return np.mean(db)
"""
        violations = check_logarithm_last_rule(bad_code)
        assert len(violations) > 0, "Gate failed to catch log-before-average violation when estimand is raw power!"
        assert "LOG_BEFORE_AVERAGE" in violations[0]

        # Good code: average raw power first, to_db once at the end
        good_code = """
# estimand: raw_power_average
import numpy as np
def compute_site_power_correct(raw_power):
    avg_power = np.mean(raw_power)
    return to_db(avg_power)
"""
        assert len(check_logarithm_last_rule(good_code)) == 0

    def test_adversarial_control_legitimate_mean_of_db_accepted(self):
        """Adversarial Control: Legitimate mean-of-dB code (e.g. log-normal stats) is NOT globally rejected."""
        legitimate_db_code = """
import numpy as np

def summarize_log_normal_effects(unit_db_modulations):
    \"\"\"Compute sample mean of decibel values across recorded units (geometric mean of power).\"\"\"
    mean_db = np.mean(unit_db_modulations)
    sem_db = np.std(unit_db_modulations) / np.sqrt(len(unit_db_modulations))
    return mean_db, sem_db
"""
        violations = check_logarithm_last_rule(legitimate_db_code)
        assert len(violations) == 0, "Legitimate mean-of-dB code was improperly rejected!"

    def test_adversarial_probe_unnamespaced_modality_pooling_rejected(self):
        """Adversarial Probe 4: Mixing SPK and LFP without explicit namespaces must be rejected."""
        # Bad feature list: mixes spikes and LFP channels with generic indices
        bad_features = ["channel_01", "unit_alpha", "power_theta", "channel_02"]
        ok, violations = check_modality_isolation(bad_features)
        assert not ok
        assert len(violations) > 0
        assert "UNNAMESPACED_MODALITY_POOLING" in violations[0]

        # Good feature list: strictly namespaced
        good_features = ["spk_unit_01", "spk_unit_02", "lfp_theta_ch01", "lfp_gamma_ch01"]
        ok, violations = check_modality_isolation(good_features)
        assert ok
        assert len(violations) == 0

    def test_adversarial_probe_root_allowlist_violation_rejected(self, tmp_path: Path):
        """Adversarial Probe 5: Disallowed files or directories at root must be rejected."""
        from scripts.harness_gate import check_root_allowlist
        # Valid root structure
        (tmp_path / "jnwb").mkdir()
        (tmp_path / "README.md").write_text("# Title\n", encoding="utf-8")
        assert len(check_root_allowlist(tmp_path)) == 0

        # Inject stray files/folders
        (tmp_path / "untracked_scratch.csv").write_text("a,b\n", encoding="utf-8")
        (tmp_path / "temp_analysis").mkdir()

        violations = check_root_allowlist(tmp_path)
        assert len(violations) == 2
        assert any("UNAUTHORIZED_ROOT_FILE" in v for v in violations)
        assert any("UNAUTHORIZED_ROOT_DIR" in v for v in violations)

    def test_adversarial_probe_undocumented_symbol_rejected(self, tmp_path: Path):
        """Adversarial Probe 6: Public symbol missing from docs/ must be caught."""
        from scripts.harness_gate import check_public_symbols_documented
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "api.md").write_text("# API\n`jnwb.compute_psd`\n", encoding="utf-8")

        violations = check_public_symbols_documented(tmp_path)
        # Should flag missing symbols from jnwb.__all__
        assert len(violations) > 0
        assert "UNDOCUMENTED_PUBLIC_SYMBOL" in violations[0]

    def test_adversarial_probe_dataset_leakage_rejected(self, tmp_path: Path):
        """Adversarial Probe 7: Experiment condition tokens and manuscript results must be caught."""
        from scripts.harness_gate import check_dataset_leakage
        fake_jnwb = tmp_path / "jnwb"
        fake_skills = tmp_path / "skills"
        fake_docs = tmp_path / "docs"
        fake_artifacts = tmp_path / "artifacts"
        fake_jnwb.mkdir()
        fake_skills.mkdir()
        fake_docs.mkdir()
        fake_artifacts.mkdir()

        # Clean generic neuroscience terms MUST be permitted (no naive word ban)
        clean_text = (
            "# Generic Electrophysiology Guide\n"
            "Analyze SPK unit spike trains and continuous LFP traces.\n"
            "Estimate response latency in theta, alpha, beta, and gamma frequency bands.\n"
        )
        (fake_jnwb / "clean.py").write_text("def compute_latency(spk, lfp, fs=1000.0): pass\n", encoding="utf-8")
        (fake_skills / "SKILL.md").write_text(clean_text, encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text(clean_text, encoding="utf-8")
        (fake_artifacts / "AGENTS.md").write_text(clean_text, encoding="utf-8")
        (fake_docs / "10_operation_specifications.md").write_text(clean_text, encoding="utf-8")

        assert len(check_dataset_leakage(tmp_path)) == 0, "Clean generic terms should not trigger violations!"

        # 1. Leak condition code into jnwb
        (fake_jnwb / "leaky.py").write_text("CONDITION = 'AXAB'\n", encoding="utf-8")
        v1 = check_dataset_leakage(tmp_path)
        assert len(v1) == 1 and "AXAB" in v1[0]
        (fake_jnwb / "leaky.py").unlink()

        # 2. Leak manuscript p-value into AGENTS.md
        (tmp_path / "AGENTS.md").write_text("The session-level test was p = 0.053\n", encoding="utf-8")
        v2 = check_dataset_leakage(tmp_path)
        assert len(v2) == 1 and "0.053" in v2[0]
        (tmp_path / "AGENTS.md").write_text(clean_text, encoding="utf-8")

        # 3. Leak study-specific finding into a docs/ page
        (fake_docs / "10_operation_specifications.md").write_text(
            "Found beta/gamma temporal resolvability > theta/alpha at session level\n", encoding="utf-8"
        )
        v3 = check_dataset_leakage(tmp_path)
        assert len(v3) >= 1 and any("beta/gamma" in v for v in v3)
        (fake_docs / "10_operation_specifications.md").write_text(clean_text, encoding="utf-8")

        # 4. Leak study-specific concept into the root AGENTS.md.
        # artifacts/AGENTS.md was a near-duplicate of the root file and was removed in
        # 0.1.3; the gate no longer scans that path.
        (tmp_path / "AGENTS.md").write_text("Study focuses on omission-linked dynamics\n", encoding="utf-8")
        v4 = check_dataset_leakage(tmp_path)
        assert len(v4) == 1 and "omission-linked" in v4[0]
        (tmp_path / "AGENTS.md").write_text(clean_text, encoding="utf-8")

        # 5. Leak forbidden causal assertion into skills
        (fake_skills / "SKILL.md").write_text("Demonstrates that LFP drives SPK\n", encoding="utf-8")
        v5 = check_dataset_leakage(tmp_path)
        assert len(v5) == 1 and "LFP drives SPK" in v5[0]

    def test_gate_6_ignores_study_prose_outside_forbidden_token_list(self, tmp_path: Path):
        """Gate 6 checks a fixed token list — not all study-specific comments."""
        from scripts.harness_gate import check_dataset_leakage
        fake_jnwb = tmp_path / "jnwb"
        fake_jnwb.mkdir()
        (fake_jnwb / "annotated.py").write_text(
            '# Corpus label "my_study_condition" is not on the Gate 6 list\n'
            "def compute_rate(): pass\n",
            encoding="utf-8",
        )
        assert check_dataset_leakage(tmp_path) == []

    def test_adversarial_probe_version_inconsistency_rejected(self, tmp_path: Path):
        """Adversarial Probe 8: Inconsistent package vs pyproject version must be caught."""
        from scripts.harness_gate import check_version_consistency
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "99.99.99"\n', encoding="utf-8")
        violations = check_version_consistency(tmp_path)
        assert len(violations) > 0
        assert "VERSION_INCONSISTENCY" in violations[0]

    def test_adversarial_probe_python_floor_inconsistency_rejected(self, tmp_path: Path):
        """Adversarial Probe 9: a floor below the declared one, with a stale classifier."""
        from scripts.harness_gate import check_python_floor_consistency
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nrequires-python = ">=3.10"\nclassifiers = ["Programming Language :: Python :: 3.10"]\n',
            encoding="utf-8"
        )
        violations = check_python_floor_consistency(tmp_path)
        assert any("PYTHON_FLOOR_INCONSISTENCY" in v for v in violations), violations
        assert any("PYTHON_CLASSIFIER_UNSUPPORTED" in v and "3.10" in v for v in violations), violations

    def test_adversarial_probe_python_upper_pin_rejected(self, tmp_path: Path):
        """Adversarial Probe 9b: THE 0.1.1 DEFECT. An upper pin must be rejected.

        `requires-python = ">=3.12, <3.13"` shipped in 0.1.1 and made the release
        uninstallable on every current interpreter -- pip silently resolved users back
        to 0.1.0, i.e. to *older code than they asked for*. The gate of the day
        **accepted** that string, because it had been written to enforce "3.12 only".
        This probe is the reason the gate was rewritten.
        """
        from scripts.harness_gate import check_python_floor_consistency
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nrequires-python = ">=3.12, <3.13"\n'
            'classifiers = [\n'
            '    "Programming Language :: Python :: 3.12",\n'
            '    "Programming Language :: Python :: 3.13",\n'
            '    "Programming Language :: Python :: 3.14",\n'
            ']\n',
            encoding="utf-8"
        )
        violations = check_python_floor_consistency(tmp_path)
        assert any("PYTHON_UPPER_PIN" in v for v in violations), (
            "an upper pin on a pure-Python wheel must be rejected; got: " + repr(violations)
        )

    def test_adversarial_probe_ci_matrix_missing_head_rejected(self, tmp_path: Path):
        """Adversarial Probe 9c: dropping the newest tested interpreter must be caught.

        A matrix narrowed back to the floor alone is how a "3.12 only" policy gets
        reintroduced by accident.
        """
        from scripts.harness_gate import PYTHON_CI_REQUIRED, check_python_floor_consistency
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "workflow.yml").write_text(
            'jobs:\n  test:\n    strategy:\n      matrix:\n'
            f'        python-version: [ "{PYTHON_CI_REQUIRED[0]}" ]\n',
            encoding="utf-8"
        )
        violations = check_python_floor_consistency(tmp_path)
        assert any(
            "PYTHON_CI_UNTESTED" in v and PYTHON_CI_REQUIRED[-1] in v for v in violations
        ), violations

    def test_declared_support_and_ci_policy_are_coherent(self):
        """The policy constants themselves must not drift apart."""
        from scripts.harness_gate import PYTHON_CI_REQUIRED, PYTHON_FLOOR, PYTHON_SUPPORTED
        assert PYTHON_SUPPORTED[0] == PYTHON_FLOOR, "the floor must be the lowest supported version"
        assert set(PYTHON_CI_REQUIRED) <= set(PYTHON_SUPPORTED), "CI must not test an undeclared version"
        assert PYTHON_FLOOR in PYTHON_CI_REQUIRED, "the floor must be tested"
        assert PYTHON_SUPPORTED[-1] in PYTHON_CI_REQUIRED, "the newest declared version must be tested"

    def test_adversarial_probe_hardcoded_test_paths_rejected(self, tmp_path: Path):
        """Adversarial Probe 10: Hardcoded machine-local test paths must be caught."""
        from scripts.harness_gate import check_no_hardcoded_test_paths
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_leaky.py").write_text('TEST_FILE = "D:/analysis/nwb/real.nwb"\n', encoding="utf-8")
        violations = check_no_hardcoded_test_paths(tmp_path)
        assert len(violations) == 1
        assert "HARDCODED_TEST_PATH" in violations[0]

    def test_real_repository_passes_all_harness_gates(self):
        """Integrity Probe: Live repository state must pass all preflight gates."""
        from scripts.harness_gate import run_full_preflight
        assert run_full_preflight() is True


class TestDocumentationDriftGates:
    """Gates 9 and 10 exist because prose cannot hold a fact true.

    docs/memory.md once claimed "exactly 105 public symbols" while the package exported 111 --
    stale within a single release cycle, in the document agents are told to read, with nothing
    failing. These probes assert the gates catch that class of drift rather than merely passing
    on a currently-clean tree.
    """

    @staticmethod
    def _scratch_repo(tmp_path: Path) -> Path:
        import shutil
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        for rel in ("docs/api.md", "mkdocs.yml", "README.md"):
            shutil.copy(REPO_ROOT / rel, tmp_path / rel)
        return tmp_path

    def test_clean_tree_passes_both_gates(self, tmp_path):
        from scripts.generate_api_md import check_api_md_is_generated
        repo = self._scratch_repo(tmp_path)
        assert check_documented_api_matches_all(repo) == []
        assert check_api_md_is_generated(repo) == []
        assert check_docs_version_matches_package(repo) == []

    def test_api_md_generator_drift_is_caught(self, tmp_path):
        from scripts.generate_api_md import check_api_md_is_generated
        repo = self._scratch_repo(tmp_path)
        api = repo / "docs/api.md"
        api.write_text(api.read_text(encoding="utf-8") + "\n<!-- drift -->\n", encoding="utf-8")
        violations = check_api_md_is_generated(repo)
        assert any("API_MD_DRIFT" in v for v in violations)

    def test_phantom_api_row_is_caught(self, tmp_path):
        """A reference row left behind for a symbol that no longer exists."""
        repo = self._scratch_repo(tmp_path)
        api = repo / "docs/api.md"
        api.write_text(api.read_text(encoding="utf-8")
                       + "\n| jnwb.removed_helper | function | removed_helper()<br>*gone* |\n",
                       encoding="utf-8")
        violations = check_documented_api_matches_all(repo)
        assert any("PHANTOM_API_ROW" in v and "removed_helper" in v for v in violations)

    def test_undocumented_export_is_caught(self, tmp_path):
        """An export with no reference row."""
        repo = self._scratch_repo(tmp_path)
        api = repo / "docs/api.md"
        api.write_text(api.read_text(encoding="utf-8").replace(
            "| jnwb.aggregate_to_db |", "| jnwb.NOTHERE_x |", 1), encoding="utf-8")
        violations = check_documented_api_matches_all(repo)
        assert any("UNDOCUMENTED_EXPORT" in v and "aggregate_to_db" in v for v in violations)

    def test_stale_duplicated_version_in_mkdocs_is_caught(self, tmp_path):
        import jnwb
        repo = self._scratch_repo(tmp_path)
        mk = repo / "mkdocs.yml"
        mk.write_text(mk.read_text(encoding="utf-8").rstrip()
                      + '\nextra:\n  jnwb_version: "0.0.9"\n', encoding="utf-8")
        violations = check_docs_version_matches_package(repo)
        assert any("DOCS_VERSION_MISMATCH" in v and "mkdocs.yml" in v for v in violations)
        assert jnwb.__version__ != "0.0.9"

    def test_stale_install_pin_in_prose_is_caught(self, tmp_path):
        repo = self._scratch_repo(tmp_path)
        rd = repo / "README.md"
        rd.write_text(rd.read_text(encoding="utf-8")
                      + "\npip install jnwb==0.0.9\n", encoding="utf-8")
        violations = check_docs_version_matches_package(repo)
        assert any("DOCS_VERSION_MISMATCH" in v and "README.md" in v for v in violations)

    def test_sphinx_toolchain_is_fully_removed(self):
        """Removing a toolchain means removing its config, deps, and CI leg together."""
        assert not (REPO_ROOT / "docs" / "conf.py").exists()
        assert not (REPO_ROOT / "docs" / "_static").exists()
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        for dep in ("sphinx", "myst-parser"):
            assert dep not in pyproject, f"{dep} still declared in pyproject.toml"
        workflow = (REPO_ROOT / ".github/workflows/workflow.yml").read_text(encoding="utf-8")
        assert "sphinx" not in workflow.lower(), "CI still runs a sphinx build"

    def test_no_hardcoded_symbol_counts_remain_in_prose(self):
        """The original defect: a symbol count written into documentation."""
        import re
        pattern = re.compile(r"\b\d{2,4}\s+(?:public\s+|exported\s+)?symbols\b", re.IGNORECASE)
        offenders = []
        for path in [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md"))]:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    offenders.append(f"{path.name}:{line_no}: {line.strip()}")
        assert offenders == [], (
            "hardcoded symbol counts found; state the invariant and let gate 9 check it "
            "instead: " + "; ".join(offenders))


class TestGateNumberingIntegrity:
    """A gate report that cites "Gate 9" must name exactly one gate.

    The original defect: docstring numbers drifted from the preflight sequence until
    "Gate 9" named both the API-set-equality gate and the Python-target gate, and
    "Gate 2", "Gate 3" and "Gate 6" were each used twice. Numbers are only meaningful
    if they are unique, so the numbering is checked rather than asserted.
    """

    @staticmethod
    def _numbered_gates() -> dict[int, str]:
        """Map gate number -> function name, read from harness_gate.py docstrings."""
        import re

        source = (REPO_ROOT / "scripts" / "harness_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        found: dict[int, list[str]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            doc = ast.get_docstring(node) or ""
            match = re.match(r"Gate (\d+)\b", doc)
            if match:
                found.setdefault(int(match.group(1)), []).append(node.name)
        duplicates = {n: names for n, names in found.items() if len(names) > 1}
        assert duplicates == {}, f"gate number reused by more than one gate: {duplicates}"
        return {n: names[0] for n, names in found.items()}

    def test_gate_numbers_are_unique(self):
        self._numbered_gates()

    def test_gate_numbers_are_contiguous_from_one(self):
        numbers = sorted(self._numbered_gates())
        assert numbers == list(range(1, len(numbers) + 1)), (
            f"gate numbers must be contiguous from 1; got {numbers}"
        )

    @staticmethod
    def _runner_order() -> list[str]:
        """The check each gate runs, in the order the runner runs them, read from GATES.

        These two tests searched `run_full_preflight`'s source text for ``name()``. That worked
        while the runner was a straight line of calls, and stopped working on 2026-09-19 when it
        became a table so that one failing gate could no longer stop the rest. The invariant is
        unchanged -- the number is the execution position -- but `GATES` is now where execution
        order lives, and reading the structure beats grepping the function that walks it.
        """
        import inspect

        from scripts import harness_gate

        known = {
            name for name in dir(harness_gate)
            if name.startswith("check_") and callable(getattr(harness_gate, name))
        }
        names = []
        for _number, run, _pass_line in harness_gate.GATES:
            # An entry is either a check wrapped by `_one`, which closes over it, or a bespoke
            # adapter that calls its checks in its body. Take the closure when there is one, and
            # otherwise read the adapter's source -- the adapter is the gate's only caller.
            closed = [
                cell.cell_contents.__name__
                for cell in (run.__closure__ or ())
                if callable(cell.cell_contents) and cell.cell_contents.__name__ in known
            ]
            if closed:
                names.extend(closed)
                continue
            body = inspect.getsource(run)
            names.extend(sorted(
                (name for name in known if f"{name}()" in body),
                key=lambda n: body.find(f"{n}()"),
            ))
        return names

    def test_gate_numbers_follow_preflight_execution_order(self):
        """The number IS the position in the runner's table, not a free label."""
        numbered = self._numbered_gates()
        order = self._runner_order()
        expected = [numbered[n] for n in sorted(numbered)]
        ran = [name for name in order if name in set(numbered.values())]
        assert ran == expected, (
            "gate numbering disagrees with the runner's order:\n"
            f"  by number: {expected}\n"
            f"  by table:  {ran}"
        )

    def test_every_numbered_gate_runs_in_preflight(self):
        """An unnumbered helper is fine; a numbered gate that never runs is not."""
        order = set(self._runner_order())
        orphans = [name for name in self._numbered_gates().values() if name not in order]
        assert orphans == [], f"numbered gates absent from the runner's table: {orphans}"

    def test_the_runner_declares_exactly_the_numbered_gates(self):
        """Neither direction may drift: no unnumbered entry in the table, no gate left out."""
        from scripts import harness_gate

        numbered = self._numbered_gates()
        assert len(harness_gate.GATES) == len(numbered), (
            f"{len(harness_gate.GATES)} entries in the runner's table against "
            f"{len(numbered)} numbered gates"
        )
        assert [n for n, _, _ in harness_gate.GATES] == sorted(numbered), (
            "the table's numbers are not the docstring numbers in order"
        )


class TestImportShadowingGate:
    """JNWB-002: a user project cloned inside the library checkout shadowed itself.

    The editable install writes a .pth containing the repository root, so any top-level
    package beside jnwb/ is importable ahead of a consumer's own package of the same
    name -- silently, from any working directory. 88 of 190 importing files took the
    wrong copy and disagreed on an anatomical label. No error was raised.
    """

    def test_clean_root_passes(self, tmp_path: Path):
        from scripts.harness_gate import check_no_shadow_packages
        (tmp_path / "jnwb").mkdir()
        (tmp_path / "jnwb" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "docs").mkdir()
        assert check_no_shadow_packages(tmp_path) == []

    def test_adversarial_probe_cloned_user_project_rejected(self, tmp_path: Path):
        """The exact JNWB-002 shape: a consumer project cloned inside the library."""
        from scripts.harness_gate import check_no_shadow_packages
        (tmp_path / "jnwb").mkdir()
        (tmp_path / "jnwb" / "__init__.py").write_text("", encoding="utf-8")
        shadow = tmp_path / "omission"
        shadow.mkdir()
        (shadow / "__init__.py").write_text("", encoding="utf-8")
        violations = check_no_shadow_packages(tmp_path)
        assert len(violations) == 1, violations
        assert "SHADOW_PACKAGE" in violations[0] and "omission" in violations[0]

    def test_gitignored_shadow_is_still_rejected(self, tmp_path: Path):
        """.gitignore hiding it from `git status` is the reason the gate exists."""
        from scripts.harness_gate import check_no_shadow_packages
        (tmp_path / "jnwb").mkdir()
        (tmp_path / "jnwb" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / ".gitignore").write_text("shadowlib/\n", encoding="utf-8")
        (tmp_path / "shadowlib").mkdir()
        (tmp_path / "shadowlib" / "__init__.py").write_text("", encoding="utf-8")
        assert any("shadowlib" in v for v in check_no_shadow_packages(tmp_path))

    def test_non_package_directory_is_not_flagged(self, tmp_path: Path):
        """A plain directory is harmless; only an __init__.py makes it importable."""
        from scripts.harness_gate import check_no_shadow_packages
        (tmp_path / "jnwb").mkdir()
        (tmp_path / "jnwb" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "artifacts").mkdir()
        (tmp_path / "artifacts" / "notes.md").write_text("x\n", encoding="utf-8")
        assert check_no_shadow_packages(tmp_path) == []

    def test_internal_root_packages_are_excluded_from_the_wheel(self):
        """scripts/ and tests/ are allowed at the root only because they never ship."""
        import tomllib

        from scripts.harness_gate import INTERNAL_ROOT_PACKAGES

        config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        find = config["tool"]["setuptools"]["packages"]["find"]
        include, exclude = find.get("include", []), find.get("exclude", [])
        assert include == ["jnwb*"], f"only jnwb may be packaged; got {include}"
        for name in INTERNAL_ROOT_PACKAGES:
            assert any(pattern.startswith(name) for pattern in exclude), (
                f"{name!r} is allowed at the repository root on the promise that it is "
                f"excluded from the distribution, but pyproject excludes {exclude}"
            )

class TestProjectIdentifierGate:
    """Gate 12 must catch a project name used as data, the 0.1.3 MCP defect."""

    @staticmethod
    def _repo(tmp_path, source):
        pkg = tmp_path / "jnwb"
        pkg.mkdir()
        (pkg / "mod.py").write_text(source, encoding="utf-8")
        return tmp_path

    def test_catches_project_table_used_as_default(self, tmp_path):
        from scripts.harness_gate import check_no_project_identifiers_in_code

        repo = self._repo(tmp_path, "def f(t):\n    if 'omission_glo_passive' in t:\n        return 1\n")
        v = check_no_project_identifiers_in_code(repo)
        assert len(v) == 1 and "omission_glo_passive" in v[0]

    def test_catches_project_name_in_identifier(self, tmp_path):
        from scripts.harness_gate import check_no_project_identifiers_in_code

        repo = self._repo(tmp_path, "omission_window = (0, 1)\n")
        assert len(check_no_project_identifiers_in_code(repo)) == 1

    def test_docstrings_comments_and_deprecated_env_vars_pass(self, tmp_path):
        from scripts.harness_gate import check_no_project_identifiers_in_code

        source = (
            '"""Promoted from omission.jnwb_ext."""\n'
            "# history: came from the omission project\n"
            "LEGACY = 'OMISSION_NWB_DIR'\n"
            "def f():\n"
            '    """Omission-era helper."""\n'
            "    return 1\n"
        )
        assert check_no_project_identifiers_in_code(self._repo(tmp_path, source)) == []

    def test_live_package_is_clean(self):
        from scripts.harness_gate import check_no_project_identifiers_in_code

        assert check_no_project_identifiers_in_code() == []


class TestHarnessResetContracts:
    """Deterministic tests for generalized harness reset structure and invariants."""

    def test_jnwb_fact_action_skill_exists_and_is_routable(self):
        skill_path = REPO_ROOT / "skills" / "jnwb-fact-action" / "SKILL.md"
        assert skill_path.exists(), "skills/jnwb-fact-action/SKILL.md must exist"
        text = skill_path.read_text(encoding="utf-8")
        assert "F -> R -> A -> V -> S" in text
        assert "High freedom in hypothesis generation; zero freedom in project-fact completion" in text

        router_text = (REPO_ROOT / "skills" / "jnwb" / "SKILL.md").read_text(encoding="utf-8")
        assert "jnwb-fact-action" in router_text, "Router skills/jnwb/SKILL.md must route substantial work to jnwb-fact-action"

    def test_all_referenced_domain_skills_exist(self):
        skills_dir = REPO_ROOT / "skills"
        assert skills_dir.exists()
        skill_names = {d.name for d in skills_dir.iterdir() if d.is_dir()}

        # Verify all 7 domain skills plus router and execution-control skill
        expected = {
            "jnwb",
            "jnwb-fact-action",
            "jnwb-nwb-data",
            "jnwb-spiking",
            "jnwb-lfp-spectral",
            "jnwb-statistics",
            "jnwb-population",
            "jnwb-connectivity",
            "jnwb-figures",
        }
        assert expected.issubset(skill_names), f"Missing expected skills: {expected - skill_names}"

    def test_mandatory_authority_loading_order_delegates_to_the_canonical_authority(self):
        """The skill points at the one loading order; it does not carry a second one.

        This asserted that five hardcoded strings appeared in the file, which passed whenever the
        text matched that literal, whatever the order meant -- and it green-lit precisely the
        five-source list P-14 showed was wrong. Recorded as P-42, the fourth instance of P-37:
        "these strings appear" was the proxy, "the skill delegates the order" is the invariant.
        Ruled 2026-09-19 (06-61, candidate C).
        """
        skill_text = (REPO_ROOT / "skills" / "jnwb-fact-action" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        section = self._loading_order_section(skill_text)

        # The directive is the FIRST paragraph, by position. Selecting it by "contains must"
        # let 06-64 add a later paragraph carrying `MUST` and a mention of the section while the
        # real directive was gone; `\bMUST\b` also matches `MUST NOT`, so a repudiation of the
        # pointer read as the pointer. Position cannot be gamed by adding prose further down.
        paragraphs = [p for p in re.split(r"\n\s*\n", section.strip()) if p.strip()]
        assert paragraphs, (
            f"the skill's loading-order section is empty. It says:\n{section[:400]}"
        )
        directive = paragraphs[0]
        assert re.search(r"\b(MUST|must)\b", directive), (
            f"the skill's loading-order section opens with no requirement:\n{directive[:400]}"
        )
        assert not re.search(r"\b(MUST NOT|must not|obsolete|superseded|do not use)\b", directive), (
            "the loading directive negates or retires the authority it should delegate to:\n"
            f"{directive[:400]}"
        )
        target = self._canonical_section_reference(directive)
        assert target, (
            "the skill's loading directive does not point at a section of AGENTS.md, which is the "
            f"sole loading-order authority. The directive says:\n{directive[:400]}"
        )

        # Resolve the pointer. The skill said "§3" while nothing checked that AGENTS.md's §3 is
        # the loop; renumbering AGENTS.md left the skill pointing at whatever landed there.
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        heading = re.search(rf"(?m)^## {re.escape(target)}\. (.+)$", agents)
        assert heading, (
            f"the skill points at AGENTS.md §{target}, which has no such numbered section"
        )
        assert "Loop" in heading.group(1), (
            f"the skill points at AGENTS.md §{target}, which is {heading.group(1)!r}, not the Loop "
            "that carries Prepare's loading order"
        )

        # Scan the WHOLE skill, not §2: 06-64 moved the order into §4 and left a decoy §2.
        # Accept dashes and asterisks as well as numerals -- an ordered list written with bullets
        # is still a second copy of the order.
        enumerated = re.findall(
            r"(?m)^\s*(?:\d+\.|[-*])\s+`?(artifacts/\w+\.md|AGENTS\.md)`?", skill_text
        )
        assert not enumerated, (
            "the skill carries its own ordered source list again. A second copy of the order is "
            f"the mechanism that produced P-14: {enumerated}"
        )

    def test_the_canonical_loading_order_reaches_every_slot_in_order(self):
        """Delegation is only worth having if the target order is complete AND ordered.

        This asserted five substrings were present -- a membership check, which is the same
        "these strings appear" proxy the commit retiring P-42 claimed to remove, reinstated one
        file over. 06-64 scrambled Prepare's order and negated it outright; both passed. An order
        is a sequence, so the assertion is on indices.
        """
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        prepare = agents.split("- **Prepare**", 1)[1].split("- **Review**", 1)[0]

        assert not re.search(r"\b(do NOT load|do not load|must not load)\b", prepare), (
            f"Prepare tells the reader not to load its own list:\n{prepare[:400]}"
        )

        # The order Prepare must state. `goal` before `fact` is the substantive part: a fact is
        # not proof that state satisfies the goal, so the goal is read first.
        expected = [
            "AGENTS.md",
            "artifacts/goal.md",
            "artifacts/fact_stack.md",
            "artifacts/state.md",
            "artifacts/problem_stack.md",
            "artifacts/todo_stack.md",
        ]
        positions = {}
        for source in expected:
            index = prepare.find(source)
            assert index >= 0, (
                f"AGENTS.md §3 Prepare never loads {source}, so a packet following it cannot rank "
                "a slot it never reads"
            )
            positions[source] = index
        actual = sorted(expected, key=positions.get)
        assert actual == expected, (
            "AGENTS.md §3 Prepare loads its sources out of order:\n"
            f"  declared: {expected}\n  found:    {actual}"
        )

    @staticmethod
    def _canonical_section_reference(directive: str) -> "str | None":
        """The AGENTS.md section number a directive delegates to, or None."""
        match = re.search(r"`?AGENTS\.md`?\s*(?:§|section\s*)(\d+)", directive)
        return match.group(1) if match else None

    @staticmethod
    def _loading_order_section(skill_text: str) -> str:
        """The skill's loading-order section, found by HEADING TEXT rather than by number.

        Matching `## 2.` let 06-64 move the order to §4 and leave a decoy §2 behind. The section
        is identified by what it is called, and the next `##` at any number ends it.
        """
        # `[^\n]*` for the heading line, not `.*` -- under re.S a dot crosses newlines and the
        # heading match swallows the file, leaving an empty body. SKILL.md is CRLF, so the body
        # is normalised before it is split into paragraphs.
        match = re.search(
            r"(?mi)^##+ [\d.]*\s*[^\n]*Authority Loading Order[^\n]*\n(.*?)(?=^##+ )",
            skill_text,
            re.S,
        )
        assert match, (
            "the skill has no Authority Loading Order section; the sweep is wrong, or the section "
            "was renamed, and either way this test cannot report on what it did not find"
        )
        return match.group(1).replace("\r\n", "\n")

    def test_fact_stack_human_authorization_rule_preserved_in_instructions(self):
        fact_stack = (REPO_ROOT / "artifacts" / "fact_stack.md").read_text(encoding="utf-8")
        assert "Human-authorized durable facts" in fact_stack
        assert "Hamm" in fact_stack

        skill_text = (REPO_ROOT / "skills" / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        assert "fact_stack.md` is strictly human-authorized" in skill_text

    def test_role_definitions_exist_and_role_domain_orthogonal(self):
        expected_roles = {"authority", "critic", "actor", "verifier", "docs-harness",
                          "jnwb-developer"}
        agents_dir = REPO_ROOT / "artifacts" / "agents"
        assert agents_dir.exists()

        existing_role_files = {p.stem for p in agents_dir.glob("*.md")}
        assert expected_roles == existing_role_files, f"Role files mismatch: {existing_role_files ^ expected_roles}"

        # The ROLE enum in the delegation contract was a field name nothing read: a role
        # could be added here and never offered to a dispatcher, or listed there and have
        # no definition to load. Both halves now have to agree.
        skill_text = (REPO_ROOT / "skills" / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        enum_line = re.search(r"^ROLE:\s*(.+)$", skill_text, re.MULTILINE)
        assert enum_line, "skills/jnwb-fact-action/SKILL.md has no ROLE: enum to validate"
        enumerated = {r.strip() for r in enum_line.group(1).split("|")}
        assert enumerated == existing_role_files, (
            f"ROLE enum and artifacts/agents/ disagree: {enumerated ^ existing_role_files}"
        )

        # Roles must be domain-orthogonal and consume domain skills
        for role in expected_roles:
            role_text = (agents_dir / f"{role}.md").read_text(encoding="utf-8")
            assert "domain skill" in role_text.lower(), f"Role {role} must reference domain skill consumption"
            assert "role" in role_text.lower()

    def test_actor_cannot_be_sole_verifier_contract(self):
        skill_text = (REPO_ROOT / "skills" / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        assert "actor" in skill_text and "sole verifier" in skill_text

        actor_text = (REPO_ROOT / "artifacts" / "agents" / "actor.md").read_text(encoding="utf-8")
        assert "Cannot Be Sole Verifier" in actor_text

        verifier_text = (REPO_ROOT / "artifacts" / "agents" / "verifier.md").read_text(encoding="utf-8")
        assert "Independent Verification" in verifier_text

    def test_roles_are_vendor_neutral_and_project_neutral(self):
        agents_dir = REPO_ROOT / "artifacts" / "agents"
        forbidden_vendors = ["claude", "sonnet", "haiku", "opus", "openai", "gpt-", "gemini"]
        forbidden_projects = ["omission"]

        for md in agents_dir.glob("*.md"):
            text = md.read_text(encoding="utf-8").lower()
            for v in forbidden_vendors:
                assert v not in text, f"Role {md.name} contains vendor/model name {v!r}"
            for p in forbidden_projects:
                assert p not in text, f"Role {md.name} contains downstream project name {p!r}"

    def test_delegation_packet_and_return_contracts_exist(self):
        skill_text = (REPO_ROOT / "skills" / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        packet_fields = [
            "ROLE:", "DOMAIN SKILL:", "GOAL:", "TODO ITEM:", "AUTHORITIES:",
            "RELEVANT FACTS:", "OBSERVED BASELINE:", "INVARIANTS:",
            "ALLOWED SCOPE:", "ACCEPTANCE:", "STOP CONDITIONS:",
        ]
        for field in packet_fields:
            assert field in skill_text, f"Missing delegation packet field {field}"

        return_fields = [
            "RESULT:", "CLAIMS:", "SMALLEST ACTION:", "VERIFICATION:", "UNRESOLVED:",
        ]
        for field in return_fields:
            assert field in skill_text, f"Missing return contract field {field}"

    def test_conflicting_conclusions_require_evidence_reconciliation(self):
        skill_text = (REPO_ROOT / "skills" / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        assert "Evidence Reconciliation" in skill_text
        assert "never through voting" in skill_text


class TestGate6RecursiveCoverage:
    """Gate 6 must see nested user-facing surfaces, not only the top level.

    An audit of this gate read its docstring instead of its globs and reported a coverage gap
    under docs/tutorials/ that did not exist -- the docstring described ``docs/*.md`` while the
    code already walked ``docs/**/*.md``. The docstring is fixed; these probes pin the actual
    surface so neither the code nor the description can drift again unnoticed.

    Genuinely unscanned at the time, and now covered: README.md, CONTRIBUTING.md,
    examples/quickstart_jnwb.py, examples/notebooks/*.ipynb, and non-numbered example modules.
    """

    TOKEN = "AXAB"          # an experiment condition token from the gate's own forbidden list

    def _plant(self, tmp_path: Path, rel: str) -> list:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# scratch surface\n{self.TOKEN}\n", encoding="utf-8")
        return check_dataset_leakage(tmp_path)

    @pytest.mark.parametrize("rel", [
        "docs/tutorials/99_planted.md",
        "docs/tutorials/deeply/nested/99_planted.md",
        "examples/tutorials/99_planted.py",
        "examples/tutorials/_support_planted.py",
        "examples/quickstart_planted.py",
        "examples/notebooks/99_planted.ipynb",
        "README.md",
        "CONTRIBUTING.md",
    ])
    def test_forbidden_token_is_detected_on_every_durable_surface(self, tmp_path, rel):
        violations = self._plant(tmp_path, rel)
        assert any(rel in v for v in violations), (
            f"gate 6 did not detect {self.TOKEN} planted at {rel}; "
            f"violations={violations}")

    def test_changelog_is_exempt_and_the_exemption_is_documented(self, tmp_path):
        """An exemption must be a named decision, not a silent skip."""
        from scripts.harness_gate import DATASET_SCAN_EXEMPT
        violations = self._plant(tmp_path, "CHANGELOG.md")
        assert not any("CHANGELOG.md" in v for v in violations)
        assert "CHANGELOG.md" in DATASET_SCAN_EXEMPT
        assert DATASET_SCAN_EXEMPT["CHANGELOG.md"].strip(), "exemption must carry a reason"

    def test_docstring_matches_the_globs_it_claims(self):
        """The defect that caused the false audit finding: a docstring narrower than the code."""
        from scripts.harness_gate import check_dataset_leakage as gate
        doc = gate.__doc__ or ""
        for claim in ["docs/**/*.md", "examples/**/*.py", "jnwb/**/*.py", "skills/**/*.md"]:
            assert claim in doc, f"gate 6 docstring omits its own scanned surface: {claim}"
        assert "recursively" in doc.lower(), (
            "docstring must state that the scan is recursive; the non-recursive claim is "
            "what made an auditor believe docs/tutorials/ was unscanned")

    def test_probe_targets_correspond_to_real_repository_surfaces(self):
        """The planted-token probes above are only meaningful if these files really exist.

        Without this, a rename could leave the parametrized probes passing against paths the
        repository no longer has -- green tests covering nothing.
        """
        from scripts.harness_gate import DATASET_SCAN_ROOT_DOCS
        for rel in ["README.md", "CONTRIBUTING.md", "examples/quickstart_jnwb.py"]:
            assert (REPO_ROOT / rel).exists(), f"probe target missing: {rel}"
        assert "README.md" in DATASET_SCAN_ROOT_DOCS


class TestDeclaredEnvironmentPreflight:
    """Release qualification must verify the environment it claims to qualify.

    An RC audit measured "1 failed, 1021 passed" on an interpreter lacking the declared `docs`
    tooling, where the strict-MkDocs test could not import MkDocs. The repository contract
    (pyproject `docs` extra + CI installing `.[test,docs]` on every matrix leg) was already
    correct -- the local environment was not provisioned to it. A missing extra must therefore
    fail loudly and early, not silently change what the suite measures.
    """

    def test_declared_requirements_include_the_docs_toolchain(self):
        from scripts.release_gate import declared_extra_requirements
        names = declared_extra_requirements()
        assert "mkdocs" in names, "the docs extra must declare mkdocs; a test hard-requires it"
        assert "pytest" in names

    def test_self_referential_aggregate_extra_is_not_treated_as_a_distribution(self):
        """`all = ["jnwb[mcp,torch,gpu,test,docs]"]` must not be probed as a package name."""
        from scripts.release_gate import declared_extra_requirements
        names = declared_extra_requirements(extras=("all",))
        assert not any(n.startswith("jnwb") for n in names), names

    def test_version_specifiers_and_markers_are_stripped(self):
        from scripts.release_gate import declared_extra_requirements
        for name in declared_extra_requirements():
            assert not any(ch in name for ch in "<>=!~[; "), f"unparsed specifier: {name!r}"

    def test_missing_distribution_is_reported(self, monkeypatch):
        import scripts.release_gate as rg
        from importlib.metadata import PackageNotFoundError

        def fake_distribution(name):
            if name == "mkdocs":
                raise PackageNotFoundError(name)
            return object()

        monkeypatch.setattr("importlib.metadata.distribution", fake_distribution)
        assert "mkdocs" in rg.verify_declared_environment()

    def test_fully_provisioned_interpreter_reports_nothing_missing(self, monkeypatch):
        """On an interpreter carrying the declared tooling, the preflight is silent."""
        import scripts.release_gate as rg

        monkeypatch.setattr("importlib.metadata.distribution", lambda name: object())
        assert rg.verify_declared_environment() == []
