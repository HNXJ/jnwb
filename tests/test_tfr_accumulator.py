"""merge(A, B) == summarize(A union B) is the one property the whole poolable-summary design
in nwb_tfr_storage_spec.md rests on (spec Part 4 checklist). Everything else here is secondary
correctness against a direct (non-streaming) computation.
"""
import numpy as np
import pytest

from jnwb.tfr_accumulator import TFRAccumulator, assert_mergeable


def _summarize(trials: np.ndarray, valid: np.ndarray = None) -> TFRAccumulator:
    """Direct, one-shot summary of a (n_trials, n_ch, n_freq, n_time) complex array."""
    acc = TFRAccumulator(trials.shape[1:])
    for i in range(trials.shape[0]):
        v = None if valid is None else valid[i]
        acc.add_trial(trials[i], valid=v)
    return acc


def _random_trials(n_trials, shape, seed):
    rng = np.random.default_rng(seed)
    re = rng.normal(size=(n_trials, *shape))
    im = rng.normal(size=(n_trials, *shape))
    # give power a realistic large-mean/small-variance profile (spec's stated failure mode
    # for naive sum/sumsq) by adding a big positive offset to the real part
    re = re * 0.05 + 5.0
    return (re + 1j * im).astype(np.complex128)


class TestMergeEquivalence:
    """The load-bearing property."""

    @pytest.mark.parametrize("shape", [(3, 4, 5), (1, 1, 1), (2, 60, 500)])
    @pytest.mark.parametrize("n_a,n_b", [(10, 15), (1, 1), (0, 10), (17, 0)])
    def test_merge_equals_summarize_union(self, shape, n_a, n_b):
        trials_a = _random_trials(n_a, shape, seed=1)
        trials_b = _random_trials(n_b, shape, seed=2)
        trials_all = np.concatenate([trials_a, trials_b], axis=0) if (n_a + n_b) else np.empty((0, *shape), np.complex128)

        acc_a = _summarize(trials_a)
        acc_b = _summarize(trials_b)
        merged = acc_a.merge(acc_b)
        direct = _summarize(trials_all)

        np.testing.assert_array_equal(merged.n, direct.n)
        # mean/M2 involve floating subtraction paths that differ in ORDER between the two-pass
        # merge and the incremental Welford pass, so exact equality is not guaranteed -- but
        # they must agree to float64 tolerance.
        valid_mask = direct.n > 0
        np.testing.assert_allclose(merged.mean[valid_mask], direct.mean[valid_mask], rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(merged.M2[valid_mask], direct.M2[valid_mask], rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(merged.sum_z, direct.sum_z, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(merged.sum_unit_z, direct.sum_unit_z, rtol=1e-12, atol=1e-12)

    def test_merge_associative_three_way(self):
        """(A merge B) merge C == A merge (B merge C) == summarize(A u B u C)."""
        shape = (2, 3, 4)
        a, b, c = (_random_trials(n, shape, seed=s) for n, s in [(5, 10), (7, 20), (3, 30)])
        acc_a, acc_b, acc_c = _summarize(a), _summarize(b), _summarize(c)

        left = acc_a.merge(acc_b).merge(acc_c)
        right = acc_a.merge(acc_b.merge(acc_c))
        direct = _summarize(np.concatenate([a, b, c], axis=0))

        for name in ("n", "mean", "M2", "sum_z", "sum_unit_z"):
            l, r, d = getattr(left, name), getattr(right, name), getattr(direct, name)
            np.testing.assert_allclose(l, r, rtol=1e-8, atol=1e-10)
            np.testing.assert_allclose(l, d, rtol=1e-8, atol=1e-10)

    def test_merge_with_masked_invalid_trials(self):
        shape = (2, 2, 2)
        trials = _random_trials(20, shape, seed=42)
        valid = np.ones((20, *shape), dtype=bool)
        # invalidate a different subset of bins on different trials -- exercises per-bin n
        rng = np.random.default_rng(0)
        valid &= rng.random((20, *shape)) > 0.3

        acc_a = _summarize(trials[:12], valid[:12])
        acc_b = _summarize(trials[12:], valid[12:])
        merged = acc_a.merge(acc_b)
        direct = _summarize(trials, valid)

        np.testing.assert_array_equal(merged.n, direct.n)
        mask = direct.n > 0
        np.testing.assert_allclose(merged.mean[mask], direct.mean[mask], rtol=1e-9, atol=1e-11)


class TestPerBinN:
    """Spec 2.4: n must be an array, not a scalar -- per-bin counts must differ correctly."""

    def test_n_varies_per_bin_with_partial_validity(self):
        shape = (2, 2)
        acc = TFRAccumulator(shape)
        z1 = np.ones(shape, dtype=complex)
        valid1 = np.array([[True, False], [True, True]])
        acc.add_trial(z1, valid1)
        z2 = np.ones(shape, dtype=complex) * 2
        valid2 = np.array([[True, True], [False, True]])
        acc.add_trial(z2, valid2)

        expected_n = np.array([[2, 1], [1, 2]])
        np.testing.assert_array_equal(acc.n, expected_n)


class TestDerivedQuantities:
    def test_power_var_sem_against_direct_formula(self):
        shape = (2, 2, 2)
        trials = _random_trials(30, shape, seed=7)
        acc = _summarize(trials)

        power = np.abs(trials) ** 2
        expected_mean = power.mean(axis=0)
        expected_var = power.var(axis=0, ddof=1)
        expected_sem = np.sqrt(expected_var / trials.shape[0])

        np.testing.assert_allclose(acc.power(), expected_mean, rtol=1e-9)
        np.testing.assert_allclose(acc.var(), expected_var, rtol=1e-8)
        np.testing.assert_allclose(acc.sem(), expected_sem, rtol=1e-8)

    def test_evoked_and_itc_against_direct_formula(self):
        shape = (2, 3)
        trials = _random_trials(25, shape, seed=8)
        acc = _summarize(trials)

        expected_evoked = np.abs(trials.mean(axis=0)) ** 2
        unit_z = trials / np.abs(trials)
        expected_itc = np.abs(unit_z.mean(axis=0))

        np.testing.assert_allclose(acc.evoked(), expected_evoked, rtol=1e-9)
        np.testing.assert_allclose(acc.itc(), expected_itc, rtol=1e-9)
        # ITC is bounded in [0, 1] by construction
        assert np.all(acc.itc() <= 1.0 + 1e-9)
        assert np.all(acc.itc() >= 0.0)

    def test_itc_is_one_for_perfectly_phase_locked_trials(self):
        """Every trial has identical phase -> ITC must be exactly 1 (ceiling case)."""
        shape = (2, 2)
        acc = TFRAccumulator(shape)
        phase = np.exp(1j * 0.7)
        for _ in range(10):
            acc.add_trial(np.full(shape, phase * 3.0))
        np.testing.assert_allclose(acc.itc(), np.ones(shape), atol=1e-10)

    def test_itc_is_near_zero_for_uniform_random_phase(self):
        """Many trials, uniformly random phase -> ITC -> 0 (floor case, statistical)."""
        shape = (1, 1)
        acc = TFRAccumulator(shape)
        rng = np.random.default_rng(123)
        n = 5000
        phases = rng.uniform(0, 2 * np.pi, n)
        for p in phases:
            acc.add_trial(np.array([[np.exp(1j * p) * 2.0]]))
        assert acc.itc()[0, 0] < 0.05  # expected ~1/sqrt(n) ~ 0.014


class TestNumericalStability:
    """Spec's stated reason to prefer Chan/Welford over sum/sumsq: catastrophic cancellation
    on large-mean/small-variance power, which is the typical TFR profile."""

    def test_small_variance_large_mean_no_cancellation(self):
        shape = (1,)
        rng = np.random.default_rng(99)
        true_mean = 1e6
        true_std = 1.0  # variance is ~1e-12 relative to mean^2
        n = 500
        vals = rng.normal(true_mean, true_std, n)
        # construct trials whose |z|^2 equals `vals` exactly: z = sqrt(vals) real
        z = np.sqrt(vals).reshape(n, 1).astype(complex)

        acc = _summarize(z)
        naive_var = np.sum((vals - vals.mean()) ** 2) / (n - 1)

        assert acc.var()[0] == pytest.approx(naive_var, rel=1e-6)
        assert acc.var()[0] == pytest.approx(true_std**2, rel=0.2)


class TestAssertMergeable:
    BASE = dict(
        freqs=np.array([4.0, 8.0, 14.0]), times=np.array([0.0, 0.1, 0.2]),
        baseline_window=(-0.2, 0.0), baseline_method="db_ratio",
        tfr_method="morlet", preproc_version="abc123",
        unit="dB", log_scaled=True,
    )

    def test_identical_attrs_do_not_raise(self):
        assert_mergeable(self.BASE, dict(self.BASE))

    def test_missing_required_key_raises(self):
        b = dict(self.BASE)
        del b["preproc_version"]
        with pytest.raises(KeyError):
            assert_mergeable(self.BASE, b)

    @pytest.mark.parametrize("key,other_val", [
        ("tfr_method", "hilbert"),
        ("preproc_version", "def456"),
        ("baseline_method", "zscore"),
        ("unit", "power"),
        ("log_scaled", False),
    ])
    def test_mismatched_value_raises(self, key, other_val):
        b = dict(self.BASE)
        b[key] = other_val
        with pytest.raises(ValueError, match="refusing to merge"):
            assert_mergeable(self.BASE, b)

    def test_mismatched_array_valued_attr_raises(self):
        b = dict(self.BASE)
        b["freqs"] = np.array([4.0, 8.0, 15.0])  # one value differs
        with pytest.raises(ValueError, match="refusing to merge"):
            assert_mergeable(self.BASE, b)


class TestWriteRoundTrip:
    def test_write_produces_expected_datasets_and_dtypes(self, tmp_path):
        import h5py

        shape = (2, 3, 4)
        trials = _random_trials(15, shape, seed=55)
        acc = _summarize(trials)
        meta = dict(TestAssertMergeable.BASE, session_id="sub-test_ses-1")

        with h5py.File(tmp_path / "summary.h5", "w") as f:
            g = f.create_group("test_group")
            acc.write(g, meta)

        with h5py.File(tmp_path / "summary.h5", "r") as f:
            g = f["test_group"]
            assert g["n"].dtype == np.int32
            assert g["mean"].dtype == np.float32
            assert g["M2"].dtype == np.float32
            assert g["sum_z"].dtype == np.complex64
            assert g["sum_unit_z"].dtype == np.complex64
            for name in ("n", "mean", "M2", "sum_z", "sum_unit_z"):
                assert g[name].shape == shape
                assert g[name].compression == "gzip"
                assert g[name].compression_opts == 1
                assert g[name].shuffle is True
            assert g.attrs["tfr_method"] == "morlet"
            assert g.attrs["session_id"] == "sub-test_ses-1"

            # values survive the float32/complex64 downcast to a sane tolerance
            np.testing.assert_allclose(g["mean"][:], acc.mean, rtol=1e-6)
            np.testing.assert_allclose(g["sum_z"][:], acc.sum_z, rtol=1e-6)
