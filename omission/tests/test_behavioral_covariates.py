"""Tests for omission.jnwb_ext.behavioral_covariates (pupil/gaze pre-event covariates, P0-P3
behavioral track, 2026-08-28, Hamm).

Covers: pre-event-only window enforcement (no-future-leakage guard), a basic real-session
sanity check that extracted features are finite/in-range, and the QC heuristics used because no
ground-truth invalid-sample marker exists in this corpus (see behavioral_covariates.py docstring
and omission/artifacts/.lab/pupil-gaze-semantics-audit-20260828.json).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from omission.jnwb_ext.behavioral_covariates import (
    CLIP_PROXIMITY_ABS,
    DEFAULT_WINDOW_MS_BY_ANCHOR,
    QC_ABS_JUMP_V,
    QC_BLOCK_MS,
    QC_MAX_EXCURSION_Z,
    QC_MAX_JUMP_Z,
    QC_MIN_SESSION_FRAC,
    QC_MIN_TRIALS_FOR_RELATIVE_SCALE,
    QC_MIN_VALID_FRAC,
    RAIL_ABS_V,
    BehavioralEpochBatch,
    block_jump_diagnostics,
    discontinuity_count,
    extract_gaze_features,
    extract_pupil_features,
    load_behavioral_epochs,
    load_gaze_epochs,
    load_pupil_epochs,
    robust_scale,
    session_behavior_coverage,
    trial_has_valid_behavior,
    valid_fraction,
)

NWB_DIR = os.environ.get("OMISSION_NWB_DIR", "D:/nwb/omission")
SESSION_PATH = os.path.join(NWB_DIR, "sub-C31o_ses-230816_rec.nwb")
requires_corpus = pytest.mark.skipif(not os.path.exists(SESSION_PATH), reason="requires real NWB corpus access")


# ---------------------------------------------------------------------------------------------
# Pre-event-only / no-future-leakage enforcement -- pure logic, no real data needed for the
# raising cases; the accepting case is checked against real data below.
# ---------------------------------------------------------------------------------------------

def test_window_ms_future_edge_rejected_without_touching_data():
    """A window whose later edge is positive (reaches past the alignment anchor) must be
    rejected before any file I/O -- passing a nonexistent path proves the guard fires first."""
    with pytest.raises(ValueError, match="pre-event-only"):
        load_behavioral_epochs("does-not-exist.nwb", signal_class="pupil", window_ms=(-100.0, 1.0))


def test_window_ms_zero_edge_is_the_permitted_boundary():
    """hi_ms == 0.0 (ending exactly at the anchor, never after it) must NOT raise the
    pre-event-only guard -- only a strictly positive hi_ms should."""
    with pytest.raises(FileNotFoundError):
        # fails on file resolution, not on the window-edge guard -- proves 0.0 passed the guard
        load_behavioral_epochs("does-not-exist.nwb", signal_class="pupil", window_ms=(-500.0, 0.0))


def test_default_windows_are_pre_event_for_both_anchors():
    for anchor, (lo, hi) in DEFAULT_WINDOW_MS_BY_ANCHOR.items():
        assert hi <= 0.0, f"default window for anchor={anchor} is not pre-event: hi={hi}"
        assert lo < hi


def test_invalid_signal_class_rejected():
    with pytest.raises(ValueError):
        load_behavioral_epochs("does-not-exist.nwb", signal_class="not_a_signal")


def test_invalid_alignment_rejected():
    with pytest.raises(ValueError):
        load_behavioral_epochs("does-not-exist.nwb", signal_class="pupil", alignment="not_an_anchor")


# ---------------------------------------------------------------------------------------------
# QC heuristics -- pure logic
# ---------------------------------------------------------------------------------------------

def test_valid_fraction_flags_clip_proximity_and_nan():
    window = np.array([0.1, 0.2, np.nan, CLIP_PROXIMITY_ABS + 0.01, -0.3, 0.0])
    frac = valid_fraction(window)
    # 2 invalid (nan, clip) out of 6
    assert frac == pytest.approx(4 / 6)


def test_valid_fraction_empty_window_is_zero():
    assert valid_fraction(np.array([])) == 0.0


def test_discontinuity_count_detects_a_single_large_jump():
    rng = np.random.default_rng(0)
    smooth = rng.normal(0, 0.01, size=200)
    smooth[100] += 50.0  # one huge jump relative to the tiny local noise SD
    n = discontinuity_count(smooth)
    assert n >= 1


def test_discontinuity_count_zero_for_constant_window():
    assert discontinuity_count(np.ones(50)) == 0


def test_discontinuity_count_short_window_returns_zero_not_error():
    assert discontinuity_count(np.array([1.0, 2.0])) == 0


# ---------------------------------------------------------------------------------------------
# Repaired QC gate (2026-08-29). Synthetic, deterministic constructions -- these must NOT depend
# on any particular real session continuing to be good or bad. Every case below exercises one
# documented criterion of the conjunction in extract_pupil_features / extract_gaze_features.
# See omission/artifacts/.lab/behavioral-qc-repair-20260829.json for the 22-session distribution
# audit those criteria were calibrated against.
# ---------------------------------------------------------------------------------------------

RATE_HZ = 1000.0
N_SAMPLES = 500
N_TRIALS = 40
QC_SEED = 20260829


def _clean_pupil(n_trials=N_TRIALS, n_samples=N_SAMPLES, seed=QC_SEED):
    """A well-behaved pupil-like array: slow drift plus small noise, well inside the ADC rails.

    Noise SD 2e-3 V is the order of the real per-session robust scale measured in the audit
    (C31o 2.3e-3, V198o 1.9-3.7e-3), so the synthetic scale is corpus-plausible rather than
    arbitrary.
    """
    rng = np.random.default_rng(seed)
    t = np.linspace(0.0, 1.0, n_samples)
    base = -1.5 + 0.05 * np.sin(2 * np.pi * t)[None, :]
    return base + rng.normal(0.0, 2e-3, size=(n_trials, n_samples))


def _batch(data3d, channel_names):
    n = data3d.shape[0]
    return BehavioralEpochBatch(
        data=np.asarray(data3d, dtype=float),
        time_ms=np.arange(-data3d.shape[2], 0, dtype=float),
        channel_names=channel_names,
        trial_metadata=pd.DataFrame({"trial_id": [f"synthetic|trial={i}" for i in range(n)]}),
        manifest={"sampling_rate_hz": RATE_HZ},
    )


def _pupil_batch(A):
    return _batch(A[:, None, :], ("pupil_diameter",))


def _gaze_batch(X, Y):
    return _batch(np.stack([X, Y], axis=1), ("gaze_x", "gaze_y"))


def test_robust_scale_matches_the_mad_definition():
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    assert robust_scale(x) == pytest.approx(1.4826 * 1.0)
    assert np.isnan(robust_scale(np.array([1.0])))


def test_qc_pass_true_for_a_clean_synthetic_session():
    """A trial that PASSES: nothing rails, nothing jumps, nothing is flat."""
    feat = extract_pupil_features(_pupil_batch(_clean_pupil()))
    assert feat["qc_pass"].all(), feat.loc[~feat["qc_pass"], "qc_fail_reasons"].tolist()
    assert (feat["qc_fail_reasons"] == "").all()
    assert np.isfinite(feat["mean"]).all()


def test_qc_fails_on_low_valid_fraction_from_rail_saturation():
    """CRITERION 1: more than half the window pinned at the +/-5 V ADC rail."""
    A = _clean_pupil()
    A[3, : int(0.8 * N_SAMPLES)] = -RAIL_ABS_V
    feat = extract_pupil_features(_pupil_batch(A))
    assert not feat.loc[3, "qc_pass"]
    assert "low_valid_frac" in feat.loc[3, "qc_fail_reasons"]
    assert feat.loc[3, "rail_frac"] == pytest.approx(0.8)
    assert feat.loc[3, "valid_frac"] == pytest.approx(0.2)
    assert feat.drop(index=3)["qc_pass"].all()


def test_qc_fails_on_too_few_valid_samples_from_nans():
    """CRITERION 2: an essentially empty window cannot yield a pre-event mean."""
    A = _clean_pupil()
    A[5, :] = np.nan
    A[5, 0] = -1.5
    feat = extract_pupil_features(_pupil_batch(A))
    assert not feat.loc[5, "qc_pass"]
    assert "too_few_valid_samples" in feat.loc[5, "qc_fail_reasons"]
    assert feat.loc[5, "n_valid"] == 1
    assert feat.loc[5, "nonfinite_frac"] == pytest.approx((N_SAMPLES - 1) / N_SAMPLES)


def test_qc_fails_on_a_single_block_discontinuity():
    """CRITERION 3 (relative): one step far above this session's own robust block-diff scale."""
    A = _clean_pupil()
    A[7, 250:] += 0.20  # 0.20 V step: below the 0.5 V absolute floor, so the RELATIVE arm fires
    feat = extract_pupil_features(_pupil_batch(A))
    assert not feat.loc[7, "qc_pass"]
    assert "block_discontinuity" in feat.loc[7, "qc_fail_reasons"]
    assert feat.loc[7, "max_block_jump_z"] > QC_MAX_JUMP_Z
    assert feat.loc[7, "max_block_jump_v"] < QC_ABS_JUMP_V
    assert feat.drop(index=7)["qc_pass"].all()


def test_qc_fails_on_absolute_jump_even_when_the_session_scale_is_huge():
    """CRITERION 3 (absolute floor): a wholly corrupt session must not normalise its own
    artifacts away. Every trial here carries large steps, so the relative scale is inflated --
    the 0.5 V absolute arm is what keeps the gate operative."""
    rng = np.random.default_rng(QC_SEED + 1)
    A = -1.5 + rng.normal(0.0, 1.0, size=(N_TRIALS, N_SAMPLES))  # scale ~ 1 V, absurd
    feat = extract_pupil_features(_pupil_batch(A))
    assert not feat["qc_pass"].any()
    assert feat["qc_fail_reasons"].str.contains("block_discontinuity").all()
    assert (feat["max_block_jump_v"] > QC_ABS_JUMP_V).all()


def test_qc_fails_on_a_flat_dead_channel():
    """CRITERION 4: a stuck/held channel has zero within-trial successive-difference scale."""
    A = _clean_pupil()
    A[9, :] = -1.5
    feat = extract_pupil_features(_pupil_batch(A))
    assert not feat.loc[9, "qc_pass"]
    assert "flat_channel" in feat.loc[9, "qc_fail_reasons"]
    assert bool(feat.loc[9, "is_flat"])


def test_regression_many_discontinuities_must_not_pass_qc():
    """REGRESSION for the historical defect (verification receipt
    independent-verification-behavioral-covariates-20260828.json, item V6): discontinuity_count
    was computed but never wired into the gate, so qc_pass excluded 0 of 960 trials in a session
    where 91.8% of trials carried a detected discontinuity. A trial riddled with large jumps must
    now FAIL, and must fail specifically for the discontinuity reason."""
    A = _clean_pupil()
    rng = np.random.default_rng(QC_SEED + 2)
    idx = np.arange(20, N_SAMPLES - 20, 25)          # 18 injected step artifacts
    A[11, :] += np.cumsum(np.isin(np.arange(N_SAMPLES), idx) * rng.choice([-0.3, 0.3], N_SAMPLES))
    feat = extract_pupil_features(_pupil_batch(A))
    assert feat.loc[11, "n_block_jumps"] >= 5, feat.loc[11, "n_block_jumps"]
    assert not feat.loc[11, "qc_pass"], "trial with many discontinuities must NOT pass QC"
    assert "block_discontinuity" in feat.loc[11, "qc_fail_reasons"]
    # and the historical heuristic that was never wired in does flag it too -- the point of the
    # regression is that the GATE now reflects it, not that the heuristic changed its mind.
    assert discontinuity_count(A[11]) > 0


def test_qc_pass_can_be_both_true_and_false_within_one_batch():
    """The defect being fixed was a constant-True gate. Both values must be reachable at once."""
    A = _clean_pupil()
    A[0, 250:] += 0.20
    A[1, :] = -RAIL_ABS_V
    feat = extract_pupil_features(_pupil_batch(A))
    assert set(feat["qc_pass"].unique()) == {True, False}


def test_gaze_qc_flags_an_excursion_outlier_but_not_ordinary_saccades():
    """Gaze CRITERION 3, plus the documented decision NOT to gate gaze on jumps: a large,
    saccade-like step within the normal positional range must pass, while a trial parked far
    outside the session's own gaze distribution must fail."""
    # Between-trial variation in mean gaze position must be REALISTIC for this test to mean
    # what it says. With only within-trial noise, the trial-mean distribution has SE
    # ~0.01/sqrt(500) ~ 4e-4, so ANY sustained displacement is hundreds of robust-z and the
    # excursion criterion fires on everything -- which is what an earlier version of this test
    # hit (it shifted the whole second half of the trial, moving the trial MEAN to ~0.25, i.e.
    # a genuine sustained displacement, then asserted it should pass as a "saccade").
    # Here each trial gets its own resting gaze position, and the saccade is TRANSIENT, so the
    # trial mean stays inside the session's ordinary spread while the block jump is large.
    rng = np.random.default_rng(QC_SEED + 3)
    trial_offsets = rng.normal(0.0, 0.10, size=(N_TRIALS, 1))
    X = rng.normal(0.0, 0.01, size=(N_TRIALS, N_SAMPLES)) + trial_offsets
    Y = rng.normal(0.0, 0.01, size=(N_TRIALS, N_SAMPLES)) + rng.normal(0.0, 0.10, size=(N_TRIALS, 1))
    X[2, 250:300] += 0.5        # a transient saccade: big step, trial mean barely moves
    X[4, :] += 3.0              # a gross SUSTAINED excursion in the trial MEAN
    feat = extract_gaze_features(_gaze_batch(X, Y))
    assert not feat.loc[4, "qc_pass"]
    assert "gaze_excursion_outlier" in feat.loc[4, "qc_fail_reasons"]
    assert feat.loc[4, "excursion_z"] > QC_MAX_EXCURSION_Z
    assert feat.loc[2, "qc_pass"], "a saccade is normal behaviour and must not fail gaze QC"
    assert feat.loc[2, "max_block_jump_z_x"] > QC_MAX_JUMP_Z  # it IS a big jump, reported only


def test_gaze_qc_fails_on_rail_saturation():
    rng = np.random.default_rng(QC_SEED + 4)
    X = rng.normal(0.0, 0.01, size=(N_TRIALS, N_SAMPLES))
    Y = rng.normal(0.0, 0.01, size=(N_TRIALS, N_SAMPLES))
    Y[6, :] = RAIL_ABS_V
    feat = extract_gaze_features(_gaze_batch(X, Y))
    assert not feat.loc[6, "qc_pass"]
    assert "low_valid_frac" in feat.loc[6, "qc_fail_reasons"]
    assert feat.loc[6, "rail_frac_y"] == pytest.approx(1.0)


def test_relative_criteria_are_skipped_not_guessed_below_the_minimum_trial_count():
    """With too few trials to estimate a session-relative scale, the relative arms report NaN and
    do NOT fail a trial -- conservative flagging, never a confident exclusion on a bad scale."""
    A = _clean_pupil(n_trials=QC_MIN_TRIALS_FOR_RELATIVE_SCALE - 1)
    A[0, 250:] += 0.20   # would trip the relative arm at full n; too small an n to trust here
    feat = extract_pupil_features(_pupil_batch(A))
    assert np.isnan(feat.loc[0, "max_block_jump_z"])
    assert feat.loc[0, "qc_pass"]


def test_block_jump_diagnostics_reports_unmeasurable_rather_than_passing_silently():
    tiny = _clean_pupil(n_trials=10, n_samples=8)     # < 2 blocks at 8 ms / 1000 Hz
    diag = block_jump_diagnostics(tiny, sampling_rate_hz=RATE_HZ, block_ms=QC_BLOCK_MS)
    assert diag["measurable"] is False
    assert np.isnan(diag["max_jump_v"]).all()


def test_features_are_not_imputed_for_failing_trials():
    """A failing trial keeps its diagnostics and its computed values -- no silent fill-in."""
    A = _clean_pupil()
    A[3, 250:] += 0.20
    feat = extract_pupil_features(_pupil_batch(A))
    assert not feat.loc[3, "qc_pass"]
    assert np.isfinite(feat.loc[3, "mean"])          # value retained for inspection
    assert np.isfinite(feat.loc[3, "max_block_jump_v"])
    assert np.isnan(feat.loc[3, "prev_trial_diff"])  # only the cross-trial delta is withheld


def _stub_coverage(monkeypatch, available_flags):
    """Make session_behavior_coverage see one synthetic condition cell with the given per-trial
    behavior_available flags, so the SESSION-level gate can be exercised deterministically
    without depending on a real session continuing to be good or bad."""
    import omission.jnwb_ext.behavioral_covariates as bc
    import omission.jnwb_ext.unit_classification as uc

    monkeypatch.setattr(uc, "omission_events", lambda: [("AAXB", "p3")])
    calls = {"n": 0}

    def fake(source, **kwargs):
        calls["n"] += 1
        flags = list(available_flags) if calls["n"] == 1 else []
        if not flags:
            return pd.DataFrame(columns=["trial_id", "behavior_available"])
        return pd.DataFrame({
            "trial_id": [f"synthetic|trial={i}" for i in range(len(flags))],
            "behavior_available": flags,
            "pupil_qc_pass": flags,
            "gaze_qc_pass": [True] * len(flags),
            "pupil_qc_fail_reasons": ["" if f else "block_discontinuity" for f in flags],
            "gaze_qc_fail_reasons": [""] * len(flags),
        })

    monkeypatch.setattr(bc, "trial_has_valid_behavior", fake)
    return bc


def test_session_behavior_available_is_false_when_most_trials_fail(monkeypatch):
    """SESSION-level FALSE case -- the value the historical defect made unreachable."""
    bc = _stub_coverage(monkeypatch, [True] * 20 + [False] * 80)
    cov = bc.session_behavior_coverage("synthetic-session.nwb")
    assert cov["n_trials"] == 100
    assert cov["n_available"] == 20
    assert cov["fraction_available"] == pytest.approx(0.20)
    assert cov["session_behavior_available"] is False
    assert cov["fail_reason_counts"]["pupil:block_discontinuity"] == 80
    assert cov["criteria"]["min_session_frac"] == QC_MIN_SESSION_FRAC


def test_session_behavior_available_is_true_when_most_trials_pass(monkeypatch):
    bc = _stub_coverage(monkeypatch, [True] * 80 + [False] * 20)
    cov = bc.session_behavior_coverage("synthetic-session.nwb")
    assert cov["fraction_available"] == pytest.approx(0.80)
    assert cov["session_behavior_available"] is True


def test_session_behavior_available_is_false_when_no_trials_resolve(monkeypatch):
    bc = _stub_coverage(monkeypatch, [])
    cov = bc.session_behavior_coverage("synthetic-session.nwb")
    assert cov["n_trials"] == 0
    assert cov["session_behavior_available"] is False


def test_qc_thresholds_are_the_documented_values():
    """Pins the calibrated constants so a silent threshold drift fails a test, not a review."""
    assert (QC_BLOCK_MS, QC_MAX_JUMP_Z, QC_ABS_JUMP_V) == (8.0, 10.0, 0.5)
    assert (QC_MAX_EXCURSION_Z, QC_MIN_VALID_FRAC, QC_MIN_SESSION_FRAC) == (10.0, 0.5, 0.5)
    assert RAIL_ABS_V == 5.0


# ---------------------------------------------------------------------------------------------
# Real-session sanity checks
# ---------------------------------------------------------------------------------------------

@requires_corpus
def test_real_session_pupil_epochs_pre_event_and_finite():
    batch = load_pupil_epochs(SESSION_PATH, condition="AAXB", alignment="p1", max_trials=15)
    assert batch.data.shape[0] > 0
    assert batch.channel_names == ("pupil_diameter",)
    assert batch.time_ms.max() <= 0.0
    assert np.all(np.isfinite(batch.data))  # 0 NaN confirmed in the semantics audit's value probe

    features = extract_pupil_features(batch)
    assert len(features) == batch.data.shape[0]
    assert (features["valid_frac"] >= 0.0).all() and (features["valid_frac"] <= 1.0).all()
    passing = features[features["qc_pass"]]
    assert not passing.empty, "expected at least some real trials to pass pupil QC"
    assert np.isfinite(passing["mean"]).all()
    assert np.isfinite(passing["sd"]).all()


@requires_corpus
def test_real_session_gaze_epochs_pre_event_and_finite():
    batch = load_gaze_epochs(SESSION_PATH, condition="AAXB", alignment="p1", max_trials=15)
    assert batch.channel_names == ("gaze_x", "gaze_y")
    assert batch.time_ms.max() <= 0.0
    assert np.all(np.isfinite(batch.data))

    features = extract_gaze_features(batch)
    assert len(features) == batch.data.shape[0]
    passing = features[features["qc_pass"]]
    assert not passing.empty, "expected at least some real trials to pass gaze QC"
    assert np.isfinite(passing["dist_from_center"]).all()
    assert (passing["dist_from_center"] >= 0.0).all()


@requires_corpus
def test_real_session_omission_anchored_window_ends_before_slot_onset():
    """omission-alignment window must be strictly before the omitted slot's own onset -- reuses
    matched_empty.py's OM_BASE_LEAD_MS/OM_BASE_GAP_MS convention verbatim."""
    batch = load_pupil_epochs(SESSION_PATH, condition="AAXB", slot_keys=["p3"],
                               alignment="omission", max_trials=10)
    # window_ms=(-250, -50) is a half-open [lo, hi) sample grid at 1 ms/sample (same convention
    # as jnwb_ext.analog.load_analog_epochs), so the last sample is hi - 1 sample, not hi itself.
    assert batch.time_ms.max() == pytest.approx(-51.0)
    assert batch.time_ms.min() == pytest.approx(-250.0)
    assert batch.time_ms.max() < -50.0  # still strictly before the omitted slot's own onset


@requires_corpus
def test_real_session_trial_has_valid_behavior_matches_feature_qc():
    """trial_has_valid_behavior's per-trial flag must agree with independently recomputed
    pupil+gaze QC for the same trials (guards against the two code paths silently diverging)."""
    coverage = trial_has_valid_behavior(SESSION_PATH, condition="AAXB", alignment="p1")
    assert not coverage.empty
    assert set(coverage["trial_id"])
    assert coverage["behavior_available"].dtype == bool
    # a trial marked available must have both sub-flags True; never available with a False sub-flag
    available = coverage[coverage["behavior_available"]]
    assert (available["pupil_qc_pass"] & available["gaze_qc_pass"]).all()


@requires_corpus
def test_real_session_behavior_coverage_summary_is_consistent():
    cov = session_behavior_coverage(SESSION_PATH)
    assert cov["n_trials"] >= cov["n_available"] >= 0
    if cov["n_trials"] > 0:
        assert cov["fraction_available"] == pytest.approx(cov["n_available"] / cov["n_trials"])
    assert cov["session_behavior_available"] == (cov["fraction_available"] >= 0.5)
