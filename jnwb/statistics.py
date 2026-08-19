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
from typing import Dict, List, Optional, Sequence, Union

import numpy as np
from scipy import stats

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
