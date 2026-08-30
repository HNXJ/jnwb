"""Adversarial benchmark for candidate common-driver-resistant controls (Hamm, 2026-08-28).

Each candidate method (omission.jnwb_ext.common_driver_control) is tested against BOTH:
  - negative control: shared per-trial jitter E_i -> {P,R}, ZERO true P->R coupling. A valid
    method must NOT flag this as significant.
  - positive control: same shared jitter confound PLUS a genuine P->R coupling term at a known
    lag. A valid method must flag this as significant AND recover a lag near the injected value.

A method that fails the negative control is unusable regardless of positive-control performance
(exactly the failure mode found for uncorrected trial-shuffle). A method that passes the negative
control but fails the positive control has traded false positives for false negatives (e.g. by
over-aggressively removing real signal) and is equally unusable.
"""
from __future__ import annotations

import numpy as np
import pytest

from omission.jnwb_ext.common_driver_control import (
    event_template_residualize,
    matched_filter_peak_realign,
    reference_peak_realign,
    synthesize_adversarial_pair,
    trial_shuffle_pvalue,
)

NEG_SEEDS = [1, 2, 3, 4, 5]
POS_SEEDS = [11, 12, 13, 14, 15]
COUPLING_LAG_MS = 30.0
COUPLING_STRENGTH = 1.2


def _raw_benchmark(seeds, coupling_strength):
    results = []
    for seed in seeds:
        P, R, _ = synthesize_adversarial_pair(jitter_sd_ms=8.0, coupling_strength=coupling_strength,
                                               coupling_lag_ms=COUPLING_LAG_MS, seed=seed)
        res = trial_shuffle_pvalue(P, R, seed=seed * 1000)
        results.append(res)
    return results


def _templateresid_benchmark(seeds, coupling_strength):
    results = []
    for seed in seeds:
        P, R, _ = synthesize_adversarial_pair(jitter_sd_ms=8.0, coupling_strength=coupling_strength,
                                               coupling_lag_ms=COUPLING_LAG_MS, seed=seed)
        Pr, Rr = event_template_residualize(P, R, n_folds=5, seed=seed)
        res = trial_shuffle_pvalue(Pr, Rr, seed=seed * 1000)
        results.append(res)
    return results


def _realign_benchmark(seeds, coupling_strength):
    results = []
    for seed in seeds:
        P, R, _ = synthesize_adversarial_pair(jitter_sd_ms=8.0, coupling_strength=coupling_strength,
                                               coupling_lag_ms=COUPLING_LAG_MS, seed=seed)
        Pa, Ra, _ = reference_peak_realign(P, R)
        res = trial_shuffle_pvalue(Pa, Ra, seed=seed * 1000)
        results.append(res)
    return results


def test_baseline_raw_trial_shuffle_confirms_prior_failure_and_positive_recovery():
    """Reproduces the prior finding as this benchmark's own baseline: raw (uncorrected)
    trial-shuffle should fail the negative control and (for reference) succeed on the positive
    control, so the improvement (or lack of it) of each candidate below is measured against a
    known baseline within this same benchmark run."""
    neg = _raw_benchmark(NEG_SEEDS, coupling_strength=0.0)
    pos = _raw_benchmark(POS_SEEDS, coupling_strength=COUPLING_STRENGTH)
    neg_fp_rate = np.mean([r["p"] < 0.05 for r in neg])
    pos_tp_rate = np.mean([r["p"] < 0.05 for r in pos])
    print(f"\n[raw] neg FP rate={neg_fp_rate:.2f} pos TP rate={pos_tp_rate:.2f}")
    print(f"[raw] neg p-values: {[round(r['p'], 4) for r in neg]}")
    print(f"[raw] pos p-values: {[round(r['p'], 4) for r in pos]}, lags: {[r['observed_lag_ms'] for r in pos]}")
    assert neg_fp_rate >= 0.6, "expected the prior 100%-false-positive-rate failure to reproduce here"


def test_candidate_A_event_template_residualization():
    neg = _templateresid_benchmark(NEG_SEEDS, coupling_strength=0.0)
    pos = _templateresid_benchmark(POS_SEEDS, coupling_strength=COUPLING_STRENGTH)
    neg_fp_rate = np.mean([r["p"] < 0.05 for r in neg])
    pos_tp_rate = np.mean([r["p"] < 0.05 for r in pos])
    print(f"\n[template-residualize] neg FP rate={neg_fp_rate:.2f} pos TP rate={pos_tp_rate:.2f}")
    print(f"[template-residualize] neg p-values: {[round(r['p'], 4) for r in neg]}")
    print(f"[template-residualize] pos p-values: {[round(r['p'], 4) for r in pos]}, "
          f"lags: {[r['observed_lag_ms'] for r in pos]}")
    # Recorded, not asserted a priori as a pass -- this test's job is to make Candidate A's
    # actual behavior against the exact confound that defeated the raw null a receipted fact.


def test_candidate_B_reference_peak_realignment():
    neg = _realign_benchmark(NEG_SEEDS, coupling_strength=0.0)
    pos = _realign_benchmark(POS_SEEDS, coupling_strength=COUPLING_STRENGTH)
    neg_fp_rate = np.mean([r["p"] < 0.05 for r in neg])
    pos_tp_rate = np.mean([r["p"] < 0.05 for r in pos])
    print(f"\n[peak-realign] neg FP rate={neg_fp_rate:.2f} pos TP rate={pos_tp_rate:.2f}")
    print(f"[peak-realign] neg p-values: {[round(r['p'], 4) for r in neg]}")
    print(f"[peak-realign] pos p-values: {[round(r['p'], 4) for r in pos]}, "
          f"lags: {[r['observed_lag_ms'] for r in pos]}")


def _matchedfilter_realign_benchmark(seeds, coupling_strength):
    results = []
    for seed in seeds:
        P, R, _ = synthesize_adversarial_pair(jitter_sd_ms=8.0, coupling_strength=coupling_strength,
                                               coupling_lag_ms=COUPLING_LAG_MS, seed=seed)
        Pa, Ra, _ = matched_filter_peak_realign(P, R, seed=seed)
        res = trial_shuffle_pvalue(Pa, Ra, seed=seed * 1000)
        results.append(res)
    return results


def test_candidate_B2_matched_filter_peak_realignment():
    """Refined Candidate B: same realignment logic, but the per-trial timing estimate uses a
    cross-validated matched-filter (cross-correlation against a group template) instead of raw
    argmax, after diagnosing that raw argmax's own estimation error (SD~13ms) exceeded the true
    jitter (SD=8ms) it needed to remove."""
    neg = _matchedfilter_realign_benchmark(NEG_SEEDS, coupling_strength=0.0)
    pos = _matchedfilter_realign_benchmark(POS_SEEDS, coupling_strength=COUPLING_STRENGTH)
    neg_fp_rate = np.mean([r["p"] < 0.05 for r in neg])
    pos_tp_rate = np.mean([r["p"] < 0.05 for r in pos])
    print(f"\n[matched-filter-realign] neg FP rate={neg_fp_rate:.2f} pos TP rate={pos_tp_rate:.2f}")
    print(f"[matched-filter-realign] neg p-values: {[round(r['p'], 4) for r in neg]}")
    print(f"[matched-filter-realign] pos p-values: {[round(r['p'], 4) for r in pos]}, "
          f"lags: {[r['observed_lag_ms'] for r in pos]}")
