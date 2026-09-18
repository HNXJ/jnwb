"""Tutorial 05: Statistical Inference — Comparisons, Resampling, and FDR.

Run: python examples/tutorials/05_statistics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# This file is run from a checkout, so prefer that checkout over any installed jnwb:
# Python puts this directory on sys.path, not the repository root. A run that is
# deliberately qualifying an installed copy says so with JNWB_EXPECTED_PACKAGE_ROOT,
# and then this guard stands aside -- otherwise it would quietly redirect CI's
# installed-wheel tutorial step back to the checkout.
import os

_CHECKOUT = Path(__file__).resolve().parents[2]
if not os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") and (
    _CHECKOUT / "jnwb" / "__init__.py"
).exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb


def main() -> None:
    rng = np.random.default_rng(42)

    # Synthetic per-trial firing rates in Hz, 30 trials per condition. The unit is
    # declared because the difference below is reported in it: a mean difference of 3
    # is 3 Hz here, and would be 3 dB or 3 uV^2 for another response measure.
    group_a = rng.normal(loc=12.0, scale=2.5, size=30)   # Hz
    group_b = rng.normal(loc=15.0, scale=2.5, size=30)   # Hz

    # 1. Exploratory Comparison (Parametric t-test + Bootstrap CI)
    comp = jnwb.StatisticalAnalysis.exploratory_compare(group_a, group_b)
    assert "parametric" in comp and "mean_diff_ci" in comp
    t_stat = comp["parametric"]["statistic"]
    p_val = comp["parametric"]["pval"]
    boot_ci = comp["mean_diff_ci"]["bootstrap_ci"]
    print(f"Group comparison: t={t_stat:.2f}, p={p_val:.4e}")
    print(f"Bootstrap 95% CI on the difference in Hz: [{boot_ci[0]:.2f}, {boot_ci[1]:.2f}]")

    # 2. Bootstrap Confidence Intervals
    boot = jnwb.StatisticalAnalysis.bootstrap_ci(group_b, n_bootstrap=1000, rng=rng)
    ci_low, ci_high = boot["bootstrap_ci"]
    assert ci_low < ci_high
    print(f"Group B mean: {np.mean(group_b):.2f} Hz [95% CI: {ci_low:.2f}, {ci_high:.2f}]")

    # 3. Label Permutation with Explicit Exchangeability
    labels = np.array(["condA"] * 30 + ["condB"] * 30)
    perm_labels = jnwb.permute_labels(labels, scheme="global", rng=rng)
    assert len(perm_labels) == len(labels)
    assert np.any(perm_labels != labels)
    print(f"Permuted labels: preserved marginal counts ({np.sum(perm_labels == 'condA')} condA)")

    # 4. Multiple Comparisons Correction: Benjamini-Hochberg FDR
    # Generates a vector of raw p-values across multiple testing sites
    raw_p = np.array([0.001, 0.008, 0.023, 0.045, 0.12, 0.45, 0.89])
    fdr_q = jnwb.StatisticalAnalysis.fdr_correct(raw_p)
    # Monotonic step-up invariant
    assert np.all(np.diff(fdr_q) >= -1e-12)
    assert np.all(fdr_q >= raw_p)
    print(f"Raw p-values: {np.round(raw_p, 3)}")
    print(f"FDR q-values: {np.round(fdr_q, 3)}")

    # 5. Cluster Permutation Test for Time-Series / Spectrograms
    time_series_a = rng.normal(loc=0.0, size=(15, 50))
    time_series_b = rng.normal(loc=0.0, size=(15, 50))
    # Inject synthetic cluster effect between bins 20 and 30
    time_series_b[:, 20:30] += 1.5
    clust_res = jnwb.cluster_permutation_test(
        time_series_a,
        time_series_b,
        n_permutations=100,
        rng=rng,
    )
    assert "clusters" in clust_res
    print(f"Cluster permutation test: detected {len(clust_res['clusters'])} candidate cluster(s)")
    if clust_res["clusters"]:
        print(f"Top cluster p-value: {clust_res['clusters'][0]['p_value']:.4f}")
        # A significant cluster licenses "the conditions differ somewhere in the
        # searched window" and nothing about where. The cluster's onset, offset, peak
        # and width are not estimates: the same threshold that made it significant
        # defined its edges, and changing `threshold` moves all four. The effect was
        # injected into bins 20-30 here, so compare the cluster against that -- but
        # report it as present in the window, not as beginning at bin 20.


if __name__ == "__main__":
    main()
