"""05-42: tutorial 00 was the page for an unfamiliar file, and broke on two common ones.

It read `acquisition["rate_hz"]` and iterated `info["acquisitions"]` alone.

A file storing `timestamps` instead of `starting_time` + `rate` -- which is what you get
whenever the sampling is not exactly regular -- ran to section 4 and died there with an
uncaught `AcquisitionNotFoundError: Series 'lfp' has no constant sampling rate`, after
printing `None Hz` for the same series.

A file whose LFP lives in a processing module -- which is where an `LFP` container usually
lives -- printed no continuous line at all, silently skipped section 4, and then claimed
"Layout discovered and aligned without assuming a schema". The string
`processing_continuous` did not appear in the script.

The tutorial's design is not the problem: on a 16-channel foreign file it finds `condition`
as the code column and recovers an injected 23.0 Hz without being told anything. What it
lacked was the other half of `inspect`'s output and a guard on the values that can be
absent.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = REPO_ROOT / "examples" / "tutorials" / "00_your_own_file.py"

FS = 500.0
N = 2000
PEAK_HZ = 23.0


def _run(path, table="trials"):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    argv = [sys.executable, str(TUTORIAL), str(path)]
    if table is not None:
        argv.append(table)
    return subprocess.run(argv, cwd=REPO_ROOT, env=env, capture_output=True, text=True)


def _scaffold(identifier):
    import pynwb

    nwb = pynwb.NWBFile(session_description="foreign", identifier=identifier,
                        session_start_time=datetime.now(timezone.utc))
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(name="g", description="d", location="V1",
                                       device=device)
    for i in range(8):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=0.0, location="V1",
                          filtering="none", group=group)
    t = np.arange(N) / FS
    data = np.sin(2 * np.pi * PEAK_HZ * t)[:, None] * np.ones((1, 8))
    nwb.add_trial_column(name="condition", description="labels")
    for k in range(6):
        nwb.add_trial(start_time=0.4 + 0.5 * k, stop_time=0.6 + 0.5 * k,
                      condition="a" if k % 2 else "b")
    nwb.add_unit(spike_times=list(np.arange(0.1, 3.5, 0.11)))
    return nwb, data


def _write(nwb, path):
    import pynwb

    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return str(path)


@pytest.fixture
def timestamps_file(tmp_path):
    """No `rate`: the series carries one timestamp per sample."""
    import pynwb

    nwb, data = _scaffold("timestamps")
    nwb.add_acquisition(pynwb.ecephys.ElectricalSeries(
        name="lfp", data=data,
        electrodes=nwb.create_electrode_table_region(list(range(8)), "all"),
        timestamps=np.arange(N) / FS))
    return _write(nwb, tmp_path / "timestamps.nwb")


@pytest.fixture
def processing_file(tmp_path):
    """Nothing in /acquisition; the LFP is in a processing module."""
    import pynwb

    nwb, data = _scaffold("processing")
    module = nwb.create_processing_module(name="ecephys", description="d")
    module.add(pynwb.ecephys.LFP(electrical_series=pynwb.ecephys.ElectricalSeries(
        name="lfp", data=data,
        electrodes=nwb.create_electrode_table_region(list(range(8)), "all"), rate=FS)))
    return _write(nwb, tmp_path / "processing.nwb")


@pytest.fixture
def plain_file(tmp_path):
    import pynwb

    nwb, data = _scaffold("plain")
    nwb.add_acquisition(pynwb.ecephys.ElectricalSeries(
        name="lfp", data=data,
        electrodes=nwb.create_electrode_table_region(list(range(8)), "all"), rate=FS))
    return _write(nwb, tmp_path / "plain.nwb")


class TestATimestampsOnlyFile:

    def test_the_tutorial_completes(self, timestamps_file):
        result = _run(timestamps_file)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_it_says_the_series_is_irregularly_sampled_rather_than_printing_none(
            self, timestamps_file):
        out = _run(timestamps_file).stdout
        assert "no constant rate (irregularly sampled)" in out
        assert "None Hz" not in out

    def test_it_says_why_it_did_not_epoch(self, timestamps_file):
        out = _run(timestamps_file).stdout
        assert "no constant sampling rate, so not epoched here" in out

    def test_it_does_not_claim_to_have_aligned_anything(self, timestamps_file):
        """The closing line used to be unconditional. A script that says "aligned" after
        aligning nothing is how a blank figure gets believed."""
        out = _run(timestamps_file).stdout
        assert "Layout discovered and aligned" not in out
        assert "no continuous series could be aligned" in out

    def test_the_rest_of_the_tutorial_still_runs(self, timestamps_file):
        out = _run(timestamps_file).stdout
        assert "6 events, onsets in seconds" in out
        assert "PSTH over" in out


class TestAProcessingModuleFile:

    def test_the_tutorial_completes(self, processing_file):
        result = _run(processing_file)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_the_continuous_series_is_reported_at_all(self, processing_file):
        """It printed no continuous line whatsoever."""
        out = _run(processing_file).stdout
        assert "Processing/ecephys LFP" in out

    def test_it_aligns_the_processing_series(self, processing_file):
        out = _run(processing_file).stdout
        assert "epochs of" in out
        assert "Layout discovered and aligned" in out

    def test_it_recovers_the_injected_frequency(self, processing_file):
        """The point of the exercise: the tutorial finds real structure in a file it was
        told nothing about."""
        out = _run(processing_file).stdout
        assert f"spectral peak at {PEAK_HZ:.1f} Hz" in out


@pytest.fixture
def ambiguous_layout_file(tmp_path):
    """A constant rate, so it gets past the rate guard, and a square array with a
    matching electrode count, so `acquisition_channel` cannot tell which axis is
    channels. This is the shape that reaches the `except jnwb.NWBInspectError` path."""
    import pynwb

    nwb, _ = _scaffold("square")
    square = np.arange(8 * 8, dtype=float).reshape(8, 8)
    nwb.add_acquisition(pynwb.ecephys.ElectricalSeries(
        name="lfp", data=square,
        electrodes=nwb.create_electrode_table_region(list(range(8)), "all"), rate=FS))
    return _write(nwb, tmp_path / "square.nwb")


class TestASeriesThatRaisesOnRead:
    """A rate the tutorial accepts, and a read it cannot complete. Without the guard this
    is an uncaught traceback on a legal file."""

    def test_the_tutorial_completes(self, ambiguous_layout_file):
        result = _run(ambiguous_layout_file)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_it_prints_the_error_rather_than_raising_it(self, ambiguous_layout_file):
        out = _run(ambiguous_layout_file).stdout
        assert "Cannot tell which axis" in out

    def test_it_does_not_claim_to_have_aligned_anything(self, ambiguous_layout_file):
        out = _run(ambiguous_layout_file).stdout
        assert "Layout discovered and aligned" not in out
        assert "no continuous series could be aligned" in out

    def test_the_rest_of_the_tutorial_still_runs(self, ambiguous_layout_file):
        out = _run(ambiguous_layout_file).stdout
        assert "6 events, onsets in seconds" in out
        assert "PSTH over" in out


class TestAnOrdinaryFileIsUnchanged:

    def test_the_tutorial_completes_and_aligns(self, plain_file):
        result = _run(plain_file)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Acquisition lfp" in result.stdout
        assert f"spectral peak at {PEAK_HZ:.1f} Hz" in result.stdout
        assert "Layout discovered and aligned" in result.stdout


class TestEveryFixtureShape:
    """05-42's accept condition: every shape `jnwb/testing/nwb_fixtures.py` can build."""

    OPTIONS = ["canonical_co_resident_options", "lfp_wrapped_options",
               "numeric_codes_options", "task_only_options",
               "processing_lfp_options"]

    @pytest.mark.parametrize("factory", OPTIONS)
    def test_the_tutorial_completes(self, tmp_path, factory):
        from jnwb.testing import nwb_fixtures

        path = tmp_path / f"{factory}.nwb"
        nwb_fixtures.write_synth_nwb(path, getattr(nwb_fixtures, factory)())
        result = _run(path, table=None)
        assert result.returncode == 0, result.stdout + result.stderr

    @pytest.mark.parametrize("factory", OPTIONS)
    def test_it_never_prints_a_bare_none(self, tmp_path, factory):
        """`None Hz`, `shape None` and `layout None` are the shape of an unguarded key
        read after 05-39 made every key always present."""
        from jnwb.testing import nwb_fixtures

        path = tmp_path / f"{factory}_none.nwb"
        nwb_fixtures.write_synth_nwb(path, getattr(nwb_fixtures, factory)())
        out = _run(path, table=None).stdout
        for bad in ("None Hz", "shape None", "layout None"):
            assert bad not in out, (bad, out)


class TestTheHelpersThemselves:

    def test_continuous_series_reads_both_lists(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("tut00", TUTORIAL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        info = {"acquisitions": [{"name": "a"}], "processing_continuous": [{"name": "p"}]}
        assert [e["name"] for e in module.continuous_series(info)] == ["a", "p"]

    @pytest.mark.parametrize("entry,expected", [
        ({"name": "x", "data_shape": [10, 2], "rate_hz": 500.0,
          "layout": "time_by_channel", "series": None},
         "Acquisition x: shape [10, 2], 500.0 Hz, time_by_channel"),
        ({"name": "x", "data_shape": [10, 2], "rate_hz": None,
          "layout": "time_by_channel", "series": None},
         "Acquisition x: shape [10, 2], no constant rate (irregularly sampled), "
         "time_by_channel"),
        ({"name": "L", "data_shape": None, "rate_hz": None, "layout": None,
          "series": ["a", "b"], "module": "ecephys"},
         "Processing/ecephys L: shape unknown shape, several series (a, b), no shared "
         "rate, layout undetermined"),
    ])
    def test_describe_continuous_says_what_is_unknown(self, entry, expected):
        import importlib.util

        spec = importlib.util.spec_from_file_location("tut00b", TUTORIAL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.describe_continuous(entry) == expected
