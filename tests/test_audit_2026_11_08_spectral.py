"""Spectral and time-frequency docstring claims and refusals, each failing before its repair.

- cross_area_coherence: the default-segment claim, and the too-short advice with an explicit noverlap.
- aperiodic_fit: the psd contract names zero as refused.
- morlet_wavelet and complex_tfr: a non-finite or negative cutoff_sigma and a negative coi_sigma are refused.
- bipolar_reference: one channel is refused by name instead of returning zero rows.
- spectral_tilt: one sample is refused by the two-sample rule.
"""

import re

import numpy as np
import pytest

from jnwb.spectral._coupling import MIN_COHERENCE_NPERSEG, cross_area_coherence, welch_segment_count
from jnwb.spectral._psd import aperiodic_fit, spectral_tilt
from jnwb.spectral._reference import bipolar_reference
from jnwb.tfr import complex_tfr, morlet_wavelet

FS = 1000.0


def _pair(n, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(size=n), rng.normal(size=n)


def test_cross_area_coherence_segment_claim_matches_the_code():
    doc = cross_area_coherence.__doc__
    assert "15 segments for any N" not in doc
    assert "14 or 15" in doc
    assert "(N - nperseg) // (nperseg - noverlap)" in doc
    counts = set()
    for n in range(1024, 32769):
        nperseg = min(max(n // 8, MIN_COHERENCE_NPERSEG), 4096)
        counts.add(welch_segment_count(n, nperseg, nperseg // 2))
    assert counts == {14, 15}


def test_too_short_advice_gives_two_segments_with_an_explicit_noverlap():
    x, y = _pair(1000)
    with pytest.raises(ValueError, match="not identifiable") as info:
        cross_area_coherence(x, y, fs=FS, freq_bands="canonical", nperseg=600, noverlap=0)
    assert "from 1 Welch segment" in str(info.value)
    advised = int(re.search(r"<= (\d+) keeps at least 2 segments", str(info.value)).group(1))
    out = cross_area_coherence(x, y, fs=FS, freq_bands="canonical", nperseg=advised, noverlap=0)
    assert out["n_segments_used"] >= 2


def test_aperiodic_fit_docstring_refuses_zero_power_as_the_code_does():
    doc = aperiodic_fit.__doc__
    assert "strictly non-negative" not in doc
    assert "strictly positive and finite" in doc
    raises = doc.split("Raises:", 1)[1].split("References:", 1)[0]
    assert "zero" in raises


def test_aperiodic_fit_refuses_a_zero_power_bin():
    freqs = np.arange(1.0, 11.0)
    psd = np.ones(10)
    psd[3] = 0.0
    with pytest.raises(ValueError, match="non-positive"):
        aperiodic_fit(freqs, psd, (1.0, 10.0))


@pytest.mark.parametrize("cutoff", [-1.0, np.nan, np.inf])
def test_morlet_wavelet_refuses_a_bad_cutoff_by_name(cutoff):
    with pytest.raises(ValueError, match="cutoff_sigma"):
        morlet_wavelet(10.0, FS, cutoff_sigma=cutoff)


def test_complex_tfr_refuses_a_negative_coi_sigma_by_name():
    x = np.random.default_rng(0).normal(size=2000)
    with pytest.raises(ValueError, match="coi_sigma"):
        complex_tfr(x, fs=FS, freqs=np.array([10.0]), coi_sigma=-1.0)


def test_bipolar_reference_refuses_one_channel_by_name():
    with pytest.raises(ValueError, match="at least 2 channels"):
        bipolar_reference(np.ones((1, 50)))


def test_bipolar_reference_of_two_channels_has_one_row():
    assert bipolar_reference(np.arange(100.0).reshape(2, 50)).shape == (1, 50)


def test_spectral_tilt_refuses_one_sample_by_the_two_sample_rule():
    with pytest.raises(ValueError, match="needs at least 2"):
        spectral_tilt(np.array([1.0]), fs=FS, freq_range=(1.0, 100.0))

