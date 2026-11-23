"""vFLIP2: the port against vFLIP2.m's output, its refusals, its bin-width dependence, and its acceptance
under nuisance conditions and on seeds 0 to 9.

The reference is ``tests/fixtures/vflip2_matlab_reference.json``: eight cases chosen from the
300 synthetic PSDs that vFLIP2.m ran in MATLAB, and ``power_example`` from the same run. The
file records the sha256 of vFLIP2.m. Each test asserts the precondition of the case it reads
before it checks the port. The sections after the port are marked by comments.
"""

from __future__ import annotations

import concurrent.futures as futures
import json
import pathlib
import sys
from pathlib import Path

import numpy as np
import pytest

import jnwb
from jnwb import clopper_pearson
from jnwb.laminar import VFlip2Result, vflip2, vflip2_from_lfp
from jnwb.testing import synth_vflip2_crossover

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # needed: the installed-wheel run clears pythonpath
from scripts import vflip2_nuisance as nui  # noqa: E402
from scripts import vflip2_recovery as rec  # noqa: E402
from scripts import vflip2_simulation as sim  # noqa: E402

DOC = json.loads((Path(__file__).resolve().parent / "fixtures"
                  / "vflip2_matlab_reference.json").read_text(encoding="utf-8"))
# The cut is vFLIP2.m's, read from the reference rather than from the module under test.
OMEGA_CUT = DOC["omega_cut"]
CASES = {case["name"]: case for case in DOC["cases"]}
NAMES = list(CASES)
WINDOW = [n for n in NAMES if CASES[n]["matlab"]["window"]]
BELOW = [n for n in NAMES if CASES[n]["class"] == "below_cut"]
NO_WINDOW = [n for n in NAMES if not CASES[n]["matlab"]["window"]]
# Searched with "both", the best window is inverted: restricting to upright changes the answer.
BOTH_INVERTED = [n for n in NAMES if CASES[n]["orientation"] == "both"
                 and CASES[n]["class"] == "accepted_inverted"]


def _psd(case):
    """JSON rows to float arrays; null is NaN, as the reference writes a NaN row."""
    return np.array([[np.nan if v is None else v for v in row] for row in case["psd"]],
                    dtype=float)


def _freqs(case, psd):
    return case["freqbinsize"] * np.arange(1, psd.shape[1] + 1)


def _run(case, orientation=None):
    psd = _psd(case)
    return vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0,
                  orientation=case["orientation"] if orientation is None else orientation)


def _quality(omega):
    return "absent" if omega <= 6 else ("medium" if omega <= 12 else "strong")


def test_vflip2_is_a_public_export():
    assert jnwb.vflip2 is vflip2
    assert jnwb.VFlip2Result is VFlip2Result
    assert {"vflip2", "VFlip2Result"} <= set(jnwb.__all__)


def test_fixture_covers_every_category_it_claims():
    classes = {c["class"] for c in DOC["cases"]}
    assert "accepted_upright" in classes, "no accepted upright window"
    assert "accepted_inverted" in classes, "no accepted inverted window"
    assert BELOW, "no case rejected below the cut"
    assert NO_WINDOW, "no case without a window"
    assert {c["orientation"] for c in DOC["cases"]} >= {"both", "upright", "inverted"}
    assert {c["freqbinsize"] for c in DOC["cases"]} >= {0.5, 1.0, 2.0}
    assert "noise" in {c["kind"] for c in DOC["cases"]}, "no noise-kind case"
    assert any(np.isnan(_psd(c)[0]).any() or np.isnan(_psd(c)[-1]).any()
               for c in DOC["cases"]), "no case with a NaN end row"
    assert BOTH_INVERTED, "no case searched with both whose best window is inverted"
    assert "power_example" in CASES
    assert len(DOC["source"]["sha256"]) == 64
    assert len(DOC["cases"]) == 9, f"expected 8 cases and power_example, got {len(DOC['cases'])}"


@pytest.mark.parametrize("name", WINDOW)
def test_every_window_matches_matlab(name):
    case = CASES[name]
    m = case["matlab"]
    # Precondition: the MATLAB numbers agree with the cut and with the case's class.
    assert m["accepted"] == (m["omega"] > OMEGA_CUT)
    if case["class"].startswith("accepted_"):
        assert m["accepted"] and m["omega"] > OMEGA_CUT
        assert m["orientation"] == case["class"][len("accepted_"):]
    res = _run(case)
    assert res.omega is not None
    np.testing.assert_allclose(res.omega, m["omega"], rtol=1e-9)
    np.testing.assert_allclose(res.goodness, m["goodness"], rtol=1e-9)
    assert res.proximal_channel == m["proximal_channel"]
    assert res.distal_channel == m["distal_channel"]
    assert res.low_peak_channel == m["low_peak_channel"]
    assert res.high_peak_channel == m["high_peak_channel"]
    assert res.crossover_channel == m["crossover_channel"]
    assert res.orientation == m["orientation"]
    assert res.low_band_hz == tuple(m["low_band_hz"])
    assert res.high_band_hz == tuple(m["high_band_hz"])
    assert res.accepted == m["accepted"]
    assert res.accepted == (res.omega > OMEGA_CUT)
    assert res.motif_quality == _quality(m["omega"])


@pytest.mark.parametrize("name", BELOW)
def test_below_the_cut_the_best_window_is_returned_and_refused(name):
    case = CASES[name]
    m = case["matlab"]
    # Precondition: a window exists and its omega is at or below the cut.
    assert m["window"] and m["omega"] <= OMEGA_CUT and not m["accepted"]
    res = _run(case)
    assert res.accepted is False
    assert res.motif_quality == "absent"
    np.testing.assert_allclose(res.omega, m["omega"], rtol=1e-9)
    assert (res.proximal_channel, res.distal_channel) == (m["proximal_channel"],
                                                          m["distal_channel"])


@pytest.mark.parametrize("name", NO_WINDOW)
def test_no_window_returns_an_empty_result(name):
    case = CASES[name]
    assert not case["matlab"]["window"]  # precondition: MATLAB found no window
    res = _run(case)
    assert res.omega is None and res.goodness is None
    assert res.accepted is False
    assert res.motif_quality is None
    assert res.low_band_hz is None and res.proximal_channel is None
    assert res.omega_cut == OMEGA_CUT


def _clean_psd():
    case = CASES["c0170"]  # accepted, upright, no NaN rows
    psd = _psd(case)
    assert np.isfinite(psd).all(), "fixture must be a finite probe"
    return case, psd


def test_an_interior_nan_row_is_refused():
    case, psd = _clean_psd()
    psd[5] = np.nan
    with pytest.raises(ValueError, match="NaN row between"):
        vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0)


def test_negative_power_is_refused():
    case, psd = _clean_psd()
    psd[5, 7] = -1.0
    with pytest.raises(ValueError, match="non-negative"):
        vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0)


def test_non_finite_power_is_refused():
    case, psd = _clean_psd()
    psd[5, 7] = np.inf
    with pytest.raises(ValueError, match="finite"):
        vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0)


def test_an_unknown_orientation_is_refused():
    case, psd = _clean_psd()
    with pytest.raises(ValueError, match="orientation must be one of"):
        vflip2(psd, _freqs(case, psd), contact_spacing=case["intdist"] * 1000.0,
               orientation="sideways")


def test_layer4_thickness_is_vflip2_m_sum_to_the_last_bit():
    """vFLIP2.m divides each thickness by 1000 and then sums; MATLAB R2024a prints
    0.58600000000000007638, one ulp above 0.586, and the ulp sets the shortest window at
    146.5 um (5 contacts in MATLAB, 4 from 0.586 itself)."""
    from jnwb.laminar._vflip2 import LAYER4_THICKNESS_MM

    assert LAYER4_THICKNESS_MM == 0.58600000000000007638
    assert LAYER4_THICKNESS_MM != 0.586
    assert np.ceil(LAYER4_THICKNESS_MM / 0.1465) == 5 and np.ceil(0.586 / 0.1465) == 4


@pytest.mark.parametrize("kwargs, match", [
    ({"contact_spacing": 0.0}, "contact_spacing"),
    ({"contact_spacing": float("nan")}, "contact_spacing"),
    ({"layer4_thickness_mm": -0.5}, "layer4_thickness_mm"),
    ({"omega_cut": float("nan")}, "omega_cut"),
])
def test_bad_scalar_arguments_are_refused(kwargs, match):
    case, psd = _clean_psd()
    args = {"contact_spacing": case["intdist"] * 1000.0, **kwargs}
    with pytest.raises(ValueError, match=match):
        vflip2(psd, _freqs(case, psd), **args)


def test_a_contact_spacing_above_200_um_is_refused():
    case, psd = _clean_psd()
    with pytest.raises(ValueError, match=r"vflip2.*contact_spacing.*200"):
        vflip2(psd, _freqs(case, psd), contact_spacing=200.5)


def test_a_contact_spacing_of_201_um_is_refused():
    case, psd = _clean_psd()
    with pytest.raises(ValueError, match=r"vflip2.*contact_spacing.*200"):
        vflip2(psd, _freqs(case, psd), contact_spacing=201.0)


def test_a_contact_spacing_of_200_um_still_searches_windows():
    rec = synth_vflip2_crossover(n_channels=32, n_samples=5000, fs=1000.0, z0=16, rng=0)
    # Precondition: the planted probe passes a window at 100 um, so a None at 200 um would
    # mean the 200 um search found nothing.
    assert vflip2_from_lfp(rec.lfp, 1000.0, contact_spacing=100.0).omega is not None
    assert vflip2_from_lfp(rec.lfp, 1000.0, contact_spacing=200.0).omega is not None


def test_a_contact_spacing_of_199_um_still_searches_windows():
    rec = synth_vflip2_crossover(n_channels=32, n_samples=5000, fs=1000.0, z0=16, rng=0)
    # Precondition: the planted probe passes a window at 100 um, so the 199 um search is
    # compared with a search that finds one.
    assert vflip2_from_lfp(rec.lfp, 1000.0, contact_spacing=100.0).omega is not None
    assert vflip2_from_lfp(rec.lfp, 1000.0, contact_spacing=199.0).omega is not None


def test_a_reversed_orientation_at_200_um_still_runs():
    rec = synth_vflip2_crossover(n_channels=32, n_samples=5000, fs=1000.0, z0=16, rng=0)
    # Precondition: the best window at 200 um is upright, so "inverted" is the reversed search.
    assert vflip2_from_lfp(rec.lfp, 1000.0, contact_spacing=200.0).orientation == "upright"
    reversed_search = vflip2_from_lfp(rec.lfp, 1000.0, contact_spacing=200.0, orientation="inverted")
    assert reversed_search.orientation in (None, "inverted")


def test_non_uniform_freqs_are_refused():
    case, psd = _clean_psd()
    freqs = _freqs(case, psd).copy()
    freqs[3] += 0.25 * (freqs[1] - freqs[0])
    with pytest.raises(ValueError, match="uniformly spaced"):
        vflip2(psd, freqs, contact_spacing=case["intdist"] * 1000.0)


def test_upright_restricts_the_search():
    assert BOTH_INVERTED, "fixture must hold a case searched with both whose best window is inverted"
    case = CASES[BOTH_INVERTED[0]]
    m = case["matlab"]
    # Precondition: the case is searched with "both" and its best window is inverted,
    # so restricting to upright must change the answer.
    assert case["orientation"] == "both" and m["orientation"] == "inverted"
    both = _run(case, orientation="both")
    upright = _run(case, orientation="upright")
    assert upright.orientation != both.orientation
    assert upright.orientation in (None, "upright")
    assert upright.omega is None or upright.omega <= both.omega


# Bin-width sensitivity (analytic omega term)
#
# vFLIP2's bin-width dependence, pinned to the analytic term of its omega.
#
# The port computes omega = log(ps_dist * band_dist * |G| * ch_span * f_span), with
# f_span = deep.size * sup.size * binsize**2 (jnwb/laminar/_vflip2.py, the omega line of the
# best-window search).
#
# Scale the frequency axis by r and keep the PSD columns. When the bands select the same columns,
# with their edges scaled by r, deep.size and sup.size do not change. ps_dist, band_dist, |G| and
# ch_span depend only on column values, row indices and those columns, so they do not change
# either. Then
#
#     omega(r) - omega(1) = log(f_span(r) / f_span(1))
#                         = 2 log r + log(n_low(r) / n_low(1)) + log(n_high(r) / n_high(1)),
#
# where n = (top edge - bottom edge) / binsize + 1 for each band, read from the returned edges.
# The test asserts the same columns, so the count terms are zero here, and it asserts that
# instead of assuming it.
#
# The scale is 1.005. The power example's bands are (5, 45) Hz and (46, 149) Hz. Scales from 1 up
# to 150/149 keep the high band's columns; scales below 1 let its top edge pass 149 Hz and change
# the selection (observed for 0.99 and 0.95 when this test was written).


CASE = next(c for c in DOC["cases"] if c["name"] == "power_example")
SPACING_UM = CASE["intdist"] * 1000.0
SCALE = 1.005


def _power_example_psd():
    return np.array([[np.nan if v is None else v for v in row] for row in CASE["psd"]],
                    dtype=float)


def _power_example_freqs(scale):
    n = len(CASE["psd"][0])
    return scale * CASE["freqbinsize"] * np.arange(1, n + 1, dtype=float)


def _bins(edges, binsize):
    """Columns in a contiguous band from its first to its last frequency."""
    return round((edges[1] - edges[0]) / binsize) + 1


def test_fixture_is_accepted_at_its_own_bin_width():
    result = vflip2(_power_example_psd(), _power_example_freqs(1.0), contact_spacing=SPACING_UM)
    assert result.accepted and result.omega > OMEGA_CUT, "the power example must be accepted"
    np.testing.assert_allclose(result.omega, CASE["matlab"]["omega"], rtol=1e-9)


def test_bin_width_shift_is_the_analytic_term():
    base = vflip2(_power_example_psd(), _power_example_freqs(1.0), contact_spacing=SPACING_UM)
    wide = vflip2(_power_example_psd(), _power_example_freqs(SCALE), contact_spacing=SPACING_UM)
    # Precondition: the same window, peaks, crossover and orientation; the bands are the same
    # columns, with edges SCALE times the base edges.
    assert base.accepted and wide.accepted, "both runs must be accepted"
    for name in ("orientation", "proximal_channel", "distal_channel", "low_peak_channel",
                 "high_peak_channel", "crossover_channel"):
        assert getattr(wide, name) == getattr(base, name), name
    np.testing.assert_allclose(wide.low_band_hz, SCALE * np.array(base.low_band_hz),
                               rtol=1e-12, atol=0)
    np.testing.assert_allclose(wide.high_band_hz, SCALE * np.array(base.high_band_hz),
                               rtol=1e-12, atol=0)
    n_low, n_high = _bins(base.low_band_hz, 1.0), _bins(base.high_band_hz, 1.0)
    n_low_w, n_high_w = _bins(wide.low_band_hz, SCALE), _bins(wide.high_band_hz, SCALE)
    assert (n_low_w, n_high_w) == (n_low, n_high), "the band column counts must be unchanged"
    expected = 2.0 * np.log(SCALE) + np.log(n_low_w / n_low) + np.log(n_high_w / n_high)
    assert abs(expected) > 1e-3, "the scale must move omega"
    # omega is near 13, so its rounding is about 2e-15; 1e-12 absolute is far below the shift.
    np.testing.assert_allclose(wide.omega - base.omega, expected, rtol=0, atol=1e-12)


def test_the_evidence_table_matches_the_script_on_the_power_example():
    """Every Dryad row of the committed evidence file is what scripts/vflip2_sensitivity.py
    computes now, so the file cannot go stale while vflip2 changes."""
    import sys

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.append(str(root))  # needed: the installed-wheel run clears pythonpath
    from scripts import vflip2_sensitivity as sens

    psd, freqs, spacing, _ = sens.load_power_example()
    computed = sens.probe_all(psd, freqs, spacing)
    rows = sens.EVIDENCE.read_text(encoding="utf-8").split("## Dryad power example")[1]
    rows = rows.split("\n## ")[0]
    for variant in sens.VARIANTS:
        group, value = sens.label(variant)
        expected = f"| {group} | {value} | {sens.fmt(computed[variant]['omega'])} |"
        assert expected in rows, expected
    assert len(sens.VARIANTS) >= 16, "every variant of the evidence file must be checked"


# Nuisance acceptance (scripts/vflip2_nuisance.py)
#
# vFLIP2 acceptance under nuisance conditions: scripts/vflip2_nuisance.py.
#
# The tests check that the snr sweep's smoke run reproduces the matched SNR-0 null of the 0.2.13 recovery run,
# probe by probe; that every count lies inside its Clopper-Pearson interval; that planted recovery needs
# acceptance and an estimate within one contact of the generator depth z0; that the evidence record holds every
# probe and every cell; that the shared-reference draw leaves a ratio-0 probe unchanged; and that a refused probe
# is recorded with its message. The counts themselves live in the evidence file, not in these asserts.




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


# Simulation pins, seeds 0 to 9 (scripts/vflip2_simulation.py)
#
# scripts/vflip2_simulation.py on seeds 0 to 9: pinned counts and the preconditions they rest on.
#
# The subset is the script's own first ten seeds (SEEDS[:10]), and every number comes from the
# script's functions, so a change to its seed list or its SNR moves the counts and fails the pins.



SUBSET = sim.SEEDS[:10]
PINNED = {
    "planted_probes": 10,
    "planted_accepted": 9,
    "planted_within_one_contact": 2,
    "null_probes": 10,
    "null_accepted": 3,
}
# 3 sigma bound on |Pearson r| between row index and log10 band power, for n_rows independent rows.
R_BOUND = 3 / np.sqrt(sim.N_CONTACTS)


@pytest.fixture(scope="module")
def outcomes():
    return sim.run_sets(seeds=SUBSET)


@pytest.fixture(scope="module")
def lfps():
    """Per seed: planted LFP at the script's SNR, null LFP at snr 0, and planted LFP at half the SNR."""
    return {
        seed: (sim.build_probe(seed, snr=sim.SNR), sim.build_probe(seed, snr=0.0),
               sim.build_probe(seed, snr=sim.SNR / 2))
        for seed in SUBSET
    }


def test_pinned_counts_on_seeds_0_to_9(outcomes):
    planted, null = outcomes
    assert len(planted) == len(null) == 10
    assert sim.counts(planted, null) == PINNED


def test_planted_and_null_share_their_background(lfps):
    """planted(s) = background + s * motif, the background drawn from the seed alone.

    So planted(SNR) - null = 2 * (planted(SNR/2) - null) holds only when all three calls draw
    one background, the null's included; the residual is background(planted) - background(null).
    """
    assert len(lfps) == 10, "the subset must hold the ten seeds of SEEDS[:10]"
    for seed, (planted, null, half) in lfps.items():
        assert np.allclose(planted - null, 2.0 * (half - null), rtol=1e-9, atol=1e-12), seed


def test_planted_component_carries_the_band_gradient(lfps):
    """Planted minus null (the motif alone): gamma higher on rows 0..c, beta higher on rows c+1..last."""
    assert len(lfps) == 10, "the subset must hold the ten seeds of SEEDS[:10]"
    for seed, (planted, null, _) in lfps.items():
        component = planted - null
        assert np.abs(component).max() > 0, seed
        c = sim.planted_contact(seed)
        gamma, beta = sim.band_rows(component)
        assert gamma[: c + 1].mean() > gamma[c + 1:].mean(), seed
        assert beta[c + 1:].mean() > beta[: c + 1].mean(), seed


def test_null_probes_have_no_larger_gradient_than_noise_allows(lfps):
    """For each null probe and band: |Pearson r(row index, log10 band power)| < 3 / sqrt(n_rows)."""
    rows = np.arange(sim.N_CONTACTS, dtype=float)
    assert len(lfps) == 10, "the subset must hold the ten seeds of SEEDS[:10]"
    for seed, (_, null, _) in lfps.items():
        for name, band in zip(("gamma", "beta"), sim.band_rows(null)):
            r = np.corrcoef(rows, np.log10(band))[0, 1]
            assert abs(r) < R_BOUND, (seed, name, r)
