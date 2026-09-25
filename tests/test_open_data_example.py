"""The open-data tutorial reads a real excerpt and derives its LFP clock from the file.

`tests/test_tutorials.py` runs `examples/tutorials/09_open_data.py` end to end. These tests pin
what that run cannot show: the excerpt is the published data it claims to be, and the sampling
rate the analysis uses is computed from the file's timestamps and spikes rather than written in.
Each clock test edits a copy of the excerpt and requires the derived values to follow the edit;
a literal rate, tick step or offset anywhere in the analysis stays put and fails.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

import h5py
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "examples" / "tutorials" / "09_open_data.py"
EXCERPT = REPO_ROOT / "examples" / "data" / "dandi000253_excerpt.nwb"
PROVENANCE = REPO_ROOT / "examples" / "data" / "dandi000253_excerpt.provenance.json"
LFP = "acquisition/probe_1_lfp/probe_1_lfp_{}/timestamps"
SPIKE_CLOCK = ("units/spike_times", "units/obs_intervals",
               "intervals/init_grating_presentations/start_time",
               "intervals/init_grating_presentations/stop_time")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest.fixture(scope="module")
def tutorial():
    spec = importlib.util.spec_from_file_location("open_data_tutorial", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


@pytest.fixture(scope="module")
def provenance():
    return json.loads(PROVENANCE.read_text(encoding="utf-8"))


def _edited_copy(tmp_path: Path, edits: dict) -> Path:
    """A copy of the excerpt with each named dataset replaced by `edit(values)`."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / EXCERPT.name
    shutil.copyfile(EXCERPT, path)
    with h5py.File(path, "r+") as h:
        for name, edit in edits.items():
            h[name][...] = edit(h[name][...])
    return path


def _clock(tutorial, path: Path):
    data = tutorial.read_excerpt(path)
    return tutorial.derive_clock(data["lfp"], data["trains"])


def test_the_excerpt_is_the_published_data_and_ships_outside_the_wheel(provenance):
    size = EXCERPT.stat().st_size
    assert size < 20_000_000, f"excerpt is {size / 1e6:.1f} MB"
    digest = hashlib.sha256(EXCERPT.read_bytes()).hexdigest()
    assert provenance["excerpt"] == {"path": "examples/data/" + EXCERPT.name,
                                     "size_bytes": size, "sha256": digest}, (
        "the provenance describes a different excerpt; rebuild both together")
    assert provenance["dandiset"]["license"] == "CC-BY-4.0"
    assert provenance["dandiset"]["doi"] == "10.48324/dandi.000253/0.240503.0152"
    for asset in provenance["assets"].values():
        assert UUID.match(asset["asset_id"]), asset
        assert asset["sha256_verified_locally"] == asset["sha256"], (
            "the excerpt was built without verifying its source against the published digest")

    find = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"]["setuptools"]["packages"]["find"]
    assert find["include"] == ["jnwb*"] and "examples*" in find["exclude"], find


def test_the_derived_clock_follows_the_timestamps_and_spikes(tutorial, provenance, tmp_path):
    pristine = _clock(tutorial, EXCERPT)
    source = provenance["source_values"]
    # The excerpt keeps the recording's edges, so it reproduces the full-session derivation.
    assert pristine.tick_step == source["lfp_timestamp_step"]
    assert pristine.tick_rate == pytest.approx(
        provenance["builder_clock_estimate"]["tick_rate_per_s"], rel=1e-12)
    assert pristine.offset_s == source["probe_first_spike_s"]

    doubled = _clock(tutorial, _edited_copy(tmp_path / "a", {
        LFP.format(s): (lambda v: 2.0 * v) for s in ("start", "window", "end")}))
    assert doubled.tick_step == 2 * pristine.tick_step
    assert doubled.tick_rate == pytest.approx(2 * pristine.tick_rate, rel=1e-12)
    assert doubled.fs_hz == pytest.approx(pristine.fs_hz, rel=1e-12)

    extra = 1e-3 * (source["lfp_last_timestamp"] - source["lfp_first_timestamp"])
    extra -= extra % pristine.tick_step
    longer = _clock(tutorial, _edited_copy(tmp_path / "b", {LFP.format("end"): lambda v: v + extra}))
    factor = 1.0 + extra / (source["lfp_last_timestamp"] - source["lfp_first_timestamp"])
    assert longer.fs_hz == pytest.approx(pristine.fs_hz * factor, rel=1e-12)
    assert longer.fs_hz != pytest.approx(pristine.fs_hz, rel=1e-6)


def test_every_rate_the_analysis_uses_is_the_one_derived_from_the_file(
        tutorial, provenance, tmp_path, monkeypatch):
    # Compress the spike clock by 0.9 about the first spike and shift it by 1 s: the file is
    # still self-consistent, its LFP rate is now fs/0.9 and its first sample 1 s later.
    t0 = provenance["source_values"]["probe_first_spike_s"]
    path = _edited_copy(tmp_path, {name: (lambda v: t0 + 0.9 * (v - t0) + 1.0)
                                   for name in SPIKE_CLOCK})
    expected = _clock(tutorial, EXCERPT).fs_hz / 0.9

    seen = []
    for owner, name in ((tutorial.jnwb, "band_power"), (tutorial.jnwb, "epoch_continuous"),
                        (tutorial, "xcorr_lag")):
        real = getattr(owner, name)

        def spy(*args, _real=real, _name=name, **kwargs):
            seen.append((_name, kwargs["fs"] if "fs" in kwargs else args[3]))
            return _real(*args, **kwargs)

        monkeypatch.setattr(owner, name, spy)

    res = tutorial.analyze(path)
    assert res["clock"].fs_hz == pytest.approx(expected, rel=1e-9)
    assert res["clock"].offset_s == pytest.approx(t0 + 1.0, abs=1e-9)
    assert {name for name, _ in seen} == {"band_power", "epoch_continuous", "xcorr_lag"}
    wrong = [(name, fs) for name, fs in seen if fs != pytest.approx(expected, rel=1e-9)]
    assert not wrong, f"{len(wrong)} calls used a rate other than the derived one: {wrong[:3]}"
    n_expected = round(tutorial.POST_S[1] * expected) - round(tutorial.POST_S[0] * expected)
    assert res["lfp"]["epoch_n_samples"] == n_expected


def test_the_clock_check_refuses_an_offset_beyond_its_bound(tutorial):
    data = tutorial.read_excerpt(EXCERPT)
    clock = tutorial.derive_clock(data["lfp"], data["trains"])
    good = data["quality"] == "good"
    lags = tutorial.check_clock(clock, data, good)["lags_s"]
    assert all(abs(lag) <= tutorial.OFFSET_BOUND_S for lag, _ in lags.values())

    shifted = dataclasses.replace(clock, offset_s=clock.offset_s + 3 * tutorial.OFFSET_BOUND_S)
    with pytest.raises(tutorial.ClockCheckError, match="exceeds"):
        tutorial.check_clock(shifted, data, good)
