"""The stated precision policy is a value, and this file checks it against live code.

Item 06-55 accepts when the dtype of every public return is a stated function of the input
dtype and the request. The statement lives in :data:`jnwb._precision.PRECISION_POLICY`.
This file *reads* it. Nothing here carries its own copy of the table: a test that restated
the policy would agree with itself while the table and the code disagreed, which is the
whole failure the registry exists to prevent.

Two guards keep that honest. ``test_every_registry_entry_has_a_live_caller`` fails if an
entry is added without an invocation, so the registry cannot grow past its own evidence.
``test_a_double_request_is_accepted`` fails if the ``DOUBLE_ONLY`` refusal degenerates into
"always raise", so the refusal has to discriminate rather than simply reject.
"""

from __future__ import annotations

import importlib
import warnings

import numpy as np
import pandas as pd
import pytest

from jnwb._precision import (
    ALWAYS_DOUBLE,
    BY_REQUEST,
    DOUBLE_ONLY,
    NO_FLOAT_OUTPUT,
    PRECISION_POLICIES,
    PRECISION_POLICY,
    PRESERVES_INPUT,
    PrecisionNotSupportedError,
    resolve_working_dtype,
)

SEED = 20260920


def resolve(dotted: str):
    """Import the object a registry key names."""
    module_name, _, attr = dotted.rpartition(".")
    return getattr(importlib.import_module(module_name), attr)


def float_dtypes(obj, depth: int = 0) -> set:
    """Every floating-point dtype reachable in a structured return.

    NumPy arrays and NumPy scalars only. A plain Python ``float`` is excluded on purpose:
    it is the language's double and carries no dtype choice, so a function returning one
    has not made a precision decision that a policy could describe. Including them made
    ``gpu_pca`` -- whose third return is ``float(explained_variance_ratio)`` -- look like it
    violated ``preserves_input`` when it does not.
    """
    found: set = set()
    if depth > 3:
        return found
    if isinstance(obj, np.ndarray):
        if obj.dtype.kind in "fc":
            found.add(obj.dtype)
    elif isinstance(obj, (bool, np.bool_)):
        pass
    elif isinstance(obj, np.floating):
        found.add(np.dtype(type(obj)))
    elif isinstance(obj, float):
        pass
    elif isinstance(obj, dict):
        for value in obj.values():
            found |= float_dtypes(value, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            found |= float_dtypes(value, depth + 1)
    elif isinstance(obj, pd.DataFrame):
        for dtype in obj.dtypes:
            if getattr(dtype, "kind", "") in "fc":
                found.add(dtype)
    elif hasattr(obj, "__dataclass_fields__"):
        for field in obj.__dataclass_fields__:
            found |= float_dtypes(getattr(obj, field), depth + 1)
    return found


# --------------------------------------------------------------------- fixtures


def _psd(dtype):
    rng = np.random.default_rng(SEED)
    freqs = np.linspace(1.0, 150.0, 120)
    depth = np.linspace(0.0, 1.0, 24)[:, None]
    low = np.exp(-((freqs[None, :] - 15.0) ** 2) / (2 * 8.0**2))
    high = np.exp(-((freqs[None, :] - 90.0) ** 2) / (2 * 30.0**2))
    psd = (depth * low * 5.0 + (1 - depth) * high * 5.0 + 0.05) * 1e-3
    psd = psd + rng.standard_normal(psd.shape) * 1e-6
    return psd.astype(dtype), freqs.astype(dtype)


def _units_frames(dtype):
    units = pd.DataFrame(
        {"unit_id": np.arange(6), "peak_channel": np.arange(6, dtype=np.int64)}
    )
    electrodes = pd.DataFrame(
        {
            "id": np.arange(6, dtype=np.int64),
            "depth": np.arange(6, dtype=dtype) * 100.0,
            "location": ["V1"] * 6,
        }
    )
    return units, electrodes


def call_gpu_pca(dtype):
    rng = np.random.default_rng(SEED)
    return resolve("jnwb.gpu_pca.gpu_pca")(
        rng.standard_normal((20, 5)).astype(dtype), n_components=3, device="cpu"
    )


def call_to_db(dtype):
    rng = np.random.default_rng(SEED)
    ratio = (np.abs(rng.standard_normal((4, 5))) + 0.5).astype(dtype)
    return resolve("jnwb.spectral.to_db")(ratio)


def call_aggregate_to_db(dtype):
    rng = np.random.default_rng(SEED)
    power = (np.abs(rng.standard_normal((4, 5))) + 0.5).astype(dtype)
    baseline = (np.abs(rng.standard_normal((4, 5))) + 0.5).astype(dtype)
    return resolve("jnwb.spectral.aggregate_to_db")(
        power, baseline, how="mean_of_ratios"
    )


def call_complex_tfr(dtype):
    """``BY_REQUEST``: the request, not the input, decides the output."""
    rng = np.random.default_rng(SEED)
    data = rng.standard_normal(512)
    requested = np.complex64 if np.dtype(dtype) == np.float32 else np.complex128
    return resolve("jnwb.tfr.complex_tfr")(
        data, fs=500.0, freqs=np.array([10.0, 20.0]), dtype=requested
    )


def call_vflip(dtype):
    psd, freqs = _psd(dtype)
    return resolve("jnwb.laminar.vflip")(psd, freqs, contact_spacing=100.0)


def call_cluster_permutation_test(dtype):
    rng = np.random.default_rng(SEED)
    X = rng.standard_normal((20, 30)).astype(dtype)
    Y = (rng.standard_normal((20, 30)) + 0.6).astype(dtype)
    return resolve("jnwb.statistics.cluster_permutation_test")(
        X, Y, n_permutations=50, rng=0
    )


def call_directed_network(dtype):
    rng = np.random.default_rng(SEED)
    return resolve("jnwb.connectivity.directed_network")(
        rng.standard_normal((4, 500)).astype(dtype), method="granger", n_jobs=1
    )


def _linear_geometry(n_channels=24, pitch_um=100.0):
    """A real ProbeGeometry, built by the library's own constructor.

    Deliberately not a stub with ``is_linear = True`` pinned on it. A hand-rolled object
    would satisfy the guard without being a linear shaft, and a fixture that does not
    build the case it is named after will agree with whatever it is pointed at.
    """
    electrodes = pd.DataFrame(
        {
            "id": np.arange(n_channels, dtype=np.int64),
            "x": np.zeros(n_channels),
            "y": np.zeros(n_channels),
            "z": np.arange(n_channels, dtype=float) * pitch_um,
            "location": ["V1"] * n_channels,
        }
    )
    geometry = resolve("jnwb.probe_geometry")(electrodes, units="um")
    assert geometry.is_linear, "the fixture did not build a linear shaft"
    return geometry


def call_label_layers(dtype):
    psd, freqs = _psd(dtype)
    result = resolve("jnwb.laminar.vflip")(psd, freqs, contact_spacing=100.0)
    return resolve("jnwb.laminar.label_layers")(result, _linear_geometry())


def call_build_permutation_plan(dtype):
    return resolve("jnwb.permutation.build_permutation_plan")(
        np.arange(20) % 2, np.arange(20) // 5, n_permutations=10, rng=0
    )


def call_enrich_units_dataframe(dtype):
    units, electrodes = _units_frames(dtype)
    return resolve("jnwb.addressing.enrich_units_dataframe")(
        units, electrodes, depth_unit="um"
    )


def call_tfr_accumulator(dtype):
    """``DOUBLE_ONLY``: the accumulators themselves, so the sweep can see their dtypes."""
    accumulator = resolve("jnwb.tfr_accumulator.TFRAccumulator")((2, 3, 4))
    return {
        "mean": accumulator.mean,
        "M2": accumulator.M2,
        "sum_z": accumulator.sum_z,
        "sum_unit_z": accumulator.sum_unit_z,
    }


#: dotted name -> how to invoke it at a given input dtype. Keys must match the registry
#: exactly; ``test_every_registry_entry_has_a_live_caller`` enforces that.
CALLERS = {
    "jnwb.gpu_pca.gpu_pca": call_gpu_pca,
    "jnwb.spectral.to_db": call_to_db,
    "jnwb.spectral.aggregate_to_db": call_aggregate_to_db,
    "jnwb.tfr.complex_tfr": call_complex_tfr,
    "jnwb.tfr_accumulator.TFRAccumulator": call_tfr_accumulator,
    "jnwb.laminar.vflip": call_vflip,
    "jnwb.statistics.cluster_permutation_test": call_cluster_permutation_test,
    "jnwb.connectivity.directed_network": call_directed_network,
    "jnwb.laminar.label_layers": call_label_layers,
    "jnwb.permutation.build_permutation_plan": call_build_permutation_plan,
    "jnwb.addressing.enrich_units_dataframe": call_enrich_units_dataframe,
}


# --------------------------------------------------------------- registry shape


def test_every_registry_entry_has_a_live_caller():
    """The registry cannot claim a policy for something this file never calls."""
    assert set(CALLERS) == set(PRECISION_POLICY), (
        "registry and caller table disagree; missing callers "
        f"{sorted(set(PRECISION_POLICY) - set(CALLERS))}, orphan callers "
        f"{sorted(set(CALLERS) - set(PRECISION_POLICY))}"
    )


def test_every_policy_is_one_of_the_declared_kinds():
    unknown = {k: v for k, v in PRECISION_POLICY.items() if v not in PRECISION_POLICIES}
    assert not unknown, f"registry names policies that do not exist: {unknown}"


def test_every_registry_key_resolves():
    for dotted in PRECISION_POLICY:
        assert resolve(dotted) is not None, f"{dotted} does not import"


def test_the_registry_covers_more_than_one_policy():
    """A registry collapsed to a single policy would pass every check below vacuously."""
    assert len(set(PRECISION_POLICY.values())) >= 4, (
        f"registry states only {sorted(set(PRECISION_POLICY.values()))}"
    )


# ------------------------------------------------------- the policies hold live


@pytest.mark.parametrize("dotted", sorted(PRECISION_POLICY))
def test_declared_policy_matches_live_behaviour(dotted):
    """Read the policy from the registry, then hold the live function to it."""
    policy = PRECISION_POLICY[dotted]
    call = CALLERS[dotted]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out32 = float_dtypes(call(np.float32))
        out64 = float_dtypes(call(np.float64))

    single = np.dtype(np.float32)
    double = np.dtype(np.float64)
    csingle = np.dtype(np.complex64)
    cdouble = np.dtype(np.complex128)

    if policy == NO_FLOAT_OUTPUT:
        assert not out32 and not out64, (
            f"{dotted} is registered {NO_FLOAT_OUTPUT} but returned float fields "
            f"{sorted(map(str, out32 | out64))}"
        )
    elif policy == PRESERVES_INPUT:
        assert out32, f"{dotted} returned no float field to check"
        assert out32 <= {single, csingle}, (
            f"{dotted} is registered {PRESERVES_INPUT} but float32 input produced "
            f"{sorted(map(str, out32))}"
        )
        assert out64 <= {double, cdouble}, (
            f"{dotted} is registered {PRESERVES_INPUT} but float64 input produced "
            f"{sorted(map(str, out64))}"
        )
    elif policy in (ALWAYS_DOUBLE, DOUBLE_ONLY):
        assert out32, f"{dotted} returned no float field to check"
        assert out32 <= {double, cdouble}, (
            f"{dotted} is registered {policy} but float32 input produced "
            f"{sorted(map(str, out32))}"
        )
        assert out32 == out64, (
            f"{dotted} is registered {policy} but its output dtype moved with "
            f"the input: {sorted(map(str, out32))} vs {sorted(map(str, out64))}"
        )
    elif policy == BY_REQUEST:
        # The request governs the transform's own coefficients. Coordinate and parameter
        # arrays travelling alongside them -- `freqs`, `times`, `n_cycles` on a ComplexTFR
        # -- stay float64 and are right to: they describe where the coefficients sit, not
        # what they are, and downcasting a frequency axis buys nothing and loses ticks.
        # So this checks the complex kind, and asserts separately that the real-valued
        # companions did NOT move, which is what makes the scoping a claim rather than an
        # excuse for whatever the function happened to do.
        complex32 = {d for d in out32 if d.kind == "c"}
        complex64_out = {d for d in out64 if d.kind == "c"}
        assert complex32 == {csingle}, (
            f"{dotted} is registered {BY_REQUEST} but a complex64 request produced "
            f"complex fields {sorted(map(str, complex32))}"
        )
        assert complex64_out == {cdouble}, (
            f"{dotted} is registered {BY_REQUEST} but a complex128 request produced "
            f"complex fields {sorted(map(str, complex64_out))}"
        )
        real32 = {d for d in out32 if d.kind == "f"}
        assert real32 <= {double}, (
            f"{dotted}: the request moved a real-valued coordinate array to "
            f"{sorted(map(str, real32))}; coordinates are float64 regardless of the request"
        )


# ------------------------------------------------- P-136: the refusal, and its non-vacuity


def test_a_32_bit_request_is_refused_not_silently_upcast():
    """P-136. 32-bit Welford misses the accumulator's documented rtol=1e-8 by 43x-33973x."""
    TFRAccumulator = resolve("jnwb.tfr_accumulator.TFRAccumulator")
    for requested in (np.float32, np.complex64):
        with pytest.raises(PrecisionNotSupportedError) as excinfo:
            TFRAccumulator((2, 3, 4), dtype=requested)
        message = str(excinfo.value)
        assert "1e-8" in message, "the refusal does not name the tolerance it would breach"
        for figure in ("43x", "33973x"):
            assert figure in message, (
                f"the refusal does not carry the measured figure {figure}; a refusal "
                "without its measurement is an assertion, not evidence"
            )
        assert np.dtype(requested).name in message, (
            "the refusal does not name the precision that was asked for"
        )


def test_a_double_request_is_accepted():
    """Non-vacuity guard: the refusal discriminates, it is not 'always raise'."""
    TFRAccumulator = resolve("jnwb.tfr_accumulator.TFRAccumulator")
    for requested in (np.float64, np.complex128, None):
        accumulator = TFRAccumulator((2, 3, 4), dtype=requested)
        assert accumulator.mean.dtype == np.dtype(np.float64)
        assert accumulator.sum_z.dtype == np.dtype(np.complex128)


def test_the_default_accumulator_is_unchanged():
    """The repair adds a keyword; it does not move the default."""
    TFRAccumulator = resolve("jnwb.tfr_accumulator.TFRAccumulator")
    accumulator = TFRAccumulator((2, 3, 4))
    assert accumulator.mean.dtype == np.dtype(np.float64)
    assert accumulator.M2.dtype == np.dtype(np.float64)
    assert accumulator.sum_z.dtype == np.dtype(np.complex128)
    assert accumulator.sum_unit_z.dtype == np.dtype(np.complex128)
    assert accumulator.n.dtype == np.dtype(np.int64)


# ------------------------------------- P-137 and P-145: one rule, every return path


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize(
    "shape,n_components,path",
    [
        ((20, 5), 3, "non-empty, unpadded"),
        ((0, 5), 3, "empty by samples"),
        ((20, 0), 3, "empty by features"),
        ((2, 5), 4, "padded, actual < requested"),
        ((5, 2), 4, "padded by features"),
    ],
)
def test_gpu_pca_dtype_does_not_depend_on_which_path_ran(dtype, shape, n_components, path):
    """P-137 (empty early return) and P-145 (padding), which share one cause.

    Output dtype must follow the input, not the path. Before the repair an empty or padded
    float32 matrix returned float64 while the same matrix non-empty returned float32.
    """
    gpu_pca = resolve("jnwb.gpu_pca.gpu_pca")
    matrix = np.zeros(shape, dtype)
    if matrix.size:
        matrix = np.random.default_rng(SEED).standard_normal(shape).astype(dtype)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        projections, components, _ = gpu_pca(matrix, n_components=n_components, device="cpu")
    expected = resolve_working_dtype(dtype)
    assert projections.dtype == expected, (
        f"{path}: projections came back {projections.dtype}, expected {expected}"
    )
    assert components.dtype == expected, (
        f"{path}: components came back {components.dtype}, expected {expected}"
    )


def test_gpu_pca_agrees_across_paths_for_one_dtype():
    """The discriminating shape: same input dtype, three paths, one output dtype."""
    gpu_pca = resolve("jnwb.gpu_pca.gpu_pca")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rng = np.random.default_rng(SEED)
        dense = gpu_pca(rng.standard_normal((20, 5)).astype(np.float32),
                        n_components=3, device="cpu")[0].dtype
        empty = gpu_pca(np.zeros((0, 5), np.float32), n_components=3, device="cpu")[0].dtype
        padded = gpu_pca(rng.standard_normal((2, 5)).astype(np.float32),
                         n_components=4, device="cpu")[0].dtype
    assert dense == empty == padded == np.dtype(np.float32), (
        f"one float32 input, three dtypes: dense={dense}, empty={empty}, padded={padded}"
    )


# ------------------------------------------------------------- the shared rule


@pytest.mark.parametrize(
    "given,expected",
    [
        (np.float32, np.float32),
        (np.float64, np.float64),
        (np.float16, np.float64),
        (np.int32, np.float64),
        (np.int64, np.float64),
    ],
)
def test_resolve_working_dtype_is_the_stated_rule(given, expected):
    assert resolve_working_dtype(given) == np.dtype(expected)
