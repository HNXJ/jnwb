"""Onsets in milliseconds were read as seconds and returned a confident array.

A file whose interval table holds onsets 1000-5000 against a 1.0 s recording -- which is
what milliseconds look like when the reader assumes seconds -- produced:

    events()          -> EventTable(time_unit='seconds', onsets=[1000. ... 5000.])
    epoch_continuous  -> (5, 800), every value NaN, no warning

The shape is right, the dtype is right, the time axis is right, and there is not one
number in it. Downstream that is a mean of NaNs, a spectrum at 0 Hz, and a figure.

Separately, a non-finite onset: `np.round(nan * fs).astype(np.int64)` is INT64_MIN, and
`idx + n_pre` then overflows to a large *positive* start with a large *negative* end. The
bounds test `0 <= start and end <= n_samples` is true of that pair, so the window took
the in-bounds branch and `arr[start:end]` returned an empty slice -- one epoch of shape
(0,), reported as a clean extraction, beside a `time_axis_s` of 800 samples. With one
valid onset alongside it, `np.stack` raised `ValueError: all input arrays must have the
same shape`, from numpy, naming nothing. `events` and `event_onsets` already raised
`InvalidOnsetValueError` for the same value.
"""

from __future__ import annotations

import numpy as np
import pytest

import jnwb
from jnwb.nwb_events import InvalidOnsetValueError

FS = 1000.0
DATA = np.arange(1000, dtype=np.float64)          # exactly 1.0 s
WIN = (-0.2, 0.6)


class TestOnsetsOnADifferentClock:

    def test_onsets_in_milliseconds_warn(self):
        with pytest.warns(UserWarning, match="fall entirely outside the data"):
            epochs, _ = jnwb.epoch_continuous(
                DATA, [1000.0, 2000.0, 3000.0, 4000.0, 5000.0], win_s=WIN, fs=FS)
        assert np.all(np.isnan(epochs))

    def test_the_warning_says_what_to_check(self):
        with pytest.warns(UserWarning) as caught:
            jnwb.epoch_continuous(DATA, [1000.0, 2000.0], win_s=WIN, fs=FS)
        message = str(caught[0].message)
        assert "2 of 2" in message
        assert "1000 to 2000 s" in message          # where the onsets are
        assert "0 to 1 s" in message                # where the data is
        assert "milliseconds" in message

    def test_negative_onsets_before_the_recording_warn_too(self):
        """The same failure with the sign flipped: a clock offset, not a unit."""
        with pytest.warns(UserWarning, match="fall entirely outside"):
            jnwb.epoch_continuous(DATA, [-50.0, -40.0, -30.0], win_s=WIN, fs=FS)

    def test_a_majority_is_required_not_a_single_stray_event(self):
        """Two in range, two out: ordinary, and silent."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            jnwb.epoch_continuous(DATA, [0.3, 0.5, 90.0, 95.0], win_s=WIN, fs=FS)

    def test_a_bare_majority_warns(self):
        """Three of four is a majority; two of four is not."""
        with pytest.warns(UserWarning):
            jnwb.epoch_continuous(DATA, [0.3, 90.0, 95.0, 99.0], win_s=WIN, fs=FS)

    def test_onsets_in_samples_are_measured_against_samples(self):
        """With `onset_unit="samples"` the extent is the sample count, not seconds."""
        with pytest.warns(UserWarning, match="0 to 1000 samples"):
            jnwb.epoch_continuous(DATA, [50000.0, 60000.0], win_s=WIN, fs=FS,
                                  onset_unit="samples")


class TestEpochsThatLegitimatelyOverhang:
    """The repair must not shout at ordinary edge events."""

    def test_events_at_the_edges_are_silent(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            epochs, _ = jnwb.epoch_continuous(DATA, [0.0, 0.5, 0.95], win_s=WIN, fs=FS)
        assert epochs.shape == (3, 800)
        assert int(np.sum(~np.all(np.isnan(epochs), axis=1))) == 3

    def test_every_event_overhanging_the_start_is_still_silent(self):
        """Both onsets sit before the pre-window fits, so both windows start at a
        negative index -- and both still overlap the data. "Starts before 0" is not
        "falls outside"; only a window that ends before 0, or begins after the last
        sample, contributes nothing."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            epochs, _ = jnwb.epoch_continuous(DATA, [0.0, 0.05], win_s=WIN, fs=FS)
        assert int(np.sum(~np.all(np.isnan(epochs), axis=1))) == 2

    def test_every_event_overhanging_the_end_is_still_silent(self):
        """The mirror case, against the last sample."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            epochs, _ = jnwb.epoch_continuous(DATA, [0.98, 0.99], win_s=WIN, fs=FS)
        assert int(np.sum(~np.all(np.isnan(epochs), axis=1))) == 2

    def test_the_partial_data_is_still_there(self):
        """An onset at 0.0 has no pre-window, and what follows it is real."""
        epochs, time_axis = jnwb.epoch_continuous(DATA, [0.0], win_s=WIN, fs=FS)
        assert np.all(np.isnan(epochs[0, :200]))
        np.testing.assert_allclose(epochs[0, 200:], DATA[:600])
        assert len(time_axis) == epochs.shape[1]

    def test_drop_and_error_policies_are_untouched(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            dropped, _ = jnwb.epoch_continuous(
                DATA, [1000.0, 2000.0], win_s=WIN, fs=FS, boundary_policy="drop")
            assert dropped.shape[0] == 0
        with pytest.raises(ValueError, match="extends outside data"):
            jnwb.epoch_continuous(DATA, [1000.0], win_s=WIN, fs=FS,
                                  boundary_policy="error")


class TestANonFiniteOnset:

    @pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
    def test_it_is_refused(self, bad):
        with pytest.raises(InvalidOnsetValueError) as exc:
            jnwb.epoch_continuous(DATA, [bad], win_s=WIN, fs=FS)
        assert "index 0" in str(exc.value)

    def test_the_index_is_the_offending_one(self):
        with pytest.raises(InvalidOnsetValueError) as exc:
            jnwb.epoch_continuous(DATA, [0.1, 0.2, np.nan], win_s=WIN, fs=FS)
        assert "index 2" in str(exc.value)

    def test_several_bad_onsets_are_counted(self):
        with pytest.raises(InvalidOnsetValueError) as exc:
            jnwb.epoch_continuous(DATA, [np.nan, 0.2, np.inf], win_s=WIN, fs=FS)
        assert "2 of 3" in str(exc.value)

    def test_it_no_longer_returns_a_zero_width_epoch(self):
        """It used to return shape (1, 0) -- an in-bounds extraction of nothing --
        beside an 800-sample time axis."""
        with pytest.raises(InvalidOnsetValueError):
            jnwb.epoch_continuous(DATA, [np.nan], win_s=WIN, fs=FS)

    def test_it_no_longer_dies_inside_numpy_on_mixed_input(self):
        """`np.stack` used to raise `ValueError: all input arrays must have the same
        shape`, which names neither the onset nor the argument."""
        with pytest.raises(InvalidOnsetValueError):
            jnwb.epoch_continuous(DATA, [np.inf, 0.5], win_s=WIN, fs=FS)

    @pytest.mark.parametrize("policy", ["nan", "drop", "error"])
    def test_every_boundary_policy_refuses_it(self, policy):
        with pytest.raises(InvalidOnsetValueError):
            jnwb.epoch_continuous(DATA, [np.nan], win_s=WIN, fs=FS,
                                  boundary_policy=policy)

    def test_the_three_entry_points_agree(self, tmp_path):
        """`events` and `event_onsets` already raised this; `epoch_continuous` returned
        an array. The accept condition for 05-40 is that all three agree."""
        from datetime import datetime, timezone

        import h5py
        import pynwb

        nwb = pynwb.NWBFile(session_description="nan onset", identifier="nan-1",
                            session_start_time=datetime.now(timezone.utc))
        nwb.add_trial(start_time=0.1, stop_time=0.2)
        nwb.add_trial(start_time=0.3, stop_time=0.4)
        path = str(tmp_path / "nan_onset.nwb")
        with pynwb.NWBHDF5IO(path, "w") as io:
            io.write(nwb)
        with h5py.File(path, "r+") as handle:
            handle["/intervals/trials/start_time"][0] = np.nan

        for call in (lambda: jnwb.events(path),
                     lambda: jnwb.event_onsets(path, table="trials"),
                     lambda: jnwb.epoch_continuous(
                         DATA, [np.nan, 0.3], win_s=WIN, fs=FS)):
            with pytest.raises(InvalidOnsetValueError):
                call()


class TestTheShapeInvariant:
    """Whatever comes back, its window axis is the time axis. The (1, 0) epoch broke
    this, which is what made it invisible."""

    @pytest.mark.parametrize("onsets", [
        [0.3], [0.0, 0.5, 0.95], [1000.0, 2000.0], [],
    ])
    def test_the_window_axis_matches_the_time_axis(self, onsets):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            epochs, time_axis = jnwb.epoch_continuous(DATA, onsets, win_s=WIN, fs=FS)
        assert epochs.shape[1] == len(time_axis) == 800

    def test_it_holds_for_two_dimensional_data(self):
        import warnings

        data2d = np.arange(1000 * 3, dtype=np.float64).reshape(1000, 3)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            epochs, time_axis = jnwb.epoch_continuous(
                data2d, [0.3, 900.0], win_s=WIN, fs=FS)
        assert epochs.shape == (2, len(time_axis), 3)
