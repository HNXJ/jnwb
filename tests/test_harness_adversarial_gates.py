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
