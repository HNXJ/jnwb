"""omission.jnwb_ext.spk_lfp_pilot -- representative-session SPK-LFP analysis under the
DOWNGRADED estimand (2026-08-29, Hamm).

WHAT THIS ANSWERS
    Does band-specific PAST LFP state carry incremental information about SUBSEQUENT firing,
    beyond measured task structure and observable state?

WHAT THIS DOES NOT ANSWER, BY CONSTRUCTION
    Whether LFP drives firing. The causal-identification branch is CONFIRMED closed
    (causal-identification-branch-seal-20260828.json): observable nuisance covariates cannot
    calibrate gain-confounded directionality on this corpus, and the directional-asymmetry
    statistic was shown to FABRICATE a direction (20/20 seeds) from symmetric common drive.
    Therefore this module reports association and past-conditioned predictive dependence ONLY.
    No function here computes a directional-asymmetry statistic, and none should be added.

TERMINOLOGY REQUIRED IN ALL OUTPUTS
    "incremental predictive dependence" / "past-conditioned predictive association".
    Never "drives", "causal influence", "routing", or "top-down causal".

CAUSALITY OF FEATURES (not of inference)
    All LFP features come from omission.jnwb_ext.causal_signal.causal_envelope: one-sided FIR
    bandpass -> rectify -> one-sided exponential smoothing. No sample after time t contributes to
    the envelope at time t. Startup transients are discarded explicitly. This guarantees temporal
    PRECEDENCE of the features; it does not license a causal claim.

    Two distinct latencies are carried through to every result and must not be conflated:
      group_delay_ms       -- the FIR's own delay
      effective_latency_ms -- group delay + smoothing centroid delay (the estimator's true lag)
    A feature at nominal lag tau reflects raw LFP at approximately tau + effective_latency_ms.
    Theta's effective latency is ~394 ms at fs=1000; high_gamma's is ~49 ms. Slow bands therefore
    support "historical state" statements, NOT millisecond-precision lag statements.

SPIKE-CONTAMINATION CONTROLS (high gamma especially, but computed for every band)
    C0  own channel (the unit's peak_channel_id)
    C1  own channel excluded (same probe, all other channels)
    C2  nearby independent channels (|delta local_index| within a stated near range, own excluded)
    C3  distant channels (|delta local_index| >= a stated far threshold, same probe)
    A high-gamma effect present in C0 but absent in C1/C2/C3 is classified as POSSIBLE SPIKE
    CONTAMINATION, not field coupling. Channel separation is expressed in local_index units (a
    probe-ordering proxy); no physical inter-contact distance is asserted.

CROSS-VALIDATION
    Physical-trial-blocked. Each row IS one physical trial keyed by the canonical identity
    (session, absolute onset) -- see trial-collision-forensics-20260829.json -- so KFold over rows
    is trial-blocked by construction. Scalers and models are fit inside training folds only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

from omission.jnwb_ext.causal_signal import BANDS, causal_envelope
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS

FS = 1000.0

# Distributed lag intervals, in ms BEFORE the response window opens. Deliberately broad and
# band-adapted downstream: per the detection-vs-localization dissociation established
# synthetically (rho-beta-identifiability-surface-20260828.json), detection is reliable well
# before lag localization is, so intervals -- not a single tau* -- are the reported quantity.
LAG_INTERVALS_MS: tuple[tuple[float, float], ...] = (
    (0.0, 25.0), (25.0, 50.0), (50.0, 100.0), (100.0, 250.0),
)

# Channel-control geometry, in local_index units along a probe (NOT physical distance).
C2_NEAR_MIN, C2_NEAR_MAX = 4, 12
C3_FAR_MIN = 40


@dataclass(frozen=True)
class ChannelSets:
    """Resolved channel indices (positions into the EpochBatch channel axis) per control."""
    c0_own: np.ndarray
    c1_own_excluded: np.ndarray
    c2_nearby: np.ndarray
    c3_distant: np.ndarray

    def as_dict(self) -> dict[str, np.ndarray]:
        return {"C0_own": self.c0_own, "C1_own_excluded": self.c1_own_excluded,
                "C2_nearby": self.c2_nearby, "C3_distant": self.c3_distant}


def electrode_row_count(nwb_path) -> int:
    """Number of rows in the session's NWB electrodes table.

    NOTE: a row COUNT is necessary but NOT sufficient to license row-position addressing -- a
    count-preserving REORDER of signal_metadata passes this check and silently mis-addresses.
    Prefer electrode_probe_sequence() with resolve_channel_sets(electrode_probes=...).
    """
    import h5py

    with h5py.File(str(nwb_path), "r") as h:
        return int(np.asarray(h["general/extracellular_ephys/electrodes/id"][()]).ravel().size)


def electrode_probe_sequence(nwb_path) -> np.ndarray:
    """Per-electrode-row probe names, in electrodes-table order.

    This is the ORDER-SENSITIVE precondition for row-position addressing. Comparing it
    element-for-element against signal_metadata['probe'] catches a reorder, which a row count
    cannot. Found necessary 2026-08-29 when a count-preserving reorder was shown to resolve
    electrode row 300 to probeB instead of probeC with no error raised.
    """
    import h5py

    with h5py.File(str(nwb_path), "r") as h:
        e = h["general/extracellular_ephys/electrodes"]
        key = "probe" if "probe" in e else "group_name"
        raw = np.asarray(e[key][()]).ravel()
    return np.array([v.decode() if isinstance(v, bytes) else str(v) for v in raw], dtype=object)


def resolve_channel_sets(signal_metadata: pd.DataFrame, peak_channel_id: int,
                          *, n_electrodes: int | None = None,
                          electrode_probes=None) -> ChannelSets | None:
    """Map a unit's peak channel to the four contamination-control channel sets, restricted to
    the unit's OWN probe (cross-probe LFP is a different signal, not a distance control).

    ADDRESSING (corrected 2026-08-29, bug-channel-id-probe-local-20260829)
        A unit's ``peak_channel_id`` is a ROW INDEX into the session-global NWB electrodes
        table. It is NOT a value to match against ``signal_metadata['channel_id']``: that column
        is session-unique in some sessions (sub-V182o_ses-260702: 512 unique of 512) and
        PROBE-LOCAL in others (sub-C31o_ses-230816_rec: 128 unique of 384, repeated on all three
        probes). Matching on it dropped 255 of 357 units in C31o and would have silently returned
        another probe's channel under any reordering of signal_metadata.

        Canonical channel identity is therefore (session, electrode row). ``probe`` and
        ``local_index`` are used ONLY for within-probe C1/C2/C3 geometry, never for identity.

        signal_metadata row i corresponds to electrodes row i (verified: equal row counts and
        element-for-element identical probe sequence in all three sessions).

        ROW-POSITION ADDRESSING NEEDS TWO PRECONDITIONS, NOT ONE:
          completeness -- no channel dropped        -> ``n_electrodes`` (row count)
          order        -- no channel reordered      -> ``electrode_probes`` (probe sequence)
        A count-only guard is INSUFFICIENT: a count-preserving reorder was demonstrated to
        resolve electrode row 300 to probeB instead of its true probeC with no error raised.
        Always pass ``electrode_probes`` where the NWB file is available; ``n_electrodes`` alone
        is retained only for callers that cannot open the file.

    Returns None when the unit's peak electrode is not among the loaded LFP channels -- callers
    must skip such units rather than silently substituting another channel.
    """
    sm = signal_metadata.reset_index(drop=True)
    if n_electrodes is not None and len(sm) != int(n_electrodes):
        raise ValueError(
            f"signal_metadata has {len(sm)} rows but the electrodes table has {n_electrodes}. "
            f"Row position no longer indexes the electrodes table, so peak_channel_id cannot be "
            f"resolved safely. Refusing to guess."
        )
    if electrode_probes is not None:
        ep = np.asarray(electrode_probes, dtype=object)
        if len(ep) != len(sm):
            raise ValueError(
                f"electrode probe sequence has {len(ep)} entries but signal_metadata has "
                f"{len(sm)} rows. Row position no longer indexes the electrodes table."
            )
        got = sm["probe"].astype(str).to_numpy()
        want = np.array([str(v) for v in ep], dtype=object)
        if not np.array_equal(got, want):
            first = int(np.flatnonzero(got != want)[0])
            raise ValueError(
                f"signal_metadata is REORDERED relative to the electrodes table: row {first} "
                f"carries probe {got[first]!r} but the electrodes table has {want[first]!r}. "
                f"Row position does not index the electrodes table, so every peak_channel_id "
                f"would resolve to the wrong channel. Refusing to guess."
            )
    own_pos = int(peak_channel_id)
    if not (0 <= own_pos < len(sm)):
        return None
    probe = sm.loc[own_pos, "probe"]
    own_local = int(sm.loc[own_pos, "local_index"])

    same_probe = sm.index[sm["probe"] == probe].to_numpy()
    delta = np.abs(sm.loc[same_probe, "local_index"].to_numpy(dtype=int) - own_local)
    is_own = same_probe == own_pos

    return ChannelSets(
        c0_own=np.array([own_pos]),
        c1_own_excluded=same_probe[~is_own],
        c2_nearby=same_probe[(~is_own) & (delta >= C2_NEAR_MIN) & (delta <= C2_NEAR_MAX)],
        c3_distant=same_probe[(~is_own) & (delta >= C3_FAR_MIN)],
    )


def band_envelope_trials(lfp_trials: np.ndarray, band: str, *, fs: float = FS,
                          smoothing_tau_ms: float = 20.0) -> tuple[np.ndarray, dict]:
    """Causal band-power envelope for ``(trial, time)`` LFP, filtered per trial.

    Returns (envelope, report). ``report`` carries the band's spec, group_delay_ms and
    effective_latency_ms -- the caller MUST propagate these into any temporal claim.
    """
    env, report = causal_envelope(np.asarray(lfp_trials, dtype=float), fs, band,
                                   smoothing_tau_ms=smoothing_tau_ms, power=True)
    return env, report


def valid_from_ms(report: dict, window_start_ms: float) -> float:
    """Earliest time (in the epoch's own ms axis) at which the causal envelope is free of the
    filter's startup transient. Samples before this are NOT usable and must be excluded rather
    than merely deprecated."""
    return float(window_start_ms) + float(report["startup_transient_ms"])


def lag_interval_features(env: np.ndarray, time_ms: np.ndarray, event_ms: float,
                           intervals=LAG_INTERVALS_MS) -> np.ndarray:
    """Mean band power in each PAST interval before ``event_ms``. Interval (a, b) means
    [event - b, event - a): strictly before the event, so no post-event sample enters."""
    out = np.empty((env.shape[0], len(intervals)))
    for k, (a, b) in enumerate(intervals):
        mask = (time_ms >= event_ms - b) & (time_ms < event_ms - a)
        out[:, k] = env[:, mask].mean(axis=1) if mask.any() else np.nan
    return out


def spike_counts_in_window(spike_times_s: np.ndarray, onsets_s: np.ndarray,
                           lo_ms: float, hi_ms: float) -> np.ndarray:
    """Per-trial spike count in [onset+lo_ms, onset+hi_ms). Counts, not rates -- the window width
    is constant across trials, so the distinction is a scale factor the model absorbs."""
    st = np.asarray(spike_times_s, dtype=float)
    out = np.empty(len(onsets_s), dtype=float)
    for i, t0 in enumerate(np.asarray(onsets_s, dtype=float)):
        lo, hi = t0 + lo_ms / 1000.0, t0 + hi_ms / 1000.0
        out[i] = float(np.searchsorted(st, hi) - np.searchsorted(st, lo))
    return out


def _held_out_r2(X: np.ndarray, y: np.ndarray, *, n_splits: int, alpha: float, seed: int) -> float:
    """Trial-blocked held-out R^2. Rows are physical trials, so KFold over rows blocks by trial.
    Scaler and Ridge are fit on training folds only."""
    n = len(y)
    if n < n_splits * 2 or np.std(y) == 0:
        return float("nan")
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    pred = np.full(n, np.nan)
    for tr, te in kf.split(X):
        sc = StandardScaler().fit(X[tr])
        model = Ridge(alpha=alpha).fit(sc.transform(X[tr]), y[tr])
        pred[te] = model.predict(sc.transform(X[te]))
    ss_res = np.sum((y - pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def incremental_predictive_dependence(
    lag_features: np.ndarray, nuisance: np.ndarray, spike_history: np.ndarray, y: np.ndarray,
    *, n_splits: int = 5, alpha: float = 1.0, seed: int = 0,
) -> dict:
    """Delta_pred = Perf(M_nuisance + past LFP) - Perf(M_nuisance).

    M_nuisance = spike history + measured task/state covariates. M_pastLFP adds the distributed
    past-LFP interval features. Delta_pred > 0 means past band power carries information about
    subsequent firing BEYOND the nuisance model -- an incremental predictive dependence, NOT a
    causal effect (see module docstring).
    """
    Z = np.column_stack([spike_history.reshape(-1, 1), nuisance]) if nuisance.size else spike_history.reshape(-1, 1)
    ok = np.isfinite(y) & np.all(np.isfinite(Z), axis=1) & np.all(np.isfinite(lag_features), axis=1)
    if ok.sum() < 40:
        return {"delta_pred": float("nan"), "r2_nuisance": float("nan"),
                "r2_past_lfp": float("nan"), "n_trials_used": int(ok.sum())}
    Zc, Lc, yc = Z[ok], lag_features[ok], y[ok]
    r2_nu = _held_out_r2(Zc, yc, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_lfp = _held_out_r2(np.column_stack([Zc, Lc]), yc, n_splits=n_splits, alpha=alpha, seed=seed)
    return {"delta_pred": float(r2_lfp - r2_nu), "r2_nuisance": float(r2_nu),
            "r2_past_lfp": float(r2_lfp), "n_trials_used": int(ok.sum())}


def distributed_lag_coefficients(lag_features: np.ndarray, nuisance: np.ndarray,
                                  spike_history: np.ndarray, y: np.ndarray, *,
                                  alpha: float = 1.0, intervals=LAG_INTERVALS_MS) -> dict:
    """Standardized signed coefficient per lag interval, from a full-data fit.

    DESCRIPTIVE, not inferential -- the inferential quantity is the held-out delta_pred above.
    SIGN IS PRESERVED per interval: a negative coefficient (band power up -> firing down) is a
    result, not a magnitude to be absolute-valued away.
    """
    Z = np.column_stack([spike_history.reshape(-1, 1), nuisance]) if nuisance.size else spike_history.reshape(-1, 1)
    ok = np.isfinite(y) & np.all(np.isfinite(Z), axis=1) & np.all(np.isfinite(lag_features), axis=1)
    if ok.sum() < 40:
        return {"coefficients": {f"{a:g}-{b:g}ms": float("nan") for a, b in intervals},
                "integrated_signed_mass": float("nan"), "n_trials_used": int(ok.sum())}
    X = np.column_stack([Z[ok], lag_features[ok]])
    sc = StandardScaler().fit(X)
    model = Ridge(alpha=alpha).fit(sc.transform(X), y[ok])
    lag_coefs = model.coef_[Z.shape[1]:]
    return {
        "coefficients": {f"{a:g}-{b:g}ms": float(c) for (a, b), c in zip(intervals, lag_coefs)},
        "integrated_signed_mass": float(np.sum(lag_coefs)),
        "n_trials_used": int(ok.sum()),
    }


def signed_association(band_power: np.ndarray, firing: np.ndarray) -> dict:
    """Signed per-trial association between band power and firing, with the four sign
    combinations preserved explicitly rather than collapsed to |r|.

    ``quadrant`` names the joint direction relative to each variable's own median, which is what
    distinguishes (band down, firing up) from (band up, firing up) -- the contrast Hamm requires
    be retained given heterogeneous signed LFP effects in this paradigm.
    """
    ok = np.isfinite(band_power) & np.isfinite(firing)
    if ok.sum() < 20 or np.std(band_power[ok]) == 0 or np.std(firing[ok]) == 0:
        return {"pearson_r": float("nan"), "spearman_rho": float("nan"),
                "sign": "undetermined", "n": int(ok.sum())}
    from scipy import stats
    p = np.asarray(band_power)[ok]
    f = np.asarray(firing)[ok]
    r, _ = stats.pearsonr(p, f)
    rho, _ = stats.spearmanr(p, f)
    hi_p, hi_f = p > np.median(p), f > np.median(f)
    quadrant = {
        "band_up_firing_up": float(np.mean(hi_p & hi_f)),
        "band_up_firing_down": float(np.mean(hi_p & ~hi_f)),
        "band_down_firing_up": float(np.mean(~hi_p & hi_f)),
        "band_down_firing_down": float(np.mean(~hi_p & ~hi_f)),
    }
    return {"pearson_r": float(r), "spearman_rho": float(rho),
            "sign": "positive" if r > 0 else "negative", "quadrant_fractions": quadrant,
            "n": int(ok.sum())}


def band_temporal_support(band: str, *, fs: float = FS, smoothing_tau_ms: float = 20.0) -> dict:
    """The band's effective temporal support, to be attached to EVERY temporal result for that
    band. Without this, a theta lag interval reads as if it had gamma-like precision."""
    probe = np.zeros(int(4 * fs))
    _, report = causal_envelope(probe + np.random.default_rng(0).normal(0, 1, probe.shape),
                                 fs, band, smoothing_tau_ms=smoothing_tau_ms, power=True)
    spec = report["spec"]  # a plain dict, not the CausalFilterSpec NamedTuple
    return {
        "band": band,
        "passband_hz": list(BANDS[band]),
        "numtaps": int(spec["numtaps"]),
        "group_delay_ms": float(spec["group_delay_ms"]),
        "smoothing_tau_ms": float(report["smoothing_tau_ms"]),
        "smoothing_centroid_delay_ms": float(report["smoothing_centroid_delay_ms"]),
        "effective_latency_ms": float(report["effective_latency_ms"]),
        "startup_transient_ms": float(report["startup_transient_ms"]),
        "interpretation_note": (
            "A feature at nominal lag tau reflects raw LFP at approximately tau + "
            f"{float(report['effective_latency_ms']):.0f} ms. Report lag INTERVALS, not a point "
            "estimate, and do not ascribe millisecond precision to slow bands."
        ),
    }


def slot_onset_ms(slot: str) -> float:
    """Onset of a sequence slot in ms relative to p1, from the canonical layout table."""
    return float(EPOCH_ONSETS_MS[slot])
