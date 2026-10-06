"""xFLIP: laminar blocks from the cross-channel correlation profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from .._dictlike import DictAccessMixin
from .._rng import surrogate_rng
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import rankdata
from ..permutation import _TIE_RTOL, _count_at_least_as_extreme, _count_each_at_least_as_extreme


@dataclass(frozen=True)
class XFlipResult(DictAccessMixin):
    """Container for Cross-Channel Laminar Correlation Profile (xFLIP) results.

    Attributes:
        corr_matrix: 2D array of shape (n_channels, n_channels) containing the
            computed or supplied inter-channel correlation matrix.
        block_bounds: Tuple of half-open integer index intervals (start, end)
            defining each contiguous contact block along the probe shaft.
        boundaries: Tuple of integer contact indices where block boundaries occur.
        labels: 1D integer array of shape (n_channels,) with block membership (0, 1, ...).
        modularity: Observed modularity/contrast score Q = mean(within) - mean(between).
        p_values: Dict mapping test names to Monte Carlo p-values ('omnibus' and per-boundary).
        accepted: Boolean flag indicating whether the block partition is statistically
            significant (p <= alpha) and satisfies all structural constraints.
        rejection_reason: Diagnostic reason string if rejected, or None if accepted.
        method: Correlation method used ('pearson', 'spearman', 'partial', or 'precomputed').
        n_channels: Number of channels evaluated.
        n_blocks: Number of detected blocks.
        boundary_drops: Optional dict mapping each interior boundary index to its
            local correlation drop (within-block neighbor correlation minus cross-boundary correlation).
        surrogate_seed_entropy: The entropy the surrogate generator was built from: the
            seed for an int `rng`, and the fresh OS entropy drawn for `rng=None`. Passing it
            back as `rng` reproduces `p_values`. None when you supplied a `Generator`, whose
            stream position cannot be recovered, and when no surrogates were drawn.
    """

    corr_matrix: np.ndarray
    block_bounds: Tuple[Tuple[int, int], ...]
    boundaries: Tuple[int, ...]
    labels: np.ndarray
    modularity: float
    p_values: Dict[str, float]
    accepted: bool
    rejection_reason: Optional[str]
    method: str
    n_channels: int
    n_blocks: int
    boundary_drops: Optional[Dict[int, float]] = None
    surrogate_seed_entropy: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to dictionary for serialization."""
        return {
            "corr_matrix": self.corr_matrix.copy(),
            "block_bounds": self.block_bounds,
            "boundaries": self.boundaries,
            "labels": self.labels.copy(),
            "modularity": float(self.modularity),
            "p_values": dict(self.p_values),
            "accepted": bool(self.accepted),
            "rejection_reason": self.rejection_reason,
            "method": str(self.method),
            "n_channels": int(self.n_channels),
            "n_blocks": int(self.n_blocks),
            "boundary_drops": dict(self.boundary_drops) if self.boundary_drops is not None else {},
            "surrogate_seed_entropy": self.surrogate_seed_entropy,
        }


def _compute_correlation_matrix(data: np.ndarray, method: str) -> np.ndarray:
    """Compute (n_channels, n_channels) correlation matrix across samples.

    Args:
        data: 2D array of shape (n_channels, n_samples).
        method: 'pearson', 'spearman', or 'partial'.
    """
    n_channels, n_samples = data.shape
    if method == "pearson":
        corr = np.corrcoef(data)
        if np.any(np.isnan(corr)):
            np.nan_to_num(corr, copy=False, nan=0.0)
            np.fill_diagonal(corr, 1.0)
        return np.clip(corr, -1.0, 1.0)

    elif method == "spearman":
        ranks = rankdata(data, axis=1)
        corr = np.corrcoef(ranks)
        if np.any(np.isnan(corr)):
            np.nan_to_num(corr, copy=False, nan=0.0)
            np.fill_diagonal(corr, 1.0)
        return np.clip(corr, -1.0, 1.0)

    elif method == "partial":
        cov = np.cov(data)
        if np.allclose(cov, 0.0):
            return np.eye(n_channels, dtype=float)
        try:
            cond = np.linalg.cond(cov)
            if cond > 1e12 or not np.isfinite(cond):
                theta = np.linalg.pinv(cov)
            else:
                theta = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            theta = np.linalg.pinv(cov)

        d = np.diag(theta)
        d_pos = np.maximum(d, 1e-12)
        denom = np.sqrt(np.outer(d_pos, d_pos))
        p_corr = -theta / denom
        np.fill_diagonal(p_corr, 1.0)
        return np.clip(p_corr, -1.0, 1.0)

    raise ValueError(f"Unknown correlation method '{method}'")


def _surrogate_phase_randomize(data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Fourier phase randomization independently per channel.

    Preserves each channel's empirical power spectral density and temporal
    autocorrelation R_{cc}(tau) while destroying cross-channel phase coherence.
    """
    n_channels, n_samples = data.shape
    fft_coeffs = np.fft.rfft(data, axis=1)
    magnitudes = np.abs(fft_coeffs)
    n_freqs = fft_coeffs.shape[1]

    rand_phases = rng.uniform(0.0, 2.0 * np.pi, size=(n_channels, n_freqs))
    rand_phases[:, 0] = 0.0
    if n_samples % 2 == 0:
        rand_phases[:, -1] = 0.0

    surrogate_fft = magnitudes * np.exp(1j * rand_phases)
    return np.fft.irfft(surrogate_fft, n=n_samples, axis=1)


def _compute_contrast(corr: np.ndarray, labels: np.ndarray) -> float:
    """Compute block contrast Q = mean(within) - mean(between)."""
    n = corr.shape[0]
    triu_r, triu_c = np.triu_indices(n, k=1)
    if len(triu_r) == 0:
        return 0.0
    vals = corr[triu_r, triu_c]
    same_label = (labels[triu_r] == labels[triu_c])
    within_cnt = int(np.sum(same_label))
    between_cnt = int(np.sum(~same_label))

    mean_within = float(np.sum(vals[same_label]) / within_cnt) if within_cnt > 0 else 0.0
    mean_between = float(np.sum(vals[~same_label]) / between_cnt) if between_cnt > 0 else 0.0
    return mean_within - mean_between


def _select_count_by_min_p(obs_q: np.ndarray, surr_q: np.ndarray) -> Tuple[int, float]:
    """The candidate count with the smallest surrogate p, and a p that accounts for choosing it.

    `obs_q` is `(K,)`, the observed contrast at each candidate count; `surr_q` is `(S, K)`,
    each surrogate's contrast at the same counts. The observation and the S surrogates are
    treated as S + 1 exchangeable draws. At each count, a draw's p is the fraction of the
    draws whose contrast is at least its own, within round-off (100 machine epsilons of a
    correlation, as ``_count_at_least_as_extreme`` counts), so the observation's p is the usual
    `(1 + #exceed) / (1 + S)`. Each draw's statistic is its smallest p over the counts, and
    the returned p is the fraction of draws whose smallest p is at most the observation's:
    the selection is repeated on every surrogate. With one candidate this is exactly the
    fixed-count p.

    Among counts tied at the smallest p, the one whose observed contrast lies the most
    surrogate standard deviations above the surrogate mean is chosen, and on a further tie
    the smallest count. The tie-break chooses the partition only; the p does not depend on it.

    Returns:
        (index into the candidates, p)
    """
    draws = np.vstack([obs_q[None, :], surr_q])
    n_draws = draws.shape[0]
    # "At least its own" counts a draw within round-off of it, by the rule every jnwb null
    # uses, applied to each draw in turn: two draws that tie to round-off each count the
    # other. The width is 100 eps * max(1, |contrast|). One sort per count: O(K S log S).
    # The p that follows compares the integer counts exactly.
    at_least = np.empty(draws.shape, dtype=np.int64)
    for i in range(draws.shape[1]):
        at_least[:, i] = _count_each_at_least_as_extreme(draws[:, i], atol=_TIE_RTOL)
    smallest = at_least.min(axis=1)
    p = float(np.count_nonzero(smallest <= smallest[0]) / n_draws)

    dev = obs_q - surr_q.mean(axis=0)
    spread = surr_q.std(axis=0)
    # A count whose surrogates do not vary scores +-inf by the sign of its deviation, or 0.
    z = np.where(dev > 0, np.inf, np.where(dev < 0, -np.inf, 0.0))
    np.divide(dev, spread, out=z, where=spread > 0)
    tied = np.flatnonzero(at_least[0] == smallest[0])
    return int(tied[np.argmax(z[tied])]), p


def _optimal_contiguous_partition(
    corr: np.ndarray,
    n_blocks: int,
    min_block_size: int,
) -> Tuple[Tuple[Tuple[int, int], ...], Tuple[int, ...], float, np.ndarray]:
    """Find globally optimal contiguous partition using 1D dynamic programming.

    Maximizes the sum over blocks of W(u, v) = S(u, v)**2 / P(u, v), where S(u, v) is
    the sum of off-diagonal correlations within [u, v) and P(u, v) = (v-u)*(v-u-1)/2 is
    their number of pairs. A single-contact block has no pairs and scores 0.

    W is the squared error removed by describing a block's within-block correlations by
    their mean rather than by 0, so the partition is the block-constant least-squares fit
    to the within-block correlations. It scores each block against its own mean; an
    uncorrelated block scores near 0 at any size, which leaves the cut at the edge of a
    correlated block. Squaring discards the sign: a block of negative mean correlation
    scores as a positive one of the same magnitude.

    INTENTIONAL BREAK (0.2.7): W was S - gamma * P with gamma the probe-wide mean
    correlation. Penalising every within-block pair by one probe-wide value favoured
    blocks of equal size, and beside an uncorrelated background moved the cut toward the
    middle of the probe, where the surrogate test could still accept it. Cuts can change
    on existing data.

    Returns:
        (block_bounds, boundaries, modularity, labels)
    """
    n = corr.shape[0]
    if n_blocks == 1:
        labels = np.zeros(n, dtype=int)
        return ((0, n),), (), 0.0, labels

    prefix = np.zeros((n + 1, n + 1), dtype=float)
    prefix[1:, 1:] = np.cumsum(np.cumsum(corr, axis=0), axis=1)
    # The off-diagonal term below was already answered from `prefix` in constant
    # time while the diagonal term re-summed a slice on every call. `np.diag` returns a
    # view, so nothing was copied, but the call plus the slice plus the reduction cost
    # 4.82 of the 5.56 microseconds an `interval_w` call took -- 87% of it -- and the DP
    # makes about 93000 of them at n=256 with n_blocks=4, once per surrogate. Prefix-
    # summing the diagonal answers it the way the off-diagonal term is already answered.
    #
    # Subtracting the diagonal's running total removes it from S exactly in real
    # arithmetic; in floating point a residue of order 1e-15 per block remains, which
    # the tests that vary the diagonal show does not move a cut. The returned modularity
    # is computed separately by `_compute_contrast` from the labels, and never sees `dp`.
    diag_cum = np.concatenate(([0.0], np.cumsum(np.diag(corr))))

    def interval_w(u: int, v: int) -> float:
        sz = v - u
        if sz < min_block_size:
            return -np.inf
        total_sub = prefix[v, v] - prefix[u, v] - prefix[v, u] + prefix[u, u]
        diag_sub = diag_cum[v] - diag_cum[u]
        s_uv = 0.5 * (total_sub - diag_sub)
        p_uv = 0.5 * sz * (sz - 1)
        if p_uv == 0:
            return 0.0
        return float(s_uv * s_uv / p_uv)

    dp = np.full((n_blocks + 1, n + 1), -np.inf, dtype=float)
    parent = np.full((n_blocks + 1, n + 1), -1, dtype=int)

    for j in range(min_block_size, n + 1):
        dp[1, j] = interval_w(0, j)

    # Every (split point u, end j) pair of one block count k is scored as one array, rows u
    # and columns j. Each element goes through the same float64 operations, in the same
    # order, as `interval_w`, so the scores are bit-identical to a scalar loop's, and
    # `argmax` down a column returns the first maximum, as a loop keeping only strictly
    # greater values would. Pairs leaving a last block shorter than `min_block_size`, and
    # u whose `dp[k - 1, u]` is -inf, score -inf; a column that is -inf throughout records
    # (-inf, -1).
    diag_prefix = np.diagonal(prefix)
    for k in range(2, n_blocks + 1):
        j = np.arange(k * min_block_size, n + 1)
        if j.size == 0:
            continue
        u = np.arange((k - 1) * min_block_size, n - min_block_size + 1)
        sz = j[None, :] - u[:, None]
        total_sub = (
            diag_prefix[j][None, :] - prefix[np.ix_(u, j)] - prefix[np.ix_(j, u)].T
            + diag_prefix[u][:, None]
        )
        diag_sub = diag_cum[j][None, :] - diag_cum[u][:, None]
        s_uv = 0.5 * (total_sub - diag_sub)
        p_uv = 0.5 * sz * (sz - 1)
        w = np.divide(s_uv * s_uv, p_uv, out=np.zeros_like(s_uv), where=p_uv > 0)
        vals = dp[k - 1, u][:, None] + w
        vals[sz < min_block_size] = -np.inf
        best = np.argmax(vals, axis=0)
        best_val = vals[best, np.arange(j.size)]
        found = best_val > -np.inf
        dp[k, j] = np.where(found, best_val, -np.inf)
        parent[k, j] = np.where(found, u[best], -1)

    if dp[n_blocks, n] == -np.inf:
        labels = np.zeros(n, dtype=int)
        return ((0, n),), (), 0.0, labels

    cuts = []
    curr_j = n
    for k in range(n_blocks, 1, -1):
        u = int(parent[k, curr_j])
        cuts.append(u)
        curr_j = u
    cuts.reverse()

    boundaries = tuple(cuts)
    all_cuts = [0] + list(boundaries) + [n]
    block_bounds = tuple((all_cuts[i], all_cuts[i + 1]) for i in range(len(all_cuts) - 1))

    labels = np.zeros(n, dtype=int)
    for b_idx, (st, en) in enumerate(block_bounds):
        labels[st:en] = b_idx

    modularity = _compute_contrast(corr, labels)
    return block_bounds, boundaries, modularity, labels


def _label_change_boundaries(labels: np.ndarray) -> Tuple[int, ...]:
    """Positions along the probe where the cluster label changes."""
    return tuple(int(i) for i in range(1, len(labels)) if labels[i] != labels[i - 1])


def _partition_is_contiguous(labels: np.ndarray) -> bool:
    """Does every cluster occupy one unbroken span of the channel index?"""
    n_clusters = int(np.unique(labels).size)
    return len(_label_change_boundaries(labels)) == max(n_clusters - 1, 0)


def _unrestricted_partition(
    corr: np.ndarray,
    n_blocks: int,
) -> Tuple[Tuple[Tuple[int, int], ...], Tuple[int, ...], float, np.ndarray]:
    """Unrestricted agglomerative clustering on correlation distance matrix."""
    n = corr.shape[0]
    if n_blocks <= 1:
        labels = np.zeros(n, dtype=int)
        return ((0, n),), (), 0.0, labels

    d = np.clip(1.0 - corr, 0.0, 2.0)
    np.fill_diagonal(d, 0.0)
    d = 0.5 * (d + d.T)
    condensed_d = squareform(d, checks=False)
    z = linkage(condensed_d, method="average")
    raw_labels = fcluster(z, t=n_blocks, criterion="maxclust") - 1

    unique_labels: List[int] = []
    for lbl in raw_labels:
        if lbl not in unique_labels:
            unique_labels.append(lbl)
    remap = {old: new for new, old in enumerate(unique_labels)}
    labels = np.array([remap[lbl] for lbl in raw_labels], dtype=int)

    bounds = []
    for k in range(len(unique_labels)):
        members = np.where(labels == k)[0]
        if len(members) > 0:
            bounds.append((int(np.min(members)), int(np.max(members) + 1)))

    modularity = _compute_contrast(corr, labels)
    return tuple(bounds), (), modularity, labels


def xflip(
    data: np.ndarray,
    *,
    method: str = "pearson",
    contiguous: bool = True,
    n_blocks: Optional[int] = 2,
    min_block_size: int = 2,
    n_surrogates: int = 200,
    surrogate_method: str = "auto",
    alpha: float = 0.05,
    min_contrast: float = 0.05,
    min_boundary_drop: float = 0.05,
    channel_axis: int = 0,
    is_corr_matrix: Optional[bool] = None,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> XFlipResult:
    """Cross-Channel Laminar Correlation Profile (xFLIP).

    Evaluates cross-channel correlation blocks along laminar electrode array shafts,
    partitions contacts into contiguous laminar compartments via exact 1D dynamic
    programming, and tests boundary significance against temporal autocorrelation-preserving
    Fourier phase surrogates.

    Mathematical Estimator:
        1. Correlation Estimation:
           - Pearson: standard sample correlation across observations:
             :math:`r_{ij} = \\frac{\\sum_t (X_{it} - \\bar{X}_i)(X_{jt} - \\bar{X}_j)}{\\sigma_i \\sigma_j}`.
           - Spearman: rank-transformed sample correlation.
           - Partial: inverse covariance (precision) matrix normalization:
             :math:`r_{ij|\\text{rest}} = -\\frac{\\Theta_{ij}}{\\sqrt{\\Theta_{ii}\\Theta_{jj}}}`.
           - Precomputed: validates symmetry, unit diagonal, and bounds [-1, 1].
        2. Optimal Contiguous Partitioning:
           When `contiguous=True`, computes the globally optimal segmentation into `n_blocks`
           contiguous intervals :math:`[b_{k-1}, b_k)` via 1D dynamic programming maximizing
           :math:`\\sum_b S_b^2 / P_b`, with :math:`S_b = \\sum_{u \\le i < j < v} R_{ij}` and
           :math:`P_b` its pair count: the block-constant least-squares fit to the
           within-block correlations. No published method defines this objective; it is
           jnwb's own criterion, and no reference is cited for it. Before 0.2.7 the
           objective was :math:`\\sum_{u \\le i < j < v} (R_{ij} - \\bar{R})`, which moved
           the cut beside an uncorrelated background toward the middle of the probe.
        3. Statistical Null Testing:
           Constructs surrogates preserving each channel's empirical power spectrum and
           temporal autocorrelation :math:`R_{cc}(\\tau)` via independent Fourier phase
           randomization (when raw time-series data is provided), or channel identity permutation
           (when a precomputed correlation matrix is provided).
        4. Monte Carlo P-value Resolution:
           Evaluates partition contrast :math:`Q = \\bar{r}_{\\text{within}} - \\bar{r}_{\\text{between}}`:
           :math:`p = \\frac{1 + \\sum_{s=1}^S \\mathbb{I}(Q_s \\ge Q - \\epsilon)}{1 + S}`,
           with :math:`\\epsilon` 100 machine epsilons, so a surrogate that reproduces
           :math:`Q` with its correlations summed in another order counts.
           No p-value can resolve to 0.0 under finite surrogate sampling.
           Under `n_blocks=None`, the observation and the surrogates are S + 1 draws; each
           draw's p at each count is the fraction of draws whose contrast is at least its
           own, its statistic is the smallest of those p over the counts, and the omnibus p
           is the fraction of draws whose statistic is at most the observation's.

    Args:
        data: 2D array of raw time series `(n_channels, n_samples)` or precomputed
            correlation matrix `(n_channels, n_channels)`.
        method: Correlation method for raw time series: `'pearson'`, `'spearman'`,
            or `'partial'` (default: `'pearson'`).
        contiguous: If True, partitions into contiguous contact segments along the probe
            shaft (default: True). If False, performs unrestricted clustering.
        n_blocks: Number of blocks to partition into (default: 2), or None to choose among
            the counts 2..min(4, n_channels // min_block_size). Each count is partitioned as
            in step 2 and tested against the same surrogates; the count with the smallest p
            is reported, and the omnibus p repeats that choice on every surrogate (step 4),
            so it accounts for the choice. Among counts tied at the smallest p, the one whose
            observed contrast lies the most surrogate standard deviations above the surrogate
            mean wins, then the smallest count. When a count's partition beats every
            surrogate, every count sits at the floor and the standardised contrast decides;
            the omnibus p does not depend on the tie-break. The per-boundary p-values are the
            chosen count's own and are not adjusted for the choice. With `n_surrogates=0`
            there is no p to choose by, and count 2 is reported. Measured on 16 to 18 contacts
            at a within-block correlation of 0.8, the true count is recovered up to a shared
            background correlation of 0.3; at 0.5, three blocks of 6 were cut into four and
            rejected. Costs about one fixed-count call at each candidate count.
        min_block_size: Minimum channel count required per block (default: 2).
        n_surrogates: Number of Monte Carlo surrogate iterations (default: 200). If 0,
            surrogate p-values are not computed (NaN) and the result is never accepted:
            not testing is not the same as passing, and `rejection_reason` says so.
        surrogate_method: `'auto'` (default), `'autocorr_preserving'`, or `'permute_channels'`.
        alpha: Significance threshold for omnibus surrogate test (default: 0.05).
        min_contrast: Minimum modularity contrast required for acceptance (default: 0.05).
        min_boundary_drop: Minimum drop between within-block neighbor correlations and cross-boundary
            correlation required for boundary acceptance (default: 0.05). Guards against false
            partitioning of continuous smooth spatial gradients without sharp boundaries.
        channel_axis: Axis corresponding to channels in raw time-series input (default: 0).
        is_corr_matrix: Explicit boolean override specifying whether `data` is a precomputed
            correlation matrix. If None, auto-detected from shape, symmetry, and values.
        rng: An int seed, a NumPy Generator, or None for fresh OS entropy. The entropy
            used is returned as `surrogate_seed_entropy` for an int or None.

    Returns:
        XFlipResult container with `block_bounds`, `boundaries`, `labels`, `modularity`,
        `p_values`, `accepted`, `rejection_reason` and `surrogate_seed_entropy`.

    Raises:
        ValueError: If data is non-2D, non-finite, ill-conditioned/non-symmetric precomputed
            matrix, or contains invalid configuration parameters.
        TypeError: If `rng` is not an int, a Generator or None; a float or bool seed is
            refused rather than truncated.
    """
    if method not in ("pearson", "spearman", "partial"):
        raise ValueError(
            f"Unknown correlation method '{method}'. Supported methods: 'pearson', 'spearman', 'partial'."
        )
    if min_block_size < 1:
        raise ValueError(f"min_block_size must be >= 1, got {min_block_size}")
    if n_blocks is not None and n_blocks < 1:
        raise ValueError(f"n_blocks must be >= 1, got {n_blocks}")
    if n_surrogates < 0:
        raise ValueError(f"n_surrogates must be >= 0, got {n_surrogates}")
    # `is_sig = p <= alpha` is vacuously true for alpha >= 1, and the two thresholds were
    # equally unchecked: alpha=5.0 with min_boundary_drop=0.0 accepted a smooth spatial
    # gradient in 15 of 15 seeds. `zflip` already range-checks the identical parameter.
    if not (np.isfinite(alpha) and 0.0 < alpha < 1.0):
        raise ValueError(f"alpha must lie in (0, 1); got {alpha}.")
    if not (np.isfinite(min_contrast) and min_contrast >= 0.0):
        raise ValueError(f"min_contrast must be a finite value >= 0; got {min_contrast}.")
    if not (np.isfinite(min_boundary_drop) and min_boundary_drop >= 0.0):
        raise ValueError(
            f"min_boundary_drop must be a finite value >= 0; got {min_boundary_drop}."
        )
    if min_block_size < 1:
        raise ValueError(f"min_block_size must be >= 1, got {min_block_size}")
    gen, seed_entropy = surrogate_rng(rng, "xflip")

    arr = np.asarray(data)
    if arr.ndim != 2:
        raise ValueError(f"data must be a 2D array, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("Input data contains non-finite values (NaN or Inf).")

    # Determine whether input is a precomputed correlation matrix
    if is_corr_matrix is True:
        if arr.shape[0] != arr.shape[1]:
            raise ValueError(f"is_corr_matrix=True requires a square (n_channels, n_channels) matrix, got {arr.shape}")
        if not np.allclose(arr, arr.T, atol=1e-4):
            raise ValueError("Precomputed correlation matrix must be symmetric.")
        if not np.allclose(np.diag(arr), 1.0, atol=1e-3):
            raise ValueError("Precomputed correlation matrix diagonal elements must be 1.0.")
        if np.any(arr < -1.0 - 1e-4) or np.any(arr > 1.0 + 1e-4):
            raise ValueError("Precomputed correlation matrix elements must be in [-1, 1].")
        is_corr = True
    elif is_corr_matrix is False:
        is_corr = False
    else:
        # Auto-detect
        if (
            arr.shape[0] == arr.shape[1]
            and np.allclose(arr, arr.T, atol=1e-4)
            and np.allclose(np.diag(arr), 1.0, atol=1e-3)
            and np.all(arr >= -1.0 - 1e-4)
            and np.all(arr <= 1.0 + 1e-4)
        ):
            is_corr = True
        else:
            is_corr = False

    if not is_corr:
        if channel_axis == 1:
            raw_data = arr.T
        elif channel_axis == 0:
            raw_data = arr
        else:
            raise ValueError(f"channel_axis must be 0 or 1, got {channel_axis}")
        n_channels, n_samples = raw_data.shape
        if n_samples <= 1:
            raise ValueError(f"Raw time-series must have at least 2 samples, got {n_samples}")
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = _compute_correlation_matrix(raw_data, method)
        resolved_method = method
        flat = np.flatnonzero(np.ptp(raw_data, axis=1) == 0)
        if flat.size > 0:
            # A zero-variance channel has no correlation with any other. Its entries were set to
            # 0, "uncorrelated", which the partition search reads as a block boundary.
            corr = corr.copy()
            corr[flat, :] = np.nan
            corr[:, flat] = np.nan
            return XFlipResult(
                corr_matrix=corr,
                block_bounds=((0, n_channels),),
                boundaries=(),
                labels=np.zeros(n_channels, dtype=int),
                modularity=np.nan,
                p_values={"omnibus": np.nan},
                accepted=False,
                rejection_reason=(
                    f"Zero-variance channel(s) {flat.tolist()} have undefined correlation; "
                    "mask or remove them before partitioning."
                ),
                method=resolved_method,
                n_channels=n_channels,
                n_blocks=1,
            )
    else:
        raw_data = None
        corr = np.clip(arr.copy(), -1.0, 1.0)
        n_channels = corr.shape[0]
        resolved_method = "precomputed"

    # Resolve surrogate method
    if surrogate_method == "auto":
        eff_surrogate_method = "autocorr_preserving" if raw_data is not None else "permute_channels"
    elif surrogate_method in ("autocorr_preserving", "phase_randomize"):
        if raw_data is None:
            raise ValueError(
                "surrogate_method='autocorr_preserving' requires raw time-series data to evaluate "
                "temporal autocorrelation; got a precomputed correlation matrix. "
                "Pass raw data or use surrogate_method='permute_channels'."
            )
        eff_surrogate_method = "autocorr_preserving"
    elif surrogate_method in ("permute_channels", "channel_permute"):
        eff_surrogate_method = "permute_channels"
    else:
        raise ValueError(
            f"Unknown surrogate_method '{surrogate_method}'. "
            "Supported: 'auto', 'autocorr_preserving', 'permute_channels'."
        )

    # Check structural feasibility
    target_k = 2 if n_blocks is None else n_blocks
    if n_channels < target_k * min_block_size:
        labels = np.zeros(n_channels, dtype=int)
        return XFlipResult(
            corr_matrix=corr,
            block_bounds=((0, n_channels),),
            boundaries=(),
            labels=labels,
            modularity=0.0,
            p_values={"omnibus": np.nan},
            accepted=False,
            rejection_reason=(
                f"Total channels ({n_channels}) insufficient for {target_k} blocks "
                f"with min_block_size {min_block_size} (requires >= {target_k * min_block_size})."
            ),
            method=resolved_method,
            n_channels=n_channels,
            n_blocks=1,
        )

    def partition(matrix: np.ndarray, k: int):
        if contiguous:
            return _optimal_contiguous_partition(matrix, k, min_block_size)
        return _unrestricted_partition(matrix, k)

    def local_labels(bounds, b):
        """The two blocks either side of boundary `b`, as (start, end, labels)."""
        left_st = 0
        right_en = n_channels
        for bb_st, bb_en in bounds:
            if bb_en == b:
                left_st = bb_st
            elif bb_st == b:
                right_en = bb_en
                break
        lbl = np.zeros(right_en - left_st, dtype=int)
        lbl[b - left_st:] = 1
        return left_st, right_en, lbl

    # INTENTIONAL BREAK (0.2.7): under `n_blocks=None` the count is the candidate with the
    # smallest surrogate p, and the same choice is repeated on every surrogate, so the
    # reported p accounts for it. The count was the one with the highest contrast, and the p
    # ignored the choice: on an AR(1) null it fell at or below 0.05 about twice as often as
    # at a fixed count.
    # Counts and p can change on existing data.
    if n_blocks is not None:
        candidates: Tuple[int, ...] = (target_k,)
    else:
        candidates = tuple(range(2, min(4, n_channels // min_block_size) + 1))
    observed = [partition(corr, k) for k in candidates]
    local_obs = [
        {b: _compute_contrast(corr[st:en, st:en], lbl)
         for b in bnd for st, en, lbl in [local_labels(bb, b)]}
        for bb, bnd, _, _ in observed
    ]

    # Monte Carlo surrogate null testing
    p_values: Dict[str, float] = {}
    chosen = 0

    if n_surrogates > 0:
        surr_q_all = np.empty((n_surrogates, len(candidates)), dtype=float)
        boundary_exceed = [{b: 0 for b in part[1]} for part in observed]

        for s_idx in range(n_surrogates):
            if eff_surrogate_method == "autocorr_preserving":
                surr_raw = _surrogate_phase_randomize(raw_data, gen)
                surr_corr = _compute_correlation_matrix(surr_raw, method)
            else:
                if contiguous:
                    perm = gen.permutation(n_channels)
                    surr_corr = corr[perm, :][:, perm]
                else:
                    triu_idx = np.triu_indices(n_channels, k=1)
                    perm_vals = gen.permutation(corr[triu_idx])
                    surr_corr = np.eye(n_channels, dtype=float)
                    surr_corr[triu_idx] = perm_vals
                    surr_corr[triu_idx[1], triu_idx[0]] = perm_vals

            for i, k in enumerate(candidates):
                surr_q_all[s_idx, i] = partition(surr_corr, k)[2]
                bb = observed[i][0]
                for b in observed[i][1]:
                    st, en, lbl = local_labels(bb, b)
                    boundary_exceed[i][b] += _count_at_least_as_extreme(
                        [_compute_contrast(surr_corr[st:en, st:en], lbl)], local_obs[i][b],
                        "greater", atol=_TIE_RTOL,
                    )

        obs_q_all = np.array([part[2] for part in observed], dtype=float)
        chosen, p_omnibus = _select_count_by_min_p(obs_q_all, surr_q_all)
        p_values["omnibus"] = p_omnibus
        for b in observed[chosen][1]:
            p_values[f"boundary_{b}"] = float(
                (1 + boundary_exceed[chosen][b]) / (1 + n_surrogates)
            )
    else:
        p_values["omnibus"] = np.nan

    # With no surrogates there is no p to choose by, and the smallest candidate is reported.
    target_k = candidates[chosen]
    b_bounds, boundaries, obs_q, labels = observed[chosen]

    # Evaluate boundary drops (local discontinuity across candidate cuts)
    # On the unrestricted path the partition carries no boundaries of its own, but a
    # partition that happens to be contiguous has the same cuts the DP would have produced.
    drop_boundaries = boundaries
    if not contiguous and _partition_is_contiguous(labels):
        drop_boundaries = _label_change_boundaries(labels)

    boundary_drops: Dict[int, float] = {}
    if len(drop_boundaries) > 0:
        for b in drop_boundaries:
            within_neighbors = []
            if b >= 2:
                within_neighbors.append(float(corr[b - 2, b - 1]))
            if b < n_channels - 1:
                within_neighbors.append(float(corr[b, b + 1]))
            mean_near = float(np.mean(within_neighbors)) if len(within_neighbors) > 0 else 1.0
            cross_val = float(corr[b - 1, b])
            boundary_drops[b] = float(mean_near - cross_val)

    # Acceptance determination
    # `n_surrogates=0` means the significance test was not performed, which is not the
    # same as passing it. Assuming True here accepted pure noise in 119 of 120 seeds
    # (contrast and boundary-drop gates opened), and the surrogate test would have rejected
    # 113 of those, with omnibus p running as high as 0.87 -- while `p_values['omnibus']`
    # was reported as NaN. `zflip` already documents the opposite contract: accepted only
    # if the surrogate test was performed AND significant. This now matches it.
    surrogates_run = n_surrogates > 0
    is_sig = bool(p_values["omnibus"] <= alpha) if surrogates_run else False
    has_contrast = (obs_q >= min_contrast)
    has_blocks = (target_k >= 2)
    # The gradient gate. It used to run only under `contiguous`, while `has_drop` was
    # initialised True, so the unrestricted path silently *skipped* it rather than failing
    # it -- the same "not tested is not passed" error the `n_surrogates=0` contract above
    # exists to prevent. A smooth spatial gradient was accepted in 15 of 15 seeds there
    # where the contiguous path accepted 0 of 15.
    #
    # The statistic is a *local* discontinuity, and locality is the point: a smooth
    # exponential decay separates perfectly well at the cluster level (within-minus-between
    # is 0.3285 on the gradient null), so only the drop across the cut distinguishes a real
    # boundary from a gradient. It is therefore applied exactly when a gradient could have
    # produced the partition -- that is, when the partition is contiguous. A genuinely
    # interleaved partition cannot come from a spatial gradient, so the gate does not apply
    # and `unrestricted_partition_is_interleaved` records that it did not.
    has_drop = True
    if min_boundary_drop > 0.0 and len(drop_boundaries) > 0:
        for b, drop_val in boundary_drops.items():
            if drop_val < min_boundary_drop:
                has_drop = False
                break

    if is_sig and has_contrast and has_blocks and has_drop:
        accepted = True
        rejection_reason = None
    else:
        accepted = False
        reasons = []
        if not surrogates_run:
            reasons.append(
                "Surrogate significance test not performed (n_surrogates=0); acceptance "
                "requires the test to run"
            )
        elif not is_sig:
            reasons.append(f"Non-significant modularity vs surrogates (p = {p_values['omnibus']:.4f} > {alpha})")
        if not has_contrast:
            reasons.append(f"Modularity contrast ({obs_q:.4f}) below min_contrast ({min_contrast})")
        if not has_blocks:
            reasons.append(f"Fewer than 2 blocks detected (k = {target_k})")
        if not has_drop:
            reasons.append(f"Boundary drop below min_boundary_drop ({min_boundary_drop})")
        rejection_reason = "; ".join(reasons)

    return XFlipResult(
        corr_matrix=corr,
        block_bounds=b_bounds,
        boundaries=boundaries,
        labels=labels,
        modularity=float(obs_q),
        p_values=p_values,
        accepted=accepted,
        rejection_reason=rejection_reason,
        method=resolved_method,
        n_channels=n_channels,
        n_blocks=target_k if accepted else 1,
        boundary_drops=boundary_drops,
        surrogate_seed_entropy=seed_entropy if surrogates_run else None,
    )
