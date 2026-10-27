"""Recovery of a planted jaxfne planar wave by jnwb's Welch PSD.

The excerpt is jaxfne's protocol_c planar traveling wave at the frozen spec values, with
seeded additive noise, plus a noise-only control. Its commit, seeds, generator settings and
planted frequency are in jaxfne_planar_wave.provenance.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

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
