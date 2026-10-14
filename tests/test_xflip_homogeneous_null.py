"""xFLIP's default null against probes with no boundary and against a two-block probe.

Phase-randomized surrogates make channels independent, so a volume-conducted probe with no
boundary sits at the omnibus p floor. The homogeneous null keeps the probe's lag-averaged
correlation, so a partition is significant only beyond smooth spatial decay. The boundary-free
probe is the one in ``artifacts/evidence/0.2.12/xflip_null_probe.py``.

This module is slow, roughly three minutes: test_false_positive_rate_on_boundary_free_probes
runs 200 probes and takes about 160 s of it. The suite has no slow marker, so the note stands
in for one.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

import jnwb

N_T = 4000
ALPHA = 0.05
N_SURROGATES = 100


def _volume_conducted(seed, n_ch=24, n_t=N_T, scale=3.0):
    """Every contact sees the same sources through one smooth kernel; nothing changes along the shaft."""
    rng = np.random.default_rng(seed)
    sources = rng.standard_normal((n_ch * 3, n_t))
    pos_src = np.linspace(-6, n_ch + 6, n_ch * 3)
    pos_ch = np.arange(n_ch)
    kernel = np.exp(-np.abs(pos_ch[:, None] - pos_src[None, :]) / scale)
    return kernel @ sources + 0.2 * rng.standard_normal((n_ch, n_t))


def _two_blocks(seed, n_t=N_T):
    """Contacts 0-11 and 12-23, each driven by its own disjoint sources through the same kernel."""
    rng = np.random.default_rng(seed)
    lfp = np.empty((24, n_t))
    for first in (0, 12):
        contacts = np.arange(first, first + 12)
        sources = rng.standard_normal((36, n_t))
        pos_src = np.linspace(first - 6, first + 17, 36)
        kernel = np.exp(-np.abs(contacts[:, None] - pos_src[None, :]) / 3.0)
        lfp[first:first + 12] = kernel @ sources
    return lfp + 0.2 * rng.standard_normal((24, n_t))


def test_a_volume_conducted_probe_is_not_significant_under_the_default_null():
    """24 contacts, kernel scale 3, seeds 0-9, 100 surrogates."""
    old_p, new_p = [], []
    for seed in range(10):
        lfp = _volume_conducted(seed)
        corr = np.corrcoef(lfp)
        assert corr[0, 1] > corr[0, 5] > corr[0, 12] > 0.0, "fixture must decay with distance"
        old = jnwb.xflip(lfp, n_surrogates=N_SURROGATES, rng=seed,
                         surrogate_method="autocorr_preserving")
        new = jnwb.xflip(lfp, n_surrogates=N_SURROGATES, rng=seed)
        old_p.append(old.p_values["omnibus"])
        new_p.append(new.p_values["omnibus"])
    floor = 1 / (N_SURROGATES + 1)
    assert sum(math.isclose(p, floor) for p in old_p) >= 9, (
        f"the fixture must be the independent-channel case: old-null p per seed {old_p}"
    )
    assert sum(p > ALPHA for p in new_p) >= 9, (
        f"default-null omnibus p per seed {new_p}; need p > {ALPHA} on at least 9 of 10"
    )


def test_b_two_blocks_with_disjoint_sources_are_accepted_at_the_boundary():
    """Contacts 0-11 and 12-23, disjoint sources per block, seeds 0-9, 100 surrogates."""
    accepted_boundaries = []
    n_accepted = 0
    for seed in range(10):
        lfp = _two_blocks(seed)
        corr = np.corrcoef(lfp)
        within = corr[:12, :12][~np.eye(12, dtype=bool)].mean()
        across = corr[:12, 12:].mean()
        assert within > across + 0.3, "fixture must have two blocks"
        res = jnwb.xflip(lfp, n_surrogates=N_SURROGATES, rng=seed)
        if res.accepted:
            n_accepted += 1
            accepted_boundaries.append(res.boundaries)
    assert n_accepted >= 9, f"accepted on {n_accepted} of 10 seeds; need at least 9"
    assert all(len(b) == 1 and abs(b[0] - 12) <= 1 for b in accepted_boundaries), (
        f"boundaries of the accepted seeds {accepted_boundaries}; each must be 12 +- 1"
    )


def test_false_positive_rate_on_boundary_free_probes_is_at_the_nominal_level():
    """200 boundary-free probes, seeds 0-199, 100 surrogates, omnibus p at alpha 0.05."""
    n = 200
    hits = 0
    for seed in range(n):
        lfp = _volume_conducted(seed)
        corr = np.corrcoef(lfp)
        assert corr[0, 1] > corr[0, 12], "fixture must decay with distance"
        res = jnwb.xflip(lfp, n_surrogates=N_SURROGATES, rng=seed)
        hits += int(res.p_values["omnibus"] <= ALPHA)
    bound = ALPHA + 2 * math.sqrt(ALPHA * (1 - ALPHA) / n)
    assert hits / n <= bound, (
        f"{hits} of {n} boundary-free probes have omnibus p <= {ALPHA}; bound {bound:.4f}"
    )


def test_correlation_matrix_with_n_samples_is_not_significant_on_a_boundary_free_probe():
    """Five boundary-free seeds, passed as correlation matrices with n_samples."""
    n_above = 0
    for seed in range(5):
        corr = np.corrcoef(_volume_conducted(seed))
        assert np.allclose(np.diag(corr), 1.0), "fixture must be a correlation matrix"
        res = jnwb.xflip(corr, n_surrogates=N_SURROGATES, rng=seed, n_samples=N_T)
        assert res.method == "precomputed"
        n_above += int(res.p_values["omnibus"] > ALPHA)
    assert n_above >= 4, f"omnibus p > {ALPHA} on {n_above} of 5 seeds; need at least 4"


def test_correlation_matrix_without_n_samples_warns_once_and_names_the_limit():
    corr = np.corrcoef(_volume_conducted(0))
    assert np.allclose(np.diag(corr), 1.0), "fixture must be a correlation matrix"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = jnwb.xflip(corr, n_surrogates=N_SURROGATES, rng=0)
    assert res.method == "precomputed"
    notes = [w for w in caught
             if issubclass(w.category, UserWarning) and "n_samples" in str(w.message)]
    assert len(notes) == 1, [str(w.message) for w in caught]
    assert "independent channels" in str(notes[0].message)


def test_n_samples_is_refused_for_raw_data_and_homogeneous_needs_it_for_a_matrix():
    lfp = _volume_conducted(0)
    with pytest.raises(ValueError, match="n_samples"):
        jnwb.xflip(lfp, n_surrogates=5, rng=0, n_samples=N_T)
    corr = np.corrcoef(lfp)
    assert np.allclose(np.diag(corr), 1.0), "fixture must be a correlation matrix"
    with pytest.raises(ValueError, match="n_samples"):
        jnwb.xflip(corr, n_surrogates=5, rng=0, surrogate_method="homogeneous")
