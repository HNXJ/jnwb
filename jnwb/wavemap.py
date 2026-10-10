"""
jnwb.wavemap -- WaveMAP: graph clustering of mean extracellular waveforms.

WaveMAP (Lee et al. 2021) builds the fuzzy k-nearest-neighbor graph of UMAP (McInnes et al.
2018) over normalized mean waveforms, one row per unit, and partitions that graph with Louvain
community detection (Blondel et al. 2008). The 2-d UMAP embedding is for display; it does not
enter the clustering.

Four functions, composed in this order:

1. `align_waveforms` cuts each mean waveform to a fixed window around its trough.
2. `normalize_waveforms` removes each row's mean and scales it so its largest absolute value
   is 1 (Lee et al. 2021, Methods; Lee et al. 2023, steps 9-10).
3. `wavemap` builds the graph and returns the Louvain labels, the modularity of the partition
   and, on request, the embedding.
4. `wavemap_resolution_sweep` repeats the clustering over random subsets and resolutions, the
   procedure Lee et al. (2021, Fig. 3B) used to choose the resolution.

None of them decides which units are kept. `align_waveforms` reports the rows whose window
leaves the stored samples and never pads them.

The resolution follows the published method's convention, the Markov time of Lambiotte et al.
(2008) as implemented by ``cylouvain``: a larger resolution gives fewer, larger clusters.
``networkx.community.louvain_communities`` takes the reciprocal (its ``resolution`` multiplies
the null-model term), so `wavemap` passes ``1 / resolution`` to it. ``python-louvain`` 0.16
(``community.best_partition``), used in some WaveMAP tutorials, agrees with the published
convention only at a resolution of 1.

`wavemap` and `wavemap_resolution_sweep` need the ``wavemap`` extra (``umap-learn`` and
``networkx``): ``pip install jnwb[wavemap]``. `align_waveforms` and `normalize_waveforms` need
only NumPy.

References:
    Lee, E. K., et al. (2021). Non-linear dimensionality reduction on extracellular waveforms
    reveals cell type diversity in premotor cortex. eLife 10, e67490. doi:10.7554/eLife.67490

    Lee, K., Carr, N., Perliss, A. & Chandrasekaran, C. (2023). WaveMAP for identifying
    putative cell types from in vivo electrophysiology. STAR Protocols 4, 102320.
    doi:10.1016/j.xpro.2023.102320

    McInnes, L., Healy, J. & Melville, J. (2018). UMAP: Uniform manifold approximation and
    projection for dimension reduction. arXiv:1802.03426.
    doi:10.48550/arXiv.1802.03426

    Blondel, V. D., et al. (2008). Fast unfolding of communities in large networks. Journal
    of Statistical Mechanics P10008. doi:10.1088/1742-5468/2008/10/P10008

    Lambiotte, R., Delvenne, J.-C. & Barahona, M. (2008). Laplacian dynamics and multiscale
    modular structure in networks. arXiv:0812.1770.
    doi:10.48550/arXiv.0812.1770
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from ._rng import DEFAULT_SEED, RNGLike, resolve_rng

__all__ = [
    "WaveMAPResult",
    "align_waveforms",
    "normalize_waveforms",
    "wavemap",
    "wavemap_resolution_sweep",
]

_EXTRA_MESSAGE = "{func}: needs umap-learn and networkx; install them with `pip install jnwb[wavemap]`."


def _waveform_matrix(waveforms, func_name: str, *, min_rows: int = 1) -> np.ndarray:
    """``waveforms`` as a float ``(n_units, n_samples)`` array, or ValueError."""
    w = np.asarray(waveforms, dtype=float)
    if w.ndim != 2 or w.shape[0] < min_rows or w.shape[1] < 2:
        raise ValueError(
            f"{func_name}: waveforms must be (n_units, n_samples) with at least {min_rows} "
            f"unit(s) and two samples; got shape {w.shape}."
        )
    return w


def _resolution(value, func_name: str) -> float:
    try:
        r = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{func_name}: resolution must be a finite positive number; got {value!r}.")
    if not (np.isfinite(r) and r > 0):
        raise ValueError(f"{func_name}: resolution must be a finite positive number; got {value!r}.")
    return r


def _require_extra(func_name: str):
    try:
        import networkx  # noqa: F401
        import umap  # noqa: F401
    except ImportError as exc:
        raise ImportError(_EXTRA_MESSAGE.format(func=func_name)) from exc


def align_waveforms(waveforms, fs: float, *, pre_s: float = 0.0004,
                    post_s: float = 0.0012) -> Tuple[np.ndarray, np.ndarray]:
    """Cut each mean waveform to the window ``[trough - pre_s, trough + post_s)``.

    The trough is the row's global minimum (its first sample when tied), at the resolution of
    one sample. The defaults are the window of Lee et al. (2021, Methods): 1.6 ms with 0.4 ms
    before the trough, 48 samples at 30 kHz. A row whose window leaves its stored samples, or
    that holds a NaN or an infinity, is returned as NaN with ``valid`` False; it is never
    padded or shifted.

    Args:
        waveforms: Mean waveforms ``(n_units, n_samples)``, one channel per unit (for example
            the peak channel `waveform_features` reports).
        fs: Sampling rate in Hz.
        pre_s: Window before the trough, in seconds; ``round(pre_s * fs)`` samples.
        post_s: Window from the trough on, in seconds; ``round(post_s * fs)`` samples.

    Returns:
        ``(aligned, valid)``: ``aligned`` is ``(n_units, n_pre + n_post)`` with the trough at
        column ``n_pre``; ``valid`` is a boolean ``(n_units,)``.

    Raises:
        ValueError: If `waveforms` is not 2-D with two or more samples, `fs` is not finite and
            positive, `pre_s` or `post_s` is negative or not finite, or the window has no
            sample.

    References:
        Lee, E. K., et al. (2021). eLife 10, e67490. doi:10.7554/eLife.67490
    """
    name = "align_waveforms"
    w = _waveform_matrix(waveforms, name)
    fs = float(fs)
    if not (np.isfinite(fs) and fs > 0):
        raise ValueError(f"{name}: fs must be a finite positive number; got {fs!r}.")
    for label, v in (("pre_s", pre_s), ("post_s", post_s)):
        if not (np.isfinite(v) and v >= 0):
            raise ValueError(f"{name}: {label} must be finite and >= 0; got {v!r}.")
    n_pre = int(round(pre_s * fs))
    n_post = int(round(post_s * fs))
    if n_pre + n_post < 1:
        raise ValueError(f"{name}: the window holds no sample at fs={fs} Hz.")
    finite = np.all(np.isfinite(w), axis=1)
    trough = np.argmin(np.where(np.isfinite(w), w, np.inf), axis=1)
    valid = finite & (trough - n_pre >= 0) & (trough + n_post <= w.shape[1])
    aligned = np.full((w.shape[0], n_pre + n_post), np.nan)
    offsets = np.arange(-n_pre, n_post)
    rows = np.flatnonzero(valid)
    aligned[rows] = w[rows[:, None], trough[rows, None] + offsets[None, :]]
    return aligned, valid


def normalize_waveforms(waveforms, *, subtract_mean: bool = True) -> np.ndarray:
    """Scale each row so its largest absolute value is 1, after removing its mean.

    The normalization of Lee et al. (2021, Methods) and Lee et al. (2023, steps 9-10): per
    unit, subtract the mean over samples (``subtract_mean=True``), then divide by the largest
    absolute value, so amplitude, which falls with distance from the electrode, does not
    drive the clustering. A row that is constant after the subtraction, or holds a NaN or an
    infinity, is returned as NaN.

    Args:
        waveforms: ``(n_units, n_samples)``.
        subtract_mean: Remove each row's mean first.

    Returns:
        ``(n_units, n_samples)`` float array.

    Raises:
        ValueError: If `waveforms` is not 2-D with two or more samples.

    References:
        Lee, E. K., et al. (2021). eLife 10, e67490. doi:10.7554/eLife.67490
        Lee, K., et al. (2023). STAR Protocols 4, 102320. doi:10.1016/j.xpro.2023.102320
    """
    w = _waveform_matrix(waveforms, "normalize_waveforms")
    if subtract_mean:
        w = w - w.mean(axis=1, keepdims=True)
    scale = np.max(np.abs(w), axis=1, keepdims=True)
    ok = np.isfinite(scale) & (scale > 0)
    return np.where(ok, w / np.where(ok, scale, 1.0), np.nan)


@dataclass(frozen=True)
class WaveMAPResult:
    """What `wavemap` returns.

    Attributes:
        labels: ``(n_units,)`` int cluster labels, 0 for the largest cluster, then by
            decreasing size (ties by the smallest member row).
        n_clusters: Number of clusters.
        modularity: Newman modularity (resolution 1) of the partition on the UMAP graph, the
            score of Lee et al. (2021, Fig. 3B).
        resolution: The Markov-time resolution used.
        embedding: ``(n_units, 2)`` UMAP embedding, or None when not requested.
        graph: The UMAP fuzzy graph, a ``scipy.sparse`` ``(n_units, n_units)`` matrix.
        parameters: ``n_neighbors``, ``min_dist``, ``metric`` and the two integer seeds drawn
            from `rng` (``umap_seed``, ``louvain_seed``).
    """

    labels: np.ndarray
    n_clusters: int
    modularity: float
    resolution: float
    embedding: Optional[np.ndarray]
    graph: Any
    parameters: Dict[str, Any]


def _seeds(gen: np.random.Generator) -> Tuple[int, int]:
    return int(gen.integers(0, 2**31 - 1)), int(gen.integers(0, 2**31 - 1))


def _louvain(graph, resolution: float, seed: int) -> Tuple[np.ndarray, float]:
    import networkx as nx

    G = nx.from_scipy_sparse_array(graph)
    comms = nx.community.louvain_communities(G, weight="weight", resolution=1.0 / resolution,
                                             seed=seed)
    comms = sorted(comms, key=lambda c: (-len(c), min(c)))
    labels = np.empty(G.number_of_nodes(), dtype=int)
    for i, c in enumerate(comms):
        labels[list(c)] = i
    return labels, float(nx.community.modularity(G, comms, weight="weight"))


def _umap(x: np.ndarray, n_neighbors: int, min_dist: float, metric: str, seed: int):
    import umap

    return umap.UMAP(n_neighbors=n_neighbors, min_dist=min_dist, metric=metric,
                     random_state=seed).fit(x)


def wavemap(waveforms, *, resolution: float, n_neighbors: int = 20, min_dist: float = 0.1,
            metric: str = "euclidean", embedding: bool = True,
            rng: RNGLike = DEFAULT_SEED) -> WaveMAPResult:
    """Cluster normalized mean waveforms on their UMAP graph with Louvain (Lee et al. 2021).

    Input class: one row per unit, already aligned and normalized (`align_waveforms`, then
    `normalize_waveforms`); rows with NaN are refused, so drop the rows ``valid`` marks False.
    The UMAP graph is built with `n_neighbors`, `min_dist` and `metric`, and Louvain runs on
    it at `resolution` in the published convention (larger, fewer clusters; module
    docstring). The defaults of `n_neighbors` and `min_dist` are those of Lee et al. (2021,
    Table 1), who chose a resolution of 1.5 by maximizing modularity with every cluster
    above 20 units; Lee et al. (2023) used 2.0 and n_neighbors 15. There is no default
    resolution: choose it from `wavemap_resolution_sweep` and report it.

    Both stochastic stages draw their integer seed from `rng`, so an ``int`` repeats the
    result on one installation; UMAP and Louvain versions may still differ across installs.
    The embedding comes from ``UMAP.transform`` of the input, as in the published code.

    Args:
        waveforms: ``(n_units, n_samples)`` finite array, ``n_units > n_neighbors``.
        resolution: Louvain resolution (Markov time), finite and positive.
        n_neighbors: UMAP neighborhood size.
        min_dist: UMAP minimum distance in the embedding; it does not change the graph.
        metric: UMAP input metric.
        embedding: Also compute the 2-d embedding.
        rng: Seed or Generator for the UMAP and Louvain seeds.

    Returns:
        `WaveMAPResult`.

    Raises:
        ValueError: If `waveforms` is not 2-D, holds a NaN or an infinity, or has no more
            rows than `n_neighbors`; or if `resolution` is not finite and positive.
        ImportError: Without the ``wavemap`` extra.
        TypeError: If `rng` is not an int, a Generator or None.

    References:
        Lee, E. K., et al. (2021). eLife 10, e67490. doi:10.7554/eLife.67490
        Lee, K., et al. (2023). STAR Protocols 4, 102320. doi:10.1016/j.xpro.2023.102320
        McInnes, L., Healy, J. & Melville, J. (2018). arXiv:1802.03426.
        doi:10.48550/arXiv.1802.03426
        Blondel, V. D., et al. (2008). J. Stat. Mech. P10008. doi:10.1088/1742-5468/2008/10/P10008
        Lambiotte, R., Delvenne, J.-C. & Barahona, M. (2008). arXiv:0812.1770.
        doi:10.48550/arXiv.0812.1770
    """
    name = "wavemap"
    x = _waveform_matrix(waveforms, name)
    if not np.all(np.isfinite(x)):
        raise ValueError(f"{name}: waveforms hold {int(np.sum(~np.isfinite(x)))} NaN or infinite "
                         "value(s); drop the rows align_waveforms marks invalid.")
    if x.shape[0] <= int(n_neighbors):
        raise ValueError(f"{name}: {x.shape[0]} units is not more than n_neighbors={n_neighbors}.")
    resolution = _resolution(resolution, name)
    gen = resolve_rng(rng, func_name=name)
    _require_extra(name)
    umap_seed, louvain_seed = _seeds(gen)
    reducer = _umap(x, int(n_neighbors), float(min_dist), metric, umap_seed)
    labels, q = _louvain(reducer.graph_, resolution, louvain_seed)
    emb = np.asarray(reducer.transform(x)) if embedding else None
    return WaveMAPResult(labels=labels, n_clusters=int(labels.max()) + 1, modularity=q,
                         resolution=resolution, embedding=emb, graph=reducer.graph_,
                         parameters={"n_neighbors": int(n_neighbors), "min_dist": float(min_dist),
                                     "metric": metric, "umap_seed": umap_seed,
                                     "louvain_seed": louvain_seed})


def wavemap_resolution_sweep(waveforms, resolutions: Sequence[float], *, n_runs: int = 25,
                             fraction: float = 0.8, n_neighbors: int = 20,
                             metric: str = "euclidean",
                             rng: RNGLike = DEFAULT_SEED) -> Dict[str, np.ndarray]:
    """Modularity and cluster count across resolutions, over random subsets of units.

    The procedure of Lee et al. (2021, Fig. 3B; defaults from its caption): each of `n_runs`
    runs draws ``floor(fraction * n_units)`` units without replacement and a new UMAP seed,
    builds one graph, and clusters it at every resolution. Lee et al. chose the resolution
    that maximized modularity while every cluster held more than 20 units; the sweep reports
    the smallest cluster of each run so that rule can be applied.

    Args:
        waveforms: Aligned, normalized ``(n_units, n_samples)``, as for `wavemap`.
        resolutions: Resolutions to test, each finite and positive.
        n_runs: Number of random subsets.
        fraction: Fraction of units per subset, in ``(0, 1]``.
        n_neighbors: UMAP neighborhood size.
        metric: UMAP input metric, as for `wavemap`.
        rng: Seed or Generator for the subsets and every seed.

    Returns:
        Dict with ``resolution`` ``(R,)`` and, each ``(R, n_runs)``, ``modularity``,
        ``n_clusters`` and ``min_cluster_size``.

    Raises:
        ValueError: As `wavemap`; also if `resolutions` is empty, `n_runs` < 1, `fraction` is
            outside ``(0, 1]``, or a subset would hold no more units than `n_neighbors`.
        ImportError: Without the ``wavemap`` extra.

    References:
        Lee, E. K., et al. (2021). eLife 10, e67490. doi:10.7554/eLife.67490
        McInnes, L., Healy, J. & Melville, J. (2018). arXiv:1802.03426.
        doi:10.48550/arXiv.1802.03426
        Blondel, V. D., et al. (2008). J. Stat. Mech. P10008. doi:10.1088/1742-5468/2008/10/P10008
        Lambiotte, R., Delvenne, J.-C. & Barahona, M. (2008). arXiv:0812.1770.
        doi:10.48550/arXiv.0812.1770
    """
    name = "wavemap_resolution_sweep"
    x = _waveform_matrix(waveforms, name)
    if not np.all(np.isfinite(x)):
        raise ValueError(f"{name}: waveforms hold NaN or infinite values.")
    res = np.array([_resolution(r, name) for r in resolutions], dtype=float)
    if res.size == 0:
        raise ValueError(f"{name}: resolutions is empty.")
    if int(n_runs) < 1:
        raise ValueError(f"{name}: n_runs must be >= 1; got {n_runs!r}.")
    if not (0 < float(fraction) <= 1):
        raise ValueError(f"{name}: fraction must be in (0, 1]; got {fraction!r}.")
    n_sub = int(np.floor(float(fraction) * x.shape[0]))
    if n_sub <= int(n_neighbors):
        raise ValueError(f"{name}: a subset of {n_sub} units is not more than n_neighbors={n_neighbors}.")
    gen = resolve_rng(rng, func_name=name)
    _require_extra(name)
    q = np.zeros((res.size, int(n_runs)))
    k = np.zeros((res.size, int(n_runs)), dtype=int)
    smallest = np.zeros((res.size, int(n_runs)), dtype=int)
    for r in range(int(n_runs)):
        idx = gen.permutation(x.shape[0])[:n_sub]
        umap_seed, louvain_seed = _seeds(gen)
        graph = _umap(x[idx], int(n_neighbors), 0.1, metric, umap_seed).graph_
        for i, t in enumerate(res):
            labels, q[i, r] = _louvain(graph, float(t), louvain_seed)
            counts = np.bincount(labels)
            k[i, r], smallest[i, r] = counts.size, counts.min()
    return {"resolution": res, "modularity": q, "n_clusters": k, "min_cluster_size": smallest}
