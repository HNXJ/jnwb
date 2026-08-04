"""
Deterministic mock-corpus test for the directed connectivity estimators.

Builds a synthetic dataset shaped like the real one --
``(condition, trial, channel, sample)`` -- with a directed graph planted in it,
and asks each estimator to recover that graph. Nothing here touches NWB, so it
runs anywhere and always gives the same numbers.

Planted structure (see :func:`make_mock`):

    drv  -> tgt   real directed edge, in condition 'omission' only
    vc_a <-> vc_b one shared source at ZERO lag: correlated, not directed
    every other ordered pair: null

Two properties of the generator matter as much as the graph itself:

* The driver is a **causally generated** AR(2) resonator, not FFT-masked band
  noise. A non-causally filtered driver is not fully predictable from its own
  past, so the target's past adds information and reverse Granger becomes
  spuriously significant (measured: p = 0.000 for a driver that truly has no
  input). That is the "filtering distorts lag structure" hazard, and it is a
  property of the *stimulus construction*, not of the estimator.
* An AR(2) resonance is broad enough for the phase slope index (measured
  jackknife z = 22 at r = 0.8) while a near-pure tone is not.

Author: Claude Code
Date: 2026-08-04
"""

import numpy as np
import pytest

from jnwb import (
    directed_connectivity,
    directed_network,
    granger,
    phase_slope_index,
)

FS = 200.0                  # Hz
BAND = (14.0, 30.0)         # the resonator sits at 20 Hz, inside beta
DELAY = 2                   # samples; 10 ms at 200 Hz
RESONANCE_HZ = 20.0
POLE_RADIUS = 0.80          # broad enough for PSI, narrow enough to be an oscillation

CONDITIONS = ("omission", "control")
CHANNELS = ("drv", "tgt", "vc_a", "vc_b")

#: ordered pairs that genuinely carry a directed influence, per condition
GROUND_TRUTH = {"omission": {("drv", "tgt")}, "control": set()}

# Estimator settings used throughout. Kept in one place so the mock is
# reproducible from the test file alone.
METHOD_KWARGS = {
    "granger": dict(order=4),
    "granger_spectral": dict(fs=FS, order=4, n_freqs=256),
    "psi": dict(fs=FS, bands=BAND, nperseg=128),
    # 49 surrogates gives exact p-values on a 1/50 grid — enough resolution for
    # every alpha=0.05 assertion here, and it halves the suite's runtime.
    "transfer_entropy": dict(k=1, l=1, delay=DELAY, bins=4, n_surrogates=49, seed=0),
}
ALL_METHODS = tuple(METHOD_KWARGS)


def _resonator(rng, n_trials, n_samples, fs=FS, hz=RESONANCE_HZ, r=POLE_RADIUS):
    """
    AR(2) with complex poles at ``r * exp(+-2j*pi*hz/fs)``: an oscillation at
    ``hz`` with a Lorentzian width set by ``r``. Causal by construction, so its
    own past is a sufficient predictor and reverse GC is genuinely null.
    """
    theta = 2 * np.pi * hz / fs
    a1, a2 = 2 * r * np.cos(theta), -(r ** 2)
    out = np.zeros((n_trials, n_samples))
    innov = rng.normal(0, 1, (n_trials, n_samples))
    for t in range(2, n_samples):
        out[:, t] = a1 * out[:, t - 1] + a2 * out[:, t - 2] + innov[:, t]
    return out


def make_mock(n_trials=20, n_samples=400, noise=0.5, seed=0):
    """
    Deterministic mock corpus.

    Returns:
        (data, meta) with ``data`` shaped
        ``(n_conditions, n_trials, n_channels, n_samples)`` and ``meta`` carrying
        conditions, channels, fs, the planted delay, and the ground-truth edges.
    """
    rng = np.random.default_rng(seed)
    n_cond, n_chan = len(CONDITIONS), len(CHANNELS)
    data = np.empty((n_cond, n_trials, n_chan, n_samples))

    for ci, condition in enumerate(CONDITIONS):
        drv = _resonator(rng, n_trials, n_samples)

        tgt = np.zeros_like(drv)
        if condition == "omission":
            # real directed edge: tgt's present depends on drv's past
            innov = rng.normal(0, 1, (n_trials, n_samples))
            for t in range(DELAY, n_samples):
                tgt[:, t] = 0.5 * tgt[:, t - 1] + 0.6 * drv[:, t - DELAY] + innov[:, t]
        else:
            # same marginal statistics, no coupling
            tgt = _resonator(rng, n_trials, n_samples)

        # volume conduction: one source seen twice at zero lag
        shared = _resonator(rng, n_trials, n_samples)
        vc_a = shared + noise * rng.normal(0, 1, (n_trials, n_samples))
        vc_b = 0.9 * shared + noise * rng.normal(0, 1, (n_trials, n_samples))

        for chi, channel in enumerate([drv, tgt, vc_a, vc_b]):
            data[ci, :, chi, :] = channel

    meta = {
        "conditions": list(CONDITIONS),
        "channels": list(CHANNELS),
        "fs": FS,
        "delay_samples": DELAY,
        "resonance_hz": RESONANCE_HZ,
        "ground_truth": GROUND_TRUTH,
        "shape": "(condition, trial, channel, sample)",
    }
    return data, meta


def slab(data, meta, condition, channel):
    """``(n_trials, n_samples)`` for one condition and channel."""
    return data[meta["conditions"].index(condition), :,
                meta["channels"].index(channel), :]


@pytest.fixture(scope="module")
def mock():
    return make_mock()


# ---------------------------------------------------------------------------
# the mock itself
# ---------------------------------------------------------------------------

def test_mock_shape_and_determinism():
    data, meta = make_mock()
    assert data.shape == (2, 20, 4, 400)
    assert meta["shape"] == "(condition, trial, channel, sample)"
    again, _ = make_mock()
    assert np.array_equal(data, again)          # same seed, same bytes
    other, _ = make_mock(seed=1)
    assert not np.array_equal(data, other)      # and the seed actually matters


def test_mock_driver_is_causal_so_reverse_granger_is_null(mock):
    """
    The property the whole test rests on. If the driver were non-causally
    filtered, its own past would not suffice and reverse GC would fire.
    """
    data, meta = mock
    res = granger(slab(data, meta, "omission", "drv"),
                  slab(data, meta, "omission", "tgt"), order=4)
    assert res.p_x_to_y < 1e-6      # the planted edge
    assert res.p_y_to_x > 0.05      # and nothing coming back


def test_mock_resonance_is_broad_enough_for_psi(mock):
    data, meta = mock
    res = phase_slope_index(slab(data, meta, "omission", "drv"),
                            slab(data, meta, "omission", "tgt"),
                            fs=FS, bands=BAND, nperseg=128)
    assert res.per_band["band"]["z"] > 10


# ---------------------------------------------------------------------------
# recovery of the planted graph
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", ALL_METHODS)
def test_recovers_planted_edge_direction(mock, method):
    data, meta = mock
    res = directed_connectivity(slab(data, meta, "omission", "drv"),
                                slab(data, meta, "omission", "tgt"),
                                method=method, **METHOD_KWARGS[method])
    assert res.x_to_y > res.y_to_x
    assert res.net > 0


@pytest.mark.parametrize("method", ALL_METHODS)
def test_edge_is_condition_specific(mock, method):
    """Present in 'omission', absent in 'control' — the contrast the corpus asks for."""
    data, meta = mock
    kw = METHOD_KWARGS[method]
    om = directed_connectivity(slab(data, meta, "omission", "drv"),
                               slab(data, meta, "omission", "tgt"), method=method, **kw)
    ct = directed_connectivity(slab(data, meta, "control", "drv"),
                               slab(data, meta, "control", "tgt"), method=method, **kw)
    assert abs(om.net) > 5 * abs(ct.net)


@pytest.mark.parametrize("method", ALL_METHODS)
def test_zero_lag_shared_source_is_not_reported_as_directed(mock, method):
    """
    vc_a and vc_b are strongly correlated and carry no direction. This is the
    volume-conduction / shared-reference case, and it is the one that
    manufactures whole spurious networks if an estimator gets it wrong.
    """
    data, meta = mock
    kw = METHOD_KWARGS[method]
    vc = directed_connectivity(slab(data, meta, "omission", "vc_a"),
                               slab(data, meta, "omission", "vc_b"), method=method, **kw)
    real = directed_connectivity(slab(data, meta, "omission", "drv"),
                                 slab(data, meta, "omission", "tgt"), method=method, **kw)
    assert abs(vc.net) < 0.25 * abs(real.net)


@pytest.mark.parametrize("method", ALL_METHODS)
def test_whole_graph_recovery(mock, method):
    """All 12 ordered pairs at once: the planted edge must be the strongest."""
    data, meta = mock
    signals = {ch: slab(data, meta, "omission", ch) for ch in CHANNELS}
    net = directed_network(signals, method=method, **METHOD_KWARGS[method])
    labels, matrix = net["labels"], net["matrix"]
    off_diagonal = ~np.eye(len(labels), dtype=bool)
    strongest = np.unravel_index(
        np.nanargmax(np.where(off_diagonal, matrix, np.nan)), matrix.shape
    )
    assert (labels[strongest[0]], labels[strongest[1]]) == ("drv", "tgt")


@pytest.mark.parametrize("method", ALL_METHODS)
def test_estimators_are_bit_identical_on_repeat(mock, method):
    data, meta = mock
    kw = METHOD_KWARGS[method]
    x, y = slab(data, meta, "omission", "drv"), slab(data, meta, "omission", "tgt")
    a = directed_connectivity(x, y, method=method, **kw)
    b = directed_connectivity(x, y, method=method, **kw)
    assert a.x_to_y == b.x_to_y
    assert a.y_to_x == b.y_to_x
    assert a.p_x_to_y == b.p_x_to_y


# ---------------------------------------------------------------------------
# reliability: error rates across independent realizations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", ["granger", "psi", "transfer_entropy"])
def test_false_positive_and_detection_rates(method):
    """
    Correctness on one dataset is not reliability. Across independent draws the
    estimator must find the planted edge nearly always and the absent edge
    almost never.
    """
    n_reps, alpha = 12, 0.05
    kw = dict(METHOD_KWARGS[method])
    false_positives = 0
    detections = 0
    for rep in range(n_reps):
        data, meta = make_mock(seed=2000 + rep)
        null = directed_connectivity(slab(data, meta, "control", "drv"),
                                     slab(data, meta, "control", "tgt"),
                                     method=method, **kw)
        signal = directed_connectivity(slab(data, meta, "omission", "drv"),
                                       slab(data, meta, "omission", "tgt"),
                                       method=method, **kw)
        false_positives += null.p_x_to_y <= alpha
        detections += signal.p_x_to_y <= alpha
    assert false_positives <= 2, f"{method}: {false_positives}/{n_reps} false positives"
    assert detections == n_reps, f"{method}: detected {detections}/{n_reps}"


def test_granger_reverse_direction_is_null_across_realizations():
    """
    GC and TE give a genuine per-direction test, so the wrong direction must
    stay null across draws. (PSI is excluded on purpose — see the next test.)
    """
    n_reps = 12
    wrong_direction_hits = 0
    for rep in range(n_reps):
        data, meta = make_mock(seed=3000 + rep)
        res = granger(slab(data, meta, "omission", "drv"),
                      slab(data, meta, "omission", "tgt"), order=4)
        wrong_direction_hits += res.p_y_to_x <= 0.05
    assert wrong_direction_hits <= 2, f"{wrong_direction_hits}/{n_reps} reverse hits"


def test_psi_reports_one_test_not_two(mock):
    """
    PSI is antisymmetric, so it has a single test and the direction is the sign.
    Reading p_y_to_x as an independent reverse test would report a significant
    lead in both directions at once.
    """
    data, meta = mock
    res = phase_slope_index(slab(data, meta, "omission", "drv"),
                            slab(data, meta, "omission", "tgt"),
                            fs=FS, bands=BAND, nperseg=128)
    assert res.p_x_to_y == res.p_y_to_x
    assert res.diagnostics["p_covers_both_directions"] is True
    assert res.x_to_y == -res.y_to_x


def test_shared_latent_with_observation_noise_is_bidirectional_by_construction():
    """
    Documented limitation, not a defect. When two channels are noisy views of one
    latent source, each channel's past carries information about the other's
    present that the other's own past does not, so GC is legitimately
    bidirectional. Every channel on a real probe is such a view, which is why
    the corpus needs bipolar derivation before cross-site GC is interpretable.
    """
    rng = np.random.default_rng(0)
    latent = _resonator(rng, 20, 400)
    a = latent + 0.6 * rng.normal(0, 1, (20, 400))
    b = np.roll(latent, DELAY, axis=1) + 0.6 * rng.normal(0, 1, (20, 400))
    res = granger(a, b, order=4)
    assert res.x_to_y > res.y_to_x          # the lag is still recovered
    assert res.p_y_to_x < 0.05              # but the reverse is NOT null
