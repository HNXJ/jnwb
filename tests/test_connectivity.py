"""Unit tests for jnwb.connectivity -- functional connectivity estimators.

Covers the public-import surface plus one smoke test per estimator. Deeper behavioral coverage
may live in downstream project test suites that call the same jnwb functions.
"""
from __future__ import annotations

import inspect
import warnings

import numpy as np
import pytest
from scipy import stats

import jnwb

from jnwb.connectivity import (
    spike_mutual_information,
    binary_occupancy_mutual_information,
    spike_count_mutual_information,
    granger_causality,
    network_topology,
    DirectedResult,
    as_trials,
    bin_spikes,
    granger,
    granger_spectral,
    phase_slope_index,
    transfer_entropy,
    directed_connectivity,
    directed_network,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        for name, obj in (
            ("spike_mutual_information", spike_mutual_information),
            ("binary_occupancy_mutual_information", binary_occupancy_mutual_information),
            ("spike_count_mutual_information", spike_count_mutual_information),
            ("granger_causality", granger_causality),
            ("network_topology", network_topology),
            ("DirectedResult", DirectedResult),
            ("as_trials", as_trials),
            ("bin_spikes", bin_spikes),
            ("granger", granger),
            ("granger_spectral", granger_spectral),
            ("phase_slope_index", phase_slope_index),
            ("transfer_entropy", transfer_entropy),
            ("directed_connectivity", directed_connectivity),
            ("directed_network", directed_network),
        ):
            assert getattr(jnwb, name) is obj

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("spike_mutual_information", "binary_occupancy_mutual_information",
                     "spike_count_mutual_information", "granger_causality", "network_topology",
                     "DirectedResult", "as_trials", "bin_spikes", "granger", "granger_spectral",
                     "phase_slope_index", "transfer_entropy", "directed_connectivity",
                     "directed_network"):
            assert name in jnwb.__all__

class TestSpikeMutualInformation:
    def test_identical_spike_trains_have_positive_mi(self):
        rng = np.random.default_rng(0)
        spikes = np.sort(rng.uniform(0, 5, 200))
        mi = spike_mutual_information(spikes, spikes, time_window=(0.0, 5.0), bin_size_ms=10.0)
        assert mi > 0

    def test_binary_occupancy_and_spike_count_aliases_delegate(self):
        rng = np.random.default_rng(1)
        s1 = np.sort(rng.uniform(0, 5, 100))
        s2 = np.sort(rng.uniform(0, 5, 100))
        mi_bo = binary_occupancy_mutual_information(s1, s2, time_window=(0.0, 5.0))
        mi_full = spike_mutual_information(s1, s2, time_window=(0.0, 5.0), estimator="binary_occupancy")
        assert mi_bo == pytest.approx(mi_full)
        mi_sc = spike_count_mutual_information(s1, s2, time_window=(0.0, 5.0))
        mi_full_sc = spike_mutual_information(s1, s2, time_window=(0.0, 5.0), estimator="spike_count")
        assert mi_sc == pytest.approx(mi_full_sc)


class TestGrangerCausality:
    def test_x_drives_y_shows_asymmetric_causality(self):
        rng = np.random.default_rng(2)
        n = 2000
        x = rng.standard_normal(n)
        y = np.zeros(n)
        for t in range(2, n):
            y[t] = 0.6 * x[t - 1] + 0.1 * rng.standard_normal()
        result = granger_causality(y, x, order=3)
        assert "F_2_to_1" in result
        assert "F_1_to_2" in result


class TestNetworkTopology:
    def test_thresholds_and_counts_edges(self):
        adj = np.array([[0.0, 0.5, 0.0], [0.5, 0.0, 0.0], [0.0, 0.0, 0.0]])
        result = network_topology(adj, threshold=0.3)
        assert result["n_edges"] == 2

    def test_a_complex_matrix_is_refused_rather_than_cast_to_its_real_part(self):
        """A purely imaginary coupling of 0.5 cast to float is 0: no edge, only a warning."""
        adj = np.array([[0.0, 0.5j], [0.5j, 0.0]])
        with pytest.raises(TypeError, match="complex"):
            network_topology(adj, threshold=0.3)
        assert network_topology(np.abs(adj), threshold=0.3)["n_edges"] == 2


class TestAsTrials:
    def test_normalizes_1d_2d_and_list_input(self):
        assert as_trials(np.arange(10.0)).shape == (1, 10)
        assert as_trials(np.zeros((4, 100))).shape == (4, 100)
        assert as_trials([np.arange(10.0), np.arange(8.0)]).shape == (2, 8)


class TestBinSpikes:
    def test_returns_trials_by_bins_shape(self):
        spike_times = [np.array([0.1, 0.2, 0.35]), np.array([0.05, 0.4])]
        counts = bin_spikes(spike_times, window=(0.0, 0.5), bin_size_ms=100.0)
        assert counts.shape == (2, 5)

    def test_temporal_coordinates_and_bin_centers(self):
        spike_times = [np.array([0.1, 0.25])]
        counts, centers = bin_spikes(
            spike_times, window=(0.0, 0.5), bin_size_ms=100.0, return_centers=True
        )
        assert counts.shape == (1, 5)
        # Bins: [0, 0.1), [0.1, 0.2), [0.2, 0.3), [0.3, 0.4), [0.4, 0.5)
        # Centers: 0.05, 0.15, 0.25, 0.35, 0.45
        expected_centers = np.array([0.05, 0.15, 0.25, 0.35, 0.45])
        np.testing.assert_allclose(centers, expected_centers, rtol=1e-12)

    def test_right_open_boundary_contract(self):
        # Window: [0.0, 0.3) with 100ms bins -> 3 bins: [0, 0.1), [0.1, 0.2), [0.2, 0.3)
        # Spikes:
        # -0.01: outside left (< t0) -> excluded
        #  0.00: exactly on t0 -> bin 0
        #  0.10: exactly on edge 1 -> bin 1 (not bin 0)
        #  0.29: strictly inside bin 2 -> bin 2
        #  0.30: exactly on t1 -> excluded (right-open boundary contract)
        #  0.35: outside right (> t1) -> excluded
        spikes = np.array([-0.01, 0.0, 0.10, 0.29, 0.30, 0.35])

        # Test case 1: per-trial list
        counts_list = bin_spikes([spikes], window=(0.0, 0.3), bin_size_ms=100.0)
        np.testing.assert_array_equal(counts_list, [[1.0, 1.0, 1.0]])

        # Test case 2: continuous spikes with trial_starts = [0.0]
        counts_trial = bin_spikes(
            spikes, window=(0.0, 0.3), bin_size_ms=100.0, trial_starts=[0.0]
        )
        np.testing.assert_array_equal(counts_trial, [[1.0, 1.0, 1.0]])

        # Test case 3: continuous spikes with non-zero trial_start, interior points
        interior_spikes = np.array([5.05, 5.15, 5.25])
        counts_offset = bin_spikes(
            interior_spikes, window=(0.0, 0.3), bin_size_ms=100.0, trial_starts=[5.0]
        )
        np.testing.assert_array_equal(counts_offset, [[1.0, 1.0, 1.0]])

    def test_output_rate_scaling(self):
        # 2 spikes in bin 0 (width = 0.05s = 50ms) -> rate = 2 / 0.05 = 40.0 Hz
        spikes = [np.array([0.01, 0.02])]
        rates = bin_spikes(spikes, window=(0.0, 0.2), bin_size_ms=50.0, output="rate")
        assert rates.shape == (1, 4)
        assert rates[0, 0] == pytest.approx(40.0)
        assert rates[0, 1] == pytest.approx(0.0)

    def test_input_validation(self):
        with pytest.raises(ValueError, match="output must be 'count' or 'rate'"):
            bin_spikes([np.array([0.1])], window=(0.0, 0.5), output="invalid")
        with pytest.raises(ValueError, match="window_s must satisfy end > start"):
            bin_spikes([np.array([0.1])], window=(0.5, 0.5))
        with pytest.raises(ValueError, match="yields 1 bins; need >= 2"):
            bin_spikes([np.array([0.1])], window=(0.0, 0.1), bin_size_ms=100.0)

    STEADY_1KHZ = np.arange(0.0005, 3.0, 0.001)  # one spike per ms, off the bin edges

    def test_a_steady_train_reads_its_rate_in_every_bin_of_a_whole_bin_window(self):
        # 0.3 / 0.01 is 29.999999999999996 in floating point, and is still 30 whole bins.
        rates = bin_spikes(self.STEADY_1KHZ, window_s=(0.0, 0.3), bin_size_ms=10.0, output="rate")
        assert rates.shape == (1, 30)
        np.testing.assert_allclose(rates, 1000.0)
        # An absolute window hours into a recording carries rounding beyond 1e-9 bins:
        # this span is 99.99999999854481 bins in floating point.
        far = bin_spikes(10000.0 + self.STEADY_1KHZ, window_s=(10000.003, 10000.103),
                         bin_size_ms=1.0, output="rate")
        assert far.shape == (1, 100)
        np.testing.assert_allclose(far, 1000.0)

    @pytest.mark.parametrize("end", [0.305, 0.304])
    def test_a_window_that_is_not_whole_bins_is_refused(self, end):
        """Rounded up, the last bin held part of its width and read low as a rate; rounded
        down, the spikes between the last edge and the window end were dropped."""
        with pytest.raises(ValueError, match=r"window_s=\(0, 0\.3\) or window_s=\(0, 0\.31\)"):
            bin_spikes(self.STEADY_1KHZ, window_s=(0.0, end), bin_size_ms=10.0, output="rate")
        with pytest.raises(ValueError, match=r"window_s=\(-0\.1, 0\.2\) or window_s=\(-0\.1, 0\.21\)"):
            bin_spikes(self.STEADY_1KHZ, window_s=(-0.1, end - 0.1), bin_size_ms=10.0,
                       trial_starts=[1.0, 2.0])

    def test_mutual_information_refuses_at_its_own_boundary(self):
        s = np.sort(np.random.default_rng(0).uniform(0.0, 1.0, 50))
        with pytest.raises(ValueError, match=r"spike_mutual_information: time_window_s="):
            spike_mutual_information(s, s, time_window_s=(0.0, 1.0), bin_size_ms=35.0)

    def test_mutual_information_bins_a_boundary_spike_as_bin_spikes_does(self):
        """A spike on the window end is outside the right-open window, so these two trains
        occupy the same bins. A last bin closed on the right counted it and lowered the MI."""
        a = np.array([0.05, 0.15, 0.5])
        b = np.array([0.05, 0.15])
        mi = spike_mutual_information(a, b, time_window_s=(0.0, 0.5), bin_size_ms=100.0)
        assert mi == pytest.approx(
            spike_mutual_information(b, b, time_window_s=(0.0, 0.5), bin_size_ms=100.0))


class TestGranger:
    def test_x_leads_y_gives_positive_net(self):
        rng = np.random.default_rng(3)
        n_trials, n_times = 20, 300
        x = rng.standard_normal((n_trials, n_times))
        y = np.zeros_like(x)
        y[:, 1:] = 0.7 * x[:, :-1] + 0.2 * rng.standard_normal((n_trials, n_times - 1))
        result = granger(x, y, order=3)
        assert isinstance(result, DirectedResult)
        assert result.x_to_y > result.y_to_x

    def test_malformed_aic_structure_warns_instead_of_silent_fallback(self):
        from unittest.mock import patch
        from jnwb.jrsa import _granger

        class _BadModel:
            @property
            def aic(self):
                raise AttributeError("no aic on mock statsmodels result")

        fake_res = {
            1: ({"ssr_ftest": (1.0, 0.05, 2.0)}, (None, _BadModel(), None)),
        }
        x = np.linspace(0, 1, 50)
        y = np.roll(x, 1)
        with patch("statsmodels.tsa.stattools.grangercausalitytests", return_value=fake_res):
            with pytest.warns(UserWarning, match="Granger AIC extraction failed"):
                _granger(x, y, max_lag=1)

    def test_granger_null_non_negative_ml_variance(self):
        """Granger causality using ML residual variance RSS/N is non-negative under plain OLS (0.2.3-REV-07)."""
        rng = np.random.default_rng(42)
        # 10 independent noise trials under true null
        x = rng.standard_normal((10, 500))
        y = rng.standard_normal((10, 500))

        result = granger(x, y, order=3, n_surrogates=0, ridge=0.0)
        assert result.x_to_y >= 0.0, f"Expected non-negative GC under plain OLS, got {result.x_to_y}"
        assert result.y_to_x >= 0.0, f"Expected non-negative GC under plain OLS, got {result.y_to_x}"
        assert result.x_to_y == pytest.approx(0.0, abs=0.01)
        assert result.y_to_x == pytest.approx(0.0, abs=0.01)

    @staticmethod
    def _var3(seed, n_trials, n_times):
        """y depends on x at lags 1 and 3 and on its own lag 1: a VAR of order 3."""
        rng = np.random.default_rng(seed)
        burn = 100
        x = rng.standard_normal((n_trials, n_times + burn))
        e = rng.standard_normal(x.shape)
        y = np.zeros_like(x)
        for t in range(3, n_times + burn):
            y[:, t] = 0.3 * y[:, t - 1] + 0.4 * x[:, t - 1] + 0.5 * x[:, t - 3] + e[:, t]
        return x[:, burn:], y[:, burn:]

    @pytest.mark.parametrize("n_z", [0, 1, 2])
    @pytest.mark.parametrize("criterion", ["aic", "bic"])
    def test_order_criteria_are_the_ml_likelihood_on_one_trimmed_sample(self, criterion, n_z):
        """Order selection scores every candidate on the rows left after trimming the largest
        candidate, with the ML variance RSS/N. statsmodels' OLS `aic`/`bic` are -2 log L plus
        the penalty, with log L at the ML variance; on one sample they differ from the
        criterion only by a constant, so differences across orders must agree. Conditioning
        series enter both the regressors and the parameter count."""
        import statsmodels.api as sm

        from jnwb.connectivity import _granger_order_criteria

        x, y = self._var3(11, 3, 120)
        z_rng = np.random.default_rng(12)
        zs = []
        for _ in range(n_z):
            z = z_rng.standard_normal(x.shape)
            z[:, 1:] += 0.5 * y[:, :-1]  # informative about y's past, so it moves the fit
            zs.append(z)
        max_order = 6
        got = _granger_order_criteria(x, y, zs, max_order, 0.0, criterion)

        want = []
        for p in range(1, max_order + 1):
            rows, target = [], []
            for tr in range(x.shape[0]):
                for t in range(max_order, x.shape[1]):
                    row = [y[tr, t - j] for j in range(1, p + 1)]
                    row += [x[tr, t - j] for j in range(1, p + 1)]
                    for z in zs:
                        row += [z[tr, t - j] for j in range(1, p + 1)]
                    rows.append(row)
                    target.append(y[tr, t])
            fit = sm.OLS(np.asarray(target), sm.add_constant(np.asarray(rows))).fit()
            want.append(getattr(fit, criterion))
        want = np.asarray(want)
        np.testing.assert_allclose(got - got[0], want - want[0], rtol=0, atol=1e-8)

    def test_auto_order_recovers_a_known_var_order(self):
        x, y = self._var3(5, 10, 400)
        result = granger(x, y, order="auto", criterion="bic", max_lag=8)
        assert result.params["order_x_to_y"] == 3

    def test_conditioning_on_a_common_driver_removes_a_spurious_lead(self):
        """z drives x at lag 1 and y at lag 2, and x has no influence on y. Without z, the
        past of x predicts y because it carries the past of z; with z in both models, the
        x-to-y temporal-lag asymmetry disappears."""
        rng = np.random.default_rng(8)
        n_trials, n_times = 10, 400
        z = rng.standard_normal((n_trials, n_times))
        x = np.zeros_like(z)
        y = np.zeros_like(z)
        x[:, 1:] = 0.8 * z[:, :-1]
        y[:, 2:] = 0.8 * z[:, :-2]
        x += 0.5 * rng.standard_normal(x.shape)
        y += 0.5 * rng.standard_normal(y.shape)

        without = granger(x, y, order=3)
        with_z = granger(x, y, order=3, Z=z)

        assert without.p_x_to_y < 1e-10
        assert without.x_to_y > 0.1
        assert with_z.p_x_to_y > 0.01
        assert with_z.x_to_y < 0.01
        assert with_z.params["n_conditioning"] == 1


class TestRowCodes:
    """The row codes behind transfer entropy's joint states number distinct rows in
    lexicographic order, the numbering `np.unique(axis=0)` gives."""

    @staticmethod
    def _reference(cols):
        return np.unique(np.column_stack(cols), axis=0, return_inverse=True)[1].ravel()

    def test_codes_equal_the_row_wise_unique_numbering(self):
        from jnwb.connectivity import _codes

        rng = np.random.default_rng(0)
        for _ in range(20):
            n_cols = int(rng.integers(2, 6))
            cols = [rng.integers(-3, int(rng.integers(1, 9)), size=3000) for _ in range(n_cols)]
            np.testing.assert_array_equal(_codes(cols), self._reference(cols))

    def test_codes_are_exact_when_the_radix_product_overflows_int64(self):
        from jnwb.connectivity import _codes

        rng = np.random.default_rng(1)
        wide = [rng.integers(0, 2**40, size=500, dtype=np.int64) for _ in range(2)]
        wide[0][:250] = wide[0][250:]  # repeated prefixes, so the second column orders them
        np.testing.assert_array_equal(_codes(wide), self._reference(wide))

    @pytest.mark.parametrize("dtype", [np.int8, np.int16])
    def test_codes_are_exact_for_narrow_signed_dtypes(self, dtype):
        """The shift to zero must not wrap: int8 100 - (-100) is 200, outside int8."""
        from jnwb.connectivity import _codes

        info = np.iinfo(dtype)
        cols = [np.array([-100, 100, 0, -100, 100], dtype=dtype),
                np.array([0, 1, 0, 1, 0], dtype=dtype)]
        np.testing.assert_array_equal(_codes(cols), self._reference(cols))
        rng = np.random.default_rng(2)
        cols = [rng.integers(info.min, info.max, size=2000, endpoint=True).astype(dtype)
                for _ in range(3)]
        np.testing.assert_array_equal(_codes(cols), self._reference(cols))

    def test_codes_are_exact_for_small_ranges_at_large_offsets(self):
        """Values near 2**61 (and 2**63 unsigned) with a range of four. Without the shift to
        zero, the key is the correct key plus a constant modulo 2**64; these offsets put that
        constant 11 below 2**63, so the keys would cross the int64 boundary and reorder."""
        from jnwb.connectivity import _codes

        rng = np.random.default_rng(3)
        for bases, dtype in (([2**61 - 1, 2**61, 5], np.int64),
                             ([2**63 + 2**61 - 1, 2**63 + 2**61, 5], np.uint64)):
            cols = [np.asarray(b, dtype=dtype) + rng.integers(0, 4, size=1000).astype(dtype)
                    for b in bases]
            np.testing.assert_array_equal(_codes(cols), self._reference(cols))



class TestPhaseSlopeIndex:
    def test_antisymmetric_under_swap(self):
        rng = np.random.default_rng(4)
        t = np.arange(0, 2, 1.0 / 1000.0)
        x = np.sin(2 * np.pi * 20 * t) + 0.1 * rng.standard_normal(len(t))
        lag_samples = 5
        y = np.roll(x, lag_samples)
        fwd = phase_slope_index(x, y, fs=1000.0, bands=(14, 30), nperseg=256)
        rev = phase_slope_index(y, x, fs=1000.0, bands=(14, 30), nperseg=256)
        assert fwd.net == pytest.approx(-rev.net, abs=1e-9)

    def test_multiband_psi_omnibus_pvalue(self):
        """Multi-band PSI computes omnibus top-level p-value rather than extracting first band (0.2.3-REV-08)."""
        from scipy import signal, stats
        rng = np.random.default_rng(42)
        n = 4000
        # Filtered band-limited signal in gamma (55-75 Hz) with 5 ms delay
        raw = rng.standard_normal(n)
        sos = signal.butter(4, [55.0, 75.0], btype="bandpass", fs=1000.0, output="sos")
        gamma_sig = signal.sosfiltfilt(sos, raw)
        x = gamma_sig + 0.05 * rng.standard_normal(n)
        y = np.roll(gamma_sig, 5) + 0.05 * rng.standard_normal(n)

        # Multi-band: theta (4-8 Hz, pure noise) and gamma (55-75 Hz, strong lead)
        bands = {"theta": (4.0, 8.0), "gamma": (55.0, 75.0)}
        res = phase_slope_index(x, y, fs=1000.0, bands=bands, n_surrogates=0)

        assert res.diagnostics["p_is_omnibus"] is True
        p_theta = float(2 * stats.norm.sf(abs(res.per_band["theta"]["z"])))
        p_gamma = float(2 * stats.norm.sf(abs(res.per_band["gamma"]["z"])))

        # Theta has no lead (p > 0.1), Gamma has massive lead (p < 1e-10)
        assert p_theta > 0.1
        assert p_gamma < 1e-10

        # Top-level p_x_to_y must NOT be equal to the first band (theta) p-value
        assert res.p_x_to_y != pytest.approx(p_theta, abs=1e-4)
        assert res.p_x_to_y < 0.05, f"Omnibus p must be significant, got {res.p_x_to_y}"



class TestTransferEntropy:
    def test_x_drives_y_gives_positive_x_to_y(self):
        rng = np.random.default_rng(5)
        n = 2000
        x = rng.integers(0, 4, n)
        y = np.zeros(n, dtype=int)
        y[1:] = x[:-1]
        result = transfer_entropy(x.astype(float), y.astype(float), k=1, l=1, delay=1,
                                   bins=4, n_surrogates=20, seed=0)
        assert isinstance(result, DirectedResult)

    def test_the_symbolic_estimator_is_refused_and_points_to_quantile(self):
        """06-202: two noisy copies of one white source tested significant both ways under
        it. The generic unknown-estimator error also names 'quantile', so the match
        requires the reason as well."""
        x = np.random.default_rng(0).normal(size=(2, 200))
        with pytest.raises(ValueError, match=r"not calibrated under zero-lag mixing.*"
                                             r"estimator='quantile'"):
            transfer_entropy(x[0], x[1], estimator="symbolic", n_surrogates=0)


def _zero_lag_pair(n, seed):
    """Two noisy copies of one white source: no directed coupling and no lead."""
    rng = np.random.default_rng(seed)
    s = rng.normal(size=n)
    return s + 0.5 * rng.normal(size=n), s + 0.5 * rng.normal(size=n)


class TestTransferEntropySurrogateComparesPlugInValues:
    """The Miller-Madow term differs between the observed table and a surrogate's, because a
    surrogate removes the zero-lag dependence and occupies more cells. Applied to both, it
    made the test reject two noisy copies of one white source in 0.11 of cases at bins 4 and
    0.37 at bins 8."""

    def test_the_p_does_not_depend_on_the_bias_correction(self):
        x, y = _zero_lag_pair(1000, 0)
        mm = transfer_entropy(x, y, bins=6, n_surrogates=49, rng=3)
        plug = transfer_entropy(x, y, bins=6, n_surrogates=49, rng=3, bias_correction=None)
        # The correction still reaches the estimate, or the identity below is vacuous.
        assert mm.x_to_y != pytest.approx(plug.x_to_y, abs=1e-6)
        assert mm.diagnostics["bias_corrected_x_to_y"] != pytest.approx(
            plug.diagnostics["bias_corrected_x_to_y"], abs=1e-6)
        assert (mm.p_x_to_y, mm.p_y_to_x, mm.p_net) == (plug.p_x_to_y, plug.p_y_to_x, plug.p_net)
        assert mm.diagnostics["surrogates"]["p_statistic"] == "plug_in"

    def test_zero_lag_mixing_at_a_large_state_space_is_not_rejected(self):
        """Pinned seeds: 15 of these 32 p-values fell below 0.05 when the surrogates carried
        the correction; none does now."""
        p = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for seed in range(16):
                x, y = _zero_lag_pair(2000, seed)
                res = transfer_entropy(x, y, bins=8, n_surrogates=49, rng=seed)
                p += [res.p_x_to_y, res.p_y_to_x]
        assert sum(v < 0.05 for v in p) <= 2, sorted(p)

    def test_a_directed_coupling_is_still_detected(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=2000)
        y = np.zeros(2000)
        y[1:] = 0.6 * x[:-1] + rng.normal(size=1999)
        res = transfer_entropy(x, y, n_surrogates=49, rng=0)
        assert res.p_x_to_y < 0.05 and res.p_y_to_x > 0.05


class TestPsiLeadPIsTheJackknife:
    """A shifted or re-paired Y removes every X-Y dependence, so a surrogate p tests coupling:
    under zero-lag mixing it rejected a lead that is not there in 0.46 of cases at nperseg 50."""

    def test_the_lead_p_is_unchanged_by_surrogates_and_the_coupling_p_has_its_own_key(self):
        x, y = _zero_lag_pair(2000, 0)
        plain = phase_slope_index(x, y, fs=1000.0, bands=(5.0, 100.0), nperseg=50)
        both = phase_slope_index(x, y, fs=1000.0, bands=(5.0, 100.0), nperseg=50,
                                 n_surrogates=49, rng=0)
        assert both.p_net == plain.p_net == both.p_x_to_y == both.p_y_to_x
        assert both.diagnostics["p_source"] == "jackknife_z"
        assert plain.diagnostics["p_coupling_surrogate"] is None
        coupling = both.diagnostics["p_coupling_surrogate"]
        assert coupling == both.per_band["band"]["p_surrogate"] and coupling != both.p_net

    def test_a_multi_band_lead_p_is_the_omnibus_jackknife_whether_or_not_surrogates_run(self):
        x, y = _zero_lag_pair(2000, 0)
        bands = {"a": (5.0, 40.0), "b": (45.0, 100.0)}
        plain = phase_slope_index(x, y, fs=1000.0, nperseg=50, bands=bands)
        both = phase_slope_index(x, y, fs=1000.0, nperseg=50, bands=bands,
                                 n_surrogates=49, rng=0)
        assert plain.diagnostics["p_is_omnibus"] and plain.p_net is not None
        assert both.p_net == plain.p_net == both.p_x_to_y == both.p_y_to_x
        assert both.diagnostics["p_source"] == "jackknife_z"
        assert both.diagnostics["p_coupling_surrogate"] is not None
        assert both.p_net != both.diagnostics["p_coupling_surrogate"]

    def test_without_the_jackknife_there_is_no_lead_p(self):
        x, y = _zero_lag_pair(2000, 0)
        res = phase_slope_index(x, y, fs=1000.0, nperseg=50, n_surrogates=49, rng=0,
                                jackknife=False, bands={"a": (5.0, 40.0), "b": (45.0, 100.0)})
        assert res.p_net is None and res.p_x_to_y is None and res.p_y_to_x is None
        assert res.diagnostics["p_source"] is None
        assert 0.0 < res.diagnostics["p_coupling_surrogate"] <= 1.0

    def test_zero_lag_mixing_is_not_read_as_a_lead(self):
        """Pinned seeds: 9 of these 20 p_net values fell below 0.05 when p_net was the
        surrogate p; none does now."""
        p = []
        for seed in range(20):
            x, y = _zero_lag_pair(2000, seed)
            p.append(phase_slope_index(x, y, fs=1000.0, bands=(5.0, 100.0), nperseg=50,
                                       n_surrogates=49, rng=seed).p_net)
        assert sum(v < 0.05 for v in p) <= 2, sorted(p)


class TestDirectedConnectivityAndNetwork:
    def test_directed_connectivity_dispatches_by_method(self):
        rng = np.random.default_rng(6)
        x = rng.standard_normal((10, 200))
        y = rng.standard_normal((10, 200))
        result = directed_connectivity(x, y, method="granger", order=2)
        assert isinstance(result, DirectedResult)

    def test_directed_network_returns_all_pairs(self):
        rng = np.random.default_rng(7)
        signals = {
            "A": rng.standard_normal((5, 100)),
            "B": rng.standard_normal((5, 100)),
            "C": rng.standard_normal((5, 100)),
        }
        result = directed_network(signals, method="granger", order=2, fdr=False)
        assert "labels" in result
        assert set(result["labels"]) == {"A", "B", "C"}

    def test_directed_network_draws_a_generator_once_per_pair_up_front(self):
        """06-203: a Generator copied into each worker would replay one stream, so the
        surrogates would depend on n_jobs. Each pair gets an int seed drawn before any
        worker starts, in pair order, and records it."""
        rng = np.random.default_rng(8)
        signals = {k: rng.standard_normal((3, 120)) for k in "ABC"}
        res = directed_network(signals, method="granger", order=1, n_surrogates=5,
                               fdr=False, rng=np.random.default_rng(3))
        recorded = [r.params["surrogate_seed_entropy"] for r in res["results"].values()]
        assert recorded == np.random.default_rng(3).integers(0, 2**63 - 1, size=3).tolist()

    def test_directed_network_refuses_two_different_generators(self):
        """`granger(rng=a, seed=b)` raises; the network must not hide the contradiction by
        drawing its per-pair seeds from one of them."""
        rng = np.random.default_rng(8)
        signals = {k: rng.standard_normal((3, 120)) for k in "AB"}
        with pytest.raises(ValueError, match="Conflicting values provided to directed_network"):
            directed_network(signals, method="granger", order=1, n_surrogates=5,
                             rng=np.random.default_rng(1), seed=np.random.default_rng(2))

    @pytest.mark.parametrize("given, parent", [({"rng": 7}, 7), ({"seed": 7}, 7), ({}, 0)])
    def test_an_int_seed_gives_each_pair_its_own_child_seed(self, given, parent):
        """IB-45, ruled 2026-10-06: an int seed, the default 0 included, reached every pair
        unchanged, so every pair drew the same surrogate stream."""
        rng = np.random.default_rng(8)
        signals = {k: rng.standard_normal((3, 120)) for k in "ABC"}
        res = directed_network(signals, method="granger", order=1, n_surrogates=5,
                               fdr=False, **given)
        expected = np.random.default_rng(parent).integers(0, 2**63 - 1, size=3).tolist()
        assert list(res["pair_seeds"].values()) == expected
        assert len(set(expected)) == 3
        recorded = [r.params["surrogate_seed_entropy"] for r in res["results"].values()]
        assert recorded == expected

    def test_a_none_seed_records_the_entropy_each_pair_drew(self):
        rng = np.random.default_rng(8)
        signals = {k: rng.standard_normal((3, 120)) for k in "ABC"}
        res = directed_network(signals, method="granger", order=1, n_surrogates=5,
                               fdr=False, rng=None)
        recorded = [r.params["surrogate_seed_entropy"] for r in res["results"].values()]
        assert list(res["pair_seeds"].values()) == recorded and len(set(recorded)) == 3


class TestConditionalDirectedNetwork:
    """Ruled 2026-10-06: Granger conditions each pair on every other node through `Z`; the
    other methods stay pairwise."""

    @staticmethod
    def _chain(n=3000, seed=11):
        """A -> B -> C at one-sample lags and no direct A -> C term."""
        rng = np.random.default_rng(seed)
        a, b, c = rng.normal(size=(3, n))
        for t in range(1, n):
            b[t] += 0.8 * a[t - 1]
            c[t] += 0.8 * b[t - 1]
        return {"A": a, "B": b, "C": c}

    def test_a_chain_has_no_direct_edge_once_conditioned(self):
        signals = self._chain()
        kw = dict(method="granger", order=2, fdr=False)
        pairwise = directed_network(signals, **kw)
        given = directed_network(signals, conditional=True, **kw)
        a, b, c = 0, 1, 2
        assert pairwise["p_matrix"][a, c] < 1e-10, "the indirect path must show pairwise"
        assert given["p_matrix"][a, c] > 0.05
        assert given["p_matrix"][a, b] < 1e-10 and given["p_matrix"][b, c] < 1e-10
        assert given["conditional"] is True and pairwise["conditional"] is False
        assert given["results"][("A", "C")].params["n_conditioning"] == 1
        assert pairwise["results"][("A", "C")].params["n_conditioning"] == 0

    @pytest.mark.parametrize("method", ["psi", "te", "granger_spectral"])
    def test_other_methods_stay_pairwise(self, method):
        with pytest.raises(ValueError, match="conditions Granger only"):
            directed_network(self._chain(n=200), method=method, conditional=True, fs=1000.0)

    def test_z_and_conditional_together_are_refused(self):
        signals = self._chain(n=200)
        with pytest.raises(ValueError, match="do not pass Z as well"):
            directed_network(signals, conditional=True, Z=signals["A"], order=1)


class TestFewTrialSurrogates:
    """Below 7 trials the surrogates circularly shift each trial instead of re-pairing
    trials: 3 trials admit 2 derangements, so the re-pairing null held two values and
    independent noise tested significant at 0.05 in 30 of 80 p-values here (bc04a791)."""

    def test_independent_noise_at_three_trials_rejects_near_alpha(self):
        ps = []
        for rep in range(40):
            g = np.random.default_rng(rep)
            x, y = g.normal(size=(3, 200)), g.normal(size=(3, 200))
            res = granger(x, y, order=1, n_surrogates=19, rng=rep)
            ps += [res.p_x_to_y, res.p_y_to_x]
        assert np.mean(np.asarray(ps) <= 0.05) <= 0.08

    @pytest.mark.parametrize("n_trials,scheme", [(6, "circular_shift"), (7, "trial_permutation")])
    def test_every_surrogate_consumer_records_the_scheme(self, n_trials, scheme):
        g = np.random.default_rng(0)
        x, y = g.normal(size=(n_trials, 128)), g.normal(size=(n_trials, 128))
        for res in (
            granger(x, y, order=1, n_surrogates=2),
            granger_spectral(x, y, fs=100.0, order=1, n_freqs=16, n_surrogates=2),
            phase_slope_index(x, y, fs=100.0, bands=(5.0, 30.0), n_surrogates=2),
            transfer_entropy(x, y, n_surrogates=2),
        ):
            assert res.params["surrogate_scheme"] == scheme, res.method
        assert granger(x, y, order=1).params["surrogate_scheme"] is None

    def test_seven_trials_keep_the_null_they_had(self):
        """Pinned before the threshold moved from 3 to 7. The means differ across BLAS builds
        in the last bits, so they are compared to 1e-12; another null differs far more."""
        g = np.random.default_rng(11)
        x = g.normal(size=(7, 200))
        y = 0.3 * np.roll(x, 1, axis=1) + g.normal(size=(7, 200))
        res = granger(x, y, order=1, n_surrogates=19, rng=0)
        sur = res.diagnostics["surrogates"]
        assert (res.p_x_to_y, res.p_y_to_x, res.p_net) == (0.05, 0.7, 0.05)
        np.testing.assert_allclose(
            [sur["null_mean_x_to_y"], sur["null_mean_y_to_x"]],
            [0.00035468224425054724, 0.0006370039765307248], rtol=1e-12, atol=0,
        )

    @pytest.mark.parametrize("n_trials", [1, 2, 3, 4, 5, 6])
    def test_below_seven_trials_each_surrogate_trial_is_its_own_trial_shifted(
        self, n_trials, monkeypatch
    ):
        """The recorded scheme and the 3-trial rate cannot see a surrogate that still
        re-pairs trials at 4-6 while reporting 'circular_shift'. Every surrogate row must be
        a nonzero roll of the same input row."""
        import jnwb.connectivity as conn

        seen = []
        real = conn._surrogate_source

        def spy(a, rng):
            out = real(a, rng)
            seen.append((a.copy(), out))
            return out

        # patched where granger looks the name up
        monkeypatch.setattr(inspect.getmodule(conn.granger), "_surrogate_source", spy)
        g = np.random.default_rng(n_trials)
        x, y = g.normal(size=(n_trials, 60)), g.normal(size=(n_trials, 60))
        granger(x, y, order=1, n_surrogates=3, rng=0)
        assert len(seen) == 6  # 3 surrogates, both directions
        for a, out in seen:
            for i in range(n_trials):
                assert any(np.array_equal(out[i], np.roll(a[i], s)) for s in range(1, 60)), (
                    f"surrogate trial {i} of {n_trials} is not trial {i} shifted"
                )


class TestCrossAreaCoherenceContract:
    """0.2.4-09: out-of-contract input must fail loudly, not plausibly.

    Both cases below previously produced a result a caller could not distinguish from a
    real measurement, or an error naming neither the argument nor the contract.
    """

    def _bands(self):
        return {"beta": (15.0, 30.0)}

    @pytest.mark.parametrize("shape", [(6, 2048), (2, 2048), (1, 2048), (3, 512)])
    def test_two_dimensional_input_is_rejected(self, shape):
        rng = np.random.default_rng(0)
        a = rng.normal(size=shape)
        b = rng.normal(size=shape)
        with pytest.raises(ValueError, match=r"must be a 1-D time series"):
            jnwb.cross_area_coherence(
                a, b, fs=1000.0, freq_bands=self._bands(), n_surrogates=3
            )

    def test_rejection_names_the_offending_argument_and_shape(self):
        rng = np.random.default_rng(0)
        good = rng.normal(size=1024)
        bad = rng.normal(size=(4, 1024))
        with pytest.raises(ValueError) as excinfo:
            jnwb.cross_area_coherence(
                good, bad, fs=1000.0, freq_bands=self._bands(), n_surrogates=3
            )
        message = str(excinfo.value)
        assert "lfp_area2" in message
        assert "(4, 1024)" in message

    def test_one_dimensional_paired_input_still_computes(self):
        rng = np.random.default_rng(0)
        a = rng.normal(size=4096)
        b = rng.normal(size=4096)
        out = jnwb.cross_area_coherence(
            a, b, fs=1000.0, freq_bands=self._bands(), n_surrogates=5
        )
        assert np.asarray(out["coherence_spectrum"]).ndim == 1
        assert np.asarray(out["frequencies"]).size == np.asarray(out["coherence_spectrum"]).size
        # Bounded in [0, 1]; the upper compare carries float slack because the
        # estimator can land exactly on 1.0 (see the segment-count caveat below).
        assert 0.0 <= out["peak_coherence_value"] <= 1.0 + 1e-9


class TestStationarityDiagnosticIsCalibrated:
    """`_adf_pvalue` drives `stationarity_ok` and `ok_for_interpretation` on every Granger
    result, so a miscalibrated one silently certifies non-stationary series as safe.

    It used to compare the Dickey-Fuller t-statistic to the normal distribution. The DF
    null is shifted well to the left (5% critical value near -2.86 with a constant, not
    -1.645), so it certified roughly 46-48% of pure random walks as stationary while its
    docstring called itself conservative.
    """

    def test_random_walks_are_not_certified_stationary(self):
        from jnwb.connectivity import _adf_pvalue

        rng = np.random.default_rng(0)
        for n in (200, 500):
            p = np.array([_adf_pvalue(np.cumsum(rng.standard_normal(n))) for _ in range(600)])
            rate = float(np.mean(p <= 0.05))
            assert rate <= 0.10, (
                f"n={n}: {rate:.3f} of pure random walks certified stationary; a calibrated "
                f"test rejects the unit root about 5% of the time under H0"
            )

    def test_a_stationary_series_is_still_detected(self):
        """The repair must not buy calibration by refusing to reject anything."""
        from jnwb.connectivity import _adf_pvalue

        rng = np.random.default_rng(1)
        hits = 0
        for _ in range(100):
            e = rng.standard_normal(500)
            y = np.zeros(500)
            for t in range(1, 500):
                y[t] = 0.5 * y[t - 1] + e[t]
            hits += _adf_pvalue(y) <= 0.05
        assert hits >= 90, f"only {hits}/100 stationary AR(1) series rejected the unit root"

    def test_degenerate_series_report_nan_rather_than_a_number(self):
        from jnwb.connectivity import _adf_pvalue

        assert np.isnan(_adf_pvalue(np.arange(5.0)))
        assert np.isnan(_adf_pvalue(np.ones(100)))


class TestTransferEntropyReportsDegenerateDiscretization:
    """The undersampling check could not see the opposite failure. A discretization that
    collapses produces FEWER joint states, so samples_per_joint_state goes UP and the check
    stays quiet. Quantile edges on a sparse series are the common case: spike counts
    averaging 0.05-0.1 per bin are almost all zero, so every quantile edge lands on 0 and
    the series maps to a single symbol. TE is then identically 0 by construction, and it
    was reported as 0.0000 bits, p = 1.0, ok_for_interpretation=True, no warnings -- on
    data where X drives Y at lag 1.
    """

    @staticmethod
    def _coupled(rate, n=2000, seed=0):
        rng = np.random.default_rng(seed)
        x = rng.poisson(rate, size=n).astype(float)
        y = np.zeros_like(x)
        y[1:] = x[:-1] + rng.poisson(rate, size=n - 1)
        return x, y

    @pytest.mark.parametrize("rate", [0.05, 0.1])
    def test_a_collapsed_discretization_is_not_certified_interpretable(self, rate):
        res = transfer_entropy(*self._coupled(rate), n_surrogates=50)
        d = res.diagnostics
        assert res.x_to_y == 0.0
        assert d["n_realized_states_x"] == 1 and d["n_realized_states_y"] == 1
        assert d["ok_for_interpretation"] is False
        assert any("degenerate_discretization" in w for w in d["warnings"])

    def test_a_partially_collapsed_discretization_is_flagged(self):
        res = transfer_entropy(*self._coupled(0.3), n_surrogates=50)
        d = res.diagnostics
        assert d["n_realized_states_x"] < 4
        assert any("discretization_collapsed" in w for w in d["warnings"])
        assert d["ok_for_interpretation"] is False

    def test_a_well_sampled_signal_is_still_clean(self):
        res = transfer_entropy(*self._coupled(5.0), n_surrogates=50)
        d = res.diagnostics
        assert d["n_realized_states_x"] == 4 and d["warnings"] == []
        assert d["ok_for_interpretation"] is True

    def test_the_discrete_estimator_recovers_the_coupling_on_sparse_counts(self):
        """The documented route for integer spike counts still works on the same data the
        quantile estimator cannot represent."""
        x, y = self._coupled(0.1)
        res = transfer_entropy(x.astype(int), y.astype(int), estimator="discrete", n_surrogates=50)
        assert res.x_to_y > 0.1
        assert res.p_x_to_y < 0.05
        assert res.diagnostics["ok_for_interpretation"] is True


@pytest.mark.parametrize("criterion", ["aic", "bic", "hqic"])
def test_select_optimal_lag_scores_every_order_on_granger_common_sample(criterion):
    """Each order was scored on its own n - p targets; on these 60-sample pairs that picked
    another order than the common-sample criteria of `granger` in about a quarter of cases."""
    from jnwb.connectivity import _granger_order_criteria, select_optimal_lag

    n, max_lag = 60, 10
    cap = min(max_lag, (n - 2) // 3)
    for s in range(40):
        e = np.random.default_rng(s).normal(size=(2, n))
        x, y = np.zeros(n), np.zeros(n)
        for t in range(2, n):
            x[t] = 0.3 * x[t - 1] + 0.2 * x[t - 2] + 0.3 * y[t - 1] + e[0, t]
            y[t] = 0.4 * y[t - 1] + e[1, t]
        scores = _granger_order_criteria(y[None], x[None], [], cap, 0.0, criterion)
        assert select_optimal_lag(x, y, max_lag=max_lag, criterion=criterion) == \
            int(np.argmin(scores)) + 1, f"seed {s}"


class TestCrossModalLagSearchPaysForItself:
    """`cross_modal_comparison` reported the p at the max-|r| lag without correcting for
    the search, so on independent white noise over 101 lags it called 99.5% of runs
    significant. It also swept a symmetric +-min(|lo|, |hi|) window, so (0, 500) searched
    nothing at all and (100, 500) searched +-100 ms.
    """

    @staticmethod
    def _independent(n=600, seed=0):
        rng = np.random.default_rng(seed)
        return rng.standard_normal(n), rng.standard_normal(n)

    def test_the_corrected_p_is_not_the_uncorrected_one(self):
        from jnwb.statistics import cross_modal_comparison

        x, y = self._independent()
        res = cross_modal_comparison(x, y, bin_ms=10.0, n_permutations=200, seed=0)
        assert res["n_lags_searched"] == 101
        assert res["lag_corrected_pvalue"] > res["uncorrected_pvalue"]

    @pytest.mark.parametrize(
        "lag_range,expected_lags,lo,hi",
        [((-500, 500), 101, -500.0, 500.0), ((-500, 100), 61, -500.0, 100.0),
         ((0, 500), 51, 0.0, 500.0), ((100, 500), 41, 100.0, 500.0)],
    )
    def test_every_searched_lag_lies_inside_the_request(self, lag_range, expected_lags, lo, hi):
        from jnwb.statistics import cross_modal_comparison

        x, y = self._independent()
        res = cross_modal_comparison(
            x, y, lag_range_ms=lag_range, bin_ms=10.0, n_permutations=20, seed=0
        )
        assert res["n_lags_searched"] == expected_lags
        assert lo <= res["lag_ms"] <= hi

    def test_a_real_lagged_coupling_is_recovered_when_the_series_is_long_enough(self):
        from jnwb.statistics import cross_modal_comparison

        rng = np.random.default_rng(0)
        x = rng.standard_normal(4000)
        y = 0.5 * np.roll(x, 20) + rng.standard_normal(4000)
        res = cross_modal_comparison(x, y, bin_ms=10.0, n_permutations=200, seed=0)
        assert res["lag_ms"] == pytest.approx(-200.0)
        assert res["lag_corrected_pvalue"] < 0.05
        assert res["warnings"] == []

    def test_a_lag_window_too_wide_for_the_series_is_flagged(self):
        """The corrected p cannot resolve below about n_lags / n_samples, so a short series
        with a wide lag window cannot reach 0.05 however strong the coupling is."""
        from jnwb.statistics import cross_modal_comparison

        x, y = self._independent(n=600)
        res = cross_modal_comparison(x, y, bin_ms=10.0, n_permutations=100, seed=0)
        assert res["lag_search_resolution_floor"] == pytest.approx(101 / 600)
        assert any("lag_window_too_wide" in w for w in res["warnings"])

    @pytest.mark.parametrize("rng", [None, 3, "generator"])
    def test_the_recorded_seed_reproduces_the_corrected_p(self, rng):
        """The result names the seed its null ran on, so it alone reproduces the p."""
        from jnwb.statistics import cross_modal_comparison

        x, y = self._independent()
        given = np.random.default_rng(11) if rng == "generator" else rng
        first = cross_modal_comparison(x, y, bin_ms=10.0, n_permutations=60, rng=given)
        seed = first["surrogate_seed_entropy"]
        assert isinstance(seed, int)
        if rng == 3:
            assert seed == 3
        if rng == "generator":
            assert seed == int(np.random.default_rng(11).integers(0, 2**63 - 1))
        again = cross_modal_comparison(x, y, bin_ms=10.0, n_permutations=60, rng=seed)
        assert again["lag_corrected_pvalue"] == first["lag_corrected_pvalue"]
        assert again["surrogate_seed_entropy"] == seed

    def test_no_seed_is_recorded_without_a_sweep(self):
        from jnwb.statistics import cross_modal_comparison

        x, y = self._independent()
        assert cross_modal_comparison(x, y, rng=3)["surrogate_seed_entropy"] is None


class TestPsiInferenceIsNotOverstated:
    """A 10-segment jackknife reported p = 0.0, and overlapping bands were summed
    twice into the headline estimate."""

    @staticmethod
    def _lagged_pair(n=6000, lag=10, seed=0):
        rng = np.random.default_rng(seed)
        base = rng.normal(size=n)
        return base, np.roll(base, lag) + 0.5 * rng.normal(size=n)

    def test_the_jackknife_p_reflects_the_segment_count(self):
        """`2 * norm.sf(|z|)` gave exactly 0.0 -- a p no 10-segment jackknife can support."""
        x, y = self._lagged_pair()
        res = phase_slope_index(x, y, fs=1000.0, nperseg=1024)
        assert res.diagnostics["p_source"] == "jackknife_z"
        assert res.p_net > 0.0, "a finite jackknife cannot support p = 0"
        n_seg = res.diagnostics["n_segments"]
        z = res.per_band["full"]["z"]
        expected = float(2 * stats.t.sf(abs(z), df=max(n_seg - 1, 1)))
        assert res.p_net == pytest.approx(expected, rel=1e-9)

    def test_fewer_segments_give_a_larger_p_for_the_same_z(self):
        """The Gaussian tail did not respond to the segment count at all."""
        z = 3.2876
        p_small = float(2 * stats.t.sf(z, df=5))
        p_large = float(2 * stats.t.sf(z, df=200))
        p_gauss = float(2 * stats.norm.sf(z))
        assert p_small > p_large > p_gauss

    def test_duplicate_bands_warn_instead_of_doubling_the_estimate(self):
        """{'a': (14, 30), 'b': (14, 30)} returned exactly 2x {'beta': (14, 30)}."""
        x, y = self._lagged_pair()
        single = phase_slope_index(x, y, fs=1000.0, nperseg=1024, bands={"beta": (14.0, 30.0)})
        with pytest.warns(RuntimeWarning, match="bands overlap"):
            doubled = phase_slope_index(
                x, y, fs=1000.0, nperseg=1024, bands={"a": (14.0, 30.0), "b": (14.0, 30.0)}
            )
        assert doubled.net == pytest.approx(2.0 * single.net, rel=1e-9)
        assert any("overlapping_bands" in w for w in doubled.diagnostics["warnings"])

    def test_partially_overlapping_bands_also_warn(self):
        x, y = self._lagged_pair()
        with pytest.warns(RuntimeWarning, match="bands overlap"):
            phase_slope_index(
                x, y, fs=1000.0, nperseg=1024, bands={"a": (14.0, 30.0), "b": (25.0, 40.0)}
            )

    def test_disjoint_bands_do_not_warn(self):
        x, y = self._lagged_pair()
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            # One trial: the segment-jackknife warning is expected and is not about bands.
            warnings.filterwarnings("ignore", message=".*leaves out one Welch segment")
            res = phase_slope_index(
                x, y, fs=1000.0, nperseg=1024, bands={"beta": (14.0, 30.0), "gamma": (35.0, 50.0)}
            )
        assert not any("overlapping_bands" in w for w in res.diagnostics["warnings"])

    def test_the_sign_convention_is_unchanged(self):
        """Antisymmetry and direction were verified correct against Nolte et al. 2008."""
        x, y = self._lagged_pair()
        fwd = phase_slope_index(x, y, fs=1000.0, nperseg=1024)
        rev = phase_slope_index(y, x, fs=1000.0, nperseg=1024)
        assert fwd.net == pytest.approx(-rev.net, rel=1e-9)
        assert fwd.net > 0.0

    def test_the_returned_spectrum_carries_the_same_sign_as_net(self):
        """The spectrum is public and plotted; summed over the band's adjacent-bin pairs it is
        the band estimate itself, so its sign is pinned by the headline value."""
        x, y = self._lagged_pair()
        fwd = phase_slope_index(x, y, fs=1000.0, nperseg=1024)
        rev = phase_slope_index(y, x, fs=1000.0, nperseg=1024)
        freqs = fwd.spectrum["freqs"]
        lo, hi = fwd.per_band["full"]["band_hz"]
        idx = np.flatnonzero((freqs >= lo) & (freqs <= hi))
        in_band = fwd.spectrum["psi_per_freq"][idx[:-1]].sum()
        assert in_band == pytest.approx(fwd.net, rel=1e-9)
        np.testing.assert_allclose(
            fwd.spectrum["psi_per_freq"], -rev.spectrum["psi_per_freq"], atol=1e-12)

    @staticmethod
    def _periodic(n=1024, period=32, seed=1):
        """Period 32 with nperseg 64 and hop 32: every Welch segment is the same segment."""
        return np.random.default_rng(seed).normal(size=period)[np.arange(n) % period]

    @pytest.mark.parametrize("bands", [None, {"a": (5.0, 20.0), "b": (20.0, 45.0)}])
    def test_a_jackknife_without_spread_has_no_z(self, bands):
        """Y equal to a periodic X made every replicate agree to rounding: sd was 8e-32, z
        -7.8e13, p 0.0 and ok_for_interpretation True."""
        x = self._periodic()
        with pytest.warns(RuntimeWarning, match="agree to rounding"):
            res = phase_slope_index(x, x.copy(), fs=100.0, nperseg=64, bands=bands)
        assert res.diagnostics["n_segments"] >= 8
        assert all(np.isnan(b["z"]) for b in res.per_band.values())
        assert res.p_net is None
        assert res.diagnostics["ok_for_interpretation"] is False
        assert any("jackknife_spread_is_round_off" in w for w in res.diagnostics["warnings"])

    def test_the_width_sits_between_round_off_and_a_part_in_1e9(self):
        """Y equal to aperiodic noise leaves replicates that differ by round-off alone (sd
        3.9e-18, the largest measured, against a width of 4.7e-12); a variation of one part
        in 1e9 gives sd 1.1e-10 and keeps its z."""
        from jnwb.connectivity._psi import _psi_round_off

        rng = np.random.default_rng(0)
        x = rng.normal(size=1024)
        with pytest.warns(RuntimeWarning, match="agree to rounding"):
            same = phase_slope_index(x, x.copy(), fs=100.0, nperseg=64)
        assert np.isnan(same.per_band["full"]["z"])
        perturbed = x + 1e-9 * rng.normal(size=1024)
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            warnings.filterwarnings("ignore", message=".*leaves out one Welch segment")
            res = phase_slope_index(x, perturbed, fs=100.0, nperseg=64)
        assert np.isfinite(res.per_band["full"]["z"])
        # Both sides of the width: above the largest measured round-off, below the spread.
        width = _psi_round_off(31, 31, 31)
        assert res.params["n_segments"] == 31 and res.per_band["full"]["n_freq_bins"] == 32
        assert 1e3 * 3.9e-18 < width < res.per_band["full"]["sd"] / 10

    def test_a_jackknife_with_spread_keeps_its_z(self):
        """The guard sits at rounding: an ordinary lagged pair keeps a finite z and no warning."""
        x, y = self._lagged_pair()
        res = phase_slope_index(x, y, fs=1000.0, nperseg=1024)
        assert np.isfinite(res.per_band["full"]["z"])
        assert not any("round_off" in w for w in res.diagnostics["warnings"])


class TestGrangerNotTestedIsNotPassed:
    """An untested assumption and a degenerate fit were both reported as
    interpretable results."""

    @staticmethod
    def _random_walks():
        rng = np.random.default_rng(0)
        return np.cumsum(rng.normal(size=800)), np.cumsum(rng.normal(size=800))

    def test_a_missing_statsmodels_raises_instead_of_reading_as_untested(self, monkeypatch):
        """`statsmodels` is a declared dependency, so its absence is a broken install, not a
        series the test could not run on. `_adf_pvalue` turned the ImportError into NaN, and
        every Granger diagnostic then read "stationarity_not_tested" with no error."""
        import sys

        from jnwb.connectivity import _adf_pvalue

        a, b = self._random_walks()
        # None in sys.modules makes `from statsmodels.tsa.stattools import ...` raise
        # ImportError; monkeypatch puts the real module back afterwards.
        monkeypatch.setitem(sys.modules, "statsmodels.tsa.stattools", None)
        with pytest.raises(ImportError):
            _adf_pvalue(a)
        with pytest.raises(ImportError):
            _adf_pvalue(np.arange(5.0))
        with pytest.raises(ImportError):
            granger(a, b, order=3)
        with warnings.catch_warnings(), pytest.raises(ImportError):
            warnings.simplefilter("ignore", DeprecationWarning)
            granger_causality(a, b, order=3)

    @pytest.mark.parametrize("failure", [np.linalg.LinAlgError("SVD did not converge"),
                                         ValueError("Invalid input, x is constant")])
    def test_a_numerical_failure_is_nan_and_reported_untested(self, monkeypatch, failure):
        """A fit that cannot run on the series stays NaN, and NaN is not a pass: two pure
        random walks once came back ok_for_interpretation=True with an empty warnings list."""
        from jnwb.connectivity import _adf_pvalue

        def singular(*args, **kwargs):
            raise failure

        a, b = self._random_walks()
        monkeypatch.setattr("statsmodels.tsa.stattools.adfuller", singular)
        assert np.isnan(_adf_pvalue(a))
        d = granger(a, b, order=3).diagnostics
        assert d["ok_for_interpretation"] is False
        assert "stationarity_not_tested" in d["warnings"]

    def test_a_floating_point_error_under_strict_errstate_is_nan_and_untested(self):
        """Under a caller's ``np.errstate(all="raise")`` the fit underflows on a series of
        amplitude 1e-300 and raised FloatingPointError, where 0.2.8 returned NaN. The series
        is finite and not constant, so it reaches the fit rather than an early NaN return."""
        from jnwb.connectivity import _adf_pvalue, _series_diagnostics

        y = 1e-300 * np.random.default_rng(12345).normal(size=50)
        assert np.all(np.isfinite(y)) and np.ptp(y) > 0
        with np.errstate(all="raise"):
            assert np.isnan(_adf_pvalue(y))
            d = _series_diagnostics(y, np.random.default_rng(0).normal(size=50), order=3)
        assert np.isnan(d["adf_pvalue"])
        assert "stationarity_not_tested" in d["warnings"]
        assert d["stationarity_ok"] is False

    def test_an_error_that_is_not_numerical_propagates(self, monkeypatch):
        """Only the named numerical failures become NaN; a defect in the call raises."""
        from jnwb.connectivity import _adf_pvalue

        def broken(*args, **kwargs):
            raise TypeError("adfuller() got an unexpected keyword argument")

        monkeypatch.setattr("statsmodels.tsa.stattools.adfuller", broken)
        with pytest.raises(TypeError, match="unexpected keyword"):
            _adf_pvalue(self._random_walks()[0])

    def test_a_tested_and_passing_series_is_still_interpretable(self):
        rng = np.random.default_rng(1)
        g = granger(rng.normal(size=800), rng.normal(size=800), order=3)
        assert g.diagnostics["warnings"] == []
        assert g.diagnostics["ok_for_interpretation"] is True

    def test_a_degenerate_fit_is_not_a_measured_zero(self):
        """granger(ones, ones) returned x_to_y = y_to_x = 0.0 with an empty warnings list
        and ok_for_interpretation=True, while transfer_entropy warns on the same input."""
        constant = np.ones(800)
        g = granger(constant, constant, order=3)
        assert np.isnan(g.x_to_y)
        assert np.isnan(g.y_to_x)
        assert any("degenerate" in w for w in g.diagnostics["warnings"])
        assert g.diagnostics["ok_for_interpretation"] is False

    def test_the_degenerate_verdict_matches_its_siblings(self):
        constant = np.ones(800)
        g = granger(constant, constant, order=3)
        te = transfer_entropy(constant, constant)
        assert g.diagnostics["ok_for_interpretation"] == te.diagnostics["ok_for_interpretation"] is False


class TestDirectedEstimatorEdges:
    """Item 10-06: the PSI segment default, its pinned spectrum, the partial-band `net`, the
    silent all-NaN q_matrix and the mutual-information error names."""

    @pytest.mark.parametrize("shape, nperseg, n_segments", [
        ((2000,), 190, 20),       # n_times // 4 = 500 left 7 segments
        ((10, 400), 100, 70),     # n_times // 4 already leaves 70: unchanged
        ((100,), 16, 11),         # the 16-sample floor wins over the segment count
    ])
    def test_the_default_segment_count(self, shape, nperseg, n_segments):
        """D10(c), ruled 2026-09-29: the default leaves at least about 20 segments."""
        rng = np.random.default_rng(0)
        res = phase_slope_index(rng.normal(size=shape), rng.normal(size=shape), fs=1000.0)
        assert (res.params["nperseg"], res.params["n_segments"]) == (nperseg, n_segments)

    def test_psi_freqs_and_the_first_term_are_pinned(self):
        """P-196: `psi_freqs` and `psi_per_freq` were returned and never checked. The first
        term is recomputed here from eq. 3 of Nolte et al. (2008) on the same segments."""
        rng = np.random.default_rng(3)
        x = rng.normal(size=640)
        y = np.roll(x, 2) + 0.5 * rng.normal(size=640)
        res = phase_slope_index(x, y, fs=100.0, nperseg=64)
        np.testing.assert_array_equal(res.spectrum["psi_freqs"],
                                      (np.arange(32) + 0.5) * 100.0 / 64)

        def spectra(a):
            a = a - a.mean()
            seg = np.stack([a[s:s + 64] for s in range(0, 640 - 64 + 1, 32)])
            return np.fft.rfft((seg - seg.mean(axis=1, keepdims=True)) * np.hanning(64), axis=1)

        fx, fy = spectra(x), spectra(y)
        c = np.mean(fx * np.conj(fy), axis=0) / np.sqrt(
            np.mean(np.abs(fx) ** 2, axis=0) * np.mean(np.abs(fy) ** 2, axis=0))
        assert res.spectrum["psi_per_freq"].shape == (32,)
        assert res.spectrum["psi_per_freq"][0] == pytest.approx(
            np.imag(np.conj(c[0]) * c[1]), rel=1e-12, abs=1e-15)
        assert res.spectrum["psi_per_freq"][0] != 0.0

    def test_net_sums_only_the_bands_with_a_slope(self):
        """P-264: a band with fewer than two bins is left out of `net`, as the docstring
        says, not counted as zero or as NaN."""
        rng = np.random.default_rng(0)
        x = rng.normal(size=2000)
        y = np.roll(x, 5) + rng.normal(size=2000)
        res = phase_slope_index(x, y, fs=1000.0, nperseg=200,
                                bands={"beta": (14.0, 30.0), "tiny": (20.5, 21.0)})
        assert np.isnan(res.per_band["tiny"]["value"])
        assert res.net == res.per_band["beta"]["value"]
        assert res.diagnostics["ok_for_interpretation"] is False
        assert "sums those bands alone" in " ".join(phase_slope_index.__doc__.split())

    def test_fdr_with_no_p_value_warns(self):
        """The all-NaN q_matrix of PSI with jackknife=False came back without a word."""
        sig = np.random.default_rng(0).normal(size=(3, 1000))
        with pytest.warns(RuntimeWarning, match="no pair returned a p-value"):
            res = directed_network(sig, method="psi", fs=1000.0, jackknife=False)
        assert np.all(np.isnan(res["q_matrix"]))
        assert "fdr_requested_but_no_pair_has_a_p_value" in res["warnings"]
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            quiet = directed_network(sig, method="psi", fs=1000.0, jackknife=False, fdr=False)
        assert "fdr_requested_but_no_pair_has_a_p_value" not in quiet["warnings"]

    @pytest.mark.parametrize("fn", [spike_mutual_information,
                                    binary_occupancy_mutual_information,
                                    spike_count_mutual_information])
    def test_each_mutual_information_function_names_itself(self, fn):
        """P-256: the two wrappers raised under the name spike_mutual_information."""
        name = fn.__name__
        with pytest.raises(ValueError, match=rf"^{name} requires non-empty"):
            fn(np.array([]), np.array([0.1]), (0.0, 1.0))
        with pytest.raises(ValueError, match=rf"^{name}\b"):
            fn(np.array([0.1]), np.array([0.2]), (0.0, 1.0), bin_size_ms=3.0)


class TestPsiJackknifeUnit:
    """P-227, ruled 2026-10-06: the jackknife leaves out one trial from three trials on, and
    one segment with a warning below that. Leaving out one of a trial's overlapping segments
    rejected in 0.059 to 0.068 under zero-lag mixing on 3 to 30 trials; one trial, 0.040 to
    0.059 (artifacts/evidence/0.2.10/10-06/records.md)."""

    KW = dict(fs=1000.0, bands=(5.0, 100.0), nperseg=100)

    @staticmethod
    def _lagged(n_trials, seed=5):
        rng = np.random.default_rng(seed)
        x = rng.normal(size=(n_trials, 400))
        return x, np.roll(x, 3, axis=1) + 2.0 * rng.normal(size=(n_trials, 400))

    def test_three_or_more_trials_leave_out_a_trial(self):
        """Each replicate is recomputed as the PSI of the other trials, a fresh call."""
        x, y = self._lagged(4)
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            res = phase_slope_index(x, y, **self.KW)
            reps = np.array([phase_slope_index(np.delete(x, i, 0), np.delete(y, i, 0),
                                               **self.KW).net for i in range(4)])
        sd = np.sqrt(3 / 4 * np.sum((reps - reps.mean()) ** 2))
        band = res.per_band["band"]
        assert res.params["jackknife_unit"] == "trial"
        assert band["sd"] == pytest.approx(sd, rel=1e-9)
        assert res.p_net == pytest.approx(2 * stats.t.sf(abs(band["value"] / sd), df=3),
                                          rel=1e-9)

    def test_fewer_than_three_trials_leave_out_a_segment_and_warn(self):
        x, y = self._lagged(2)
        with pytest.warns(RuntimeWarning, match="leaves out one Welch segment"):
            res = phase_slope_index(x, y, **self.KW)
        n_seg = res.params["n_segments"]
        assert res.params["jackknife_unit"] == "segment" and n_seg == 14
        z = res.per_band["band"]["z"]
        assert res.p_net == pytest.approx(2 * stats.t.sf(abs(z), df=n_seg - 1), rel=1e-12)

    def test_the_round_off_bound_is_k_n_eps_scale(self):
        """P-331: k = 4, n the segments, scale the bin pairs times sqrt(units - 1), as the
        docstring of `_psi_round_off` derives."""
        from jnwb.connectivity._psi import _psi_round_off

        eps = np.finfo(float).eps
        # abs=0: approx's default abs of 1e-12 exceeds these bounds and accepted any k.
        assert _psi_round_off(70, 9, 10) == pytest.approx(
            4 * 70 * eps * 9 * 3.0, rel=1e-15, abs=0)
        assert _psi_round_off(20, 5, 20) == pytest.approx(
            4 * 20 * eps * 5 * np.sqrt(19), rel=1e-15, abs=0)


class TestRoundOffBounds:
    """P-331 (ruled 2026-10-06): width and constant checks use a round-off bound
    k * n * eps * scale, with k stated and derived where the bound is defined."""

    def test_a_linearly_detrended_line_is_exactly_zero_and_noise_survives(self):
        """The residue of a fitted line was 5e-15 and 3e-11 on these two trials."""
        from jnwb.connectivity._trials import _detrend_trials

        t = np.arange(1000.0)
        line = np.stack([3.7 + 0.013 * t, -2e5 + 41.0 * t])
        np.testing.assert_array_equal(_detrend_trials(line, "linear"), 0.0)
        noisy = line + 1e-6 * np.random.default_rng(0).normal(size=line.shape)
        assert np.all(np.std(_detrend_trials(noisy, "linear"), axis=1) > 5e-7)

    def test_granger_on_a_detrended_line_is_degenerate_not_a_number(self):
        """The residue passed the exact zero-variance guard: y_to_x was 0.0027 with no
        degenerate warning on a pure line."""
        x = 5.0 + 0.01 * np.arange(500.0)
        y = np.random.default_rng(0).normal(size=500)
        res = granger(x, y, order=2, detrend="linear")
        assert np.isnan(res.y_to_x)
        assert "degenerate_residual_variance_var_not_identifiable" in res.diagnostics["warnings"]

    def test_the_detrend_bound_is_k_n_eps_scale_with_k_4(self):
        from jnwb._spread import DETREND_ROUND_OFF_K, zero_detrend_residue

        assert DETREND_ROUND_OFF_K == 4.0
        original = np.array([[2.0, -8.0, 1.0, 0.5]])
        bound = 4.0 * 4 * np.finfo(float).eps * 8.0
        at = np.array([[bound, -bound, 0.0, 0.5 * bound]])
        np.testing.assert_array_equal(zero_detrend_residue(at, original, axis=1), 0.0)
        over = at * 1.01
        np.testing.assert_array_equal(zero_detrend_residue(over, original, axis=1), over)

    def test_the_te_bound_is_k_n_eps_scale_with_k_4(self):
        from jnwb.connectivity._transfer_entropy import _te_round_off

        eps = np.finfo(float).eps
        assert _te_round_off((1.0, 2.0, 0.5, 2.5), (4, 16, 4, 64)) == pytest.approx(
            4 * 88 * eps * 6.0, rel=1e-15, abs=0)
        assert _te_round_off((0.1, 0.1, 0.05, 0.1), (2, 2, 2, 2)) == pytest.approx(
            4 * 8 * eps * 1.0, rel=1e-15, abs=0)

    def test_the_te_net_tie_width_follows_the_entropies(self, monkeypatch):
        """The net width was 100 eps (|TE_xy| + |TE_yx|), the size of a value near zero, not
        of the four entropies of about two bits each it cancels."""
        import jnwb.connectivity._transfer_entropy as te_mod

        seen = []
        real = te_mod._surrogate_p

        def record(null, observed, alternative, scale=0.0, atol=0.0):
            seen.append((alternative, scale, atol))
            return real(null, observed, alternative, scale=scale, atol=atol)

        monkeypatch.setattr(te_mod, "_surrogate_p", record)
        rng = np.random.default_rng(2)
        x, y = rng.normal(size=600), rng.normal(size=600)
        res = transfer_entropy(x, y, n_surrogates=9, rng=0)
        xq = te_mod._discretize(x[None], 4, "quantile")
        yq = te_mod._discretize(y[None], 4, "quantile")
        ro_xy = te_mod._te_one_direction(xq, yq, 1, 1, 1, "mm", return_round_off=True)[4]
        ro_yx = te_mod._te_one_direction(yq, xq, 1, 1, 1, "mm", return_round_off=True)[4]
        net = [atol for alternative, _, atol in seen if alternative == "two-sided"]
        assert len(net) == 1 and res.p_net is not None
        one_way = [atol for alternative, _, atol in seen if alternative == "greater"]
        assert len(one_way) == 2 and one_way[0] > ro_xy and one_way[1] > ro_yx
        plain = 100 * np.finfo(float).eps * (abs(res.x_to_y) + abs(res.y_to_x))
        assert net[0] > ro_xy + ro_yx > 100 * plain

    def test_a_caller_tie_width_reaches_the_count(self):
        from jnwb.connectivity._common import _surrogate_p

        null = np.array([0.0])
        assert _surrogate_p(null, 1e-13, "greater") == 0.5
        assert _surrogate_p(null, 1e-13, "greater", atol=2e-13) == 1.0

    def test_the_te_one_way_tie_width_is_observed_plus_draw_round_off(self, monkeypatch):
        """With every round-off bound pinned to 1.0 the one-way width is 2.0 (observed plus
        the draws' largest) and the net width 4.0; dropping the observed term gave 1.0 and
        2.0, a width that still exceeded the observed bound on real data."""
        import jnwb.connectivity._transfer_entropy as te_mod

        seen = []
        real = te_mod._surrogate_p

        def record(null, observed, alternative, scale=0.0, atol=0.0):
            seen.append((alternative, atol))
            return real(null, observed, alternative, scale=scale, atol=atol)

        monkeypatch.setattr(te_mod, "_surrogate_p", record)
        monkeypatch.setattr(te_mod, "_te_round_off", lambda entropies, cells: 1.0)
        rng = np.random.default_rng(2)
        transfer_entropy(rng.normal(size=600), rng.normal(size=600), n_surrogates=9, rng=0)
        assert [a for alt, a in seen if alt == "greater"] == [2.0, 2.0]
        assert [a for alt, a in seen if alt == "two-sided"] == [4.0]

    @pytest.mark.parametrize("residue_has_nan", [True, False])
    def test_a_nan_slice_is_left_as_it_is_and_a_clean_one_is_zeroed(self, residue_has_nan):
        """The max of a slice holding a NaN is NaN, so no bound admits it: its finite
        round-off-sized entries stay, where a NaN-skipping max zeroed them."""
        from jnwb._spread import zero_detrend_residue

        original = np.array([[1.0, 2.0, np.nan, 4.0], [1.0, 2.0, 3.0, 4.0],
                             [1.0, 2.0, 3.0, 4.0]])
        tiny = np.tile([1e-20, 2e-20, 3e-20, 4e-20], (3, 1))
        if residue_has_nan:
            tiny[0, 2] = np.nan
        tiny[2, 1] = np.nan      # finite original, NaN residue
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            out = zero_detrend_residue(tiny, original, axis=1)
        np.testing.assert_array_equal(out[0], tiny[0])
        np.testing.assert_array_equal(out[1], 0.0)
        np.testing.assert_array_equal(out[2], tiny[2])


class TestEstimatorEdgesRound2:
    """Round-2 reach of 10-06: each assertion is on the quantity a one-line mutant moves."""

    def test_conditioning_uses_every_other_node_not_the_first(self):
        """Four nodes, pair (A, D): the others are X then B. A -> B -> D has no direct
        A -> D edge; conditioning on X alone left it at p < 1e-10."""
        rng = np.random.default_rng(3)
        n = 3000
        a, x, b, d = rng.normal(size=(4, n))
        for t in range(1, n):
            b[t] += 0.8 * a[t - 1]
            d[t] += 0.8 * b[t - 1]
        res = directed_network({"A": a, "X": x, "B": b, "D": d}, method="granger", order=2,
                               fdr=False, conditional=True)
        assert res["results"][("A", "D")].params["n_conditioning"] == 2
        assert res["p_matrix"][0, 3] > 0.05
        assert res["p_matrix"][0, 2] < 1e-10 and res["p_matrix"][2, 3] < 1e-10

    def test_multiband_total_p_uses_trial_degrees_of_freedom(self):
        """Leaving out a trial, the total's t has trials - 1 degrees of freedom, not the
        segment count minus one."""
        kw = dict(fs=1000.0, nperseg=100,
                  bands={"lo": (5.0, 30.0), "hi": (40.0, 100.0)})
        rng = np.random.default_rng(5)
        x = rng.normal(size=(4, 400))
        y = np.roll(x, 3, axis=1) + 2.0 * rng.normal(size=(4, 400))
        res = phase_slope_index(x, y, **kw)
        reps = np.array([phase_slope_index(np.delete(x, i, 0), np.delete(y, i, 0), **kw).net
                         for i in range(4)])
        sd = np.sqrt(3 / 4 * np.sum((reps - reps.mean()) ** 2))
        assert res.params["jackknife_unit"] == "trial" and res.params["n_segments"] != 4
        assert res.p_net == pytest.approx(2 * stats.t.sf(abs(res.net / sd), df=3), rel=1e-9)

    def test_the_gc_alias_is_granger(self):
        rng = np.random.default_rng(1)
        x, y = rng.normal(size=(2, 400))
        a = directed_connectivity(x, y, method="gc", order=2)
        b = directed_connectivity(x, y, method="granger", order=2)
        assert (a.method, a.x_to_y, a.y_to_x) == (b.method, b.x_to_y, b.y_to_x)
        net = directed_network({"x": x, "y": y}, method="gc", order=2, fdr=False)
        assert net["matrix"][0, 1] == b.x_to_y
