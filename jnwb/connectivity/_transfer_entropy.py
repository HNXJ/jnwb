"""Transfer entropy on discretised series."""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from .._layout import require_trial_length
from .._rng import Default, RNGLike, resolve_seed_alias
from ._common import DirectedResult, _surrogate_p, _surrogate_rng, _surrogate_scheme, _surrogate_source
from ._trials import _detrend_trials, _pair_trials


# ---------------------------------------------------------------------------
# 3. Transfer entropy (model-free, nonlinear)
# ---------------------------------------------------------------------------


def _discretize(a: np.ndarray, bins: int, strategy: str) -> np.ndarray:
    """
    Map a (n_trials, n_times) float array to integer states in [0, bins).

    Edges are computed once over all trials so every trial shares a state space.
    """
    flat = a.ravel()
    if strategy == "uniform":
        lo, hi = float(flat.min()), float(flat.max())
        if hi <= lo:
            return np.zeros_like(a, dtype=np.int64)
        edges = np.linspace(lo, hi, bins + 1)[1:-1]
    elif strategy == "quantile":
        qs = np.linspace(0.0, 1.0, bins + 1)[1:-1]
        edges = np.unique(np.quantile(flat, qs))
        if edges.size == 0:
            return np.zeros_like(a, dtype=np.int64)
    elif strategy == "discrete":
        vals = np.unique(flat)
        if vals.size > 64:
            raise ValueError(
                f"estimator='discrete' saw {vals.size} distinct values; that is a "
                "continuous signal — use 'quantile' or 'uniform' instead."
            )
        return np.searchsorted(vals, a).astype(np.int64)
    else:  # pragma: no cover - guarded by caller
        raise ValueError(f"unknown discretization {strategy!r}")
    return np.searchsorted(edges, a, side="right").astype(np.int64)


def _codes(cols: List[np.ndarray]) -> np.ndarray:
    """Row-wise integer codes for a list of equal-length integer vectors.

    Codes number the distinct rows in lexicographic order, first column most significant,
    which is the order ``np.unique(axis=0)`` gives. Each column is shifted to start at zero
    and the row becomes one mixed-radix integer, first column the most significant digit,
    so a 1-D ``np.unique`` of the keys yields the same codes without sorting rows. When
    the product of the radices would not fit in int64, the row-wise ``np.unique`` runs
    instead.
    """
    if len(cols) == 1:
        return np.asarray(np.unique(cols[0], return_inverse=True)[1]).ravel()
    arrays = [np.asarray(c).ravel() for c in cols]
    if all(np.issubdtype(a.dtype, np.integer) for a in arrays) and arrays[0].size > 0:
        radices = [int(a.max()) - int(a.min()) + 1 for a in arrays]
        span = 1
        for r in radices:
            span *= r
        if span < 2**62:
            key = np.zeros(arrays[0].size, dtype=np.int64)
            for a, r in zip(arrays, radices):
                # Subtract in int64, where a narrower signed dtype cannot wrap; uint64 is
                # shifted in its own dtype, where the offset is non-negative and below 2**62.
                if a.dtype == np.uint64:
                    offset = (a - a.min()).astype(np.int64)
                else:
                    offset = a.astype(np.int64) - np.int64(a.min())
                key = key * r + offset
            return np.asarray(np.unique(key, return_inverse=True)[1]).ravel()
    stacked = np.column_stack(arrays)
    # ravel(): NumPy 2.0 briefly returned a column vector for axis-wise inverse
    return np.asarray(np.unique(stacked, axis=0, return_inverse=True)[1]).ravel()


def _entropy_plugin_and_cells(codes: np.ndarray) -> Tuple[float, int]:
    """Plug-in Shannon entropy in bits and the number of occupied cells."""
    n = codes.size
    if n == 0:
        return 0.0, 0
    counts = np.bincount(codes)
    counts = counts[counts > 0]
    p = counts / n
    return float(-np.sum(p * np.log2(p))), int(counts.size)


def _entropy_bits(codes: np.ndarray, bias_correction: Optional[str]) -> float:
    """Plug-in Shannon entropy in bits, optionally Miller-Madow corrected."""
    h, cells = _entropy_plugin_and_cells(codes)
    if bias_correction == "mm" and codes.size:
        h += (cells - 1) / (2.0 * codes.size * np.log(2.0))
    return h


def _te_one_direction(
    src_q: np.ndarray,
    tgt_q: np.ndarray,
    k: int,
    l: int,
    delay: int,
    bias_correction: Optional[str],
) -> Tuple[float, float, int, int]:
    """
    TE(source -> target) in bits from pre-discretized integer series.

    TE = H(Y_t, Y_hist) + H(Y_hist, X_hist) - H(Y_hist) - H(Y_t, Y_hist, X_hist)

    Returns ``(te, te_plugin, n_samples, n_joint)``: ``te`` carries ``bias_correction``,
    ``te_plugin`` is the uncorrected sum of the same four entropies, and ``n_joint`` is the
    number of occupied (Y_t, Y_hist, X_hist) cells.
    """
    n_trials, n_times = tgt_q.shape
    start = max(k, delay + l - 1)
    if n_times - start < 2:
        raise ValueError(
            f"history k={k}, l={l}, delay={delay} leaves < 2 samples per trial "
            f"(n_times={n_times})"
        )
    fut, y_hist, x_hist = [], [], []
    for tr in range(n_trials):
        t = np.arange(start, n_times)
        fut.append(tgt_q[tr, t])
        y_hist.append(np.column_stack([tgt_q[tr, t - j] for j in range(1, k + 1)]))
        x_hist.append(
            np.column_stack([src_q[tr, t - delay - j] for j in range(0, l)])
        )
    a = np.concatenate(fut)
    b = np.vstack(y_hist)
    c = np.vstack(x_hist)

    code_b = _codes([b[:, j] for j in range(b.shape[1])])
    code_c = _codes([c[:, j] for j in range(c.shape[1])])
    h_ab, k_ab = _entropy_plugin_and_cells(_codes([a, code_b]))
    h_bc, k_bc = _entropy_plugin_and_cells(_codes([code_b, code_c]))
    h_b, k_b = _entropy_plugin_and_cells(code_b)
    h_abc, k_abc = _entropy_plugin_and_cells(_codes([a, code_b, code_c]))
    te_plugin = float(h_ab + h_bc - h_b - h_abc)
    te = te_plugin
    if bias_correction == "mm":
        # Miller-Madow adds (cells - 1) / (2 N ln 2) to each entropy; the four terms share N.
        mm = 2.0 * a.size * np.log(2.0)
        te = float(
            (h_ab + (k_ab - 1) / mm) + (h_bc + (k_bc - 1) / mm)
            - (h_b + (k_b - 1) / mm) - (h_abc + (k_abc - 1) / mm)
        )
    return te, te_plugin, a.size, int(k_abc)


def transfer_entropy(
    X,
    Y,
    k: int = 1,
    l: int = 1,
    delay: int = 1,
    estimator: str = "quantile",
    bins: int = 4,
    symbolic_order: int = 3,
    bias_correction: Optional[str] = "mm",
    n_surrogates: int = 200,
    rng: RNGLike = Default(0),
    detrend: Optional[str] = None,
    time_axis: int = -1,
    *,
    seed: Any = Default(0),
) -> DirectedResult:
    """
    Transfer entropy — model-free, nonlinear directed information flow, in bits.

    ``TE(X -> Y) = I(Y_t ; X_past | Y_past)``: how much X's past reduces
    uncertainty about Y's present *beyond* what Y's own past already explains.

    TE is positively biased at finite sample size, so a raw TE > 0 means nothing
    on its own. This implementation therefore runs a surrogate test by default
    and reports both the raw value and ``bias_corrected`` (raw minus surrogate
    mean, the "effective transfer entropy"). With ``n_surrogates=0`` there is no
    null to subtract and the ``bias_corrected_*`` keys are absent. ``bias_corrected_*``
    sits above zero under zero-lag mixing with no directed coupling. On two noisy
    copies of one white source (n = 2000, quantile bins 4, k = l = 1, 49 surrogates, 40
    seeds) its mean was 0.0014 bits (sd 0.0033), against 0.0001 for independent pairs.
    The mechanism is inferred, not tested: the data's joint table occupies fewer cells than
    a surrogate's, so the two carry different Miller-Madow terms and plug-in biases (see
    Significance).
    It is an estimate of size; the p is the test.

    Significance. ``p_x_to_y``, ``p_y_to_x`` and ``p_net`` compare the plug-in TE of the
    data with the plug-in TE of each surrogate, whatever ``bias_correction`` is, so the p
    does not depend on it (``diagnostics['surrogates']['p_statistic'] == 'plug_in'``). A
    surrogate removes any zero-lag X-Y dependence and so occupies more joint
    (Y_t, Y_hist, X_hist) cells than the data. The net Miller-Madow term falls as that
    count grows, so a corrected statistic sits above a corrected null for reasons unrelated
    to directed flow. Measured on two noisy copies of one white source
    (``X = s + 0.5 e1``, ``Y = s + 0.5 e2``), quantile bins 4, k = l = 1, 199 surrogates,
    P(p < 0.05) per direction: 0.025 to 0.031 at n = 500 (runs of 3000 and 2000 seeds),
    0.047 and 0.051 at n = 2000 (3000), 0.053 and 0.058 at n = 4000 (5000), 0.054 and
    0.061 at n = 8000 (2000) and 0.043 at n = 16000 (1500); independent white or AR(1)
    pairs gave 0.036 to 0.062 (1000 seeds). The residue near n = 4000 to 8000 is a
    limitation: the rate reaches about 0.06 there and decays at larger n. The test is
    conservative where the data leave cells nearly empty that a surrogate fills: 0.000 of
    1000 at bins 8 or at k = l = 2 (n = 2000). It is calibrated
    only for a white common source; a coloured one gives X's past real information about
    Y's present beyond Y's noisy past, and the test rejects, as Granger does.

    Args:
        X, Y: (n_times,), (n_trials, n_times), or list of 1-D trials
        k: target history length (samples)
        l: source history length (samples)
        delay: source lag in samples; ``delay=1`` is the immediate past
        estimator:
            ``'quantile'`` — equal-population bins (default; robust to skew/outliers)
            ``'uniform'``  — equal-width bins
            ``'discrete'`` — the signal is already integer-valued (spike counts);
                             states are taken as-is, no binning
            ``'symbolic'`` raises ``ValueError``. Its surrogate null is not calibrated
            under zero-lag mixing: two noisy copies of one white source, with no
            directed coupling, test significant in both directions. Use
            ``'quantile'`` until a calibrated null exists.
        bins: number of states for quantile/uniform
        symbolic_order: kept so that later positional arguments keep their places;
            it configures only the refused ``'symbolic'`` estimator and is unused
        bias_correction: ``'mm'`` (Miller-Madow) applied to each entropy term of the
            reported estimate (``x_to_y``, ``y_to_x``, ``net`` and ``bias_corrected_*``),
            or None. The surrogate p never uses it: see Significance below.
        n_surrogates: surrogate draws for the p-value and bias correction.
            Set to 0 only if you are calibrating the null some other way.
        rng: surrogate randomness, as in :func:`granger`: an ``int`` seed (default 0), a
            ``Generator``, from which one child seed is drawn and used, or ``None`` for
            fresh OS entropy; a float is refused. Passing
            ``params['surrogate_seed_entropy']`` back as ``rng`` reproduces the
            p-values (``seed`` is the old spelling and still works)
        detrend: usually ``None``; TE is invariant to monotone rescaling under
            the quantile estimator, so z-scoring buys nothing

    Returns:
        DirectedResult with ``unit='bits'``. ``diagnostics['samples_per_joint_state']``
        below ~10 means the estimate is undersampled and a warning fires — reduce
        ``bins``, ``k``, or ``l`` rather than reporting it.

    References:
        Schreiber, T. (2000). Measuring information transfer. Phys. Rev. Lett.
        doi:10.1103/PhysRevLett.85.461 -- transfer entropy, eq. 4, with target history
        `k` and source history `l`; ``delay=1`` is the paper's alignment.
        Marschinski, R., & Kantz, H. (2002). Eur. Phys. J. B.
        doi:10.1140/epjb/e2002-00379-2 -- effective transfer entropy, the raw value minus
        the surrogate mean, reported as ``bias_corrected_*``. The surrogates here permute
        trials (7 or more) or circularly shift the source (fewer), which keeps its
        autocorrelation; ``params['surrogate_scheme']`` records which.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='transfer_entropy')
    surrogate_rng, seed_entropy = _surrogate_rng(seed, "transfer_entropy")
    if estimator == "symbolic":
        # INTENTIONAL BREAK (0.2.6.1). Ordinal patterns of order m span m samples, so a
        # target pattern and a source pattern one step earlier share samples. Zero-lag
        # mixing therefore reads as information flow, while the surrogates -- which shift
        # or re-pair the source -- destroy that overlap, and the null sits below it. On two
        # noisy copies of one white source (20 replicates, 49 surrogates) it rejected at
        # 0.05 in both directions 19 times; the quantile estimator rejected 1 and 3 times.
        raise ValueError(
            "transfer_entropy: estimator='symbolic' is refused. Its surrogate null is not "
            "calibrated under zero-lag mixing, so a common source with no directed "
            "coupling tests significant in both directions. Use estimator='quantile'."
        )
    if estimator not in ("quantile", "uniform", "discrete"):
        raise ValueError(f"estimator must be quantile|uniform|discrete; got {estimator!r}")
    if min(k, l) < 1 or delay < 1:
        raise ValueError(f"k, l, delay must all be >= 1; got k={k}, l={l}, delay={delay}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    # The embedding consumes max(k, delay * l) leading samples per trial.
    _history = max(int(k), int(delay) * int(l))
    require_trial_length(
        x, _history, "transfer_entropy", history_name="k/l/delay", time_axis=time_axis
    )
    x = _detrend_trials(x, detrend)
    y = _detrend_trials(y, detrend)
    n_trials, n_times = x.shape

    xq = _discretize(x, bins, estimator)
    yq = _discretize(y, bins, estimator)

    te_xy, plug_xy, n_used, n_joint_xy = _te_one_direction(xq, yq, k, l, delay, bias_correction)
    te_yx, plug_yx, _, n_joint_yx = _te_one_direction(yq, xq, k, l, delay, bias_correction)

    p_xy = p_yx = p_net = None
    eff_xy, eff_yx = te_xy, te_yx
    surrogate_info: Dict[str, Any] = {"n_surrogates": int(n_surrogates)}

    if n_surrogates > 0:
        null_xy = np.empty(int(n_surrogates))
        null_yx = np.empty(int(n_surrogates))
        plug_null_xy = np.empty(int(n_surrogates))
        plug_null_yx = np.empty(int(n_surrogates))
        for i in range(int(n_surrogates)):
            null_xy[i], plug_null_xy[i] = _te_one_direction(
                _surrogate_source(xq, surrogate_rng).astype(np.int64),
                yq, k, l, delay, bias_correction,
            )[:2]
            null_yx[i], plug_null_yx[i] = _te_one_direction(
                _surrogate_source(yq, surrogate_rng).astype(np.int64),
                xq, k, l, delay, bias_correction,
            )[:2]
        # INTENTIONAL BREAK (0.2.7): the test compares plug-in values, observed and
        # surrogate alike. The surrogate removes any zero-lag X-Y dependence, so it occupies
        # more (Y_t, Y_hist, X_hist) cells than the observed table. The net Miller-Madow term,
        # (K_ab + K_bc - K_b - K_abc) / (2 N ln 2), falls as K_abc grows, so the surrogate's is
        # smaller and the corrected statistic sat above the corrected null for reasons
        # unrelated to directed flow. With X = s + 0.5 e1, Y = s + 0.5 e2 and s white, P(p < 0.05) was
        # 0.11 at bins 4 and 0.37 at bins 8 (n = 2000). The correction stays on the
        # reported estimate.
        p_xy = _surrogate_p(plug_null_xy, plug_xy, "greater")
        p_yx = _surrogate_p(plug_null_yx, plug_yx, "greater")
        p_net = _surrogate_p(
            plug_null_xy - plug_null_yx, plug_xy - plug_yx, "two-sided",
            scale=abs(plug_xy) + abs(plug_yx),
        )
        eff_xy = te_xy - float(null_xy.mean())
        eff_yx = te_yx - float(null_yx.mean())
        surrogate_info.update(
            {
                "p_statistic": "plug_in",
                "null_mean_x_to_y": float(null_xy.mean()),
                "null_mean_y_to_x": float(null_yx.mean()),
                "null_sd_x_to_y": float(null_xy.std(ddof=1)) if n_surrogates > 1 else 0.0,
                "null_sd_y_to_x": float(null_yx.std(ddof=1)) if n_surrogates > 1 else 0.0,
                "bias_corrected_x_to_y": eff_xy,
                "bias_corrected_y_to_x": eff_yx,
            }
        )

    samples_per_state = n_used / max(max(n_joint_xy, n_joint_yx), 1)
    n_states_x = int(np.unique(xq).size)
    n_states_y = int(np.unique(yq).size)
    warnings_all: List[str] = []
    if samples_per_state < 10:
        warnings_all.append(
            f"undersampled_te_{samples_per_state:.1f}_samples_per_joint_state"
        )
    # The opposite failure to undersampling, and it was invisible: a discretization that
    # collapses reports FEWER joint states, so samples_per_joint_state goes UP and the
    # undersampling check stays quiet. Quantile edges on a sparse series are the common
    # case -- spike counts averaging 0.05 or 0.1 per bin are almost all zero, so every
    # quantile edge lands on 0 and the whole series maps to one symbol. TE is then
    # identically 0 by construction. Measured with X driving Y at lag 1: TE = 0.0000 bits,
    # p = 1.0, ok_for_interpretation = True and no warning at all.
    if min(n_states_x, n_states_y) < 2:
        warnings_all.append(
            f"degenerate_discretization_{min(n_states_x, n_states_y)}_state_te_is_identically_zero"
        )
    elif estimator in ("quantile", "uniform") and min(n_states_x, n_states_y) < bins:
        warnings_all.append(
            f"discretization_collapsed_to_{min(n_states_x, n_states_y)}_of_{bins}_requested_bins"
        )
    if n_surrogates == 0:
        warnings_all.append("no_surrogates_raw_te_is_positively_biased")

    return DirectedResult(
        method="transfer_entropy",
        x_to_y=te_xy,
        y_to_x=te_yx,
        net=te_xy - te_yx,
        unit="bits",
        p_x_to_y=p_xy,
        p_y_to_x=p_yx,
        p_net=p_net,
        n_trials=n_trials,
        n_times=n_times,
        params={
            "k": int(k),
            "l": int(l),
            "delay": int(delay),
            "estimator": estimator,
            "bins": int(bins) if estimator in ("quantile", "uniform") else None,
            "bias_correction": bias_correction,
            "n_surrogates": int(n_surrogates),
            "detrend": detrend,
            "seed": None if isinstance(seed, np.random.Generator) else seed,
            "surrogate_seed_entropy": seed_entropy if n_surrogates > 0 else None,
            "surrogate_scheme": _surrogate_scheme(n_trials) if n_surrogates > 0 else None,
        },
        diagnostics={
            "n_embedding_samples": int(n_used),
            "n_realized_states_x": n_states_x,
            "n_realized_states_y": n_states_y,
            "n_joint_states_x_to_y": int(n_joint_xy),
            "n_joint_states_y_to_x": int(n_joint_yx),
            "samples_per_joint_state": float(samples_per_state),
            # Only present when surrogates ran. Without them there is no null
            # mean to subtract, and eff_* still holds the raw estimate -- a
            # value under this name would claim a correction that never
            # happened. Granger reports the pair the same way.
            **(
                {"bias_corrected_x_to_y": eff_xy, "bias_corrected_y_to_x": eff_yx}
                if n_surrogates > 0
                else {}
            ),
            "surrogates": surrogate_info,
            "warnings": warnings_all,
            "ok_for_interpretation": len(warnings_all) == 0,
        },
    )
