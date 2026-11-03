"""phase_locking_index refuses non-finite LFP timestamps by name.

A NaN step compares False to 0, so the strictly-increasing check let a NaN timestamp through and
the NaN phase it produced was blamed on lfp_phase.

A metrics dict without `response_zscore` is undefined to `classify_response_significance`, not a
z of 0 that classifies 'none'.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from jnwb.spiking import classify_response_significance, phase_locking_index

FS = 1000.0


def _inputs():
    t = np.arange(2000) / FS
    phase = np.angle(np.exp(1j * 2 * np.pi * 8.0 * t))
    spikes = np.linspace(0.1, 1.9, 40)
    return spikes, phase, t


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_a_non_finite_timestamp_is_refused_by_name(bad):
    spikes, phase, t = _inputs()
    t[700] = bad
    assert np.any((spikes > t[699]) & (spikes < t[701])), "fixture must put a spike beside it"
    with pytest.raises(ValueError, match=r"phase_locking_index: lfp_timestamps\[700\] is"):
        phase_locking_index(spikes, phase, t)


def test_finite_timestamps_still_give_a_phase_estimate():
    spikes, phase, t = _inputs()
    out = phase_locking_index(spikes, phase, t)
    assert out["n_spikes"] == 40
    assert np.isfinite(out["rayleigh_z"]) and np.isfinite(out["preferred_phase"])


def _counts_only_metrics() -> dict:
    """Per-trial counts and window lengths with no response_zscore: the effect size is unknown."""
    return {
        "response_count": 25,
        "baseline_counts": np.array([2, 3, 1, 2, 2, 1, 3, 2, 2, 2.0]),
        "response_counts": np.array([4, 5, 3, 4, 4, 3, 5, 4, 4, 4.0]),
        "baseline_duration_s": 1.0,
        "response_duration_s": 1.0,
    }


def test_a_missing_response_zscore_is_undefined_and_not_a_zero_z():
    metrics = _counts_only_metrics()
    assert "response_zscore" not in metrics, "fixture must omit the z key"
    with pytest.warns(UserWarning, match="response_zscore"):
        missing = classify_response_significance(metrics)
    assert missing["confidence"] == "undefined"
    assert not missing["is_significant"]
    assert np.isfinite(missing["pvalue"]), "the counts test ran, so its p stands"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        measured = classify_response_significance({**metrics, "response_zscore": 0.0})
    assert measured["confidence"] == "none", "z = 0 is a measured zero effect, not undefined"
    assert not [w for w in caught if "response_zscore" in str(w.message)], (
        "a present response_zscore of 0 must not warn about a missing key"
    )
