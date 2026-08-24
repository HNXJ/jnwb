"""
Statistical Analysis Module: Parametric + Non-parametric + family-wise FDR

API Layers
----------
**Exploratory** (``exploratory_compare``, ``exploratory_correlate``, ``exploratory_multi``):
    Dual parametric + non-parametric reporting for pilot analysis.
    Returns raw p-values only.  No q-values, no FDR correction applied.
    Use freely during exploration; do not cite these p-values as confirmatory.

**Confirmatory** (``confirmatory_compare``):
    Requires an explicit hypothesis string and alpha level.
    Returns BH-adjusted q-values suitable for cross-hypothesis family correction.
    Use StatisticalAnalysis.fdr_correct() on a *collection* of confirmatory p-values
    when testing many hypotheses (units / channels / frequencies / time bins).

**Legacy** (``compare_groups``, ``compare_multiple_groups``, ``correlate``):
    Still functional; emit DeprecationWarnings on the ``fdr_pval_*`` output keys.
    Migrate to exploratory_* or confirmatory_* as appropriate.

Author: Claude Code
Date: 2025-06-24
Revised: 2026-07-26 — Exploratory / Confirmatory API split
"""

from __future__ import annotations

import logging
import warnings
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats

from .permutation import permute_labels

log = logging.getLogger(__name__)


def clopper_pearson(k, n, alpha: float = 0.05):
    """Exact (Clopper-Pearson) binomial confidence interval via the Beta-quantile form.

    Promoted 2026-08-14 from six byte-identical independent implementations
    (``context/figures/figstyle.py`` and five ``scripts/*.py`` aggregation scripts) --
    proportions on this project get this, never a bootstrap.
    """
    k, n = int(k), int(n)
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def fires_in_window(spike_times: np.ndarray, onset_s: float, window_ms) -> bool:
    """True iff >=1 spike falls in [onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000).

    PROMOTED 2026-08-23 from omission.jnwb_ext.unit_inclusion (99%-jnwb-sufficiency
    normalization): pure spike-array/searchsorted arithmetic on an arbitrary onset and window,
    no session or condition coupling.
    """
    t0 = onset_s + window_ms[0] / 1000.0
    t1 = onset_s + window_ms[1] / 1000.0
    if t1 <= t0:
        return False
    n = int(np.searchsorted(spike_times, t1, side="right") - np.searchsorted(spike_times, t0, side="left"))
    return n > 0


def fire_indicator(spike_times: np.ndarray, onsets_s: np.ndarray, window_ms) -> np.ndarray:
    """Vectorized boolean fire indicator, one entry per onset, constant window.

    PROMOTED 2026-08-23 alongside ``fires_in_window`` (see its docstring).
    """
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
    """Paired binary test: P(fire | target window) vs P(fire | paired baseline window).

    PROMOTED 2026-08-23 from omission.jnwb_ext.unit_inclusion (99%-jnwb-sufficiency
    normalization): a fully generic paired-proportions inferential routine -- two plain boolean
    arrays, an explicit RNG, and shuffle/bootstrap counts in; no session, condition, or
    omission-slot semantics.

    Significance: shuffle-null on which member of each trial's pair counts as "target"
    (sign-flip of the paired difference), alternative="greater" (tests whether the target
    window's fire probability exceeds the paired baseline's). Risk-difference CI: paired
    bootstrap over trials (percentile method) -- distinct RNG draws from the shuffle-null so the
    hypothesis test and the interval don't share randomness. Odds ratio: McNemar-style
    discordant-pair estimator with Haldane-Anscombe continuity correction (avoids div-by-zero
    when one discordant count is 0).

    Args:
        fires_target: (n,) bool array, one entry per paired trial.
        fires_null: (n,) bool array, the paired baseline/control condition.
        n_shuffles: number of sign-flip draws for the shuffle-null p-value.
        n_bootstrap: number of paired-bootstrap draws for the risk-difference CI.
        rng: explicit numpy.random.Generator.

    Returns:
        dict with p_fire_target, p_fire_pre_omission_baseline, risk_difference (+ CI),
        odds_ratio (+ CI), p_value_fire_shuffle, n_trials. All-NaN/p=1.0 when fewer than 2
        paired trials are available.
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


def rate_in_window(spike_times: np.ndarray, onset_s: float, window_ms: Tuple[float, float]) -> float:
    """Firing rate (Hz) in ``[onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000)``.

    PROMOTED 2026-08-23 from omission.jnwb_ext.unit_classification's private
    ``_rate_in_window`` (99%-jnwb-sufficiency normalization): pure spike-array/searchsorted
    arithmetic on an arbitrary onset and window, the rate-valued sibling of
    ``fires_in_window``.
    """
    t0 = onset_s + window_ms[0] / 1000.0
    t1 = onset_s + window_ms[1] / 1000.0
    if t1 <= t0:
        return 0.0
    n = int(np.searchsorted(spike_times, t1, side="right") - np.searchsorted(spike_times, t0, side="left"))
    return n / ((window_ms[1] - window_ms[0]) / 1000.0)


def shuffle_pvalue_paired(
    a: np.ndarray,
    b: np.ndarray,
    n_shuffles: int,
    rng: np.random.Generator,
    alternative: str = "two-sided",
) -> Tuple[float, float]:
    """Shuffle-controlled p-value for ``mean(a - b)`` via paired sign-flips.

    PROMOTED 2026-08-23 from omission.jnwb_ext.unit_classification's private
    ``_shuffle_pvalue_paired`` (99%-jnwb-sufficiency normalization): pure paired-array
    statistics, no session or condition coupling.

    Null: randomly flip the sign of each paired difference (equivalent to swapping a/b labels
    within trial). Returns (observed_diff, p_value).
    """
    n = min(len(a), len(b))
    if n < 2:
        return 0.0, 1.0
    diff = np.asarray(a[:n], dtype=float) - np.asarray(b[:n], dtype=float)
    obs = float(np.mean(diff))
    flips = rng.choice(np.array([-1.0, 1.0]), size=(n_shuffles, n))
    null = flips @ diff / n
    if alternative == "greater":
        p = (1.0 + np.sum(null >= obs)) / (n_shuffles + 1.0)
    elif alternative == "less":
        p = (1.0 + np.sum(null <= obs)) / (n_shuffles + 1.0)
    else:
        p = (1.0 + np.sum(np.abs(null) >= abs(obs))) / (n_shuffles + 1.0)
    return obs, float(p)


def shuffle_pvalue_unpaired(
    a: np.ndarray,
    b: np.ndarray,
    n_shuffles: int,
    rng: np.random.Generator,
    alternative: str = "greater",
) -> Tuple[float, float]:
    """Shuffle-controlled p-value for ``mean(a) - mean(b)`` via label-shuffling.

    PROMOTED 2026-08-23 from omission.jnwb_ext.unit_classification's private
    ``_shuffle_pvalue_unpaired`` (99%-jnwb-sufficiency normalization): pure independent-array
    statistics, no session or condition coupling.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 2 or len(b) < 2:
        return 0.0, 1.0
    obs = float(np.mean(a) - np.mean(b))
    pooled = np.concatenate([a, b])
    n_a = len(a)
    null = np.empty(n_shuffles)
    for i in range(n_shuffles):
        rng.shuffle(pooled)
        null[i] = float(np.mean(pooled[:n_a]) - np.mean(pooled[n_a:]))
    if alternative == "greater":
        p = (1.0 + np.sum(null >= obs)) / (n_shuffles + 1.0)
    elif alternative == "less":
        p = (1.0 + np.sum(null <= obs)) / (n_shuffles + 1.0)
    else:
        p = (1.0 + np.sum(np.abs(null) >= abs(obs))) / (n_shuffles + 1.0)
    return obs, float(p)


def detect_trial_cycles(epochs_df: pd.DataFrame, gap_factor: float = 10.0) -> np.ndarray:
    """Detect temporal cluster ("cycle") boundaries in a trial table via a gap threshold.

    PROMOTED 2026-08-23 from omission.jnwb_ext.omission_identity (99%-jnwb-sufficiency
    normalization): pure temporal-clustering arithmetic on a plain ``start_time`` column, no
    condition or session coupling.

    Sorts ``epochs_df["start_time"]``, flags gaps that exceed ``gap_factor * median(gap)`` as
    cluster boundaries, and returns a 0-indexed integer cluster/cycle id per row, in the
    original row order of ``epochs_df`` (not sorted order).

    Args:
        epochs_df: DataFrame with a ``start_time`` column.
        gap_factor: a gap is a cluster boundary when it exceeds this multiple of the median
            inter-event gap.

    Returns:
        (n_rows,) int array of cycle ids, in ``epochs_df``'s original row order.
    """
    order = np.argsort(epochs_df["start_time"].values)
    t_sorted = epochs_df["start_time"].values[order]
    gaps = np.diff(t_sorted)
    thresh = gap_factor * np.median(gaps) if len(gaps) else np.inf
    breaks = np.where(gaps > thresh)[0]
    cycle_sorted = np.zeros(len(t_sorted), dtype=int)
    for b in breaks:
        cycle_sorted[b + 1:] += 1
    cycle = np.empty(len(order), dtype=int)
    cycle[order] = cycle_sorted
    return cycle


def assign_subblock_quartiles(epochs_df: pd.DataFrame, n_quantiles: int = 4) -> np.ndarray:
    """Assign each row a temporal quantile bucket 0..n_quantiles-1 by its own start_time order.

    PROMOTED 2026-08-23 from omission.jnwb_ext.omission_identity (99%-jnwb-sufficiency
    normalization): pure temporal-ordering/bucketing arithmetic, no condition or session
    coupling.

    Args:
        epochs_df: DataFrame with a ``start_time`` column.
        n_quantiles: number of equal-sized (as equal as possible) temporal buckets.

    Returns:
        (n_rows,) int array of quantile bucket ids, in ``epochs_df``'s original row order.
    """
    order = np.argsort(epochs_df["start_time"].values)
    n = len(order)
    q = np.empty(n, dtype=int)
    edges = np.linspace(0, n, n_quantiles + 1).astype(int)
    for k in range(n_quantiles):
        q[order[edges[k]:edges[k + 1]]] = k
    return q


def shuffle_r2_ci(
    y_true: np.ndarray,
    y_score: np.ndarray,
    groups: Optional[np.ndarray] = None,
    n_shuffle: int = 200,
    random_state: int = 42,
) -> Dict[str, float]:
    """R^2 (squared Pearson correlation) between a continuous score and a 0/1 label, with a
    shuffle-null 95% CI.

    PROMOTED 2026-08-23 from omission.jnwb_ext.omission_identity (99%-jnwb-sufficiency
    normalization): pure array statistics built on the already-generic ``permute_labels``, no
    session or condition coupling.

    The CI is a percentile of the null distribution, not of the estimate -- R^2 has no closed
    form for an exact/analytic CI the way a proportion built from counts does, so a shuffle-null
    percentile CI is used instead. If ``groups`` is given (e.g. a session or cycle id), labels
    are shuffled WITHIN each group (``permute_labels(..., scheme="within_group")``) so the null
    preserves the group structure instead of pooling across it; without ``groups``, a global
    shuffle is used.

    Args:
        y_true: (n,) array, typically a 0/1 label.
        y_score: (n,) array, a continuous decision score.
        groups: optional (n,) group id array for within-group shuffling.
        n_shuffle: number of shuffle draws.
        random_state: seed for the shuffle RNG.

    Returns:
        dict with r2_observed, r2_null_ci_lo, r2_null_ci_hi, r2_null_mean, p_val, n_shuffle.
    """
    def _r2(y, s):
        if np.std(s) == 0 or np.std(y) == 0:
            return 0.0
        r = np.corrcoef(y, s)[0, 1]
        return float(r ** 2)

    r2_obs = _r2(y_true, y_score)
    rng = np.random.default_rng(random_state)
    null = np.empty(n_shuffle)
    scheme = "global" if groups is None else "within_group"
    for i in range(n_shuffle):
        y_perm = permute_labels(y_true, groups=groups, scheme=scheme, rng=rng)
        null[i] = _r2(y_perm, y_score)
    p_val = float(np.mean(null >= r2_obs))
    p_val = p_val if p_val > 0 else 1.0 / (n_shuffle + 1)
    return {
        "r2_observed": r2_obs,
        "r2_null_ci_lo": float(np.percentile(null, 2.5)),
        "r2_null_ci_hi": float(np.percentile(null, 97.5)),
        "r2_null_mean": float(np.mean(null)),
        "p_val": p_val,
        "n_shuffle": n_shuffle,
    }


def coef_rows(
    res,
    model: str,
    band: Optional[str] = None,
    extra: Optional[Dict] = None,
    exclude_vc: str = "probe Var",
    estimate_key: str = "estimate_db",
    stat_key: str = "z",
) -> List[Dict]:
    """Flatten a fitted (Mixed)LM's coefficient table into one dict per term.

    Promoted 2026-08-14 from byte-identical copies in ``area_subject_glmm.py`` and
    ``fit_omission_band_power_glmm.py`` (band-power GLMM family: ``coef_rows(res, model, band,
    extra)`` positionally, matching those two files' original signature order, still works
    unchanged) and genericized for ``fit_population_firing_lfp_power_glmm.py``'s variant
    (different excluded variance component and field names -- pass ``band=None,
    extra=..., exclude_vc="session Var", estimate_key="estimate_z", stat_key="tstat"``).
    Always drops the random-effect ``"Group Var"`` term plus whichever variance-component term
    ``exclude_vc`` names.
    """
    rows = []
    exclude = {"Group Var", exclude_vc}
    for name in res.params.index:
        if name.startswith("Group") or name in exclude:
            continue
        row = {"model": model}
        if band is not None:
            row["band"] = band
        row["term"] = name
        row[estimate_key] = float(res.params[name])
        row["se"] = float(res.bse[name])
        row[stat_key] = float(res.tvalues[name])
        row["p_raw"] = float(res.pvalues[name])
        row["ci_lo"] = float(res.conf_int().loc[name, 0])
        row["ci_hi"] = float(res.conf_int().loc[name, 1])
        row.update(extra or {})
        rows.append(row)
    return rows


class StatisticalAnalysis:
    """
    Dual statistical testing with honest multiple-comparison handling.

    Workflow:
        result = StatisticalAnalysis.compare_groups(group1, group2, paired=False)

    Family-wise FDR (across many hypotheses):
        q = StatisticalAnalysis.fdr_correct(p_values)
    """

    ALPHA = 0.05
    # Back-compat alias
    ALPHA_FDR = 0.05

    @staticmethod
    def fdr_correct(
        p_values: Union[Sequence[float], np.ndarray],
        method: str = "bh",
    ) -> np.ndarray:
        """
        Benjamini-Hochberg (or compatible) FDR across a hypothesis family.

        Args:
            p_values: 1-D array of raw p-values (one per hypothesis)
            method: passed to ``scipy.stats.false_discovery_control``

        Returns:
            FDR-adjusted q-values, same shape as input (flattened 1-D)
        """
        p = np.asarray(p_values, dtype=float).ravel()
        if p.size == 0:
            return p
        return np.asarray(stats.false_discovery_control(p, method=method), dtype=float)

    @staticmethod
    def _uncorrected_flags(param_p: float, nonparam_p: float) -> Dict:
        """Single-comparison flags; not FDR.  Emits DeprecationWarning."""
        warnings.warn(
            "fdr_pval_parametric and fdr_pval_nonparametric are deprecated aliases that "
            "mirror raw p-values (they are NOT FDR-adjusted). "
            "Switch to exploratory_compare() for clean dual reporting, or "
            "confirmatory_compare() + fdr_correct() for publication inference.",
            DeprecationWarning,
            stacklevel=3,
        )
        return {
            # Deprecated aliases: equal to raw p-values (NOT FDR-adjusted).
            "fdr_pval_parametric": float(param_p),
            "fdr_pval_nonparametric": float(nonparam_p),
            "significant_parametric": float(param_p) < StatisticalAnalysis.ALPHA,
            "significant_nonparametric": float(nonparam_p) < StatisticalAnalysis.ALPHA,
            "multiple_comparison": {
                "applied": False,
                "method": None,
                "reason": "single_comparison_dual_report",
                "note": (
                    "Parametric and nonparametric tests are dual exploratory reports. "
                    "Do not treat the deprecated fdr_pval_* keys as FDR; they mirror raw p. "
                    "Use StatisticalAnalysis.fdr_correct(p_values) across a hypothesis family."
                ),
            },
        }

    @staticmethod
    def _bootstrap_mean_diff_ci(
        a: np.ndarray,
        b: np.ndarray,
        paired: bool,
        n_bootstrap: int = 2000,
        ci: float = 0.95,
    ) -> Dict:
        rng = np.random.default_rng(42)
        if paired and len(a) == len(b) and len(a) > 1:
            diffs = a - b
            stats_boot = np.empty(n_bootstrap)
            for i in range(n_bootstrap):
                sample = rng.choice(diffs, size=len(diffs), replace=True)
                stats_boot[i] = np.mean(sample)
            observed = float(np.mean(diffs))
        else:
            if len(a) < 1 or len(b) < 1:
                return {
                    "observed_mean_diff": float("nan"),
                    "bootstrap_ci": (float("nan"), float("nan")),
                    "n_bootstrap": int(n_bootstrap),
                }
            stats_boot = np.empty(n_bootstrap)
            for i in range(n_bootstrap):
                sa = rng.choice(a, size=len(a), replace=True)
                sb = rng.choice(b, size=len(b), replace=True)
                stats_boot[i] = np.mean(sa) - np.mean(sb)
            observed = float(np.mean(a) - np.mean(b))

        alpha = (1.0 - ci) / 2.0
        lo, hi = np.percentile(stats_boot, [alpha * 100, (1 - alpha) * 100])
        return {
            "observed_mean_diff": observed,
            "bootstrap_ci": (float(lo), float(hi)),
            "n_bootstrap": int(n_bootstrap),
            "ci": float(ci),
        }

    @staticmethod
    def compare_groups(
        group1: np.ndarray,
        group2: np.ndarray,
        paired: bool = False,
        n_bootstrap: int = 2000,
    ) -> Dict:
        """
        Compare two groups: parametric (t-test) + non-parametric (Mann-Whitney / Wilcoxon).

        Effect sizes are named explicitly:
        - paired: Cohen's dz = mean(diff) / std(diff)
        - independent: Cohen's d (pooled within-group SD)

        Does **not** apply FDR to the two dual-test p-values.
        """
        group1 = np.asarray(group1).flatten()
        group2 = np.asarray(group2).flatten()

        valid1 = group1[~np.isnan(group1)]
        valid2 = group2[~np.isnan(group2)]

        result: Dict = {
            "n1": len(valid1),
            "n2": len(valid2),
            "mean1": np.mean(valid1) if len(valid1) > 0 else np.nan,
            "mean2": np.mean(valid2) if len(valid2) > 0 else np.nan,
            "std1": np.std(valid1, ddof=1) if len(valid1) > 1 else np.nan,
            "std2": np.std(valid2, ddof=1) if len(valid2) > 1 else np.nan,
            "sem1": stats.sem(valid1) if len(valid1) > 0 else np.nan,
            "sem2": stats.sem(valid2) if len(valid2) > 0 else np.nan,
            "median1": np.median(valid1) if len(valid1) > 0 else np.nan,
            "median2": np.median(valid2) if len(valid2) > 0 else np.nan,
            "iqr1": stats.iqr(valid1) if len(valid1) > 0 else np.nan,
            "iqr2": stats.iqr(valid2) if len(valid2) > 0 else np.nan,
            "mad1": stats.median_abs_deviation(valid1) if len(valid1) > 0 else np.nan,
            "mad2": stats.median_abs_deviation(valid2) if len(valid2) > 0 else np.nan,
        }

        if paired and len(valid1) == len(valid2):
            t_stat, t_pval = stats.ttest_rel(valid1, valid2)
            w_stat, w_pval = stats.wilcoxon(valid1, valid2)
            df = len(valid1) - 1
            diff = valid1 - valid2
            sd_diff = np.std(diff, ddof=1) if len(valid1) > 1 else np.nan
            cohens_dz = float(np.mean(diff) / sd_diff) if sd_diff and sd_diff > 0 else 0.0

            result.update(
                {
                    "parametric": {
                        "test": "paired_t_test",
                        "statistic": float(t_stat) if not np.isnan(t_stat) else 0.0,
                        "pval": float(t_pval) if not np.isnan(t_pval) else 1.0,
                        "df": int(df),
                        "effect_size": cohens_dz,
                        "effect_size_name": "cohens_dz",
                    },
                    "non_parametric": {
                        "test": "wilcoxon",
                        "statistic": float(w_stat) if not np.isnan(w_stat) else 0.0,
                        "pval": float(w_pval) if not np.isnan(w_pval) else 1.0,
                    },
                }
            )
            paired_flag = True
        else:
            t_stat, t_pval = stats.ttest_ind(valid1, valid2)
            u_stat, u_pval = stats.mannwhitneyu(valid1, valid2, alternative="two-sided")
            df = len(valid1) + len(valid2) - 2

            pooled_std = (
                np.sqrt(
                    ((len(valid1) - 1) * np.var(valid1, ddof=1)
                     + (len(valid2) - 1) * np.var(valid2, ddof=1))
                    / df
                )
                if df > 0
                else 0.0
            )
            cohens_d = (
                (np.mean(valid1) - np.mean(valid2)) / pooled_std if pooled_std > 0 else 0.0
            )

            result.update(
                {
                    "parametric": {
                        "test": "independent_t_test",
                        "statistic": float(t_stat) if not np.isnan(t_stat) else 0.0,
                        "pval": float(t_pval) if not np.isnan(t_pval) else 1.0,
                        "df": int(df),
                        "effect_size": float(cohens_d),
                        "effect_size_name": "cohens_d_pooled",
                    },
                    "non_parametric": {
                        "test": "mann_whitney_u",
                        "statistic": float(u_stat) if not np.isnan(u_stat) else 0.0,
                        "pval": float(u_pval) if not np.isnan(u_pval) else 1.0,
                    },
                }
            )
            paired_flag = False

        result.update(
            StatisticalAnalysis._uncorrected_flags(
                result["parametric"]["pval"],
                result["non_parametric"]["pval"],
            )
        )
        result["mean_diff_ci"] = StatisticalAnalysis._bootstrap_mean_diff_ci(
            valid1, valid2, paired=paired_flag, n_bootstrap=n_bootstrap
        )
        return result

    @staticmethod
    def compare_multiple_groups(groups: Dict[str, np.ndarray]) -> Dict:
        """Compare multiple groups: ANOVA + Kruskal-Wallis (no 2-test FDR)."""
        group_data = [np.asarray(g).flatten() for g in groups.values()]
        group_data = [g[~np.isnan(g)] for g in group_data]
        group_names = list(groups.keys())

        f_stat, f_pval = stats.f_oneway(*group_data)
        h_stat, h_pval = stats.kruskal(*group_data)

        grand_mean = np.concatenate(group_data).mean() if len(group_data) > 0 else 0
        ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in group_data)
        ss_total = sum(np.sum((g - grand_mean) ** 2) for g in group_data)
        eta_squared = ss_between / ss_total if ss_total > 0 else 0

        k = len(group_data)
        n_total = sum(len(g) for g in group_data)
        df_between = k - 1
        df_within = n_total - k

        result = {
            "n_groups": len(group_names),
            "group_names": group_names,
            "group_sizes": [len(g) for g in group_data],
            "group_means": [np.mean(g) if len(g) > 0 else np.nan for g in group_data],
            "group_stds": [np.std(g, ddof=1) if len(g) > 1 else np.nan for g in group_data],
            "group_sems": [stats.sem(g) if len(g) > 0 else np.nan for g in group_data],
            "group_medians": [np.median(g) if len(g) > 0 else np.nan for g in group_data],
            "group_iqrs": [stats.iqr(g) if len(g) > 0 else np.nan for g in group_data],
            "group_mads": [
                stats.median_abs_deviation(g) if len(g) > 0 else np.nan for g in group_data
            ],
            "parametric": {
                "test": "one_way_anova",
                "statistic": float(f_stat) if not np.isnan(f_stat) else 0.0,
                "pval": float(f_pval) if not np.isnan(f_pval) else 1.0,
                "df_between": int(df_between),
                "df_within": int(df_within),
                "effect_size": float(eta_squared),
                "effect_size_name": "eta_squared",
            },
            "non_parametric": {
                "test": "kruskal_wallis",
                "statistic": float(h_stat) if not np.isnan(h_stat) else 0.0,
                "pval": float(h_pval) if not np.isnan(h_pval) else 1.0,
            },
        }
        result.update(
            StatisticalAnalysis._uncorrected_flags(
                result["parametric"]["pval"],
                result["non_parametric"]["pval"],
            )
        )
        return result

    @staticmethod
    def correlate(x: np.ndarray, y: np.ndarray) -> Dict:
        """Correlate two variables: Pearson r + Spearman rho (no 2-test FDR)."""
        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()

        valid = ~(np.isnan(x) | np.isnan(y))
        x_valid = x[valid]
        y_valid = y[valid]

        if len(x_valid) < 3:
            return {"error": "Insufficient valid samples"}

        r_pearson, p_pearson = stats.pearsonr(x_valid, y_valid)
        rho_spearman, p_spearman = stats.spearmanr(x_valid, y_valid)
        df = len(x_valid) - 2

        result = {
            "n": len(x_valid),
            "parametric": {
                "test": "pearson_r",
                # NaN (e.g. zero-variance input) is propagated, not rewritten to 0.0/1.0 --
                # "undefined" and "measured zero correlation" are different claims.
                "statistic": float(r_pearson),
                "pval": float(p_pearson),
                "df": int(df),
                "effect_size": float(r_pearson**2),
                "effect_size_name": "r_squared",
            },
            "non_parametric": {
                "test": "spearman_rho",
                "statistic": float(rho_spearman),
                "pval": float(p_spearman),
                "df": int(df),
                "effect_size": float(rho_spearman**2),
                "effect_size_name": "rho_squared",
            },
        }
        result.update(
            StatisticalAnalysis._uncorrected_flags(
                result["parametric"]["pval"],
                result["non_parametric"]["pval"],
            )
        )
        return result

    @staticmethod
    def bootstrap_ci(
        data: np.ndarray,
        statistic_func=np.mean,
        n_bootstrap: int = 10000,
        ci: float = 0.95,
    ) -> Dict:
        """Bootstrap confidence intervals + parametric CI."""
        data = np.asarray(data).flatten()
        data = data[~np.isnan(data)]

        mean = np.mean(data)
        sem = stats.sem(data)
        t_crit = stats.t.ppf((1 + ci) / 2, len(data) - 1)
        parametric_ci = (mean - t_crit * sem, mean + t_crit * sem)

        bootstrap_stats = []
        rng = np.random.default_rng(42)
        for _ in range(n_bootstrap):
            resample = rng.choice(data, size=len(data), replace=True)
            bootstrap_stats.append(statistic_func(resample))

        bootstrap_stats = np.array(bootstrap_stats)
        alpha = (1 - ci) / 2
        bootstrap_ci = (
            np.percentile(bootstrap_stats, alpha * 100),
            np.percentile(bootstrap_stats, (1 - alpha) * 100),
        )

        return {
            "statistic": float(statistic_func(data)),
            "parametric_ci": tuple(float(x) for x in parametric_ci),
            "bootstrap_ci": tuple(float(x) for x in bootstrap_ci),
            "bootstrap_std": float(np.std(bootstrap_stats)),
        }

    @staticmethod
    def permutation_test(x: np.ndarray, y: np.ndarray, n_permutations: int = 5000) -> Dict:
        """Permutation test for difference between two groups."""
        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()

        x = x[~np.isnan(x)]
        y = y[~np.isnan(y)]

        obs_diff = np.mean(x) - np.mean(y)

        combined = np.concatenate([x, y])
        n_x = len(x)

        perm_diffs = np.empty(n_permutations)
        rng = np.random.default_rng(42)
        for i in range(n_permutations):
            perm_idx = rng.permutation(len(combined))
            perm_x = combined[perm_idx[:n_x]]
            perm_y = combined[perm_idx[n_x:]]
            perm_diffs[i] = np.mean(perm_x) - np.mean(perm_y)

        p_value = (np.abs(perm_diffs) >= np.abs(obs_diff)).sum() / n_permutations

        return {
            "observed_difference": float(obs_diff),
            "pval": float(p_value),
            "perm_mean": float(np.mean(perm_diffs)),
            "perm_std": float(np.std(perm_diffs)),
            "significant": p_value < 0.05,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Exploratory API  (no q-values, no FDR theatre)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def exploratory_compare(
        group1: np.ndarray,
        group2: np.ndarray,
        paired: bool = False,
        n_bootstrap: int = 2000,
    ) -> Dict:
        """
        Dual parametric + non-parametric comparison for **exploratory analysis**.

        Returns raw p-values only — no ``fdr_pval_*`` keys, no FDR theatre.
        Do **not** cite these p-values as publication-level inference without
        applying ``fdr_correct()`` across the full hypothesis family.

        Equivalent to ``compare_groups`` minus the deprecated flags.
        """
        # Re-use the internals but strip deprecated keys
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = StatisticalAnalysis.compare_groups(
                group1, group2, paired=paired, n_bootstrap=n_bootstrap
            )
        for key in ("fdr_pval_parametric", "fdr_pval_nonparametric", "multiple_comparison"):
            result.pop(key, None)
        result["api"] = "exploratory"
        return result

    @staticmethod
    def exploratory_correlate(x: np.ndarray, y: np.ndarray) -> Dict:
        """
        Dual Pearson r + Spearman rho for **exploratory analysis**.

        Returns raw p-values only — no deprecated flags, no FDR theatre.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = StatisticalAnalysis.correlate(x, y)
        for key in ("fdr_pval_parametric", "fdr_pval_nonparametric", "multiple_comparison"):
            result.pop(key, None)
        result["api"] = "exploratory"
        return result

    @staticmethod
    def exploratory_multi(groups: Dict[str, np.ndarray]) -> Dict:
        """
        Dual ANOVA + Kruskal-Wallis for **exploratory analysis** of multiple groups.

        Returns raw p-values only — no deprecated flags, no FDR theatre.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = StatisticalAnalysis.compare_multiple_groups(groups)
        for key in ("fdr_pval_parametric", "fdr_pval_nonparametric", "multiple_comparison"):
            result.pop(key, None)
        result["api"] = "exploratory"
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Confirmatory API  (requires hypothesis + alpha; returns q-values)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def confirmatory_compare(
        group1: np.ndarray,
        group2: np.ndarray,
        hypothesis: str,
        alpha: float = 0.05,
        paired: bool = False,
        n_bootstrap: int = 2000,
    ) -> Dict:
        """
        **Confirmatory** two-group comparison.

        Requires an explicit ``hypothesis`` string documenting what is being
        tested.  Returns both raw p-values and BH-adjusted q-values (computed
        from the two dual-test p-values as a minimal within-comparison family).

        For cross-hypothesis correction (many units / channels / frequencies),
        collect the ``q_parametric`` values across hypotheses and apply
        ``fdr_correct()`` again.

        Args:
            group1, group2: Data arrays.
            hypothesis: Plain-language statement of what is being tested,
                e.g. "FR during omission > FR during stimulus in FEF O+ units".
            alpha: Significance threshold (default 0.05).
            paired: Whether to use a paired test.
            n_bootstrap: Bootstrap iterations for CI.

        Returns:
            Dict with all exploratory_compare keys plus:
                ``hypothesis``, ``alpha``, ``q_parametric``, ``q_nonparametric``,
                ``confirmed_parametric``, ``confirmed_nonparametric``, ``api``.
        """
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError(
                "confirmatory_compare() requires a non-empty hypothesis string. "
                "Example: hypothesis='FR_omission > FR_stimulus in FEF O+ units'"
            )
        result = StatisticalAnalysis.exploratory_compare(
            group1, group2, paired=paired, n_bootstrap=n_bootstrap
        )
        param_p = result["parametric"]["pval"]
        nonparam_p = result["non_parametric"]["pval"]
        # BH-correct across the two dual-test p-values (minimal within-comparison family)
        q_vals = StatisticalAnalysis.fdr_correct([param_p, nonparam_p])
        result.update(
            {
                "hypothesis": hypothesis.strip(),
                "alpha": float(alpha),
                "q_parametric": float(q_vals[0]),
                "q_nonparametric": float(q_vals[1]),
                "confirmed_parametric": float(q_vals[0]) < alpha,
                "confirmed_nonparametric": float(q_vals[1]) < alpha,
                "api": "confirmatory",
            }
        )
        return result


def cross_modal_comparison(
    tfr_data: np.ndarray,
    spike_data: np.ndarray,
    lag_range_ms: Tuple[int, int] = (-500, 500),
    bin_ms: Optional[float] = None,
) -> Dict:
    """Trial-averaged correlation between a TFR-derived signal and a spike-count signal.

    PROMOTED 2026-08-23 from omission.jnwb_ext.functions (99%-jnwb-sufficiency normalization):
    takes no session or condition argument at all -- reduces ``tfr_data``/``spike_data`` to 1D
    (averaging over frequency/trials as needed), truncates to the common length, and delegates
    to ``StatisticalAnalysis.correlate``. No task-specific state.

    ``lag_range_ms`` needs a time scale to convert milliseconds to a sample-index shift, and
    neither input array carries one (they are plain 1D series after reduction, of unknown bin
    width). Rather than assume a bin width, that conversion is opt-in via ``bin_ms``:

    - ``bin_ms=None`` (default): behavior is unchanged from before this fix -- a single
      zero-lag correlation is computed, ``lag_range_ms`` is accepted but not used, and the
      result carries a ``lag_ms: 0.0`` field making that explicit rather than silent.
    - ``bin_ms`` given (the time-series' bin width in ms): a real lag sweep runs over every
      integer sample shift whose ``shift * bin_ms`` falls within ``lag_range_ms``, correlating
      ``tfr`` against ``spike`` shifted by each lag. The best (max |r|) lag is reported.

    Args:
        tfr_data: time-frequency power array (freq x time x trials, or fewer dims).
        spike_data: spike count array (time x trials, or fewer dims).
        lag_range_ms: (min_ms, max_ms) lag window to search; only used when ``bin_ms`` is given.
        bin_ms: bin width in ms of the (already frequency/trial-reduced) 1D series. ``None``
            skips the lag sweep and preserves the original zero-lag-only behavior.

    Returns:
        dict with correlation (StatisticalAnalysis.correlate output at the best lag), n_samples,
        lag_ms (0.0 unless a sweep ran), lfp_leads_spikes (True when the best lag is negative,
        i.e. the TFR/LFP signal is shifted earlier than spikes), interpretation -- or
        {'error': ...} when inputs are missing or too short.
    """
    if tfr_data is None or spike_data is None:
        return {'error': 'Input arrays cannot be None'}

    # Standardize time-series signals
    # If 3D, average over frequency
    if tfr_data.ndim == 3:
        tfr_mean = np.mean(tfr_data, axis=0)
    else:
        tfr_mean = tfr_data

    # Average across trials if needed
    if tfr_mean.ndim == 2:
        tfr_avg = np.mean(tfr_mean, axis=-1)
    else:
        tfr_avg = tfr_mean

    if spike_data.ndim == 2:
        spike_avg = np.mean(spike_data, axis=-1)
    else:
        spike_avg = spike_data

    n_pts = min(len(tfr_avg), len(spike_avg))
    if n_pts < 3:
        return {'error': 'Insufficient sample size for correlation'}

    x = tfr_avg[:n_pts]
    y = spike_avg[:n_pts]

    if bin_ms is None:
        corr_res = StatisticalAnalysis.correlate(x, y)
        return {
            'correlation': corr_res,
            'n_samples': n_pts,
            'lag_ms': 0.0,
            'lfp_leads_spikes': False,
            'interpretation': 'Zero-lag linear correlation between trial-averaged LFP envelope and spike counts',
        }

    max_shift = int(np.floor(min(abs(lag_range_ms[0]), abs(lag_range_ms[1])) / bin_ms))
    best_shift, best_corr, best_abs_r = 0, None, -1.0
    for shift in range(-max_shift, max_shift + 1):
        # shift > 0 tests whether x (TFR) at t+shift matches y (spikes) at t, i.e. the pattern
        # appears in y first and in x "shift" samples later -- x lags y (LFP lags spikes).
        # shift < 0 tests the reverse: x leads y (LFP leads spikes).
        if shift < 0:
            xs, ys = x[:shift], y[-shift:]
        elif shift > 0:
            xs, ys = x[shift:], y[:-shift]
        else:
            xs, ys = x, y
        if len(xs) < 3:
            continue
        candidate = StatisticalAnalysis.correlate(xs, ys)
        r = abs(candidate['parametric']['statistic'])
        if r > best_abs_r:
            best_abs_r, best_shift, best_corr = r, shift, candidate

    if best_corr is None:
        return {'error': 'Insufficient sample size for correlation at any lag in lag_range_ms'}

    return {
        'correlation': best_corr,
        'n_samples': n_pts,
        'lag_ms': float(best_shift * bin_ms),
        'lfp_leads_spikes': best_shift < 0,
        'interpretation': (
            'Best-lag linear correlation between trial-averaged LFP envelope and spike counts '
            f'(searched {lag_range_ms} ms in {bin_ms} ms steps)'
        ),
    }
