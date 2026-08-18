r"""
S1 (analysis_spec_SPK.md): likelihood-of-firing unit-inclusion criterion.

Replaces fixation-baseline-contrast selection with P(unit fires | omission) vs
P(unit fires | immediately pre-omission baseline). The bug this fixes: the old
template-correlation O+ classifier (scripts/archive_oneoff/find_all_s_and_o_units.py) scores a
unit against a template that is zero at the fx epoch, so a unit that fires strongly during BOTH
fixation and omission correlates poorly with the template and can be rejected despite a genuine
omission response. jnwb.unit_classification's own O+ path does not use fx and is not the buggy
mechanism -- this module does not replace it, only adds a second, independent criterion
alongside it.

Corrected criterion (Hamm, 2026-08-17): a unit is accepted as omission-responsive if it fires
more during the omission slot than during the immediately-preceding pre-omission window --
fixation firing is simply not part of the comparison at all, at any amplitude, which is the
direct fix (not a fx-inclusive random-timeline null, which was the first-pass design here and
is superseded).

Baseline window, v2 (duration-matched, Hamm 2026-08-17): the first cut used
jnwb.unit_classification's own OM_BASE_LEAD_MS/OM_BASE_GAP_MS (250ms window ending 50ms before
the omission slot) -- this was WRONG for a fire-probability comparison: a 200ms window has a
mechanically lower P(>=1 spike) than the 531ms omission window even for a unit with zero real
selectivity, purely from window length (P(fire) = 1-exp(-rate*duration)). Measured on the
first smoke-test session: this length artifact alone predicted 0.60 correlation with the
observed effect and averaged LARGER than the mean observed risk difference (0.181 vs 0.134),
inflating the inclusion rate to 73.7% against this project's own documented O+ prevalence
target of <1%. Fixed by duration-matching the baseline window to the omission window's own
duration (531ms), ending OM_BASE_GAP_MS (50ms) before the omission window starts -- this trades
the length artifact for a smaller, different one (the window's leading ~81ms falls in the tail
of the PRECEDING stimulus presentation rather than purely in the delay period), a cost accepted
explicitly by Hamm over either re-shortening the omission window or switching to a
rate-normalized comparison.

This module is criterion-agnostic new code; jnwb/unit_classification.py is not edited
(Conservation) -- its criterion-agnostic helpers (_rate_in_window, precompute_condition_onsets,
omission_events, SLOT_WINDOW_MS, GLO_CONDITIONS, OM_BASE_GAP_MS) are imported directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import false_discovery_control

from jnwb.unit_classification import (
    OM_BASE_GAP_MS,
    SLOT_WINDOW_MS,
    _rate_in_window,  # noqa: F401 -- imported for reuse/reference by callers, not used directly here
    omission_events,
)

METHOD_ID = "likelihood_of_firing_vs_local_pre_omission_baseline_v2_duration_matched"


def local_pre_omission_window(omission_win_ms: Tuple[float, float]) -> Tuple[float, float]:
    """Immediately pre-omission reference window, duration-matched to the omission window
    (avoids the P(fire)=1-exp(-rate*duration) length artifact a shorter baseline window would
    introduce) and gap-separated from it by OM_BASE_GAP_MS so the two never collide/overlap."""
    dur = omission_win_ms[1] - omission_win_ms[0]
    end = omission_win_ms[0] - OM_BASE_GAP_MS
    return (end - dur, end)


@dataclass(frozen=True)
class InclusionConfig:
    n_shuffles: int = 2000
    n_bootstrap: int = 2000
    alpha: float = 0.05
    min_omission_events: int = 8
    seed: int = 42


def fires_in_window(spike_times: np.ndarray, onset_s: float, window_ms: Tuple[float, float]) -> bool:
    """True iff >=1 spike falls in [onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000)."""
    t0 = onset_s + window_ms[0] / 1000.0
    t1 = onset_s + window_ms[1] / 1000.0
    if t1 <= t0:
        return False
    n = int(np.searchsorted(spike_times, t1, side="right") - np.searchsorted(spike_times, t0, side="left"))
    return n > 0


def fire_indicator(spike_times: np.ndarray, onsets_s: np.ndarray, window_ms: Tuple[float, float]) -> np.ndarray:
    """Vectorized boolean fire indicator, one entry per onset, constant window."""
    return np.asarray(
        [fires_in_window(spike_times, float(o), window_ms) for o in onsets_s], dtype=bool
    )


def paired_fire_prob_test(
    fires_target: np.ndarray,
    fires_null: np.ndarray,
    n_shuffles: int,
    n_bootstrap: int,
    rng: np.random.Generator,
) -> Dict:
    """
    Paired binary test: P(fire | target window) vs P(fire | paired baseline window).

    Significance: shuffle-null on which member of each trial's pair counts as "target"
    (sign-flip of the paired difference, mirrors unit_classification._shuffle_pvalue_paired,
    alternative="greater" since inclusion asks whether omission firing exceeds the immediately
    pre-omission baseline). Risk-difference CI: paired bootstrap over trials (percentile
    method) -- distinct RNG draws from the shuffle-null so the hypothesis test and the interval
    don't share randomness. Odds ratio: McNemar-style discordant-pair estimator with
    Haldane-Anscombe continuity correction (avoids div-by-zero when one discordant count is 0).
    """
    t = np.asarray(fires_target, dtype=bool)
    u = np.asarray(fires_null, dtype=bool)
    n = min(len(t), len(u))
    if n < 2:
        return {
            "p_fire_target": float(np.mean(t)) if len(t) else float("nan"),
            "p_fire_pre_omission_baseline": float(np.mean(u)) if len(u) else float("nan"),
            "risk_difference": float("nan"),
            "risk_difference_ci_lo": float("nan"),
            "risk_difference_ci_hi": float("nan"),
            "odds_ratio": float("nan"),
            "odds_ratio_ci_lo": float("nan"),
            "odds_ratio_ci_hi": float("nan"),
            "p_value_fire_shuffle": 1.0,
            "n_trials": int(n),
        }

    ta = t[:n].astype(float)
    ua = u[:n].astype(float)
    diff = ta - ua
    obs = float(np.mean(diff))
    p_target = float(np.mean(ta))
    p_null = float(np.mean(ua))

    flips = rng.choice(np.array([-1.0, 1.0]), size=(n_shuffles, n))
    null_dist = flips @ diff / n
    p_value = (1.0 + np.sum(null_dist >= obs)) / (n_shuffles + 1.0)

    boot_idx = rng.integers(0, n, size=(n_bootstrap, n))
    boot_diffs = diff[boot_idx].mean(axis=1)
    ci_lo, ci_hi = np.percentile(boot_diffs, [2.5, 97.5])

    n10 = float(np.sum((ta == 1) & (ua == 0)))
    n01 = float(np.sum((ta == 0) & (ua == 1)))
    n10c, n01c = n10 + 0.5, n01 + 0.5
    odds_ratio = n10c / n01c
    se_log_or = float(np.sqrt(1.0 / n10c + 1.0 / n01c))
    log_or = float(np.log(odds_ratio))
    or_ci_lo = float(np.exp(log_or - 1.96 * se_log_or))
    or_ci_hi = float(np.exp(log_or + 1.96 * se_log_or))

    return {
        "p_fire_target": p_target,
        "p_fire_pre_omission_baseline": p_null,
        "risk_difference": obs,
        "risk_difference_ci_lo": float(ci_lo),
        "risk_difference_ci_hi": float(ci_hi),
        "odds_ratio": float(odds_ratio),
        "odds_ratio_ci_lo": or_ci_lo,
        "odds_ratio_ci_hi": or_ci_hi,
        "p_value_fire_shuffle": float(p_value),
        "n_trials": int(n),
    }


def classify_unit_omission_inclusion(
    spike_times: np.ndarray,
    onsets: Dict[str, np.ndarray],
    cfg: InclusionConfig,
    rng: np.random.Generator,
) -> Dict:
    """
    Pool every omission event ((cond, slot) from unit_classification.omission_events()) into
    one paired fire-probability test per unit, mirroring
    unit_classification._collect_omission_rates' pooling-across-omission-events pattern. The
    baseline is the immediately pre-omission window (local_pre_omission_window) -- fixation is
    not part of the comparison at any amplitude, which is the fix.
    """
    st = np.sort(np.asarray(spike_times, dtype=float))
    target_parts: List[np.ndarray] = []
    null_parts: List[np.ndarray] = []

    for cond, slot in omission_events():
        trials = onsets.get(cond, np.array([]))
        if len(trials) == 0:
            continue
        win = SLOT_WINDOW_MS[slot]
        base_win = local_pre_omission_window(win)
        target_parts.append(fire_indicator(st, trials, win))
        null_parts.append(fire_indicator(st, trials, base_win))

    fires_target = np.concatenate(target_parts) if target_parts else np.array([], dtype=bool)
    fires_null = np.concatenate(null_parts) if null_parts else np.array([], dtype=bool)

    result: Dict = {"n_omission_trials": int(len(fires_target)), "method": METHOD_ID}
    if len(fires_target) >= cfg.min_omission_events:
        result.update(
            paired_fire_prob_test(fires_target, fires_null, cfg.n_shuffles, cfg.n_bootstrap, rng)
        )
    else:
        result.update(
            {
                "p_fire_target": float("nan"),
                "p_fire_pre_omission_baseline": float("nan"),
                "risk_difference": float("nan"),
                "risk_difference_ci_lo": float("nan"),
                "risk_difference_ci_hi": float("nan"),
                "odds_ratio": float("nan"),
                "odds_ratio_ci_lo": float("nan"),
                "odds_ratio_ci_hi": float("nan"),
                "p_value_fire_shuffle": 1.0,
                "n_trials": int(len(fires_target)),
            }
        )
    return result


def assign_omission_inclusion_labels(df: pd.DataFrame, cfg: InclusionConfig) -> pd.DataFrame:
    """
    BH-FDR correct p_value_fire_shuffle across all units in df (one call per session, matching
    unit_classification._assign_labels' per-session correction scope -- a unit's inclusion
    status should not depend on which other sessions happen to be in the batch).
    """
    out = df.copy()
    p = out["p_value_fire_shuffle"].to_numpy(dtype=float)
    q = np.ones_like(p)
    mask = np.isfinite(p)
    if mask.sum() > 0:
        q[mask] = false_discovery_control(p[mask], method="bh")
    out["q_fire_shuffle"] = q
    out["is_omission_inclusion_new"] = (
        (out["q_fire_shuffle"] < cfg.alpha)
        & (out["risk_difference"] > 0)
        & (out["n_omission_trials"] >= cfg.min_omission_events)
    )
    return out


STABLE_CRITERION_VERSION = "presence_ks_snr_v2"


def assign_quality_tier(
    quality: pd.Series,
    trial_presence_fraction: pd.Series,
    snr: pd.Series,
    presence_threshold: float = 0.98,
    snr_threshold: float = 0.5,
) -> pd.Series:
    """
    quality==0 -> 'mua' (Kilosort-flagged, addressing.py's own convention: is_stable = quality>=1).
    quality==1 & presence>threshold & snr>snr_threshold -> 'stable'.
    quality==1 & (presence<=threshold or snr<=snr_threshold or either missing) -> 'unstable'.

    `snr` is confirmed available corpus-wide on the raw NWB units table (session._units_df,
    100% non-null across one session per subject, checked 2026-08-17) -- not routed through the
    layer-scoped, 30%-coverage outputs/layers/unit_layers.csv, so this gate is added at no
    extra data-collection cost (STABLE_CRITERION_VERSION bumped from a presence+KS-only v1).
    Still approximates spec's fuller stable definition: FR<100Hz-at-any-1s has no existing
    primitive in this repo and is NOT implemented here -- see STABLE_CRITERION_VERSION in the
    caller's manifest for which version backs a given run. One known data-quality caveat: at
    least one subject (C31o) has units with snr==inf (near-zero-noise denominator in the
    upstream Kilosort/curation computation) -- these pass snr>0.5 trivially; flagged, not
    corrected here (upstream of this repo). 'unstable' here means "not certified stable by
    presence+snr", not specifically "died mid-session" (no such detector exists in this repo);
    that finer distinction is deferred, not built here.
    """
    q = pd.to_numeric(quality, errors="coerce")
    presence = pd.to_numeric(trial_presence_fraction, errors="coerce")
    snr_num = pd.to_numeric(snr, errors="coerce")
    tier = pd.Series("unstable", index=quality.index, dtype=object)
    tier[q == 0] = "mua"
    stable_mask = (q == 1) & (presence > presence_threshold) & (snr_num > snr_threshold)
    tier[stable_mask] = "stable"
    unstable_mask = (q == 1) & ~stable_mask
    tier[unstable_mask] = "unstable"
    return tier


def compare_old_new_criteria(
    new_df: pd.DataFrame,
    old_df: pd.DataFrame,
    new_key: Tuple[str, str] = ("session", "unit_row"),
    old_key: Tuple[str, str] = ("session_prefix", "unit_row_idx"),
    class_col_new: str = "is_omission_inclusion_new",
    class_col_old: str = "is_Oplus",
) -> pd.DataFrame:
    """
    Old-vs-new unit-inclusion comparison, joined on the identity key convention already used by
    context/figures/fig03_unit_census/fig03_unit_census.py::attach_legacy() ((session,unit_row)
    <-> (session_prefix,unit_row_idx)). A unit in new_df absent from old_df (old pipeline never
    screened it, e.g. it failed old_df's own upstream quality/rate filter) is 'gained' with
    old_screened=False, kept distinct from a unit the old test actually scored and rejected.
    """
    new_s, new_u = new_key
    old_s, old_u = old_key
    old_small = old_df[[old_s, old_u, class_col_old]].rename(
        columns={old_s: new_s, old_u: new_u, class_col_old: "_old_class"}
    )
    merged = new_df.merge(old_small, on=[new_s, new_u], how="left")
    merged["old_screened"] = merged["_old_class"].notna()
    merged["_old_class"] = merged["_old_class"].astype("boolean").fillna(False).astype(bool)
    new_class = merged[class_col_new].astype(bool)
    old_class = merged["_old_class"].astype(bool)

    def _transition(row_new: bool, row_old: bool, screened: bool) -> str:
        if not screened:
            return "gained" if row_new else "unchanged_excluded"
        if row_new and not row_old:
            return "gained"
        if row_old and not row_new:
            return "lost"
        if row_new and row_old:
            return "unchanged_included"
        return "unchanged_excluded"

    merged["transition"] = [
        _transition(bool(n), bool(o), bool(s))
        for n, o, s in zip(new_class, old_class, merged["old_screened"])
    ]
    merged = merged.drop(columns=["_old_class"])
    return merged


def old_new_summary_table(
    compared: pd.DataFrame,
    group_cols: Tuple[str, ...] = ("area", "quality_tier"),
) -> pd.DataFrame:
    """Explicit gained/lost/unchanged counts per class per area per quality tier."""
    cols = list(group_cols) + ["transition"]
    summary = compared.groupby(cols).size().reset_index(name="n_units")
    return summary
