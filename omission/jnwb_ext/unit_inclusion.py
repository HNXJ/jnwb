r"""
S1 (analysis_spec_SPK.md): likelihood-of-firing unit-inclusion criterion.

Replaces fixation-baseline-contrast selection with P(unit fires | omission) vs
P(unit fires | immediately pre-omission baseline). The bug this fixes: the old
template-correlation O+ classifier (scripts/archive_oneoff/find_all_s_and_o_units.py) scores a
unit against a template that is zero at the fx epoch, so a unit that fires strongly during BOTH
fixation and omission correlates poorly with the template and can be rejected despite a genuine
omission response. omission.jnwb_ext.unit_classification's own O+ path does not use fx and is not the buggy
mechanism -- this module does not replace it, only adds a second, independent criterion
alongside it.

Corrected criterion (Hamm, 2026-08-17): a unit is accepted as omission-responsive if it fires
more during the omission slot than during the immediately-preceding pre-omission window --
fixation firing is simply not part of the comparison at all, at any amplitude, which is the
direct fix (not a fx-inclusive random-timeline null, which was the first-pass design here and
is superseded).

Baseline window, v2 (duration-matched, Hamm 2026-08-17): the first cut used
omission.jnwb_ext.unit_classification's own OM_BASE_LEAD_MS/OM_BASE_GAP_MS (250ms window ending 50ms before
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

from omission.jnwb_ext.unit_classification import (
    OM_BASE_GAP_MS,
    SLOT_WINDOW_MS,
    _rate_in_window,  # noqa: F401 -- imported for reuse/reference by callers, not used directly here
    omission_events,
)
from jnwb.statistics import fires_in_window, fire_indicator, paired_fire_prob_test
from jnwb.metadata import assign_quality_tier, compare_old_new_criteria, old_new_summary_table

# fires_in_window, fire_indicator, paired_fire_prob_test PROMOTED 2026-08-23 to jnwb.statistics;
# assign_quality_tier, compare_old_new_criteria, old_new_summary_table PROMOTED 2026-08-23 to
# jnwb.metadata (99%-jnwb-sufficiency normalization) -- re-imported here under their original
# names so no call site in this module or its callers needs to change.

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
