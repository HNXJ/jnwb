"""Item 15-11: the planted vFLIP2 crossover generator, its oracle, and scripts/vflip2_recovery.py.

The contract is artifacts/evidence/0.2.13/vflip2_generator_design.md. The tests check the generator's
definitions, the window definition, the helper table against its plain-numpy recomputation, the frozen
oracle, and the script's caller path. Calibration outcomes live in the evidence file, not here.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

from jnwb.testing import synth_vflip2_crossover  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
from scripts import vflip2_recovery as rec  # noqa: E402


def _probe_psd(lfp: np.ndarray):
    """A five-trial probe's PSD and grid, from the estimator's own front end (as vflip2_from_lfp)."""
    psd = rec.V._psd_hanning(lfp.reshape(rec.N_CONTACTS, 5, 1000).transpose(0, 2, 1), rec.FS)
    return psd, np.arange(1, psd.shape[1] + 1, dtype=float)


def test_generator_is_exported_and_matches_its_definitions():
    import jnwb.testing as testing

    assert "synth_vflip2_crossover" in testing.__all__
    z0 = 12
    assert 8 <= z0 <= 23
    null = synth_vflip2_crossover(z0=z0, n_samples=20000, snr=0.0, rng=3)
    planted = synth_vflip2_crossover(z0=z0, n_samples=20000, snr=4.0, rng=3)
    noiseless = synth_vflip2_crossover(z0=z0, n_samples=20000, snr=4.0, background=False, rng=3)
    assert null.lfp.shape == (32, 20000)
    assert planted.phi == pytest.approx(np.exp(-1.0 / (1000.0 * 0.03)), rel=1e-12)
    contacts = np.arange(32, dtype=float)
    expected_low = np.clip(0.5 + (contacts - z0) / 31.0, 0.05, 0.95)
    assert np.array_equal(planted.low_weight, expected_low)
    assert np.array_equal(planted.high_weight, 1.0 - expected_low)
    assert planted.low_weight[z0] == 0.5
    # Planted minus null is the motif alone: the same draws as the background-free probe.
    assert np.allclose(planted.lfp - null.lfp, noiseless.lfp, rtol=0, atol=1e-12)
    # Stationary variance 1 (pooled over contacts and samples), and SNR as a total-variance ratio.
    assert abs(null.lfp.var() - 1.0) < 0.05
    assert abs((planted.lfp - null.lfp).var() / null.lfp.var() - 4.0) < 0.4


def test_generator_refuses_a_bool_depth():
    # True is an int in Python; as a contact index it would silently mean depth 1.
    assert synth_vflip2_crossover(z0=8, n_samples=64, snr=0.0, rng=0).z0 == 8  # precondition
    with pytest.raises(TypeError):
        synth_vflip2_crossover(z0=True, n_samples=64, snr=0.0, rng=0)


def test_first_sample_is_drawn_from_the_stationary_distribution():
    first = np.array([synth_vflip2_crossover(z0=8, n_samples=200, snr=0.0, rng=s).lfp[:, 0]
                      for s in range(300)])
    assert first.size == 300 * 32  # precondition: 300 seeds, 32 contacts
    assert abs(first.var() - 1.0) < 0.08


def test_window_is_undefined_only_when_every_row_is_clipped_at_one_bound():
    low = synth_vflip2_crossover(z0=8, n_samples=64, snr=0.0, rng=0).low_weight
    assert np.all(low[22:32] == 0.95)  # precondition: contacts 22..31 are clipped at the top
    assert not rec.window_defined(low, 23, 29)  # rows 22..28 (0-based), all clipped at 0.95
    assert rec.window_defined(low, 21, 28)  # row 20 (0-based) is not clipped at 0.95
    assert rec.window_defined(low, 1, 7)


def test_frozen_count_is_the_smallest_count_that_passes():
    counts = (200, 800, 3200)
    assert rec.choose_count({200: False, 800: True, 3200: True}, counts) == 800
    assert rec.choose_count({200: True, 800: False, 3200: True}, counts) == 200
    assert rec.choose_count({200: False, 800: False, 3200: False}, counts) is None


@pytest.fixture(scope="module")
def probe_table():
    """A depth-12 measured probe: its PSD, its weights and the helper table of its windows."""
    child = rec.children()[rec.CHILD_MEASURED]
    probe = synth_vflip2_crossover(z0=12, n_samples=rec.N_SAMPLES, snr=rec.SNR,
                                   rng=np.random.default_rng(child))
    psd, freqs = _probe_psd(probe.lfp)
    return psd, freqs, probe.low_weight, rec.window_table(psd, freqs, probe.low_weight)


def test_helper_table_matches_its_plain_numpy_recomputation(probe_table):
    psd, freqs, weights, helper = probe_table
    plain = rec.plain_rows(psd, freqs, weights)
    assert len(helper) == 351  # windows of 32 rows: 6-row minimum, proximal 1..27, distal to 32
    assert any(r["defined"] and not np.isnan(r["z_planted"]) for r in helper)  # precondition
    assert rec.compare_rows(helper, plain) == []


def test_noiseless_control_returns_an_accepted_crossover_inside_its_window():
    # Structure only: how close the crossover lands to the background-off oracle is a measure in the
    # evidence file (the control line of vflip2_recovery.md), not an assertion here.
    kids = rec.children()
    lfp = synth_vflip2_crossover(z0=rec.Z0_FIRST, n_samples=rec.N_SAMPLES, snr=rec.SNR, background=False,
                                 rng=np.random.default_rng(kids[rec.CHILD_CONTROL])).lfp
    psd, freqs = _probe_psd(lfp)
    # Precondition: the control has power in both bands at every contact.
    assert (psd[:, rec._in_band(freqs, rec.VFLIP2_LOW_BAND_HZ)].sum(axis=1) > 0).all()
    assert (psd[:, rec._in_band(freqs, rec.VFLIP2_HIGH_BAND_HZ)].sum(axis=1) > 0).all()
    out = rec.probe_job(("noiseless", 0, rec.Z0_FIRST, rec.CHILD_CONTROL, kids[rec.CHILD_CONTROL]))
    assert out["accepted"], "precondition: vflip2 accepts this control seed"
    lo, hi = out["window"]
    assert lo <= out["zhat"] <= hi, (out["zhat"], out["window"])


def test_background_off_children_are_appended_after_the_measured_ones():
    kids = rec.children()
    assert len(kids) == rec.N_CHILDREN == 260
    assert rec.CONTROL_ORACLE_CHILD[("A", 8)] == 228 and rec.CONTROL_ORACLE_CHILD[("B", 23)] == 259
    # Every child the background-on oracle and the runs use keeps its seed.
    old = np.random.SeedSequence(rec.ENTROPY).spawn(rec.N_BACKGROUND_CHILDREN)
    assert all(np.array_equal(a.generate_state(4), b.generate_state(4)) for a, b in zip(kids, old))


def test_seeds_reproduce_one_probe_and_separate_two():
    kids = rec.children()
    make = lambda child: synth_vflip2_crossover(  # noqa: E731
        z0=12, n_samples=500, snr=4.0, rng=np.random.default_rng(child)).lfp
    assert np.array_equal(make(kids[16]), make(kids[16]))
    assert not np.array_equal(make(kids[16]), make(kids[17]))


def test_frozen_oracle_is_gated_and_matches_plain_numpy():
    doc = json.loads(rec.ORACLE_PATH.read_text(encoding="utf-8"))
    kids = rec.children()
    for kind in rec.KINDS:
        frozen = doc["frozen_count"][kind]
        gate = {int(c): doc["disagreement"][kind][c]["passes"] for c in doc["disagreement"][kind]}
        assert rec.choose_count(gate, doc["counts_trials"]) == frozen
        assert doc["disagreement"][kind][str(frozen)]["planted_bad"] == 0
    # Rederive the window tables at depths 8 and 23 from the stored A PSDs of both grids and of the
    # control. Every window, omega and good included, must equal the plain-numpy recomputation.
    assert doc["control_oracle"]["stats"]["passes"]
    for z0 in (8, 23):
        weights = rec.low_weight_for(z0)
        for kind in rec.KINDS:
            freqs = np.array(doc["freqs"][kind], dtype=float)
            psd = np.array(doc["psd"][kind][str(z0)]["psd"], dtype=float)
            rows = rec.window_table(psd, freqs, weights)
            # Precondition: a full table, with good windows so that omega is compared.
            assert len(rows) == 351 and sum(r["good"] for r in rows) > 0
            assert rec.compare_rows(rows, rec.plain_rows(psd, freqs, weights)) == []
        cfreqs = np.array(doc["control_oracle"]["freqs"], dtype=float)
        cpsd = np.array(doc["control_oracle"]["psd"][str(z0)]["psd"], dtype=float)
        crows = rec.window_table(cpsd, cfreqs, weights)
        assert len(crows) == 351 and sum(r["good"] for r in crows) > 0
        assert rec.compare_rows(crows, rec.plain_rows(cpsd, cfreqs, weights)) == []
    # The stored s1 A PSD at depth 8 is the one its seed reproduces exactly.
    kind, z0 = "s1", 8
    count = doc["frozen_count"][kind]
    idx = doc["children"][f"{kind}_{count}_A"]["index"]
    out = rec.oracle_job((kind, count, "A", z0, idx, kids[idx]))
    assert out["plain_mismatches"] == []
    # The oracle was stored on one platform; FFT rounding differs across platforms, and the
    # smallest bins sit three decades below the largest, so their relative error is amplified.
    np.testing.assert_allclose(out["psd"], np.array(doc["psd"][kind][str(z0)]["psd"], dtype=float),
                               rtol=1e-9, atol=0)


def test_one_sided_nan_is_indeterminate_and_gates_nothing():
    nan = float("nan")

    def table(zs):
        return {"rows": [{"p": 1 + i, "d": 7 + i, "defined": True, "z_planted": z, "z_picked": z,
                          "bands": None} for i, z in enumerate(zs)], "plain_mismatches": []}

    # Window 0: one oracle finds a crossover, the other does not (indeterminate, not gated).
    # Window 1: a 1-contact difference (passes). Window 2: a 2-contact difference (fails).
    mixed = rec.pair_stats("s1", 800, [8], {("s1", 800, "A", 8): table([5.0, 5.0, 5.0]),
                                            ("s1", 800, "B", 8): table([nan, 6.0, 7.0])})
    assert mixed["indeterminate"] == 1 and mixed["n_defined"] == 3
    assert mixed["planted_bad"] == 1 and not mixed["passes"]
    only_nan = rec.pair_stats("s1", 800, [8], {("s1", 800, "A", 8): table([5.0, 5.0]),
                                               ("s1", 800, "B", 8): table([nan, 6.0])})
    assert only_nan["indeterminate"] == 1 and only_nan["planted_bad"] == 0 and only_nan["passes"]


def test_caller_prints_the_recovery_table_at_one_probe():
    # One probe, loaded from the frozen oracle (no rebuild), so the test stays under the fast-test budget.
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vflip2_recovery.py"), "--n", "1",
         "--oracle-file", str(rec.ORACLE_PATH)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = proc.stdout
    assert "oracle loaded from" in out
    assert "pool check: 5 probes serial vs pool identical" in out
    for row in ("| 1 | Detection", "| 3 | Unconditional recovery", "| 6 | Null acceptance"):
        assert row in out, row
    # Shape only: the calibration counts belong to the evidence file, not to a test assertion.
    assert re.search(r"^summary: detection \d+ of 1; recovery \d+ of 1; null accepted \d+ of 1$",
                     out, re.M), out[-400:]
