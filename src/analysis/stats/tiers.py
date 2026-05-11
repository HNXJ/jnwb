import numpy as np
from scipy.stats import permutation_test, ttest_ind
from statsmodels.stats.multitest import multipletests
from src.analysis.io.logger import log

def get_significance_tier(p_value):
    """
    Assigns a Significance Tier (S_k) based on logarithmic resolution.
    
    Tiers:
    - Null: p >= 0.5
    - Insignificant: 0.5 > p >= 0.05
    - Sig-1: 0.05 > p >= 0.01 (*)
    - Sig-k: 10^-k > p >= 10^-(k+1) (k*)
    """
    if p_value >= 0.5:
        return "Null", 0, ""
    if p_value >= 0.05:
        return "Insignificant", 0, "n.s."
    
    if p_value < 1e-10: # Cap at Sig-10 for sanity
        return "Sig-10+", 10, "**********"
        
    k = int(np.floor(-np.log10(p_value)))
    if k == 1:
        return "Sig-1", 1, "*"
    
    return f"Sig-{k}", k, "*" * k

def format_stats_proof(test_name, p_value, n_sessions, n_units):
    """
    Generates a high-density statistical proof string for plot titles/legends.
    """
    tier_name, k, stars = get_significance_tier(p_value)
    proof = f"[{test_name}] p={p_value:.2e} ({tier_name}) | N={n_sessions}S/{n_units}U"
    return proof, stars

def run_permutation_test(data_a, data_b, n_permutations=1000, unit_of_inference="trial"):
    """
    Performs a 2-sample permutation test on the difference of means.
    data_a, data_b: (n_trials, ...) arrays.
    unit_of_inference: 'trial' (descriptive) or 'session' (population inference).
    """
    if unit_of_inference == "trial":
        log.warning("Unit of inference is 'TRIAL'. Pooled trial-level inference is DESCRIPTIVE and risks pseudoreplication. Session-level hierarchy is not modeled.")
        
    def statistic(x, y, axis):
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)
    
    res = permutation_test((data_a, data_b), statistic, 
                           permutation_type='independent', 
                           vectorized=True, 
                           n_resamples=n_permutations)
    return res.pvalue, res.statistic

def run_frequency_wise_comparison(spec_a, spec_b, alpha=0.05):
    """
    Performs point-by-point T-tests across frequencies with FDR correction.
    spec_a, spec_b: (n_units/trials, n_freqs)
    Returns: p_values_corrected, significance_mask
    """
    _, p_vals = ttest_ind(spec_a, spec_b, axis=0, equal_var=False)
    p_vals = np.nan_to_num(p_vals, nan=1.0)
    rejected, p_corrected, _, _ = multipletests(p_vals, alpha=alpha, method='fdr_bh')
    return p_corrected, rejected

def compute_granger_bootstrapped_null(target_pool, source_pool, gc_func, n_boots=200):
    """
    Generates a null distribution of GC by shuffling target/source pairs.
    target_pool, source_pool: Lists of session time-series.
    """
    null_dist = []
    n_sessions = len(target_pool)
    for _ in range(n_boots):
        # Shuffle sessions
        shuffled_source = [source_pool[i] for i in np.random.permutation(n_sessions)]
        # Average across sessions
        ts_target = np.mean(np.stack(target_pool, axis=0), axis=0)
        ts_source = np.mean(np.stack(shuffled_source, axis=0), axis=0)
        # Compute GC
        val = gc_func(ts_target, ts_source)
        null_dist.append(val)
    return np.array(null_dist)
