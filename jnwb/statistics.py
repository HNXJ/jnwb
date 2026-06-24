"""
Statistical Analysis Module: Parametric + Non-parametric + FDR Correction

Every analysis automatically computes:
- Parametric test (t-test, ANOVA, Pearson r, etc.)
- Non-parametric equivalent (Mann-Whitney U, Kruskal-Wallis, Spearman rho, etc.)
- FDR correction (Benjamini-Hochberg, α=0.05)
- Effect sizes (Cohen's d, r, eta²)

Author: Claude Code
Date: 2025-06-24
"""

import logging
from typing import Dict, Tuple, Optional, List
import numpy as np
import pandas as pd
from scipy import stats

log = logging.getLogger(__name__)


class StatisticalAnalysis:
    """
    Automatic dual statistical testing with FDR correction.

    Workflow:
        result = StatisticalAnalysis.compare_groups(group1, group2, paired=False)

    Returns:
        {
            'parametric': {'statistic': t, 'pval': p_t, 'effect_size': cohens_d},
            'non_parametric': {'statistic': U, 'pval': p_u},
            'fdr_pval_parametric': p_fdr_t,
            'fdr_pval_nonparametric': p_fdr_u,
            'significant_parametric': bool,
            'significant_nonparametric': bool,
        }
    """

    ALPHA_FDR = 0.05

    @staticmethod
    def compare_groups(group1: np.ndarray, group2: np.ndarray, paired: bool = False) -> Dict:
        """
        Compare two groups: parametric (t-test) + non-parametric (Mann-Whitney U or Wilcoxon).

        Args:
            group1: First group data
            group2: Second group data
            paired: Whether samples are paired

        Returns:
            Dictionary with parametric, non-parametric, and FDR-corrected results
        """
        group1 = np.asarray(group1).flatten()
        group2 = np.asarray(group2).flatten()

        # Remove NaN
        valid1 = group1[~np.isnan(group1)]
        valid2 = group2[~np.isnan(group2)]

        result = {
            'n1': len(valid1),
            'n2': len(valid2),
            'mean1': np.mean(valid1),
            'mean2': np.mean(valid2),
            'std1': np.std(valid1, ddof=1) if len(valid1) > 1 else np.nan,
            'std2': np.std(valid2, ddof=1) if len(valid2) > 1 else np.nan,
        }

        if paired and len(valid1) == len(valid2):
            # Paired tests
            t_stat, t_pval = stats.ttest_rel(valid1, valid2)
            w_stat, w_pval = stats.wilcoxon(valid1, valid2)

            result.update({
                'parametric': {
                    'test': 'paired_t_test',
                    'statistic': float(t_stat),
                    'pval': float(t_pval),
                    'effect_size': float(np.mean(valid1 - valid2) / np.std(valid1 - valid2, ddof=1) if len(valid1) > 1 else 0),
                },
                'non_parametric': {
                    'test': 'wilcoxon',
                    'statistic': float(w_stat),
                    'pval': float(w_pval),
                },
            })
        else:
            # Independent tests
            t_stat, t_pval = stats.ttest_ind(valid1, valid2)
            u_stat, u_pval = stats.mannwhitneyu(valid1, valid2, alternative='two-sided')

            # Cohen's d
            pooled_std = np.sqrt(
                ((len(valid1) - 1) * np.var(valid1, ddof=1) +
                 (len(valid2) - 1) * np.var(valid2, ddof=1)) /
                (len(valid1) + len(valid2) - 2)
            )
            cohens_d = (np.mean(valid1) - np.mean(valid2)) / pooled_std if pooled_std > 0 else 0

            result.update({
                'parametric': {
                    'test': 'independent_t_test',
                    'statistic': float(t_stat),
                    'pval': float(t_pval),
                    'effect_size': float(cohens_d),
                },
                'non_parametric': {
                    'test': 'mann_whitney_u',
                    'statistic': float(u_stat),
                    'pval': float(u_pval),
                },
            })

        # FDR correction (conservative: treat as part of multiple-comparison family)
        pvals = [result['parametric']['pval'], result['non_parametric']['pval']]
        fdr_pvals = stats.false_discovery_control(pvals, method='bh')

        result['fdr_pval_parametric'] = float(fdr_pvals[0])
        result['fdr_pval_nonparametric'] = float(fdr_pvals[1])
        result['significant_parametric'] = float(fdr_pvals[0]) < StatisticalAnalysis.ALPHA_FDR
        result['significant_nonparametric'] = float(fdr_pvals[1]) < StatisticalAnalysis.ALPHA_FDR

        return result

    @staticmethod
    def compare_multiple_groups(groups: Dict[str, np.ndarray]) -> Dict:
        """
        Compare multiple groups: ANOVA + Kruskal-Wallis with FDR.

        Args:
            groups: Dictionary {group_name: data_array}

        Returns:
            Dictionary with ANOVA, K-W, and FDR results
        """
        group_data = [np.asarray(g).flatten() for g in groups.values()]
        group_data = [g[~np.isnan(g)] for g in group_data]
        group_names = list(groups.keys())

        # ANOVA
        f_stat, f_pval = stats.f_oneway(*group_data)

        # Kruskal-Wallis
        h_stat, h_pval = stats.kruskal(*group_data)

        # Effect size: eta-squared
        grand_mean = np.concatenate(group_data).mean()
        ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in group_data)
        ss_total = sum(np.sum((g - grand_mean) ** 2) for g in group_data)
        eta_squared = ss_between / ss_total if ss_total > 0 else 0

        result = {
            'n_groups': len(group_names),
            'group_names': group_names,
            'group_sizes': [len(g) for g in group_data],
            'group_means': [np.mean(g) for g in group_data],
            'group_stds': [np.std(g, ddof=1) if len(g) > 1 else np.nan for g in group_data],
            'parametric': {
                'test': 'one_way_anova',
                'statistic': float(f_stat),
                'pval': float(f_pval),
                'effect_size': float(eta_squared),
            },
            'non_parametric': {
                'test': 'kruskal_wallis',
                'statistic': float(h_stat),
                'pval': float(h_pval),
            },
        }

        # FDR correction
        pvals = [result['parametric']['pval'], result['non_parametric']['pval']]
        fdr_pvals = stats.false_discovery_control(pvals, method='bh')

        result['fdr_pval_parametric'] = float(fdr_pvals[0])
        result['fdr_pval_nonparametric'] = float(fdr_pvals[1])
        result['significant_parametric'] = float(fdr_pvals[0]) < StatisticalAnalysis.ALPHA_FDR
        result['significant_nonparametric'] = float(fdr_pvals[1]) < StatisticalAnalysis.ALPHA_FDR

        return result

    @staticmethod
    def correlate(x: np.ndarray, y: np.ndarray) -> Dict:
        """
        Correlate two variables: Pearson r + Spearman rho with FDR.

        Args:
            x: First variable
            y: Second variable

        Returns:
            Dictionary with Pearson, Spearman, and FDR results
        """
        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()

        # Remove NaN
        valid = ~(np.isnan(x) | np.isnan(y))
        x_valid = x[valid]
        y_valid = y[valid]

        if len(x_valid) < 3:
            return {'error': 'Insufficient valid samples'}

        # Pearson r
        r_pearson, p_pearson = stats.pearsonr(x_valid, y_valid)

        # Spearman rho
        rho_spearman, p_spearman = stats.spearmanr(x_valid, y_valid)

        result = {
            'n': len(x_valid),
            'parametric': {
                'test': 'pearson_r',
                'statistic': float(r_pearson),
                'pval': float(p_pearson),
                'effect_size': float(r_pearson ** 2),  # R²
            },
            'non_parametric': {
                'test': 'spearman_rho',
                'statistic': float(rho_spearman),
                'pval': float(p_spearman),
                'effect_size': float(rho_spearman ** 2),
            },
        }

        # FDR correction
        pvals = [result['parametric']['pval'], result['non_parametric']['pval']]
        fdr_pvals = stats.false_discovery_control(pvals, method='bh')

        result['fdr_pval_parametric'] = float(fdr_pvals[0])
        result['fdr_pval_nonparametric'] = float(fdr_pvals[1])
        result['significant_parametric'] = float(fdr_pvals[0]) < StatisticalAnalysis.ALPHA_FDR
        result['significant_nonparametric'] = float(fdr_pvals[1]) < StatisticalAnalysis.ALPHA_FDR

        return result

    @staticmethod
    def bootstrap_ci(data: np.ndarray, statistic_func=np.mean, n_bootstrap: int = 10000,
                     ci: float = 0.95) -> Dict:
        """
        Bootstrap confidence intervals + parametric CI.

        Args:
            data: Input data
            statistic_func: Function to compute statistic
            n_bootstrap: Number of bootstrap samples
            ci: Confidence interval (0.95 = 95%)

        Returns:
            Dictionary with bootstrap and parametric CIs
        """
        data = np.asarray(data).flatten()
        data = data[~np.isnan(data)]

        # Parametric CI (normal approximation)
        mean = np.mean(data)
        sem = stats.sem(data)  # Standard error of mean
        t_crit = stats.t.ppf((1 + ci) / 2, len(data) - 1)
        parametric_ci = (mean - t_crit * sem, mean + t_crit * sem)

        # Bootstrap CI
        bootstrap_stats = []
        np.random.seed(42)
        for _ in range(n_bootstrap):
            resample = np.random.choice(data, size=len(data), replace=True)
            bootstrap_stats.append(statistic_func(resample))

        bootstrap_stats = np.array(bootstrap_stats)
        alpha = (1 - ci) / 2
        bootstrap_ci = (
            np.percentile(bootstrap_stats, alpha * 100),
            np.percentile(bootstrap_stats, (1 - alpha) * 100),
        )

        return {
            'statistic': float(statistic_func(data)),
            'parametric_ci': tuple(float(x) for x in parametric_ci),
            'bootstrap_ci': tuple(float(x) for x in bootstrap_ci),
            'bootstrap_std': float(np.std(bootstrap_stats)),
        }

    @staticmethod
    def permutation_test(x: np.ndarray, y: np.ndarray, n_permutations: int = 5000) -> Dict:
        """
        Permutation test for difference between two groups.

        Args:
            x: First group
            y: Second group
            n_permutations: Number of permutations

        Returns:
            Dictionary with observed statistic, p-value, permutation distribution
        """
        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()

        x = x[~np.isnan(x)]
        y = y[~np.isnan(y)]

        # Observed difference in means
        obs_diff = np.mean(x) - np.mean(y)

        # Permutation test
        combined = np.concatenate([x, y])
        n_x = len(x)

        perm_diffs = []
        np.random.seed(42)
        for _ in range(n_permutations):
            perm_idx = np.random.permutation(len(combined))
            perm_x = combined[perm_idx[:n_x]]
            perm_y = combined[perm_idx[n_x:]]
            perm_diffs.append(np.mean(perm_x) - np.mean(perm_y))

        perm_diffs = np.array(perm_diffs)
        p_value = (np.abs(perm_diffs) >= np.abs(obs_diff)).sum() / n_permutations

        return {
            'observed_difference': float(obs_diff),
            'pval': float(p_value),
            'perm_mean': float(np.mean(perm_diffs)),
            'perm_std': float(np.std(perm_diffs)),
            'significant': p_value < 0.05,
        }
