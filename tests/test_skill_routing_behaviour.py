"""The six corrected routing rows, executed rather than parsed.

`tests/test_skills_validation.py` checks every row against `inspect.signature`, which catches
a swapped argument, a keyword-only argument passed positionally, an invented default and an
omitted required parameter. Two of the six defects 05-67 corrected are not in the signature:
a row that named a result key the function does not return, and a row that described a
two-trace estimator as working across channel pairs. Those are checked here by running the
code, along with the behaviour that makes the argument order matter at all.

Skills are release surfaces, so each check is against the live library, never against the
skill's own text.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import jnwb

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def _skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def test_swapping_the_paired_fire_arguments_negates_the_effect_without_raising():
    """Why the row's argument order was worth correcting rather than annotating.

    The old row put `fires_null` first. With the missing `n_shuffles` supplied, that call
    succeeds and reports the effect with its sign reversed.
    """
    rng = np.random.default_rng(0)
    target = (rng.random(40) < 0.8).astype(int)
    null = (rng.random(40) < 0.2).astype(int)

    correct = jnwb.paired_fire_prob_test(target, null, n_shuffles=200, n_bootstrap=200,
                                         rng=np.random.default_rng(1))
    swapped = jnwb.paired_fire_prob_test(null, target, n_shuffles=200, n_bootstrap=200,
                                         rng=np.random.default_rng(1))

    assert correct["risk_difference"] > 0
    assert swapped["risk_difference"] == pytest.approx(-correct["risk_difference"])
    assert "Target first" in _skill("jnwb-statistics"), (
        "the routing row no longer warns that the order is silent"
    )


def test_band_power_raises_on_the_default_the_row_now_states():
    lfp = np.random.default_rng(2).normal(size=2000)
    with pytest.raises(ValueError, match="baseline"):
        jnwb.band_power(lfp, fs=1000.0, freq_range=(14.0, 30.0))
    assert jnwb.band_power(lfp, fs=1000.0, freq_range=(14.0, 30.0), normalize=False) > 0.0


def test_cross_area_coherence_refuses_the_channel_matrix_the_row_used_to_promise():
    two_d = np.random.default_rng(3).normal(size=(4, 2000))
    with pytest.raises(ValueError, match="1-D"):
        jnwb.cross_area_coherence(two_d, two_d, fs=1000.0, freq_bands="canonical")
    assert "two 1-D traces" in _skill("jnwb-lfp-spectral")


def test_the_repair_info_has_no_frac_flagged_key():
    """`info.get('frac_flagged', 0)` returns 0 and skips the check the row asked for."""
    rng = np.random.default_rng(4)
    seg = rng.normal(0, 1, (12, 4, 200))
    seg[3, :, 50:60] += 40.0
    info = jnwb.repair_lfp_trials(seg)[-1]

    assert "frac_flagged" not in info
    assert "max_fraction_trials_flagged_at_a_sample" in info
    skill = _skill("jnwb-lfp-spectral")
    assert "max_fraction_trials_flagged_at_a_sample" in skill
    assert "max_trial_fraction" in skill, "the guard that acts on it is not named"


def test_epoch_continuous_is_keyword_only_where_the_row_now_says_so():
    data = np.random.default_rng(5).normal(size=(5000, 3))
    onsets = np.array([1.0, 2.0])
    with pytest.raises(TypeError, match="positional"):
        jnwb.epoch_continuous(data, onsets, (-0.1, 0.4), 1000.0)
    epochs, times = jnwb.epoch_continuous(data, onsets, win_s=(-0.1, 0.4), fs=1000.0)
    # (n_onsets, n_times, n_channels)
    assert epochs.shape == (2, times.size, data.shape[1])


def test_nested_cv_linear_svm_has_no_n_splits_default():
    X = np.random.default_rng(6).normal(size=(60, 8))
    y = np.random.default_rng(7).integers(0, 2, 60)
    with pytest.raises(TypeError, match="n_splits"):
        jnwb.nested_cv_linear_svm(X, y)
    assert jnwb.nested_cv_linear_svm(X, y, n_splits=3)["accuracy"] >= 0.0
