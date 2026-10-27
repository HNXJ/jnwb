"""vFLIP2 acceptance under nuisance conditions: scripts/vflip2_nuisance.py.

The tests check that the snr sweep's smoke run reproduces the matched SNR-0 null of the 0.2.13 recovery run,
probe by probe; that every count lies inside its Clopper-Pearson interval; that planted recovery needs
acceptance and an estimate within one contact of the generator depth z0; that the evidence record holds every
probe and every cell; that the shared-reference draw leaves a ratio-0 probe unchanged; and that a refused probe
is recorded with its message. The counts themselves live in the evidence file, not in these asserts.
"""

from __future__ import annotations

import concurrent.futures as futures
import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # needed: the installed-wheel run clears pythonpath
from jnwb import clopper_pearson  # noqa: E402
from jnwb.testing import synth_vflip2_crossover  # noqa: E402
from scripts import vflip2_nuisance as nui  # noqa: E402
from scripts import vflip2_recovery as rec  # noqa: E402


@pytest.fixture(scope="module")
def snr_smoke():
    """The snr sweep at two probes per cell, through the sweep runner (the smoke path, pooled)."""
    with futures.ProcessPoolExecutor(max_workers=4) as pool:
        return nui.run_cells(nui.sweep_cells("snr"), n=2, pool=pool)


def test_smoke_runs_the_snr_sweep_and_its_null_is_the_recovery_null(snr_smoke):
    cells = nui.sweep_cells("snr")
    assert len(cells) == 6 and cells[0]["snr"] == 0.0  # precondition: the null cell, then five planted cells
    default = nui.default_cell(0.0)
    assert all(cells[0][k] == default[k] for k in ("tau_s", "shared_ratio", "spacing", "fs", "n_samples"))
    for out in snr_smoke:
        assert out["n"] == 2
        assert out["accepted"] + out["refused"] <= out["n"]
    recorded = json.loads(rec.JSON_PATH.read_text(encoding="utf-8"))["probes"]["null"][:2]
    assert [p["child"] for p in recorded] == [rec.CHILD_MEASURED, rec.CHILD_MEASURED + 1]  # precondition
    got = snr_smoke[0]["probes"]
    assert [p["accepted"] for p in got] == [p["accepted"] for p in recorded]
    assert [p["window"] for p in got] == [p["window"] for p in recorded]


def test_every_count_lies_inside_its_interval(snr_smoke):
    assert any(r["accepted"] > 0 for r in snr_smoke if r["cell"]["kind"] == "planted")  # precondition
    checked = 0
    for r in snr_smoke:
        m = nui.measures(r)
        if r["cell"]["kind"] == "planted":
            assert m["recovery"]["k"] <= r["accepted"]  # recovery needs acceptance
        for name, block in m.items():
            k, n = block["k"], block["n"]
            lo, hi = block["ci95"]
            assert block["ci95"] == [round(v, 4) for v in clopper_pearson(k, n)], (name, block)
            assert lo <= k / n <= hi, (r["cell"]["name"], name, block)
            checked += 1
    assert checked == 11  # six acceptance counts and five planted recovery counts


def test_planted_recovery_needs_acceptance_and_an_estimate_within_one_contact_of_z0():
    assert nui.recovered({"accepted": True, "zhat": 12.0, "z0": 13})  # one contact away counts
    assert not nui.recovered({"accepted": True, "zhat": 11.0, "z0": 13})  # two contacts away does not
    assert not nui.recovered({"accepted": False, "zhat": 13.0, "z0": 13})  # not accepted does not
    assert not nui.recovered({"accepted": True, "zhat": None, "z0": 13})  # no estimate does not


def test_the_evidence_record_holds_every_probe_and_every_cell():
    snr4 = nui.cell("snr", "snr 4", snr=4.0)
    probes = [{"index": i, "z0": 8, "child": rec.CHILD_MEASURED + i, "accepted": True, "window": [2, 9],
               "zhat": 8.0, "omega": 1.5, "refused": None} for i in range(2)]
    result = {"cell": snr4, "n": 2, "accepted": 2, "refused": 0, "messages": [], "probes": probes}
    md, doc = nui.document([result], None, 2)
    assert len(doc["sweeps"]["snr"][0]["probes"]) == 2  # every probe
    assert "| planted | snr 4 (default cell) | 2 | 2 of 2" in md  # one row per cell


def test_shared_reference_at_ratio_zero_is_the_plain_probe():
    kw = dict(z0=12, child=rec.CHILD_MEASURED, snr=4.0, tau_s=0.03, n_samples=rec.N_SAMPLES, fs=rec.FS)
    plain = nui.make_lfp(shared_ratio=0.0, **kw)
    shared = nui.make_lfp(shared_ratio=1.0, **kw)
    assert plain.shape == (rec.N_CONTACTS, rec.N_SAMPLES)  # precondition
    assert not np.array_equal(plain, shared)  # precondition: ratio 1 adds a reference
    bare = synth_vflip2_crossover(rec.N_CONTACTS, rec.N_SAMPLES, rec.FS, z0=12, snr=4.0, tau_s=0.03,
                                  rng=np.random.default_rng(rec.children()[rec.CHILD_MEASURED])).lfp
    assert np.array_equal(plain, bare)


def test_a_refused_probe_is_recorded_with_the_estimators_message():
    out = nui.run_cell(nui.cell("spacing", "250 um", spacing=250.0, snr=0.0), n=1)
    assert out["n"] == 1
    assert out["refused"] == 1  # vflip2 refuses spacing above 200 um
    assert out["accepted"] == 0  # a refused probe is not counted as accepted
    assert any("at most 200 um" in msg for msg in out["messages"])
