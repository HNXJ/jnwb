# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Zhat-3 synthetic behavioral bridge (2026-08-28, Hamm). Tests whether a behavioral proxy B
(gain -> B, alongside the existing gain -> {P,R}) can materially repair the catastrophic
gain-confound FPR failure found for Zhat-0/1/2 (amplitude-only gain proxy, r=+0.28 with
true_gain, FPR=1.00 at n=300). Sweeps B's fidelity (target correlation with true_gain) across a
RANGE rather than tuning to one value, producing a fidelity -> {gain-null FPR, PC2 power} curve
that a real pupil/gaze proxy's empirically-estimated reliability can later be located on -- per
Hamm's explicit instruction not to tune synthetic fidelity to make the real analysis look viable.

This is the FIRST, BINARY question per Hamm's acceptance criterion: does behavior materially
repair gain-confound FPR at ANY plausible fidelity? If not (FPR stays near 1.0 even at high
fidelity), that would point to a deeper problem than proxy noise (echoing the earlier
oracle-vs-proxy-fidelity lesson from the timing-confound diagnosis, where oracle fidelity alone
did NOT fix a functional-form problem) -- reported explicitly, not glossed over.

Run with: python -m omission.scripts.dev_zhat3_behavioral_bridge_20260828
"""
import json
from pathlib import Path

import numpy as np

from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, estimate_timing_nested, fit_nuisance_tier, simulate_behavioral_proxy,
)

N_TRIALS = 300
SEEDS = list(range(20))
RHO = 0.5
DELAY_MS = 30.0
FPR_THRESHOLD = 0.05  # delta > this counts as a "detection" on null data, matching the prior Zhat-0/1/2 benchmark's stated convention

GAIN_NULL = dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=0.0)
GAIN_PC2 = dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=1.5)

TARGET_R_SWEEP = [0.0, 0.1, 0.28, 0.4, 0.6, 0.8, 0.95]

results = {"fpr_by_fidelity": {}, "power_by_fidelity": {}, "reference": {}}

print("=== Zhat-3 (Zhat-2 + behavioral proxy B) fidelity sweep ===")
for target_r in TARGET_R_SWEEP:
    null_deltas, pos_deltas = [], []
    for seed in SEEDS:
        # null
        P, R, true_jitter, true_gain, _ = synthesize_realized_coupling_pair(
            n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
            z_seed=seed, private_seed=seed + 960000, **GAIN_NULL,
        )
        dataset = build_trial_level_dataset(P, R, seed=seed)
        timing_hat = estimate_timing_nested(P, n_splits=5, seed=seed)
        B = simulate_behavioral_proxy(true_gain, target_r=target_r, seed=seed)
        fit = fit_nuisance_tier(dataset, "Zhat-2_plus_timing_gain", timing_hat=timing_hat, extra_Z=[B], n_splits=5, seed=seed)
        null_deltas.append(fit["delta"])

        # positive control
        P2, R2, tj2, tg2, _ = synthesize_realized_coupling_pair(
            n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
            z_seed=seed, private_seed=seed + 960000, **GAIN_PC2,
        )
        dataset2 = build_trial_level_dataset(P2, R2, seed=seed)
        timing_hat2 = estimate_timing_nested(P2, n_splits=5, seed=seed)
        B2 = simulate_behavioral_proxy(tg2, target_r=target_r, seed=seed)
        fit2 = fit_nuisance_tier(dataset2, "Zhat-2_plus_timing_gain", timing_hat=timing_hat2, extra_Z=[B2], n_splits=5, seed=seed)
        pos_deltas.append(fit2["delta"])

    null_deltas = np.array(null_deltas)
    pos_deltas = np.array(pos_deltas)
    fpr = float(np.mean(null_deltas > FPR_THRESHOLD))
    power = float(np.mean(pos_deltas > np.quantile(null_deltas, 0.95)))
    results["fpr_by_fidelity"][str(target_r)] = {
        "null_delta_mean": float(null_deltas.mean()), "null_delta_sd": float(null_deltas.std(ddof=1)), "fpr": fpr,
    }
    results["power_by_fidelity"][str(target_r)] = {
        "pos_delta_mean": float(pos_deltas.mean()), "pos_delta_sd": float(pos_deltas.std(ddof=1)), "power": power,
    }
    print(f"  target_r={target_r:.2f}  null_delta={null_deltas.mean():+.4f}+-{null_deltas.std(ddof=1):.4f} "
          f"FPR={fpr:.2f}   pos_delta={pos_deltas.mean():+.4f}+-{pos_deltas.std(ddof=1):.4f} power={power:.2f}")

# reference bookends: Zhat-2 alone (no B) and oracle-gain-only (B=true_gain exactly, target_r=1 case, already covered by sweep's r=0.95 but add exact 1.0 too)
print("\n=== Reference bookends ===")
null_deltas_z2, pos_deltas_z2 = [], []
for seed in SEEDS:
    P, R, true_jitter, true_gain, _ = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
        z_seed=seed, private_seed=seed + 960000, **GAIN_NULL,
    )
    dataset = build_trial_level_dataset(P, R, seed=seed)
    timing_hat = estimate_timing_nested(P, n_splits=5, seed=seed)
    fit = fit_nuisance_tier(dataset, "Zhat-2_plus_timing_gain", timing_hat=timing_hat, n_splits=5, seed=seed)
    null_deltas_z2.append(fit["delta"])

    P2, R2, tj2, tg2, _ = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
        z_seed=seed, private_seed=seed + 960000, **GAIN_PC2,
    )
    dataset2 = build_trial_level_dataset(P2, R2, seed=seed)
    timing_hat2 = estimate_timing_nested(P2, n_splits=5, seed=seed)
    fit2 = fit_nuisance_tier(dataset2, "Zhat-2_plus_timing_gain", timing_hat=timing_hat2, n_splits=5, seed=seed)
    pos_deltas_z2.append(fit2["delta"])

null_deltas_z2, pos_deltas_z2 = np.array(null_deltas_z2), np.array(pos_deltas_z2)
fpr_z2 = float(np.mean(null_deltas_z2 > FPR_THRESHOLD))
power_z2 = float(np.mean(pos_deltas_z2 > np.quantile(null_deltas_z2, 0.95)))
results["reference"]["Zhat-2_no_behavior"] = {
    "null_delta_mean": float(null_deltas_z2.mean()), "fpr": fpr_z2,
    "pos_delta_mean": float(pos_deltas_z2.mean()), "power": power_z2,
}
print(f"  Zhat-2 (no B)   null_delta={null_deltas_z2.mean():+.4f} FPR={fpr_z2:.2f}   pos_delta={pos_deltas_z2.mean():+.4f} power={power_z2:.2f}")

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "zhat3-behavioral-bridge-fidelity-sweep-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "schema_version": 3,
    "id": "zhat3-behavioral-bridge-fidelity-sweep-20260828",
    "kind": "evidence",
    "title": "Zhat-3 (behavioral proxy B) fidelity sweep: does behavior repair gain-confound FPR?",
    "status": "provisional",
    "n_trials": N_TRIALS, "n_seeds": len(SEEDS), "rho": RHO, "delay_ms": DELAY_MS,
    "fpr_threshold": FPR_THRESHOLD, "target_r_sweep": TARGET_R_SWEEP,
    "results": results,
}, indent=2))
print(f"\nWrote {out_path}")
