"""05-85 shape dimension: a declared return shape, checked by calling the function.

A wrong return shape in a docstring is invisible from inside the library. The array is
whatever shape the code makes it, every test of that array passes, and only a reader building
the next step from the documentation is misled -- which is the same failure the axis
specification had, one layer down.

An introspective sweep could not settle this: it could build a call for 3 of 29 candidate
functions, and both disagreements it reported were its own, one from reading an input shape
as a return shape and one from handing a channel-major array to a time-major function. So
these are fixtures, and the dimensions are chosen mutually distinct -- 7 trials, 50 bins,
512 samples, 5 channels -- so that no two axes can be confused for one another and a
transposed return would fail rather than coincide.

Five exported functions declare a named shape in a `Returns:` block.
`build_time_resolved_matrix` and `compute_population_trajectory` each take a live NWB
session and are not constructible here; `TestTheUncoveredTwoAreNamed` keeps that gap stated
rather than implied by their absence. The third, `laplacian_reference`, is pinned in
`tests/test_axis_convention_matches_the_specification.py`, where its axis order is the
subject.
"""

from __future__ import annotations

import inspect
import re

import numpy as np
import pytest

import jnwb

N_TRIALS, N_BINS, N_TIMES = 7, 50, 512

RETURN_SHAPE = re.compile(r"\((n_[a-z_]+(?:,\s*n_[a-z_]+)+)\)")

NEEDS_A_SESSION = ("build_time_resolved_matrix", "compute_population_trajectory")


def returns_block(func) -> str:
    """The `Returns:` section only.

    Deliberately not a search of the whole docstring: a function that describes its input
    shape and not its output would otherwise have the input claim checked against the
    returned array, which is how the sweep this module replaces produced a false finding
    against `bipolar_reference`.
    """
    doc = inspect.getdoc(func) or ""
    lines = doc.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines)
                     if ln.strip() in ("Returns:", "Returns"))
    except StopIteration:
        return ""
    out = []
    for line in lines[start + 1:]:
        if line.strip() and not line.startswith((" ", "\t")):
            break
        out.append(line)
    return "\n".join(out)


def declared_shapes(func) -> list[tuple[str, ...]]:
    return [tuple(a.strip() for a in m.split(","))
            for m in RETURN_SHAPE.findall(returns_block(func))]


class TestBinSpikes:
    def test_it_declares_trials_by_bins(self):
        assert ("n_trials", "n_bins") in declared_shapes(jnwb.bin_spikes)

    def test_it_returns_trials_by_bins(self):
        """Seven trials over a 500 ms window at 10 ms: 7 and 50 cannot be swapped."""
        rng = np.random.default_rng(0)
        spikes = [np.sort(rng.uniform(0.0, 0.5, 20)) for _ in range(N_TRIALS)]
        binned = jnwb.bin_spikes(spikes, window_s=(0.0, 0.5), bin_size_ms=10.0)
        assert binned.shape == (N_TRIALS, N_BINS)

    def test_the_bin_count_follows_the_window_and_width(self):
        """Pins the second axis as bins rather than as a number that happens to be 50."""
        rng = np.random.default_rng(1)
        spikes = [np.sort(rng.uniform(0.0, 0.5, 20)) for _ in range(N_TRIALS)]
        binned = jnwb.bin_spikes(spikes, window_s=(0.0, 0.5), bin_size_ms=25.0)
        assert binned.shape == (N_TRIALS, 20)


class TestDetectBandOutliers:
    def test_it_declares_trials_by_times(self):
        assert ("n_trials", "n_times") in declared_shapes(jnwb.detect_band_outliers)

    def test_it_returns_a_mask_of_trials_by_times(self):
        rng = np.random.default_rng(0)
        flagged, scale = jnwb.detect_band_outliers(
            rng.standard_normal((N_TRIALS, N_TIMES)))
        assert flagged.shape == (N_TRIALS, N_TIMES)
        assert flagged.dtype == bool, "the docstring calls this a bool mask"
        assert isinstance(scale, float)

    def test_the_mask_keeps_the_input_shape_when_the_axes_are_swapped(self):
        """The shape claim has to hold for the caller's array, not for one orientation."""
        rng = np.random.default_rng(0)
        flagged, _ = jnwb.detect_band_outliers(
            rng.standard_normal((N_TIMES, N_TRIALS)))
        assert flagged.shape == (N_TIMES, N_TRIALS)


class TestTheUncoveredTwoAreNamed:
    """A gap that is stated cannot be mistaken later for a dimension that was checked."""

    @pytest.mark.parametrize("name", NEEDS_A_SESSION)
    def test_it_still_declares_a_return_shape(self, name: str):
        assert declared_shapes(getattr(jnwb, name)), (
            f"{name} was listed here as declaring a return shape that no fixture checks; "
            f"if the claim is gone, remove it from NEEDS_A_SESSION"
        )

    @pytest.mark.parametrize("name", NEEDS_A_SESSION)
    def test_it_still_requires_a_session(self, name: str):
        """If the session argument goes, the reason for not covering it goes with it."""
        first = next(iter(inspect.signature(getattr(jnwb, name)).parameters))
        assert first == "session", (
            f"{name} no longer takes a session first, so it may now be constructible here"
        )


class TestTheListOfDeclaringFunctionsIsComplete:
    def test_every_function_declaring_a_return_shape_is_accounted_for(self):
        """A new declaration must be covered or named, not silently join the gap."""
        covered = {"bin_spikes", "detect_band_outliers", "laplacian_reference",
                   *NEEDS_A_SESSION}
        declaring = {
            name for name in jnwb.__all__
            if callable(getattr(jnwb, name, None))
            and not inspect.isclass(getattr(jnwb, name))
            and declared_shapes(getattr(jnwb, name))
        }
        assert declaring <= covered, (
            f"{sorted(declaring - covered)} declare a return shape that nothing checks"
        )
