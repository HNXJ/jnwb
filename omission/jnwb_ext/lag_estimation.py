"""omission.jnwb_ext.lag_estimation -- minimal signed lag-association reference estimator.

PROTOTYPE, NOT Analysis A. This is the small, deliberately simple estimator the P0 synthetic
validation harness (``omission/tests/test_causal_validation.py``) uses to prove the lag-sign
convention, causal-feature construction, and null machinery behave correctly on known-delay
synthetic data, per Hamm's explicit sequencing (P0 validation harness before the real scientific
estimators). The full P4 fine-scale SPK-LFP lag estimator (session/area/unit/band aggregation,
trial structure, permutation-null p-values, peak-lag multiplicity correction) is separate,
later, and will reuse/extend this function rather than duplicate its core computation -- do not
treat this module as already answering a scientific question about real data.

Fixed sign convention (never reversed, per Hamm's explicit instruction):
    lag > 0 ms  =>  LFP precedes spike (band feature at t predicts firing at t + lag)
    lag < 0 ms  =>  spike precedes LFP (firing at t predicts band feature at t + |lag|)
"""
from __future__ import annotations

import numpy as np


def lagged_association(
    P: np.ndarray,
    R: np.ndarray,
    lags_ms: np.ndarray,
    *,
    fs: float,
    method: str = "pearson",
) -> np.ndarray:
    r"""C(tau) = Assoc(P(t), R(t + tau)) for each tau in lags_ms.

    Args:
        P: (n_times,) causal band amplitude/power trace (the presumed "leading" signal at
            positive lag).
        R: (n_times,) causally estimated firing-activity trace, same sampling rate and time
            base as P.
        lags_ms: 1-D array of lags to evaluate, in ms. Positive = LFP leads spike (R is looked
            up FORWARD in time relative to P, i.e. R(t + tau) for tau > 0 uses a firing sample
            that occurs after the P sample it's paired with -- LFP "predicts ahead").
        fs: sampling rate, Hz (shared by P and R).
        method: "pearson" (signed linear correlation -- the default; preserves sign, unlike an
            absolute-value or squared measure) is the only method implemented here; extend only
            if a documented scientific need arises.

    Returns:
        (len(lags_ms),) signed association values, one per lag. NaN where a lag leaves fewer
        than 3 overlapping samples (undefined correlation).

    For tau > 0 (LFP leads spike): pair P[t] with R[t + tau_samples] -- i.e. shift R BACKWARD
    (equivalently, drop R's leading edge and P's trailing edge) so each P sample is compared to
    an R sample that occurs tau_samples later in absolute time. For tau < 0 the roles invert
    (P is looked up forward relative to R), which is exactly "spike precedes LFP": firing at t
    predicts a P sample that occurs later.
    """
    if method != "pearson":
        raise ValueError(f"only method='pearson' is implemented, got {method!r}")
    P = np.asarray(P, dtype=float)
    R = np.asarray(R, dtype=float)
    if P.shape != R.shape or P.ndim != 1:
        raise ValueError("P and R must be 1-D arrays of equal length")
    n = P.shape[0]

    out = np.full(len(lags_ms), np.nan, dtype=float)
    for i, tau_ms in enumerate(lags_ms):
        tau_samples = int(round(tau_ms * fs / 1000.0))
        if tau_samples >= 0:
            p_seg = P[: n - tau_samples] if tau_samples > 0 else P
            r_seg = R[tau_samples:]
        else:
            p_seg = P[-tau_samples:]
            r_seg = R[: n + tau_samples]
        if len(p_seg) < 3 or np.std(p_seg) == 0 or np.std(r_seg) == 0:
            continue
        out[i] = float(np.corrcoef(p_seg, r_seg)[0, 1])
    return out
