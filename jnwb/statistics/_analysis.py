"""``StatisticalAnalysis`` and the module-level FDR correction that forwards to it."""

from __future__ import annotations

import warnings
from typing import Dict, Optional, Sequence, Tuple, Union
import numpy as np
from .._rng import DEFAULT_SEED, RNGLike, resolve_rng
from .._spread import is_constant as _is_constant
from scipy import stats
from ..permutation import _count_at_least_as_extreme
from ._tests import clopper_pearson, mann_whitney_p_floor, exact_sign_flip, _tie_tolerance, _zero_spread_t


def fdr_correct(
    p_values: Union[Sequence[float], np.ndarray],
    method: str = "bh",
) -> np.ndarray:
    """Benjamini-Hochberg (or compatible) FDR across a hypothesis family.

    This one forwards the other way: `StatisticalAnalysis.fdr_correct` holds the
    implementation and this module-level name delegates to it. The other four
    module/class pairs in this file run class -> module.

    Args:
        p_values: 1-D array of raw p-values (one per hypothesis).
        method: Passed to ``scipy.stats.false_discovery_control``. Default "bh".

    Returns:
        np.ndarray: FDR-adjusted q-values, same shape as input (flattened 1-D).

    References:
        Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate. J. R.
        Stat. Soc. B. doi:10.1111/j.2517-6161.1995.tb02031.x -- the step-up procedure,
        returned as adjusted p-values (``method='bh'``).
        Benjamini, Y., & Yekutieli, D. (2001). The control of the false discovery rate in
        multiple testing under dependency. Ann. Stat. doi:10.1214/aos/1013699998
        -- ``method='by'``, valid under arbitrary dependence.
    """
    return StatisticalAnalysis.fdr_correct(p_values, method=method)


_TEST_CHOICES = ("both", "parametric", "nonparametric")


_CORRELATION_METHODS = ("both", "pearson", "spearman")


def _resolve_test_choice(test: str, func_name: str) -> Tuple[bool, bool]:
    """Map a ``test=`` argument to ``(run_parametric, run_nonparametric)``.

    Callers use this to declare one primary test. The unselected test is then not
    computed at all, rather than computed and filtered out of the return: a pre-registered
    family budget is a statement about how many tests were performed, and filtering a dual
    result afterwards leaves that count outside the caller's control.
    """
    if not isinstance(test, str) or test not in _TEST_CHOICES:
        raise ValueError(
            f"{func_name}: test must be one of {_TEST_CHOICES}; got {test!r}. "
            f"Use 'both' (the default) for the dual exploratory report."
        )
    return test in ("both", "parametric"), test in ("both", "nonparametric")


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

        References:
            Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate. J. R.
            Stat. Soc. B. doi:10.1111/j.2517-6161.1995.tb02031.x -- the step-up
            procedure, returned as adjusted p-values (``method='bh'``).
            Benjamini, Y., & Yekutieli, D. (2001). The control of the false discovery rate
            in multiple testing under dependency. Ann. Stat. doi:10.1214/aos/1013699998
            -- ``method='by'``, valid under arbitrary dependence.
        """
        p = np.asarray(p_values, dtype=float).ravel()
        if p.size == 0:
            return p
        return np.asarray(stats.false_discovery_control(p, method=method), dtype=float)

    @staticmethod
    def _uncorrected_flags(
        param_p: Optional[float] = None,
        nonparam_p: Optional[float] = None,
    ) -> Dict:
        """Single-comparison unadjusted significance flags; not family-wise FDR.

        A test that was not run contributes no flag, so ``n_tests`` is the number of tests
        actually performed rather than the number the function is capable of performing.
        That is the number a pre-registered family budget is spent against.
        """
        flags: Dict = {}
        if param_p is not None:
            flags["significant_parametric"] = float(param_p) < StatisticalAnalysis.ALPHA
        if nonparam_p is not None:
            flags["significant_nonparametric"] = float(nonparam_p) < StatisticalAnalysis.ALPHA

        n_tests = len(flags)
        dual = n_tests == 2
        flags["multiple_comparison"] = {
            "applied": False,
            "method": None,
            "reason": "single_comparison_dual_report" if dual else "single_comparison_one_test",
            "n_tests": n_tests,
            "note": (
                (
                    "Parametric and nonparametric tests are dual exploratory reports. "
                    if dual
                    else "One test was performed, as selected by test=. "
                )
                + "Use StatisticalAnalysis.fdr_correct(p_values) across a hypothesis family."
            ),
        }
        return flags

    @staticmethod
    def _bootstrap_mean_diff_ci(
        a: np.ndarray,
        b: np.ndarray,
        paired: bool,
        n_bootstrap: int = 2000,
        ci: float = 0.95,
        rng: RNGLike = DEFAULT_SEED,
    ) -> Dict:
        rng = resolve_rng(rng, func_name="_bootstrap_mean_diff_ci")
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
        rng: RNGLike = DEFAULT_SEED,
        *,
        test: str = "both",
    ) -> Dict:
        """
        Compare two groups: parametric (t-test) + non-parametric (Mann-Whitney / Wilcoxon).

        Effect sizes are named explicitly:
        - paired: Cohen's dz = mean(diff) / std(diff)
        - independent: Cohen's d (pooled within-group SD)

        Does **not** apply FDR to the two dual-test p-values.

        A test the data cannot support -- an empty group, one observation per group, two
        identical constant groups, or paired groups whose every difference is zero -- reports
        its ``statistic`` and ``pval`` as NaN, a t-test's ``df`` as float NaN, and its
        ``significant_*`` flag is False. An effect size whose SD is zero or undefined is NaN.
        Constant groups at different values, or paired groups whose differences are one
        non-zero constant, have no spread: the t-test's ``statistic`` is -inf or +inf and its
        ``pval`` 0.0. Constancy is tested by exact equality, so 0.3 and 0.5 behave alike.

        Args:
            test: Which test to perform -- ``"both"`` (default), ``"parametric"`` or
                ``"nonparametric"``. Naming one runs only that test: the other is not
                computed and its keys are absent from the result. Declare the primary test
                here when a pre-registered analysis budgets one test per hypothesis;
                leaving the default runs two and spends two.
        """
        run_param, run_nonparam = _resolve_test_choice(test, "compare_groups")

        group1 = np.asarray(group1).flatten()
        group2 = np.asarray(group2).flatten()

        if paired:
            if len(group1) != len(group2):
                raise ValueError(
                    "compare_groups(paired=True) requires equal group lengths; "
                    f"got n1={len(group1)}, n2={len(group2)}"
                )
            mask = np.isfinite(group1) & np.isfinite(group2)
            valid1 = group1[mask]
            valid2 = group2[mask]
            if len(valid1) < 2:
                raise ValueError(
                    "compare_groups(paired=True) requires at least two paired observations "
                    f"after NaN exclusion; got n={len(valid1)}"
                )
        else:
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

        if paired:
            if run_param:
                t_stat, t_pval = stats.ttest_rel(valid1, valid2)
                df = len(valid1) - 1
                diff = valid1 - valid2
                if _is_constant(diff):
                    # Zero spread, tested exactly; scipy sees it only when the computed SD is 0.
                    t_stat, t_pval = _zero_spread_t(valid1[0], valid2[0])
                    cohens_dz = float("nan")
                else:
                    sd_diff = np.std(diff, ddof=1)
                    cohens_dz = float(np.mean(diff) / sd_diff) if sd_diff > 0 else float("nan")
                # An undefined test (e.g. identical groups) stays NaN rather than reading as
                # statistic 0.0 and p 1.0, which is a measured null result.
                result["parametric"] = {
                    "test": "paired_t_test",
                    "statistic": float(t_stat),
                    "pval": float(t_pval),
                    # A test with no estimate has no degrees of freedom either.
                    "df": float("nan") if np.isnan(t_stat) else int(df),
                    "effect_size": cohens_dz,
                    "effect_size_name": "cohens_dz",
                }
            if run_nonparam:
                w_stat, w_pval = stats.wilcoxon(valid1, valid2)
                # The default zero_method drops zero differences; with none left there is no
                # rank to test, yet scipy returns statistic 0.0 and p 1.0.
                if not np.any(valid1 != valid2):
                    w_stat, w_pval = float("nan"), float("nan")
                result["non_parametric"] = {
                    "test": "wilcoxon",
                    "statistic": float(w_stat),
                    "pval": float(w_pval),
                }
            paired_flag = True
        else:
            df = len(valid1) + len(valid2) - 2
            if run_param:
                t_stat, t_pval = stats.ttest_ind(valid1, valid2)
                both_constant = bool(len(valid1) and len(valid2)
                                     and _is_constant(valid1) and _is_constant(valid2))
                if both_constant and df > 0:
                    t_stat, t_pval = _zero_spread_t(valid1[0], valid2[0])
                # A one-observation group adds nothing to the pooled sum of squares; its
                # ddof=1 variance is NaN, and 0 * NaN made the pooled SD NaN and d read 0.0.
                ss1 = (len(valid1) - 1) * np.var(valid1, ddof=1) if len(valid1) > 1 else 0.0
                ss2 = (len(valid2) - 1) * np.var(valid2, ddof=1) if len(valid2) > 1 else 0.0
                pooled_std = np.sqrt((ss1 + ss2) / df) if df > 0 else 0.0
                cohens_d = (
                    (np.mean(valid1) - np.mean(valid2)) / pooled_std
                    if not both_constant and len(valid1) and len(valid2) and pooled_std > 0
                    else float("nan")
                )
                result["parametric"] = {
                    "test": "independent_t_test",
                    "statistic": float(t_stat),
                    "pval": float(t_pval),
                    "df": float("nan") if np.isnan(t_stat) else int(df),
                    "effect_size": float(cohens_d),
                    "effect_size_name": "cohens_d_pooled",
                }
            if run_nonparam:
                u_stat, u_pval = stats.mannwhitneyu(valid1, valid2, alternative="two-sided")
                result["non_parametric"] = {
                    "test": "mann_whitney_u",
                    "statistic": float(u_stat),
                    "pval": float(u_pval),
                }
            paired_flag = False

        result.update(
            StatisticalAnalysis._uncorrected_flags(
                result["parametric"]["pval"] if run_param else None,
                result["non_parametric"]["pval"] if run_nonparam else None,
            )
        )
        result["mean_diff_ci"] = StatisticalAnalysis._bootstrap_mean_diff_ci(
            valid1, valid2, paired=paired_flag, n_bootstrap=n_bootstrap, rng=rng
        )
        return result

    @staticmethod
    def compare_multiple_groups(
        groups: Dict[str, np.ndarray],
        *,
        test: str = "both",
    ) -> Dict:
        """Compare multiple groups: ANOVA + Kruskal-Wallis (no 2-test FDR).

        A test the data cannot support -- an empty group, one observation per group for the
        ANOVA, or identical constant groups -- reports its ``statistic`` and ``pval`` as NaN,
        and its ``significant_*`` flag is False; an ANOVA with no estimate reports
        ``df_between`` and ``df_within`` as float NaN, and ``group_sizes`` keeps the counts.
        ``eta_squared`` is NaN when the data have no variance.

        Args:
            test: Which test to perform -- ``"both"`` (default), ``"parametric"``
                (one-way ANOVA) or ``"nonparametric"`` (Kruskal-Wallis). Naming one runs
                only that test; the other is not computed and its keys are absent.
        """
        run_param, run_nonparam = _resolve_test_choice(test, "compare_multiple_groups")

        group_data = [np.asarray(g).flatten() for g in groups.values()]
        group_data = [g[~np.isnan(g)] for g in group_data]
        group_names = list(groups.keys())

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
        }

        if run_param:
            f_stat, f_pval = stats.f_oneway(*group_data)
            grand_mean = np.concatenate(group_data).mean() if len(group_data) > 0 else 0
            ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in group_data)
            ss_total = sum(np.sum((g - grand_mean) ** 2) for g in group_data)
            # No variance at all leaves no share of it to explain: 0/0, not 0.
            eta_squared = ss_between / ss_total if ss_total > 0 else float("nan")
            # The sums of squares of constant data are rounding residue, not zero; decide the
            # two degenerate cases exactly. An empty group, or a non-finite value, keeps the NaN
            # computed above.
            if group_data and all(len(g) and np.all(np.isfinite(g)) for g in group_data):
                if _is_constant(np.concatenate(group_data)):
                    eta_squared = float("nan")
                elif all(_is_constant(g) for g in group_data):
                    eta_squared = 1.0
            result["parametric"] = {
                "test": "one_way_anova",
                "statistic": float(f_stat),
                "pval": float(f_pval),
                # A test with no estimate has no degrees of freedom; group_sizes keeps the counts.
                "df_between": float("nan") if np.isnan(f_stat) else int(df_between),
                "df_within": float("nan") if np.isnan(f_stat) else int(df_within),
                "effect_size": float(eta_squared),
                "effect_size_name": "eta_squared",
            }
        if run_nonparam:
            h_stat, h_pval = stats.kruskal(*group_data)
            result["non_parametric"] = {
                "test": "kruskal_wallis",
                "statistic": float(h_stat),
                "pval": float(h_pval),
            }

        result.update(
            StatisticalAnalysis._uncorrected_flags(
                result["parametric"]["pval"] if run_param else None,
                result["non_parametric"]["pval"] if run_nonparam else None,
            )
        )
        return result

    @staticmethod
    def correlate(x: np.ndarray, y: np.ndarray, *, method: str = "both") -> Dict:
        """Correlate two variables: Pearson r + Spearman rho (no 2-test FDR).

        A constant input has no correlation: that block reports ``statistic``, ``pval``,
        ``effect_size`` and ``df`` as float NaN, and its ``significant_*`` flag is False. A
        defined correlation keeps its integer ``df``.

        Args:
            method: Which correlation to compute -- ``"both"`` (default), ``"pearson"``
                (returned under ``parametric``) or ``"spearman"`` (under ``non_parametric``).
                Naming one computes only that one; the other is not computed and its keys
                are absent. Name the correlation before seeing the data when the analysis
                budgets one test per hypothesis; the default runs two and spends two.
        """
        if not isinstance(method, str) or method not in _CORRELATION_METHODS:
            raise ValueError(
                f"correlate: method must be one of {_CORRELATION_METHODS}; got {method!r}."
            )
        run_pearson = method in ("both", "pearson")
        run_spearman = method in ("both", "spearman")

        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()

        valid = ~(np.isnan(x) | np.isnan(y))
        x_valid = x[valid]
        y_valid = y[valid]

        if len(x_valid) < 3:
            return {"error": "Insufficient valid samples"}

        df = len(x_valid) - 2
        result: Dict = {"n": len(x_valid)}
        if run_pearson:
            r_pearson, p_pearson = stats.pearsonr(x_valid, y_valid)
            result["parametric"] = {
                "test": "pearson_r",
                # NaN (e.g. zero-variance input) is propagated, not rewritten to 0.0/1.0 --
                # "undefined" and "measured zero correlation" are different claims.
                "statistic": float(r_pearson),
                "pval": float(p_pearson),
                # A correlation with no estimate has no degrees of freedom either.
                "df": float("nan") if np.isnan(r_pearson) else int(df),
                "effect_size": float(r_pearson**2),
                "effect_size_name": "r_squared",
            }
        if run_spearman:
            rho_spearman, p_spearman = stats.spearmanr(x_valid, y_valid)
            result["non_parametric"] = {
                "test": "spearman_rho",
                "statistic": float(rho_spearman),
                "pval": float(p_spearman),
                "df": float("nan") if np.isnan(rho_spearman) else int(df),
                "effect_size": float(rho_spearman**2),
                "effect_size_name": "rho_squared",
            }
        result.update(
            StatisticalAnalysis._uncorrected_flags(
                result["parametric"]["pval"] if run_pearson else None,
                result["non_parametric"]["pval"] if run_spearman else None,
            )
        )
        return result

    @staticmethod
    def bootstrap_ci(
        data: np.ndarray,
        statistic_func=np.mean,
        n_bootstrap: int = 10000,
        ci: float = 0.95,
        rng: RNGLike = DEFAULT_SEED,
    ) -> Dict:
        """Bootstrap confidence intervals + parametric CI.

        ``rng`` defaults to the seed this function used to hide in its body; pass ``None``
        for fresh entropy, or a ``Generator`` to keep one stream across calls.
        """
        rng = resolve_rng(rng, func_name="bootstrap_ci")

        data = np.asarray(data).flatten()
        data = data[~np.isnan(data)]

        mean = np.mean(data)
        sem = stats.sem(data)
        t_crit = stats.t.ppf((1 + ci) / 2, len(data) - 1)
        parametric_ci = (mean - t_crit * sem, mean + t_crit * sem)

        bootstrap_stats = []
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
    def permutation_test(
        x: np.ndarray,
        y: np.ndarray,
        n_permutations: int = 5000,
        rng: RNGLike = DEFAULT_SEED,
    ) -> Dict:
        """Permutation test for the difference in means between two samples.

        **This is a flat shuffle. Do not use it on grouped or nested data.** Every
        observation is treated as exchangeable with every other, so trials nested in
        sessions, blocks, subjects or cycles are shuffled across that structure and the
        null absorbs the between-group differences the design confounds the effect with.
        The resulting p-value is anticonservative, and nothing here detects the nesting or
        warns: the two samples are the only structure this function is given.

        Measured on a confounded design whose true condition effect is zero -- two sessions
        with baselines 0.0 and 6.0, 12 vs 4 trials in one and 4 vs 12 in the other -- the
        flat null has standard deviation 1.07 and returns p = 0.0025, while a within-group
        null over the same data has standard deviation 0.17 and returns p = 0.24. The flat
        shuffle reports a significant effect that does not exist.

        For grouped data use ``jnwb.permute_labels(labels, groups=..., scheme=
        "within_group", rng=...)``, which takes the exchangeability structure explicitly,
        or ``jnwb.cluster_permutation_test(X, Y, groups=..., scheme="within_group")`` when
        the comparison is over time or frequency. Grouping arguments are deliberately not
        accepted here; ``permute_labels`` already implements the schemes.

        ``rng`` defaults to the seed this function used to hide in its body; pass ``None``
        for fresh entropy, or a ``Generator`` to keep one stream across calls.
        """
        rng = resolve_rng(rng, func_name="permutation_test")

        x = np.asarray(x, dtype=float).flatten()
        y = np.asarray(y, dtype=float).flatten()

        n_x_in, n_y_in = len(x), len(y)
        x = x[np.isfinite(x)]
        y = y[np.isfinite(y)]
        n_dropped = (n_x_in - len(x)) + (n_y_in - len(y))
        if n_dropped:
            warnings.warn(
                f"permutation_test: dropped {n_dropped} non-finite sample(s) "
                f"({n_x_in - len(x)} from x, {n_y_in - len(y)} from y). The test is on the "
                "remaining samples.",
                RuntimeWarning,
                stacklevel=2,
            )
        if len(x) < 2 or len(y) < 2:
            # Every comparison against a NaN observed difference was False, so the
            # exceedance count was 0 and the p-value came out at its floor, 1/(B+1):
            # two all-NaN groups reported pval 0.0002 and significant=True.
            return {
                "observed_difference": float("nan"),
                "pval": float("nan"),
                "perm_mean": float("nan"),
                "perm_std": float("nan"),
                "significant": False,
                "n_x": len(x),
                "n_y": len(y),
            }

        combined = np.concatenate([x, y])
        combined = combined - np.mean(combined)  # see _tie_tolerance
        n_x = len(x)
        obs_diff = np.mean(combined[:n_x]) - np.mean(combined[n_x:])

        perm_diffs = np.empty(n_permutations)
        for i in range(n_permutations):
            perm_idx = rng.permutation(len(combined))
            perm_x = combined[perm_idx[:n_x]]
            perm_y = combined[perm_idx[n_x:]]
            perm_diffs[i] = np.mean(perm_x) - np.mean(perm_y)

        k = _count_at_least_as_extreme(perm_diffs, obs_diff, "two-sided",
                                       atol=_tie_tolerance(combined))
        p_value = (1 + k) / (n_permutations + 1)

        return {
            "observed_difference": float(obs_diff),
            "pval": float(p_value),
            "perm_mean": float(np.mean(perm_diffs)),
            "perm_std": float(np.std(perm_diffs)),
            "significant": p_value < 0.05,
            "n_x": len(x),
            "n_y": len(y),
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
        *,
        test: str = "both",
    ) -> Dict:
        """
        Dual parametric + non-parametric comparison for **exploratory analysis**.

        Pass ``test="parametric"`` or ``test="nonparametric"`` to name one primary test;
        only that one is computed and only its keys are returned. The default runs both.

        Every p-value in the result is raw. No key in it is FDR-corrected, and no key
        claims to be: corrected values are spelled ``q_`` and are returned only by
        ``confirmatory_compare``. Do **not** cite these p-values as publication-level
        inference without applying ``fdr_correct()`` across the full hypothesis family.

        Equivalent to ``compare_groups`` minus the ``multiple_comparison`` block. The result
        carries ``correction: "none"``, so a consumer reading it can tell these p-values were
        not corrected without knowing which entry point produced them.
        """
        # Re-use compare_groups and strip the multiple_comparison block
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = StatisticalAnalysis.compare_groups(
                group1, group2, paired=paired, n_bootstrap=n_bootstrap, test=test
            )
        result.pop("multiple_comparison", None)
        result["api"] = "exploratory"
        result["correction"] = "none"
        return result

    @staticmethod
    def exploratory_correlate(x: np.ndarray, y: np.ndarray, *, method: str = "both") -> Dict:
        """
        Dual Pearson r + Spearman rho for **exploratory analysis**.

        Pass ``method="pearson"`` or ``method="spearman"`` to name one correlation; only
        that one is computed and only its keys are returned. The default computes both.

        Every p-value in the result is raw, and so are the ``significant_*`` flags. The
        result carries ``correction: "none"``, as ``exploratory_compare`` does.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = StatisticalAnalysis.correlate(x, y, method=method)
        result.pop("multiple_comparison", None)
        result["api"] = "exploratory"
        result["correction"] = "none"
        return result

    @staticmethod
    def exploratory_multi(groups: Dict[str, np.ndarray], *, test: str = "both") -> Dict:
        """
        Dual ANOVA + Kruskal-Wallis for **exploratory analysis** of multiple groups.

        Every p-value in the result is raw and no key in it claims otherwise. Pass
        ``test="parametric"`` or ``test="nonparametric"`` to name one primary test; only
        that one is computed. The default runs both. The result carries
        ``correction: "none"``.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = StatisticalAnalysis.compare_multiple_groups(groups, test=test)
        result.pop("multiple_comparison", None)
        result["api"] = "exploratory"
        result["correction"] = "none"
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
        collect the RAW ``result["parametric"]["pval"]`` across hypotheses and
        apply ``fdr_correct()`` once. Do not feed ``q_parametric`` back into
        ``fdr_correct()``: those values are already BH-adjusted within their own
        comparison, and adjusting them again compounds the two corrections. A
        p-value of 0.2694 becomes q = 0.3481 within its comparison and 0.3665
        after a second pass over twenty hypotheses. The error is conservative --
        it costs power rather than creating false positives -- but the resulting
        numbers no longer carry an FDR guarantee at any level.

        Args:
            group1, group2: Data arrays.
            hypothesis: Plain-language statement of what is being tested,
                e.g. "mean rate in condition A > mean rate in condition B".
            alpha: Significance threshold (default 0.05).
            paired: Whether to use a paired test.
            n_bootstrap: Bootstrap iterations for CI.

        Returns:
            Dict with all exploratory_compare keys plus:
                ``hypothesis``, ``alpha``, ``q_parametric``, ``q_nonparametric``,
                ``confirmed_parametric``, ``confirmed_nonparametric``, ``api``.
            A test whose ``pval`` is NaN has a NaN q-value and is not confirmed.
        """
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError(
                "confirmatory_compare() requires a non-empty hypothesis string. "
                "Example: hypothesis='rate in condition A > rate in condition B'"
            )
        # `alpha=2.0` used to return `confirmed_parametric=True` for q = 0.1188 -- a
        # confirmation at an impossible significance level, from a confirmatory API.
        # `clopper_pearson` validates the identical parameter.
        if not (0.0 < float(alpha) < 1.0):
            raise ValueError(
                f"confirmatory_compare: alpha must be in (0, 1), got {alpha}."
            )
        result = StatisticalAnalysis.exploratory_compare(
            group1, group2, paired=paired, n_bootstrap=n_bootstrap
        )
        param_p = result["parametric"]["pval"]
        nonparam_p = result["non_parametric"]["pval"]
        # BH-correct across the two dual-test p-values (minimal within-comparison family).
        # An undefined p enters the family as 1.0, the value it used to be reported as, so a
        # defined partner's q is unchanged; its own q is NaN.
        p_pair = np.array([param_p, nonparam_p], dtype=float)
        q_vals = StatisticalAnalysis.fdr_correct(np.where(np.isnan(p_pair), 1.0, p_pair))
        q_vals[np.isnan(p_pair)] = np.nan
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

    @staticmethod
    def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
        """Exact (Clopper-Pearson) binomial confidence interval via Beta quantiles.

        Forwards to the module-level `clopper_pearson`, which holds the implementation.
        """
        return clopper_pearson(k, n, alpha=alpha)

    @staticmethod
    def clopper_pearson_ci(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
        """Older spelling of `clopper_pearson`, kept for callers that used it.

        Forwards to the module-level `clopper_pearson`, same as the method it aliases.
        """
        return clopper_pearson(k, n, alpha=alpha)

    @staticmethod
    def mann_whitney_p_floor(n1: int, n2: int, alternative: str = "two-sided") -> float:
        """Attainable minimal non-zero p-value floor for Mann-Whitney U test without ties.

        Forwards to the module-level `mann_whitney_p_floor`, which holds the implementation.
        """
        return mann_whitney_p_floor(n1, n2, alternative=alternative)

    @staticmethod
    def exact_sign_flip(
        diffs: Union[Sequence[float], np.ndarray],
        alternative: str = "two-sided",
        n_mc: int = 10000,
        rng: RNGLike = DEFAULT_SEED,
    ) -> Tuple[float, float, float]:
        """Exact paired sign-flip permutation test for paired sample differences.

        Forwards to the module-level `exact_sign_flip`, which holds the implementation.
        """
        return exact_sign_flip(diffs, alternative=alternative, n_mc=n_mc, rng=rng)
