"""Unit tests for the S1 likelihood-of-firing unit-inclusion criterion (jnwb.unit_inclusion)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from jnwb.unit_classification import GLO_CONDITIONS, OM_BASE_GAP_MS, SLOT_WINDOW_MS
from jnwb.unit_inclusion import (
    InclusionConfig,
    assign_omission_inclusion_labels,
    assign_quality_tier,
    classify_unit_omission_inclusion,
    compare_old_new_criteria,
    fire_indicator,
    fires_in_window,
    local_pre_omission_window,
    old_new_summary_table,
    paired_fire_prob_test,
)

# The old template-correlation classifier's O+ epoch template and epoch bounds, replicated
# from scripts/archive_oneoff/find_all_s_and_o_units.py (EPOCH_BOUNDS, TEMPLATES["O+"]) --
# not imported, since that script is an executable pipeline (readiness CSV, NWB I/O), not an
# importable library; the constants are small and stable (Conservation: that file is untouched).
_OLD_EPOCH_BOUNDS_MS = [
    (-500.0, 0.0), (0.0, 531.0), (531.0, 1031.0), (1031.0, 1562.0),
    (1562.0, 2062.0), (2062.0, 2593.0), (2593.0, 3093.0), (3093.0, 3624.0), (3624.0, 4124.0),
]
_OLD_O_PLUS_TEMPLATE_P2 = np.array([0, 0, 0, 1, 0, 0, 0, 0, 0], dtype=float)  # RXRR (omission at p2)


def _rate_in_epoch(spike_times: np.ndarray, onset_s: float, bounds_ms) -> float:
    t0 = onset_s + bounds_ms[0] / 1000.0
    t1 = onset_s + bounds_ms[1] / 1000.0
    n = int(np.searchsorted(spike_times, t1, side="right") - np.searchsorted(spike_times, t0, side="left"))
    return n / ((bounds_ms[1] - bounds_ms[0]) / 1000.0)


def test_ground_truth_high_fx_and_omission_unit_retained_by_new_rejected_by_old():
    """Spec's own required ground-truth case: a unit that fires strongly during fixation AND
    during omission must be retained by the new likelihood criterion and rejected by the old
    template-correlation criterion.

    New criterion (Hamm, 2026-08-17): accept if the unit fires more during omission than during
    the immediately pre-omission window -- fixation is simply not part of that comparison at
    any amplitude, so this unit is retained regardless of how much it fires at fx.

    Old criterion: numerically explored before writing this test (Pearson r of a 9-epoch rate
    vector against the O+ one-hot template) -- a unit firing EQUALLY at fx and the omission slot
    (everything else at zero) still gets r~0.66, comfortably above the old classifier's r>0.3
    threshold, because 7 of 9 epochs still agree (both near zero) and the shared omission-slot
    peak dominates. The old classifier only actually rejects the unit once fixation firing
    clearly DOMINATES the omission response (r crosses below 0.3 once fx rate exceeds ~2.5x the
    omission-slot rate, at zero background elsewhere) -- this is the honest boundary of the old
    bug, not "any co-firing", and this test uses a 3x-dominant fixation response to trigger the
    old rejection unambiguously rather than asserting a milder case that the old code would not
    actually fail.
    """
    rng = np.random.default_rng(7)
    n_trials = 60
    # RXRR: omission at p2. One trial onset every 6s of "session" time.
    onset_times = np.arange(n_trials) * 6.0
    spikes = []
    for onset in onset_times:
        # fx window [-500,0)ms: strongly dominant firing (3x the omission-slot count)
        spikes.extend(onset + rng.uniform(-0.5, 0.0, size=15))
        # p2 (omission) window [1031,1562)ms: still clearly firing, but less than fx
        spikes.extend(onset + 1.031 + rng.uniform(0.0, 0.531, size=5))
        # everywhere else: silent, so the old classifier's rejection is attributable to the
        # fx/omission relationship being tested, not to unrelated noise
    spike_times = np.sort(np.asarray(spikes, dtype=float))

    onsets = {c: np.array([], dtype=float) for c in GLO_CONDITIONS}
    onsets["RXRR"] = onset_times

    cfg = InclusionConfig(n_shuffles=500, n_bootstrap=500, seed=11)
    rng_test = np.random.default_rng(cfg.seed)
    result = classify_unit_omission_inclusion(spike_times, onsets, cfg, rng_test)

    assert result["n_omission_trials"] == n_trials
    assert result["p_fire_target"] > 0.9  # fires almost every omission trial
    assert result["p_fire_pre_omission_baseline"] < 0.1  # silent in the pre-omission window
    assert result["risk_difference"] > 0.7  # clearly more likely than the pre-omission baseline
    assert result["p_value_fire_shuffle"] < 0.01

    labeled = assign_omission_inclusion_labels(pd.DataFrame([result]), cfg)
    assert bool(labeled["is_omission_inclusion_new"].iloc[0]) is True

    # Old mechanism: build the 9-epoch rate vector exactly as find_all_s_and_o_units.py does
    # and correlate against its O+ template for RXRR -- this is the buggy mechanism, and it
    # must reject the same unit because of the fx-epoch-0 mismatch.
    rates = np.zeros(len(_OLD_EPOCH_BOUNDS_MS))
    # Average per-trial rate vector across trials (matches the old script's per-unit vector).
    per_trial = np.zeros((n_trials, len(_OLD_EPOCH_BOUNDS_MS)))
    for ti, onset in enumerate(onset_times):
        for ei, bounds in enumerate(_OLD_EPOCH_BOUNDS_MS):
            per_trial[ti, ei] = _rate_in_epoch(spike_times, float(onset), bounds)
    rates = per_trial.mean(axis=0)
    r_oplus = float(np.corrcoef(rates, _OLD_O_PLUS_TEMPLATE_P2)[0, 1])
    assert r_oplus <= 0.3, (
        "old template-correlation mechanism should NOT retain this unit "
        f"(got r={r_oplus:.3f}, its own threshold requires r>0.3)"
    )


def test_fires_in_window_and_fire_indicator_edge_cases():
    spikes = np.array([0.1, 0.2, 0.5, 1.0])
    assert fires_in_window(spikes, 0.0, (50.0, 300.0)) is True  # 0.1, 0.2 inside
    assert fires_in_window(spikes, 0.0, (600.0, 900.0)) is False  # nothing in (0.6,0.9)
    assert fires_in_window(np.array([]), 0.0, (0.0, 500.0)) is False  # empty spike train
    assert fires_in_window(spikes, 0.0, (500.0, 500.0)) is False  # zero-width window

    onsets = np.array([0.0, 10.0])
    ind = fire_indicator(spikes, onsets, (50.0, 300.0))
    assert ind.dtype == bool
    assert list(ind) == [True, False]


def test_local_pre_omission_window_duration_matched_and_no_collision():
    """The baseline window must (1) never overlap (collide) with the omission window it's
    paired against, and (2) match its duration exactly -- a shorter baseline window would
    give it a mechanically lower P(>=1 spike) purely from window length
    (P(fire)=1-exp(-rate*duration)), independent of any real omission selectivity. This was a
    real bug found and fixed 2026-08-17 (see module docstring): the first-cut 200ms baseline
    inflated the inclusion rate to 73.7% on a smoke-test session, with the length artifact
    alone correlating r=0.60 with the observed effect."""
    for slot in (2, 3, 4):
        win = SLOT_WINDOW_MS[slot]
        win_dur = win[1] - win[0]
        base = local_pre_omission_window(win)
        base_dur = base[1] - base[0]
        assert base_dur == pytest.approx(win_dur)  # duration-matched -- no length artifact
        assert base[1] == win[0] - OM_BASE_GAP_MS
        assert base[1] <= win[0]  # ends at or before the omission window starts -- no overlap


def test_paired_fire_prob_test_null_case_no_true_difference():
    rng = np.random.default_rng(42)
    n = 300
    p = 0.4
    t = rng.random(n) < p
    u = rng.random(n) < p
    result = paired_fire_prob_test(t, u, n_shuffles=1000, n_bootstrap=1000, rng=rng)
    assert result["p_value_fire_shuffle"] > 0.05
    assert abs(result["risk_difference"]) < 0.15


def test_paired_fire_prob_test_detects_strong_effect():
    rng = np.random.default_rng(5)
    n = 400
    t = rng.random(n) < 0.9
    u = rng.random(n) < 0.1
    result = paired_fire_prob_test(t, u, n_shuffles=1000, n_bootstrap=1000, rng=rng)
    assert result["risk_difference"] == pytest.approx(0.8, abs=0.1)
    assert result["p_value_fire_shuffle"] < 0.01
    assert result["risk_difference_ci_lo"] > 0.5
    assert result["odds_ratio"] > 1.0


def test_determinism_same_seed_byte_identical_different_seed_differs():
    rng = np.random.default_rng(99)
    n_trials = 60
    onset_times = np.arange(n_trials) * 6.0
    spikes = []
    for onset in onset_times:
        spikes.extend(onset + rng.uniform(-0.5, 0.0, size=6))
        # imperfect separation (not every trial fires) so the shuffle/bootstrap distributions
        # aren't degenerate at a fixed extreme -- lets a reseed actually change the outcome
        if rng.random() < 0.8:
            spikes.extend(onset + 1.031 + rng.uniform(0.0, 0.531, size=6))
    spike_times = np.sort(np.asarray(spikes, dtype=float))
    onsets = {c: np.array([], dtype=float) for c in GLO_CONDITIONS}
    onsets["RXRR"] = onset_times

    cfg = InclusionConfig(n_shuffles=300, n_bootstrap=300, seed=123)
    r1 = classify_unit_omission_inclusion(spike_times, onsets, cfg, np.random.default_rng(cfg.seed))
    r2 = classify_unit_omission_inclusion(spike_times, onsets, cfg, np.random.default_rng(cfg.seed))
    assert r1 == r2  # byte-identical dict, same seed

    r3 = classify_unit_omission_inclusion(spike_times, onsets, cfg, np.random.default_rng(cfg.seed + 1))
    assert r3["p_value_fire_shuffle"] != r1["p_value_fire_shuffle"] or r3["risk_difference_ci_lo"] != r1["risk_difference_ci_lo"]


def test_assign_quality_tier_branches():
    quality = pd.Series([0, 1, 1, 1, 1], index=[0, 1, 2, 3, 4])
    presence = pd.Series([0.99, 0.99, 0.50, np.nan, 0.99], index=[0, 1, 2, 3, 4])
    snr = pd.Series([2.0, 2.0, 2.0, 2.0, 0.1], index=[0, 1, 2, 3, 4])
    tier = assign_quality_tier(quality, presence, snr, presence_threshold=0.98, snr_threshold=0.5)
    assert tier[0] == "mua"
    assert tier[1] == "stable"
    assert tier[2] == "unstable"  # low presence
    assert tier[3] == "unstable"  # missing presence row -> fail-safe, not stable
    assert tier[4] == "unstable"  # good presence but low snr


def test_compare_old_new_criteria_gained_lost_unchanged():
    new_df = pd.DataFrame(
        {
            "session": ["s1", "s1", "s1", "s1"],
            "unit_row": [0, 1, 2, 3],
            "area": ["FEF", "FEF", "V1", "V1"],
            "quality_tier": ["stable"] * 4,
            "is_omission_inclusion_new": [True, False, True, True],
        }
    )
    old_df = pd.DataFrame(
        {
            "session_prefix": ["s1", "s1", "s1"],  # unit_row 3 never screened by old pipeline
            "unit_row_idx": [0, 1, 2],
            "is_Oplus": [False, False, True],
        }
    )
    compared = compare_old_new_criteria(new_df, old_df)
    tmap = dict(zip(compared["unit_row"], compared["transition"]))
    assert tmap[0] == "gained"              # new True, old False
    assert tmap[1] == "unchanged_excluded"  # new False, old False
    assert tmap[2] == "unchanged_included"  # new True, old True
    assert tmap[3] == "gained"              # new True, old unscreened -> gained per spec
    assert bool(compared.set_index("unit_row").loc[3, "old_screened"]) is False

    summary = old_new_summary_table(compared, group_cols=("area", "quality_tier"))
    assert summary["n_units"].sum() == 4
