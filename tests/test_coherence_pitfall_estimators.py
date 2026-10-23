"""``partial_coherence`` and ``coherence_bias_floor``, and the pinned default of ``cross_area_coherence``.

Partial coherence conditions the coherence between two signals on a further signal
(Dahlhaus, 2000). The bias floor is the coherence that randomly paired epochs produce, the bias
that a finite epoch count leaves (Maris, Schoffelen and Fries, 2007). The default outputs of
``cross_area_coherence`` are pinned to the values it returned before these estimators existed.
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
    # Added by fact S10: an additive key naming the circular shift of 1-D input. The values
    # above are unchanged; the set moved because the result gained a key.
    "surrogate_scheme",
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
    0.0010. Both calls draw their shifts from the same seed, so they share one null."""
    coherence_rejections = 0
    partial_rejections = 0
    for seed in range(12):
        x, y, z = _driver_triplet(seed, n=2000)
        coherence = jnwb.cross_area_coherence(
            x, y, fs=FS, freq_bands="canonical", n_surrogates=49, rng=seed,
        )
        partial = jnwb.partial_coherence(
            x, y, z, fs=FS, freq_bands="canonical", n_surrogates=49, rng=seed,
        )
        coherence_rejections += coherence["band_significance"]["beta"] < 0.05
        partial_rejections += partial["band_significance"]["beta"] < 0.05
    assert coherence_rejections >= 11, f"coherence significant at {coherence_rejections} of 12"
    assert partial_rejections <= 3, f"partial significant at {partial_rejections} of 12"


def test_independent_conditioner_keeps_partial_within_0p06_of_coherence_over_30_seeds():
    worst = 0.0
    for seed in range(30):
        rng = np.random.default_rng(100 + seed)
        x, y, z = rng.normal(size=(3, 4000))
        # The observed values do not depend on the surrogate count, so one surrogate suffices.
        res = jnwb.partial_coherence(
            x, y, z, fs=FS, freq_bands="canonical", rng=seed, n_surrogates=1,
        )
        for band in CANONICAL_BANDS:
            gap = abs(res["band_coherence"][band] - res["unconditioned_band_coherence"][band])
            worst = max(worst, gap)
    assert worst <= 0.06, f"largest |partial - coherence| over 30 seeds is {worst}"


def test_conditioning_on_the_common_driver_removes_the_beta_coupling():
    """Planted values. x and y share only the 15-25 Hz driver z at zero lag, so the
    unconditioned beta coherence is above 0.7 while the partial given z sits below 0.15,
    at seeds 0 and 1, and the two seeds differ."""
    seen = set()
    for seed in (0, 1):
        x, y, z = _driver_triplet(seed)
        res = jnwb.partial_coherence(
            x, y, z, fs=FS, freq_bands="canonical", n_surrogates=1, rng=seed,
        )
        assert res["unconditioned_band_coherence"]["beta"] > 0.7, (
            f"seed {seed}: the fixture carries no shared beta rhythm"
        )
        assert res["band_coherence"]["beta"] < 0.15, (
            f"seed {seed}: conditioning left {res['band_coherence']['beta']:.4f}"
        )
        seen.add(round(res["band_coherence"]["beta"], 6))
    assert len(seen) == 2, "two seeds must change the estimate"


def test_partial_spectrum_is_a_per_frequency_companion_of_the_coherence_spectrum():
    x, y, z = _driver_triplet(1)
    res = jnwb.partial_coherence(x, y, z, fs=FS, freq_bands="canonical", n_surrogates=1)
    spectrum = res["coherence_spectrum"]
    assert spectrum.shape == res["frequencies"].shape
    assert np.all(np.isfinite(spectrum))
    assert np.all((spectrum >= 0.0) & (spectrum <= 1.0 + 1e-12))


def test_a_singular_cross_spectral_matrix_is_refused_with_its_frequency():
    rng = np.random.default_rng(5)
    x = rng.normal(size=2000)
    y = rng.normal(size=2000)
    with pytest.raises(ValueError, match="singular") as info:
        jnwb.partial_coherence(x, y, 2.0 * x, fs=FS, freq_bands="canonical")
    assert re.search(r"at [0-9.]+ Hz", str(info.value)), str(info.value)


def test_the_conditioning_signal_is_refused_when_it_is_not_one_dimensional():
    x, y, z = _driver_triplet(0, n=2000)
    with pytest.raises(ValueError, match="Z must be a 1-D"):
        jnwb.partial_coherence(x, y, z[None, :], fs=FS, freq_bands="canonical")


# --- the paired-epoch bias floor --------------------------------------------------------

#: The three site pairs of the floor fixtures, in the order `pair_means` reports them.
SITE_PAIRS = ((0, 1), (0, 2), (1, 2))


def _independent_sites(seed, n_sites=3, n_epochs=20, n_times=1000):
    return np.random.default_rng(seed).normal(size=(n_sites, n_epochs, n_times))


def _shared_rhythm_sites(seed, n_epochs=20, n_times=1000):
    """Sites 0 and 1 share a 24 Hz rhythm within each epoch, at a random phase per epoch; site 2 is
    independent noise. Every site carries its own noise on top."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_times) / FS
    phase = rng.uniform(0.0, 2.0 * np.pi, size=(n_epochs, 1))
    shared = np.sin(2.0 * np.pi * 24.0 * t[None, :] + phase)
    sites = rng.normal(size=(3, n_epochs, n_times))
    sites[0] += shared
    sites[1] += shared
    return sites


def _aligned_band_coherence(a, b):
    """Observed coherence of aligned epochs: epoch i of ``a`` with epoch i of ``b``, pooled over every
    segment of every epoch, averaged over each canonical band. It is built from the estimator the floor
    uses, so the comparison is between two pairings of one estimator."""
    from jnwb.spectral._coupling import _csd_spectra_cpu, _pooled_coherence

    n_times = a.shape[-1]
    nperseg = min(max(n_times // 8, 8), 4096)
    freqs, pxx, pyy, sxy = _csd_spectra_cpu(a, b, FS, nperseg, nperseg // 2)
    coherence = _pooled_coherence(pxx, pyy, sxy)
    return {
        band: float(np.mean(coherence[(freqs >= lo) & (freqs <= hi)]))
        for band, (lo, hi) in CANONICAL_BANDS.items()
    }


#: Per-band tolerance of the bias-matching test, 0.0023. The standard error of the gap between two
#: means is sqrt(se_aligned^2 + se_floor^2), with se_aligned the standard error of the mean aligned
#: coherence over seeds 0 to 9 and se_floor that of the mean floor. At theta and alpha, the largest
#: bands, that is sqrt(0.00076^2 + 0.00013^2) = 0.00077; the tolerance is 3 of those, 0.00231,
#: rounded down to 0.0023. The aligned term dominates. The floor's own Monte-Carlo standard error
#: (0.00008 at n_draws=200) is not the binding quantity. Each seed's aligned value is the mean over
#: the three pairs. Theta and alpha share the 8 Hz bin at this segment length, so they coincide.
#: Measured with the probe in scratchpad file _temp_e4measure_1406r.py.
BIAS_TOLERANCE = 0.0023


def test_independent_epochs_match_the_floor_in_mean_at_seeds_0_to_9():
    """Bias matching. Independent epochs carry no coupling, so their aligned coherence estimates the
    bias that the floor estimates. Over seeds 0 to 9 and the three site pairs, the mean aligned
    coherence matches the mean floor in every canonical band to within BIAS_TOLERANCE.

    Measured gaps (mean floor minus mean aligned), theta to high_gamma: +0.00017, +0.00017,
    -0.00123, -0.00024, +0.00023. Each sits inside the tolerance.
    """
    aligned = {band: [] for band in CANONICAL_BANDS}
    floor = {band: [] for band in CANONICAL_BANDS}
    for seed in range(10):
        sites = _independent_sites(seed)
        result = jnwb.coherence_bias_floor(sites, fs=FS, freq_bands="canonical", rng=seed)
        for band in CANONICAL_BANDS:
            floor[band].append(result["floor_per_band"][band])
        for a, b in SITE_PAIRS:
            observed = _aligned_band_coherence(sites[a], sites[b])
            for band in CANONICAL_BANDS:
                aligned[band].append(observed[band])
    for band in CANONICAL_BANDS:
        assert len(floor[band]) == 10 and len(aligned[band]) == 30, "the examined set is not whole"
        gap = float(np.mean(floor[band]) - np.mean(aligned[band]))
        assert abs(gap) <= BIAS_TOLERANCE, f"{band}: mean floor minus mean aligned is {gap:+.5f}"


def test_independent_sites_match_one_over_k_within_a_factor_of_two():
    """Planted values. Independent epochs carry no coupling, so each pair's mean draw
    estimates the 1/K null and the maximum over the three pairs stays within [0.5/K, 2/K]
    in every canonical band at seeds 0 to 9 (K = 280 Welch segments for this fixture)."""
    for seed in range(10):
        result = jnwb.coherence_bias_floor(
            _independent_sites(seed), fs=FS, freq_bands="canonical", rng=seed,
        )
        k = result["n_segments_used"]
        assert k == 280, f"seed {seed}: the fixture's segment count moved to {k}"
        for band in CANONICAL_BANDS:
            floor = result["floor_per_band"][band]
            assert 0.5 / k <= floor <= 2.0 / k, (
                f"seed {seed} {band}: floor {floor:.5f} outside [0.5/K, 2/K]"
            )


def test_the_floor_is_the_maximum_over_pairs_of_their_mean_draws_exactly():
    """The floor is the maximum over site pairs of each pair's mean over the draws. It is therefore at
    least every pair's mean and equal to the largest of them: an exact equality, not a tolerance."""
    result = jnwb.coherence_bias_floor(_independent_sites(0), fs=FS, freq_bands="canonical", rng=0)
    means = result["pair_means"]
    assert set(means) == {str(pair) for pair in SITE_PAIRS}
    for band in CANONICAL_BANDS:
        per_pair = [means[str(pair)][band] for pair in SITE_PAIRS]
        assert result["floor_per_band"][band] == max(per_pair), band
        assert all(value <= result["floor_per_band"][band] for value in per_pair), band


def test_halving_the_epochs_raises_the_floor_in_every_band_at_seeds_0_to_4():
    """The floor tracks the epoch count: fewer epochs leave a larger bias. At every band and every
    seed 0 to 4 the floor from 10 epochs exceeds the floor from 20. Means over seeds 0 to 9, theta to
    high_gamma: 10 epochs 0.01162, 0.01162, 0.00877, 0.00886, 0.00799; 20 epochs 0.00502, 0.00502,
    0.00396, 0.00391, 0.00401."""
    for seed in range(5):
        full = jnwb.coherence_bias_floor(
            _independent_sites(seed), fs=FS, freq_bands="canonical", rng=seed,
        )
        half = jnwb.coherence_bias_floor(
            _independent_sites(seed, n_epochs=10), fs=FS, freq_bands="canonical", rng=seed,
        )
        assert set(half["floor_per_band"]) == set(CANONICAL_BANDS)
        for band in CANONICAL_BANDS:
            assert half["floor_per_band"][band] > full["floor_per_band"][band], (seed, band)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_a_rhythm_shared_within_epochs_lifts_the_aligned_coherence_above_the_floor(seed):
    sites = _shared_rhythm_sites(seed)
    floor = jnwb.coherence_bias_floor(sites, fs=FS, freq_bands="canonical", rng=seed)
    shared = _aligned_band_coherence(sites[0], sites[1])
    independent = _aligned_band_coherence(sites[0], sites[2])
    assert shared["beta"] > independent["beta"], "fixture must carry the shared rhythm"
    assert shared["beta"] > floor["floor_per_band"]["beta"], (
        f"beta aligned {shared['beta']} vs floor {floor['floor_per_band']['beta']}"
    )


def test_the_floor_names_its_scheme_and_its_pairs():
    res = jnwb.coherence_bias_floor(_independent_sites(0), fs=FS, freq_bands="canonical", rng=0)
    assert res["exchangeability_scheme"] == "random_epoch_pairing_max_over_site_pairs"
    assert res["max_over_pairs"] is True
    assert set(res["pair_means"]) == {"(0, 1)", "(0, 2)", "(1, 2)"}
    assert set(res["floor_per_band"]) == set(CANONICAL_BANDS)


def test_a_single_epoch_is_refused():
    with pytest.raises(ValueError, match="2 epochs"):
        jnwb.coherence_bias_floor(_independent_sites(0, n_epochs=1), fs=FS, freq_bands="canonical")


def test_one_site_is_refused():
    with pytest.raises(ValueError, match="2 sites"):
        jnwb.coherence_bias_floor(_independent_sites(0, n_sites=1), fs=FS, freq_bands="canonical")


def test_two_dimensional_input_is_refused():
    with pytest.raises(ValueError, match="n_sites, n_epochs, n_times"):
        jnwb.coherence_bias_floor(
            np.random.default_rng(0).normal(size=(2, 1000)), fs=FS, freq_bands="canonical",
        )


def test_a_pairing_other_than_random_pairs_is_refused():
    with pytest.raises(ValueError, match="random_pairs"):
        jnwb.coherence_bias_floor(
            _independent_sites(0), fs=FS, freq_bands="canonical", pairing="circular",
        )


def test_two_rng_none_calls_give_different_floors():
    sites = _independent_sites(0)
    first = jnwb.coherence_bias_floor(sites, fs=FS, freq_bands="canonical", rng=None, n_draws=50)
    second = jnwb.coherence_bias_floor(sites, fs=FS, freq_bands="canonical", rng=None, n_draws=50)
    assert first["surrogate_seed_entropy"] != second["surrogate_seed_entropy"]
    assert first["floor_per_band"] != second["floor_per_band"]


def test_the_reported_entropy_reproduces_the_floor():
    sites = _independent_sites(0)
    first = jnwb.coherence_bias_floor(sites, fs=FS, freq_bands="canonical", rng=None, n_draws=50)
    again = jnwb.coherence_bias_floor(
        sites, fs=FS, freq_bands="canonical", rng=first["surrogate_seed_entropy"], n_draws=50,
    )
    for band in CANONICAL_BANDS:
        assert_allclose(
            again["floor_per_band"][band], first["floor_per_band"][band], rtol=1e-12, atol=0,
        )


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


def test_cross_area_coherence_names_the_circular_shift_its_floor_drew():
    """Fact S10: continuous input draws circular shifts, and the result says so."""
    x, y = _pinned_pair()
    drawn = jnwb.cross_area_coherence(x, y, fs=FS, freq_bands="canonical", rng=7, n_surrogates=10)
    assert drawn["n_surrogates_used"] == 10, "the fixture must draw a null"
    assert drawn["surrogate_scheme"] == "circular_shift"


def test_partial_coherence_names_the_circular_shift_its_null_drew():
    """Fact S10: the partial-coherence null shifts Y circularly, and the result says so."""
    x, y, z = _driver_triplet(0, n=2000)
    drawn = jnwb.partial_coherence(x, y, z, fs=FS, freq_bands="canonical", n_surrogates=5, rng=7)
    assert drawn["n_surrogates_used"] == 5, "the fixture must draw a null"
    assert drawn["surrogate_scheme"] == "circular_shift"
