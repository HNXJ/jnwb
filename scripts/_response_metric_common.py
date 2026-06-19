from pathlib import Path
import numpy as np
import scipy.stats as stats

def locate_file_recursively(data_root, filename):
    """Find a file in the data root, failing closed on missing or ambiguity."""
    matches = list(Path(data_root).rglob(filename))
    if not matches:
        raise FileNotFoundError(f"Required file '{filename}' not found under data root '{data_root}'")
    if len(matches) > 1:
        raise ValueError(f"Ambiguity detected: multiple matches found for '{filename}' under '{data_root}': {[str(m) for m in matches]}")
    return matches[0]

def compute_cohens_d(x, y):
    """Computes standardized effect size (Cohen's d) across trials."""
    mx, my = np.mean(x), np.mean(y)
    vx, vy = np.var(x, ddof=1), np.var(y, ddof=1)
    pooled_std = np.sqrt((vx + vy) / 2.0) + 1e-8
    return (mx - my) / pooled_std

def run_paired_test(x, y):
    """Runs Wilcoxon signed-rank test across trials, handling zero-variance cases gracefully."""
    diff = x - y
    if np.all(diff == 0):
        return 1.0, 0.0 # No difference, p-value=1.0, effect size=0.0
    try:
        stat, p = stats.wilcoxon(x, y)
        d = compute_cohens_d(x, y)
        return float(p), float(d)
    except Exception:
        # Fallback if Wilcoxon fails due to identical values
        d = compute_cohens_d(x, y)
        return 1.0, float(d)

def run_unpaired_test(x, y):
    """Runs Mann-Whitney U test across trials."""
    if np.all(x == y):
        return 1.0, 0.0
    try:
        stat, p = stats.mannwhitneyu(x, y, alternative="two-sided")
        d = compute_cohens_d(x, y)
        return float(p), float(d)
    except Exception:
        d = compute_cohens_d(x, y)
        return 1.0, float(d)
