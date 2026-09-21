"""Every tutorial under examples/tutorials/ must run top to bottom."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TUTORIAL_DIR = REPO_ROOT / "examples" / "tutorials"
TUTORIALS = sorted(
    p for p in TUTORIAL_DIR.glob("[0-9][0-9]_*.py")
)


def test_there_are_tutorials_to_run():
    assert TUTORIALS, f"no numbered tutorials in {TUTORIAL_DIR}"


@pytest.mark.parametrize("path", TUTORIALS, ids=lambda p: p.name)
def test_tutorial_executes(path: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    res = subprocess.run(
        [sys.executable, str(path)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def _external_nwb(path: Path) -> Path:
    """An NWB file written with plain `pynwb`, by code that never imports jnwb.

    Deliberately unlike anything jnwb's own fixtures produce: the interval table is named
    `epochs` rather than `trials`, and its code column is `stimulus` rather than `codes`, so
    a reader that has memorised jnwb's own layout fails here instead of passing by recognition.
    """
    from datetime import datetime, timezone

    import numpy as np
    from pynwb import NWBHDF5IO, NWBFile
    from pynwb.ecephys import ElectricalSeries

    nwb = NWBFile(
        session_description="written by a lab that has never heard of jnwb",
        identifier="EXTERNAL_FIXTURE",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(
        name="shank0", description="one shank", location="cortex", device=device
    )
    for index in range(4):
        nwb.add_electrode(group=group, location="cortex", x=0.0, y=0.0, z=float(index))
    region = nwb.create_electrode_table_region(list(range(4)), "all four")

    rng = np.random.default_rng(11)
    nwb.add_acquisition(
        ElectricalSeries(
            name="ElectricalSeries",
            data=rng.standard_normal((5_000, 4)).astype("float32"),
            electrodes=region,
            starting_time=0.0,
            rate=1000.0,
        )
    )
    nwb.add_epoch_column(name="stimulus", description="stimulus code")
    for index in range(6):
        nwb.add_epoch(start_time=index * 0.5, stop_time=index * 0.5 + 0.3, stimulus=index % 3)

    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


def test_the_external_branch_of_tutorial_00_is_exercised(tmp_path: Path):
    """P-150: the one tutorial that can read a foreign file was only ever run without one.

    `00_your_own_file.py` is the only script accepting `sys.argv[1]`, and the parametrized run
    above invokes every tutorial with no arguments, so the external branch never executed and
    the script wrote its own stand-in instead. Passing that suite was therefore evidence about
    the stand-in path only.

    One correction to P-150's premise, measured rather than assumed: the stand-in is written
    with plain `pynwb`, not with jnwb's fixtures, so even the no-argument run is not jnwb
    reading back its own bytes. Of the nine tutorials, five author through `write_synth_nwb`,
    three touch no NWB at all, and this one authors through the reference implementation. What
    was genuinely untested is the *branch*, not the provenance -- and this runs it.
    """
    target = TUTORIAL_DIR / "00_your_own_file.py"
    assert target.is_file(), f"{target} is gone; this test no longer covers anything"

    external = _external_nwb(tmp_path / "foreign.nwb")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    res = subprocess.run(
        [sys.executable, str(target), str(external)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "No path given" not in res.stdout, (
        "the script fell back to its stand-in, so the argument was not read and this test "
        "is measuring the same path as the parametrized run above"
    )
    assert "epochs" in res.stdout, (
        f"the foreign file's interval table was not discovered:\n{res.stdout}"
    )
