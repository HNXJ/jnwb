"""vFLIP2: the port against vFLIP2.m's output, and its refusals.

The reference is ``tests/fixtures/vflip2_matlab_reference.json``: eight cases chosen from the
300 synthetic PSDs that vFLIP2.m ran in MATLAB, and ``power_example`` from the same run. The
file records the sha256 of vFLIP2.m. Each test asserts the precondition of the case it reads
before it checks the port.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import jnwb
from jnwb.laminar import VFlip2Result, vflip2, vflip2_from_lfp
from jnwb.testing import synth_vflip2_crossover

DOC = json.loads((Path(__file__).resolve().parent / "fixtures"
                  / "vflip2_matlab_reference.json").read_text(encoding="utf-8"))
# The cut is vFLIP2.m's, read from the reference rather than from the module under test.
OMEGA_CUT = DOC["omega_cut"]
CASES = {case["name"]: case for case in DOC["cases"]}
NAMES = list(CASES)
WINDOW = [n for n in NAMES if CASES[n]["matlab"]["window"]]
BELOW = [n for n in NAMES if CASES[n]["class"] == "below_cut"]
NO_WINDOW = [n for n in NAMES if not CASES[n]["matlab"]["window"]]
# Searched with "both", the best window is inverted: restricting to upright changes the answer.
BOTH_INVERTED = [n for n in NAMES if CASES[n]["orientation"] == "both"
                 and CASES[n]["class"] == "accepted_inverted"]


def _psd(case):
    """JSON rows to float arrays; null is NaN, as the reference writes a NaN row."""
    return np.array([[np.nan if v is None else v for v in row] for row in case["psd"]],
                    dtype=float)


def _freqs(case, psd):
    return case["freqbinsize"] * np.arange(1, psd.shape[1] + 1)


def _run(case, orientation=None):
    psd = _psd(case)
    return vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0,
                  orientation=case["orientation"] if orientation is None else orientation)


def _quality(omega):
    return "absent" if omega <= 6 else ("medium" if omega <= 12 else "strong")


def test_vflip2_is_a_public_export():
    assert jnwb.vflip2 is vflip2
    assert jnwb.VFlip2Result is VFlip2Result
    assert {"vflip2", "VFlip2Result"} <= set(jnwb.__all__)


def test_fixture_covers_every_category_it_claims():
    classes = {c["class"] for c in DOC["cases"]}
    assert "accepted_upright" in classes, "no accepted upright window"
    assert "accepted_inverted" in classes, "no accepted inverted window"
    assert BELOW, "no case rejected below the cut"
    assert NO_WINDOW, "no case without a window"
    assert {c["orientation"] for c in DOC["cases"]} >= {"both", "upright", "inverted"}
    assert {c["freqbinsize"] for c in DOC["cases"]} >= {0.5, 1.0, 2.0}
    assert "noise" in {c["kind"] for c in DOC["cases"]}, "no noise-kind case"
    assert any(np.isnan(_psd(c)[0]).any() or np.isnan(_psd(c)[-1]).any()
               for c in DOC["cases"]), "no case with a NaN end row"
    assert BOTH_INVERTED, "no case searched with both whose best window is inverted"
    assert "power_example" in CASES
    assert len(DOC["source"]["sha256"]) == 64
    assert len(DOC["cases"]) == 9, f"expected 8 cases and power_example, got {len(DOC['cases'])}"


@pytest.mark.parametrize("name", WINDOW)
def test_every_window_matches_matlab(name):
    case = CASES[name]
    m = case["matlab"]
    # Precondition: the MATLAB numbers agree with the cut and with the case's class.
    assert m["accepted"] == (m["omega"] > OMEGA_CUT)
    if case["class"].startswith("accepted_"):
        assert m["accepted"] and m["omega"] > OMEGA_CUT
        assert m["orientation"] == case["class"][len("accepted_"):]
    res = _run(case)
    assert res.omega is not None
    np.testing.assert_allclose(res.omega, m["omega"], rtol=1e-9)
    np.testing.assert_allclose(res.goodness, m["goodness"], rtol=1e-9)
    assert res.proximal_channel == m["proximal_channel"]
    assert res.distal_channel == m["distal_channel"]
    assert res.low_peak_channel == m["low_peak_channel"]
    assert res.high_peak_channel == m["high_peak_channel"]
    assert res.crossover_channel == m["crossover_channel"]
    assert res.orientation == m["orientation"]
    assert res.low_band_hz == tuple(m["low_band_hz"])
    assert res.high_band_hz == tuple(m["high_band_hz"])
    assert res.accepted == m["accepted"]
    assert res.accepted == (res.omega > OMEGA_CUT)
    assert res.motif_quality == _quality(m["omega"])


@pytest.mark.parametrize("name", BELOW)
def test_below_the_cut_the_best_window_is_returned_and_refused(name):
    case = CASES[name]
    m = case["matlab"]
    # Precondition: a window exists and its omega is at or below the cut.
    assert m["window"] and m["omega"] <= OMEGA_CUT and not m["accepted"]
    res = _run(case)
    assert res.accepted is False
    assert res.motif_quality == "absent"
    np.testing.assert_allclose(res.omega, m["omega"], rtol=1e-9)
    assert (res.proximal_channel, res.distal_channel) == (m["proximal_channel"],
                                                          m["distal_channel"])


@pytest.mark.parametrize("name", NO_WINDOW)
def test_no_window_returns_an_empty_result(name):
    case = CASES[name]
    assert not case["matlab"]["window"]  # precondition: MATLAB found no window
    res = _run(case)
    assert res.omega is None and res.goodness is None
    assert res.accepted is False
    assert res.motif_quality is None
    assert res.low_band_hz is None and res.proximal_channel is None
    assert res.omega_cut == OMEGA_CUT


def _clean_psd():
    case = CASES["c0170"]  # accepted, upright, no NaN rows
    psd = _psd(case)
    assert np.isfinite(psd).all(), "fixture must be a finite probe"
    return case, psd


def test_an_interior_nan_row_is_refused():
    case, psd = _clean_psd()
    psd[5] = np.nan
    with pytest.raises(ValueError, match="NaN row between"):
        vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0)


def test_negative_power_is_refused():
    case, psd = _clean_psd()
    psd[5, 7] = -1.0
    with pytest.raises(ValueError, match="non-negative"):
        vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0)


def test_non_finite_power_is_refused():
    case, psd = _clean_psd()
    psd[5, 7] = np.inf
    with pytest.raises(ValueError, match="finite"):
        vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0)


def test_an_unknown_orientation_is_refused():
    case, psd = _clean_psd()
    with pytest.raises(ValueError, match="orientation must be one of"):
        vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0,
               orientation="sideways")


def test_layer4_thickness_is_vflip2_m_sum_to_the_last_bit():
    """vFLIP2.m divides each thickness by 1000 and then sums; MATLAB R2024a prints
    0.58600000000000007638, one ulp above 0.586, and the ulp sets the shortest window at
    146.5 um (5 contacts in MATLAB, 4 from 0.586 itself)."""
    from jnwb.laminar._vflip2 import LAYER4_THICKNESS_MM

    assert LAYER4_THICKNESS_MM == 0.58600000000000007638
    assert LAYER4_THICKNESS_MM != 0.586
    assert np.ceil(LAYER4_THICKNESS_MM / 0.1465) == 5 and np.ceil(0.586 / 0.1465) == 4


@pytest.mark.parametrize("kwargs, match", [
    ({"contact_spacing": 0.0}, "contact_spacing"),
    ({"contact_spacing": float("nan")}, "contact_spacing"),
    ({"layer4_thickness_mm": -0.5}, "layer4_thickness_mm"),
    ({"omega_cut": float("nan")}, "omega_cut"),
])
def test_bad_scalar_arguments_are_refused(kwargs, match):
    case, psd = _clean_psd()
    args = {"contact_spacing": case["intdist"] * 1000.0, **kwargs}
    with pytest.raises(ValueError, match=match):
        vflip2(psd, _freqs(case, psd), **args)


def test_a_contact_spacing_above_200_um_is_refused():
    case, psd = _clean_psd()
    with pytest.raises(ValueError, match=r"vflip2.*contact_spacing.*200"):
        vflip2(psd, _freqs(case, psd), contact_spacing=200.5)


def test_a_contact_spacing_of_200_um_still_searches_windows():
    rec = synth_vflip2_crossover(n_channels=32, n_samples=5000, fs=1000.0, z0=16, rng=0)
    # Precondition: the planted probe passes a window at 100 um, so a None at 200 um would
    # mean the 200 um search found nothing.
    assert vflip2_from_lfp(rec.lfp, 1000.0, contact_spacing=100.0).omega is not None
    assert vflip2_from_lfp(rec.lfp, 1000.0, contact_spacing=200.0).omega is not None


def test_non_uniform_freqs_are_refused():
    case, psd = _clean_psd()
    freqs = _freqs(case, psd).copy()
    freqs[3] += 0.25 * (freqs[1] - freqs[0])
    with pytest.raises(ValueError, match="uniformly spaced"):
        vflip2(psd, freqs, contact_spacing=case["intdist"] * 1000.0)


def test_upright_restricts_the_search():
    assert BOTH_INVERTED, "fixture must hold a case searched with both whose best window is inverted"
    case = CASES[BOTH_INVERTED[0]]
    m = case["matlab"]
    # Precondition: the case is searched with "both" and its best window is inverted,
    # so restricting to upright must change the answer.
    assert case["orientation"] == "both" and m["orientation"] == "inverted"
    both = _run(case, orientation="both")
    upright = _run(case, orientation="upright")
    assert upright.orientation != both.orientation
    assert upright.orientation in (None, "upright")
    assert upright.omega is None or upright.omega <= both.omega
