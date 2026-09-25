"""Three ways a call did the wrong thing quietly, and now says so.

The shared shape is the one that does not get noticed: the call returned a value of the right
type and plausible magnitude, so nothing downstream had a reason to look.

* ``gaussian_smooth_rate`` consumed a non-finite bin and widened it. A Gaussian kernel is a
  weighted sum, so one bad bin contaminates every bin it reaches: measured at ``bin_ms=10,
  sigma_ms=20``, an interior NaN widens 1 into 17, and the NaN a boundary policy actually
  produces sits at an epoch edge where the kernel reaches one side only and the same call
  widens 1 into 9. Both magnitudes are pinned separately here so neither drifts into the
  other -- the composed figure is 9, not the 17 first recorded (P-112).
* ``acquisition_channel`` returned the volts conversion applied to an int16 series whose file
  stores a contradicting unit, and warned nothing. `inspect` warns where the contradiction is
  declared; this is where the harm lands (P-120).
* ``label_layers`` is duck-typed on ``crossover_contact``. Handed a result type without it, it
  raised a bare ``AttributeError`` when ``accepted=True`` and -- in the ordinary
  ``accepted=False`` case -- short-circuited before reading the field at all and returned a
  full-length array of ``'na'`` with no error and no warning (P-123).

Each defect is pinned in both directions. A test that only asserts the new warning passes on
a function that warns unconditionally, which is a different defect with the same test.
"""
from __future__ import annotations

import pathlib
import sys
import warnings
from datetime import datetime, timezone

import h5py
import numpy as np
import pytest
from pynwb import NWBHDF5IO, NWBFile
from pynwb.ecephys import ElectricalSeries

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# append, never insert(0): the wheel leg must keep resolving the installed copy.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from jnwb.laminar import label_layers  # noqa: E402
from jnwb.nwb_inspect import acquisition_channel  # noqa: E402
from jnwb.spiking import gaussian_smooth_rate  # noqa: E402

BIN_MS = 10.0
SIGMA_MS = 20.0


# --------------------------------------------------------------------------------------
# P-112 -- a boundary NaN is reported, and the magnitude is measured at both positions.
# --------------------------------------------------------------------------------------

def _spread(n_bins: int, nan_at: int) -> int:
    rate = np.ones(n_bins, dtype=float)
    rate[nan_at] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = gaussian_smooth_rate(rate, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)
    return int(np.count_nonzero(~np.isfinite(out)))


def test_an_interior_nan_widens_and_the_width_is_pinned():
    assert _spread(101, 50) == 17


def test_an_epoch_edge_nan_widens_less_because_the_kernel_reaches_one_side():
    """The composed magnitude is 9, not 17.

    This is the position a boundary policy actually produces, so it is the number that
    describes the defect in practice. Pinned separately from the interior case so a future
    change cannot quietly substitute one for the other.
    """
    assert _spread(101, 0) == 9


def test_a_nonfinite_bin_is_reported_with_both_counts():
    rate = np.ones(101, dtype=float)
    rate[0] = np.nan
    with pytest.warns(RuntimeWarning) as caught:
        gaussian_smooth_rate(rate, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)
    message = str(caught[0].message)
    assert "1 non-finite bin(s)" in message
    assert "spread to 9" in message, message


def test_a_clean_trace_warns_nothing():
    """Without this, a warning that always fires would satisfy the test above."""
    rate = np.ones(101, dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = gaussian_smooth_rate(rate, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)
    assert np.all(np.isfinite(out))


def test_the_array_is_still_returned():
    """Reporting, not refusing: a caller knowingly smoothing a padded epoch is not broken."""
    rate = np.ones(101, dtype=float)
    rate[0] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = gaussian_smooth_rate(rate, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)
    assert out.shape == rate.shape
    assert np.count_nonzero(np.isfinite(out)) == 92


# --------------------------------------------------------------------------------------
# P-120 -- the harm lands where the conversion is applied, so the warning is there too.
# --------------------------------------------------------------------------------------

def _electrical_series_file(tmp_path: pathlib.Path, stored_unit: str | None) -> pathlib.Path:
    """An int16 ElectricalSeries, optionally with a contradicting unit patched into the file.

    The patch is unavoidable: `ElectricalSeries.__init__` does not accept `unit` at all,
    because the schema fixes it. That is precisely why the object model cannot express the
    contradiction and why a file can still hold it.
    """
    path = tmp_path / f"series_{stored_unit or 'schema'}.nwb"
    nwb = NWBFile(
        session_description="unit contradiction",
        identifier="p120",
        session_start_time=datetime(2026, 9, 21, tzinfo=timezone.utc),
    )
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(
        name="shank", description="shank", location="cortex", device=device
    )
    for i in range(4):
        nwb.add_electrode(
            x=0.0, y=0.0, z=float(i) * 20.0, imp=0.0, location="cortex",
            filtering="none", group=group, group_name="shank",
        )
    region = nwb.create_electrode_table_region(list(range(4)), "all")
    nwb.add_acquisition(
        ElectricalSeries(
            name="lfp_series",
            data=np.arange(4 * 50, dtype=np.int16).reshape(50, 4),
            electrodes=region,
            rate=1000.0,
            conversion=1.0e-6,
        )
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)
    if stored_unit is not None:
        with h5py.File(str(path), "r+") as f:
            f["/acquisition/lfp_series/data"].attrs["unit"] = stored_unit
    return path


def test_the_object_model_cannot_show_the_contradiction(tmp_path):
    """The premise the warning exists for, measured rather than assumed.

    If `series.unit` ever started reporting the stored value, the warning would be
    unnecessary -- and a reader of this test would have no way to know that had changed.
    """
    path = _electrical_series_file(tmp_path, "n.a.")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with NWBHDF5IO(str(path), "r") as io:
            series = io.read().acquisition["lfp_series"]
            assert series.unit == "volts"
            assert series.data.attrs["unit"] == "n.a."


def test_a_contradicting_stored_unit_is_reported(tmp_path):
    path = _electrical_series_file(tmp_path, "n.a.")
    with pytest.warns(RuntimeWarning, match="fixes the data unit"):
        data, rate = acquisition_channel(str(path), "lfp_series", channel=0)
    assert rate == 1000.0
    assert data.shape == (50,)


def test_the_report_names_both_units_and_the_conversion(tmp_path):
    path = _electrical_series_file(tmp_path, "n.a.")
    with pytest.warns(RuntimeWarning) as caught:
        acquisition_channel(str(path), "lfp_series", channel=0)
    message = str(caught[0].message)
    assert "'volts'" in message
    assert "'n.a.'" in message
    assert "int16" in message


def test_a_schema_consistent_file_warns_nothing(tmp_path):
    """The other direction: the warning must not fire on every ElectricalSeries."""
    path = _electrical_series_file(tmp_path, None)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        data, rate = acquisition_channel(str(path), "lfp_series", channel=0)
    assert rate == 1000.0
    assert data.shape == (50,)


# --------------------------------------------------------------------------------------
# P-123 -- a result type without the field is refused, in both accepted states.
# --------------------------------------------------------------------------------------

class _WrongResult:
    """Stands in for XFlipResult / ZFlipResult: no `crossover_contact`."""

    def __init__(self, accepted: bool, n_channels: int = 24):
        self.accepted = accepted
        self.n_channels = n_channels
        self.index_space = "shaft_rank"


@pytest.mark.parametrize("accepted", [True, False])
def test_a_result_without_a_crossover_is_refused_in_both_accepted_states(accepted):
    """`accepted=False` is the case that mattered and the one that was silent.

    `or` short-circuits, so the missing field was never read and the function returned a
    full-length array of 'na' -- a wrong-type result reading as an honest negative.
    """
    from jnwb.testing.synth import synth_laminar_motif

    motif = synth_laminar_motif()
    geometry = motif["probe_geometry"] if isinstance(motif, dict) else motif.probe_geometry
    with pytest.raises(TypeError, match="crossover_contact"):
        label_layers(
            _WrongResult(accepted, n_channels=len(list(geometry.channel_ids))),
            probe_geometry=geometry,
        )


def test_the_refusal_names_the_offending_type():
    from jnwb.testing.synth import synth_laminar_motif

    motif = synth_laminar_motif()
    geometry = motif["probe_geometry"] if isinstance(motif, dict) else motif.probe_geometry
    with pytest.raises(TypeError) as excinfo:
        label_layers(
            _WrongResult(False, n_channels=len(list(geometry.channel_ids))),
            probe_geometry=geometry,
        )
    assert "_WrongResult" in str(excinfo.value)
