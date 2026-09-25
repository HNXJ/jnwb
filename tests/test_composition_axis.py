"""Axis conventions across a composition boundary, not within one function (06-21).

Three chains from the declared high-risk subset, each a producer whose output axis order is
the consumer's input axis order only by convention:

    H2  bandpass_filter        -> current_source_density_1d, voltage_curvature_1d
    H3  a trials-by-time array -> granger, granger_spectral, transfer_entropy,
                                  phase_slope_index
    H4  channel_correlation_matrix -> bad_channels_from_correlation

**Every fixture here has deliberately unequal dimensions** -- 64 x 6000, 7 x 400. That is the
whole point of the item rather than a detail of it: on a square fixture a transposed array has
the same shape as a correct one, so every assertion below would pass on the defect it exists to
catch. A future edit that rounds 6000 down to 64 for speed silently disarms this module.

The nearest existing coverage of H2 is `test_axis_convention_matches_the_specification.py`,
whose `cross_convention_hops` is a static scan over source text: it executes nothing and lists
`current_source_density_1d` only as a producer, never as a consumer. These tests execute the
pair on arrays instead.

**Legs that fail today carry `xfail(strict=True)`**, so repairing the defect makes the test fail
and forces the marker off. A non-strict marker would let the repair land unnoticed; a weakened
assertion would let the defect land unnoticed.

Provenance: which `jnwb` this suite imported is asserted once, in
`test_import_provenance.py`, which is the only module allowed to make that assertion because it
is the only one that honours `JNWB_EXPECTED_PACKAGE_ROOT` and so works both for this checkout
and for a run qualifying an installed copy. This module reports the path it measured in its
failure messages instead of asserting it a second time.
"""

from __future__ import annotations

import numpy as np
import pytest

import jnwb

# --------------------------------------------------------------------------------------
# Fixtures. Unequal dimensions everywhere, so a transpose cannot pass by coincidence.
# --------------------------------------------------------------------------------------

N_CHANNELS = 64
N_SAMPLES = 6000
N_TRIALS = 7
N_TIMES = 400

FS = 1000.0
PITCH_UM = 40.0
CONDUCTIVITY_S_PER_M = 0.3
LOW_CUT, HIGH_CUT = 10.0, 40.0

assert N_CHANNELS != N_SAMPLES, "the laminar fixture must not be square"
assert N_TRIALS != N_TIMES, "the trial fixture must not be square"


def _where_jnwb_came_from() -> str:
    return f"(jnwb under test: {jnwb.__file__})"


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(values, dtype=float) ** 2)))


def _pink_lfp(seed: int = 0) -> np.ndarray:
    """A (n_channels, n_times) LFP with a 1/f temporal spectrum and independent channels.

    The spectrum matters. On temporally white noise a second difference along time is as
    large as one along depth, so the wrong-axis route produces a number of the right order
    and the defect looks mild. Real LFP is strongly autocorrelated in time, which is what
    makes the time-axis derivative collapse and the wrong answer look plausible.
    """
    rng = np.random.default_rng(seed)
    freqs = np.fft.rfftfreq(N_SAMPLES, d=1.0 / FS)
    amplitude = np.ones_like(freqs)
    amplitude[1:] = freqs[1:] ** -1.0
    spectrum = (
        rng.normal(size=(N_CHANNELS, freqs.size))
        + 1j * rng.normal(size=(N_CHANNELS, freqs.size))
    ) * amplitude
    lfp = np.fft.irfft(spectrum, n=N_SAMPLES, axis=1)
    return lfp / np.std(lfp) * 1e-4


def _coupled_trials(seed: int = 0, coupling: float = 1.2) -> tuple[np.ndarray, np.ndarray]:
    """(n_trials, n_times) X and Y, with Y driven by X at a one-sample lag."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(N_TRIALS, N_TIMES))
    y = np.zeros_like(x)
    y[:, 1:] = coupling * x[:, :-1] + 0.5 * rng.normal(size=(N_TRIALS, N_TIMES - 1))
    return x, y


def _channel_major_lfp_with_bad_channels(seed: int = 0) -> tuple[np.ndarray, list[int]]:
    """A (n_channels, n_times) array sharing one common signal, with three dead channels."""
    rng = np.random.default_rng(seed)
    common = rng.normal(size=N_SAMPLES)
    lfp = common[None, :] + 0.3 * rng.normal(size=(N_CHANNELS, N_SAMPLES))
    dead = [7, 23, 55]
    for channel in dead:
        lfp[channel] = rng.normal(size=N_SAMPLES)  # uncorrelated with the probe
    return lfp, dead


# --------------------------------------------------------------------------------------
# H2  bandpass_filter -> current_source_density_1d / voltage_curvature_1d
#
# bandpass_filter defaults to axis=-1 (time-major reading); the two laminar consumers
# default to axis=0 (channel-major reading). The pair is coherent only on a channel-major
# array, and nothing on either side states the assumption.
# --------------------------------------------------------------------------------------

LAMINAR_CONSUMERS = ("current_source_density_1d", "voltage_curvature_1d")


def _laminar(name: str, array: np.ndarray, axis: int | None = None) -> np.ndarray:
    kwargs: dict[str, object] = {"pitch_um": PITCH_UM}
    if name == "current_source_density_1d":
        kwargs["conductivity_s_per_m"] = CONDUCTIVITY_S_PER_M
    if axis is not None:
        kwargs["axis"] = axis
    return getattr(jnwb, name)(array, **kwargs)


def test_h2_the_channel_major_route_differentiates_along_depth() -> None:
    """The reference route, pinned against hand arithmetic rather than against itself.

    Passes while the invariant is violated if: the shape were the only thing checked. A
    (62, 6000) result is also what a depth derivative of the *wrong* filtered array would
    have, so the second difference is recomputed here from the filtered array directly.
    """
    lfp = _pink_lfp()
    filtered = jnwb.bandpass_filter(lfp, fs=FS, low_cut=LOW_CUT, high_cut=HIGH_CUT)
    csd = _laminar("current_source_density_1d", filtered)

    assert csd.shape == (N_CHANNELS - 2, N_SAMPLES), (
        f"the reference route lost the depth axis: {csd.shape} {_where_jnwb_came_from()}"
    )
    pitch_m = PITCH_UM * 1e-6
    by_hand = -CONDUCTIVITY_S_PER_M * (
        filtered[2:, :] - 2.0 * filtered[1:-1, :] + filtered[:-2, :]
    ) / pitch_m**2
    assert np.allclose(csd, by_hand, rtol=1e-9, atol=0.0), (
        "the reference route is not a second difference across contacts at this pitch "
        f"{_where_jnwb_came_from()}"
    )


@pytest.mark.parametrize("consumer", LAMINAR_CONSUMERS)
def test_h2_naming_each_axis_makes_the_two_layouts_agree(consumer: str) -> None:
    """Both layouts are computable; only the *defaults* disagree.

    This separates the defect from a capability gap: the functions can do the right thing on
    a time-major array, so the xfail below is about the silent default, not about a missing
    feature.

    Passes while the invariant is violated if: both sides computed the same wrong thing. The
    test above pins the channel-major side to hand arithmetic, so that is covered.
    """
    lfp = _pink_lfp()
    channel_major = _laminar(
        consumer, jnwb.bandpass_filter(lfp, fs=FS, low_cut=LOW_CUT, high_cut=HIGH_CUT)
    )
    time_major = _laminar(
        consumer,
        jnwb.bandpass_filter(lfp.T, fs=FS, low_cut=LOW_CUT, high_cut=HIGH_CUT, axis=0),
        axis=1,
    )
    assert channel_major.shape == (N_CHANNELS - 2, N_SAMPLES)
    assert time_major.shape == (N_SAMPLES, N_CHANNELS - 2)
    assert np.allclose(channel_major, time_major.T, rtol=1e-9, atol=0.0), (
        f"{consumer} does not agree with itself across layouts when each axis is named "
        f"{_where_jnwb_came_from()}"
    )


@pytest.mark.parametrize("consumer", LAMINAR_CONSUMERS)
def test_h2_the_time_major_default_spelling_must_raise_or_agree(consumer: str) -> None:
    """Measured when P-115 was raised: shape (5998, 64) against (62, 6000), RMS ratio 0.109,
    no error. The strict xfail this carried is removed: `jnwb._layout` refuses the time-major
    spelling on two independent physical bounds, and this test takes a refusal as satisfaction.

    The invariant is that a caller who hands the pair a time-major array is either refused or
    given the same answer up to a transpose. Which of the two is a source decision and is not
    presumed here -- either outcome satisfies this test.

    Passes while the invariant is violated if: the comparison were made on a square fixture,
    where the transposed result has the conformable shape and `allclose` can be reached at
    all. 64 x 6000 makes the shapes themselves disagree.
    """
    lfp = _pink_lfp()
    reference = _laminar(
        consumer, jnwb.bandpass_filter(lfp, fs=FS, low_cut=LOW_CUT, high_cut=HIGH_CUT)
    )

    try:
        time_major = _laminar(
            consumer, jnwb.bandpass_filter(lfp.T, fs=FS, low_cut=LOW_CUT, high_cut=HIGH_CUT)
        )
    except (ValueError, TypeError):
        return  # refused at one end or the other: the invariant holds

    assert time_major.shape == reference.T.shape, (
        f"{consumer} accepted a time-major array and returned {time_major.shape}, which is "
        f"neither a refusal nor the transpose of {reference.shape}; RMS ratio "
        f"{_rms(time_major) / _rms(reference):.6f} {_where_jnwb_came_from()}"
    )
    assert np.allclose(reference, time_major.T, rtol=1e-6, atol=0.0), (
        f"{consumer} returned a finite array of the right shape and the wrong values "
        f"{_where_jnwb_came_from()}"
    )


# --------------------------------------------------------------------------------------
# H3  a trials-by-time array -> the four directed-coupling estimators
#
# Each estimator takes `time_axis`, defaulting to -1. A (n_times, n_trials) array under that
# default is read as n_times trials of n_trials samples.
# --------------------------------------------------------------------------------------

#: The three that return a number on a transposed array. `phase_slope_index` refuses, and is
#: tested separately below -- that asymmetry is a finding, not a gap in this list.
SILENT_ESTIMATORS = ("granger", "granger_spectral", "transfer_entropy")
ALL_ESTIMATORS = SILENT_ESTIMATORS + ("phase_slope_index",)


def _estimator_kwargs(name: str) -> dict[str, object]:
    if name in ("granger_spectral", "phase_slope_index"):
        return {"fs": FS}
    if name == "transfer_entropy":
        return {"n_surrogates": 0}
    return {}


@pytest.mark.parametrize("estimator", ALL_ESTIMATORS)
def test_h3_the_two_time_axis_spellings_are_identical(estimator: str) -> None:
    """`f(X, Y, time_axis=-1)` and `f(X.T, Y.T, time_axis=0)` describe the same data.

    Holds today, bit for bit, for all four. This is the half that says `time_axis` is wired
    correctly wherever it is passed, which is what makes the default the defect rather than
    the parameter.

    Passes while the invariant is violated if: the estimator returned a constant (0.0, say)
    for every input, making any two calls trivially equal. The coupling assertion below rules
    that out -- the reference has to be a real estimate that finds the injected direction.
    """
    x, y = _coupled_trials()
    fn = getattr(jnwb, estimator)
    kwargs = _estimator_kwargs(estimator)

    named_last = fn(x, y, time_axis=-1, **kwargs)
    named_first = fn(x.T, y.T, time_axis=0, **kwargs)

    assert named_last.x_to_y == named_first.x_to_y, (
        f"{estimator} x_to_y differs between the two spellings of the same data: "
        f"{named_last.x_to_y!r} against {named_first.x_to_y!r} {_where_jnwb_came_from()}"
    )
    assert named_last.y_to_x == named_first.y_to_x, (
        f"{estimator} y_to_x differs between the two spellings {_where_jnwb_came_from()}"
    )
    assert named_last.x_to_y > 0.1, (
        f"{estimator} found no forward coupling on a fixture built with it, so the equality "
        f"above compares two degenerate values {_where_jnwb_came_from()}"
    )
    assert named_last.x_to_y > named_last.y_to_x, (
        f"{estimator} does not recover the injected direction {_where_jnwb_came_from()}"
    )


def test_h3_as_trials_reads_the_named_axis_and_a_transpose_swaps_the_meaning() -> None:
    """The mechanism the estimators inherit, pinned on its own.

    Passes while the invariant is violated if: the fixture were square, where (7, 400) and
    (400, 7) are the same shape and the last assertion cannot distinguish them.
    """
    x, _ = _coupled_trials()

    assert jnwb.as_trials(x, time_axis=-1).shape == (N_TRIALS, N_TIMES)
    assert np.array_equal(
        jnwb.as_trials(x, time_axis=-1), jnwb.as_trials(x.T, time_axis=0)
    ), f"as_trials disagrees with itself across the two spellings {_where_jnwb_came_from()}"
    assert jnwb.as_trials(x.T).shape == (N_TIMES, N_TRIALS), (
        "a transposed array under the default is no longer read as "
        f"{N_TRIALS} trials of {N_TIMES} samples {_where_jnwb_came_from()}"
    )


@pytest.mark.parametrize("estimator", SILENT_ESTIMATORS)
def test_h3_a_transposed_trial_array_must_not_read_as_no_coupling(estimator: str) -> None:
    """Measured when P-116 was raised, at 7 x 400: x_to_y 1.90 correct against 1.1e-07
    transposed. The strict xfail this carried is removed: `require_trial_length` refuses a
    trial too short to carry the estimator's own lag structure, which is the quantity pooling
    hid -- 400 trials of 7 samples supply thousands of design rows in total.

    Across six seeds the understatement ranges from 5,147x to 17,716,885x; transfer_entropy
    goes negative on the transposed layout, which a non-negative quantity cannot be.

    The invariant is that the wrong layout is loud. Refusal satisfies it; returning the
    correct estimate satisfies it; quietly returning a near-zero number does not.

    Passes while the invariant is violated if: the threshold were absolute rather than
    relative to the reference. A fixture with weak true coupling would then clear a small
    absolute bar while still having collapsed.
    """
    x, y = _coupled_trials()
    fn = getattr(jnwb, estimator)
    kwargs = _estimator_kwargs(estimator)

    reference = fn(x, y, time_axis=-1, **kwargs)
    assert reference.x_to_y > 0.1, "the fixture has no coupling to understate"

    try:
        transposed = fn(x.T, y.T, **kwargs)
    except (ValueError, TypeError):
        return  # refused: the invariant holds

    assert transposed.x_to_y > 0.5 * reference.x_to_y, (
        f"{estimator} accepted a {x.T.shape} array under the default time_axis and returned "
        f"x_to_y={transposed.x_to_y!r} against {reference.x_to_y!r} -- an understatement of "
        f"{reference.x_to_y / transposed.x_to_y:,.0f}x that reads as no coupling "
        f"{_where_jnwb_came_from()}"
    )


def test_h3_phase_slope_index_refuses_the_transposed_layout() -> None:
    """One of the four consumers is already loud, and that has to stay true.

    `phase_slope_index` reaches a spectral estimate whose segment length is taken from the
    time axis, so a transposed array gives it nperseg=7 and it refuses by name. The other
    three fit a model that is happy with 7 samples and return a number instead.

    This is the half that catches a repair going the wrong way: a change that made the
    spectral path tolerate a 7-sample segment would turn the one loud consumer in this chain
    silent, and nothing else in the suite would notice.

    Passes while the invariant is violated if: any exception were accepted. A typo in the
    keyword arguments raises TypeError and would satisfy a bare `pytest.raises(Exception)`,
    so the correct spelling is required to succeed in the same test and the error type and
    message are both pinned.
    """
    x, y = _coupled_trials()

    correct = jnwb.phase_slope_index(x, y, fs=FS, time_axis=-1)
    assert correct.x_to_y > 0.1, (
        f"the correct spelling did not produce an estimate, so the refusal below is not "
        f"specific to the layout {_where_jnwb_came_from()}"
    )

    with pytest.raises(ValueError, match="nperseg"):
        jnwb.phase_slope_index(x.T, y.T, fs=FS)


# --------------------------------------------------------------------------------------
# H4  channel_correlation_matrix -> bad_channels_from_correlation
#
# The producer correlates rows. Handed a time-major array it correlates time points, and the
# consumer cannot tell a 6000 x 6000 time-point matrix from a channel matrix.
# --------------------------------------------------------------------------------------


def test_h4_the_channel_major_verdict_has_one_entry_per_channel_and_finds_bad_ones() -> None:
    """The reference route, with a verdict that has to be a real verdict.

    Passes while the invariant is violated if: only the length were checked.
    `np.zeros(corr.shape[0], dtype=bool)` has the right length for any input, so three
    uncorrelated channels are injected and must be the ones flagged.
    """
    lfp, dead = _channel_major_lfp_with_bad_channels()
    corr = jnwb.channel_correlation_matrix(lfp)
    bad, summary, _z = jnwb.bad_channels_from_correlation(corr)

    assert corr.shape == (N_CHANNELS, N_CHANNELS), (
        f"the correlation matrix is over {corr.shape[0]} things, not {N_CHANNELS} channels "
        f"{_where_jnwb_came_from()}"
    )
    assert bad.shape == (N_CHANNELS,)
    assert summary.shape == (N_CHANNELS,)
    assert sorted(np.flatnonzero(bad).tolist()) == dead, (
        f"the verdict flagged {np.flatnonzero(bad).tolist()}, not the injected "
        f"{dead} {_where_jnwb_came_from()}"
    )


def test_h4_a_time_major_array_must_not_yield_a_verdict_over_samples() -> None:
    """Measured when P-117 was raised: (6000, 64) in, a (6000, 6000) matrix out, a 6000-entry
    verdict flagging 0 "channels", and no error anywhere. The strict xfail this carried is
    removed: `channel_correlation_matrix` now refuses at the point where rows stop being
    channels. The caller read "no bad channels" from a
    computation that never looked at a channel.

    Either step may be the one that refuses -- where the guard belongs is a source decision
    and is not presumed here.

    Passes while the invariant is violated if: the fixture were square. At 64 x 6000 the
    verdict length alone separates the two readings; at 64 x 64 it cannot.
    """
    lfp, dead = _channel_major_lfp_with_bad_channels()

    try:
        corr = jnwb.channel_correlation_matrix(lfp.T)
        bad, _summary, _z = jnwb.bad_channels_from_correlation(corr)
    except (ValueError, TypeError):
        return  # refused at one end or the other: the invariant holds

    assert bad.shape == (N_CHANNELS,), (
        f"a time-major array produced a verdict of length {bad.shape[0]} over a "
        f"{corr.shape} matrix, flagging {int(np.sum(bad))} of the {len(dead)} bad channels "
        f"actually present {_where_jnwb_came_from()}"
    )
