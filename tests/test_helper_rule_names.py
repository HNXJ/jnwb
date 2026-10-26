"""Same-named helpers that applied different rules (item 12-12).

Each pair now has one name per rule. The tests call the public functions that use each
helper and pin the rule they apply; the import test fails on a tree that still has the
shared names.
"""
from __future__ import annotations

import h5py
import numpy as np
import pytest

import jnwb
from jnwb import artifact_detection, check_ragged_indices, laminar_curation
from jnwb.laminar._xflip import xflip
from jnwb.statistics import shuffle_pvalue_paired


def test_helpers_carry_their_rule_in_their_names():
    from jnwb.artifact_detection import _robust_z_zero_fallback  # noqa: F401
    from jnwb.jrsa._inference import _require_alternative_exact  # noqa: F401
    from jnwb.laminar_curation import _robust_z_std_fallback  # noqa: F401
    from jnwb.nwb_inspect import _decode_bytes_replace  # noqa: F401
    from jnwb.nwb_integrity import _decode_bytes_strict_or_str  # noqa: F401
    from jnwb.statistics._tests import _require_alternative_casefold  # noqa: F401


def test_jrsa_refuses_a_case_variant_that_statistics_folds():
    rng = np.random.default_rng(3)
    x1 = rng.normal(size=(15, 8))
    x2 = -x1 + 0.4 * rng.normal(size=(15, 8))
    with pytest.raises(ValueError, match="unrecognized alternative 'GREATER'"):
        jnwb.jrsa(x1, x2, metric="pearson", alternative="GREATER", rng=0)
    upper = shuffle_pvalue_paired(x1[:, 0], x2[:, 0], 200, rng=0, alternative="GREATER")
    lower = shuffle_pvalue_paired(x1[:, 0], x2[:, 0], 200, rng=0, alternative="greater")
    assert np.isfinite(lower[1])
    assert upper == lower


def test_integrity_check_refuses_a_column_name_that_is_not_utf8(tmp_path):
    path = tmp_path / "units.h5"
    with h5py.File(path, "w") as f:
        g = f.create_group("units")
        g.create_dataset("id", data=np.arange(2))
        g.create_dataset("spike_times", data=np.arange(5, dtype="f8"))
        g.create_dataset("spike_times_index", data=np.array([3, 5], dtype="int64"))
        g.attrs["colnames"] = np.array([b"\xff"], dtype="S")
    with pytest.raises(UnicodeDecodeError):
        check_ragged_indices(path, table="units")


def test_zero_mad_is_scaled_by_the_mean_deviation_in_the_artifact_rule_and_by_the_std_in_the_laminar_rule():
    corr = np.zeros((4, 4))
    np.fill_diagonal(corr, 1.0)
    corr[3, :3] = 1.0
    _, summary, z = artifact_detection.bad_channels_from_correlation(corr)
    assert summary.tolist() == [0.0, 0.0, 0.0, 1.0]   # precondition: MAD of the summary is 0
    # artifact rule: zero MAD falls back to the mean absolute deviation, 0.25 * 1.253314
    np.testing.assert_allclose(z, [0.0, 0.0, 0.0, 1.0 / (0.25 * 1.253314)], rtol=1e-12)

    rng = np.random.default_rng(0)
    base = rng.standard_normal(4000)
    data = np.vstack([base, base, base, 2.0 * base])
    out = laminar_curation.detect_bad_channels(data, 1000.0, max_power_z=2.0)
    assert np.all(out["log_power"][:3] == out["log_power"][0])   # precondition: MAD is 0
    assert out["bad_mask"].tolist() == [False, False, False, True]  # laminar rule: std fallback


def test_xflip_flags_a_finite_constant_channel_as_flat():
    rng = np.random.default_rng(1)
    arr = rng.standard_normal((4, 200))
    arr[3, :] = 0.5
    res = xflip(arr, channel_axis=0)
    assert np.isfinite(res.corr_matrix[:3, :3]).all()   # precondition: varying channels correlate
    assert np.isnan(res.corr_matrix[3]).all()           # zero spread: correlation undefined
