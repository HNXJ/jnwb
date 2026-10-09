"""Interpretational pitfalls of coupling and direction, as tests.

Each test builds the case it is named after, with a stated ground truth and an
explicit `rng`, so a test that stops exercising its case fails rather than passing
vacuously. Sources are rows of the Pitfalls table in
`artifacts/evidence/0.2.9/references/bastos_survey.md`, which tabulates what
Bastos and Schoffelen (2016) and Vezoli et al. (2021) say goes wrong and which
jnwb function answers it.

These tests record present behaviour. They do not repair it: no estimator in
jnwb detects a shared reference, volume conduction, an unrecorded common driver
or a noise asymmetry, so in each case the caller's step is stated in
`docs/common_mistakes.md` and what the test pins is the size of the effect the
estimator reports anyway.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import numpy as np
import pytest

import jnwb

FS = 500.0
N_TIMES = 4000
SEED = 7
ALPHA_BAND = {"alpha": (8.0, 14.0)}


def _shared_reference_pair(seed=SEED, n=N_TIMES, ar=0.5, n_contacts=2):
    """Two areas with independent local sources and one shared reference, no interaction.

    Ground truth: `src_a` drives nothing and `src_b` drives nothing; the only
    structure the two areas share is `ref`, which reaches every contact with the
    same sign and the same amplitude. Two contacts per area are returned so
    `bipolar_reference` has a neighbour to difference against: contact 0 carries
    its local source plus the shared reference, contact 1 carries the shared
    reference alone.

    Returns (area_a, area_b), each (n_contacts, n_times).
    """
    rng = np.random.default_rng(seed)
    ref = np.zeros(n)
    innovations = rng.normal(size=n)
    for i in range(1, n):
        ref[i] = ar * ref[i - 1] + innovations[i]
    area_a = np.vstack([rng.normal(size=n) + ref, ref])
    area_b = np.vstack([rng.normal(size=n) + ref, ref])
    assert area_a.shape == (n_contacts, n), (
        "fixture must build the case it is named after"
    )
    # No interaction means the two areas share only `ref`, so once it is differenced away
    # what is left must be uncorrelated. Without this the shape check would pass whatever
    # the two areas contained.
    residual = np.corrcoef(
        jnwb.bipolar_reference(area_a)[0], jnwb.bipolar_reference(area_b)[0]
    )[0, 1]
    assert abs(residual) < 0.05, (
        f"the areas must share no interaction once the reference is gone: r={residual}"
    )
    return area_a, area_b


def _alpha_coherence(x, y):
    result = jnwb.cross_area_coherence(
        x, y, fs=FS, freq_bands=ALPHA_BAND, n_surrogates=19, rng=0
    )
    return result["band_coherence"]["alpha"]


class TestCommonReference:
    """Common reference: a reference shared by two channels adds zero-lag coherence and
    Granger influence
    between them (Bastos and Schoffelen 2016 table 2; the common-reference row).
    Bastos et al. (2020) difference adjacent contacts before coherence and Granger
    for exactly this reason."""

    #: Unipolar pair with the shared reference present, alpha-band mean coherence.
    UNIPOLAR_COHERENCE = 0.7152

    #: Same pair after `bipolar_reference`. The reference is common-mode on adjacent
    #: contacts, so the difference cancels it and leaves the two independent sources,
    #: whose coherence is near zero. The drop is about 15x.
    BIPOLAR_COHERENCE = 0.0471

    #: `granger` F statistic (`diagnostics['f_x_to_y']`), unipolar vs bipolar on the same
    #: pair. A shared reference makes each channel a lagged predictor of the other, which
    #: is the inflation this test measures; the drop is about 109x. `x_to_y` is a different
    #: quantity and is not the F statistic.
    UNIPOLAR_F_XY = 51.99
    BIPOLAR_F_XY = 0.479

    def test_coherence_is_inflated_and_bipolar_reference_removes_the_inflation(self):
        """Coherence between two areas with no interaction is far above zero while the
        shared reference is present, and near zero after it is differenced away."""
        area_a, area_b = _shared_reference_pair()
        bipolar_a = jnwb.bipolar_reference(area_a)
        bipolar_b = jnwb.bipolar_reference(area_b)
        assert bipolar_a.shape == (area_a.shape[0] - 1, N_TIMES), (
            "one row fewer per area"
        )

        unipolar = _alpha_coherence(area_a[0], area_b[0])
        bipolar = _alpha_coherence(bipolar_a[0], bipolar_b[0])

        # The fixture must still produce the inflation, or the two bounds below are vacuous.
        assert unipolar == pytest.approx(self.UNIPOLAR_COHERENCE, rel=0.02), (
            f"the unipolar fixture no longer reproduces: {unipolar!r}"
        )
        assert bipolar == pytest.approx(self.BIPOLAR_COHERENCE, rel=0.05), (
            f"the bipolar fixture no longer reproduces: {bipolar!r}"
        )
        assert unipolar > 0.3, (
            "a shared reference must inflate coherence well above zero"
        )
        assert bipolar < 0.1, "bipolar differencing must cancel a common-mode reference"
        assert bipolar < unipolar / 5.0, "the inflation must drop, not merely shrink"

    def test_two_contacts_carrying_only_the_shared_reference_cohere_perfectly(self):
        """The degenerate case that fixes the ceiling: two copies of one reference are
        coherent at 1.0 by algebra, which is what makes any real pair's coherence
        suspect while a reference is shared."""
        area_a, area_b = _shared_reference_pair()
        assert _alpha_coherence(area_a[1], area_b[1]) == pytest.approx(1.0, abs=1e-6)

    def test_granger_is_inflated_and_bipolar_reference_removes_the_inflation(self):
        """`granger` on the same pair. Unipolar, each channel predicts the other at
        F ~ 52 and both directions sit at the surrogate floor (p = 0.05); after bipolar
        differencing F falls to ~ 0.48 and p rises to 0.70. The inflated pair is one
        reference reaching both channels, and no interaction is present."""
        area_a, area_b = _shared_reference_pair()
        bipolar_a = jnwb.bipolar_reference(area_a)
        bipolar_b = jnwb.bipolar_reference(area_b)

        unipolar = jnwb.granger(area_a[0], area_b[0], order=2, n_surrogates=19, rng=0)
        bipolar = jnwb.granger(
            bipolar_a[0], bipolar_b[0], order=2, n_surrogates=19, rng=0
        )

        f_unipolar = unipolar.diagnostics["f_x_to_y"]
        f_bipolar = bipolar.diagnostics["f_x_to_y"]
        assert f_unipolar == pytest.approx(self.UNIPOLAR_F_XY, rel=0.05), (
            f"the unipolar fixture no longer reproduces: {f_unipolar!r}"
        )
        assert f_bipolar == pytest.approx(self.BIPOLAR_F_XY, rel=0.05), (
            f"the bipolar fixture no longer reproduces: {f_bipolar!r}"
        )
        assert f_unipolar > 10.0, (
            "a shared reference must inflate the Granger statistic"
        )
        assert f_bipolar < 1.0, (
            "bipolar differencing must remove the common-mode predictor"
        )
        assert f_bipolar < f_unipolar / 50.0, (
            "the inflation must drop by orders of magnitude"
        )

    def test_the_two_estimators_agree_on_the_same_pair(self):
        """The claim is one reference inflating two different estimators. Both are read
        off one pair, so a change to the fixture moves them together and the two
        assertions cannot drift apart."""
        area_a, area_b = _shared_reference_pair()
        bipolar_a = jnwb.bipolar_reference(area_a)
        bipolar_b = jnwb.bipolar_reference(area_b)

        coherence_drop = _alpha_coherence(area_a[0], area_b[0]) / _alpha_coherence(
            bipolar_a[0], bipolar_b[0]
        )
        granger_drop = (
            jnwb.granger(
                area_a[0], area_b[0], order=2, n_surrogates=19, rng=0
            ).diagnostics["f_x_to_y"]
            / jnwb.granger(
                bipolar_a[0], bipolar_b[0], order=2, n_surrogates=19, rng=0
            ).diagnostics["f_x_to_y"]
        )

        assert coherence_drop > 5.0
        assert granger_drop > 50.0
        assert granger_drop > coherence_drop, (
            "the F statistic is the more inflated of the two on this fixture"
        )

    def test_laplacian_referencing_removes_the_inflation_too(self):
        """The guard column names two re-referencing paths and both are exercised here.
        `laplacian_reference` subtracts a neighbour mean rather than the nearer contact,
        so it is a different operation reaching the same cancellation."""
        area_a, area_b = _shared_reference_pair()
        laplacian_a = jnwb.laplacian_reference(area_a)
        laplacian_b = jnwb.laplacian_reference(area_b)
        assert laplacian_a.shape == area_a.shape, "laplacian keeps the contact count"

        unipolar = _alpha_coherence(area_a[0], area_b[0])
        re_referenced = _alpha_coherence(laplacian_a[0], laplacian_b[0])
        assert unipolar > 0.3, "the shared reference must inflate coherence first"
        assert re_referenced < unipolar / 5.0, (
            f"laplacian referencing must cancel it: {re_referenced} against {unipolar}"
        )


def _volume_conduction_pair(seed=8, n=N_TIMES, w=0.2):
    """Two channels carrying one instantaneous mixture: field spread with no interaction.

    Ground truth: `shared` reaches x and y at zero lag and with the same sign, so the two
    are coherent and neither leads. The two channels differ only in the noise each adds,
    drawn from its own generator, so they are not identical.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FS
    shared = sum(
        np.sin(2.0 * np.pi * f * t + 2.0 * np.pi * rng.random()) for f in (10.0, 12.5)
    ) / np.sqrt(2.0)
    x = shared + w * np.random.default_rng(seed + 101).normal(size=n)
    y = shared + w * np.random.default_rng(seed + 202).normal(size=n)
    assert not np.allclose(x, y), "the fixture must not make the two channels identical"
    return x, y


class TestVolumeConduction:
    """Volume conduction: field spread couples sites with no interaction at zero lag.
    `imaginary_coherency` and `wpli` discard the zero-lag component, so they stay near zero
    while coherence is high (Bastos and Schoffelen 2016 table 2, volume-conduction row).
    Neither confers immunity: a lagged interaction is also present in any real recording,
    which is why a positive control on a lagged pair is pinned beside the bounds."""

    #: Alpha-band mean coherence of the fixture, and the imaginary part it decomposes into.
    COHERENCE = 0.8533
    ICOH_MEAN = 0.00179
    ICOH_ABS_MEAN = 0.00933
    WPLI = 0.0444

    def test_coherence_is_high_while_the_zero_lag_measures_stay_near_zero(self):
        x, y = _volume_conduction_pair()
        coherence = _alpha_coherence(x, y)
        icoh = jnwb.imaginary_coherency(x, y, fs=FS, freq_range=(8.0, 14.0))
        wpli = jnwb.wpli(x, y, fs=FS, freq_range=(8.0, 14.0))

        assert coherence == pytest.approx(self.COHERENCE, rel=0.02), (
            f"the fixture no longer reproduces: {coherence!r}"
        )
        assert coherence > 0.4, "zero-lag mixing must produce high coherence"
        assert icoh["icoh_mean"] == pytest.approx(self.ICOH_MEAN, rel=0.05)
        assert wpli["wpli"] == pytest.approx(self.WPLI, rel=0.05)

        # The two zero-lag measures are the ones the row says stay near zero.
        assert abs(icoh["icoh_mean"]) < 0.05, "imaginary coherency must reject zero lag"
        assert icoh["icoh_abs_mean"] < 0.05
        assert wpli["wpli"] < 0.15, "wPLI must reject zero-lag-only coupling"
        assert coherence > 10.0 * abs(icoh["icoh_mean"])
        assert coherence > 5.0 * wpli["wpli"]

    def test_the_signed_mean_is_smaller_than_the_absolute_mean(self):
        """The signed imaginary coherency averages positive and negative lags toward zero,
        so the absolute mean is the larger of the two and is the honest bound."""
        x, y = _volume_conduction_pair()
        icoh = jnwb.imaginary_coherency(x, y, fs=FS, freq_range=(8.0, 14.0))
        assert icoh["icoh_abs_mean"] == pytest.approx(self.ICOH_ABS_MEAN, rel=0.05)
        assert abs(icoh["icoh_mean"]) < icoh["icoh_abs_mean"], (
            "zero-lag mixing has no preferred sign, so |mean| < abs mean"
        )

    def test_coherence_alone_does_not_distinguish_the_two_cases(self):
        """The reason the pitfall is a caller step: coherence reads high here, where the
        only coupling is volume spread, and reads high for a genuine interaction too."""
        x, y = _volume_conduction_pair()
        driven = np.roll(x, 10) + 0.2 * np.random.default_rng(9).normal(size=N_TIMES)
        spread = _alpha_coherence(x, y)
        interacting = _alpha_coherence(x, driven)
        assert spread > 0.4
        assert interacting > 0.4, (
            "if only the spread case were high, coherence would detect the difference"
        )

    def test_the_zero_lag_measures_do_fire_on_a_lagged_interaction(self):
        """The control that makes the bounds above meaningful. `wpli` and
        `imaginary_coherency` are not simply near zero on everything: on a lagged pair they
        respond, so the near-zero results on the zero-lag fixture are the measures working
        rather than the estimator returning a constant."""
        x, _ = _volume_conduction_pair()
        lagged = np.roll(x, 10) + 0.2 * np.random.default_rng(9).normal(size=N_TIMES)
        range_ = (8.0, 14.0)
        icoh = jnwb.imaginary_coherency(x, lagged, fs=FS, freq_range=range_)
        wpli = jnwb.wpli(x, lagged, fs=FS, freq_range=range_)

        assert abs(icoh["icoh_mean"]) > 0.05, (
            f"a lagged interaction must register: |icoh| = {abs(icoh['icoh_mean'])}"
        )
        assert wpli["wpli"] > 0.15, (
            f"a lagged interaction must register: wpli = {wpli['wpli']}"
        )


def _common_input_pair(seed=SEED, n=N_TIMES, ar=0.5, d1=1, d2=3, noise_sd=1.0):
    """An unrecorded common driver reaches x after d1 samples and y after d2 > d1.

    Ground truth: x and y never reference each other, so no true direction exists between
    them. The driver is AR(1), so a lag model can read its structure, and the unequal
    delays are what give a bivariate fit something to credit to the earlier channel.
    Returns (driver, x, y), each (n_times,).
    """
    rng = np.random.default_rng(seed)
    driver = np.zeros(n)
    innovations = rng.normal(size=n)
    for i in range(1, n):
        driver[i] = ar * driver[i - 1] + innovations[i]
    x = np.zeros(n)
    y = np.zeros(n)
    x[d1:] = driver[: n - d1]
    y[d2:] = driver[: n - d2]
    x = x + noise_sd * rng.normal(size=n)
    y = y + noise_sd * rng.normal(size=n)
    return driver, x, y


class TestCommonInput:
    """Common input: an unrecorded source drives both signals and leaves a Granger
    direction between
    them (Bastos and Schoffelen 2016 table 2, common-input row). No estimator removes it;
    recording the driver and conditioning on it does."""

    #: `diagnostics['f_x_to_y']` bivariate vs conditional at order 3, which must be at
    #: least the larger delay d2 = 3. The ratio is about 1680.
    F_BIVARIATE = 548.44
    F_CONDITIONAL = 0.3263

    def test_a_bivariate_fit_credits_a_direction_and_conditioning_removes_it(self):
        driver, x, y = _common_input_pair()
        bivariate = jnwb.granger(x, y, order=3, n_surrogates=19, rng=0)
        conditional = jnwb.granger(x, y, order=3, Z=driver, n_surrogates=19, rng=0)

        f_bivariate = bivariate.diagnostics["f_x_to_y"]
        f_conditional = conditional.diagnostics["f_x_to_y"]
        assert f_bivariate == pytest.approx(self.F_BIVARIATE, rel=0.05), (
            f"the bivariate fixture no longer reproduces: {f_bivariate!r}"
        )
        assert f_bivariate > 100.0, (
            "an unrecorded driver must inflate the bivariate fit"
        )
        assert bivariate.p_x_to_y == pytest.approx(0.05), "and it reads significant"

        assert f_conditional < 5.0, (
            "conditioning on the driver must remove the inflation"
        )
        assert conditional.p_x_to_y > 0.2, "and the direction must read as unsupported"
        assert f_conditional < f_bivariate / 100.0

    def test_the_direction_is_not_credited_when_the_delays_are_equal(self):
        """Ground truth for the fixture. With d1 == d2 both channels see the driver at the
        same lag, so there is no asymmetry for a bivariate fit to credit and the F
        statistic stays low. Without this, the test above would pass on any two AR-driven
        signals."""
        _, x, y = _common_input_pair(d2=1)
        equal_delays = jnwb.granger(x, y, order=3, n_surrogates=19, rng=0)
        assert equal_delays.diagnostics["f_x_to_y"] < 100.0, (
            "equal delays must not produce the inflation"
        )

    def test_order_below_the_larger_delay_does_not_remove_the_inflation(self):
        """The repair is not cosmetic. At order 2, which is below d2 = 3, the model cannot
        span the delay difference and conditioning leaves the inflation in place, so the
        removal depends on the order reaching the driver."""
        driver, x, y = _common_input_pair()
        bivariate = jnwb.granger(x, y, order=2, n_surrogates=19, rng=0)
        conditional = jnwb.granger(x, y, order=2, Z=driver, n_surrogates=19, rng=0)
        assert (
            conditional.diagnostics["f_x_to_y"]
            > 0.5 * bivariate.diagnostics["f_x_to_y"]
        ), "an order below the delay difference cannot condition the driver away"


def _independent_pair(seed=0, n=N_TIMES):
    """Two uncoupled noise sources: the null every bias-free measure is read against."""
    rng = np.random.default_rng(seed)
    return rng.normal(size=n), rng.normal(size=n)


def _ppc_over_segments(x, y, nperseg, freq_range=(8.0, 14.0)):
    """PPC over the phase differences of non-overlapping Welch segments.

    `pairwise_phase_consistency` takes one phase angle per observation, so the caller
    reduces each segment's complex mean phase difference to that angle. The TFR is
    (n_freqs, n_times), so time is sliced on the last axis.
    """
    freqs = np.fft.rfftfreq(nperseg, d=1.0 / FS)
    in_band = freqs[(freqs >= freq_range[0]) & (freqs <= freq_range[1])]
    assert in_band.size, f"no frequency bin in {freq_range} at nperseg={nperseg}"
    phase_x = np.angle(jnwb.complex_tfr(x, FS, in_band).z)
    phase_y = np.angle(jnwb.complex_tfr(y, FS, in_band).z)
    step = nperseg // 2
    segment_phases = []
    for start in range(0, N_TIMES - nperseg + 1, step):
        window = slice(start, start + nperseg)
        segment_phases.append(
            np.angle(np.mean(np.exp(1j * (phase_x[:, window] - phase_y[:, window]))))
        )
    return jnwb.pairwise_phase_consistency(np.array(segment_phases))


class TestSampleSizeBias:
    """Sample-size bias: coherence sits near 1/K for K Welch segments under no coupling.
    The bias-free
    measures are `pairwise_phase_consistency` and `wpli`'s debiased value; both stay near
    zero at every segment count (Bastos and Schoffelen 2016 table 2, sample-size row)."""

    #: (nperseg, coherence, wpli, wpli_debiased_sq, ppc) at seed 0, K = 4, 8, 16, 32.
    ROWS = (
        (1600, 0.2949, 0.5531, -0.0441, -0.1288),
        (888, 0.0886, 0.3501, -0.1027, -0.0780),
        (470, 0.0600, 0.2325, -0.0495, -0.0289),
        (235, 0.0330, 0.1865, -0.0169, -0.0248),
    )

    #: K = 2 is deliberately absent. With two observations PPC is cos(dphi) by algebra, so
    #: it is one uniform deviate rather than an estimate, and at K = 4 the spread over 40
    #: seeds reaches 0.958. The pinned K values are the ones with a usable null.
    def test_coherence_tracks_one_over_k(self):
        for nperseg, coherence, _, _, _ in self.ROWS:
            measured, k = _alpha_coherence_at(*_independent_pair(), nperseg=nperseg)
            expected = 1.0 / k
            assert measured == pytest.approx(coherence, rel=0.02), (
                f"the K = {k} row no longer reproduces: {measured!r}"
            )
            assert measured == pytest.approx(expected, rel=0.35), (
                f"coherence {measured} should sit near 1/K = {expected} at K = {k}"
            )

    def test_both_bias_free_measures_stay_near_zero_at_every_segment_count(self):
        for nperseg, _, wpli, debiased, ppc in self.ROWS:
            x, y = _independent_pair()
            measured_ppc = _ppc_over_segments(x, y, nperseg)
            measured_wpli = jnwb.wpli(
                x, y, fs=FS, freq_range=(8.0, 14.0), nperseg=nperseg
            )

            assert measured_ppc == pytest.approx(ppc, rel=0.05)
            assert measured_wpli["wpli"] == pytest.approx(wpli, rel=0.05)
            assert measured_wpli["wpli_debiased_sq"] == pytest.approx(
                debiased, rel=0.05
            )

            assert abs(measured_ppc) < 0.2, (
                f"PPC must stay near zero at nperseg={nperseg}"
            )
            assert abs(measured_wpli["wpli_debiased_sq"]) < 0.25, (
                f"debiased wPLI must stay near zero at nperseg={nperseg}"
            )

    def test_the_estimator_reports_the_segment_count_the_bias_scales_with(self):
        """The row's guard names `n_segments_used`, and the 1/K claim only holds against
        the segment count the estimator itself used, so that key is read directly here."""
        x, y = _independent_pair()
        result = jnwb.cross_area_coherence(
            x, y, fs=FS, freq_bands=ALPHA_BAND, nperseg=888, n_surrogates=19, rng=0
        )
        assert result["n_segments_used"] == 8, (
            f"the estimator must report the segment count, got {result['n_segments_used']}"
        )
        assert result["band_coherence"]["alpha"] == pytest.approx(1.0 / 8, rel=0.35), (
            "and the coherence must sit near its reciprocal"
        )

    def test_the_biased_measure_is_the_one_that_grows_with_fewer_segments(self):
        """The contrast that makes the row a finding: plain wPLI and coherence both rise as
        segments are removed, while the debiased value and PPC do not."""
        x, y = _independent_pair()
        few = jnwb.wpli(x, y, fs=FS, freq_range=(8.0, 14.0), nperseg=1600)
        many = jnwb.wpli(x, y, fs=FS, freq_range=(8.0, 14.0), nperseg=235)
        assert few["wpli"] > 2.0 * many["wpli"], "plain wPLI is the biased one"
        assert abs(few["wpli_debiased_sq"]) < abs(many["wpli"]), (
            "the debiased value must not carry the bias"
        )


def _ar_pair(n, seed, phi1=0.5, phi2=0.3):
    """An AR(2) source, so a lag model has real structure to fit.

    `phi2 = 0.0` gives an AR(1), used where a simpler process is wanted.
    """
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    innovations = rng.normal(size=n)
    for i in range(2, n):
        out[i] = phi1 * out[i - 1] + phi2 * out[i - 2] + innovations[i]
    return out


def _snr_pair(mult, seed=SEED, lag=8, base=1.0, n=N_TIMES):
    """x drives y one way at a lag, and only y carries extra noise.

    Ground truth: the coupling runs x to y and never back. `mult` sets the extra noise
    added to y alone, so the two channels' signal-to-noise ratios differ while the
    direction under test does not.
    """
    rng = np.random.default_rng(seed)
    x = _ar_pair(n, seed) + base * rng.normal(size=n)
    y = np.zeros(n)
    y[lag:] = 0.8 * x[: n - lag]
    y = y + base * rng.normal(size=n) + mult * base * rng.normal(size=n)
    return x, y


def _asymmetric_noise_pair(mult, seed=SEED, n=N_TIMES):
    """Two channels with NO coupling between them, and only one carrying extra noise.

    Ground truth, the case the row names: x and y are independent AR(2) processes, so no
    direction exists between them at any noise level. `mult` sets the extra noise added to
    y alone.
    """
    x = _ar_pair(n, seed)
    y = _ar_pair(n, seed + 1) + mult * np.random.default_rng(seed).normal(size=n)
    return x, y


class TestSignalToNoiseAsymmetry:
    """Signal-to-noise asymmetry: the channel with the better signal-to-noise ratio appears to
    lead, so a Granger direction can be spurious (Bastos and Schoffelen 2016 table 2,
    SNR-asymmetry row).

    Recorded here, on two channels that do not couple at all with extra noise on one of them:
    `granger` reports a significant direction (p = 0.005 at order 8) while none exists.
    What the measurements establish is narrower than "a false positive", and the class is
    written to that width.

    The surrogate null is not simply mis-calibrated. Against a null that phase-randomises y
    and so destroys cross-dependence while preserving both marginals, the observed F of
    12.70 sits against a null mean of 1.93 and a 95th percentile of 3.69, and p is 0.005
    under both nulls at 10 of 10 seeds. What that does NOT show is why the asymmetry is
    there: the null cannot separate unequal observation noise from VAR order, latent
    structure, or another modelling assumption, and this class attributes it to none of
    them.

    It needs the asymmetry: with matched noise the same pair reports nothing at any order
    from 1 to 20, at 10 of 10 seeds.

    The direction is set by the order, not by the signal-to-noise ratio. At order 1 the
    credit runs y to x at 7 of 10 seeds; at every order from 2 to 20 it runs x to y at 9 or
    10 of 10. Reversing the asymmetry (noise on x instead) removes the effect at order 8
    entirely. So the row's "the better channel appears to lead" is the wrong description of
    what happens here: neither channel leads, and which one is credited is a property of the
    fitted order.

    The gap item 11-04 closes is the second estimator in its bullet: a time-reversed
    Granger control, which separates a strong from a weak asymmetry. `jnwb` has no
    time-reversal or power-stratification control today, and no proposal for either, so
    comparing power between the channels is the caller's only step.
    """

    #: `diagnostics['f_x_to_y']` on the uncoupled pair, order 8, at 6x noise on y, and
    #: `diagnostics['f_x_to_y']` on the coupled pair at 0.5x and 4x noise, order 12, lag 8.
    F_XY_UNCOUPLED_NOISY = 12.70
    F_XY_CLEAN = 714.54
    F_XY_NOISY = 60.57

    def test_an_uncoupled_pair_gains_a_reported_direction_from_the_noise_asymmetry(
        self,
    ):
        """The case the row names. The two channels are independent, so there is no
        direction to report, and one of them is noisier than the other."""
        clean = jnwb.granger(
            *_asymmetric_noise_pair(0.0), order=8, n_surrogates=99, rng=0
        )
        noisy = jnwb.granger(
            *_asymmetric_noise_pair(6.0), order=8, n_surrogates=99, rng=0
        )

        assert clean.p_x_to_y == pytest.approx(0.65), (
            "with matched noise the pair is correctly not significant"
        )
        f_noisy = noisy.diagnostics["f_x_to_y"]
        assert f_noisy == pytest.approx(self.F_XY_UNCOUPLED_NOISY, rel=0.05), (
            f"the asymmetric fixture no longer reproduces: {f_noisy!r}"
        )
        assert noisy.p_x_to_y == pytest.approx(0.01), (
            "the direction reads significant although no coupling exists"
        )
        assert noisy.net > 0.0, "and at this order the credit runs x to y"
        matched_noise = jnwb.granger(
            *_asymmetric_noise_pair(1.0), order=8, n_surrogates=99, rng=0
        )
        assert f_noisy < matched_noise.diagnostics["f_x_to_y"], (
            "the inflation must come from the asymmetry, not from the noise alone"
        )

    def test_the_credited_direction_is_set_by_the_order_not_by_the_noise_ratio(self):
        """The finding that revises the row's own description. At order 1 the credit runs
        y to x; at every order from 2 up it runs x to y. Which channel is credited is a
        property of the fitted order, so "the better-signal channel appears to lead" is
        not what happens on this fixture -- neither channel leads."""
        by_order = {}
        for order in (1, 2, 8):
            credits = set()
            for seed in range(10):
                result = jnwb.granger(
                    *_asymmetric_noise_pair(6.0, seed=seed),
                    order=order,
                    n_surrogates=99,
                    rng=0,
                )
                if result.p_x_to_y < 0.05 and result.p_y_to_x >= 0.05:
                    credits.add("x_to_y")
                elif result.p_y_to_x < 0.05 and result.p_x_to_y >= 0.05:
                    credits.add("y_to_x")
            by_order[order] = credits
        assert by_order[1] == {"y_to_x"}, (
            f"order 1 must credit the reverse direction, got {by_order[1]}"
        )
        assert by_order[2] == {"x_to_y"}, (
            f"order 2 must credit x to y, got {by_order[2]}"
        )
        assert by_order[8] == {"x_to_y"}, (
            f"order 8 must credit x to y, got {by_order[8]}"
        )

    def test_matched_noise_reports_nothing_at_any_order(self):
        """The control that makes the asymmetry necessary rather than incidental: the same
        pair with matched noise is silent at every order tested."""
        for order in (1, 2, 4, 8, 20):
            result = jnwb.granger(
                *_asymmetric_noise_pair(0.0), order=order, n_surrogates=99, rng=0
            )
            assert result.p_x_to_y > 0.05, f"order {order} must not credit x to y"
            assert result.p_y_to_x > 0.05, f"order {order} must not credit y to x"

    def test_the_significance_survives_a_null_that_preserves_both_marginals(self):
        """Rules out one alternative and no more. The shipped surrogate null could have been
        mis-calibrated; against a null that phase-randomises y, destroying cross-dependence
        while leaving each series' power spectrum intact, the observed F still sits far
        outside it. That the asymmetry comes from unequal observation noise rather than
        from VAR order or latent structure is not settled here and is not claimed."""
        x, y = _asymmetric_noise_pair(6.0)
        observed = jnwb.granger(x, y, order=8, n_surrogates=0, rng=0).diagnostics[
            "f_x_to_y"
        ]

        rng = np.random.default_rng(0)
        n_times = len(y)
        spectrum = np.abs(np.fft.rfft(y))
        null = []
        for _ in range(99):
            phase = rng.uniform(0.0, 2.0 * np.pi, len(spectrum))
            phase[0] = 0.0
            randomised = np.fft.irfft(spectrum * np.exp(1j * phase), n=n_times)
            null.append(
                jnwb.granger(x, randomised, order=8, n_surrogates=0, rng=0).diagnostics[
                    "f_x_to_y"
                ]
            )
        null = np.array(null)

        assert observed == pytest.approx(self.F_XY_UNCOUPLED_NOISY, rel=0.05)
        assert observed > 3.0 * null.mean(), (
            f"observed F {observed} against null mean {null.mean()}"
        )
        assert observed > np.percentile(null, 95), (
            "the observation must sit outside 95% of a dependence-free null"
        )
        assert (np.sum(null >= observed) + 1) / (len(null) + 1) <= 0.02, (
            "so p stays small under a null that shares none of the surrogate's construction"
        )

    def test_a_real_coupling_survives_the_same_asymmetry(self):
        """The complement, on a pair that does couple one way at a lag. Here the reported
        direction is the true one at every noise level and what the noise destroys is the
        effect size: `f_x_to_y` falls from about 715 to about 61 between 0.5x and 4x. The
        F statistic is invariant to per-channel rescaling, so added noise weakens both
        directions rather than swapping them.
        """
        x, y = _snr_pair(4.0)
        result = jnwb.granger(x, y, order=12, n_surrogates=19, rng=0)

        f_xy = result.diagnostics["f_x_to_y"]
        assert f_xy == pytest.approx(self.F_XY_NOISY, rel=0.05), (
            f"the noisy fixture no longer reproduces: {f_xy!r}"
        )
        # The direction `granger` reports today, recorded rather than asserted as correct.
        assert result.p_x_to_y == pytest.approx(0.05), (
            "x to y is credited, at the floor"
        )
        assert result.p_y_to_x > 0.5, "y to x is not credited"
        assert f_xy > 50.0
        assert result.diagnostics["f_y_to_x"] < 2.0

    def test_the_effect_size_collapses_while_the_direction_holds(self):
        """The asymmetry is real and measurable even though the label does not change."""
        clean = jnwb.granger(*_snr_pair(0.5), order=12, n_surrogates=19, rng=0)
        noisy = jnwb.granger(*_snr_pair(4.0), order=12, n_surrogates=19, rng=0)

        f_clean = clean.diagnostics["f_x_to_y"]
        f_noisy = noisy.diagnostics["f_x_to_y"]
        assert f_clean == pytest.approx(self.F_XY_CLEAN, rel=0.05), (
            f"the clean fixture no longer reproduces: {f_clean!r}"
        )
        assert f_noisy < f_clean / 5.0, (
            "the effect size must collapse with the asymmetry"
        )
        # Both directions are still labelled the same way.
        assert clean.p_x_to_y == pytest.approx(noisy.p_x_to_y)

    def test_the_power_difference_the_caller_must_read_is_there(self):
        """The row's remedy is comparing power between channels. That difference is what
        the estimator itself ignores: y's band power rises with its noise while x's does
        not move, and the reported direction is unchanged across the same sweep."""
        powers_y = [
            jnwb.band_power(
                _snr_pair(mult)[1], FS, freq_range=(8.0, 14.0), normalize=False
            )
            for mult in (0.5, 4.0)
        ]
        powers_x = [
            jnwb.band_power(
                _snr_pair(mult)[0], FS, freq_range=(8.0, 14.0), normalize=False
            )
            for mult in (0.5, 4.0)
        ]
        # x is bit-identical across `mult` by construction, so its power cannot move; only
        # the comparison below is informative, and it is y's that carries the asymmetry.
        assert powers_x[0] == pytest.approx(powers_x[1], rel=1e-9), "x's power is fixed"
        assert powers_y[1] > powers_y[0], "y's power rises with its noise"
        assert (
            jnwb.granger(*_snr_pair(0.5), order=12, n_surrogates=19, rng=0).p_y_to_x
            > 0.5
            and jnwb.granger(*_snr_pair(4.0), order=12, n_surrogates=19, rng=0).p_y_to_x
            > 0.5
        ), "and the direction is credited the same way at both"


def _routed_influence_pair(seed=3, n=N_TIMES, lag=5, gain=0.7):
    """x drives z, z drives y, and x never drives y directly.

    Ground truth: the only path from x to y runs through z, so a bivariate fit that
    credits x is crediting an influence that a third signal carries. Returns (x, y, z),
    each (n_times,).
    """
    rng = np.random.default_rng(seed)
    x = _ar_pair(n, seed, phi1=0.5, phi2=0.0)
    z = np.zeros(n)
    y = np.zeros(n)
    e_z = rng.normal(size=n)
    e_y = rng.normal(size=n)
    for i in range(lag, n):
        z[i] = gain * x[i - lag] + e_z[i]
        y[i] = gain * z[i - lag] + e_y[i]
    return x, y, z


def _direct_influence_pair(seed=3, n=N_TIMES, lag=5, gain=0.7):
    """x drives y directly, as the control for the class above."""
    rng = np.random.default_rng(seed)
    x = _ar_pair(n, seed, phi1=0.5, phi2=0.0)
    y = np.zeros(n)
    e_y = rng.normal(size=n)
    for i in range(lag, n):
        y[i] = gain * x[i - lag] + e_y[i]
    unrelated = np.random.default_rng(seed + 9).normal(size=n)
    return x, y, unrelated


class TestBivariateAgainstConditionalGranger:
    """Bivariate against conditional Granger: a bivariate fit credits X with influence
    routed through a third recorded signal
    (Bastos and Schoffelen 2016 table 2, bivariate-vs-conditional row). `granger` takes
    `Z`; `directed_network(conditional=True)` conditions on all other nodes;
    `granger_spectral` has no `Z`.

    This is a different mechanism from `TestCommonInput`: there the third signal is
    unrecorded and drives both, here it is recorded, lies on the path, and is the thing the
    caller can condition on.
    """

    #: Bivariate vs conditional `f_x_to_y` at order 8, and the direct-influence control.
    ROUTED_BIVARIATE_F = 216.69
    ROUTED_CONDITIONAL_F = 0.10071
    DIRECT_BIVARIATE_F = 132.20
    DIRECT_CONDITIONAL_F = 131.88

    def test_a_bivariate_fit_credits_an_influence_routed_through_a_third_signal(self):
        """The row's case. x does not drive y; z does. The bivariate fit sees only x and y
        and reports a large, significant influence, so it has credited a path it cannot
        see."""
        x, y, z = _routed_influence_pair()
        bivariate = jnwb.granger(x, y, order=8, n_surrogates=99, rng=0)
        conditional = jnwb.granger(x, y, order=8, Z=z, n_surrogates=99, rng=0)

        f_bivariate = bivariate.diagnostics["f_x_to_y"]
        assert f_bivariate == pytest.approx(self.ROUTED_BIVARIATE_F, rel=0.05), (
            f"the routed fixture no longer reproduces: {f_bivariate!r}"
        )
        assert bivariate.p_x_to_y < 0.05, (
            "the bivariate fit calls the influence significant"
        )
        assert conditional.p_x_to_y > 0.2, (
            "while conditioning on the signal that carries the path does not"
        )

    def test_conditioning_removes_the_routed_influence_by_orders_of_magnitude(self):
        x, y, z = _routed_influence_pair()
        bivariate = jnwb.granger(x, y, order=8, n_surrogates=99, rng=0)
        conditional = jnwb.granger(x, y, order=8, Z=z, n_surrogates=99, rng=0)

        f_bivariate = bivariate.diagnostics["f_x_to_y"]
        f_conditional = conditional.diagnostics["f_x_to_y"]
        assert f_conditional == pytest.approx(self.ROUTED_CONDITIONAL_F, rel=0.05), (
            f"the conditional fixture no longer reproduces: {f_conditional!r}"
        )
        assert f_conditional < f_bivariate / 100.0, (
            "conditioning must remove the routed influence, not merely shrink it"
        )

    def test_a_direct_influence_survives_conditioning(self):
        """The control that makes the test mean what it says. Conditioning on a signal
        unrelated to the path must leave a genuine influence alone, so the removal above is
        the conditioning working rather than the estimator losing everything."""
        x, y, unrelated = _direct_influence_pair()
        bivariate = jnwb.granger(x, y, order=8, n_surrogates=99, rng=0)
        conditional = jnwb.granger(x, y, order=8, Z=unrelated, n_surrogates=99, rng=0)

        f_bivariate = bivariate.diagnostics["f_x_to_y"]
        f_conditional = conditional.diagnostics["f_x_to_y"]
        assert f_bivariate == pytest.approx(self.DIRECT_BIVARIATE_F, rel=0.05)
        assert f_conditional == pytest.approx(self.DIRECT_CONDITIONAL_F, rel=0.05)
        assert f_conditional > 0.5 * f_bivariate, (
            "a direct influence must not be removed by conditioning on an unrelated signal"
        )
        assert conditional.p_x_to_y < 0.05, "and it must stay significant"

    def test_granger_spectral_carries_no_conditioning_argument(self):
        """The row's other guard: `granger_spectral` has no `Z`, so a caller who wants a
        frequency-resolved direction on a routed pair has no conditional route in jnwb."""
        import inspect

        assert "Z" not in inspect.signature(jnwb.granger_spectral).parameters
        assert "Z" in inspect.signature(jnwb.granger).parameters

    def test_directed_network_conditions_on_every_other_node(self):
        """`directed_network(conditional=True)` is the network-level form of the same
        guard, and it is recorded as reporting the flag it ran with."""
        x, y, z = _routed_influence_pair()
        unconditional = jnwb.directed_network(
            [x, y, z],
            method="granger",
            labels=["x", "y", "z"],
            conditional=False,
            order=8,
            n_surrogates=49,
            rng=0,
            fdr=False,
        )
        conditional = jnwb.directed_network(
            [x, y, z],
            method="granger",
            labels=["x", "y", "z"],
            conditional=True,
            order=8,
            n_surrogates=49,
            rng=0,
            fdr=False,
        )
        assert unconditional["conditional"] is False
        assert conditional["conditional"] is True
        assert conditional["n_nodes"] == 3
        assert len(conditional["matrix"]) == 3, "and the matrix keeps every node"


def _alpha_coherence_at(x, y, nperseg, **kwargs):
    """Alpha coherence and the Welch segment count the estimator itself used.

    K is read from `n_segments_used` rather than recomputed, so the bound is checked
    against the segment count that produced the coherence. This is the cross-area
    estimator the sample-size-bias row names, and `kwargs` lets a caller pass its own
    extra arguments.
    """
    result = jnwb.cross_area_coherence(
        x, y, fs=FS, freq_bands=ALPHA_BAND, nperseg=nperseg, n_surrogates=19, rng=0
    )
    return result["band_coherence"]["alpha"], result["n_segments_used"]


def _lagged_pair(lag=10, seed=0, n=N_TIMES, gain=0.8, noise=0.3):
    """y is x delayed by `lag` samples, so the true direction is x to y."""
    x = _ar_pair(n, seed, phi1=0.6, phi2=0.0)
    y = np.zeros(n)
    y[lag:] = gain * x[: n - lag]
    y = y + noise * np.random.default_rng(seed + 1).normal(size=n)
    return x, y


def _unequal_delay_pair(seed=2, n=N_TIMES, d1=1, d2=4, noise=0.03, driver_phi=0.6):
    """A common driver reaching x after d1 samples and y after d2, with no true lead.

    Ground truth: x and y never reference each other, so no direction exists between them.
    The delay difference alone can produce one, which is the gap. `driver_phi` varies the
    driver's own dynamics so the tests can show the artefact is not a property of one AR(1).
    """
    driver = _ar_pair(n, seed, phi1=driver_phi, phi2=0.0)
    x = np.zeros(n)
    y = np.zeros(n)
    x[d1:] = driver[: n - d1]
    y[d2:] = driver[: n - d2]
    x = x + noise * np.random.default_rng(seed + 101).normal(size=n)
    y = y + noise * np.random.default_rng(seed + 202).normal(size=n)
    return x, y


class TestPhaseSlopeIsNotDirection:
    """Phase slope as direction: a phase slope gives a lag asymmetry in the statistics, not
    an anatomical direction
    (Bastos and Schoffelen 2016, phase-difference slope row; `AGENTS.md` 4.8 and 5).

    `phase_slope_index` does what its row claims for the half it can: it separates the lead
    from coupling, signs it with the argument order, and refuses when the two signals carry
    no lead at all. The gap it cannot close is named below and pinned by the last test.
    """

    BETA = {"beta": (14.0, 30.0)}

    #: `net` and the beta z for a pair where x leads y by 10 samples.
    NET_X_LEADS = 1.6828
    Z_X_LEADS = 41.872

    def test_a_known_lead_is_detected_and_signed_by_the_argument_order(self):
        x, y = _lagged_pair()
        forward = jnwb.phase_slope_index(
            x, y, fs=FS, bands=self.BETA, n_surrogates=19, rng=0
        )
        swapped = jnwb.phase_slope_index(
            y, x, fs=FS, bands=self.BETA, n_surrogates=19, rng=0
        )

        assert forward.net == pytest.approx(self.NET_X_LEADS, rel=0.02), (
            f"the lead fixture no longer reproduces: {forward.net!r}"
        )
        assert forward.per_band["beta"]["z"] == pytest.approx(self.Z_X_LEADS, rel=0.02)
        assert forward.net > 0.0, "x leads y, so the net asymmetry is positive"
        assert swapped.net == pytest.approx(-forward.net), (
            "swapping the arguments flips the sign and nothing else"
        )
        assert forward.p_net < 1e-10
        # The lead is reported apart from coupling, which is what the row asks of it.
        assert forward.diagnostics["p_covers_both_directions"] is True
        assert "p_coupling_surrogate" in forward.diagnostics

    def test_identical_signals_are_refused_rather_than_reported(self):
        """The estimator declines when there is no lead to report: `p_net` is None and the
        reason is named."""
        x, _ = _lagged_pair()
        result = jnwb.phase_slope_index(
            x, x, fs=FS, bands=self.BETA, n_surrogates=19, rng=0
        )
        assert result.p_net is None, "no lead means no p, not p = 1"
        assert result.diagnostics["warnings"], "and the refusal is named"
        assert any("round_off" in w for w in result.diagnostics["warnings"])

    def test_an_unequal_delay_common_driver_produces_a_significant_asymmetry(self):
        """The gap, named: PSI tests whether a lag asymmetry is distinguishable from zero,
        not whether it is causal. A common driver reaching the two signals at unequal lags
        yields a net asymmetry of about 0.54 with p near 2e-23 and an EMPTY warnings list,
        so no diagnostic PSI reports separates a true lead from any other origin of lag
        asymmetry. Recording the driver and passing it as `Z` to `granger` removes the
        artefact, as `TestCommonInput` shows; PSI takes no such argument, so the caller's
        step for this row is to confirm the lead against a recorded driver by another
        estimator.
        """
        x, y = _unequal_delay_pair()
        result = jnwb.phase_slope_index(
            x, y, fs=FS, bands=self.BETA, n_surrogates=19, rng=0
        )
        assert result.net == pytest.approx(0.5380, rel=0.02), (
            f"the common-driver fixture no longer reproduces: {result.net!r}"
        )
        assert result.p_net < 1e-20, (
            "a delay asymmetry is detected as highly significant"
        )
        assert result.diagnostics["warnings"] == [], (
            "and nothing in the result flags it as a common-input artefact"
        )

    def test_the_artefact_holds_across_driver_type_delay_and_noise(self):
        """Not one fixture. The lead appears for every driver with power spread across the
        band, at every delay pair tested, and it scales with the delay difference."""
        net_by_gap = {}
        for d1, d2 in ((1, 2), (1, 4), (1, 8)):
            x, y = _unequal_delay_pair(d1=d1, d2=d2)
            result = jnwb.phase_slope_index(
                x, y, fs=FS, bands=self.BETA, n_surrogates=19, rng=0
            )
            assert result.p_net < 1e-15, f"delays ({d1}, {d2}) must be read as a lead"
            assert result.diagnostics["warnings"] == []
            net_by_gap[d2 - d1] = result.net
        assert net_by_gap[1] < net_by_gap[3] < net_by_gap[7], (
            f"net must grow with the delay difference, got {net_by_gap}"
        )

        # A shallow and a near-unit-root driver, neither the AR(1) the fixture above uses.
        for phi in (0.3, 0.99):
            x, y = _unequal_delay_pair(driver_phi=phi)
            result = jnwb.phase_slope_index(
                x, y, fs=FS, bands=self.BETA, n_surrogates=19, rng=0
            )
            assert result.p_net < 1e-15, (
                f"an AR(1) at phi={phi} must also read as a lead"
            )

    def test_equal_delays_are_not_read_as_a_lead(self):
        """The control that makes the asymmetry the cause. With the driver reaching both
        channels at the same lag there is nothing for PSI to convert, and it stays silent."""
        for phi in (0.3, 0.6, 0.9, 0.99):
            x, y = _unequal_delay_pair(d1=3, d2=3, driver_phi=phi)
            result = jnwb.phase_slope_index(
                x, y, fs=FS, bands=self.BETA, n_surrogates=19, rng=0
            )
            assert abs(result.net) < 0.05, (
                f"equal delays must give no asymmetry, got net={result.net} at phi={phi}"
            )
            assert result.p_net > 0.05, (
                f"equal delays must not read as a lead, p={result.p_net} at phi={phi}"
            )

    def test_a_single_frequency_driver_gives_nothing(self):
        """The boundary the estimator already documents. The artefact needs power spread
        across the band: a pure in-band sinusoid driver produces no lead, which is why
        `phase_slope_index`'s docstring says a low |z| on a narrowband signal is not
        evidence of no lead."""
        time = np.arange(N_TIMES) / FS
        driver = np.sin(2.0 * np.pi * 20.0 * time)
        x = np.zeros(N_TIMES)
        y = np.zeros(N_TIMES)
        x[1:] = driver[: N_TIMES - 1]
        y[4:] = driver[: N_TIMES - 4]
        x = x + 0.03 * np.random.default_rng(11).normal(size=N_TIMES)
        y = y + 0.03 * np.random.default_rng(12).normal(size=N_TIMES)
        result = jnwb.phase_slope_index(
            x, y, fs=FS, bands=self.BETA, n_surrogates=19, rng=0
        )
        assert result.p_net > 0.05, (
            f"a narrowband driver carries no lead to report, got p={result.p_net}"
        )


def _var_pair(seed=5, phi=0.5, lag=3, n=N_TIMES):
    """A stationary VAR in which x drives y with a lag of `lag` samples.

    `y` is its own AR(1) and takes x at lag 3, so the pair is a VAR(3) in y and a VAR(1) in
    x. Orders at or above 3 span the true structure; `order=1` is the mis-specified case
    the filtering tests measure.
    """
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = np.zeros(n)
    innovations = rng.normal(size=n)
    for i in range(lag, n):
        y[i] = phi * y[i - 1] + 0.6 * x[i - lag] + innovations[i]
    return x, y


class TestFilteringBeforeGranger:
    """Filtering before Granger: Granger causality is invariant under an invertible filter,
    so band-passing cannot
    isolate a band, and it often raises the fitted order (Bastos and Schoffelen 2016
    table 2, filtering row; Barnett and Seth 2011, whose abstract states the invariance and
    the order effect). The caller's step is to read `per_band` of `granger_spectral`.

    Recorded here, on a VAR(3) pair. NO INVARIANCE IS CLAIMED: the raw-to-filtered ratio is
    0.666 at the true order and stays between 0.449 and 0.799 at every order from 4 to 20,
    which is substantial estimator sensitivity rather than numerical invariance. What the
    measurements support is narrower: the extreme order-1 figure of 6604 is misspecification
    interacting with the filter and disappears under an adequate order. Two things remain
    regardless of order: `order='auto'` moves from 3 to the `max_lag` ceiling of 20, which
    changes the fitted estimand and not only its precision; and no filter recovers a band
    value, since the same pair gives 0.666 with an 8-60 Hz filter and 0.457 with 30-80 Hz
    against `granger_spectral`'s 0.2976.
    """

    def test_filtering_before_granger_does_not_reproduce_a_band(self):
        """The reason the row is a caller's step: filtering is not a band selector, so a
        caller who filters first and reads `granger` is not reading the alpha band."""
        x, y = _var_pair()
        filtered_x = jnwb.bandpass_filter(x, FS, 8.0, 60.0)
        filtered_y = jnwb.bandpass_filter(y, FS, 8.0, 60.0)

        raw = jnwb.granger(x, y, order=1, n_surrogates=19, rng=0)
        filtered = jnwb.granger(filtered_x, filtered_y, order=1, n_surrogates=19, rng=0)
        ratio = filtered.diagnostics["f_x_to_y"] / raw.diagnostics["f_x_to_y"]
        assert ratio == pytest.approx(6604.0, rel=0.05), (
            f"the filtered F ratio no longer reproduces: {ratio}"
        )
        assert ratio > 100.0, (
            f"the F statistic must move far more than an invertible filter allows: {ratio}"
        )

    def test_the_invariance_holds_across_correctly_specified_orders(self):
        """The measured result, which supports the docs rather than contradicting them: at
        every order that spans the true structure the filter moves `f_x_to_y` by a factor
        inside 0.4 to 0.9, with or without zero phase. The order-1 and order-2 figures are
        misspecification, so they are not evidence against the invariance."""
        x, y = _var_pair()
        filtered_x = jnwb.bandpass_filter(x, FS, 8.0, 60.0)
        filtered_y = jnwb.bandpass_filter(y, FS, 8.0, 60.0)

        for order in (3, 4, 5, 6, 8, 12, 20):
            raw = jnwb.granger(x, y, order=order, n_surrogates=19, rng=0)
            filtered = jnwb.granger(
                filtered_x, filtered_y, order=order, n_surrogates=19, rng=0
            )
            ratio = filtered.diagnostics["f_x_to_y"] / raw.diagnostics["f_x_to_y"]
            assert 0.3 < ratio < 1.0, (
                f"order {order} must stay within the invariance, got {ratio}"
            )

        at_true_order = (
            jnwb.granger(
                filtered_x, filtered_y, order=3, n_surrogates=19, rng=0
            ).diagnostics["f_x_to_y"]
            / jnwb.granger(x, y, order=3, n_surrogates=19, rng=0).diagnostics[
                "f_x_to_y"
            ]
        )
        assert at_true_order == pytest.approx(0.666, rel=0.02), (
            f"the order-3 ratio no longer reproduces: {at_true_order}"
        )

    def test_no_filter_configuration_recovers_the_band_value(self):
        """Why the row says filtering is not a band selector. The same pair filtered to
        8-60 Hz and to 30-80 Hz gives different statistics, and neither matches what
        `granger_spectral` reports for the spectrum, so a caller who filters first is
        reading an artefact of the filter's band."""
        x, y = _var_pair()
        spectral = jnwb.granger_spectral(x, y, fs=FS, order=3, n_surrogates=19, rng=0)
        full = spectral.per_band["full"]["value"]

        ratios = {}
        for low, high in ((1.0, 100.0), (8.0, 60.0), (8.0, 30.0), (30.0, 80.0)):
            filtered = jnwb.granger(
                jnwb.bandpass_filter(x, FS, low, high),
                jnwb.bandpass_filter(y, FS, low, high),
                order=3,
                n_surrogates=19,
                rng=0,
            )
            raw = jnwb.granger(x, y, order=3, n_surrogates=19, rng=0)
            ratios[(low, high)] = (
                filtered.diagnostics["f_x_to_y"] / raw.diagnostics["f_x_to_y"]
            )
        assert ratios[(8.0, 60.0)] == pytest.approx(0.666, rel=0.02)
        assert ratios[(30.0, 80.0)] == pytest.approx(0.457, rel=0.02)
        assert ratios[(8.0, 60.0)] != pytest.approx(ratios[(30.0, 80.0)], rel=0.05), (
            "two different bands must not give the same answer"
        )

        filtered_8_60 = jnwb.granger(
            jnwb.bandpass_filter(x, FS, 8.0, 60.0),
            jnwb.bandpass_filter(y, FS, 8.0, 60.0),
            order=3,
            n_surrogates=19,
            rng=0,
        )
        assert filtered_8_60.x_to_y == pytest.approx(0.2080, rel=0.02)
        assert full == pytest.approx(0.2976, rel=0.02), (
            "and the filtered value is not the spectral one a caller wanted"
        )

    def test_filtering_raises_the_fitted_order_to_the_ceiling(self):
        x, y = _var_pair()
        raw = jnwb.granger(x, y, order="auto", n_surrogates=19, rng=0)
        filtered = jnwb.granger(
            jnwb.bandpass_filter(x, FS, 8.0, 60.0),
            jnwb.bandpass_filter(y, FS, 8.0, 60.0),
            order="auto",
            n_surrogates=19,
            rng=0,
        )
        assert raw.params["order_x_to_y"] == 3
        assert filtered.params["order_x_to_y"] == 20
        assert (
            "selected_order_hit_max_lag_ceiling" in filtered.diagnostics["warnings"]
        ), "and the ceiling is named rather than passed silently"
        assert "selected_order_hit_max_lag_ceiling" not in raw.diagnostics["warnings"]

    def test_filtering_raises_the_reverse_statistic(self):
        """The reverse direction is the dangerous half. The unfiltered fit already reports
        `f_y_to_x` at 1.90, so this is not an effect filtering invents from nothing; it is
        an effect filtering multiplies by 217, from a value near the noise floor to one
        four orders of magnitude larger. The p-value stays at the surrogate floor either
        way, so the inflation is visible in the statistic and not in the significance."""
        x, y = _var_pair()
        raw = jnwb.granger(x, y, order=1, n_surrogates=19, rng=0)
        filtered = jnwb.granger(
            jnwb.bandpass_filter(x, FS, 8.0, 60.0),
            jnwb.bandpass_filter(y, FS, 8.0, 60.0),
            order=1,
            n_surrogates=19,
            rng=0,
        )
        f_raw = raw.diagnostics["f_y_to_x"]
        f_filtered = filtered.diagnostics["f_y_to_x"]
        assert f_raw == pytest.approx(1.9048, rel=0.05), (
            f"the unfiltered reverse statistic no longer reproduces: {f_raw!r}"
        )
        assert f_filtered == pytest.approx(413.36, rel=0.05)
        assert f_filtered > 100.0 * f_raw, (
            "filtering must not be read as evidence for a direction it inflated"
        )
        assert raw.p_y_to_x == pytest.approx(0.05), (
            "and the p-value does not reveal the inflation, which is why the statistic is "
            "the thing to read"
        )


class TestNonStationarityIsOnlyFlaggedWhenExplosive:
    """Non-stationarity: a slowly decaying or drifting mode makes a finite-order VAR fail
    (Friston et al. 2014). Three predicates are distinct and the library's key stands for
    the first: S1, the fitted VAR's companion matrix has spectral radius below 1;
    S2, the observed process is stationary; S3, a stationarity diagnostic rejects a unit
    root. S1 does not establish S2, and S3 is evidence about a statistical null rather than
    proof of stationarity.

    What the class records, against those three:

    - A slowly decaying mode at phi = 0.999 gives radius 0.99860, so S1 holds and the key
      says `stationary` True, while the series plainly is not stationary (S2 fails) and
      `granger`'s ADF does not reject the unit root at p = 0.50 (S3 does not reject).
    - A 0.05 Hz drift reaches a radius within float rounding of 1.0, so S1's verdict turns
      on the last bits of a float and no warning is raised either way, while `granger`'s ADF
      rejects the unit root.
    - Neither test substitutes for the other: on a random walk the ADF verdict flips between
      the raw series (p = 0.0009, S3 rejects) and the lagged copy `granger` is handed
      (p = 0.085, S3 does not reject).

    Only the explosive mode (phi = 1.002, radius 1.00200) is caught by both.
    """

    def test_the_radius_check_fires_on_an_explosive_mode(self):
        explosive = _ar_pair(N_TIMES, 11, phi1=1.002, phi2=0.0)
        result = jnwb.granger_spectral(
            np.roll(explosive, 5), explosive, fs=FS, n_surrogates=19, rng=0
        )
        assert result.diagnostics["spectral_radius"] > 1.0
        assert result.diagnostics["stationary"] is False
        assert any(
            w.startswith("var_non_stationary_spectral_radius")
            for w in result.diagnostics["warnings"]
        ), "and the reason is named"

    def test_a_slowly_decaying_mode_passes_the_radius_check_unflagged(self):
        """The case the row names. A mode at phi = 0.999 has an eigenvalue below 1, so the
        fitted VAR is dynamically stable and the key says so."""
        slow = _ar_pair(N_TIMES, 8, phi1=0.999, phi2=0.0)
        result = jnwb.granger_spectral(
            np.roll(slow, 5), slow, fs=FS, n_surrogates=19, rng=0
        )
        assert result.diagnostics["spectral_radius"] == pytest.approx(0.99860, rel=1e-3)
        assert result.diagnostics["stationary"] is True
        assert result.diagnostics["warnings"] == []

    def test_the_two_estimators_disagree_about_the_slowly_decaying_mode(self):
        """`granger`'s ADF test calls it a unit root and `granger_spectral` calls it
        stationary. A caller reading either key alone is misled on this fixture."""
        slow = _ar_pair(N_TIMES, 8, phi1=0.999, phi2=0.0)
        spectral = jnwb.granger_spectral(
            np.roll(slow, 5), slow, fs=FS, n_surrogates=19, rng=0
        )
        var = jnwb.granger(np.roll(slow, 5), slow, order=4, n_surrogates=19, rng=0)
        assert spectral.diagnostics["stationary"] is True
        assert "possible_nonstationarity_adf_p>0.05" in var.diagnostics["warnings"]

    def test_a_random_walk_passes_the_radius_check_but_not_the_adf_one(self):
        """The reverse disagreement, so neither key is trustworthy alone.

        The ADF verdict here depends on which of two nearly identical series is tested:
        on the raw walk `adfuller` returns p = 0.0009 and certifies stationarity, while on
        the lagged copy `np.roll(walk, 5)` -- the series `granger` is handed -- it returns
        p = 0.085 and raises the warning. One test, two opposite answers, and the radius
        check passing the pair throughout.
        """
        rng = np.random.default_rng(7)
        random_walk = np.cumsum(rng.normal(size=N_TIMES))
        lagged = np.roll(random_walk, 5)
        spectral = jnwb.granger_spectral(
            lagged, random_walk, fs=FS, n_surrogates=19, rng=0
        )
        var = jnwb.granger(lagged, random_walk, order=4, n_surrogates=19, rng=0)
        assert spectral.diagnostics["spectral_radius"] == pytest.approx(
            0.99613, rel=1e-3
        )
        assert spectral.diagnostics["stationary"] is True, (
            "the radius check passes a random walk"
        )
        assert "possible_nonstationarity_adf_p>0.05" in var.diagnostics["warnings"], (
            "while the ADF check on the lagged copy calls it a unit root"
        )

    def test_a_drift_sits_within_rounding_of_the_threshold(self):
        """A unit-root mode reaches a radius within float rounding of 1.0, so which side of
        the strict comparison it lands on is a property of the build, not of the data. On
        this machine it landed 1.6e-15 below; CI's linear-algebra stack put it at or above.
        Either way no warning is raised, so a mode sitting on the boundary gets no signal
        from `granger_spectral` at all. The pin here is the placement and the silence, not
        the verdict."""
        time = np.arange(N_TIMES) / FS
        drift = np.sin(2.0 * np.pi * 0.05 * time)
        delayed = np.roll(drift, 5)
        result = jnwb.granger_spectral(delayed, drift, fs=FS, n_surrogates=19, rng=0)
        radius = result.diagnostics["spectral_radius"]

        assert radius == pytest.approx(1.0, abs=1e-13), (
            f"the drift radius must sit on the threshold, got {radius!r}"
        )
        assert result.diagnostics["stationary"] == (radius < 1.0), (
            "the key is the strict comparison of the radius, nothing more"
        )
        assert result.diagnostics["warnings"] == [], (
            "and a radius on the threshold raises no warning on either side"
        )

        var = jnwb.granger(delayed, drift, order=4, n_surrogates=19, rng=0)
        assert "possible_nonstationarity_adf_p>0.05" in var.diagnostics["warnings"], (
            "the ADF check still calls the drifting pair a unit root"
        )

    def test_granger_carries_no_stationarity_key(self):
        """The asymmetry between the two estimators is itself part of the row."""
        rng = np.random.default_rng(7)
        random_walk = np.cumsum(rng.normal(size=N_TIMES))
        result = jnwb.granger(
            np.roll(random_walk, 5), random_walk, order=4, n_surrogates=19, rng=0
        )
        assert "stationary" not in result.diagnostics
        assert "spectral_radius" not in result.diagnostics


#: Every row of the `docs/common_mistakes.md` pitfalls table, mapped to the class that
#: holds it. Item 11-31 requires each of the nine rows to be held by a test here or to
#: have its gap named in that test's docstring. The rows marked `gap` are held by a test
#: that pins the gap itself, so the reader of the failing assertion learns what is missing.
PITFALL_ROWS = {
    "Common reference": TestCommonReference,
    "Volume conduction": TestVolumeConduction,
    "Signal-to-noise asymmetry": TestSignalToNoiseAsymmetry,
    "Common input": TestCommonInput,
    "Bivariate against conditional Granger": TestBivariateAgainstConditionalGranger,
    "Sample-size bias": TestSampleSizeBias,
    "Phase slope as direction": TestPhaseSlopeIsNotDirection,
    "Filtering before Granger": TestFilteringBeforeGranger,
    "Non-stationarity": TestNonStationarityIsOnlyFlaggedWhenExplosive,
}


class TestEveryPitfallRowIsHeldOrNamesItsGap:
    """Item 11-31: the table in `docs/common_mistakes.md` states each pitfall once, and
    this module holds each of the nine rows or names the gap in the holding test's
    docstring.

    The check is over the table as it reads on disk, not over the copy transcribed here,
    so a row added to the documentation fails until a test holds it or names its gap.
    """

    @staticmethod
    def _table():
        """The pitfalls table as it reads on disk: (row, guard cell) per entry."""
        path = Path(__file__).resolve().parents[1] / "docs" / "common_mistakes.md"
        text = path.read_text(encoding="utf-8")
        start = text.index("## Interpretational Pitfalls of Coupling and Direction")
        table = text[start:]
        rows = []
        for line in table.splitlines():
            if not line.startswith("|"):
                if rows:
                    break
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if (
                len(cells) == 3
                and cells[0] not in ("Pitfall",)
                and set(cells[0]) != {"-"}
            ):
                rows.append((cells[0], cells[2]))
        return rows

    @staticmethod
    def _documented_rows():
        return [row for row, _ in TestEveryPitfallRowIsHeldOrNamesItsGap._table()]

    @classmethod
    def _documented_rows_with_guards(cls):
        for row, guard in cls._table():
            assert row in PITFALL_ROWS, f"the documented row {row!r} is not mapped"
            yield row, guard, PITFALL_ROWS[row]

    def test_the_table_has_the_nine_rows_this_module_maps(self):
        documented = self._documented_rows()
        assert documented == list(PITFALL_ROWS), (
            "the pitfalls table and this module disagree: "
            f"documented {documented}, mapped {list(PITFALL_ROWS)}"
        )

    def test_every_row_has_a_holding_class_in_this_module(self):
        for row, holder in PITFALL_ROWS.items():
            tests = [
                name
                for name in dir(holder)
                if name.startswith("test_") and callable(getattr(holder, name))
            ]
            assert tests, (
                f"the row {row!r} maps to {holder.__name__}, which holds no test"
            )
            docstring = (holder.__doc__ or "").strip()
            assert docstring, (
                f"the row {row!r} is held by {holder.__name__}, whose docstring names "
                "neither what it records nor what gap is left"
            )

    def test_every_row_names_itself_in_the_holding_docstring(self):
        """Semantic coverage, not name correspondence. A class mapped to a row its
        docstring never mentions cannot show which pitfall its tests hold, and two rows
        sharing one class hides that."""
        for row, holder in PITFALL_ROWS.items():
            assert row in (holder.__doc__ or ""), (
                f"{holder.__name__} is mapped to the row {row!r} but its docstring never "
                "names it, so the mapping is not evidenced"
            )

    def test_every_row_calls_the_operation_its_documented_guard_names(self):
        """Binds each row to the mechanism it describes. The guard column of each row names
        the operations that answer it, so the holding class must actually call them: a row
        whose test never calls the guard's operation is held by name only."""
        symbols = re.compile(r"`([a-z_][a-z0-9_]*)`")
        for row, guard, holder in self._documented_rows_with_guards():
            tests_source = "".join(
                inspect.getsource(getattr(holder, name))
                for name in dir(holder)
                if name.startswith("test_") and callable(getattr(holder, name))
            )
            for name in symbols.findall(guard):
                if not hasattr(jnwb, name):
                    continue  # a doc label or an argument, not a public symbol
                assert f"jnwb.{name}" in tests_source, (
                    f"the row {row!r} names {name!r} in its guard column, but no test in "
                    f"{holder.__name__} calls it"
                )

    def test_every_documented_row_is_reachable_from_this_module(self):
        """The reverse direction: a row the table states must name the class that holds
        it, so a documentation row cannot be left unheld by removing its entry here."""
        module = sys.modules[__name__]
        # This closure class checks the mapping; it does not hold a pitfall row itself.
        declared = {
            name
            for name, value in vars(module).items()
            if isinstance(value, type)
            and name.startswith("Test")
            and name != "TestEveryPitfallRowIsHeldOrNamesItsGap"
        }
        mapped = {holder.__name__ for holder in PITFALL_ROWS.values()}
        assert declared == mapped, (
            f"test classes here are {sorted(declared)}, mapped rows are {sorted(mapped)}"
        )
