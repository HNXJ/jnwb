import numpy as np

def benjamini_hochberg(p_values):
    """Computes adjusted q-values using Benjamini-Hochberg FDR correction.
    Handles NaNs by ignoring them in ranking and setting their q-value to NaN (or 1.0 depending on preference).
    """
    p_arr = np.array(p_values, dtype=float)
    n = len(p_arr)
    if n == 0:
        return p_arr
    
    # Handle NaNs: ignore them in ranking, set their q-value to 1.0
    nan_mask = np.isnan(p_arr)
    p_clean = p_arr[~nan_mask]
    n_clean = len(p_clean)
    if n_clean == 0:
        return p_arr
    
    sort_idx = np.argsort(p_clean)
    sorted_p = p_clean[sort_idx]
    
    q_vals = np.zeros(n_clean)
    min_q = 1.0
    for i in range(n_clean - 1, -1, -1):
        p_val = sorted_p[i]
        rank = i + 1
        q_val = p_val * n_clean / rank
        min_q = min(min_q, q_val)
        q_vals[i] = min_q
        
    adjusted_p = np.zeros(n_clean)
    adjusted_p[sort_idx] = q_vals
    
    result = np.full(n, np.nan)
    result[~nan_mask] = adjusted_p
    return result
