"""Shuffle confidence intervals for R^2, coefficient rows and the LFP-spike comparison."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from .._rng import RNGLike, recorded_rng, resolve_rng, Default, resolve_seed_alias
from .._spread import is_constant as _is_constant
from ..permutation import _count_at_least_as_extreme, permute_labels
from ._tests import _require_shuffle_inputs
from ._analysis import StatisticalAnalysis


def shuffle_r2_ci(
    y_true: np.ndarray,
    y_score: np.ndarray,
    groups: Optional[np.ndarray] = None,
    n_shuffle: int = 200,
    rng: RNGLike = Default(42),
    *,
    random_state: Any = Default(42),
) -> Dict[str, float]:
    """R^2 (squared Pearson correlation) between a continuous score and a 0/1 label, with a
    shuffle-null 95% CI.

    Built on ``permute_labels`` for label shuffles. The CI is a percentile of the null distribution, not of the estimate -- R^2 has no closed
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
        rng: seed, Generator, or None for fresh entropy, for the shuffle RNG
            (``random_state`` is the old spelling and still works).

    Returns:
        dict with r2_observed, r2_null_ci_lo, r2_null_ci_hi, r2_null_mean, p_val, n_shuffle.
        A single-class label or a constant score has no R^2: every field but ``n_shuffle`` is
        then NaN.
    """
    random_state = resolve_seed_alias(rng, random_state, alias_name='random_state', func_name='shuffle_r2_ci')
    def _r2(y, s):
        # A constant label or score has no correlation to square; 0.0 would read as "none".
        if _is_constant(s) or _is_constant(y):
            return float("nan")
        r = np.corrcoef(y, s)[0, 1]
        return float(r ** 2)

    _require_shuffle_inputs(
        np.asarray(y_true, dtype=float),
        np.asarray(y_score, dtype=float),
        n_shuffle,
        "shuffle_r2_ci",
    )
    r2_obs = _r2(y_true, y_score)
    rng = resolve_rng(random_state, func_name="shuffle_r2_ci")
    null = np.empty(n_shuffle)
    scheme = "global" if groups is None else "within_group"
    for i in range(n_shuffle):
        y_perm = permute_labels(y_true, groups=groups, scheme=scheme, rng=rng)
        null[i] = _r2(y_perm, y_score)
    # Every comparison against a NaN is False, which would put p at its floor, 1/(B+1).
    k = _count_at_least_as_extreme(null, r2_obs, "greater")
    p_val = float((1 + k) / (n_shuffle + 1)) if np.isfinite(r2_obs) else float("nan")
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

    Always drops the random-effect ``"Group Var"`` term plus whichever variance-component term
    ``exclude_vc`` names. Rename estimate/stat columns via ``estimate_key`` and ``stat_key`` when
    the fitted model uses non-default field names (e.g. z-scored outcomes).
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


def _lag_align(x: np.ndarray, y: np.ndarray, shift: int) -> Tuple[np.ndarray, np.ndarray]:
    """Overlapping segments of x and y at an integer sample shift (see cross_modal_comparison)."""
    if shift < 0:
        return x[:shift], y[-shift:]
    if shift > 0:
        return x[shift:], y[:-shift]
    return x, y


def _abs_pearson(a: np.ndarray, b: np.ndarray) -> float:
    """|Pearson r| without the p-value, for permutation nulls. 0.0 if either is constant."""
    if len(a) < 3 or _is_constant(a) or _is_constant(b):
        return 0.0
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt(np.dot(a, a) * np.dot(b, b)))
    if denom <= 0.0:
        return 0.0
    return abs(float(np.dot(a, b) / denom))


def cross_modal_comparison(
    tfr_data: np.ndarray,
    spike_data: np.ndarray,
    lag_range_ms: Tuple[int, int] = (-500, 500),
    bin_ms: Optional[float] = None,
    n_permutations: int = 1000,
    rng: RNGLike = Default(None),
    *,
    seed: Any = Default(None),
) -> Dict:
    """Trial-averaged correlation between a TFR-derived signal and a spike-count signal.

    Reduces ``tfr_data``/``spike_data`` to 1D (averaging over frequency/trials as needed),
    truncates to the common length, and delegates to ``StatisticalAnalysis.correlate``.

    ``lag_range_ms`` needs a time scale to convert milliseconds to a sample-index shift, and
    neither input array carries one (they are plain 1D series after reduction, of unknown bin
    width). Rather than assume a bin width, that conversion is opt-in via ``bin_ms``:

    - ``bin_ms=None`` (default): behavior is unchanged from before this fix -- a single
      zero-lag correlation is computed, ``lag_range_ms`` is accepted but not used, and the
      result carries a ``lag_ms: 0.0`` field making that explicit rather than silent.
    - ``bin_ms`` given (the time-series' bin width in ms): a real lag sweep runs over every
      integer sample shift whose ``shift * bin_ms`` falls within ``lag_range_ms``, correlating
      ``tfr`` against ``spike`` shifted by each lag. The best (max |r|) lag is reported.

      Read ``lag_corrected_pvalue``, not ``correlation['parametric']['pval']``. The latter is
      the p at the selected lag and pays nothing for having searched: on independent white
      noise over 101 lags it fell below 0.05 in 99.5% of runs. The corrected p compares the
      observed maximum |r| against the maximum |r| over the same lags when one series is
      circularly shifted, which holds the false-positive rate at 0.043.

      That null cannot resolve a p below about ``n_lags / n_samples``, because a shift lands
      a genuine peak back inside the searched window about that often. ``lag_search_
      resolution_floor`` reports the ratio and ``warnings`` flags it above 0.05. Keep the
      series long relative to the lag window: at 101 lags, a true coupling was detected in
      0.15 of runs at 600 samples, 0.95 at 2000 and 1.00 at 4000.

    Args:
        tfr_data: time-frequency power array (freq x time x trials, or fewer dims).
        spike_data: spike count array (time x trials, or fewer dims).
        lag_range_ms: (min_ms, max_ms) lag window to search; only used when ``bin_ms`` is given.
        bin_ms: bin width in ms of the (already frequency/trial-reduced) 1D series. ``None``
            skips the lag sweep and preserves the original zero-lag-only behavior. A value
            that is not positive and finite raises ``ValueError``.
        n_permutations: circular shifts in the null of ``lag_corrected_pvalue``.
        rng: randomness of that null: an ``int`` seed, a ``Generator``, from which one child
            seed is drawn and used, or ``None`` (default) for fresh OS entropy. The result's
            ``surrogate_seed_entropy`` is the seed that ran, and passing it back as ``rng``
            reproduces ``lag_corrected_pvalue``; it is ``None`` when no sweep ran. ``seed``
            is the old spelling and still works.

    Returns:
        dict with correlation (StatisticalAnalysis.correlate output at the best lag), n_samples,
        lag_ms (0.0 unless a sweep ran), lfp_leads_spikes (True when the best lag is negative,
        i.e. the TFR/LFP signal is shifted earlier than spikes), surrogate_seed_entropy,
        interpretation -- or
        {'error': ...} when inputs are missing or too short.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='cross_modal_comparison')
    if tfr_data is None or spike_data is None:
        return {'error': 'Input arrays cannot be None'}

    # A single non-finite sample made every lag's correlation NaN, so every permutation
    # comparison was False and `lag_corrected_pvalue` came out at its floor, 1/(B+1):
    # on the same data one NaN moved it from 0.8322 to 0.000999 and flipped
    # `significant_lag_corrected` from False to True. An all-NaN input leaked a bare
    # KeyError('parametric') from the internals.
    for _name, _arr in (("tfr_data", tfr_data), ("spike_data", spike_data)):
        _a = np.asarray(_arr, dtype=float)
        if _a.size == 0:
            raise ValueError(f"cross_modal_comparison: {_name} is empty.")
        if not np.all(np.isfinite(_a)):
            raise ValueError(
                f"cross_modal_comparison: {_name} must be finite; drop or repair NaN or "
                "Inf values first. A non-finite sample makes every lag's statistic NaN "
                "and drives the permutation p-value to its floor."
            )

    if tfr_data.ndim == 3 and spike_data.ndim == 2:
        n_freq, n_time, n_trials = tfr_data.shape
        spike_time, spike_trials = spike_data.shape
        if n_time == spike_time and n_trials == spike_trials:
            pass
        elif n_trials == spike_time and n_time == spike_trials:
            raise ValueError(
                "tfr_data must be shaped (freq, time, trials) and spike_data (time, trials); "
                f"got tfr_data {tfr_data.shape}, spike_data {spike_data.shape}"
            )
        else:
            raise ValueError(
                "tfr_data must be shaped (freq, time, trials) and spike_data (time, trials); "
                f"got tfr_data {tfr_data.shape}, spike_data {spike_data.shape}"
            )

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
        corr_res = StatisticalAnalysis.exploratory_correlate(x, y)
        return {
            'correlation': corr_res,
            'n_samples': n_pts,
            'lag_ms': 0.0,
            'lfp_leads_spikes': False,
            'surrogate_seed_entropy': None,
            'interpretation': 'Zero-lag linear correlation between trial-averaged LFP envelope and spike counts',
        }

    # Every integer sample shift whose shift * bin_ms falls inside lag_range_ms, which is
    # what this function documents. It previously took
    # max_shift = floor(min(|lo|, |hi|) / bin_ms) and swept a symmetric +-max_shift, so an
    # asymmetric request was silently replaced by a different window: (-500, 100) searched
    # +-100 ms, (100, 500) searched +-100 ms (a window not even inside the request), and
    # (0, 500) searched nothing at all because min(0, 500) is 0.
    if not (np.isfinite(bin_ms) and bin_ms > 0):
        raise ValueError(
            "cross_modal_comparison: bin_ms must be a positive, finite bin width in ms, "
            f"got {bin_ms!r}."
        )
    lo_ms, hi_ms = float(lag_range_ms[0]), float(lag_range_ms[1])
    if hi_ms < lo_ms:
        lo_ms, hi_ms = hi_ms, lo_ms
    shifts = [sh for sh in range(int(np.floor(lo_ms / bin_ms)), int(np.ceil(hi_ms / bin_ms)) + 1)
              if lo_ms <= sh * bin_ms <= hi_ms and abs(sh) <= n_pts - 3]
    if not shifts:
        return {'error': 'lag_range_ms selects no usable sample shift at this bin_ms'}

    best_shift, best_corr, best_abs_r = None, None, -1.0
    for shift in shifts:
        # shift > 0 tests whether x (TFR) at t+shift matches y (spikes) at t, i.e. the pattern
        # appears in y first and in x "shift" samples later -- x lags y (LFP lags spikes).
        # shift < 0 tests the reverse: x leads y (LFP leads spikes).
        xs, ys = _lag_align(x, y, shift)
        if len(xs) < 3:
            continue
        candidate = StatisticalAnalysis.exploratory_correlate(xs, ys)
        r = abs(candidate['parametric']['statistic'])
        if r > best_abs_r:
            best_abs_r, best_shift, best_corr = r, shift, candidate

    if best_corr is None:
        return {'error': 'Insufficient sample size for correlation at any lag in lag_range_ms'}

    # The p-value inside `correlation` is the p at the selected lag, for one comparison. The
    # lag was chosen as the maximum |r| over every shift in `shifts`, so that p pays nothing
    # for the search and is not a false-positive rate. Measured on independent white noise
    # with bin_ms=10 over +-500 ms (101 lags), it fell below 0.05 in 99.5% of runs and
    # `significant_parametric` was True in 99.5% of runs.
    #
    # The corrected p compares the observed maximum |r| against the distribution of the
    # maximum |r| over the same lag set when one series is circularly shifted at random.
    # Circular shifting preserves each series' own autocorrelation, which an i.i.d.
    # permutation would destroy, and removes only the cross-series dependence.
    # The shift is drawn from the full circle on purpose. A shift-predictor null that draws
    # only from beyond the searched window looks more powerful but is not valid: circular
    # shifts form a group, and excluding the shifts that overlap the searched window breaks
    # the exchangeability the p-value rests on. Measured at n = 600 over 101 lags, the
    # restricted null rejected 11.7% of independent pairs against a nominal 5%, because a
    # 600-sample series holds only about six non-overlapping windows of 101 lags: whichever
    # window contains the global maximum wins, so the restricted p cannot resolve below
    # about 1/6. The full-circle null measured 4.0%.
    gen, seed_entropy = recorded_rng(seed, "cross_modal_comparison")
    null_max = np.empty(int(n_permutations), dtype=float)
    for b in range(int(n_permutations)):
        y_null = np.roll(y, int(gen.integers(1, n_pts)))
        null_max[b] = max(_abs_pearson(*_lag_align(x, y_null, sh)) for sh in shifts)
    lag_corrected_p = float(
        (1 + _count_at_least_as_extreme(null_max, best_abs_r, "greater"))
        / (int(n_permutations) + 1)
    )

    # How small a corrected p this configuration can even produce. A circular shift lands a
    # genuine peak back inside the searched window with probability about
    # n_lags / n_samples, and those draws match the observed maximum, so the corrected p
    # cannot go far below that ratio however strong the coupling is. Measured with a true
    # lag-20 coupling at amplitude 0.5 and 200 permutations:
    #
    #     n=600,  101 lags, ratio 0.168 -> detected in 0.15 of runs
    #     n=2000, 101 lags, ratio 0.051 -> 0.95
    #     n=4000, 101 lags, ratio 0.025 -> 1.00
    #
    # So the series must be long relative to the lag window: roughly n_lags / n_samples
    # below the alpha you intend to use.
    resolution_floor = len(shifts) / float(n_pts)

    return {
        'correlation': best_corr,
        'n_samples': n_pts,
        'lag_ms': float(best_shift * bin_ms),
        'lfp_leads_spikes': best_shift < 0,
        'n_lags_searched': len(shifts),
        'uncorrected_pvalue': float(best_corr['parametric']['pval']),
        'lag_corrected_pvalue': lag_corrected_p,
        'surrogate_seed_entropy': seed_entropy,
        'significant_lag_corrected': bool(lag_corrected_p < 0.05),
        'lag_search_resolution_floor': float(resolution_floor),
        'warnings': (
            [f'lag_window_too_wide_for_series_floor_{resolution_floor:.3f}']
            if resolution_floor >= 0.05 else []
        ),
        'interpretation': (
            'Best-lag linear correlation between trial-averaged LFP envelope and spike counts '
            f'(searched {lag_range_ms} ms in {bin_ms} ms steps, {len(shifts)} lags). '
            'Read lag_corrected_pvalue, not correlation.parametric.pval: the latter is the '
            'p at the selected lag and pays nothing for the search over lags.'
        ),
    }
