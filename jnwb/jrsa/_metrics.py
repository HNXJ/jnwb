"""The similarity and coupling metrics and their dispatch table."""

from __future__ import annotations

import warnings
import numpy as np
from .._spread import is_constant
from ._backends import _ensure_np


def _pearson(x1, x2, axis=-1, **kwargs):
    # Check if inputs are CuPy arrays
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            a = x1.ravel() if x1.ndim > 1 else x1
            y2 = x2 if x2 is not None else x1
            b = y2.ravel() if y2.ndim > 1 else y2
            if len(a) != len(b):
                raise ValueError(
                    f"_pearson: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
                )
            n = len(a)
            # CuPy correlation calculation
            a_mean = cp.mean(a)
            b_mean = cp.mean(b)
            a_std = cp.std(a)
            b_std = cp.std(b)
            # NaN for a constant vector, as on the CPU path, decided by exact equality: cp.std
            # of 100 values of 2.7 is 4.4e-16. The absolute cutoff and offset an earlier
            # version used reported 0.0 there and shrank r at small amplitude.
            if is_constant(a, xp=cp) or is_constant(b, xp=cp):
                r = cp.array(cp.nan)
            else:
                r = cp.mean((a - a_mean) * (b - b_mean)) / (a_std * b_std)
            df = n - 2
            t = r * cp.sqrt(df) / cp.sqrt(1 - r ** 2 + 1e-12)
            
            # Parametric p-value calculated on CPU/GPU boundary
            t_cpu = float(t.get()) if hasattr(t, "get") else float(t)
            from scipy.stats import t as sp_t
            p_val = 2 * sp_t.sf(abs(t_cpu), df)
            return r, t, cp.abs(r), np.float64(p_val), float(df)
    except ImportError:
        pass

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.reshape(-1) if x1.ndim > 1 else x1
    b = x2.reshape(-1) if x2.ndim > 1 else x2
    if len(a) != len(b):
        raise ValueError(
            f"_pearson: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
        )
    n = len(a)
    from jnwb.statistics import StatisticalAnalysis
    res = StatisticalAnalysis.exploratory_correlate(a, b)
    if "error" in res:
        raise ValueError(f"_pearson: cannot compute correlation ({res['error']}, n={n})")
    p_info = res["parametric"]
    r, p = p_info["statistic"], p_info["pval"]
    df = np.float64(p_info["df"])
    t = r * np.sqrt(df) / np.sqrt(1 - r ** 2 + 1e-12)
    return np.float64(r), np.float64(t), np.float64(abs(r)), np.float64(p), df


def _spearman(x1, x2, axis=-1, **kwargs):
    # For spearman rank, we rank-transform on CuPy then run Pearson
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            a = x1.ravel() if x1.ndim > 1 else x1
            y2 = x2 if x2 is not None else x1
            b = y2.ravel() if y2.ndim > 1 else y2
            if len(a) != len(b):
                raise ValueError(
                    f"_spearman: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
                )
            # Average ranks for ties, as scipy.stats.spearmanr does on the CPU path. The double
            # argsort this replaces broke ties by position, so tied data gave a different rho on
            # the GPU and a constant vector got distinct ranks instead of an undefined result.
            from scipy.stats import rankdata
            a_rank = cp.asarray(rankdata(cp.asnumpy(a)))
            b_rank = cp.asarray(rankdata(cp.asnumpy(b)))
            n = len(a)
            a_mean = cp.mean(a_rank)
            b_mean = cp.mean(b_rank)
            a_std = cp.std(a_rank)
            b_std = cp.std(b_rank)
            if float(a_std) == 0.0 or float(b_std) == 0.0:
                rho = cp.array(cp.nan)
            else:
                rho = cp.mean((a_rank - a_mean) * (b_rank - b_mean)) / (a_std * b_std)
            df = n - 2
            t = rho * cp.sqrt(df) / cp.sqrt(1 - rho ** 2 + 1e-12)
            
            # Parametric p-value calculated on CPU/GPU boundary
            t_cpu = float(t.get()) if hasattr(t, "get") else float(t)
            from scipy.stats import t as sp_t
            p_val = 2 * sp_t.sf(abs(t_cpu), df)
            return rho, t, cp.abs(rho), np.float64(p_val), float(df)
    except ImportError:
        pass

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.reshape(-1) if x1.ndim > 1 else x1
    b = x2.reshape(-1) if x2.ndim > 1 else x2
    if len(a) != len(b):
        raise ValueError(
            f"_spearman: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
        )
    n = len(a)
    from jnwb.statistics import StatisticalAnalysis
    res = StatisticalAnalysis.exploratory_correlate(a, b)
    if "error" in res:
        raise ValueError(f"_spearman: cannot compute correlation ({res['error']}, n={n})")
    np_info = res["non_parametric"]
    rho, p = np_info["statistic"], np_info["pval"]
    df = np.float64(np_info["df"])
    t = rho * np.sqrt(df) / np.sqrt(1 - rho ** 2 + 1e-12)
    return np.float64(rho), np.float64(t), np.float64(abs(rho)), np.float64(p), df


def _kendall(x1, x2, axis=-1, **kwargs):
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.stats import kendalltau
    a = x1.reshape(-1) if x1.ndim > 1 else x1
    b = x2.reshape(-1) if x2.ndim > 1 else x2
    if len(a) != len(b):
        raise ValueError(
            f"_kendall: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
        )
    tau, p = kendalltau(a, b)
    return np.float64(tau), np.float64(tau), np.float64(abs(tau)), np.float64(p), None


def _cosine(x1, x2, axis=-1, **kwargs):
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            a = x1.ravel()
            y2 = x2 if x2 is not None else x1
            b = y2.ravel()
            if len(a) != len(b):
                raise ValueError(
                    f"_cosine: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
                )
            na, nb = float(cp.linalg.norm(a)), float(cp.linalg.norm(b))
            sim = cp.dot(a / na, b / nb) if na > 0 and nb > 0 else cp.array(cp.nan)
            return sim, sim, cp.abs(sim), None, None
    except ImportError:
        pass

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()
    if len(a) != len(b):
        raise ValueError(
            f"_cosine: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
        )
    # Undefined (NaN) for a zero vector. The 1e-12 offset this replaces reported 0.0 there
    # and biased small-amplitude inputs.
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    sim = np.dot(a / na, b / nb) if na > 0 and nb > 0 else np.nan
    return np.float64(sim), np.float64(sim), np.float64(abs(sim)), None, None


def _rsa(x1, x2, axis=-1, rdm_metric="correlation", **kwargs):
    """Representational similarity analysis via condensed RDM correlation (delegating to jnwb.rsa).

    A distance undefined for some condition pair (correlation distance of a zero-variance
    row) makes the similarity NaN, which is what the pre-delegation `pdist` + `spearmanr`
    implementation returned.
    """
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from ..rsa import _condensed_distances, rdm_similarity
    v1 = _condensed_distances(x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1), rdm_metric)
    v2 = _condensed_distances(x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1), rdm_metric)
    if not (np.all(np.isfinite(v1)) and np.all(np.isfinite(v2))):
        nan = np.float64(np.nan)
        return nan, nan, nan, nan, None
    rho, p = rdm_similarity(v1, v2, metric="spearman")
    return np.float64(rho), np.float64(rho), np.float64(abs(rho)), np.float64(p), None


def _cka(x1, x2, axis=-1, kernel="linear", **kwargs):
    """Centered Kernel Alignment optimized for linear complexity O(md^2) when d << m."""
    # The linear-kernel identity below is what makes this O(m*d1*d2) rather than O(m^3);
    # it is not a Gram matrix that a kernel could be substituted into. `kernel='rbf'` and
    # `kernel='nonsense_kernel'` were both accepted and both returned the linear answer.
    if kernel != "linear":
        raise NotImplementedError(
            f"jrsa(metric='cka') implements the linear kernel only; got kernel={kernel!r}. "
            "The linear form is computed in closed form, not from an explicit Gram matrix, "
            "so another kernel cannot be substituted. Use metric='hsic' for a kernel CKA."
        )
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    d1, d2 = X.shape[1], Y.shape[1]
    
    # Standard centering: H @ K @ H.
    # For linear kernel: Kx = X @ X.T.
    # Center matrix: X_c = (I - 1/m * 11^T) @ X = X - mean(X, axis=0).
    # Then centered Gram matrix is X_c @ X_c.T.
    # Its trace/dot product is equivalent to trace((X_c @ X_c.T) @ (Y_c @ Y_c.T))
    # which can be computed as ||X_c.T @ Y_c||_F^2, which is O(m * d1 * d2) instead of O(m^3).
    X_c = X - np.mean(X, axis=0, keepdims=True)
    Y_c = Y - np.mean(Y, axis=0, keepdims=True)
    
    # Calculate trace of Kx_c @ Ky_c which is ||X_c.T @ Y_c||_F^2
    # CKA is invariant to scaling either input, so normalise first. The ratio used to carry a
    # 1e-12 offset under a quantity that scales as amplitude^8, which drove CKA toward 0 for
    # small-amplitude inputs (0.72 -> 0.08 at 1e-3 scale) and reported 0.0 for a constant one.
    nx, ny = np.linalg.norm(X_c), np.linalg.norm(Y_c)
    if nx == 0 or ny == 0:
        nan = np.float64(np.nan)
        return nan, nan, nan, None, None
    X_c = X_c / nx
    Y_c = Y_c / ny
    cross = X_c.T @ Y_c
    num = np.sum(cross ** 2)
    
    # Denominators are ||X_c.T @ X_c||_F^2 and ||Y_c.T @ Y_c||_F^2
    denom_x = np.sum((X_c.T @ X_c) ** 2)
    denom_y = np.sum((Y_c.T @ Y_c) ** 2)
    
    cka_val = num / np.sqrt(denom_x * denom_y)
    return np.float64(cka_val), np.float64(cka_val), np.float64(cka_val), None, None


def _rv(x1, x2, axis=-1, **kwargs):
    """RV coefficient optimized via trace identity to run at O(md^2) when d << m."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    
    # Standard formula uses full gram matrices: S_xx = X @ X.T (m x m)
    # trace(S_xy @ S_xy.T) = trace(X @ Y.T @ Y @ X.T) = trace(X.T @ X @ Y.T @ Y)
    # = Frobenius norm of (X.T @ Y) squared. This drops calculation from O(m^3) to O(m * d1 * d2 + d1^3).
    # The RV coefficient is defined on column-centred matrices, exactly as _cka centres
    # above. Without centring the Gram matrices are dominated by the common mean, so any
    # two representations sharing an offset look identical: two independent Gaussian
    # samples shifted by +50 returned RV = 1.0000, and independent zero-mean samples
    # returned 0.16 where the centred value is the small-sample floor.
    X = X - X.mean(axis=0, keepdims=True)
    Y = Y - Y.mean(axis=0, keepdims=True)

    # RV is invariant to scaling either input; normalise first (see _cka).
    nx, ny = np.linalg.norm(X), np.linalg.norm(Y)
    if nx == 0 or ny == 0:
        nan = np.float64(np.nan)
        return nan, nan, nan, None, None
    X = X / nx
    Y = Y / ny
    C_xy = X.T @ Y
    num = np.sum(C_xy ** 2)
    
    C_xx = X.T @ X
    C_yy = Y.T @ Y
    denom_x = np.sum(C_xx ** 2)
    denom_y = np.sum(C_yy ** 2)
    
    rv = num / np.sqrt(denom_x * denom_y)
    return np.float64(rv), np.float64(rv), np.float64(rv), None, None


def _hsic(x1, x2, axis=-1, sigma=1.0, **kwargs):
    """Hilbert-Schmidt Independence Criterion with efficient centering.
    Avoids explicit dense centering matrix allocation.
    Assumes symmetric kernels (like the default Gaussian RBF) such that K^T = K
    and trace(Kx @ Ky) = sum(Kx * Ky).
    """
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial.distance import cdist
    # Both sides need the same (n_samples, n_features) shape: cdist rejects anything else, and
    # flattening only x1 made every non-2-D call fail on x2 instead.
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    
    Kx = np.exp(-cdist(X, X, "sqeuclidean") / (2 * sigma ** 2))
    Ky = np.exp(-cdist(Y, Y, "sqeuclidean") / (2 * sigma ** 2))
    
    # Assert kernel symmetry to avoid silent failure on non-symmetric custom kernels
    if not (np.allclose(Kx, Kx.T) and np.allclose(Ky, Ky.T)):
         raise ValueError("HSIC optimization requires symmetric kernel matrices.")
    
    # Tr(Kx @ H @ Ky @ H) where H = I - 1/m * J.
    # Tr(Kx @ H @ Ky @ H) = Tr(Kx @ Ky) - 2/m * sum(Kx @ Ky) + 1/m^2 * sum(Kx) * sum(Ky) (fully centered trace).
    # Since kernels are symmetric, Tr(Kx @ Ky) = sum(Kx * Ky).
    tr_kx_ky = np.sum(Kx * Ky)
    row_sum_kx = np.sum(Kx, axis=1)
    col_sum_ky = np.sum(Ky, axis=0)
    term2 = (2.0 / m) * np.dot(row_sum_kx, col_sum_ky)
    term3 = (1.0 / (m ** 2)) * np.sum(Kx) * np.sum(Ky)
    
    hsic_val = (tr_kx_ky - term2 + term3) / ((m - 1) ** 2)
    return np.float64(hsic_val), np.float64(hsic_val), np.float64(hsic_val), None, None


def _distance_correlation(x1, x2, axis=-1, **kwargs):
    """Distance correlation (Székely & Rizzo)."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial.distance import cdist
    X = x1.reshape(x1.shape[0], -1) if x1.ndim > 1 else x1[:, None]
    Y = x2.reshape(x2.shape[0], -1) if x2.ndim > 1 else x2[:, None]
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]

    def _dcov(A, B):
        A = A - A.mean(axis=0) - A.mean(axis=1, keepdims=True) + A.mean()
        B = B - B.mean(axis=0) - B.mean(axis=1, keepdims=True) + B.mean()
        return np.sqrt(abs(np.mean(A * B)))

    dA = cdist(X, X)
    dB = cdist(Y, Y)
    dcov_xy = _dcov(dA, dB)
    dcov_xx = _dcov(dA, dA)
    dcov_yy = _dcov(dB, dB)
    # Undefined (NaN) when every row of an input is identical. The 1e-12 offset this replaces
    # reported 0.0 there and biased small-amplitude inputs.
    dc = dcov_xy / np.sqrt(dcov_xx * dcov_yy) if dcov_xx > 0 and dcov_yy > 0 else np.nan
    return np.float64(dc), np.float64(dc), np.float64(dc), None, None


def _mutual_information(x1, x2, axis=-1, bins=32, **kwargs):
    """Mutual information via histogram estimator."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    _require_paired_shape(x1, x2, "mutual_information")
    a = x1.ravel()
    b = x2.ravel()
    c_xy, xe, ye = np.histogram2d(a, b, bins=bins)
    c_xy = c_xy / c_xy.sum()
    c_x = c_xy.sum(axis=1)
    c_y = c_xy.sum(axis=0)
    outer = np.outer(c_x, c_y)
    mask = c_xy > 0
    mi = np.sum(c_xy[mask] * np.log(c_xy[mask] / (outer[mask] + 1e-12)))
    return np.float64(mi), np.float64(mi), np.float64(mi), None, None


def _procrustes(x1, x2, axis=-1, **kwargs):
    """Procrustes dissimilarity (1 - similarity)."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial import procrustes as sp_proc
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    n = min(X.shape[1], Y.shape[1])
    X, Y = X[:, :n], Y[:, :n]
    _, _, disparity = sp_proc(X, Y)
    sim = 1.0 - float(disparity)
    return np.float64(sim), np.float64(sim), np.float64(sim), None, None


def _grangercausalitytests_compat(data, maxlag):
    """Call statsmodels grangercausalitytests across versions with/without ``verbose``."""
    import inspect

    from statsmodels.tsa.stattools import grangercausalitytests

    kwargs = {"maxlag": maxlag}
    if "verbose" in inspect.signature(grangercausalitytests).parameters:
        kwargs["verbose"] = False
    return grangercausalitytests(data, **kwargs)


def _granger(x1, x2, axis=-1, max_lag=5, **kwargs):
    """Granger causality F-statistic (x2 → x1) with best lag selection by AIC."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    _require_one_series(x1, "granger_ssr_ftest", "jnwb.granger")
    _require_paired_shape(x1, x2, "granger_ssr_ftest")
    try:
        a = x1.ravel()
        b = x2.ravel()
        data = np.column_stack([a, b])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = _grangercausalitytests_compat(data, maxlag=max_lag)
        
        # Select best lag from 1 to max_lag based on minimum AIC
        # statsmodels grangercausalitytests returns a dict.
        # For each lag, res[lag][1] contains the results of the OLS regressions.
        # Under res[lag][1], there are multiple regression results (e.g. 'lrtest', 'params_ftest', 'ssr_chi2test', 'ssr_ftest').
        # The unrestricted OLS model results are in res[lag][1][1] (unrestricted model object).
        # We can fetch the AIC from res[lag][1][1].aic
        best_lag = 1
        min_aic = float('inf')
        for lag in range(1, max_lag + 1):
            try:
                # res[lag][1] is a list of [res_restricted, res_unrestricted, joint_test_results] or similar.
                # In statsmodels: res[lag][1] contains (results_d, results_m, lr_result) where results_m is the unrestricted OLS model result.
                unrestricted_model = res[lag][1][1]
                aic = unrestricted_model.aic
                if aic < min_aic:
                    min_aic = aic
                    best_lag = lag
            except (IndexError, KeyError, AttributeError, TypeError) as exc:
                warnings.warn(
                    f"Granger AIC extraction failed at lag {lag}: {exc}; skipping lag",
                    stacklevel=2,
                )
        
        f_stat = float(res[best_lag][0]["ssr_ftest"][0])
        p_val = float(res[best_lag][0]["ssr_ftest"][1])
        df = float(res[best_lag][0]["ssr_ftest"][2])
        return np.float64(f_stat), np.float64(f_stat), np.float64(f_stat), np.float64(p_val), np.float64(df)
    except ImportError:
        warnings.warn("statsmodels required for Granger causality; returning NaN.")
        return np.float64(np.nan), None, None, None, None


def _require_one_series(x, metric, trial_function):
    """Refuse an input holding more than one row for a metric that reads temporal order.

    Flattening several rows into one series made the last sample of each row the past of the
    first sample of the next, so every join between rows entered the estimate as a time step.
    """
    if int(np.prod(x.shape[:-1])) > 1:
        raise ValueError(
            f"jrsa(metric={metric!r}) takes one series per input; got shape "
            f"{tuple(x.shape)}. Flattening the rows would count each join between rows as a "
            "time transition, and pooling the rows or averaging per-row values are different "
            f"estimators. Pass one row at a time, or use {trial_function}, which takes "
            "(n_trials, n_times)."
        )


def _require_paired_shape(x1, x2, metric):
    """Refuse two inputs of different shapes for a metric that pairs their flattened samples.

    Pairing by ``x2.ravel()[:len(a)]`` truncated a longer second input and returned a
    number computed on the samples that happened to line up.
    """
    if x1.shape != x2.shape:
        raise ValueError(
            f"jrsa(metric={metric!r}) pairs the samples of x1 and x2 one to one, so both "
            f"need the same shape; got {tuple(x1.shape)} and {tuple(x2.shape)}."
        )


def _entropy(probs):
    """Calculate Shannon entropy in nats from probability array."""
    probs = probs[probs > 0]
    return -np.sum(probs * np.log(probs))


def _transfer_entropy(x1, x2, axis=-1, bins=10, **kwargs):
    """Transfer entropy (x2 → x1) via plug-in histogram estimator.

    The history is one past sample of each series and is not configurable. A `k` option
    used to be declared here and never read, so `jrsa(..., k=5)` passed the keyword check
    and returned the one-sample answer; without it, `k` is refused like any unknown option.
    `jnwb.transfer_entropy` takes the target and source history lengths.

    Only one series per input is accepted. Flattening several rows into one series made the
    last sample of each row the past of the first sample of the next, so every join between
    rows was counted as a time transition.
    """
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    _require_one_series(x1, "transfer_entropy_histogram_nats", "jnwb.transfer_entropy")
    _require_paired_shape(x1, x2, "transfer_entropy_histogram_nats")
    a = x1.ravel()
    b = x2.ravel()
    
    # We estimate TE(Y -> X) = H(X_t, X_{t-1}) + H(X_{t-1}, Y_{t-1}) - H(X_{t-1}) - H(X_t, X_{t-1}, Y_{t-1})
    # with Y = b, X = a.
    xt = a[1:]
    xt1 = a[:-1]
    yt1 = b[:-1]
    
    # Digitise and joint histogram of 3 variables
    sample = np.column_stack([xt, xt1, yt1])
    hist_3d, _ = np.histogramdd(sample, bins=bins)
    p_3d = hist_3d / hist_3d.sum()
    
    # Marginals
    p_xt_xt1 = p_3d.sum(axis=2)
    p_xt1_yt1 = p_3d.sum(axis=0)
    p_xt1 = p_3d.sum(axis=(0, 2))
    
    # Entropies
    h_3d = _entropy(p_3d)
    h_xt_xt1 = _entropy(p_xt_xt1)
    h_xt1_yt1 = _entropy(p_xt1_yt1)
    h_xt1 = _entropy(p_xt1)
    
    te = h_xt_xt1 + h_xt1_yt1 - h_xt1 - h_3d
    te = max(0.0, te)  # non-negative constraint
    
    return np.float64(te), np.float64(te), np.float64(te), None, None


def _phase_slope(x1, x2, axis=-1, fs=None, nperseg=None, noverlap=None,
                 bands=None, jackknife=True, **kwargs):
    """
    Phase Slope Index (PSI), delegated to :func:`jnwb.connectivity.phase_slope_index`.

    Superseded implementation (pre-2026-08-04) took a single ``rfft`` of the whole
    ravelled record. A one-segment coherency has magnitude identically 1 at every
    frequency, so its phase-slope sum is unweighted by coherence and is not PSI in
    the sense of Nolte et al. (2008). Coherency must be averaged over segments.

    Args:
        fs: sampling rate in Hz. When omitted, ``fs=2.0`` is used so frequencies
            read as normalized units (Nyquist = 1.0) — ``bands`` given in Hz then
            mean nothing, so pass a real ``fs`` if you want a named band.
        nperseg / noverlap / bands / jackknife: forwarded verbatim.

    Returns:
        (psi, jackknife_z, |psi|, p, None) — ``psi`` keeps its physical scale;
        ``statistic`` is now the jackknife z rather than a copy of ``psi``, and
        ``p`` is the two-sided normal-approximation p-value on that z (previously
        both were ``None``).
    """
    # PSI delegates to jnwb.connectivity's segmented estimator.
    from ..connectivity import phase_slope_index as _psi_impl

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    _require_one_series(x1, "phase_slope", "jnwb.phase_slope_index")
    _require_paired_shape(x1, x2, "phase_slope")
    a = x1.ravel()
    b = x2.ravel()
    if fs is None:
        fs = 2.0  # normalized frequency: Nyquist == 1.0
        if bands is None:
            warnings.warn(
                "phase_slope called without fs and without bands: the result is a "
                "PSI summed over the entire spectrum, where a narrowband lead is "
                "diluted by broadband noise and the sign can flip with nperseg. "
                "Pass fs= and bands= (or a normalized band, Nyquist=1.0) to get a "
                "frequency-specific direction.",
                RuntimeWarning,
                stacklevel=2,
            )
    res = _psi_impl(
        a, b, fs=fs, bands=bands, nperseg=nperseg,
        noverlap=noverlap, jackknife=jackknife,
    )
    band = next(iter(res.per_band.values()))
    z = band.get("z", np.nan)
    p = res.p_x_to_y
    return (
        np.float64(res.x_to_y),
        np.float64(z),
        np.float64(abs(res.x_to_y)),
        None if p is None else np.float64(p),
        None,
    )


#: Metrics that consume whole representations rather than paired observations along the
#: last axis. Each reshapes its inputs to (n_observations, n_features) and ignores `axis`
#: entirely, so observations lie on axis 0.
#:
#: This matters for the permutation null. `_permutation_test` shuffled axis=-1 for every
#: metric, which for these is the FEATURE axis -- and all of them are invariant to a
#: permutation of features, because a column permutation is an orthogonal transform and
#: these are all orthogonally invariant. Every permuted value therefore equalled the
#: observed one and the null was a point mass, so p came back as exactly 1.0 regardless of
#: the data. Measured on independent 60 x 12 Gaussian representations, `cka`, `rv`, `hsic`,
#: `distance_correlation` and `procrustes` all reported p = 1.0000.
_OBSERVATION_AXIS_0_METRICS = frozenset({
    "cka", "rv", "hsic", "distance_correlation", "procrustes", "rsa",
})

_METRIC_DISPATCH = {
    "pearson": _pearson,
    "spearman": _spearman,
    "kendall": _kendall,
    "cosine": _cosine,
    "rsa": _rsa,
    "cka": _cka,
    "rv": _rv,
    "hsic": _hsic,
    "distance_correlation": _distance_correlation,
    "mutual_information": _mutual_information,
    "procrustes": _procrustes,
    "granger_ssr_ftest": _granger,
    "transfer_entropy_histogram_nats": _transfer_entropy,
    "phase_slope": _phase_slope,
}
