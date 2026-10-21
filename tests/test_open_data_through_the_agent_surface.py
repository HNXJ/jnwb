"""The open-data tutorial's questions, asked through the agent-facing surface.

`tests/test_open_data_example.py` pins the direct-Python tutorial, `examples/tutorials/09_open_data.py`.
These tests put the same questions to the surface an agent reads: the MCP tools `inspect_nwb`,
`get_event_codes_and_timings` and `prepare_signal_reference`, and the skills' routing (each
`skills/*/SKILL.md` and the reference pages it loads). Where both surfaces answer with numbers, the numbers agree. Where one surface
refuses, the test asserts the refusal and the reason it gives.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

import jnwb

pytest.importorskip("mcp")
from jnwb.mcp_server import (  # noqa: E402
    get_event_codes_and_timings,
    inspect_nwb,
    prepare_signal_reference,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "examples" / "tutorials" / "09_open_data.py"
EXCERPT = REPO_ROOT / "examples" / "data" / "dandi000253_excerpt.nwb"

#: Fields of an `inspect` acquisition entry, which both surfaces report and these tests compare.
ACQUISITION_FIELDS = ("name", "series", "data_shape", "data_dtype", "layout", "rate_hz", "starting_time")

@pytest.fixture(scope="module")
def tutorial():
    spec = importlib.util.spec_from_file_location("open_data_tutorial_agent_surface", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


@pytest.fixture(scope="module")
def excerpt_clock(tutorial):
    """The tutorial's read of the excerpt, and the clock it derives from that read."""
    data = tutorial.read_excerpt(EXCERPT)
    return data, tutorial.derive_clock(data["lfp"], data["trains"])


def _acquisition_view(info: dict) -> dict:
    return {
        "acquisitions": [{f: a[f] for f in ACQUISITION_FIELDS} for a in info["acquisitions"]],
        "interval_tables": [
            (t["name"], t["n_rows"], [c["name"] for c in t["columns"]])
            for t in info["interval_tables"]
        ],
        "units_n_rows": info["units"]["n_rows"],
        "electrodes_n_rows": info["electrodes"]["n_rows"],
    }


def _tutorial_calls() -> list[str]:
    """Names of the jnwb functions the tutorial calls, grepped from its source at collection."""
    return sorted(set(re.findall(r"jnwb\.(\w+)\(", SCRIPT.read_text(encoding="utf-8"))))


def test_inspect_nwb_lists_the_series_shapes_and_rates_that_jnwb_inspect_lists(tutorial, excerpt_clock):
    """Compared field by field: acquisition `name`, `series`, `data_shape`, `data_dtype`, `layout`,
    `rate_hz` and `starting_time`; interval tables' `name`, `n_rows` and column names; units and
    electrodes `n_rows`. The excerpt stores LFP timestamps and no rate, so both surfaces report
    `rate_hz` None, as the tutorial's own read of each segment does."""
    data, _ = excerpt_clock
    direct = _acquisition_view(jnwb.inspect(EXCERPT))
    answer = inspect_nwb(str(EXCERPT))
    assert "error" not in answer, answer
    via_mcp = _acquisition_view(answer)

    # Non-empty precondition: the series inspect lists are the three segments the tutorial reads.
    listed = sorted(s for a in direct["acquisitions"] for s in (a["series"] or []))
    assert listed == sorted(f"{tutorial.LFP_CONTAINER}_{seg}" for seg in tutorial.SEGMENTS), listed
    assert direct["interval_tables"] and direct["units_n_rows"] > 0, direct

    for field in ACQUISITION_FIELDS:
        assert [a[field] for a in via_mcp["acquisitions"]] == [
            a[field] for a in direct["acquisitions"]
        ], f"acquisition field {field!r} differs between inspect_nwb and jnwb.inspect"
    assert via_mcp["interval_tables"] == direct["interval_tables"], "interval tables differ"
    assert via_mcp["units_n_rows"] == direct["units_n_rows"], "units n_rows differ"
    assert via_mcp["electrodes_n_rows"] == direct["electrodes_n_rows"], "electrodes n_rows differ"

    stored = [data["lfp"][seg]["rate"] for seg in tutorial.SEGMENTS]
    assert stored == [None] * len(stored), stored
    assert [a["rate_hz"] for a in direct["acquisitions"]] == [None], direct["acquisitions"]


def test_get_event_codes_with_the_tutorials_code_column_returns_the_tutorials_events(tutorial):
    """The tutorial codes the gratings by `orientation`. Named as `code_column`, the tool returns
    the same onsets, stops and codes as `jnwb.events`; without it, no column matches the tool's
    name rule and it refuses, listing the table's columns."""
    direct = jnwb.events(EXCERPT, table=tutorial.GRATINGS, code_column="orientation")
    assert direct.n_events > 0, "the tutorial's gratings table must hold events"
    table_path = f"/intervals/{tutorial.GRATINGS}"

    res = get_event_codes_and_timings(str(EXCERPT), event_group_path=table_path,
                                      code_column="orientation")
    assert "error" not in res, res
    assert res["total_events"] == direct.n_events
    np.testing.assert_allclose([r["start_time"] for r in res["events"]], direct.onsets,
                               rtol=1e-12, atol=0)
    np.testing.assert_allclose([r["stop_time"] for r in res["events"]], direct.stop_times,
                               rtol=1e-12, atol=0)
    # Blank gratings store orientation NaN, so the codes compare with NaN equal to NaN.
    np.testing.assert_array_equal([float(r["code"]) for r in res["events"]],
                                  [float(c) for c in direct.codes])

    refused = get_event_codes_and_timings(str(EXCERPT), event_group_path=table_path)
    assert refused.get("error_type") == "ParseError", refused
    assert "Could not find a code column" in refused["error"], refused["error"]
    assert "'orientation'" in refused["error"] and "code_column=" in refused["error"], refused

    absent = get_event_codes_and_timings(str(EXCERPT), event_group_path=table_path,
                                         code_column="no_such_column")
    assert absent.get("error_type") == "ParseError", absent


def test_prepare_signal_reference_names_the_timestamps_the_derived_clock_reads(tutorial, excerpt_clock):
    """For each LFP segment the tutorial reads: the reference states no rate, as the tutorial reads
    none, and names a timestamps dataset holding the same ticks the tutorial reads. Those ticks step
    by the derived `tick_step`, and the first start tick is the derived `first_tick`. `tick_rate`
    and `offset_s` come from spike times, which a reference does not carry. The reference names no
    reader, and `acquisition_channel` refuses the same series with the same reason."""
    data, clock = excerpt_clock
    ticks_by_segment = {}
    for seg in tutorial.SEGMENTS:
        series = f"{tutorial.LFP_CONTAINER}_{seg}"
        ref = prepare_signal_reference(
            str(EXCERPT), f"/acquisition/{tutorial.LFP_CONTAINER}/{series}/data")
        assert "error" not in ref, ref

        assert ref["rate_hz"] is None and data["lfp"][seg]["rate"] is None, (
            seg, ref["rate_hz"], data["lfp"][seg]["rate"])
        ts_path = f"/acquisition/{tutorial.LFP_CONTAINER}/{series}/timestamps"
        assert ref["timestamps_path"] == ts_path, ref["timestamps_path"]
        assert ts_path in ref["access_hint"], ref["access_hint"]

        with h5py.File(EXCERPT, "r") as h:
            ticks = np.asarray(h[ts_path][()], dtype=np.float64)
        assert ticks.size > 1, f"{ts_path} holds no ticks to check"
        np.testing.assert_array_equal(ticks, data["lfp"][seg]["ticks"])
        assert list(ref["shape"]) == list(data["lfp"][seg]["data"].shape), (seg, ref["shape"])
        steps = np.unique(np.diff(ticks))
        assert steps.size == 1, (seg, steps[:5])
        np.testing.assert_allclose(steps, [clock.tick_step], rtol=1e-12, atol=0)
        ticks_by_segment[seg] = ticks

        assert ref["reader"] is None, ref["reader"]
        with pytest.raises(jnwb.NWBInspectError, match="has no constant sampling rate"):
            jnwb.acquisition_channel(EXCERPT, name=f"{tutorial.LFP_CONTAINER}/{series}", channel=0)

    np.testing.assert_allclose(ticks_by_segment["start"][0], clock.first_tick, rtol=1e-12, atol=0)


def test_the_tutorial_call_set_is_read_from_the_script():
    assert _tutorial_calls(), "the grep found no jnwb call in the tutorial, so nothing is checked"


@pytest.mark.parametrize("name", _tutorial_calls())
def test_every_function_the_tutorial_calls_has_a_skill_routing_row(name):
    """Each name the tutorial calls is public and appears as an inline `jnwb.<name>(` in at least
    one skill: its SKILL.md or a page under its `references/`. The names come from the grep at
    collection time."""
    assert name in jnwb.__all__, f"the tutorial calls jnwb.{name}, which jnwb.__all__ does not export"
    pages = {
        str(p.relative_to(REPO_ROOT / "skills")): p.read_text(encoding="utf-8")
        for p in sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
        + sorted((REPO_ROOT / "skills").glob("*/references/*.md"))
    }
    assert any(k.endswith("SKILL.md") for k in pages), "no skill pages found, so nothing is checked"
    pattern = re.compile(r"`jnwb\." + re.escape(name) + r"\(")
    routed = [skill for skill, text in pages.items() if pattern.search(text)]
    assert routed, f"no skill page routes an inline `jnwb.{name}(`"
