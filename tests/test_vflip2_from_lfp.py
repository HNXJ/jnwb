"""vflip2_from_lfp: vFLIP2.m's raw and raw_cut PSD, against MATLAB's output, and its refusals.

The committed reference is ``tests/fixtures/vflip2_from_lfp_matlab_reference.json``: seeded
synthetic laminar LFP (continuous, trial-cut, and trials of unequal length) that vFLIP2.m ran
in MATLAB, with the PSD it computed and its Results. The Dryad test data are too large to
ship; their test runs only where the data and vFLIP2.m's saved output are on disk.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

import jnwb
from jnwb.laminar import _vflip2, vflip2_from_lfp

DOC = json.loads((Path(__file__).resolve().parent / "fixtures"
                  / "vflip2_from_lfp_matlab_reference.json").read_text(encoding="utf-8"))
CASES = {case["name"]: case for case in DOC["cases"]}
SPACING_UM = DOC["intdist_mm"] * 1000.0

# Where the Dryad download unpacks by default; JNWB_VFLIP2_TESTDATA overrides it.
DRYAD_DATA = Path(os.environ.get(
    "JNWB_VFLIP2_TESTDATA",
    Path.home() / "Downloads" / "doi_10_5061_dryad_9w0vt4bnp__v20251104" / "vFLIP2_testdata.mat"))
DRYAD_REFERENCE = Path(os.environ.get("JNWB_VFLIP2_REFERENCE",
                                      "E:/derived/vflip2_ref/reference.mat"))


def _lfp(case):
    if case["name"] == "cell":
        return [np.array(t, dtype=float) for t in case["lfp"]]
    return np.array(case["lfp"], dtype=float)


def _run_capturing_psd(monkeypatch, lfp, fs):
    """Run vflip2_from_lfp and return (result, the psd and freqs it handed to vflip2)."""
    seen = {}
    inner = _vflip2.vflip2

    def spy(psd, freqs, **kwargs):
        seen["psd"], seen["freqs"] = np.array(psd), np.array(freqs)
        return inner(psd, freqs, **kwargs)

    monkeypatch.setattr(_vflip2, "vflip2", spy)
    result = vflip2_from_lfp(lfp, fs, contact_spacing=SPACING_UM)
    return result, seen["psd"], seen["freqs"]


def _assert_matches_matlab(result, psd, freqs, matlab_psd, matlab):
    np.testing.assert_allclose(psd, matlab_psd, rtol=1e-9, atol=0)
    # vFLIP2.m labels PSD column k as k Hz (freqbinsize 1, its line 130).
    np.testing.assert_array_equal(freqs, np.arange(1, matlab_psd.shape[1] + 1))
    assert result.accepted
    np.testing.assert_allclose(result.omega, matlab["omega"], rtol=1e-9)
    np.testing.assert_allclose(result.goodness, matlab["goodnessvalue"], rtol=1e-9)
    assert result.low_band_hz == (matlab["startinglowfreq"], matlab["endinglowfreq"])
    assert result.high_band_hz == (matlab["startinghighfreq"], matlab["endinghighfreq"])
    assert (result.proximal_channel + 1, result.distal_channel + 1) == (
        matlab["proximalchannel"], matlab["distalchannel"])
    assert (result.low_peak_channel + 1, result.high_peak_channel + 1,
            result.crossover_channel + 1) == (
        matlab["lowfreqmaxchannel"], matlab["highfreqmaxchannel"], matlab["crossoverchannel"])


def test_vflip2_from_lfp_is_a_public_export():
    assert jnwb.vflip2_from_lfp is vflip2_from_lfp
    assert "vflip2_from_lfp" in jnwb.__all__


def test_fixture_covers_each_input_form():
    assert set(CASES) == {"raw", "trialcut", "cell"}
    assert np.array(CASES["raw"]["lfp"]).ndim == 2
    assert np.array(CASES["trialcut"]["lfp"]).ndim == 3
    assert len({len(t[0]) for t in CASES["cell"]["lfp"]}) == 2, "cell trials differ in length"
    # The raw case drops a remainder shorter than one trial.
    assert len(CASES["raw"]["lfp"][0]) % CASES["raw"]["fs"] != 0
    for name in ("trialcut", "cell"):
        assert not float(CASES[name]["fs"]).is_integer(), "trial-cut cases use a non-integer fs"
    for case in CASES.values():
        assert case["results"] is not None, f"{case['name']}: vFLIP2.m must return a window"


@pytest.mark.parametrize("name", ["raw", "trialcut", "cell"])
def test_psd_and_result_match_vflip2_m(monkeypatch, name):
    case = CASES[name]
    result, psd, freqs = _run_capturing_psd(monkeypatch, _lfp(case), case["fs"])
    _assert_matches_matlab(result, psd, freqs, np.array(case["psd"], dtype=float),
                           case["results"])


def test_continuous_lfp_refuses_a_non_integer_fs_as_vflip2_m_fails():
    assert DOC["raw_noninteger_fs_error"] != "none", "vFLIP2.m must fail on this input"
    case = CASES["raw"]
    with pytest.raises(ValueError, match="integer fs"):
        vflip2_from_lfp(_lfp(case), case["fs"] + 0.5, contact_spacing=SPACING_UM)


@pytest.mark.skipif(not (DRYAD_DATA.exists() and DRYAD_REFERENCE.exists()),
                    reason="the Dryad vFLIP2 test data and vFLIP2.m's output are not on disk")
@pytest.mark.parametrize("field", ["raw", "trialcut"])
def test_dryad_test_data_match_vflip2_m(monkeypatch, field):
    from scipy import io

    data = io.loadmat(DRYAD_DATA, squeeze_me=True, struct_as_record=False)["vFLIP2_testdata"]
    ref = getattr(io.loadmat(DRYAD_REFERENCE, squeeze_me=True, struct_as_record=False)["out"],
                  field)
    matlab = {name: float(getattr(ref.results, name)) for name in ref.results._fieldnames}
    # run_reference.m calls vFLIP2 with intdist 0.1 and fsample 1000.
    result, psd, freqs = _run_capturing_psd(monkeypatch, getattr(data, field), 1000)
    _assert_matches_matlab(result, psd, freqs, np.asarray(ref.psd, dtype=float), matlab)


@pytest.mark.parametrize("fs", [0, -1000.0, np.nan, np.inf, True, "1000"])
def test_refuses_a_bad_fs(fs):
    with pytest.raises(ValueError, match="fs must be"):
        vflip2_from_lfp(np.zeros((4, 2000)), fs, contact_spacing=100.0)


@pytest.mark.parametrize("lfp, match", [
    (np.zeros(2000), "lfp must be"),
    (np.zeros((4, 2000, 2, 1)), "lfp must be"),
    (np.zeros((4, 999)), "at least one 1000-sample trial"),
    (np.zeros((4, 1000, 0)), "empty axis"),
    ([], "one or more"),
    ([np.zeros(1000)], "one or more"),
    ([np.zeros((4, 1000)), np.zeros((3, 1000))], "same channel count"),
])
def test_refuses_a_wrong_shape(lfp, match):
    with pytest.raises(ValueError, match=match):
        vflip2_from_lfp(lfp, 1000, contact_spacing=100.0)


def test_refuses_an_fs_that_puts_150_hz_past_the_fft():
    # At 100 Hz, 100-sample trials pad to 128 points and 150 Hz maps to bin 193.
    with pytest.raises(ValueError, match="150 Hz"):
        vflip2_from_lfp(np.ones((4, 100, 2)), 100.0, contact_spacing=100.0)
