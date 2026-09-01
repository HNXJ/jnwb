"""omission.jnwb_ext.identifiability -- frequency-specific temporal identifiability sweep.

Pre-P4 requirement (Hamm, 2026-08-27): before any band-specific SPK-LFP lag is interpreted,
empirically determine each band's actual temporal resolution using the EXACT causal feature
pipeline intended for real data (``causal_envelope`` + ``lagged_association``), not a simplified
proxy. Synthetic band-state/spike pairs are built at true delays
{0,5,10,25,50,100,250,500} ms, both directions (LFP-leads-spike and spike-leads-LFP), and the
estimator's recovered nominal lag is compared against ground truth to quantify bias, variance,
sign accuracy, and neighboring-delay discriminability, per band.

Key design point: the synthetic "true LFP band state" S(t) is a smooth, non-negative AR(1)-power
process. A raw LFP trace is built by amplitude-modulating a band-center carrier by sqrt(S(t)).
The spike-rate proxy R(t) is driven by S(t) at a KNOWN true delay -- not by the estimator's own
causal_envelope output. ``causal_envelope`` is then applied to the raw LFP (exactly as it would
be on real data), producing P_hat(t), which itself lags the true S(t) by the band's own
effective_latency_ms (filter group delay + smoothing centroid delay). Because
``lagged_association`` correlates P_hat against R (not S against R), the estimator's OWN latency
necessarily enters the recovered nominal lag: recovered_lag ~= true_delay - effective_latency_ms.
This sweep exists to make that bias/variance relationship an empirical, per-band, receipted
quantity rather than an assumption.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from omission.jnwb_ext.causal_signal import BANDS, causal_envelope, filter_spec
from omission.jnwb_ext.lag_estimation import lagged_association
from omission.jnwb_ext.seed import stable_seed

FS = 1000.0


def _ar1_power(n: int, rho: float, rng: np.random.Generator) -> np.ndarray:
    x = np.empty(n)
    x[0] = rng.normal(0, 1.0)
    for i in range(1, n):
        x[i] = rho * x[i - 1] + rng.normal(0, np.sqrt(1 - rho ** 2))
    return x ** 2  # smooth, non-negative power-like process


def _synthesize_pair(band: str, true_delay_ms: float, fs: float, seed: int, noise_sd: float = 0.3):
    """Returns (raw_lfp, R, true_delay_ms). true_delay_ms > 0: LFP band state leads spike proxy.
    true_delay_ms < 0: spike proxy leads LFP band state (roles swapped in construction)."""
    rng = np.random.default_rng(seed)
    low_hz, high_hz = BANDS[band]
    f0 = (low_hz + high_hz) / 2.0
    delay_samples = int(round(abs(true_delay_ms) * fs / 1000.0))
    pad = delay_samples + 200  # burn-in beyond the shift itself
    n = 4000 + pad

    driver = _ar1_power(n, rho=0.97, rng=rng)  # the leading process (whichever role it plays)
    follower = np.empty(n)
    if delay_samples == 0:
        follower = driver.copy()
    else:
        follower[:delay_samples] = rng.normal(0, 0.1, size=delay_samples)
        follower[delay_samples:] = driver[: n - delay_samples]

    if true_delay_ms >= 0:
        S = driver         # true LFP band-state process
        R_drive = follower  # spike-rate drive, delayed relative to S by true_delay_ms
    else:
        R_drive = driver     # spike-rate drive leads
        S = follower          # true LFP band-state, delayed relative to spike drive

    t = np.arange(n)
    carrier = np.sin(2 * np.pi * f0 * t / fs)
    raw_lfp = np.sqrt(np.maximum(S, 0)) * carrier + rng.normal(0, noise_sd, size=n)
    R = R_drive + rng.normal(0, noise_sd, size=n)
    return raw_lfp, R, n


def recover_lag(band: str, true_delay_ms: float, fs: float, seed: int, lag_grid_ms: np.ndarray) -> dict:
    raw_lfp, R, n = _synthesize_pair(band, true_delay_ms, fs, seed)
    P_hat, report = causal_envelope(raw_lfp, fs, band, power=True)
    spec = filter_spec(band, fs)
    burn_in = spec.startup_transient_samples
    C = lagged_association(P_hat[burn_in:], R[burn_in:], lag_grid_ms, fs=fs)
    if np.all(np.isnan(C)):
        return {"recovered_lag_ms": np.nan, "peak_corr": np.nan,
                "effective_latency_ms": report["effective_latency_ms"]}
    peak_idx = int(np.nanargmax(np.abs(C)))
    return {
        "recovered_lag_ms": float(lag_grid_ms[peak_idx]),
        "peak_corr": float(C[peak_idx]),
        "effective_latency_ms": report["effective_latency_ms"],
    }


def run_identifiability_sweep(
    *,
    bands: dict = BANDS,
    true_delays_ms=(0, 5, 10, 25, 50, 100, 250, 500),
    n_repeats: int = 8,
    fs: float = FS,
    lag_grid_ms: np.ndarray | None = None,
) -> pd.DataFrame:
    if lag_grid_ms is None:
        lag_grid_ms = np.arange(-1000, 1001, 5.0)

    rows = []
    for band in bands:
        for d in true_delays_ms:
            signed_delays = [0.0] if d == 0 else [float(d), -float(d)]
            for signed_d in signed_delays:
                for rep in range(n_repeats):
                    seed = stable_seed(band, signed_d, rep)
                    res = recover_lag(band, signed_d, fs, seed, lag_grid_ms)
                    rows.append({
                        "band": band, "true_delay_ms": signed_d, "repeat": rep,
                        "recovered_lag_ms": res["recovered_lag_ms"],
                        "peak_corr": res["peak_corr"],
                        "effective_latency_ms": res["effective_latency_ms"],
                        "bias_ms": res["recovered_lag_ms"] - signed_d if not np.isnan(res["recovered_lag_ms"]) else np.nan,
                        "correct_sign": (
                            np.nan if signed_d == 0 else
                            bool(np.sign(res["recovered_lag_ms"]) == np.sign(signed_d))
                            if not np.isnan(res["recovered_lag_ms"]) else False
                        ),
                    })
    return pd.DataFrame(rows)


def summarize_sweep(df: pd.DataFrame) -> pd.DataFrame:
    """Per-band summary: bias/variance of recovered lag, TWO distinct sign-accuracy quantities,
    and a minimum resolvable delay -- all computed separately per signed true_delay (never
    pooling +delay with -delay, which sit on opposite sides of the estimator's own bias baseline
    and would corrupt any separation statistic if pooled by |delay|).

    Two sign-accuracy quantities are reported, and must not be conflated (this distinction is
    itself part of what this sweep is for):
      - p_correct_sign_nominal: sign(recovered_lag_ms) vs sign(true_delay_ms) -- the naive
        reading a user would get from Estimand B if they treated the raw nominal lag as the
        directional answer. This is EXPECTED to be poor for |true_delay| << effective_latency_ms,
        because recovered_lag_ms ~= true_delay_ms - effective_latency_ms: a small positive true
        delay still yields a negative nominal lag once the estimator's own latency dominates.
        A low value here is not necessarily an estimator failure -- it is the exact conflation
        risk Hamm's review flagged, made an explicit, measured quantity.
      - p_correct_sign_latency_corrected: sign(recovered_lag_ms + effective_latency_ms) vs
        sign(true_delay_ms) -- correcting for the estimator's OWN known, constant latency before
        asking about directionality. This is the meaningful Estimand-A-style quantity: can the
        pipeline recover which side of zero the true delay is on, once its own bias is removed.

    min_resolvable_delay_ms (per sign, then the two signs' worse case is kept) is the smallest
    tested |true_delay_ms| at which the (latency-corrected) recovered-delay distribution's mean
    separates from 0 by more than 1 SD of the true_delay=0 distribution's own spread -- an
    explicit, conservative, reportable criterion, not a claim of a sharp physical threshold.
    """
    out = []
    for band, g in df.groupby("band"):
        eff_lat = float(g["effective_latency_ms"].iloc[0])
        corrected = g["recovered_lag_ms"] + eff_lat  # bias-corrected recovered TRUE delay estimate

        zero = corrected[g["true_delay_ms"] == 0].dropna()
        zero_sd = float(zero.std()) if len(zero) > 1 else np.nan
        zero_mean = float(zero.mean()) if len(zero) else np.nan

        sign_nominal = np.sign(g["recovered_lag_ms"]) == np.sign(g["true_delay_ms"])
        sign_corrected = np.sign(corrected) == np.sign(g["true_delay_ms"])
        nonzero_mask = g["true_delay_ms"] != 0

        min_resolvable_per_sign = []
        for sign in (1, -1):
            mags = sorted(g.loc[(np.sign(g["true_delay_ms"]) == sign), "true_delay_ms"].abs().unique())
            resolved = None
            for mag in mags:
                sub = corrected[(np.sign(g["true_delay_ms"]) == sign) & (g["true_delay_ms"].abs() == mag)].dropna()
                if len(sub) < 2 or np.isnan(zero_sd):
                    continue
                if abs(float(sub.mean()) - zero_mean) > zero_sd:
                    resolved = float(mag)
                    break
            if resolved is not None:
                min_resolvable_per_sign.append(resolved)
        min_resolvable = max(min_resolvable_per_sign) if len(min_resolvable_per_sign) == 2 else None

        # robust (median/IQR) companion stats -- a peak-argmax estimator can be multimodal
        # (secondary/sidelobe correlation peaks, worst for narrowband/low-frequency filters),
        # in which case a mean/SD summary is misleading: a few gross outliers inflate variance
        # without describing the estimator's TYPICAL behavior. Report both, do not average over
        # this distinction.
        corrected_dev = (corrected - (g["true_delay_ms"])).abs()  # |corrected recovered - true|, per row
        median_abs_dev_from_true = float(corrected_dev.median())
        mad = float((corrected_dev - corrected_dev.median()).abs().median()) * 1.4826  # normal-consistent MAD
        outlier_thresh = median_abs_dev_from_true + 5 * mad if mad > 0 else median_abs_dev_from_true + 50.0
        outlier_fraction = float((corrected_dev > outlier_thresh).mean())

        out.append({
            "band": band,
            "effective_latency_ms": eff_lat,
            "zero_delay_corrected_mean_ms": zero_mean,
            "zero_delay_corrected_sd_ms": zero_sd,
            "mean_bias_ms": float(g["bias_ms"].mean()),
            "mean_abs_bias_ms": float(g["bias_ms"].abs().mean()),
            "median_abs_deviation_from_true_ms": median_abs_dev_from_true,
            "mad_robust_sd_ms": mad,
            "outlier_fraction_gt_median_plus_5mad": outlier_fraction,
            "p_correct_sign_nominal": float(sign_nominal[nonzero_mask].mean()),
            "p_correct_sign_latency_corrected": float(sign_corrected[nonzero_mask].mean()),
            "min_resolvable_delay_ms": min_resolvable,
        })
    return pd.DataFrame(out).sort_values("effective_latency_ms").reset_index(drop=True)
