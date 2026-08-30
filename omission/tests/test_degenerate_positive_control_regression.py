"""Regression test for the DELIBERATELY preserved degenerate positive control (2026-08-28).

common_driver_control.degenerate_common_cause_mediated_positive_control's coupling term is a
deterministic function of the shared timing nuisance e_i alone (never of P's realized trace), so
a sufficiently expressive nuisance-conditioning model is EXPECTED and REQUIRED to null it along
with the confound -- that is not an estimator power failure, it is the correct behavior of a
valid conditional estimator faced with an unidentifiable "coupling" term. This test pins that
expected behavior so it stays visible in the suite rather than disappearing from history now that
the (structurally valid) realized_coupling_generator has superseded it as the live positive
control -- see realized_coupling_generator.py and dev_distributed_lag_structured_timing_20260828.py
/ distributed-lag-structured-timing-20260828.json for the original finding.
"""
import numpy as np

from omission.jnwb_ext.common_driver_control import degenerate_common_cause_mediated_positive_control
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, fit_structured_timing_oracle, _poly_expand,
)

N_TRIALS = 300
SEEDS = list(range(5))
TIMING_ONLY = dict(jitter_sd_ms=8.0, amp_gain=0.0, coupling_strength=0.0)
POSITIVE = dict(jitter_sd_ms=8.0, amp_gain=0.0, coupling_strength=0.6, coupling_lag_ms=30.0)


def _quadratic_delta(params, seed):
    P, R, true_jitter, true_gain = degenerate_common_cause_mediated_positive_control(
        n_trials=N_TRIALS, seed=seed, **params
    )
    dataset = build_trial_level_dataset(P, R, seed=seed)
    fit = fit_structured_timing_oracle(dataset, _poly_expand(true_jitter, 2), seed=seed)
    return fit["delta"]


def test_quadratic_conditioning_nulls_both_confound_and_degenerate_coupling():
    """Required regression behavior: quadratic-in-jitter oracle conditioning drives BOTH the
    negative-control Delta and the degenerate positive-control Delta toward zero (D ~= 0),
    because the degenerate coupling term is unidentifiable given e_i alone. A future change that
    makes D large here would mean this generator's coupling stopped being degenerate -- which
    would itself be a finding worth surfacing, not silently absorbing."""
    null_deltas = np.array([_quadratic_delta(TIMING_ONLY, seed) for seed in SEEDS])
    coupling_deltas = np.array([_quadratic_delta(POSITIVE, seed) for seed in SEEDS])
    D = coupling_deltas.mean() - null_deltas.mean()

    assert abs(null_deltas.mean()) < 0.05, f"null Delta should be ~0 under quadratic conditioning, got {null_deltas.mean():.4f}"
    assert abs(coupling_deltas.mean()) < 0.05, (
        f"degenerate positive-control Delta should ALSO be ~0 under quadratic conditioning "
        f"(unidentifiable coupling), got {coupling_deltas.mean():.4f}"
    )
    assert abs(D) < 0.05, f"D should be ~0 for this degenerate generator, got {D:.4f}"
