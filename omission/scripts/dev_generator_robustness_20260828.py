# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""dev_generator_robustness_20260828.py -- generalization stress test for the negative-control
candidates B2 (matched_filter_peak_realign + trial_shuffle_pvalue) and C
(matched_permutation_pvalue) validated in omission/jnwb_ext/common_driver_control.py.

MOTIVATION. B2 and C were tuned/validated against ONE specific adversarial generator
(synthesize_adversarial_pair): a shared per-trial timing jitter E_i applied identically to both
P and R via symmetric Gaussian kernels. A control that only works for the exact generator used
to design it is overfit and untrustworthy on real data, which will not match any one synthetic
structure exactly. This script builds THREE structurally different negative-control (zero true
P->R coupling) generators and re-runs raw trial_shuffle_pvalue, B2, and C against each, to see
whether the near-zero false-positive property generalizes or breaks down.

This file is standalone -- it does NOT edit common_driver_control.py (other work is in flight on
that shared file). It reuses, via import, the already-validated primitives:
  - FS, LAGS_MS, trial_shuffle_pvalue, matched_filter_peak_realign, matched_permutation_pvalue,
    _gaussian_kernel from omission.jnwb_ext.common_driver_control
All three new generators below are local to this file, and are all constructed with EXACTLY ZERO
true P->R (or R->P) information transfer -- only a shared confound -- so any p < alpha is a false
positive by construction.

Variant 1 -- ASYMMETRIC (skewed) event kernels. Real synaptic/population responses rise fast and
decay slowly (physiologically closer to an alpha function / EMG than a symmetric Gaussian). We
replace the symmetric Gaussian with a "split-Gaussian" kernel: narrow sigma before the peak
(fast rise), wide sigma after the peak (slow decay). Same shared-jitter E_i structure as the
validated generator, only the kernel shape changes.

Variant 2 -- PARTIALLY INDEPENDENT jitter. Instead of P and R sharing the exact same E_i, R's
jitter is rho * E_i + sqrt(1 - rho^2) * independent_noise_i, for rho in {1.0, 0.7, 0.3}. rho=1.0
reproduces the original (fully shared) confound as a sanity check; lower rho tests whether B2/C
degrade gracefully as sharing becomes imperfect (the realistic case).

Variant 3 -- SLOW LATENT COMMON STATE modulating AMPLITUDE, not timing. An AR(1) latent state
across TRIAL INDEX (not within-trial time), stationary N(0,1), with high autocorrelation (phi),
scales the PEAK AMPLITUDE of both P's and R's response kernels on every trial. Timing jitter is
set to ZERO in this variant so the confound is a pure amplitude co-modulation with no timing
signal at all -- a deliberate stress test of whether B2 (a timing realignment) and C (a
timing-nuisance-binned permutation) have a blind spot for a confound mechanism they were never
designed to address.

Usage: python omission/scripts/dev_generator_robustness_20260828.py
Output: omission/artifacts/.lab/generator-robustness-20260828.json (+ printed summary table)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from omission.jnwb_ext.common_driver_control import (
    FS,
    LAGS_MS,
    _gaussian_kernel,
    matched_filter_peak_realign,
    matched_permutation_pvalue,
    trial_shuffle_pvalue,
)

ALPHA = 0.05
# 2026-08-28 SCOPE CUT (Hamm/coordinator, mid-task): the original 8-seed/n_perm=150/3-rho design
# does not finish within a single blocking call; reduced to 3 seeds, n_perm=50, rho in {1.0, 0.3}
# (dropped 0.7), and Candidate C is skipped for variant 2 (both rho values) since it is the most
# expensive method per seed and rho=1.0 vs rho=0.3 raw/B2 behavior alone is enough to see whether
# degradation is graceful. All 3 variants are kept; C still runs for variant 1 and variant 3.
N_PERM = 50
SEEDS = [0, 1, 2]  # 3 seeds per configuration (reduced from 8 for a single blocking run)

# raw/B2 use n_trials=60 -- matches the regime B2 was originally validated at in
# common_driver_control.py's own docstring-referenced benchmark (n_trials=60, jitter_sd_ms=8.0).
N_TRIALS_RAWB2 = 60
TRIAL_LEN = 400
P_CENTER, P_SIGMA = 150.0, 25.0
R_CENTER, R_SIGMA = 220.0, 5.0
NOISE_SD = 0.3
JITTER_SD_MS = 8.0

# C needs n_trials>=200 with ~10 trials/bin to stay in its validated regime (module docstring:
# "needs n_trials>=200 with ~10 trials/bin for near-nominal false-positive rate").
N_TRIALS_C = 200
N_BINS_C = 20  # 200/20 = 10 trials/bin exactly


# -------------------------------------------------------------------------------------------
# Variant 1: asymmetric (skewed) event kernels
# -------------------------------------------------------------------------------------------

def _skewed_kernel(t, center, sigma, skew_ratio=2.5):
    """Split-Gaussian: narrow sigma before the peak (fast rise), sigma*skew_ratio after the peak
    (slow decay) -- a simple, numpy-only stand-in for an alpha-function / exponentially-modified-
    Gaussian PSP shape, chosen because it needs no extra dependency (no scipy) and its asymmetry
    is controlled by a single interpretable parameter (skew_ratio)."""
    sigma_left = sigma
    sigma_right = sigma * skew_ratio
    left = np.exp(-0.5 * ((t - center) / sigma_left) ** 2)
    right = np.exp(-0.5 * ((t - center) / sigma_right) ** 2)
    return np.where(t < center, left, right)


def synth_skewed_kernel_negctrl(n_trials, trial_len=TRIAL_LEN, p_center=P_CENTER, p_sigma=P_SIGMA,
                                 r_center=R_CENTER, r_sigma=R_SIGMA, jitter_sd_ms=JITTER_SD_MS,
                                 noise_sd=NOISE_SD, skew_ratio=2.5, seed=0):
    """Zero-coupling negative control: shared jitter E_i drives both P and R via SKEWED kernels
    instead of symmetric Gaussians. No coupling term -- pure shared confound."""
    rng = np.random.default_rng(seed)
    t = np.arange(trial_len)
    P_trials = np.empty((n_trials, trial_len))
    R_trials = np.empty((n_trials, trial_len))
    for i in range(n_trials):
        e_i = rng.normal(0, jitter_sd_ms) if jitter_sd_ms > 0 else 0.0
        P_trials[i] = _skewed_kernel(t, p_center + e_i, p_sigma, skew_ratio) + rng.normal(0, noise_sd, trial_len)
        R_trials[i] = _skewed_kernel(t, r_center + e_i, r_sigma, skew_ratio) + rng.normal(0, noise_sd, trial_len)
    return P_trials, R_trials


# -------------------------------------------------------------------------------------------
# Variant 2: partially independent (correlated, not identical) jitter
# -------------------------------------------------------------------------------------------

def synth_partial_shared_jitter_negctrl(n_trials, rho, trial_len=TRIAL_LEN, p_center=P_CENTER,
                                         p_sigma=P_SIGMA, r_center=R_CENTER, r_sigma=R_SIGMA,
                                         jitter_sd_ms=JITTER_SD_MS, noise_sd=NOISE_SD, seed=0):
    """Zero-coupling negative control: P's jitter is E_i ~ N(0, jitter_sd_ms); R's jitter is
    rho*E_i + sqrt(1-rho^2)*independent_i (same marginal SD as E_i, correlation rho with E_i).
    rho=1.0 reproduces the original fully-shared-jitter generator exactly (as a sanity check);
    rho<1 makes the confound imperfectly shared, which is the realistic case on real data."""
    rng = np.random.default_rng(seed)
    t = np.arange(trial_len)
    e = rng.normal(0, jitter_sd_ms, size=n_trials)
    indep = rng.normal(0, jitter_sd_ms, size=n_trials)
    r_jitter = rho * e + np.sqrt(max(0.0, 1 - rho ** 2)) * indep
    P_trials = np.empty((n_trials, trial_len))
    R_trials = np.empty((n_trials, trial_len))
    for i in range(n_trials):
        P_trials[i] = _gaussian_kernel(t, p_center + e[i], p_sigma) + rng.normal(0, noise_sd, trial_len)
        R_trials[i] = _gaussian_kernel(t, r_center + r_jitter[i], r_sigma) + rng.normal(0, noise_sd, trial_len)
    return P_trials, R_trials


# -------------------------------------------------------------------------------------------
# Variant 3: slow latent common state modulating AMPLITUDE (not timing)
# -------------------------------------------------------------------------------------------

def _ar1_latent(n_trials, phi, rng):
    """Stationary AR(1) over TRIAL INDEX, marginal N(0,1): x_i = phi*x_{i-1} + sqrt(1-phi^2)*eps_i.
    High phi => slowly drifting state across trials (e.g. arousal/session-state proxy)."""
    x = np.empty(n_trials)
    x[0] = rng.normal(0, 1)
    for i in range(1, n_trials):
        x[i] = phi * x[i - 1] + np.sqrt(1 - phi ** 2) * rng.normal(0, 1)
    return x


def synth_amplitude_comod_negctrl(n_trials, trial_len=TRIAL_LEN, p_center=P_CENTER, p_sigma=P_SIGMA,
                                   r_center=R_CENTER, r_sigma=R_SIGMA, noise_sd=NOISE_SD,
                                   phi=0.95, amp_gain=0.6, jitter_sd_ms=0.0, seed=0):
    """Zero-coupling negative control: NO shared timing jitter by default (jitter_sd_ms=0 --
    pure amplitude-only confound, the sharpest test of whether B2/C's timing-focused logic has a
    blind spot). A slow AR(1) latent state z_i (autocorrelated across trials) scales BOTH P's and
    R's peak amplitude on every trial via (1 + amp_gain*z_i). z_i is never used for coupling --
    both signals' kernels stay centered at their own fixed nominal centers (no timing information
    is shared at all when jitter_sd_ms=0)."""
    rng = np.random.default_rng(seed)
    t = np.arange(trial_len)
    z = _ar1_latent(n_trials, phi, rng)
    P_trials = np.empty((n_trials, trial_len))
    R_trials = np.empty((n_trials, trial_len))
    for i in range(n_trials):
        e_i = rng.normal(0, jitter_sd_ms) if jitter_sd_ms > 0 else 0.0
        amp = 1.0 + amp_gain * z[i]
        P_trials[i] = amp * _gaussian_kernel(t, p_center + e_i, p_sigma) + rng.normal(0, noise_sd, trial_len)
        R_trials[i] = amp * _gaussian_kernel(t, r_center + e_i, r_sigma) + rng.normal(0, noise_sd, trial_len)
    return P_trials, R_trials


# -------------------------------------------------------------------------------------------
# Harness
# -------------------------------------------------------------------------------------------

def run_negative_control_battery(gen_fn_rawb2, gen_fn_c, label, extra=None, skip_c=False):
    """gen_fn_rawb2(seed) -> (P,R) at N_TRIALS_RAWB2; gen_fn_c(seed) -> (P,R) at N_TRIALS_C.
    Runs raw trial_shuffle_pvalue, B2 (matched_filter_peak_realign + trial_shuffle_pvalue), and
    (unless skip_c) C (matched_permutation_pvalue) across SEEDS, and reports false-positive rate
    at alpha=0.05 for each method run."""
    results = {"label": label, "extra": extra or {}, "seeds": SEEDS, "skip_c": skip_c,
               "raw": [], "b2": [], "c": []}
    for seed in SEEDS:
        t0 = time.time()
        P, R = gen_fn_rawb2(seed)
        r_raw = trial_shuffle_pvalue(P, R, n_perm=N_PERM, seed=seed)
        P_al, R_al, shifts = matched_filter_peak_realign(P, R, n_folds=5, max_shift=60, seed=seed)
        r_b2 = trial_shuffle_pvalue(P_al, R_al, n_perm=N_PERM, seed=seed + 100)
        results["raw"].append({"seed": seed, "p": r_raw["p"]})
        results["b2"].append({"seed": seed, "p": r_b2["p"]})

        if not skip_c:
            Pc, Rc = gen_fn_c(seed)
            r_c = matched_permutation_pvalue(Pc, Rc, n_bins=N_BINS_C, n_perm=N_PERM, seed=seed)
            results["c"].append({"seed": seed, "p": r_c["p"]})
            c_str = f"c_p={r_c['p']:.4f}"
        else:
            c_str = "c=SKIPPED"
        print(f"  [{label}] seed={seed} raw_p={r_raw['p']:.4f} b2_p={r_b2['p']:.4f} "
              f"{c_str}  ({time.time()-t0:.1f}s)", flush=True)

    methods = ("raw", "b2") if skip_c else ("raw", "b2", "c")
    for method in methods:
        ps = np.array([r["p"] for r in results[method]])
        n_fp = int(np.sum(ps < ALPHA))
        results[f"{method}_fpr"] = n_fp / len(ps)
        results[f"{method}_n_fp"] = n_fp
        results[f"{method}_n_seeds"] = len(ps)
        results[f"{method}_ps"] = ps.tolist()
    return results


def main():
    t_start = time.time()
    all_results = []

    # Variant 1: asymmetric skewed kernels
    all_results.append(run_negative_control_battery(
        gen_fn_rawb2=lambda seed: synth_skewed_kernel_negctrl(N_TRIALS_RAWB2, seed=seed),
        gen_fn_c=lambda seed: synth_skewed_kernel_negctrl(N_TRIALS_C, seed=seed + 500000),
        label="variant1_skewed_kernel",
        extra={"skew_ratio": 2.5},
    ))

    # Variant 2: partially independent jitter, rho in {1.0, 0.3} (0.7 dropped for scope; C
    # skipped here -- most expensive method per seed, and raw/B2 alone across rho=1.0 vs 0.3 is
    # enough to see whether degradation is graceful, per the scope cut above)
    for rho in (1.0, 0.3):
        all_results.append(run_negative_control_battery(
            gen_fn_rawb2=lambda seed, rho=rho: synth_partial_shared_jitter_negctrl(N_TRIALS_RAWB2, rho, seed=seed),
            gen_fn_c=lambda seed, rho=rho: synth_partial_shared_jitter_negctrl(N_TRIALS_C, rho, seed=seed + 500000),
            label=f"variant2_partial_jitter_rho{rho}",
            extra={"rho": rho},
            skip_c=True,
        ))

    # Variant 3: slow latent amplitude co-modulation (pure amplitude confound, jitter_sd_ms=0)
    all_results.append(run_negative_control_battery(
        gen_fn_rawb2=lambda seed: synth_amplitude_comod_negctrl(N_TRIALS_RAWB2, seed=seed),
        gen_fn_c=lambda seed: synth_amplitude_comod_negctrl(N_TRIALS_C, seed=seed + 500000),
        label="variant3_amplitude_comod",
        extra={"phi": 0.95, "amp_gain": 0.6, "jitter_sd_ms": 0.0},
    ))

    summary = {
        "generated_by": "omission/scripts/dev_generator_robustness_20260828.py",
        "purpose": (
            "Generalization stress test of negative-control candidates B2 "
            "(matched_filter_peak_realign+trial_shuffle_pvalue) and C (matched_permutation_pvalue), "
            "validated in common_driver_control.py against ONE generator (symmetric-Gaussian, "
            "fully-shared per-trial timing jitter), re-run against 3 structurally different "
            "zero-coupling confound generators."
        ),
        "alpha": ALPHA,
        "n_perm": N_PERM,
        "n_seeds": len(SEEDS),
        "n_trials_raw_b2": N_TRIALS_RAWB2,
        "n_trials_c": N_TRIALS_C,
        "n_bins_c": N_BINS_C,
        "runtime_sec": time.time() - t_start,
        "results": all_results,
    }

    out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "generator-robustness-20260828.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== SUMMARY: false-positive rate at alpha=0.05 (n_seeds=%d, n_perm=%d) ===" % (len(SEEDS), N_PERM))
    print(f"{'variant':<32}{'raw_fpr':>10}{'b2_fpr':>10}{'c_fpr':>10}")
    for r in all_results:
        c_fpr_str = f"{r['c_fpr']:.3f}" if not r.get("skip_c") else "SKIPPED"
        print(f"{r['label']:<32}{r['raw_fpr']:>10.3f}{r['b2_fpr']:>10.3f}{c_fpr_str:>10}")
    print(f"\nTotal runtime: {summary['runtime_sec']:.1f}s")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
