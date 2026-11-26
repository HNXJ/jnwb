"""Recovery of a planted jaxfne planar wave by jnwb's Welch PSD.

The excerpt is jaxfne's protocol_c planar traveling wave at the frozen spec values, with
seeded additive noise, plus a noise-only control. Its commit, seeds, generator settings and
planted frequency are in jaxfne_planar_wave.provenance.json.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

import jnwb

DATA_DIR = Path(__file__).resolve().parent / "data"
EXCERPT_PATH = DATA_DIR / "jaxfne_planar_wave.npz"
PROVENANCE_PATH = DATA_DIR / "jaxfne_planar_wave.provenance.json"

# Welch reads the peak off a grid of bin centres spaced fs / nperseg apart. A frequency
# between two centres is at most half a spacing from the nearest one, so the tolerance is
# half a bin. The planted 10 Hz lies on a centre for every nperseg used here (the grids are
# 0.5 Hz and 1 Hz), so the expected error is zero; half a bin is the bound the test allows.
HALF_BIN = 0.5


def _load() -> tuple[dict, dict[str, np.ndarray]]:
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    with np.load(EXCERPT_PATH) as npz:
        arrays = {name: npz[name] for name in npz.files}
    return provenance, arrays


def _assert_planted_truth(provenance: dict, arrays: dict[str, np.ndarray]) -> None:
    truth = provenance["ground_truth"]
    assert truth["spectral_peak_hz"] > 0.0, "fixture must plant a nonzero frequency"
    assert truth["amplitude"] > 0.0, "fixture must plant a nonzero wave"
    assert truth["noise_sigma"] > 0.0, "fixture must plant noise"
    field = arrays["field"]
    assert field.shape == (provenance["sampling"]["n_samples"], provenance["sampling"]["n_sites"])
    assert np.var(field) > 0.0, "fixture must carry signal"
    fs_hz = provenance["sampling"]["fs_hz"]
    np.testing.assert_allclose(np.diff(arrays["time_s"]), 1.0 / fs_hz, rtol=1e-12)


def _peak_frequencies(
    trace: np.ndarray, fs_hz: float, nperseg: int
) -> tuple[np.ndarray, np.ndarray]:
    """Peak frequency (Hz) and peak PSD per channel of a (n_samples, n_channels) trace."""
    freqs_hz, psd = jnwb.compute_psd(trace, fs_hz, axis=0, nperseg=nperseg)
    peak_index = np.argmax(psd, axis=0)
    channels = np.arange(psd.shape[1])
    return freqs_hz[peak_index], psd[peak_index, channels]


def test_planted_truth_is_recorded_and_nonzero():
    provenance, arrays = _load()
    _assert_planted_truth(provenance, arrays)


def test_psd_peak_recovers_planted_frequency_at_every_site():
    provenance, arrays = _load()
    _assert_planted_truth(provenance, arrays)
    fs_hz = provenance["sampling"]["fs_hz"]
    n_samples = arrays["field"].shape[0]
    tol_hz = HALF_BIN * fs_hz / n_samples
    planted_hz = provenance["ground_truth"]["spectral_peak_hz"]

    peak_hz, _ = _peak_frequencies(arrays["field"], fs_hz, nperseg=n_samples)

    assert np.all(np.abs(peak_hz - planted_hz) <= tol_hz), (
        f"planted {planted_hz} Hz, recovered {peak_hz} Hz, tolerance {tol_hz} Hz"
    )


def test_noise_only_control_does_not_recover_the_planted_peak():
    provenance, arrays = _load()
    _assert_planted_truth(provenance, arrays)
    fs_hz = provenance["sampling"]["fs_hz"]
    n_samples = arrays["noise_only_control"].shape[0]
    tol_hz = HALF_BIN * fs_hz / n_samples
    planted_hz = provenance["ground_truth"]["spectral_peak_hz"]

    peak_hz, _ = _peak_frequencies(arrays["noise_only_control"], fs_hz, nperseg=n_samples)

    assert np.all(np.abs(peak_hz - planted_hz) > tol_hz), (
        f"control peaks {peak_hz} Hz sit within {tol_hz} Hz of planted {planted_hz} Hz"
    )


def test_recovery_holds_in_each_half_and_the_peak_power_changes_with_the_slice():
    provenance, arrays = _load()
    _assert_planted_truth(provenance, arrays)
    fs_hz = provenance["sampling"]["fs_hz"]
    n_samples = arrays["field"].shape[0]
    half = n_samples // 2
    tol_hz = HALF_BIN * fs_hz / half
    planted_hz = provenance["ground_truth"]["spectral_peak_hz"]

    peak_a, power_a = _peak_frequencies(arrays["field"][:half], fs_hz, nperseg=half)
    peak_b, power_b = _peak_frequencies(arrays["field"][half:], fs_hz, nperseg=half)

    assert np.all(np.abs(peak_a - planted_hz) <= tol_hz), f"first half peaks {peak_a} Hz"
    assert np.all(np.abs(peak_b - planted_hz) <= tol_hz), f"second half peaks {peak_b} Hz"
    assert not np.array_equal(power_a, power_b), "peak power must differ between data slices"


BROADBAND_EXCERPT_PATH = DATA_DIR / "jaxfne_delayed_broadband.npz"
BROADBAND_PROVENANCE_PATH = DATA_DIR / "jaxfne_delayed_broadband.provenance.json"
BROADBAND_BAND = {"broadband": (4.0, 44.0)}
BROADBAND_NPERSEG = 250
BROADBAND_GC_ORDER = 10


def _load_broadband() -> tuple[dict, dict[str, np.ndarray]]:
    provenance = json.loads(BROADBAND_PROVENANCE_PATH.read_text(encoding="utf-8"))
    with np.load(BROADBAND_EXCERPT_PATH) as npz:
        arrays = {name: npz[name] for name in npz.files}
    return provenance, arrays


def _deranged_permutation(n_trials: int, seed: int = 12345) -> np.ndarray:
    rng = np.random.default_rng(seed)
    identity = np.arange(n_trials)
    perm = rng.permutation(n_trials)
    while np.any(perm == identity):
        perm = rng.permutation(n_trials)
    return perm


def test_delayed_broadband_provenance_and_integrity():
    provenance, arrays = _load_broadband()
    assert set(arrays) == set(provenance["arrays"])
    for name, arr in arrays.items():
        meta = provenance["arrays"][name]
        assert list(arr.shape) == meta["shape"]
        assert str(arr.dtype) == meta["dtype"]
        assert hashlib.sha256(arr.tobytes()).hexdigest() == meta["sha256_of_bytes"]

    sampling = provenance["sampling"]
    fs_hz = sampling["fs_hz"]
    np.testing.assert_allclose(np.diff(arrays["time_s"]), 1.0 / fs_hz, rtol=1e-12)
    expected_shape = (sampling["n_trials"], sampling["n_samples"], sampling["n_sites"])
    for cond in ("forward_x_to_y", "reverse_y_to_x", "uncoupled_null", "zero_lag_common_source"):
        arr = arrays[cond]
        assert arr.shape == expected_shape
        assert np.all(np.isfinite(arr))
        assert float(np.min(arr)) > 0.0, f"{cond} touched rate floor"
        assert float(np.var(arr)) > 0.0

    unc_var = float(np.var(arrays["uncoupled_null"]))
    theo_var = provenance["theoretical_model"]["uncoupled_stationary_variance"]
    assert unc_var == pytest.approx(theo_var, rel=0.25)
    assert provenance["source"]["git_status_short_clean"] is True
    assert "not empirical validation" in provenance["validation_scope"]


def test_delayed_broadband_psd_matches_ar1_spectrum():
    provenance, arrays = _load_broadband()
    fs_hz = provenance["sampling"]["fs_hz"]
    dt_s = 1.0 / fs_hz
    alpha = provenance["theoretical_model"]["alpha"]
    sigma = provenance["generator_configuration"]["sigma"]

    unc = arrays["uncoupled_null"]
    freqs, psd_unc = jnwb.compute_psd(unc[:, :, 0], fs_hz, axis=1, nperseg=BROADBAND_NPERSEG)
    psd_mean = psd_unc.mean(axis=0)

    sigma_eps2 = (sigma ** 2) * alpha
    theo_psd = (
        2.0
        * dt_s
        * sigma_eps2
        / (1.0 + (1.0 - alpha) ** 2 - 2.0 * (1.0 - alpha) * np.cos(2.0 * np.pi * freqs * dt_s))
    )
    band_mask = (freqs >= 4.0) & (freqs <= 200.0)
    log_r = float(np.corrcoef(np.log10(psd_mean[band_mask]), np.log10(theo_psd[band_mask]))[0, 1])
    mean_rel_err = float(
        np.mean(np.abs(psd_mean[band_mask] - theo_psd[band_mask]) / theo_psd[band_mask])
    )
    assert log_r > 0.95
    assert mean_rel_err < 0.25

    low_mask = (freqs >= 4.0) & (freqs <= 24.0)
    high_mask = (freqs >= 100.0) & (freqs <= 250.0)
    assert float(psd_mean[low_mask].mean() / psd_mean[high_mask].mean()) > 3.0

    fwd = arrays["forward_x_to_y"]
    for site in (0, 1):
        _, psd_site = jnwb.compute_psd(fwd[:, :, site], fs_hz, axis=1, nperseg=BROADBAND_NPERSEG)
        site_mean = psd_site.mean(axis=0)
        assert float(site_mean[low_mask].mean() / site_mean[high_mask].mean()) > 3.0


def test_delayed_broadband_positive_forward_recovery():
    provenance, arrays = _load_broadband()
    fs_hz = provenance["sampling"]["fs_hz"]
    fwd = arrays["forward_x_to_y"]
    X, Y = fwd[:, :, 0], fwd[:, :, 1]

    psi = jnwb.phase_slope_index(
        X, Y, fs=fs_hz, bands=BROADBAND_BAND, nperseg=BROADBAND_NPERSEG, jackknife=True,
        signal_class="lfp",
    )
    assert psi.net > 0.0
    assert psi.params["jackknife_unit"] == "trial"
    assert psi.p_net is not None and psi.p_net < 0.01
    assert psi.diagnostics["ok_for_interpretation"] is True
    psi_rev = jnwb.phase_slope_index(
        Y, X, fs=fs_hz, bands=BROADBAND_BAND, nperseg=BROADBAND_NPERSEG, jackknife=True,
        signal_class="lfp",
    )
    assert psi_rev.net == pytest.approx(-psi.net, abs=1e-12)

    gc = jnwb.granger(
        X, Y, order=BROADBAND_GC_ORDER, n_surrogates=200, rng=0, signal_class="lfp"
    )
    gc_repeat = jnwb.granger(
        X, Y, order=BROADBAND_GC_ORDER, n_surrogates=200, rng=0, signal_class="lfp"
    )
    assert gc.x_to_y > gc.y_to_x
    assert gc.net > 0.0
    assert gc.p_x_to_y is not None and gc.p_x_to_y < 0.05
    assert gc.p_x_to_y == gc_repeat.p_x_to_y

    gtr = jnwb.granger_time_reversed(X, Y, order=BROADBAND_GC_ORDER, signal_class="lfp")
    assert gtr.net > 0.0
    assert gtr.diagnostics["sign_flip"] is True
    assert gtr.diagnostics["ok_for_interpretation"] is True

    gs = jnwb.granger_spectral(
        X, Y, fs=fs_hz, order=BROADBAND_GC_ORDER, bands=BROADBAND_BAND, signal_class="lfp"
    )
    assert gs.x_to_y > gs.y_to_x
    assert gs.net > 0.0

    gnp = jnwb.granger_nonparametric(X, Y, fs=fs_hz, bands=BROADBAND_BAND, n_freqs=129)
    assert gnp.x_to_y > gnp.y_to_x
    assert gnp.net > 0.0


def test_delayed_broadband_unwrapped_phase_linearity_separates_filter_lag_from_synaptic_delay():
    provenance, arrays = _load_broadband()
    fs_hz = provenance["sampling"]["fs_hz"]
    dt_s = 1.0 / fs_hz
    alpha = provenance["theoretical_model"]["alpha"]
    weight = provenance["ground_truth"]["realized_edge_weight"]
    d_steps = provenance["ground_truth"]["discrete_arrival_lag_steps"]
    planted_delay_ms = provenance["ground_truth"]["planted_synaptic_delay_ms"]

    fwd = arrays["forward_x_to_y"]
    freqs, pxy = signal.csd(fwd[:, :, 0], fwd[:, :, 1], fs=fs_hz, nperseg=BROADBAND_NPERSEG, axis=1)
    # scipy.signal.csd computes E[X* Y]; conjugate gives S_xy = E[X Y*] to match PSI sign.
    pxy_mean = np.conj(pxy.mean(axis=0))

    passband = (freqs >= 4.0) & (freqs <= 32.0)
    phase_obs = np.unwrap(np.angle(pxy_mean[passband]))
    omega = 2.0 * np.pi * freqs[passband]
    slope_obs, intercept_obs = np.polyfit(omega, phase_obs, 1)
    pred = slope_obs * omega + intercept_obs
    ss_res = float(np.sum((phase_obs - pred) ** 2))
    ss_tot = float(np.sum((phase_obs - np.mean(phase_obs)) ** 2))
    r2 = 1.0 - ss_res / ss_tot

    z = np.exp(-1j * omega * dt_s)
    transfer_h = alpha * weight * (z ** d_steps) / (1.0 - (1.0 - alpha) * z)
    phase_theo = np.unwrap(np.angle(np.conj(transfer_h)))
    slope_theo, _ = np.polyfit(omega, phase_theo, 1)

    est_delay_ms = float(slope_obs * 1000.0)
    theo_delay_ms = float(slope_theo * 1000.0)
    assert r2 > 0.95
    assert abs(est_delay_ms - theo_delay_ms) <= 1.5
    assert est_delay_ms > planted_delay_ms


def test_delayed_broadband_negative_reverse_control():
    provenance, arrays = _load_broadband()
    fs_hz = provenance["sampling"]["fs_hz"]
    rev = arrays["reverse_y_to_x"]
    X, Y = rev[:, :, 0], rev[:, :, 1]

    psi = jnwb.phase_slope_index(
        X, Y, fs=fs_hz, bands=BROADBAND_BAND, nperseg=BROADBAND_NPERSEG, jackknife=True,
        signal_class="lfp",
    )
    assert psi.net < 0.0
    assert psi.p_net is not None and psi.p_net < 0.01
    assert psi.diagnostics["ok_for_interpretation"] is True

    gc = jnwb.granger(
        X, Y, order=BROADBAND_GC_ORDER, n_surrogates=200, rng=0, signal_class="lfp"
    )
    assert gc.net < 0.0
    assert gc.y_to_x > gc.x_to_y
    assert gc.p_y_to_x is not None and gc.p_y_to_x < 0.05

    gtr = jnwb.granger_time_reversed(X, Y, order=BROADBAND_GC_ORDER, signal_class="lfp")
    assert gtr.net < 0.0
    assert gtr.diagnostics["sign_flip"] is True
    assert gtr.diagnostics["ok_for_interpretation"] is True

    gs = jnwb.granger_spectral(
        X, Y, fs=fs_hz, order=BROADBAND_GC_ORDER, bands=BROADBAND_BAND, signal_class="lfp"
    )
    assert gs.net < 0.0

    gnp = jnwb.granger_nonparametric(X, Y, fs=fs_hz, bands=BROADBAND_BAND, n_freqs=129)
    assert gnp.net < 0.0


def test_delayed_broadband_uncoupled_null_control():
    provenance, arrays = _load_broadband()
    fs_hz = provenance["sampling"]["fs_hz"]
    fwd = arrays["forward_x_to_y"]
    unc = arrays["uncoupled_null"]

    fwd_psi = jnwb.phase_slope_index(
        fwd[:, :, 0], fwd[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND,
        nperseg=BROADBAND_NPERSEG, jackknife=True, signal_class="lfp",
    )
    fwd_gc = jnwb.granger(
        fwd[:, :, 0], fwd[:, :, 1], order=BROADBAND_GC_ORDER, n_surrogates=0, signal_class="lfp"
    )
    fwd_gnp = jnwb.granger_nonparametric(
        fwd[:, :, 0], fwd[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND, n_freqs=129
    )

    psi = jnwb.phase_slope_index(
        unc[:, :, 0], unc[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND,
        nperseg=BROADBAND_NPERSEG, jackknife=True, signal_class="lfp",
    )
    assert psi.p_net is not None and psi.p_net > 0.05
    assert abs(psi.net) < 0.25 * fwd_psi.net

    gc = jnwb.granger(
        unc[:, :, 0], unc[:, :, 1], order=BROADBAND_GC_ORDER, n_surrogates=200, rng=0,
        signal_class="lfp",
    )
    assert gc.p_x_to_y is not None and gc.p_x_to_y > 0.05
    assert gc.p_y_to_x is not None and gc.p_y_to_x > 0.05
    assert abs(gc.net) < 0.20 * fwd_gc.net

    gnp = jnwb.granger_nonparametric(
        unc[:, :, 0], unc[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND, n_freqs=129
    )
    assert abs(gnp.net) < 0.20 * fwd_gnp.net


def test_delayed_broadband_zero_lag_common_source_control():
    provenance, arrays = _load_broadband()
    fs_hz = provenance["sampling"]["fs_hz"]
    fwd = arrays["forward_x_to_y"]
    cs = arrays["zero_lag_common_source"]

    zero_lag_r = float(np.mean([np.corrcoef(x, y)[0, 1] for x, y in zip(cs[:, :, 0], cs[:, :, 1])]))
    assert zero_lag_r > 0.7, "fixture must carry strong zero-lag common-source correlation"

    fwd_psi = jnwb.phase_slope_index(
        fwd[:, :, 0], fwd[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND,
        nperseg=BROADBAND_NPERSEG, jackknife=True, signal_class="lfp",
    )
    fwd_gtr = jnwb.granger_time_reversed(
        fwd[:, :, 0], fwd[:, :, 1], order=BROADBAND_GC_ORDER, signal_class="lfp"
    )
    fwd_gnp = jnwb.granger_nonparametric(
        fwd[:, :, 0], fwd[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND, n_freqs=129
    )

    # Phase slope index shows reduced sensitivity to zero-lag common-source mixing.
    psi = jnwb.phase_slope_index(
        cs[:, :, 0], cs[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND,
        nperseg=BROADBAND_NPERSEG, jackknife=True, signal_class="lfp",
    )
    assert psi.p_net is not None and psi.p_net > 0.05
    assert abs(psi.net) < 0.25 * fwd_psi.net

    gtr = jnwb.granger_time_reversed(
        cs[:, :, 0], cs[:, :, 1], order=BROADBAND_GC_ORDER, signal_class="lfp"
    )
    assert (not gtr.diagnostics["ok_for_interpretation"]) or (abs(gtr.net) < 0.20 * fwd_gtr.net)

    gnp = jnwb.granger_nonparametric(
        cs[:, :, 0], cs[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND, n_freqs=129
    )
    assert abs(gnp.net) < 0.20 * fwd_gnp.net


def test_delayed_broadband_trial_shuffle_control():
    provenance, arrays = _load_broadband()
    fs_hz = provenance["sampling"]["fs_hz"]
    fwd = arrays["forward_x_to_y"]
    X = fwd[:, :, 0]
    perm = _deranged_permutation(X.shape[0])
    Y_shuf = fwd[perm, :, 1]

    fwd_psi = jnwb.phase_slope_index(
        fwd[:, :, 0], fwd[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND,
        nperseg=BROADBAND_NPERSEG, jackknife=True, signal_class="lfp",
    )
    fwd_gc = jnwb.granger(
        fwd[:, :, 0], fwd[:, :, 1], order=BROADBAND_GC_ORDER, n_surrogates=0, signal_class="lfp"
    )
    fwd_gnp = jnwb.granger_nonparametric(
        fwd[:, :, 0], fwd[:, :, 1], fs=fs_hz, bands=BROADBAND_BAND, n_freqs=129
    )

    psi = jnwb.phase_slope_index(
        X, Y_shuf, fs=fs_hz, bands=BROADBAND_BAND,
        nperseg=BROADBAND_NPERSEG, jackknife=True, signal_class="lfp",
    )
    assert psi.p_net is not None and psi.p_net > 0.05
    assert abs(psi.net) < 0.25 * fwd_psi.net

    gc = jnwb.granger(
        X, Y_shuf, order=BROADBAND_GC_ORDER, n_surrogates=200, rng=0, signal_class="lfp"
    )
    assert gc.p_x_to_y is not None and gc.p_x_to_y > 0.05
    assert abs(gc.net) < 0.20 * fwd_gc.net

    gnp = jnwb.granger_nonparametric(
        X, Y_shuf, fs=fs_hz, bands=BROADBAND_BAND, n_freqs=129
    )
    assert abs(gnp.net) < 0.20 * fwd_gnp.net

