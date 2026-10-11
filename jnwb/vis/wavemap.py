"""
jnwb.vis.wavemap -- The WaveMAP display: the embedding by cluster beside each cluster's mean waveform.

- ``plot_wavemap``: panel A is the 2-d UMAP embedding of a `jnwb.wavemap` result, one trace per
  cluster; panel B is each cluster's mean of the normalized waveforms, in the same color.
"""

from __future__ import annotations

import numpy as np
import plotly.colors
import plotly.graph_objects as go

from ..wavemap import WaveMAPResult, normalize_waveforms
from .canvas import PlotlyPublicationCanvas
from .theme import NATURE_ACCENTS, TOL_MUTED, configure_axis

# The smallest palette that gives every cluster its own color; a static export has no hover text,
# so a reused color would merge two clusters in both panels.
_PALETTES = (NATURE_ACCENTS, TOL_MUTED, plotly.colors.qualitative.Dark24)


def _layout_key(axis_name: str) -> str:
    """Layout attribute of a Plotly axis name: ``x`` -> ``xaxis``, ``y2`` -> ``yaxis2``."""
    return f"{axis_name[0]}axis{axis_name[1:]}"


def _palette(n_clusters: int) -> list:
    """One distinct color per cluster, or ValueError when no palette holds that many."""
    for palette in _PALETTES:
        if n_clusters <= len(palette):
            return list(palette)
    raise ValueError(f"plot_wavemap: {n_clusters} clusters exceed the {len(_PALETTES[-1])} "
                     "distinct colors available; cluster at a coarser resolution.")


def plot_wavemap(result: WaveMAPResult, waveforms, *, layout: str = "1.5col",
                 height_mm: float = 80.0) -> PlotlyPublicationCanvas:
    """Draw a WaveMAP result: the embedding colored by cluster, and each cluster's mean waveform.

    Call it as ``plot_wavemap(result, waveforms)``; ``layout`` and ``height_mm`` are keyword-only.

    Panel A (``tags`` "A") scatters ``result.embedding`` by ``result.labels``. Panel B (``B``)
    draws, for each cluster, the mean over its units of ``normalize_waveforms(waveforms)``, in the
    color of the cluster in panel A. The mean is the only value computed here; the embedding
    and the labels are the result's.

    Args:
        result: What `jnwb.wavemap` returned with ``embedding=True``.
        waveforms: ``(n_units, n_samples)`` aligned waveforms, one row per unit in the order
            `result` clustered, un-normalized (`normalize_waveforms` is applied here).
        layout: Canvas width preset, as for `PlotlyPublicationCanvas`.
        height_mm: Canvas height in mm.

    Returns:
        The `PlotlyPublicationCanvas` with both panels. Write it with ``canvas.fig`` or seal it
        with ``canvas.save_and_seal``.

    Raises:
        ValueError: If ``result.embedding`` is None, if the result or `waveforms` holds no units,
            if ``len(result.labels)`` differs from the number of rows of `waveforms` or of
            ``result.embedding``, if a row has no finite normalized value (a NaN, an infinity or
            a flat trace), which the mean would hide, or if the clusters outnumber the 24
            distinct colors (each cluster gets its own color: the Nature accents up to 7, Tol's
            muted set up to 9, Plotly's Dark24 up to 24).
    """
    if result.embedding is None:
        raise ValueError("plot_wavemap: result.embedding is None; call wavemap(..., embedding=True) "
                         "to draw the embedding.")
    labels = np.asarray(result.labels)
    if labels.shape[0] == 0 or len(waveforms) == 0:
        raise ValueError("plot_wavemap: the result or the waveforms hold no units; there is nothing "
                         "to draw.")
    normalized = normalize_waveforms(waveforms)
    if labels.shape[0] != normalized.shape[0]:
        raise ValueError(f"plot_wavemap: result.labels has {labels.shape[0]} entries but waveforms "
                         f"has {normalized.shape[0]} rows; pass the waveforms the result clustered.")
    n_bad = int(np.sum(~np.all(np.isfinite(normalized), axis=1)))
    if n_bad:
        raise ValueError(f"plot_wavemap: {n_bad} waveform row(s) have no finite normalized value "
                         "(a NaN, an infinity or a flat trace); drop them, as wavemap requires.")
    embedding = np.asarray(result.embedding, dtype=float)
    if embedding.shape[0] != labels.shape[0]:
        raise ValueError(f"plot_wavemap: result.embedding has {embedding.shape[0]} rows but "
                         f"result.labels has {labels.shape[0]} entries; the embedding needs one row "
                         "per label.")
    clusters = np.unique(labels)
    palette = _palette(clusters.size)

    canvas = PlotlyPublicationCanvas(layout=layout, height_mm=height_mm, rows=1, cols=2,
                                     tags=[["A", "B"]])
    x_emb, y_emb = canvas.get_axis_names(0, 0)
    x_mean, y_mean = canvas.get_axis_names(0, 1)
    n_samples = normalized.shape[1]
    for i, k in enumerate(clusters):
        members = labels == k
        name = f"cluster {int(k)}"
        colour = palette[i]
        canvas.fig.add_trace(go.Scatter(
            x=embedding[members, 0], y=embedding[members, 1], mode="markers", name=name,
            legendgroup=name, showlegend=False, marker=dict(color=colour, size=5),
            xaxis=x_emb, yaxis=y_emb,
            hovertemplate=f"{name}<br>UMAP 1: %{{x:.2f}}<br>UMAP 2: %{{y:.2f}}<extra></extra>",
        ))
        canvas.fig.add_trace(go.Scatter(
            x=np.arange(n_samples), y=normalized[members].mean(axis=0), mode="lines", name=name,
            legendgroup=name, showlegend=False, line=dict(color=colour, width=1.5),
            xaxis=x_mean, yaxis=y_mean,
            hovertemplate=f"{name}<br>Sample: %{{x}}<br>Mean: %{{y:.3f}}<extra></extra>",
        ))

    configure_axis(getattr(canvas.fig.layout, _layout_key(x_emb)), title="UMAP 1")
    configure_axis(getattr(canvas.fig.layout, _layout_key(y_emb)), title="UMAP 2")
    configure_axis(getattr(canvas.fig.layout, _layout_key(x_mean)), title="Sample")
    configure_axis(getattr(canvas.fig.layout, _layout_key(y_mean)),
                   title="Normalized amplitude")
    return canvas
