"""Adversarial Verification Probes for Harness Gates.

Tests that previously possible agent / subagent failure modes are now
mechanically caught and rejected by the harness gate.
"""
from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from scripts.harness_gate import (
    check_frozen_boundary,
    check_modality_isolation,
    omission_check_logarithm_last_rule,
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
        """Adversarial Probe 3: Averaging decibels before power normalization must be caught."""
        # Bad code: average across sites of to_db(power)
        bad_code = """
import numpy as np
def compute_site_power(raw_power):
    db = to_db(raw_power)
    return np.mean(db)
"""
        violations = omission_check_logarithm_last_rule(bad_code)
        assert len(violations) > 0, "Gate failed to catch log-before-average violation!"
        assert "LOG_BEFORE_AVERAGE" in violations[0]

        # Good code: average raw power first, to_db once at the end
        good_code = """
import numpy as np
def compute_site_power_correct(raw_power):
    avg_power = np.mean(raw_power)
    return to_db(avg_power)
"""
        assert len(omission_check_logarithm_last_rule(good_code)) == 0

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
        (fake_docs / "11_extending_and_development.md").write_text(clean_text, encoding="utf-8")

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

        # 3. Leak study-specific finding into docs/11_extending_and_development.md
        (fake_docs / "11_extending_and_development.md").write_text(
            "Found beta/gamma temporal resolvability > theta/alpha at session level\n", encoding="utf-8"
        )
        v3 = check_dataset_leakage(tmp_path)
        assert len(v3) >= 1 and any("beta/gamma" in v for v in v3)
        (fake_docs / "11_extending_and_development.md").write_text(clean_text, encoding="utf-8")

        # 4. Leak study-specific concept into artifacts/AGENTS.md
        (fake_artifacts / "AGENTS.md").write_text("Study focuses on omission-linked dynamics\n", encoding="utf-8")
        v4 = check_dataset_leakage(tmp_path)
        assert len(v4) == 1 and "omission-linked" in v4[0]
        (fake_artifacts / "AGENTS.md").write_text(clean_text, encoding="utf-8")

        # 5. Leak forbidden causal assertion into skills
        (fake_skills / "SKILL.md").write_text("Demonstrates that LFP drives SPK\n", encoding="utf-8")
        v5 = check_dataset_leakage(tmp_path)
        assert len(v5) == 1 and "LFP drives SPK" in v5[0]

    def test_adversarial_probe_version_inconsistency_rejected(self, tmp_path: Path):
        """Adversarial Probe 8: Inconsistent package vs pyproject version must be caught."""
        from scripts.harness_gate import check_version_consistency
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "99.99.99"\n', encoding="utf-8")
        violations = check_version_consistency(tmp_path)
        assert len(violations) > 0
        assert "VERSION_INCONSISTENCY" in violations[0]

    def test_adversarial_probe_python_target_inconsistency_rejected(self, tmp_path: Path):
        """Adversarial Probe 9: Non-Python 3.12 targets in pyproject or workflows must be caught."""
        from scripts.harness_gate import check_python_target_consistency
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nrequires-python = ">=3.10"\nclassifiers = ["Programming Language :: Python :: 3.10"]\n',
            encoding="utf-8"
        )
        violations = check_python_target_consistency(tmp_path)
        assert len(violations) >= 2
        assert all("PYTHON_TARGET_INCONSISTENCY" in v for v in violations)

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
