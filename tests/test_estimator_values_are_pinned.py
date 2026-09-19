"""Estimators whose returned numbers no test constrained.

05-83 mandatory target 3. 05-54's Accept read "no estimator in sections 1-2 survives its
own mutation", which was broader than the nine candidates its evidence named. Measuring the
rest: 22 mutations, each preserving shape, keys and dtype and changing a returned number,
run against the whole suite. Eighteen survived all 2679 tests.

A nineteenth appeared to die and did not. `np.log` -> `np.log2` in `granger_spectral` was
recorded as killed by `test_the_probe_agrees_with_an_independent_wall_clock`, a test that
times two imports -- an expression no import executes. Two clean re-runs return SURVIVED.
That test now retries; the mutation is pinned here.

Every oracle below is independent of the code under test: a closed form worked out by hand,
an analytic identity the estimator must satisfy, or a quantity the same function computes
by a path the mutation does not touch. None re-implements the estimator.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf
from scipy import stats

from jnwb.artifact_repair import detect_band_outliers, repair_lfp_trials
from jnwb.connectivity import (
    _entropy_bits,
    granger,
    granger_causality,
    granger_spectral,
    network_topology,
    spike_mutual_information,
)
from jnwb.spectral import compute_psd, laplacian_reference, spectral_tilt
from jnwb.spiking import classify_response_significance, gaussian_smooth_rate
from jnwb.statistics import StatisticalAnalysis, coef_rows
from jnwb.viz import raster_psth


class TestComputePsdReturnsADensity:
    """`scaling="spectrum"` changes every returned number and preserves shape and dtype."""

    def test_it_integrates_to_the_variance_of_the_signal(self):
        """Parseval. A density integrates to the variance; a spectrum is 1.49x that here.

        The two differ by the window's effective noise bandwidth, so no tolerance that
        admits Welch's own estimation error also admits the wrong scaling.
        """
        fs = 500.0
        x = np.random.default_rng(3).normal(size=8000)

        freqs, psd = compute_psd(x, fs=fs)
        integral = float(np.trapezoid(psd, freqs))

        assert integral == pytest.approx(x.var(), rel=0.05), (
            f"the PSD integrates to {integral:.4f} where the signal's variance is "
            f"{x.var():.4f}; scaling='spectrum' gives a ratio near 1.49"
        )

    def test_a_sinusoid_puts_its_variance_at_its_own_frequency(self):
        """A second reading of the same property, localised instead of integrated."""
        fs, f0, amplitude = 500.0, 40.0, 3.0
        t = np.arange(10000) / fs
        x = amplitude * np.sin(2 * np.pi * f0 * t)

        freqs, psd = compute_psd(x, fs=fs)
        peak = int(np.argmax(psd))

        assert freqs[peak] == pytest.approx(f0, abs=1.0)
        # A pure tone's variance is A^2/2, and for a density it lands in the peak's
        # neighbourhood rather than in the peak bin alone.
        band = (freqs >= f0 - 2) & (freqs <= f0 + 2)
        assert float(np.trapezoid(psd[band], freqs[band])) == pytest.approx(
            amplitude ** 2 / 2, rel=0.05)


class TestSpectralTiltIsFittedOnTwoDecimalLogAxes:
    def test_a_brownian_trace_returns_an_exponent_of_minus_two(self):
        """Integrated white noise has PSD proportional to f^-2 by construction.

        The fit takes log10 of both axes, so the slope is the exponent. Taking log2 of the
        frequency axis alone rescales it by log10(2): -2 becomes -0.60, and no tolerance
        wide enough to cover Welch's scatter comes close to that.
        """
        rng = np.random.default_rng(3)
        brownian = np.cumsum(rng.normal(size=60000))

        out = spectral_tilt(brownian, fs=1000.0, freq_range=(5.0, 100.0))

        assert out["exponent"] == pytest.approx(-2.0, abs=0.25), out["exponent"]

    def test_the_offset_is_reported_in_linear_power(self):
        """`offset` is 10**intercept, so it is positive whatever the trace's scale."""
        rng = np.random.default_rng(11)
        brownian = np.cumsum(rng.normal(size=20000))

        out = spectral_tilt(brownian, fs=1000.0, freq_range=(5.0, 100.0))

        assert out["offset"] > 0.0
        assert np.isfinite(out["offset"])


class TestLaplacianReferenceSubtractsTheNeighbourMeanOnce:
    def test_a_quadratic_profile_gives_exactly_minus_one(self):
        """The one profile with a closed-form discrete Laplacian.

        For v_i = i^2 the neighbour mean is i^2 + 1, so every contact with two neighbours
        returns exactly -1, and the first contact (whose only neighbour is v_1 = 1) also
        returns -1. The last returns 16 - 9 = 7. Any rescaling of the difference moves all
        five, and shape and dtype are unchanged.
        """
        data = (np.arange(5, dtype=float) ** 2)[:, None] * np.ones((1, 4))

        out = laplacian_reference(data)

        np.testing.assert_array_equal(
            out, np.array([-1.0, -1.0, -1.0, -1.0, 7.0])[:, None] * np.ones((1, 4)))

    def test_a_linear_ramp_is_flattened_to_zero_in_the_interior(self):
        """A linear field has no curvature, so the interior must be exactly zero."""
        data = (3.0 * np.arange(6, dtype=float))[:, None] * np.ones((1, 2))

        out = laplacian_reference(data)

        np.testing.assert_array_equal(out[1:-1], np.zeros((4, 2)))


class TestCohensDIsDividedByThePooledStandardDeviation:
    def test_it_matches_a_closed_form_worked_out_by_hand(self):
        """group1 = 1..5 and group2 = 3..7 have means 3 and 5 and variance 2.5 each.

        The pooled SD is sqrt((4*2.5 + 4*2.5) / 8) = sqrt(2.5), so d = -2 / sqrt(2.5)
        exactly. Halving the denominator halves d, which nothing else checked.
        """
        group1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        group2 = np.array([3.0, 4.0, 5.0, 6.0, 7.0])

        out = StatisticalAnalysis.compare_groups(group1, group2)

        assert out["parametric"]["effect_size_name"] == "cohens_d_pooled"
        assert out["parametric"]["effect_size"] == pytest.approx(-2.0 / np.sqrt(2.5))

    def test_swapping_the_groups_flips_only_the_sign(self):
        group1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        group2 = np.array([3.0, 4.0, 5.0, 6.0, 7.0])

        forward = StatisticalAnalysis.compare_groups(group1, group2)
        reverse = StatisticalAnalysis.compare_groups(group2, group1)

        assert forward["parametric"]["effect_size"] == pytest.approx(
            -reverse["parametric"]["effect_size"])


class TestEtaSquaredWeighsEachGroupByItsSize:
    def test_it_matches_a_closed_form_worked_out_by_hand(self):
        """Groups 1..3, 4..6 and 7..9 have means 2, 5, 8 about a grand mean of 5.

        SS_between = 3*9 + 3*0 + 3*9 = 54 and SS_total = 29 + 2 + 29 = 60, so eta^2 = 0.9
        exactly. Dropping the group-size weight gives 18/60 = 0.3, in range and wrong.
        """
        groups = {
            "a": np.array([1.0, 2.0, 3.0]),
            "b": np.array([4.0, 5.0, 6.0]),
            "c": np.array([7.0, 8.0, 9.0]),
        }

        out = StatisticalAnalysis.compare_multiple_groups(groups)

        assert out["parametric"]["effect_size_name"] == "eta_squared"
        assert out["parametric"]["effect_size"] == pytest.approx(0.9)

    def test_unequal_group_sizes_change_the_answer(self):
        """The weight only shows itself when the groups differ in size.

        Duplicating one group's observations leaves every mean untouched and every
        unweighted term untouched, so an unweighted SS_between cannot move. The weighted
        one must.
        """
        base = {
            "a": np.array([1.0, 2.0, 3.0]),
            "b": np.array([4.0, 5.0, 6.0]),
            "c": np.array([7.0, 8.0, 9.0]),
        }
        widened = dict(base, a=np.array([1.0, 2.0, 3.0] * 3))

        assert (StatisticalAnalysis.compare_multiple_groups(base)["parametric"]["effect_size"]
                != pytest.approx(
                    StatisticalAnalysis.compare_multiple_groups(
                        widened)["parametric"]["effect_size"]))


class TestBootstrapCiHalvesItsAlphaBetweenTheTails:
    def test_it_agrees_with_the_parametric_interval_it_reports_beside(self):
        """The same call computes a t interval from `(1 + ci) / 2`, which the mutation
        does not touch. On 500 normal draws the two must agree; leaving alpha unhalved
        turns the 95% interval into the 90% one, which is 0.84x as wide.
        """
        data = np.random.default_rng(7).normal(10.0, 2.0, size=500)

        out = StatisticalAnalysis.bootstrap_ci(
            data, n_bootstrap=4000, ci=0.95, rng=np.random.default_rng(1))

        lo, hi = out["bootstrap_ci"]
        plo, phi = out["parametric_ci"]
        ratio = (hi - lo) / (phi - plo)

        assert ratio == pytest.approx(1.0, abs=0.07), (
            f"the bootstrap interval is {ratio:.3f}x the parametric one; an unhalved "
            f"alpha gives 0.84"
        )

    def test_a_wider_confidence_level_gives_a_wider_interval(self):
        data = np.random.default_rng(7).normal(10.0, 2.0, size=200)

        narrow = StatisticalAnalysis.bootstrap_ci(
            data, n_bootstrap=2000, ci=0.80, rng=np.random.default_rng(1))["bootstrap_ci"]
        wide = StatisticalAnalysis.bootstrap_ci(
            data, n_bootstrap=2000, ci=0.99, rng=np.random.default_rng(1))["bootstrap_ci"]

        assert wide[0] < narrow[0] and narrow[1] < wide[1], (narrow, wide)


class TestCoefRowsKeepsTheTwoIntervalBoundsApart:
    @staticmethod
    def _fit():
        rng = np.random.default_rng(7)
        frame = pd.DataFrame({"x": rng.normal(size=80)})
        frame["y"] = 2.5 * frame["x"] + rng.normal(scale=0.5, size=80)
        return smf.ols("y ~ x", data=frame).fit()

    def test_the_estimate_lies_strictly_inside_its_own_interval(self):
        """Reading the upper bound into `ci_lo` leaves both bounds above the estimate."""
        rows = coef_rows(self._fit(), model="ols", estimate_key="estimate", stat_key="t")

        assert rows, "the fit produced no coefficient rows"
        for row in rows:
            assert row["ci_lo"] < row["estimate"] < row["ci_hi"], row

    def test_the_interval_is_symmetric_about_the_estimate(self):
        """An OLS interval is estimate +/- t*se, so the two half-widths are equal."""
        rows = coef_rows(self._fit(), model="ols", estimate_key="estimate", stat_key="t")

        for row in rows:
            assert (row["estimate"] - row["ci_lo"]) == pytest.approx(
                row["ci_hi"] - row["estimate"]), row


class TestSpikeMutualInformationIsReportedInBits:
    def test_two_identical_balanced_trains_carry_exactly_one_bit(self):
        """MI(x, x) is H(x), and a balanced binary occupancy has H = 1 bit exactly.

        Reporting nats instead gives ln 2 = 0.693 -- in range, positive, and wrong.
        """
        spikes = np.arange(50) * 0.01 + 0.005

        mi = spike_mutual_information(
            spikes, spikes, time_window_s=(0.0, 1.0), bin_size_ms=10.0)

        assert mi == pytest.approx(1.0)

    def test_an_unbalanced_occupancy_matches_its_binary_entropy(self):
        """A second point on the same curve: 25 of 100 bins occupied gives H(0.25)."""
        spikes = np.arange(25) * 0.01 + 0.005
        p = 0.25
        entropy_bits = -(p * np.log2(p) + (1 - p) * np.log2(1 - p))

        mi = spike_mutual_information(
            spikes, spikes, time_window_s=(0.0, 1.0), bin_size_ms=10.0)

        assert mi == pytest.approx(entropy_bits)


class TestNetworkDensityCountsOrderedPairs:
    def test_a_fully_connected_triangle_in_a_four_node_graph(self):
        """Six directed edges among four nodes is 6 / (4*3) = 0.5.

        Dividing by n^2 counts the n self-pairs the function has just zeroed out, giving
        0.375 -- still in [0, 1], and wrong.
        """
        adjacency = np.array([[0.0, 1.0, 1.0, 0.0],
                              [1.0, 0.0, 1.0, 0.0],
                              [1.0, 1.0, 0.0, 0.0],
                              [0.0, 0.0, 0.0, 0.0]])

        out = network_topology(adjacency, threshold=0.5)

        assert out["n_edges"] == 6
        assert out["density"] == pytest.approx(0.5)

    def test_a_complete_graph_has_density_one(self):
        """The property that fixes the denominator: every ordered pair present is 1.0."""
        adjacency = np.ones((5, 5))

        out = network_topology(adjacency, threshold=0.5)

        assert out["density"] == pytest.approx(1.0), out["density"]


class TestMillerMadowCorrectsInBits:
    """`_entropy_bits` is private, and reached only through `transfer_entropy`'s own
    estimate, where the correction is one term among several and cannot be read off. The
    correction's size is the whole question here, so it is tested where it is visible."""

    def test_the_correction_is_the_nats_formula_divided_by_ln_two(self):
        """100 samples over 2 equally likely symbols: the plug-in entropy is 1 bit and
        the Miller-Madow term is (K-1)/(2N) nats, which is 1/(2*100*ln 2) bits.

        Leaving out the ln 2 adds a nats-sized correction to a bits-sized entropy: 1.0050
        against 1.0072. Both are plausible, and only one is the documented unit.
        """
        codes = np.array([0] * 50 + [1] * 50)

        plugin = _entropy_bits(codes, None)
        corrected = _entropy_bits(codes, "mm")

        assert plugin == pytest.approx(1.0)
        assert corrected == pytest.approx(1.0 + 1.0 / (2 * 100 * np.log(2.0)), abs=1e-12)

    def test_the_correction_shrinks_as_the_sample_grows(self):
        """It is a 1/N bias term, so ten times the data is a tenth of the correction."""
        small = np.array([0] * 50 + [1] * 50)
        large = np.array([0] * 500 + [1] * 500)

        delta_small = _entropy_bits(small, "mm") - _entropy_bits(small, None)
        delta_large = _entropy_bits(large, "mm") - _entropy_bits(large, None)

        assert delta_small == pytest.approx(10.0 * delta_large)


def _ar_gc(src: np.ndarray, tgt: np.ndarray, p: int) -> float:
    """ln(restricted residual variance / unrestricted), by lstsq and nothing else.

    An oracle rather than a re-implementation: it shares no code with the estimator's
    solver, order selection or ridge path, and it writes `np.log` explicitly, which is the
    property under test. `jnwb/connectivity.py` documents the residual variance as the
    maximum-likelihood RSS / N, so that convention is used and no other. Measured, it
    reproduces `granger`'s number to 0.0.
    """
    n = len(tgt)
    rows = n - p
    y = tgt[p:]
    tgt_lags = np.column_stack([tgt[p - k - 1:n - k - 1] for k in range(p)])
    src_lags = np.column_stack([src[p - k - 1:n - k - 1] for k in range(p)])

    def ml_var(design: np.ndarray) -> float:
        design = np.column_stack([np.ones(rows), design])
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
        resid = y - design @ beta
        return float(resid @ resid) / rows

    return float(np.log(ml_var(tgt_lags) / ml_var(np.column_stack([tgt_lags, src_lags]))))


def _driven_pair(n: int = 1500, seed: int = 5):
    """x white, y driven by x at lag 1 with its own autoregression. x -> y only."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = np.empty(n)
    y[0] = 0.0
    for i in range(1, n):
        y[i] = 0.6 * y[i - 1] + 0.8 * x[i - 1] + 0.3 * rng.normal()
    return x, y


class TestGrangerIsReportedInNats:
    """`unit` says "log variance ratio". Base 2 leaves every number 1.4427x too large."""

    @pytest.mark.parametrize("order", [1, 2, 3])
    def test_it_matches_an_independent_least_squares_fit(self, order: int):
        x, y = _driven_pair()

        out = granger(x, y, order=order, detrend=None)

        assert out.x_to_y == pytest.approx(_ar_gc(x, y, order), rel=1e-9)

    def test_the_undriven_direction_matches_too(self):
        """Pinning only the strong direction would leave the weak one free."""
        x, y = _driven_pair()

        out = granger(x, y, order=2, detrend=None)

        assert out.y_to_x == pytest.approx(_ar_gc(y, x, 2), rel=1e-6)


class TestDeprecatedGrangerCausalityIsReportedInNats:
    def test_each_statistic_is_the_log_of_the_variances_it_reports(self):
        """This function returns its own restricted and unrestricted variances, so the
        oracle is in the result: F must be their natural log ratio. Base 2 breaks the
        identity between the number and the two numbers beside it.
        """
        x, y = _driven_pair()

        # This function is deprecated and still shipped, so the call is made inside the
        # warning it is contracted to raise rather than leaking one into the suite's output.
        with pytest.warns(DeprecationWarning):
            out = granger_causality(x, y, order=2)

        assert out["F_1_to_2"] == pytest.approx(
            float(np.log(out["var_restricted_2"] / out["var_unrestricted_2"])), rel=1e-9)
        assert out["F_2_to_1"] == pytest.approx(
            float(np.log(out["var_restricted_1"] / out["var_unrestricted_1"])), rel=1e-9)


class TestSpectralGrangerIntegratesToTheTimeDomainValue:
    def test_the_frequency_average_matches_granger(self):
        """Geweke's decomposition: the spectral GC averages to the time-domain GC.

        Measured at 0.9996 of it here. A base change on the spectral side alone breaks the
        identity by 1/ln 2 = 1.4427, which no tolerance that admits the 0.04% numerical
        gap can absorb. `granger` is pinned independently above, so this cannot pass by
        both sides moving together.
        """
        x, y = _driven_pair(n=3000)

        time_domain = granger(x, y, order=2, detrend=None)
        spectral = granger_spectral(x, y, fs=200.0, order=2, detrend=None, n_freqs=512)

        mean_spectral = float(np.mean(np.asarray(spectral.spectrum["gc_x_to_y"])))

        assert mean_spectral == pytest.approx(time_domain.x_to_y, rel=0.02), (
            f"spectral mean {mean_spectral:.6f} against time-domain "
            f"{time_domain.x_to_y:.6f}; base 2 on one side gives a ratio of 1.44"
        )


class TestResponseSignificanceReportsATwoSidedP:
    def test_the_five_percent_critical_value_returns_five_percent(self):
        """z = 1.95996 is the two-sided 5% point. One-sided returns 0.025 -- a smaller
        p from the same z, which reads as a stronger result than the data support."""
        z = 1.959963984540054

        out = classify_response_significance(
            {"response_zscore": z, "response_count": 50})

        assert out["pvalue"] == pytest.approx(0.05)

    def test_a_second_z_matches_the_normal_survival_function(self):
        out = classify_response_significance(
            {"response_zscore": 1.0, "response_count": 50})

        assert out["pvalue"] == pytest.approx(2.0 * stats.norm.sf(1.0))


class TestGaussianSmoothingUsesTheSigmaItWasGiven:
    def test_a_delta_is_widened_to_exactly_sigma_over_bin_width(self):
        """The smoothed impulse response of a Gaussian filter has standard deviation
        sigma_ms / bin_ms bins, by definition. Halving the conversion halves the width
        while leaving the shape, the shape's dtype and the array's shape intact.
        """
        delta = np.zeros(601)
        delta[300] = 1.0

        smoothed = gaussian_smooth_rate(delta, bin_ms=1.0, sigma_ms=10.0)

        offsets = np.arange(601) - 300
        width = float(np.sqrt((smoothed * offsets ** 2).sum() / smoothed.sum()))
        assert width == pytest.approx(10.0, rel=0.01), width

    def test_the_conversion_uses_the_bin_width_not_just_the_sigma(self):
        """Doubling bin_ms and sigma_ms together must leave the width in bins unchanged."""
        delta = np.zeros(601)
        delta[300] = 1.0
        offsets = np.arange(601) - 300

        def width(bin_ms, sigma_ms):
            out = gaussian_smooth_rate(delta, bin_ms=bin_ms, sigma_ms=sigma_ms)
            return float(np.sqrt((out * offsets ** 2).sum() / out.sum()))

        assert width(1.0, 10.0) == pytest.approx(width(2.0, 20.0), rel=1e-9)


class TestRasterPsthReportsSpikesPerSecond:
    def test_one_spike_in_a_ten_millisecond_bin_is_a_hundred_hertz(self):
        """The closed form: 1 spike / 0.01 s = 100 Hz. Dividing by bin_ms/100 instead
        returns 10 Hz -- a plausible firing rate, off by the factor between ms and s.
        """
        centres, mean, _ = raster_psth(
            np.array([0.005]), np.array([0.0]), (0.0, 100.0), bin_ms=10.0)

        assert centres[0] == pytest.approx(5.0)
        assert mean[0] == pytest.approx(100.0)

    def test_three_spikes_in_one_bin_triple_the_rate(self):
        _, mean, _ = raster_psth(
            np.array([0.001, 0.003, 0.007]), np.array([0.0]), (0.0, 100.0), bin_ms=10.0)

        assert mean[0] == pytest.approx(300.0)


class TestDetectBandOutliersReturnsTheRawPooledMad:
    def test_the_scale_is_the_median_absolute_residual_itself(self):
        """The docstring defines it: "scale = median(|resid|) pooled over all
        (trial, time)". Four trials at 0, 1, 3, 4 have a per-time median of 2 and
        absolute residuals 2, 1, 1, 2, so the pooled median is exactly 1.5.

        Applying the 1.4826 consistency constant would return 2.2239 -- the estimator of a
        normal standard deviation, which is not what this returns, and every z computed
        against it would shrink by the same factor.
        """
        column = np.array([0.0, 1.0, 3.0, 4.0])

        _, scale = detect_band_outliers(np.column_stack([column, column]), z_thresh=6.0)

        assert scale == pytest.approx(1.5)

    def test_scaling_the_data_scales_the_reported_scale(self):
        """A scale in the data's own units, not a normalised one."""
        column = np.array([0.0, 1.0, 3.0, 4.0])
        trace = np.column_stack([column, column])

        _, scale = detect_band_outliers(trace, z_thresh=6.0)
        _, scaled = detect_band_outliers(7.0 * trace, z_thresh=6.0)

        assert scaled == pytest.approx(7.0 * scale)


class TestTrialRepairSubstitutesTheCrossTrialMedian:
    def test_a_flagged_cell_takes_the_median_and_not_the_mean(self):
        """Five trials, one of which is 100 at a single time and 0 everywhere else. The
        cross-trial median there is 0 and the mean is 20, so the substituted value says
        which statistic was used. A mean is pulled by the very outlier being repaired,
        which is the reason the median is specified.
        """
        segments = np.zeros((5, 2, 3))
        segments[4, :, 1] = 100.0

        repaired, _, diagnostics = repair_lfp_trials(segments, min_trials=3)

        assert diagnostics["n_flagged_cells"] == 1
        np.testing.assert_allclose(repaired[4, :, 1], np.zeros(2))

    def test_unflagged_cells_are_returned_untouched(self):
        segments = np.zeros((5, 2, 3))
        segments[4, :, 1] = 100.0

        repaired, _, _ = repair_lfp_trials(segments, min_trials=3)

        np.testing.assert_array_equal(repaired[:4], segments[:4])
        np.testing.assert_array_equal(repaired[4, :, [0, 2]], segments[4, :, [0, 2]])
