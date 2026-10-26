"""The three coefficient-of-determination sites call one helper and keep their values.

The pinned values are what the sites returned on the fixed inputs below before the helper
replaced their formulas. A flat spectrum has no variance to explain, so its R-squared is NaN.
"""
import inspect
import math

import numpy as np
import pytest
from numpy.testing import assert_allclose

from jnwb.laminar._vflip2 import _band_regress
from jnwb.onset_fitting import fit_exponential_onset, onset_model
from jnwb.spectral._psd import aperiodic_fit, spectral_tilt


def test_the_onset_fit_keeps_its_r2_on_a_fixed_input():
    t = np.arange(-100.0, 500.0, 5.0)
    clean = onset_model(t, t0=100.0, tau=30.0, amplitude=20.0, baseline=5.0)
    rate = clean + np.random.default_rng(0).normal(0.0, 1.0, t.size)
    fit = fit_exponential_onset(t, rate, t0_bounds=(0.0, 400.0))
    assert fit["converged"] is True, "fixture must converge"
    assert_allclose(fit["r2"], 0.989982842212482, rtol=1e-12)


def test_the_spectral_tilt_keeps_its_fit_quality_on_a_fixed_input():
    fs = 1000.0
    tt = np.arange(0.0, 8.0, 1.0 / fs)
    lfp = np.cumsum(np.random.default_rng(1).normal(size=tt.size)) * 0.01
    assert_allclose(spectral_tilt(lfp, fs=fs)["fit_quality"], 0.8121180013921898, rtol=1e-12)


def _psd_fixture():
    freqs = np.arange(1.0, 100.0, 0.5)
    psd = 10 ** (1.0 - 1.5 * np.log10(freqs)) * np.exp(0.05 * np.random.default_rng(2).normal(size=freqs.size))
    return freqs, psd


def test_the_aperiodic_fit_keeps_its_r_squared_on_a_fixed_input():
    freqs, psd = _psd_fixture()
    fit = aperiodic_fit(freqs, psd, freq_range=(2.0, 90.0), mode="fixed")
    assert_allclose(fit.r_squared, 0.9985361564055385, rtol=1e-12)


def test_a_flat_spectrum_has_no_r_squared():
    freqs, _ = _psd_fixture()
    fit = aperiodic_fit(freqs, np.full(freqs.size, 3.0), freq_range=(2.0, 90.0), mode="fixed")
    assert math.isnan(fit.r_squared)


def test_the_helper_is_one_minus_the_ratio_as_a_float_and_nan_without_variance():
    from jnwb._spread import r_squared

    assert r_squared(1.0, 4.0) == 0.75
    assert isinstance(r_squared(np.float64(1.0), np.float64(4.0)), float)
    assert math.isnan(r_squared(0.0, 0.0))
    assert math.isnan(r_squared(1.0, 0.5, floor=0.5)), "ss_tot must exceed the floor"
    assert r_squared(1.0, 0.6, floor=0.5) == pytest.approx(1.0 - 1.0 / 0.6, rel=1e-15)


@pytest.mark.parametrize("site, call", [
    (fit_exponential_onset, "r_squared(ss_res, ss_tot)"),
    (spectral_tilt, "_r_squared(ss_res, ss_tot)"),
    (aperiodic_fit, "_r_squared(ss_res, ss_tot, floor=flat_tol)"),
    (_band_regress, "r_squared(sse, tss)"),
])
def test_each_site_calls_the_shared_helper(site, call):
    assert call in inspect.getsource(site), f"{site.__name__} must call the shared helper"


def test_the_band_regression_keeps_its_r_squared_on_a_fixed_input():
    band = np.random.default_rng(11).normal(size=40)
    band[[5, 17]] = np.nan
    _, r2, _ = _band_regress(band)
    assert_allclose(r2, 0.11596152714165153, rtol=1e-12)


def test_a_flat_band_keeps_its_minus_infinite_r_squared():
    """A band with no variance but a residual keeps -inf; the helper would give NaN."""
    assert _band_regress(np.full(12, 3.0))[1] == -math.inf
