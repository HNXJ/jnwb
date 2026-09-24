"""05-43: the device changed the number, twice over.

`AGENTS.md` invariant 6 says device and worker count never change a number. Two SVD
paths broke it on a live RTX A4000:

`gpu_pca(X(4000, 60), n_components=3)` returned float64 on CPU and float32 on CUDA, and
neither path pinned a sign, so `max|cpu - cuda|` on the projections was **8.005**. Align
the signs by hand and it drops to 6.5e-04 -- the float32 residue. Both defects were live
at once, and the second hid the first.

`compute_population_trajectory` was already float64 on both devices; only component signs
differed, which showed as `max_rel = 2.0` -- the exact signature of a flipped component.
Sign-aligned agreement was 6.5e-13.

The audit reported both as one item and prescribed "match the CPU dtype on the CUDA
branch" for both. That is wrong for `trajectory.py`, which uses `torch.as_tensor` and
therefore never lost precision; its only defect was the sign.

Why the suite was green: `tests/test_backend.py` compared the two devices with
`_, _, var_cuda = gpu_pca(...)`, keeping only `explained_variance_ratio`. That scalar is
invariant to a sign flip and agrees to 1e-7 across float32 and float64, so a test named
"cpu and cuda agree" passed while the returned projections differed by 8.0. The test is
strengthened here rather than trusted.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from jnwb._backend import torch_cuda_available
from jnwb.gpu_pca import gpu_pca, pin_component_signs
from jnwb.trajectory import compute_population_trajectory

requires_cuda = pytest.mark.skipif(
    not torch_cuda_available(), reason="no CUDA device on this machine"
)


def _pivot_signs(components: np.ndarray) -> np.ndarray:
    """The sign of each component's largest-magnitude loading."""
    pivot = np.argmax(np.abs(components), axis=1)
    return np.sign(components[np.arange(components.shape[0]), pivot])


class TestThePinItself:
    """`pin_component_signs` is pure numpy, so this half runs on any machine."""

    def test_every_pivot_loading_comes_out_positive(self):
        rng = np.random.default_rng(0)
        components = rng.standard_normal((4, 9))
        projections = rng.standard_normal((20, 4))

        pinned, _ = pin_component_signs(components, projections)

        assert np.all(_pivot_signs(pinned) > 0)

    def test_it_does_not_change_what_the_basis_reconstructs(self):
        """Flipping a component and its column of the projections together is a no-op on
        the product, which is the only thing a caller can observe about the pair."""
        rng = np.random.default_rng(1)
        components = rng.standard_normal((3, 7))
        projections = rng.standard_normal((25, 3))

        pinned_c, pinned_p = pin_component_signs(components, projections)

        assert np.allclose(projections @ components, pinned_p @ pinned_c)

    def test_a_flipped_input_lands_on_the_same_answer(self):
        """The property that makes it a convention rather than a transformation: two
        SVDs that disagree only about sign are mapped to one output."""
        rng = np.random.default_rng(2)
        components = rng.standard_normal((3, 7))
        projections = rng.standard_normal((25, 3))
        flip = np.array([1.0, -1.0, -1.0])

        a = pin_component_signs(components, projections)
        b = pin_component_signs(components * flip[:, None], projections * flip[None, :])

        assert np.array_equal(a[0], b[0])
        assert np.array_equal(a[1], b[1])

    def test_applying_it_twice_changes_nothing(self):
        rng = np.random.default_rng(3)
        components = rng.standard_normal((3, 7))
        projections = rng.standard_normal((25, 3))

        once = pin_component_signs(components, projections)
        twice = pin_component_signs(*once)

        assert np.array_equal(once[0], twice[0])
        assert np.array_equal(once[1], twice[1])

    def test_an_all_zero_component_has_no_largest_loading_and_is_left_alone(self):
        components = np.zeros((2, 5))
        components[1, 3] = -2.0
        projections = np.ones((4, 2))

        pinned_c, pinned_p = pin_component_signs(components, projections)

        assert np.array_equal(pinned_c[0], np.zeros(5))
        assert pinned_c[1, 3] == 2.0
        assert np.array_equal(pinned_p[:, 0], np.ones(4))
        assert np.array_equal(pinned_p[:, 1], -np.ones(4))

    def test_an_empty_component_matrix_is_returned_unchanged(self):
        components = np.zeros((0, 5))
        projections = np.zeros((4, 0))

        pinned_c, pinned_p = pin_component_signs(components, projections)

        assert pinned_c.shape == (0, 5)
        assert pinned_p.shape == (4, 0)


class TestGpuPcaPinsItsSignsOnEitherDevice:
    """CPU-only, so it fails on a machine with no GPU too."""

    @staticmethod
    def _matrix(seed=0, shape=(300, 20), dtype=np.float64):
        rng = np.random.default_rng(seed)
        return rng.standard_normal(shape).astype(dtype)

    def test_the_returned_components_carry_the_convention(self):
        _, components, _ = gpu_pca(self._matrix(), n_components=3, device="cpu")

        assert np.all(_pivot_signs(components) > 0)

    def test_the_fixture_is_not_vacuous(self):
        """Guard against a fixture whose raw LAPACK signs already happen to be positive,
        which would let the test pass with no pin at all. Seed 0 gives [+, +, -]."""
        matrix = self._matrix()
        scaled = (matrix - matrix.mean(0, keepdims=True)) / matrix.std(0, keepdims=True)
        _, _, vt = np.linalg.svd(scaled, full_matrices=False)

        assert np.any(_pivot_signs(vt[:3, :]) < 0)

    @pytest.mark.parametrize("seed", range(6))
    def test_the_convention_holds_whatever_lapack_picked(self, seed):
        _, components, _ = gpu_pca(self._matrix(seed), n_components=3, device="cpu")

        assert np.all(_pivot_signs(components) > 0)

    def test_the_projections_are_flipped_with_their_components(self):
        """A pin applied to the components alone would silently change what the
        projections mean."""
        matrix = self._matrix(seed=4)
        projections, components, _ = gpu_pca(matrix, n_components=3, device="cpu")

        scaled = (matrix - matrix.mean(0, keepdims=True)) / matrix.std(0, keepdims=True)
        assert np.allclose(projections, scaled @ components.T)

    def test_padding_beyond_the_available_components_is_untouched(self):
        """`n_components` larger than the rank pads with zeros, and a zero row has no
        largest loading to pin."""
        projections, components, _ = gpu_pca(
            self._matrix(shape=(6, 3)), n_components=5, device="cpu")

        assert components.shape == (5, 3)
        assert np.array_equal(components[3:], np.zeros((2, 3)))


class TestGpuPcaUsesOneDtypeForBothBranches:

    def test_float64_in_float64_out(self):
        rng = np.random.default_rng(0)
        projections, components, _ = gpu_pca(
            rng.standard_normal((80, 12)), n_components=3, device="cpu")

        assert projections.dtype == np.float64
        assert components.dtype == np.float64

    def test_float32_stays_float32_because_that_is_what_numpy_linalg_does(self):
        rng = np.random.default_rng(0)
        matrix = rng.standard_normal((80, 12)).astype(np.float32)
        projections, _, _ = gpu_pca(matrix, n_components=3, device="cpu")

        assert projections.dtype == np.float32

    def test_float16_is_promoted_rather_than_rejected(self):
        """`np.linalg.svd` refuses float16 outright, so before the dtype was decided
        ahead of the branch this raised on CPU and quietly succeeded in float32 on
        CUDA -- the device deciding whether the call worked at all."""
        rng = np.random.default_rng(0)
        matrix = rng.standard_normal((80, 12)).astype(np.float16)

        projections, _, _ = gpu_pca(matrix, n_components=3, device="cpu")

        assert projections.dtype == np.float64


class TestTrajectoryPinsItsSigns:

    class _Session:
        """Row-index lookup, matching the convention in `tests/test_trajectory.py`."""

        def __init__(self, n_units=24, seed=0):
            rng = np.random.default_rng(seed)
            self._df = pd.DataFrame({
                "unit_id": [5 + 3 * i for i in range(n_units)],
                "area": ["V1"] * n_units,
                "quality": ["stable"] * n_units,
            })
            self._spikes = {i: np.sort(rng.uniform(0.0, 60.0, 400))
                            for i in range(n_units)}

        def get_units(self, quality=None, area=None):
            df = self._df.copy()
            if area:
                df = df[df["area"] == area]
            if quality:
                df = df[df["quality"] == quality]
            return df

        def get_spike_times(self, unit_id):
            return self._spikes.get(unit_id, np.array([]))

    @staticmethod
    def _epochs():
        return pd.DataFrame({"start_time": np.arange(2.0, 50.0, 1.5)})

    def _reference(self, session, epochs):
        """The same computation, pinned independently of the library."""
        from jnwb.trajectory import build_time_resolved_matrix

        x, _, _ = build_time_resolved_matrix(
            session, "V1", epochs, (-1000.0, 2000.0), 20.0, None)
        n_trials, n_units, n_bins = x.shape
        flat = x.transpose(0, 2, 1).reshape(n_trials * n_bins, n_units)
        std = flat.std(0, keepdims=True)
        std[std == 0.0] = 1.0
        scaled = (flat - flat.mean(0, keepdims=True)) / std
        _, _, vt = np.linalg.svd(scaled, full_matrices=False)
        return scaled, vt[:3, :], (n_trials, n_bins)

    def test_the_fixture_is_not_vacuous(self):
        session = self._Session()
        _, vt, _ = self._reference(session, self._epochs())

        assert np.any(_pivot_signs(vt) < 0)

    def test_pinning_the_transposed_pair_would_be_visible(self):
        """A second vacuity guard, and the one that matters. Pinning on the sign of each
        component's largest *projection* instead of its largest *loading* is also a
        consistent flip of both arrays, so it survives every invariant a caller can
        check -- unless the fixture is one where the two rules disagree. Seed 1 was not:
        both rules gave [-1, -1, -1] there, and a transposed pin passed the whole file.
        Seed 0 gives [-1, -1, +1] against [+1, -1, +1]."""
        session = self._Session()
        scaled, vt, _ = self._reference(session, self._epochs())
        by_loading = _pivot_signs(vt)
        by_projection = _pivot_signs((scaled @ vt.T).T)

        assert not np.array_equal(by_loading, by_projection)

    def test_the_trajectory_matches_an_independently_pinned_reference(self):
        """Without the pin the library returns whatever sign LAPACK chose, which the
        previous test shows is negative for at least one component here."""
        session = self._Session()
        epochs = self._epochs()
        scaled, vt, (n_trials, n_bins) = self._reference(session, epochs)
        components, projections = pin_component_signs(vt, scaled @ vt.T)
        expected = projections.reshape(n_trials, n_bins, 3).transpose(0, 2, 1)

        result = compute_population_trajectory(
            session, "V1", epochs, n_components=3, device="cpu")

        assert np.allclose(result["trajectory"], expected, atol=1e-10)

    def test_explained_variance_is_untouched_by_the_pin(self):
        """A sign convention must not move the variance, which does not depend on it."""
        session = self._Session()
        epochs = self._epochs()
        scaled, _, _ = self._reference(session, epochs)
        s = np.linalg.svd(scaled, compute_uv=False)

        result = compute_population_trajectory(
            session, "V1", epochs, n_components=3, device="cpu")

        assert result["explained_variance"] == pytest.approx(
            float(np.sum(s[:3] ** 2) / np.sum(s ** 2)), rel=1e-12)


@requires_cuda
class TestTheTwoDevicesReturnTheSameNumbers:
    """The measurement the audit made, as a test. Skipped without a GPU, which is
    honest: on a CPU-only machine `device='cuda'` falls back and the comparison is
    vacuous."""

    @staticmethod
    def _both(fn):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return fn("cpu"), fn("cuda")

    def test_gpu_pca_projections_agree_without_any_post_hoc_alignment(self):
        rng = np.random.default_rng(0)
        matrix = rng.standard_normal((4000, 60))
        cpu, cuda = self._both(
            lambda d: gpu_pca(matrix, n_components=3, device=d))

        assert np.max(np.abs(cpu[0] - cuda[0])) < 1e-9

    def test_gpu_pca_components_agree_including_their_signs(self):
        rng = np.random.default_rng(0)
        matrix = rng.standard_normal((4000, 60))
        cpu, cuda = self._both(
            lambda d: gpu_pca(matrix, n_components=3, device=d))

        assert np.array_equal(_pivot_signs(cpu[1]), _pivot_signs(cuda[1]))
        assert np.max(np.abs(cpu[1] - cuda[1])) < 1e-9

    def test_gpu_pca_returns_the_same_dtype_on_both_devices(self):
        rng = np.random.default_rng(0)
        matrix = rng.standard_normal((4000, 60))
        cpu, cuda = self._both(
            lambda d: gpu_pca(matrix, n_components=3, device=d))

        assert cpu[0].dtype == cuda[0].dtype == np.float64
        assert cpu[1].dtype == cuda[1].dtype == np.float64

    def test_gpu_pca_keeps_float32_on_both_devices(self):
        rng = np.random.default_rng(0)
        matrix = rng.standard_normal((500, 30)).astype(np.float32)
        cpu, cuda = self._both(
            lambda d: gpu_pca(matrix, n_components=3, device=d))

        assert cpu[0].dtype == cuda[0].dtype == np.float32

    def test_the_trajectory_is_not_reflected_through_the_origin(self):
        session = TestTrajectoryPinsItsSigns._Session()
        epochs = TestTrajectoryPinsItsSigns._epochs()
        cpu, cuda = self._both(lambda d: compute_population_trajectory(
            session, "V1", epochs, n_components=3, device=d))

        assert np.max(np.abs(cpu["trajectory"] - cuda["trajectory"])) < 1e-9
