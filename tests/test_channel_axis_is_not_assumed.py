"""A time-major array must not be read as channel-major and returned as a finite answer.

Three consumers accepted a transposed array silently. The defect is not that the number was
slightly wrong -- it is that the wrong answer is *finite, plausible and load-bearing*:

* ``bandpass_filter`` defaults ``axis=-1`` and ``current_source_density_1d`` defaults
  ``axis=0``, so the obvious two-call chain differentiates along time and divides by a pitch
  in micrometres. On 64x6000 the RMS ratio was 0.108993, a 9.17x discrepancy. The ratio is
  fixture-dependent: on temporally white noise it is 1.86 and looks like rounding, while on
  the physically correct 1/f shape it is 0.109.
* ``channel_correlation_matrix`` on a (6000, 64) array returned a (6000, 6000) matrix, and
  ``bad_channels_from_correlation`` reported a 6000-entry verdict flagging 0 "channels" -- a
  safety check that cannot fail, read downstream as evidence the data is clean.

Both directions are asserted separately, because either one alone is a proxy. A test that
only pins the refusal passes on a function that refuses everything; a test that only pins the
good-layout answer passes on the unrepaired code. The bounds are also asserted to be
physical rather than tuned: a 384-contact probe -- the densest in wide use -- must pass.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# append, never insert(0): `pyproject.toml` already sets pytest's pythonpath, and shadowing it
# would make this module test the checkout while the wheel leg believes it tested the wheel.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from jnwb._layout import MAX_LAMINAR_CHANNELS, MAX_PROBE_SPAN_UM  # noqa: E402
from jnwb.artifact_detection import (  # noqa: E402
    bad_channels_from_correlation,
    channel_correlation_matrix,
)
from jnwb.filtering import bandpass_filter  # noqa: E402
from jnwb.spectral import current_source_density_1d, voltage_curvature_1d  # noqa: E402

N_CHANNELS = 64
N_TIMES = 6000
PITCH_UM = 20.0
CONDUCTIVITY = 0.3


def _pink(n_channels: int, n_times: int, seed: int = 7) -> np.ndarray:
    """Channel-major noise with a 1/f spectrum -- the shape that makes the defect severe.

    On temporally white noise the transposed RMS ratio is 1.86 and reads as rounding; the
    fixture spectrum is therefore part of what is under test, not incidental.
    """
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((n_channels, n_times))
    spectrum = np.fft.rfft(white, axis=-1)
    freqs = np.fft.rfftfreq(n_times)
    scale = np.ones_like(freqs)
    scale[1:] = 1.0 / np.sqrt(freqs[1:])
    return np.fft.irfft(spectrum * scale, n=n_times, axis=-1)


# --------------------------------------------------------------------------------------
# The good layout still works, and works unchanged.
# --------------------------------------------------------------------------------------

def test_channel_major_curvature_is_unchanged_and_finite():
    data = _pink(N_CHANNELS, N_TIMES)
    curvature = voltage_curvature_1d(data, pitch_um=PITCH_UM, axis=0)
    assert curvature.shape == (N_CHANNELS - 2, N_TIMES)
    assert np.all(np.isfinite(curvature))


def test_channel_major_csd_is_unchanged_and_finite():
    data = _pink(N_CHANNELS, N_TIMES)
    csd = current_source_density_1d(
        data, pitch_um=PITCH_UM, conductivity_s_per_m=CONDUCTIVITY, axis=0
    )
    assert csd.shape == (N_CHANNELS - 2, N_TIMES)
    assert np.all(np.isfinite(csd))
    # The physical relation is untouched by the guard.
    curvature = voltage_curvature_1d(data, pitch_um=PITCH_UM, axis=0)
    assert np.allclose(csd, -CONDUCTIVITY * curvature, rtol=0, atol=0)


def test_channel_major_correlation_is_unchanged():
    data = _pink(N_CHANNELS, N_TIMES)
    corr = channel_correlation_matrix(data)
    assert corr.shape == (N_CHANNELS, N_CHANNELS)
    bad, summary, z = bad_channels_from_correlation(corr)
    assert bad.shape == (N_CHANNELS,)
    assert summary.shape == (N_CHANNELS,)
    assert z.shape == (N_CHANNELS,)


def test_a_time_major_array_passed_with_the_right_axis_is_accepted():
    """The guard refuses a wrong *axis*, not a wrong memory layout.

    A caller who genuinely holds `(n_times, n_channels)` and says so must be served, or the
    repair would have replaced a silent wrong answer with a false refusal.
    """
    data = _pink(N_CHANNELS, N_TIMES).T
    assert data.shape == (N_TIMES, N_CHANNELS)
    curvature = voltage_curvature_1d(data, pitch_um=PITCH_UM, axis=1)
    assert curvature.shape == (N_TIMES, N_CHANNELS - 2)
    assert np.all(np.isfinite(curvature))


# --------------------------------------------------------------------------------------
# The transposed layout is refused, at each of the three entry points.
# --------------------------------------------------------------------------------------

def test_the_filter_then_csd_chain_refuses_instead_of_returning_nonsense():
    """The exact two-call chain that produced the 9.17x discrepancy.

    `bandpass_filter` defaults axis=-1 and `current_source_density_1d` defaults axis=0, so
    this reads as correct code. Before the repair it returned a finite array.
    """
    data = _pink(N_CHANNELS, N_TIMES)
    filtered = bandpass_filter(data, 500.0, 10.0, 100.0)
    with pytest.raises(ValueError, match="contact limit for a laminar axis"):
        current_source_density_1d(
            filtered.T, pitch_um=PITCH_UM, conductivity_s_per_m=CONDUCTIVITY
        )


def test_time_major_curvature_refuses():
    data = _pink(N_CHANNELS, N_TIMES).T
    with pytest.raises(ValueError, match="time-major"):
        voltage_curvature_1d(data, pitch_um=PITCH_UM)


def test_time_major_channel_correlation_refuses():
    data = _pink(N_CHANNELS, N_TIMES).T
    with pytest.raises(ValueError, match="contact limit for a laminar axis"):
        channel_correlation_matrix(data)


def test_the_refusal_names_the_argument_that_fixes_it():
    """A refusal that does not say what to change trades a wrong answer for a dead end."""
    data = _pink(N_CHANNELS, N_TIMES).T
    with pytest.raises(ValueError) as excinfo:
        voltage_curvature_1d(data, pitch_um=PITCH_UM)
    message = str(excinfo.value)
    assert "axis=" in message
    assert str(N_TIMES) in message
    assert str(N_CHANNELS) in message


# --------------------------------------------------------------------------------------
# The bounds are physical, not tuned. A real device must pass; only a sample count fails.
# --------------------------------------------------------------------------------------

def test_the_densest_real_probe_is_accepted():
    """384 simultaneously recorded sites at 20 um -- Neuropixels 1.0, a 7.66 mm shank."""
    data = _pink(384, 512)
    curvature = voltage_curvature_1d(data, pitch_um=PITCH_UM, axis=0)
    assert curvature.shape == (382, 512)
    assert 384 <= MAX_LAMINAR_CHANNELS
    assert PITCH_UM * 383 < MAX_PROBE_SPAN_UM


def test_the_span_bound_catches_a_transposition_the_count_bound_would_miss():
    """The two bounds are independent, so a pitch choice cannot slip a transposition through.

    A channel count under the contact limit can still imply an impossible shank. Without the
    span bound this array would be accepted and differentiated along time.
    """
    n_ch = MAX_LAMINAR_CHANNELS - 24
    data = _pink(8, n_ch)
    assert data.shape[1] <= MAX_LAMINAR_CHANNELS  # the count bound does not fire
    impossible_pitch = (MAX_PROBE_SPAN_UM / (n_ch - 1)) * 2.0
    with pytest.raises(ValueError, match="above the .* mm limit"):
        voltage_curvature_1d(data, pitch_um=impossible_pitch, axis=1)


def test_a_pitch_within_the_span_bound_is_accepted():
    """The span bound's own negative case, so it is not passing by always firing."""
    n_ch = MAX_LAMINAR_CHANNELS - 24
    data = _pink(8, n_ch)
    fine_pitch = (MAX_PROBE_SPAN_UM / (n_ch - 1)) * 0.5
    curvature = voltage_curvature_1d(data, pitch_um=fine_pitch, axis=1)
    assert curvature.shape == (8, n_ch - 2)
