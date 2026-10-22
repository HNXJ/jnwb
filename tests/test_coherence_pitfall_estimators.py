"""Partial coherence and the paired-epoch bias floor of ``cross_area_coherence``.

Partial coherence conditions the coherence between two signals on further signals
(Dahlhaus, 2000). The paired-epoch floor is the coherence that trials paired at random
produce, the bias that a finite trial count leaves (Maris, Schoffelen and Fries, 2007;
Bastos and Schoffelen, 2016). The default outputs are pinned to the values the estimator
returned before these keywords existed.
"""

import re
from collections import Counter

import numpy as np
import pytest
from numpy.testing import assert_allclose
from scipy import signal, stats

import jnwb
from jnwb.spectral._common import CANONICAL_BANDS

FS = 1000.0

# --- values the estimator returned before these keywords existed ------------------------
# Recorded from the pre-change code on a fixed input; not re-derived from the new code.

BASE_DEFAULT_KEYS = {
    "band_coherence", "band_significance", "coherence_spectrum", "device_used",
    "frequencies", "n_segments_used", "n_surrogates_used", "noverlap", "nperseg",
    "p_value_floor", "peak_coherence_freq", "peak_coherence_value",
    "surrogate_seed_entropy",
}

BASE_DEFAULT_BAND_COHERENCE = {
    "theta": 0.2090709703631849,
    "alpha": 0.11845914678681849,
    "beta": 0.3620046691169042,
    "low_gamma": 0.28209797137491366,
    "high_gamma": 0.2833337761436651,
}

BASE_DEFAULT_BAND_SIGNIFICANCE = {
    "theta": 0.09803921568627451,
    "alpha": 0.27450980392156865,
    "beta": 0.0196078431372549,
    "low_gamma": 0.0196078431372549,
    "high_gamma": 0.0196078431372549,
}

BASE_DEFAULT_COHERENCE_SPECTRUM = [
    0.45754856973515573, 0.360438182866155, 0.0577037578602148, 0.1792145357134222,
    0.31864187858408183, 0.4198799612396868, 0.2919686489733314, 0.4175281876705167,
    0.15180996199984556, 0.2793604672053505, 0.2721867612996057, 0.3142454069647226,
    0.39288725940504415, 0.46535651522132193, 0.2743890012043757, 0.3759635748456953,
    0.2306856714167975, 0.29788914362514723, 0.3175168237666144, 0.12730764321160887,
    0.17756183585776011, 0.15407928892525613, 0.23553528579612673, 0.5616356165127369,
    0.5122148772902717, 0.14464338867745286, 0.37550885271569995, 0.30054074495678607,
    0.07614426230368872, 0.025741500218295663, 0.07975928661479414, 0.1704654406014554,
    0.2882870009065463, 0.12587866253249225, 0.21000886380041134, 0.23470747875557169,
    0.28689456061810986, 0.33378741327332556, 0.0683929034802171, 0.1917834250340076,
    0.4798870032610547, 0.36525942474653933, 0.18584078059457232, 0.39237502180530115,
    0.2611642430228412, 0.31694908094162905, 0.5183474284748546, 0.25354834376764696,
    0.06496372473770622, 0.02378630736145727, 0.22148732358639756, 0.3668363616526808,
    0.36500450646012744, 0.24468889333678936, 0.21581024218214628, 0.44694211829818603,
    0.4114086077343618, 0.1400231041905468, 0.33828965520648074, 0.47919214859094333,
    0.10268044180424286, 0.09274022235834051, 0.22296041926508758, 0.27676667124089765,
    0.44290429088462197, 0.2760298451067837, 0.25615292487261837, 0.48338376478778006,
    0.5032849936243934, 0.30680902489120404, 0.3179633559731661, 0.2930558042982906,
    0.5107942379740887, 0.16277039623921283, 0.1808381778954566, 0.33828190297481864,
    0.46356359236507866, 0.32688774342044113, 0.3215984840339457, 0.5230068460258012,
    0.39002674265630655, 0.15875997163623265, 0.2007778598673876, 0.4896466573934918,
    0.20269294804370447, 0.32659949100243874, 0.49692143250939963, 0.3259851236325087,
    0.17176153228158783, 0.48652120387047376, 0.3761865430665792, 0.32209214619627474,
    0.5594158520229674, 0.3879289558514485, 0.1905829853525065, 0.43868512376594176,
    0.011725982348436048, 0.08339178181288798, 0.34262475150482186, 0.19777895754481278,
    0.3829035939640719, 0.22141362135769763, 0.34848979008724984, 0.07380301909547392,
    0.3491789793959648, 0.33353590447944087, 0.24368557321879536, 0.5255604091484285,
    0.5750546963751765, 0.4123576928059064, 0.5222148809127197, 0.4162832857346893,
    0.19551401386101308, 0.12510617535064408, 0.29917302778059, 0.32301593456246863,
    0.21885422751458997, 0.3544662857098725, 0.4447849632943264, 0.35066156356060235,
    0.3745747125616715, 0.13504835725289183, 0.3570185117829272, 0.3123565070248362,
    0.24168036519436492, 0.34404122655968694,
]

BASE_EXPLICIT_BAND_COHERENCE = {"low": 0.2758301982153717, "high": 0.28255403956940456}
BASE_EXPLICIT_BAND_SIGNIFICANCE = {"low": 0.03225806451612903, "high": 0.06451612903225806}


def _pinned_pair():
    rng = np.random.default_rng(7)
    x = rng.normal(size=2000)
    y = 0.6 * x + rng.normal(size=2000)
    return x, y


def _driver_triplet(seed, n=4000):
    """A 15-25 Hz driver z feeds x and y at zero lag; x and y share no other path."""
    rng = np.random.default_rng(seed)
    sos = signal.butter(4, [15.0, 25.0], btype="bandpass", fs=FS, output="sos")
    z = signal.sosfiltfilt(sos, rng.normal(size=n))
    z = z / np.std(z)
    x = z + 0.5 * rng.normal(size=n)
    y = z + 0.5 * rng.normal(size=n)
    return x, y, z


def _independent_trials(seed, n_trials=20, n_times=1000):
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n_trials, n_times)), rng.normal(size=(n_trials, n_times))


def _rhythm_trials(seed, n_trials=20, n_times=1000):
    """A 24 Hz rhythm shared by x and y within each trial, at a random phase per trial."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_times) / FS
    phase = rng.uniform(0.0, 2.0 * np.pi, size=(n_trials, 1))
    shared = np.sin(2.0 * np.pi * 24.0 * t[None, :] + phase)
    x = shared + rng.normal(size=(n_trials, n_times))
    y = shared + rng.normal(size=(n_trials, n_times))
    return x, y


# --- the default outputs are unchanged --------------------------------------------------


def test_default_outputs_are_unchanged_bit_for_bit():
    x, y = _pinned_pair()
    default = jnwb.cross_area_coherence(x, y, fs=FS, freq_bands="canonical")
    assert set(default) == BASE_DEFAULT_KEYS, "a default call gained or lost a key"
    assert_allclose(default["frequencies"], np.arange(126) * 4.0, rtol=1e-12, atol=0)
    assert_allclose(default["coherence_spectrum"], BASE_DEFAULT_COHERENCE_SPECTRUM,
                    rtol=1e-12, atol=0)
    for band, value in BASE_DEFAULT_BAND_COHERENCE.items():
        assert_allclose(default["band_coherence"][band], value, rtol=1e-12, atol=0)
    assert default["band_significance"] == BASE_DEFAULT_BAND_SIGNIFICANCE
    assert default["peak_coherence_freq"] == 432.0
    assert_allclose(default["peak_coherence_value"], 0.5750546963751765, rtol=1e-12, atol=0)
    assert default["n_segments_used"] == 15
    assert default["surrogate_seed_entropy"] == 42
    assert default["device_used"] == "cpu"


def test_explicit_segmentation_and_seed_outputs_are_unchanged_bit_for_bit():
    x, y = _pinned_pair()
    res = jnwb.cross_area_coherence(
        x, y, fs=FS, freq_bands={"low": (2.0, 20.0), "high": (20.0, 80.0)},
        rng=7, n_surrogates=30, nperseg=256, noverlap=100,
    )
    assert set(res) == BASE_DEFAULT_KEYS
    for band, value in BASE_EXPLICIT_BAND_COHERENCE.items():
        assert_allclose(res["band_coherence"][band], value, rtol=1e-12, atol=0)
    assert res["band_significance"] == BASE_EXPLICIT_BAND_SIGNIFICANCE
    assert_allclose(res["peak_coherence_value"], 0.6113799310510335, rtol=1e-12, atol=0)
    assert res["peak_coherence_freq"] == 0.0
    assert res["n_segments_used"] == 12
    assert res["surrogate_seed_entropy"] == 7


# --- partial coherence ------------------------------------------------------------------


def test_common_driver_partial_rejects_at_the_5_percent_rate_over_12_seeds():
    """Over 12 seeds of 2000 samples with 49 surrogates, coherence is significant in the driven
    band at every seed, and the partial coherence given the driver rejects at the rate of the
    circular-shift null. With 49 surrogates p = (k + 1) / 50, so p < 0.05 needs k <= 1: a
    null rejection rate of 2/50 = 0.04. At that rate, the bound of at most 3 rejections of 12
    has upper tail P(X >= 4) = 0.0010, the tail of the former bound of 6 of 40, P(X >= 7) =
    0.0010."""
    coherence_rejections = 0
    partial_rejections = 0
    for seed in range(12):
        x, y, z = _driver_triplet(seed, n=2000)
        res = jnwb.cross_area_coherence(
            x, y, fs=FS, freq_bands="canonical", n_surrogates=49, rng=seed, condition_on=z,
        )
        coherence_rejections += res["band_significance"]["beta"] < 0.05
        partial_rejections += res["partial_band_significance"]["beta"] < 0.05
    assert coherence_rejections >= 11, f"coherence significant at {coherence_rejections} of 12"
    assert partial_rejections <= 3, f"partial significant at {partial_rejections} of 12"


def test_independent_conditioner_keeps_partial_within_0p06_of_coherence_over_30_seeds():
    worst = 0.0
    for seed in range(30):
        rng = np.random.default_rng(100 + seed)
        x, y, z = rng.normal(size=(3, 4000))
        # The observed values do not depend on the surrogate count, so one surrogate suffices.
        res = jnwb.cross_area_coherence(
            x, y, fs=FS, freq_bands="canonical", rng=seed, n_surrogates=1, condition_on=z,
        )
        for band in CANONICAL_BANDS:
            gap = abs(res["partial_coherence"][band] - res["band_coherence"][band])
            worst = max(worst, gap)
    assert worst <= 0.06, f"largest |partial - coherence| over 30 seeds is {worst}"


def test_partial_spectrum_is_a_per_frequency_companion_of_the_coherence_spectrum():
    x, y, z = _driver_triplet(1)
    res = jnwb.cross_area_coherence(
        x, y, fs=FS, freq_bands="canonical", n_surrogates=1, condition_on=z,
    )
    spectrum = res["partial_coherence_spectrum"]
    assert spectrum.shape == res["coherence_spectrum"].shape
    assert np.all(np.isfinite(spectrum))
    assert np.all((spectrum >= 0.0) & (spectrum <= 1.0 + 1e-12))


def test_a_singular_cross_spectral_matrix_is_refused_with_its_frequency():
    rng = np.random.default_rng(5)
    x = rng.normal(size=2000)
    y = rng.normal(size=2000)
    with pytest.raises(ValueError, match="singular") as info:
        jnwb.cross_area_coherence(x, y, fs=FS, freq_bands="canonical", condition_on=2.0 * x)
    assert re.search(r"at [0-9.]+ Hz", str(info.value)), str(info.value)


def test_condition_on_is_refused_with_bias_floor():
    X, Y = _independent_trials(0)
    with pytest.raises(ValueError, match="condition_on"):
        jnwb.cross_area_coherence(
            X, Y, fs=FS, freq_bands="canonical", bias_floor="paired_epochs",
            condition_on=X[0],
        )


# --- the paired-epoch bias floor --------------------------------------------------------


def test_independent_trials_exceed_floor_q95_at_1_to_13_of_100_seeds_in_every_band():
    # At a 5% exceedance rate, 14 or more of 100 has tail probability 0.0005 (binom.sf). The
    # bound is wide so that a seed near the floor on another platform does not decide the test.
    counts = {band: 0 for band in CANONICAL_BANDS}
    for seed in range(100):
        X, Y = _independent_trials(seed)
        res = jnwb.cross_area_coherence(
            X, Y, fs=FS, freq_bands="canonical", bias_floor="paired_epochs", rng=seed,
            n_pairings=50,
        )
        for band in CANONICAL_BANDS:
            if res["band_coherence"][band] > res["floor_q95"][band]:
                counts[band] += 1
    assert all(1 <= count <= 13 for count in counts.values()), (
        f"observed coherence exceeded floor_q95 at {counts} of 100 seeds; each band needs 1 to 13"
    )


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_planted_shared_rhythm_exceeds_the_floor(seed):
    X, Y = _rhythm_trials(seed)
    res = jnwb.cross_area_coherence(
        X, Y, fs=FS, freq_bands="canonical", bias_floor="paired_epochs", rng=seed,
        n_pairings=50,
    )
    assert res["pairing_scheme"] == "derangement"
    assert res["n_pairings"] == 50
    assert res["band_coherence"]["beta"] > res["floor_q95"]["beta"], (
        f"beta observed {res['band_coherence']['beta']} vs floor_q95 {res['floor_q95']['beta']}"
    )
    assert res["floor_mean"]["beta"] <= res["floor_q95"]["beta"]


def test_a_single_trial_is_refused_with_bias_floor():
    X = np.random.default_rng(0).normal(size=(1, 1000))
    with pytest.raises(ValueError, match="at least 2 trials"):
        jnwb.cross_area_coherence(X, X.copy(), fs=FS, freq_bands="canonical",
                                  bias_floor="paired_epochs")


def test_one_dimensional_input_is_refused_with_bias_floor():
    x, y = _pinned_pair()
    with pytest.raises(ValueError, match="trial-shaped"):
        jnwb.cross_area_coherence(x, y, fs=FS, freq_bands="canonical",
                                  bias_floor="paired_epochs")


def test_two_rng_none_calls_give_different_floors():
    X, Y = _independent_trials(0)
    first = jnwb.cross_area_coherence(X, Y, fs=FS, freq_bands="canonical",
                                      bias_floor="paired_epochs", rng=None, n_pairings=50)
    second = jnwb.cross_area_coherence(X, Y, fs=FS, freq_bands="canonical",
                                       bias_floor="paired_epochs", rng=None, n_pairings=50)
    assert first["surrogate_seed_entropy"] != second["surrogate_seed_entropy"]
    assert first["floor_mean"] != second["floor_mean"]


def test_the_reported_entropy_reproduces_the_floor():
    X, Y = _independent_trials(0)
    first = jnwb.cross_area_coherence(X, Y, fs=FS, freq_bands="canonical",
                                      bias_floor="paired_epochs", rng=None, n_pairings=50)
    again = jnwb.cross_area_coherence(
        X, Y, fs=FS, freq_bands="canonical", bias_floor="paired_epochs",
        rng=first["surrogate_seed_entropy"], n_pairings=50,
    )
    for band in CANONICAL_BANDS:
        assert_allclose(again["floor_mean"][band], first["floor_mean"][band], rtol=1e-12, atol=0)
        assert_allclose(again["floor_q95"][band], first["floor_q95"][band], rtol=1e-12, atol=0)


def test_derangement_sampler_is_uniform_on_four_items():
    from jnwb.spectral._coupling import _random_derangement

    rng = np.random.default_rng(0)
    draws = [tuple(int(v) for v in _random_derangement(4, rng)) for _ in range(9000)]
    assert all(all(perm[i] != i for i in range(4)) for perm in draws), "a draw fixes a point"
    counts = Counter(draws)
    assert len(counts) == 9, f"expected all 9 derangements of 4 items, saw {sorted(counts)}"
    keys = sorted(counts)
    _, p_value = stats.chisquare([counts[k] for k in keys], np.full(9, 1000.0))
    assert p_value > 0.01, f"chi-square p = {p_value} over {dict(counts)}"
