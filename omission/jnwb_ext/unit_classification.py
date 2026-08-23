"""
Shuffle-controlled unit classification: S+, S-, O+.

Definitions (p1-relative timing from ``omission.jnwb_ext.sequence_layout``):

**Stimulus-present coding (S+ / S-)**
  Pool firing in every (condition, slot) among the 12 GLO conditions where the
  slot letter is a real stimulus (not ``X``), e.g. p1 of any trial; p2 of
  RRRR/RRXR/RRRX; p3 of RRRR/RXRR/RRRX; …
  Compare each trial's present-slot rate to that trial's fx baseline
  ``[-500, 0]`` ms. Sign of the mean difference → S+ (excited) or S-
  (inhibited). Significance via label-shuffle null (random shuffle controlled).

**Omission coding (O+)**
  Pool firing in omission slots only: p2 of *X**, p3 of **X*, p4 of ***X
  (A/B/R families). Require significant elevation vs (1) the same trial's
  local pre-omission baseline and (2) the matched control condition's same
  slot (AAAB/BBBA/RRRR). Both tests shuffle-controlled.

Prevalence targets under honest FP control (session-level BH-FDR on shuffle
p-values): S+ ~35%, S- ~15%, O+ <1% (enriched in FEF/PFC). These are
expected operating points, not hard quotas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from scipy.stats import false_discovery_control

from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS, FULL_SEQUENCE_END_MS
from jnwb.statistics import (
    rate_in_window as _rate_in_window,
    shuffle_pvalue_paired as _shuffle_pvalue_paired,
    shuffle_pvalue_unpaired as _shuffle_pvalue_unpaired,
)

# _rate_in_window, _shuffle_pvalue_paired, _shuffle_pvalue_unpaired PROMOTED 2026-08-23 to
# jnwb.statistics (as public rate_in_window/shuffle_pvalue_paired/shuffle_pvalue_unpaired;
# 99%-jnwb-sufficiency normalization) -- re-imported here under their original private names so
# no call site in this module or its callers needs to change.

log = logging.getLogger(__name__)

# 12 GLO conditions: 4-letter codes; X = omission at that presentation slot.
GLO_CONDITIONS: Tuple[str, ...] = (
    "AAAB", "AXAB", "AAXB", "AAAX",
    "BBBA", "BXBA", "BBXA", "BBBX",
    "RRRR", "RXRR", "RRXR", "RRRX",
)

CONTROL_CONDITION: Dict[str, str] = {
    "A": "AAAB",
    "B": "BBBA",
    "R": "RRRR",
}

PRESENTATION_DUR_MS = 531.0
DELAY_DUR_MS = 500.0
BASELINE_MS: Tuple[float, float] = (-500.0, 0.0)
# Local pre-omission baseline: 200 ms ending 50 ms before omission onset
OM_BASE_LEAD_MS = 250.0
OM_BASE_GAP_MS = 50.0

SLOT_WINDOW_MS: Dict[int, Tuple[float, float]] = {
    1: (EPOCH_ONSETS_MS["p1"], EPOCH_ONSETS_MS["p1"] + PRESENTATION_DUR_MS),
    2: (EPOCH_ONSETS_MS["p2"], EPOCH_ONSETS_MS["p2"] + PRESENTATION_DUR_MS),
    3: (EPOCH_ONSETS_MS["p3"], EPOCH_ONSETS_MS["p3"] + PRESENTATION_DUR_MS),
    4: (EPOCH_ONSETS_MS["p4"], EPOCH_ONSETS_MS["p4"] + PRESENTATION_DUR_MS),
}

# Delay epochs used to reject fatigue / non-selective elevation
DELAY_WINDOW_MS: Dict[str, Tuple[float, float]] = {
    "d1": (EPOCH_ONSETS_MS["d1"], EPOCH_ONSETS_MS["d1"] + DELAY_DUR_MS),
    "d2": (EPOCH_ONSETS_MS["d2"], EPOCH_ONSETS_MS["d2"] + DELAY_DUR_MS),
    "d3": (EPOCH_ONSETS_MS["d3"], EPOCH_ONSETS_MS["d3"] + DELAY_DUR_MS),
    "d4": (EPOCH_ONSETS_MS["d4"], min(EPOCH_ONSETS_MS["d4"] + DELAY_DUR_MS, FULL_SEQUENCE_END_MS)),
}

METHOD_ID = "shuffle_controlled_sso_v2_omit_vs_delay"
OPLUSPLUS_METHOD_ID = "o_plusplus_random_control_nested_v1"

# R-family omission conditions (random-control topology)
R_FAMILY_OMISSIONS: Tuple[Tuple[str, int], ...] = (
    ("RXRR", 2),
    ("RRXR", 3),
    ("RRRX", 4),
)


@dataclass(frozen=True)
class ClassificationConfig:
    n_shuffles: int = 2000
    alpha: float = 0.05
    # O+ must survive stricter FDR (user: p < 0.01 corrected)
    alpha_omission: float = 0.01
    min_trials: int = 8
    min_stim_events: int = 20
    min_omission_events: int = 8
    seed: int = 42
    apply_fdr: bool = True
    # Soft effect floors (Hz) to avoid tiny-rate noise calling significance
    min_abs_stim_effect_hz: float = 0.5
    min_omission_effect_hz: float = 2.0
    # S- requires measurable baseline activity (cannot inhibit silence)
    min_baseline_for_s_minus_hz: float = 3.5
    # S+ requires measurable stimulus-driven rate
    min_stim_rate_for_s_plus_hz: float = 0.5
    # Nested O++ (stricter random-control robust subset of inclusive O+)
    min_omission_effect_hz_plusplus: float = 4.0
    min_omission_events_plusplus: int = 12
    min_r_family_slots_plusplus: int = 2
    alpha_omission_plusplus: float = 0.01


@dataclass(frozen=True)
class OPlusPlusTemplateConfig:
    """O++ census from R-family template-correlation table (grand_oplus_units.csv)."""

    min_mean_correlation: float = 0.60
    max_permutation_pval: float = 0.05
    higher_order_areas: Tuple[str, ...] = ("FEF", "PFC")
    require_higher_order: bool = True


def family_of(condition: str) -> str:
    return condition[0] if condition[0] != "X" else condition[1]


def slot_is_omission(condition: str, slot: int) -> bool:
    return condition[slot - 1] == "X"


def slot_is_stimulus(condition: str, slot: int) -> bool:
    return condition[slot - 1] != "X"


def stimulus_present_events() -> List[Tuple[str, int]]:
    """All (condition, slot) with a present stimulus."""
    return [
        (cond, slot)
        for cond in GLO_CONDITIONS
        for slot in (1, 2, 3, 4)
        if slot_is_stimulus(cond, slot)
    ]


def omission_events() -> List[Tuple[str, int]]:
    """All (condition, slot) that are omissions."""
    return [
        (cond, slot)
        for cond in GLO_CONDITIONS
        for slot in (1, 2, 3, 4)
        if slot_is_omission(cond, slot)
    ]


def _paired_mean_diff(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return float(np.mean(a[:n] - b[:n]))


def precompute_condition_onsets(session, correct_only: bool = True) -> Dict[str, np.ndarray]:
    """p1-aligned trial onsets (seconds) per condition name."""
    out: Dict[str, np.ndarray] = {}
    for cond in GLO_CONDITIONS:
        epochs = session.get_epochs(phase=2, condition=cond, correct_only=correct_only)
        if epochs is None or len(epochs) == 0:
            out[cond] = np.array([], dtype=float)
        else:
            out[cond] = np.asarray(epochs["start_time"].values, dtype=float)
    return out


def _collect_stim_and_baseline_rates(
    spike_times: np.ndarray,
    onsets: Dict[str, np.ndarray],
) -> Tuple[np.ndarray, np.ndarray]:
    """Paired present-stimulus rates and fx baselines (one pair per trial×slot)."""
    stim_rates: List[float] = []
    base_rates: List[float] = []
    st = np.sort(np.asarray(spike_times, dtype=float))
    for cond, slot in stimulus_present_events():
        trials = onsets.get(cond, np.array([]))
        win = SLOT_WINDOW_MS[slot]
        for onset in trials:
            stim_rates.append(_rate_in_window(st, float(onset), win))
            base_rates.append(_rate_in_window(st, float(onset), BASELINE_MS))
    return np.asarray(stim_rates, dtype=float), np.asarray(base_rates, dtype=float)


def _collect_omission_rates(
    spike_times: np.ndarray,
    onsets: Dict[str, np.ndarray],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (omission_rates, local_baseline_rates, control_slot_rates, delay_mean_rates).

    local_baseline: [omit_onset - 250, omit_onset - 50] ms
    control_slot: same slot window on the family control condition (unpaired)
    delay_mean: mean rate across d1–d4 on the *same* omission trial (anti-fatigue)
    """
    om_rates: List[float] = []
    om_base: List[float] = []
    ctrl_rates: List[float] = []
    delay_means: List[float] = []
    st = np.sort(np.asarray(spike_times, dtype=float))

    for cond, slot in omission_events():
        trials = onsets.get(cond, np.array([]))
        if len(trials) == 0:
            continue
        win = SLOT_WINDOW_MS[slot]
        omit_start = win[0]
        base_win = (omit_start - OM_BASE_LEAD_MS, omit_start - OM_BASE_GAP_MS)
        fam = family_of(cond)
        ctrl_cond = CONTROL_CONDITION[fam]
        ctrl_trials = onsets.get(ctrl_cond, np.array([]))

        for onset in trials:
            onset_f = float(onset)
            om_rates.append(_rate_in_window(st, onset_f, win))
            om_base.append(_rate_in_window(st, onset_f, base_win))
            d_rates = [
                _rate_in_window(st, onset_f, DELAY_WINDOW_MS[d])
                for d in ("d1", "d2", "d3", "d4")
            ]
            delay_means.append(float(np.mean(d_rates)))

        if len(ctrl_trials) > 0:
            rng_local = np.random.default_rng(abs(hash((cond, slot))) % (2**31))
            idx = rng_local.choice(
                len(ctrl_trials), size=len(trials), replace=len(ctrl_trials) < len(trials)
            )
            for onset in ctrl_trials[idx]:
                ctrl_rates.append(_rate_in_window(st, float(onset), win))

    return (
        np.asarray(om_rates, dtype=float),
        np.asarray(om_base, dtype=float),
        np.asarray(ctrl_rates, dtype=float),
        np.asarray(delay_means, dtype=float),
    )


def _collect_r_family_omission_slot_rates(
    spike_times: np.ndarray,
    onsets: Dict[str, np.ndarray],
) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
    """Per R-family omission slot → (omission_rates, RRRR control_slot_rates)."""
    st = np.sort(np.asarray(spike_times, dtype=float))
    out: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
    ctrl_trials = onsets.get("RRRR", np.array([]))
    for cond, slot in R_FAMILY_OMISSIONS:
        trials = onsets.get(cond, np.array([]))
        if len(trials) == 0 or len(ctrl_trials) == 0:
            out[slot] = (np.array([], dtype=float), np.array([], dtype=float))
            continue
        win = SLOT_WINDOW_MS[slot]
        om = np.asarray(
            [_rate_in_window(st, float(onset), win) for onset in trials], dtype=float
        )
        rng_local = np.random.default_rng(abs(hash((cond, slot, "R"))) % (2**31))
        idx = rng_local.choice(
            len(ctrl_trials), size=len(trials), replace=len(ctrl_trials) < len(trials)
        )
        ctrl = np.asarray(
            [_rate_in_window(st, float(onset), win) for onset in ctrl_trials[idx]],
            dtype=float,
        )
        out[slot] = (om, ctrl)
    return out


def classify_unit(
    spike_times: np.ndarray,
    onsets: Dict[str, np.ndarray],
    cfg: ClassificationConfig,
    rng: np.random.Generator,
) -> Dict:
    """Classify one unit; returns raw p-values (FDR applied at session level)."""
    stim, base = _collect_stim_and_baseline_rates(spike_times, onsets)
    om, om_base, ctrl, delay_mean = _collect_omission_rates(spike_times, onsets)
    r_slots = _collect_r_family_omission_slot_rates(spike_times, onsets)

    result = {
        "n_stim_events": int(len(stim)),
        "n_omission_events": int(len(om)),
        "mean_stim_hz": float(np.mean(stim)) if len(stim) else np.nan,
        "mean_baseline_hz": float(np.mean(base)) if len(base) else np.nan,
        "mean_omission_hz": float(np.mean(om)) if len(om) else np.nan,
        "mean_omission_baseline_hz": float(np.mean(om_base)) if len(om_base) else np.nan,
        "mean_control_slot_hz": float(np.mean(ctrl)) if len(ctrl) else np.nan,
        "mean_delay_hz": float(np.mean(delay_mean)) if len(delay_mean) else np.nan,
        "stim_effect_hz": np.nan,
        "p_stim_shuffle": 1.0,
        "p_s_plus_shuffle": 1.0,
        "p_s_minus_shuffle": 1.0,
        "om_vs_base_effect_hz": np.nan,
        "p_om_vs_base_shuffle": 1.0,
        "om_vs_ctrl_effect_hz": np.nan,
        "p_om_vs_ctrl_shuffle": 1.0,
        "om_vs_delay_effect_hz": np.nan,
        "p_om_vs_delay_shuffle": 1.0,
        "n_r_family_omission_events": 0,
        "n_r_family_slots_sig": 0,
        "r_family_om_vs_ctrl_effect_hz": np.nan,
        "p_r_family_om_vs_ctrl_shuffle": 1.0,
    }

    if len(stim) >= cfg.min_stim_events:
        n = min(len(stim), len(base))
        diff = np.asarray(stim[:n], dtype=float) - np.asarray(base[:n], dtype=float)
        obs = float(np.mean(diff))
        flips = rng.choice(np.array([-1.0, 1.0]), size=(cfg.n_shuffles, n))
        null = flips @ diff / n
        p_two = (1.0 + np.sum(np.abs(null) >= abs(obs))) / (cfg.n_shuffles + 1.0)
        p_pos = (1.0 + np.sum(null >= obs)) / (cfg.n_shuffles + 1.0)
        p_neg = (1.0 + np.sum(null <= obs)) / (cfg.n_shuffles + 1.0)
        result["stim_effect_hz"] = obs
        result["p_stim_shuffle"] = float(p_two)
        result["p_s_plus_shuffle"] = float(p_pos)
        result["p_s_minus_shuffle"] = float(p_neg)

    if len(om) >= cfg.min_omission_events and len(om_base) >= cfg.min_omission_events:
        eff_b, p_b = _shuffle_pvalue_paired(om, om_base, cfg.n_shuffles, rng, alternative="greater")
        result["om_vs_base_effect_hz"] = eff_b
        result["p_om_vs_base_shuffle"] = p_b

    if len(om) >= cfg.min_omission_events and len(ctrl) >= cfg.min_omission_events:
        eff_c, p_c = _shuffle_pvalue_unpaired(om, ctrl, cfg.n_shuffles, rng, alternative="greater")
        result["om_vs_ctrl_effect_hz"] = eff_c
        result["p_om_vs_ctrl_shuffle"] = p_c

    # Anti-fatigue: omission px must exceed mean(d1..d4) on the same trials
    if len(om) >= cfg.min_omission_events and len(delay_mean) >= cfg.min_omission_events:
        eff_d, p_d = _shuffle_pvalue_paired(
            om, delay_mean, cfg.n_shuffles, rng, alternative="greater"
        )
        result["om_vs_delay_effect_hz"] = eff_d
        result["p_om_vs_delay_shuffle"] = p_d

    # Random-control (R-family) nested metrics for O++
    r_om_all: List[float] = []
    r_ctrl_all: List[float] = []
    n_slots_sig = 0
    for slot, (om_s, ctrl_s) in r_slots.items():
        if len(om_s) < cfg.min_trials or len(ctrl_s) < cfg.min_trials:
            continue
        r_om_all.extend(om_s.tolist())
        r_ctrl_all.extend(ctrl_s.tolist())
        eff_s, p_s = _shuffle_pvalue_unpaired(
            om_s, ctrl_s, cfg.n_shuffles, rng, alternative="greater"
        )
        if (
            p_s < cfg.alpha_omission_plusplus
            and eff_s >= cfg.min_omission_effect_hz_plusplus
        ):
            n_slots_sig += 1
    result["n_r_family_omission_events"] = int(len(r_om_all))
    result["n_r_family_slots_sig"] = int(n_slots_sig)
    if len(r_om_all) >= cfg.min_omission_events_plusplus and len(r_ctrl_all) >= cfg.min_omission_events_plusplus:
        eff_r, p_r = _shuffle_pvalue_unpaired(
            np.asarray(r_om_all, dtype=float),
            np.asarray(r_ctrl_all, dtype=float),
            cfg.n_shuffles,
            rng,
            alternative="greater",
        )
        result["r_family_om_vs_ctrl_effect_hz"] = eff_r
        result["p_r_family_om_vs_ctrl_shuffle"] = p_r

    return result


def _assign_labels(df: pd.DataFrame, cfg: ClassificationConfig) -> pd.DataFrame:
    """Apply FDR + effect floors → boolean flags and display_class."""
    out = df.copy()

    def _q(col: str) -> np.ndarray:
        if col not in out.columns:
            return np.ones(len(out), dtype=float)
        p = out[col].to_numpy(dtype=float)
        if not cfg.apply_fdr:
            return p
        # NaN-safe: only correct finite p
        q = np.ones_like(p)
        mask = np.isfinite(p)
        if mask.sum() == 0:
            return q
        q[mask] = false_discovery_control(p[mask], method="bh")
        return q

    out["q_stim_shuffle"] = _q("p_stim_shuffle")
    out["q_s_plus_shuffle"] = _q("p_s_plus_shuffle")
    out["q_s_minus_shuffle"] = _q("p_s_minus_shuffle")
    out["q_om_vs_base_shuffle"] = _q("p_om_vs_base_shuffle")
    out["q_om_vs_ctrl_shuffle"] = _q("p_om_vs_ctrl_shuffle")
    out["q_om_vs_delay_shuffle"] = _q("p_om_vs_delay_shuffle")
    out["q_r_family_om_vs_ctrl_shuffle"] = _q("p_r_family_om_vs_ctrl_shuffle")

    out["is_s_plus"] = (
        (out["q_s_plus_shuffle"] < cfg.alpha)
        & (out["stim_effect_hz"] >= cfg.min_abs_stim_effect_hz)
        & (out["mean_stim_hz"] >= cfg.min_stim_rate_for_s_plus_hz)
        & (out["n_stim_events"] >= cfg.min_stim_events)
    )
    out["is_s_minus"] = (
        (out["q_s_minus_shuffle"] < cfg.alpha)
        & (out["stim_effect_hz"] <= -cfg.min_abs_stim_effect_hz)
        & (out["mean_baseline_hz"] >= cfg.min_baseline_for_s_minus_hz)
        & (out["n_stim_events"] >= cfg.min_stim_events)
    )

    # Reliable O+: omission px > local baseline AND > control slot AND > mean(d1..d4)
    # all at FDR q < alpha_omission (default 0.01)
    out["is_o_plus"] = (
        (out["q_om_vs_base_shuffle"] < cfg.alpha_omission)
        & (out["q_om_vs_ctrl_shuffle"] < cfg.alpha_omission)
        & (out["q_om_vs_delay_shuffle"] < cfg.alpha_omission)
        & (out["om_vs_base_effect_hz"] >= cfg.min_omission_effect_hz)
        & (out["om_vs_ctrl_effect_hz"] >= cfg.min_omission_effect_hz)
        & (out["om_vs_delay_effect_hz"] >= cfg.min_omission_effect_hz)
        & (out["n_omission_events"] >= cfg.min_omission_events)
    )

    # Nested O++: inclusive O+ + random-control R-family robustness
    has_r = "n_r_family_slots_sig" in out.columns
    if has_r:
        out["is_o_plusplus"] = (
            out["is_o_plus"]
            & (out["n_r_family_slots_sig"] >= cfg.min_r_family_slots_plusplus)
            & (out["n_r_family_omission_events"] >= cfg.min_omission_events_plusplus)
            & (out["q_r_family_om_vs_ctrl_shuffle"] < cfg.alpha_omission_plusplus)
            & (out["r_family_om_vs_ctrl_effect_hz"] >= cfg.min_omission_effect_hz_plusplus)
            & (out["om_vs_base_effect_hz"] >= cfg.min_omission_effect_hz_plusplus)
            & (out["om_vs_ctrl_effect_hz"] >= cfg.min_omission_effect_hz_plusplus)
            & (out["om_vs_delay_effect_hz"] >= cfg.min_omission_effect_hz_plusplus)
        )
    else:
        out["is_o_plusplus"] = False

    def _tier(row) -> str:
        if bool(row.get("is_o_plusplus", False)):
            return "O++"
        if bool(row.get("is_o_plus", False)):
            return "O+"
        return "Null"

    out["o_plus_tier"] = out.apply(_tier, axis=1)

    # Priority: O++ > O+ > S+ > S- > Other
    def _display(row) -> str:
        if row.get("is_o_plusplus", False):
            return "O++"
        if row["is_o_plus"]:
            return "O+"
        if row["is_s_plus"]:
            return "S+"
        if row["is_s_minus"]:
            return "S-"
        return "Other"

    out["display_class"] = out.apply(_display, axis=1)
    return out


def assign_o_plusplus_from_template_table(
    df: pd.DataFrame,
    cfg: Optional[OPlusPlusTemplateConfig] = None,
) -> pd.DataFrame:
    """
    Mark nested O++ on an R-family template-correlation table (grand_oplus_units.csv).

    This function does not change the inclusive O+ classification or count on the input
    table -- it only adds an `is_o_plusplus` column marking a robust subset. It does not
    itself assert or depend on any specific inclusive O+ percentage; the manuscript's
    currently-cited inclusive O+ figure lives in context/docs/CONTEXT.md, not here (the
    421/8597=4.90% figure previously referenced at this line is retracted synthetic data
    per CONTEXT.md Section 8 -- see artifacts/.lab/agent-harness-audit-20260810.json,
    claim-p0-stale-census-in-executable-code -- removed 2026-08-10, do not restore it here).
    Default: FEF/PFC with mean_correlation >= 0.60 and permutation_pval <= 0.05
    (operating target ~40 units; random-control templates RXRR/RRXR/RRRX).
    """
    cfg = cfg or OPlusPlusTemplateConfig()
    out = df.copy()
    corr = out["mean_correlation"].astype(float)
    pval = out["permutation_pval"].astype(float)
    area_ok = out["area"].isin(cfg.higher_order_areas) if cfg.require_higher_order else True
    out["is_o_plusplus"] = (
        (corr >= cfg.min_mean_correlation)
        & (pval <= cfg.max_permutation_pval)
        & area_ok
    )
    out["o_plus_tier"] = np.where(out["is_o_plusplus"], "O++", "O+")
    return out


def oplusplus_census_summary(df: pd.DataFrame) -> Dict:
    """Summarize an O++-labeled template table."""
    n = int(df["is_o_plusplus"].sum()) if "is_o_plusplus" in df.columns else 0
    sub = df[df["is_o_plusplus"]] if n else df.iloc[0:0]
    areas = sub["area"].value_counts().to_dict() if n else {}
    fef_pfc = int(sub["area"].isin(["FEF", "PFC"]).sum()) if n else 0
    return {
        "n_o_plusplus": n,
        "n_candidates": int(len(df)),
        "fef_pfc_n": fef_pfc,
        "fef_pfc_frac": float(fef_pfc / n) if n else 0.0,
        "area_counts": {str(k): int(v) for k, v in areas.items()},
        "mean_correlation_median": float(sub["mean_correlation"].median()) if n else None,
        "method": OPLUSPLUS_METHOD_ID,
    }


def classify_session_units(
    session,
    cfg: Optional[ClassificationConfig] = None,
    unit_ids: Optional[Sequence[int]] = None,
    correct_only: bool = True,
) -> pd.DataFrame:
    """
    Classify all (or selected) units in a session.

    Returns a DataFrame indexed by unit_id with shuffle p/q values and
    ``display_class`` in {O+, S+, S-, Null}.
    """
    cfg = cfg or ClassificationConfig()
    onsets = precompute_condition_onsets(session, correct_only=correct_only)
    for cond, arr in onsets.items():
        log.info("onsets %s: n=%d", cond, len(arr))

    units_df = session._units_df
    if unit_ids is None:
        unit_ids = list(units_df.index)

    rows = []
    rng_root = np.random.default_rng(cfg.seed)
    for i, uid in enumerate(unit_ids):
        uid_i = int(uid)
        spikes = session.get_spike_times(uid_i)
        if spikes is None or len(spikes) == 0:
            continue
        # Independent stream per unit for reproducibility
        rng = np.random.default_rng(rng_root.integers(0, 2**31 - 1))
        metrics = classify_unit(spikes, onsets, cfg, rng)
        area = units_df.loc[uid_i].get("area", "") if uid_i in units_df.index else ""
        layer = units_df.loc[uid_i].get("layer", "") if uid_i in units_df.index else ""
        fr = units_df.loc[uid_i].get("firing_rate", np.nan) if uid_i in units_df.index else np.nan
        metrics.update(
            {
                "unit_id": uid_i,
                "area": area,
                "layer": layer,
                "firing_rate": float(fr) if fr == fr else np.nan,
            }
        )
        rows.append(metrics)
        if (i + 1) % 50 == 0:
            log.info("classified %d / %d units", i + 1, len(unit_ids))

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = _assign_labels(df, cfg)
    df = df.set_index("unit_id").sort_index()
    return df


def prevalence_summary(df: pd.DataFrame) -> Dict[str, float]:
    """Fraction of classified units in each display class."""
    n = len(df)
    if n == 0:
        return {}
    # Accept legacy "Null" as Other
    cls = df["display_class"].replace({"Null": "Other"})
    counts = cls.value_counts()
    out = {k: float(counts.get(k, 0)) / n for k in ("S+", "S-", "O+", "Other")}
    out["n_units"] = float(n)
    out["n_S+"] = float(counts.get("S+", 0))
    out["n_S-"] = float(counts.get("S-", 0))
    out["n_O+"] = float(counts.get("O+", 0))
    out["n_Other"] = float(counts.get("Other", 0))
    return out


def config_to_dict(cfg: ClassificationConfig) -> Dict:
    return {
        "n_shuffles": cfg.n_shuffles,
        "alpha": cfg.alpha,
        "alpha_omission": cfg.alpha_omission,
        "min_trials": cfg.min_trials,
        "min_stim_events": cfg.min_stim_events,
        "min_omission_events": cfg.min_omission_events,
        "seed": cfg.seed,
        "apply_fdr": cfg.apply_fdr,
        "min_abs_stim_effect_hz": cfg.min_abs_stim_effect_hz,
        "min_omission_effect_hz": cfg.min_omission_effect_hz,
        "min_baseline_for_s_minus_hz": cfg.min_baseline_for_s_minus_hz,
        "min_stim_rate_for_s_plus_hz": cfg.min_stim_rate_for_s_plus_hz,
        "min_omission_effect_hz_plusplus": cfg.min_omission_effect_hz_plusplus,
        "min_omission_events_plusplus": cfg.min_omission_events_plusplus,
        "min_r_family_slots_plusplus": cfg.min_r_family_slots_plusplus,
        "alpha_omission_plusplus": cfg.alpha_omission_plusplus,
        "method": METHOD_ID,
        "oplusplus_method": OPLUSPLUS_METHOD_ID,
        "glo_conditions": list(GLO_CONDITIONS),
    }


def config_from_dict(d: Dict) -> ClassificationConfig:
    keys = {
        "n_shuffles",
        "alpha",
        "alpha_omission",
        "min_trials",
        "min_stim_events",
        "min_omission_events",
        "seed",
        "apply_fdr",
        "min_abs_stim_effect_hz",
        "min_omission_effect_hz",
        "min_baseline_for_s_minus_hz",
        "min_stim_rate_for_s_plus_hz",
        "min_omission_effect_hz_plusplus",
        "min_omission_events_plusplus",
        "min_r_family_slots_plusplus",
        "alpha_omission_plusplus",
    }
    return ClassificationConfig(**{k: d[k] for k in keys if k in d})


def discover_nwb_paths(nwb_root: Union[str, Path]) -> List[Path]:
    root = Path(nwb_root)
    return sorted(root.glob("*.nwb"))


def _git_sha(repo_root: Path) -> str:
    try:
        import subprocess

        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def classify_nwb_file(
    nwb_path: Union[str, Path],
    cfg: Optional[ClassificationConfig] = None,
    context: str = "omission_glo_passive",
    unit_ids: Optional[Sequence[int]] = None,
) -> pd.DataFrame:
    """Load one NWB, classify units, attach session provenance columns."""
    from omission import read

    cfg = cfg or ClassificationConfig()
    nwb_path = Path(nwb_path)
    session = read(str(nwb_path), context=context)
    df = classify_session_units(session, cfg=cfg, unit_ids=unit_ids)
    if df.empty:
        return df
    df = df.reset_index()
    df.insert(0, "nwb_path", str(nwb_path.resolve()))
    df.insert(1, "nwb_stem", nwb_path.stem)
    df.insert(2, "session_id", nwb_path.stem)
    # Normalize legacy Null
    df["display_class"] = df["display_class"].replace({"Null": "Other"})
    return df


def append_session_to_grand_table(
    session_df: pd.DataFrame,
    grand_path: Union[str, Path],
    cfg: ClassificationConfig,
    repo_root: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Append/replace one session's rows in the grand unit table.

    Reproducibility: rows for the same ``nwb_stem`` are replaced so re-runs
    are idempotent. Writes atomic CSV + sidecar config JSON next to the table.
    """
    import json
    from datetime import datetime, timezone

    grand_path = Path(grand_path)
    grand_path.parent.mkdir(parents=True, exist_ok=True)
    repo_root = repo_root or Path(__file__).resolve().parents[1]

    session_df = session_df.copy()
    if "nwb_stem" not in session_df.columns:
        raise ValueError("session_df must include nwb_stem")
    stem = str(session_df["nwb_stem"].iloc[0])
    session_df["classified_at_utc"] = datetime.now(timezone.utc).isoformat()
    session_df["git_sha"] = _git_sha(repo_root)
    session_df["method"] = METHOD_ID
    for k, v in config_to_dict(cfg).items():
        if k in ("glo_conditions", "method"):
            continue
        session_df[f"cfg_{k}"] = v

    if grand_path.is_file():
        grand = pd.read_csv(grand_path)
        grand = grand[grand["nwb_stem"] != stem]
        grand = pd.concat([grand, session_df], ignore_index=True)
    else:
        grand = session_df

    tmp = grand_path.with_suffix(".csv.tmp")
    grand.to_csv(tmp, index=False)
    tmp.replace(grand_path)

    meta = {
        "grand_table": str(grand_path.resolve()),
        "last_session": stem,
        "n_rows": int(len(grand)),
        "n_sessions": int(grand["nwb_stem"].nunique()),
        "git_sha": _git_sha(repo_root),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config_to_dict(cfg),
        "prevalence_overall": prevalence_summary(
            grand.rename(columns={"display_class": "display_class"})
            if "display_class" in grand.columns
            else grand
        ),
    }
    # prevalence_summary expects display_class column
    if "display_class" in grand.columns:
        meta["prevalence_overall"] = prevalence_summary(grand)

    meta_path = grand_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return grand


def classify_all_nwbs(
    nwb_root: Union[str, Path],
    grand_path: Union[str, Path],
    cfg: Optional[ClassificationConfig] = None,
    context: str = "omission_glo_passive",
    per_session_dir: Optional[Union[str, Path]] = None,
    max_files: Optional[int] = None,
) -> pd.DataFrame:
    """
    Walk all ``*.nwb`` under ``nwb_root``, classify, write per-session CSV,
    and append into the grand table.
    """
    import json

    cfg = cfg or ClassificationConfig()
    nwb_paths = discover_nwb_paths(nwb_root)
    if max_files is not None:
        nwb_paths = nwb_paths[: max_files]
    per_session_dir = Path(per_session_dir) if per_session_dir else Path(grand_path).parent / "per_session"
    per_session_dir.mkdir(parents=True, exist_ok=True)

    # Freeze config once for the run
    run_cfg_path = Path(grand_path).parent / "classification_config_freeze.json"
    run_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    run_cfg_path.write_text(json.dumps(config_to_dict(cfg), indent=2), encoding="utf-8")

    grand = pd.DataFrame()
    for i, path in enumerate(nwb_paths, start=1):
        log.info("[%d/%d] classifying %s", i, len(nwb_paths), path.name)
        try:
            session_df = classify_nwb_file(path, cfg=cfg, context=context)
        except Exception as e:
            log.exception("FAILED %s: %s", path.name, e)
            continue
        if session_df.empty:
            log.warning("No units classified for %s", path.name)
            continue
        session_csv = per_session_dir / f"{path.stem}_shuffle_class.csv"
        session_df.to_csv(session_csv, index=False)
        prev = prevalence_summary(session_df)
        (per_session_dir / f"{path.stem}_prevalence.json").write_text(
            json.dumps(prev, indent=2), encoding="utf-8"
        )
        log.info("  %s prevalence %s", path.stem, prev)
        grand = append_session_to_grand_table(session_df, grand_path, cfg)

    return grand
