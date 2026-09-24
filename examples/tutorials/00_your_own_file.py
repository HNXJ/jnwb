"""Tutorial 00: Your Own NWB File — Discovering a Layout You Did Not Write.

Every other tutorial writes a synthetic file and asserts against values it already knows.
This one does the opposite: it reads the layout off ``jnwb.inspect`` and adapts, which is
what you need when the file came from someone else.

Run against your own recording:

    python examples/tutorials/00_your_own_file.py /path/to/recording.nwb [interval_table]

When a file holds several interval tables, jnwb refuses to choose one; name it as the second
argument, which is what the refusal tells you to do.

Run with no argument and it builds a small stand-in with plain ``pynwb`` first, deliberately
naming its code column ``stimulus`` rather than ``codes`` so the discovery step has something
real to discover.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# This file is run from a checkout, so prefer that checkout over any installed jnwb:
# Python puts this directory on sys.path, not the repository root. A run that is
# deliberately qualifying an installed copy says so with JNWB_EXPECTED_PACKAGE_ROOT,
# and then this guard stands aside -- otherwise it would quietly redirect CI's
# installed-wheel tutorial step back to the checkout.
import os

_CHECKOUT = Path(__file__).resolve().parents[2]
if not os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") and (
    _CHECKOUT / "jnwb" / "__init__.py"
).exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb

_STRUCTURAL_COLUMNS = {"id", "start_time", "stop_time", "tags", "timeseries"}


def write_stand_in(path: Path) -> Path:
    """A minimal file written the way a lab that has never heard of jnwb would write one."""
    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries

    rng = np.random.default_rng(7)
    fs, n_samples, n_channels = 1000.0, 30_000, 8

    nwb = NWBFile(
        session_description="stand-in recording",
        identifier="TUTORIAL_00_STAND_IN",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(
        name="shank0", description="stand-in", location="unknown", device=device
    )
    for index in range(n_channels):
        nwb.add_electrode(group=group, location="unknown", x=0.0, y=0.0, z=float(index) * 50.0)
    region = nwb.create_electrode_table_region(list(range(n_channels)), "all")

    t = np.arange(n_samples) / fs
    lfp = np.sin(2 * np.pi * 18.0 * t)[None, :] + rng.normal(0, 0.7, (n_channels, n_samples))
    nwb.add_acquisition(
        ElectricalSeries(
            name="lfp", data=lfp.T.astype("float32"), electrodes=region,
            starting_time=0.0, rate=fs,
        )
    )

    nwb.add_trial_column(name="stimulus", description="stimulus label")
    for index, onset in enumerate(np.arange(2.0, 28.0, 3.0)):
        nwb.add_trial(
            start_time=float(onset), stop_time=float(onset + 1.0),
            stimulus="grating" if index % 2 == 0 else "blank",
        )

    for unit in range(3):
        nwb.add_unit(spike_times=np.sort(rng.uniform(0.0, 30.0, 600)), electrodes=[unit])

    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


def choose_code_column(table: dict) -> str | None:
    """Pick the column that looks like event codes, or None if the table has none.

    `codes` is jnwb's default name, not an NWB requirement, so it is preferred when present
    and otherwise the first non-structural column with sample values is used. Whatever this
    returns is passed explicitly: jnwb never guesses on your behalf.
    """
    names = [column["name"] for column in table["columns"]]
    if "codes" in names:
        return "codes"
    for column in table["columns"]:
        if column["name"] in _STRUCTURAL_COLUMNS:
            continue
        if column.get("sample_values"):
            return column["name"]
    return None


def continuous_series(info: dict) -> list[dict]:
    """Every continuous series in the file, acquisitions first.

    `inspect` reports acquisition series and processing-module series in two lists with the
    same keys. An `LFP` container usually lives in a processing module, so reading
    `info["acquisitions"]` alone finds no continuous series in most files.
    """
    return list(info["acquisitions"]) + list(info["processing_continuous"])


def describe_continuous(entry: dict) -> str:
    """One line per series, saying plainly what is unknown rather than printing `None`.

    `rate_hz` is `None` for a series stored with `timestamps` instead of a constant rate,
    and for a container wrapping several series that do not share one. `data_shape` and
    `layout` are `None` in the second case for the same reason.
    """
    where = f"Processing/{entry['module']}" if "module" in entry else "Acquisition"
    shape = entry["data_shape"] if entry["data_shape"] is not None else "unknown shape"
    if entry["rate_hz"] is None:
        if entry.get("series") and len(entry["series"]) > 1:
            rate = f"several series ({', '.join(entry['series'])}), no shared rate"
        else:
            rate = "no constant rate (irregularly sampled)"
    else:
        rate = f"{entry['rate_hz']} Hz"
    layout = entry["layout"] or "layout undetermined"
    return f"{where} {entry['name']}: shape {shape}, {rate}, {layout}"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        if len(sys.argv) > 1:
            path = Path(sys.argv[1])
            if not path.exists():
                raise SystemExit(f"No such file: {path}")
        else:
            path = write_stand_in(Path(tmpdir) / "stand_in.nwb")
            print(f"No path given; wrote a stand-in file at {path.name}")

        # 1. What is in here? inspect never picks a default table for you.
        info = jnwb.inspect(path)
        print(f"Session: {info['session']['identifier']}")
        print(f"Units: {info['units']['n_rows']}")
        continuous = continuous_series(info)
        if not continuous:
            print("No continuous series anywhere in the file.")
        for entry in continuous:
            print(f"{describe_continuous(entry)}")

        tables = info["interval_tables"]
        if not tables:
            print("No interval tables; nothing to align to. Stopping here.")
            return
        for table in tables:
            print(f"Interval table {table['name']}: {[c['name'] for c in table['columns']]}")

        # 2. Let jnwb apply its own rule -- `trials`, else the sole table, else refuse --
        #    instead of reimplementing a policy here. Picking `tables[0]` would look like it
        #    worked on a file with five interval tables and quietly align to the wrong one.
        requested = sys.argv[2] if len(sys.argv) > 2 else None
        try:
            resolved = jnwb.events(path, table=requested, code_column=None)
        except jnwb.AmbiguousIntervalTableError as err:
            print(f"jnwb will not guess between these tables: {err}")
            print(f"Re-run naming one: python {Path(sys.argv[0]).name} <file.nwb> <table>")
            return
        table = next(t for t in tables if t["name"] == resolved.table)
        code_column = choose_code_column(table)
        print(f"Using table {table['name']!r} with code_column={code_column!r}")

        event_table = jnwb.events(path, table=table["name"], code_column=code_column)
        print(f"{event_table.n_events} events, onsets in {event_table.time_unit}")

        if code_column is None:
            onsets = event_table.onsets
            print("No code column, so every event is used.")
        else:
            code = event_table.codes[0]
            onsets = jnwb.event_onsets(
                path, table=table["name"], code_column=code_column, codes=[code]
            )
            print(f"Code {code!r}: {onsets.size} of {event_table.n_events} events")
        assert onsets.size > 0 and np.all(np.isfinite(onsets))

        # 3. Align spikes, if the file has any.
        if info["units"]["n_rows"] > 0:
            spikes = jnwb.unit_spike_times(path, unit_index=0)
            time_bins, rate_hz, _ = jnwb.raster_psth(
                spikes, onsets, win_ms=(-200.0, 600.0), bin_ms=20.0
            )
            print(
                f"Unit 0: {spikes.size} spikes, PSTH over {time_bins.size} bins, "
                f"mean {np.nanmean(rate_hz):.2f} Hz"
            )

        # 4. Align a continuous channel, if the file has one.
        aligned = False
        for entry in continuous:
            name = entry["name"]
            if entry.get("rate_hz") is None:
                # Either the series carries `timestamps` rather than a constant rate, or
                # it is a container wrapping several series with different rates. Both
                # are legal files; neither has one sampling rate to epoch by.
                print(f"{name}: no constant sampling rate, so not epoched here. "
                      f"Read its timestamps and resample if you need a spectrum.")
                continue
            try:
                signal, fs_hz = jnwb.acquisition_channel(path, name=name, channel=0)
            except jnwb.NWBInspectError as err:
                print(f"{name}: {err}")
                continue
            # Onsets are session times, and sample 0 of `signal` is at the series'
            # starting_time, which inspect reports per series. Add it to the signal's time
            # axis by subtracting it from the onsets; acquisition_channel warns when it is not 0.
            start_s = entry.get("starting_time") or 0.0
            epochs, _ = jnwb.epoch_continuous(
                signal, onsets - start_s, win_s=(-0.2, 0.6), fs=fs_hz)
            freqs, psd = jnwb.compute_psd(signal, fs=fs_hz)
            print(
                f"{name}: {epochs.shape[0]} epochs of {epochs.shape[1]} samples, "
                f"spectral peak at {freqs[np.argmax(psd)]:.1f} Hz"
            )
            aligned = True
            break

        # The closing line reports what happened rather than what was hoped for. A
        # script that says "aligned" after aligning nothing is how a blank figure gets
        # believed.
        if aligned:
            print("Layout discovered and aligned without assuming a schema.")
        elif continuous:
            print("Layout discovered; no continuous series could be aligned, and the "
                  "lines above say why for each one.")
        else:
            print("Layout discovered; this file has no continuous series to align.")


if __name__ == "__main__":
    main()
