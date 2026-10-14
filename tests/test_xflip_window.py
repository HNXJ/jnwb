"""`xflip` on `vflip2`'s frame: `window=`, `contact_spacing` and the layer 4 shortest block.

The window comes from running `vflip2` on `power_example`, the PSD vFLIP2.m ran in MATLAB
(``tests/fixtures/vflip2_matlab_reference.json``), padded with NaN rows, which vflip2 excludes
when they lead or trail. The padding moves the window off row 0, so the offset back to probe
rows is exercised. The correlation probe is synthetic and matches it row for row: noise above
the window, two blocks inside it that meet at vflip2's crossover, and an artefact block below.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from jnwb.laminar import VFlip2Result, vflip2, xflip
from jnwb.laminar._vflip2 import LAYER4_THICKNESS_MM

DOC = json.loads((Path(__file__).resolve().parent / "fixtures"
                  / "vflip2_matlab_reference.json").read_text(encoding="utf-8"))
CASES = {case["name"]: case for case in DOC["cases"]}
LEAD, TRAIL = 5, 15


def _psd(case, lead=0, trail=0):
    psd = np.array([[np.nan if v is None else v for v in row] for row in case["psd"]], dtype=float)
    pad = np.full((1, psd.shape[1]), np.nan)
    return np.vstack([np.repeat(pad, lead, axis=0), psd, np.repeat(pad, trail, axis=0)])


def _v2(name, lead=0, trail=0):
    case = CASES[name]
    psd = _psd(case, lead, trail)
    freqs = case["freqbinsize"] * np.arange(1, psd.shape[1] + 1)
    return vflip2(psd, freqs, contact_spacing=case["intdist"] * 1000.0,
                  orientation=case["orientation"]), psd.shape[0]


@pytest.fixture(scope="module")
def probe():
    v2, n = _v2("power_example", LEAD, TRAIL)
    assert v2.accepted and v2.proximal_channel > 0, "fixture must give an accepted window off row 0"
    assert v2.distal_channel < n - 1, "fixture must leave rows below the window for the artefact"
    first, cross, last = v2.proximal_channel, v2.crossover_channel, v2.distal_channel
    block = np.full(n, -1)  # -1: uncorrelated rows above the window
    block[first:cross] = 0
    block[cross:last + 1] = 1
    block[last + 1:] = 2  # the artefact
    c = np.where(block[:, None] == block[None, :], 0.6, 0.1)
    c[block == 2, :] = 0.0
    c[:, block == 2] = 0.0
    c[np.ix_(block == 2, block == 2)] = 0.95
    c[block == -1, :] = 0.0
    c[:, block == -1] = 0.0
    np.fill_diagonal(c, 1.0)
    data = np.linalg.cholesky(c) @ np.random.default_rng(0).standard_normal((n, 4000))
    return v2, data


def test_window_reports_the_in_window_boundary_in_probe_rows(probe):
    v2, data = probe
    whole = xflip(data, n_surrogates=50, rng=1)
    assert whole.boundaries == (v2.distal_channel + 1,), "the whole probe must cut at the artefact"
    assert all(abs(b - v2.crossover_channel) > 1 for b in whole.boundaries)

    res = xflip(data, window=v2, n_surrogates=50, rng=1)
    assert res.accepted
    assert res.window == (v2.proximal_channel, v2.distal_channel)
    (b,) = res.boundaries
    assert abs(b - v2.crossover_channel) <= 1
    assert res.block_bounds == ((v2.proximal_channel, b), (b, v2.distal_channel + 1))
    assert set(res.p_values) == {"omnibus", f"boundary_{b}"}
    assert set(res.boundary_drops) == {b}
    assert res.n_channels == res.labels.size == v2.distal_channel - v2.proximal_channel + 1


def test_a_pair_is_taken_in_either_order(probe):
    v2, data = probe
    a = xflip(data, window=(v2.proximal_channel, v2.distal_channel), n_surrogates=20, rng=3)
    b = xflip(data, window=(v2.distal_channel, v2.proximal_channel), n_surrogates=20, rng=3)
    assert a.window == b.window == (v2.proximal_channel, v2.distal_channel)
    assert a.boundaries == b.boundaries and a.p_values == b.p_values


def test_a_matrix_is_windowed_on_rows_and_columns(probe):
    v2, data = probe
    raw = xflip(data, window=v2, n_surrogates=0)
    mat = xflip(np.corrcoef(data), window=v2, n_samples=data.shape[1], n_surrogates=0)
    assert mat.boundaries == raw.boundaries
    np.testing.assert_allclose(mat.corr_matrix, raw.corr_matrix, rtol=0, atol=1e-12)


def test_contact_spacing_adds_boundaries_um_from_row_0(probe):
    v2, data = probe
    res = xflip(data, window=v2, contact_spacing=100.0, min_block_size=2, n_surrogates=0)
    assert res.boundaries and res.boundaries[0] > v2.proximal_channel
    assert res.boundaries_um == tuple(b * 100.0 for b in res.boundaries)
    assert xflip(data, window=v2, n_surrogates=0).boundaries_um is None


def test_contact_spacing_sets_the_shortest_block_to_layer_4():
    from jnwb.testing.synth import synth_correlation_blocks

    data, _, _ = synth_correlation_blocks([3, 10], n_samples=2000, rng=4)
    layer4 = math.ceil(LAYER4_THICKNESS_MM / (100.0 / 1000.0))  # vflip2's shortest window
    assert layer4 == 6
    two = xflip(data, min_block_size=2, n_surrogates=0)
    assert two.boundaries == (3,), "fixture must cut at 3 with blocks of 2"
    default = xflip(data, contact_spacing=100.0, n_surrogates=0)
    assert default.boundaries == xflip(data, min_block_size=layer4, n_surrogates=0).boundaries
    assert default.boundaries != two.boundaries
    explicit = xflip(data, contact_spacing=100.0, min_block_size=2, n_surrogates=0)
    assert explicit.boundaries == two.boundaries


def test_without_the_new_arguments_nothing_changes():
    from jnwb.testing.synth import synth_correlation_blocks

    data, _, _ = synth_correlation_blocks([5, 7], n_samples=500, rng=2)
    res = xflip(data, n_surrogates=20, rng=5)
    old = xflip(data, min_block_size=2, n_surrogates=20, rng=5)
    assert res.window is None and res.boundaries_um is None
    assert res.boundaries == old.boundaries and res.p_values == old.p_values


def test_an_empty_or_rejected_vflip2_result_is_refused(probe):
    _, data = probe
    empty, _ = _v2("c0022")
    assert empty.proximal_channel is None, "fixture must be a result with no window"
    with pytest.raises(ValueError, match="holds no window"):
        xflip(data, window=empty, n_surrogates=0)
    rejected, _ = _v2("c0234")
    assert not rejected.accepted and rejected.proximal_channel is not None, (
        "fixture must be a rejected result that keeps its window")
    with pytest.raises(ValueError, match="rejected"):
        xflip(data, window=rejected, n_surrogates=0)


@pytest.mark.parametrize("window", [(-1, 10), (5, 51), (60, 3)])
def test_a_window_outside_the_probe_is_refused(probe, window):
    _, data = probe
    assert data.shape[0] == 51
    with pytest.raises(ValueError, match="outside the probe"):
        xflip(data, window=window, n_surrogates=0)


def test_a_window_shorter_than_one_block_is_refused(probe):
    _, data = probe
    with pytest.raises(ValueError, match="fewer than min_block_size 3"):
        xflip(data, window=(10, 11), min_block_size=3, n_surrogates=0)
    with pytest.raises(ValueError, match="fewer than min_block_size 6"):
        xflip(np.corrcoef(data), window=(10, 14), contact_spacing=100.0, n_samples=4000,
              n_surrogates=0)


@pytest.mark.parametrize("window", [(True, 10), (1, 2, 3), (1.0, 10), "ab", 5])
def test_a_window_that_is_not_two_int_rows_is_refused(probe, window):
    _, data = probe
    with pytest.raises(TypeError, match="window must be"):
        xflip(data, window=window, n_surrogates=0)


@pytest.mark.parametrize("spacing", [0.0, -100.0, np.nan, np.inf])
def test_a_bad_contact_spacing_is_refused(spacing):
    with pytest.raises(ValueError, match="contact_spacing must be finite and positive"):
        xflip(np.eye(6), contact_spacing=spacing, n_surrogates=0)


def test_layer4_thickness_sets_the_default_shortest_block(probe):
    _, data = probe
    rows = 16 - 10 + 1  # the window (10, 16) holds 7 contacts
    assert 6 <= rows < 8, "fixture must lie between the default and the 0.8 mm shortest block"
    assert math.ceil(0.8 / (100.0 / 1000.0)) == 8, "precondition: 0.8 mm is 8 contacts at 100 um"
    default = xflip(data, window=(10, 16), contact_spacing=100.0, n_surrogates=0)
    assert "with min_block_size 6" in default.rejection_reason, "default: 6 contacts at 100 um"
    with pytest.raises(ValueError, match="hold 7 contacts, fewer than min_block_size 8"):
        xflip(data, window=(10, 16), contact_spacing=100.0, layer4_thickness_mm=0.8,
              n_surrogates=0)


@pytest.mark.parametrize("thickness", [0.0, -0.8, np.nan, np.inf])
def test_a_bad_layer4_thickness_is_refused(thickness):
    with pytest.raises(ValueError, match="layer4_thickness_mm must be finite and positive"):
        xflip(np.eye(6), contact_spacing=100.0, layer4_thickness_mm=thickness, n_surrogates=0)


def test_an_out_of_probe_window_names_its_rows_sorted():
    data = np.random.default_rng(0).normal(size=(32, 200))
    assert data.shape[0] == 32
    with pytest.raises(ValueError, match=r"window rows \(3, 40\) fall outside"):
        xflip(data, window=(40, 3), n_surrogates=0)
