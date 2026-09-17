"""Estimators that no test could distinguish from a constant.

Every test here exists because a mutation of the implementation it covers changed no test
result anywhere in the full suite. Each one names the mutation it kills.

The four covered here are the survivors of an eight-mutant sweep. The other four
mutations the 05-54 audit listed -- the two shuffle p-values collapsing to `1/(n+1)`,
`shuffle_r2_ci.p_val` pinned to 0.001, `fdr_correct` returning its input, and
`laplacian_reference` dropping its un-permute -- all died against the existing suite, so
they are already covered and nothing is added for them here.

Two design rules these follow:

An estimator needs a positive control computed by a route that does not reuse the
implementation. A file of null cases cannot tell a working estimator from a constant, and
a self-comparison cannot tell one from a copy of itself.

A p-value under the null is uniform, so a single seed showing `p > 0.2` is a draw, not a
property. Choosing the seed that passes is fitting the test to the data. These calibrate
over many seeds instead and assert the shape of the distribution.
"""

import numpy as np
import pytest
from scipy import signal as sp_signal

import jnwb
from jnwb.statistics import StatisticalAnalysis, paired_fire_prob_test


class TestImaginaryCoherencyAgainstAnIndependentOracle:
    """Kills: `icoh_mean` and `icoh_abs_mean` forced to 0.0.

    The existing coverage lives in a file named `nonfabrication` and is entirely
    rejection cases plus one null case asserting `abs(icoh_mean) < 0.1`, which 0.0
    satisfies perfectly.
    """

    FS = 500.0
    BAND = (18.0, 22.0)

    @staticmethod
    def _oracle(x, y, fs, nperseg, noverlap, freq_range):
        """Im(coherency) recomputed from first principles: segment, detrend, window, rFFT.

        Reuses no jnwb helper and no scipy spectral estimator, so a shared bug cannot
        cancel. Coherency is scale-invariant, so the density normalisation scipy applies
        identically to all three spectra cancels in the ratio and is omitted here.
        """
        win = sp_signal.get_window("hann", nperseg)
        step = nperseg - noverlap
        segs_x, segs_y = [], []
        start = 0
        while start + nperseg <= len(x):
            sx = x[start:start + nperseg]
            sy = y[start:start + nperseg]
            segs_x.append(np.fft.rfft((sx - sx.mean()) * win))
            segs_y.append(np.fft.rfft((sy - sy.mean()) * win))
            start += step
        X = np.array(segs_x)
        Y = np.array(segs_y)
        pxx = np.mean(np.abs(X) ** 2, axis=0)
        pyy = np.mean(np.abs(Y) ** 2, axis=0)
        sxy = np.mean(np.conj(X) * Y, axis=0)
        coh = sxy / np.sqrt(pxx * pyy)
        freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
        mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
        im = np.imag(coh[mask])
        return {
            "mean": float(np.mean(im)),
            "abs_mean": float(np.mean(np.abs(im))),
            "n_bins": int(mask.sum()),
            "freqs": freqs,
            "mask": mask,
            "im_per_bin": im,
            "pxx": pxx,
        }

    def _phase_shifted_pair(self, n_samples=8192):
        """A narrowband pair at a fixed phase offset, so Im(Cxy) keeps one sign.

        Deliberately not a broadband lagged source. A pure delay rotates the cross
        spectrum by an angle proportional to frequency, so Im(Cxy) changes sign across a
        wide band and `icoh_mean` -- a *signed* mean -- partially cancels toward zero.
        That would let an implementation returning a constant 0.0 agree with the oracle
        by accident, which is the mutation this test exists to kill. A fixed phase offset
        inside a narrow band holds the sign constant instead.
        """
        rng = np.random.default_rng(7)
        t = np.arange(n_samples) / self.FS
        x = np.sin(2 * np.pi * 20 * t) + 0.5 * rng.normal(size=n_samples)
        y = np.sin(2 * np.pi * 20 * t + np.pi / 3) + 0.5 * rng.normal(size=n_samples)
        return x, y

    def test_matches_an_independent_oracle_on_a_phase_shifted_pair(self):
        x, y = self._phase_shifted_pair()
        nperseg = min(max(len(x) // 8, 8), 1024)
        noverlap = nperseg // 2
        ref = self._oracle(x, y, self.FS, nperseg, noverlap, self.BAND)

        # Non-vacuity, three ways.
        # 1. The band must contain the constructed 20 Hz component. Without this, a
        #    frequency-selection change could leave a non-zero aggregate that comes from
        #    noise bins rather than the signal.
        in_band = ref["freqs"][ref["mask"]]
        assert in_band.min() <= 20.0 <= in_band.max(), in_band
        peak_hz = float(ref["freqs"][int(np.argmax(ref["pxx"]))])
        assert self.BAND[0] <= peak_hz <= self.BAND[1], (
            f"the spectral peak is at {peak_hz} Hz, outside the band under test"
        )
        # 2. The sign must hold where the signal is, not only in the average. Checking
        #    every in-band bin would be checking something the construction does not
        #    imply: only ~3 of the 9 bins carry the 20 Hz component, and in the
        #    noise-dominated remainder Im(coherency) is small with arbitrary sign. The
        #    bin is selected by power, which is independent of the quantity under test.
        band_freqs = ref["freqs"][ref["mask"]]
        peak_i = int(np.argmax(ref["pxx"][ref["mask"]]))
        assert abs(band_freqs[peak_i] - 20.0) < 1.0, band_freqs[peak_i]
        assert ref["im_per_bin"][peak_i] > 0.5, ref["im_per_bin"]
        # 3. The aggregate must be far enough from zero that a constant 0.0 disagrees.
        assert abs(ref["mean"]) > 0.05, f"oracle too close to zero to discriminate: {ref['mean']}"
        assert ref["abs_mean"] > 0.05, ref["abs_mean"]

        out = jnwb.imaginary_coherency(x, y, fs=self.FS, freq_range=self.BAND)

        assert out["n_freqs"] == ref["n_bins"]
        assert out["icoh_mean"] == pytest.approx(ref["mean"], abs=1e-10)
        assert out["icoh_abs_mean"] == pytest.approx(ref["abs_mean"], abs=1e-10)

    def test_a_phase_shifted_pair_produces_a_non_zero_estimate_of_the_right_sign(self):
        """The positive control the null-only coverage never had.

        The sign follows from the estimator's definition, not from a run. The
        implementation takes its cross spectrum from ``scipy.signal.csd(x, y, ...)``, and
        scipy defines that as ``conj(X) * Y`` -- stated in the `csd` docstring ("Pxy is
        computed with the conjugate FFT of X"), repeated as a comment in
        `_spectral_py.py`, and implemented as ``np.conjugate(result) * result_y``. The
        oracle above uses the same orientation. Under the opposite convention,
        ``X * conj(Y)``, the correct expectation here would be negative.

        Given that orientation, with ``x = sin(wt)`` and ``y = sin(wt + pi/3)``, the cross
        spectrum is ``|X|^2 * exp(i*pi/3)``, whose imaginary part is positive.

        If this fails, the question is whether the estimator has a sign error -- not
        whether the expectation here should be flipped to match what it returned.
        """
        x, y = self._phase_shifted_pair()
        out = jnwb.imaginary_coherency(x, y, fs=self.FS, freq_range=self.BAND)
        assert out["icoh_abs_mean"] > 0.05, out
        assert out["icoh_mean"] > 0.05, out


class TestBipolarReferenceHasAPinnedSign:
    """Kills: `bipolar_reference` returning `ordered[:-1] - ordered[1:]`.

    Every existing test either checks shape, checks rejection, or feeds data symmetric
    enough that the flip is invisible.
    """

    def test_subtracts_the_shallower_channel_from_the_deeper(self):
        data = np.array([[1.0, 1.0], [3.0, 5.0], [6.0, 11.0]])
        out = jnwb.bipolar_reference(data)
        expected = np.array([[2.0, 4.0], [3.0, 6.0]])
        np.testing.assert_allclose(out, expected)
        # Non-vacuity: the flipped result must be a different array, or this cannot
        # distinguish the two orientations.
        assert not np.allclose(expected, -expected)


class TestPValuesAreCalibratedUnderTheNull:
    """Kills: `paired_fire_prob_test`'s p pinned to 0.0001, and `confirmed_*` forced True.

    A p-value under the null is uniform, so one seed reporting a large p is a draw rather
    than a property, and picking the seed that passes fits the test to the data. These
    calibrate across seeds: under the null a small minority of draws should be
    significant, and a constant makes that fraction 0 or 1.
    """

    N_SEEDS = 20

    def test_paired_fire_prob_is_not_significant_on_most_null_draws(self):
        p_values = []
        for seed in range(self.N_SEEDS):
            rng = np.random.default_rng(seed)
            # Same fire probability in both windows: nothing to detect.
            target = rng.random(200) < 0.3
            null = rng.random(200) < 0.3
            out = paired_fire_prob_test(
                target, null, n_shuffles=200, n_bootstrap=200,
                rng=np.random.default_rng(seed + 1000),
            )
            p_values.append(out["p_value_fire_shuffle"])

        p = np.asarray(p_values, dtype=float)
        assert len(np.unique(p)) > 1, f"p is constant across null draws: {p[0]}"
        assert np.mean(p < 0.05) <= 0.25, (
            f"{np.mean(p < 0.05):.0%} of null draws came out significant: {p.tolist()}"
        )

    def test_paired_fire_prob_still_detects_a_real_difference(self):
        """Without this, "always report nothing" would satisfy the calibration above."""
        rng = np.random.default_rng(0)
        target = rng.random(200) < 0.7
        null = rng.random(200) < 0.15
        out = paired_fire_prob_test(
            target, null, n_shuffles=500, n_bootstrap=200,
            rng=np.random.default_rng(1),
        )
        assert out["p_value_fire_shuffle"] < 0.01, out

    def test_confirmatory_compare_rarely_confirms_null_data(self):
        confirmations = []
        for seed in range(self.N_SEEDS):
            rng = np.random.default_rng(seed)
            g1 = rng.normal(size=60)
            g2 = rng.normal(size=60)
            out = StatisticalAnalysis.confirmatory_compare(
                g1, g2, hypothesis="null data, nothing to confirm", n_bootstrap=200
            )
            confirmations.append(
                bool(out["confirmed_parametric"]) or bool(out["confirmed_nonparametric"])
            )

        rate = float(np.mean(confirmations))
        assert rate <= 0.25, f"{rate:.0%} of null comparisons were confirmed"

    def test_confirmatory_compare_still_confirms_a_real_difference(self):
        rng = np.random.default_rng(0)
        g1 = rng.normal(loc=2.0, size=60)
        g2 = rng.normal(loc=0.0, size=60)
        out = StatisticalAnalysis.confirmatory_compare(
            g1, g2, hypothesis="a two-sigma separation is real", n_bootstrap=200
        )
        assert out["confirmed_parametric"] is True, out
        assert out["confirmed_nonparametric"] is True, out
