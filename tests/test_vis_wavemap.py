"""tests/test_vis_wavemap.py -- jnwb.vis.plot_wavemap draws one WaveMAP result.

The figure has one trace group per cluster, the two panels share each cluster's colour, the
drawn means are the means of the normalized waveforms, each refusal fires, and a label swap
changes the means drawn. The result is built directly; one test clusters a small synthetic set
with `jnwb.wavemap` when the wavemap extra is installed.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

# jnwb.vis needs the optional `vis` extra; test_optional_vis_extra.py covers its absence.
pytest.importorskip("plotly")

from jnwb import WaveMAPResult, normalize_waveforms  # noqa: E402
from jnwb.vis import plot_wavemap  # noqa: E402


def _result(labels, embedding_seed=0):
    labels = np.asarray(labels, dtype=int)
    rng = np.random.default_rng(embedding_seed)
    embedding = rng.standard_normal((labels.size, 2)) + 4.0 * labels[:, None]
    return WaveMAPResult(labels=labels, n_clusters=int(labels.max()) + 1, modularity=0.0,
                         resolution=1.0, embedding=embedding, graph=None, parameters={})


@pytest.fixture
def wave_set():
    """Thirty units in three clusters of ten, with random waveforms of 48 samples."""
    labels = np.repeat([0, 1, 2], 10)
    waveforms = np.random.default_rng(1).standard_normal((30, 48))
    assert np.unique(labels).size == 3, "fixture must have three clusters"
    assert np.isfinite(normalize_waveforms(waveforms)).all(), "fixture rows must normalize"
    return waveforms, _result(labels)


def _drawn_means(canvas):
    """Cluster index -> the y values drawn in panel B, read from the figure."""
    return {int(t.legendgroup.split()[1]): np.asarray(t.y, dtype=float)
            for t in canvas.fig.data if t.xaxis == "x2"}


def test_the_figure_has_one_trace_group_per_cluster(wave_set):
    waveforms, result = wave_set
    canvas = plot_wavemap(result, waveforms)
    groups = {}
    for trace in canvas.fig.data:
        groups.setdefault(trace.legendgroup, []).append(trace)
    assert sorted(groups) == [f"cluster {k}" for k in range(3)], sorted(groups)
    for name, members in groups.items():
        assert len(members) == 2, f"{name} has {len(members)} traces; one per panel is expected"
        assert {t.xaxis for t in members} == {"x", "x2"}


def test_the_two_panels_share_each_clusters_colour(wave_set):
    waveforms, result = wave_set
    canvas = plot_wavemap(result, waveforms)
    colours = {}
    for trace in canvas.fig.data:
        colour = trace.marker.color if trace.xaxis == "x" else trace.line.color
        colours.setdefault(trace.legendgroup, set()).add(colour)
    assert colours, "the figure drew no traces"
    assert all(len(c) == 1 for c in colours.values()), colours
    assert len({next(iter(c)) for c in colours.values()}) == 3, "clusters share a colour"


def test_the_drawn_means_are_the_means_of_the_normalized_waveforms(wave_set):
    waveforms, result = wave_set
    drawn = _drawn_means(plot_wavemap(result, waveforms))
    normalized = normalize_waveforms(waveforms)
    assert sorted(drawn) == [0, 1, 2], sorted(drawn)
    for k in range(3):
        np.testing.assert_allclose(drawn[k], normalized[result.labels == k].mean(axis=0),
                                   rtol=1e-12)


def test_a_result_without_an_embedding_is_refused(wave_set):
    waveforms, result = wave_set
    bare = dataclasses.replace(result, embedding=None)
    assert bare.embedding is None
    with pytest.raises(ValueError, match="embedding=True"):
        plot_wavemap(bare, waveforms)


def test_labels_that_do_not_match_the_waveform_rows_are_refused(wave_set):
    waveforms, result = wave_set
    short = dataclasses.replace(result, labels=result.labels[:-1])
    with pytest.raises(ValueError, match="labels has 29 entries but waveforms has 30 rows"):
        plot_wavemap(short, waveforms)
    with pytest.raises(ValueError, match="labels has 30 entries but waveforms has 29 rows"):
        plot_wavemap(result, waveforms[:-1])


def test_an_embedding_of_another_length_is_refused_by_name():
    """Ten labels with a seven-row embedding: refused with both lengths, not an IndexError."""
    labels = np.repeat([0, 1], 5)
    waveforms = np.random.default_rng(2).standard_normal((10, 48))
    result = _result(labels)
    short = dataclasses.replace(result, embedding=result.embedding[:7])
    assert short.embedding.shape == (7, 2), "fixture embedding must have seven rows"
    with pytest.raises(ValueError, match="embedding has 7 rows but result.labels has 10 entries"):
        plot_wavemap(short, waveforms)


def test_an_empty_result_or_empty_waveforms_are_refused_by_name(wave_set):
    empty = WaveMAPResult(labels=np.zeros(0, dtype=int), n_clusters=0, modularity=0.0,
                          resolution=1.0, embedding=np.zeros((0, 2)), graph=None, parameters={})
    with pytest.raises(ValueError, match="hold no units"):
        plot_wavemap(empty, np.zeros((0, 48)))
    waveforms, result = wave_set
    with pytest.raises(ValueError, match="hold no units"):
        plot_wavemap(result, np.zeros((0, 48)))


def test_a_row_with_no_normalized_value_is_refused(wave_set):
    """A flat trace normalizes to NaN; the mean of its cluster would hide it, so it is refused."""
    waveforms, result = wave_set
    flat = waveforms.copy()
    flat[4] = 1.0
    assert np.isnan(normalize_waveforms(flat)[4]).all(), "fixture row 4 must normalize to NaN"
    with pytest.raises(ValueError, match="no finite normalized value"):
        plot_wavemap(result, flat)


def test_a_swapped_label_changes_the_means_drawn(wave_set):
    """A mutant that swaps the labels of two units from different clusters must change the
    means drawn for both clusters; a figure that ignored the labels would not."""
    waveforms, result = wave_set
    normalized = normalize_waveforms(waveforms)
    i = int(np.flatnonzero(result.labels == 0)[0])
    j = int(np.flatnonzero(result.labels == 1)[0])
    assert not np.allclose(normalized[i], normalized[j]), "fixture units must differ"

    swapped = result.labels.copy()
    swapped[[i, j]] = swapped[[j, i]]
    drawn = _drawn_means(plot_wavemap(result, waveforms))
    mutant = _drawn_means(plot_wavemap(dataclasses.replace(result, labels=swapped), waveforms))
    assert not np.allclose(drawn[0], mutant[0]), "cluster 0 mean did not change"
    assert not np.allclose(drawn[1], mutant[1]), "cluster 1 mean did not change"


def test_a_wavemap_result_on_a_small_synthetic_set_draws_its_clusters():
    """The same figure from `jnwb.wavemap` itself; needs the wavemap extra (umap-learn, networkx)."""
    pytest.importorskip("umap")
    pytest.importorskip("networkx")
    from jnwb import wavemap

    rng = np.random.default_rng(3)
    t = np.linspace(0.0, 1.0, 48)
    fast = -np.exp(-((t - 0.3) / 0.05) ** 2) + 0.3 * np.exp(-((t - 0.6) / 0.1) ** 2)
    slow = -np.exp(-((t - 0.4) / 0.15) ** 2) + 0.5 * np.exp(-((t - 0.7) / 0.05) ** 2)
    raw = np.vstack([fast + 0.02 * rng.standard_normal((40, 48)),
                     slow + 0.02 * rng.standard_normal((40, 48))])
    result = wavemap(normalize_waveforms(raw), resolution=1.0, rng=0)
    assert result.n_clusters >= 2, "fixture must cluster into two or more groups"

    canvas = plot_wavemap(result, raw)
    groups = {trace.legendgroup for trace in canvas.fig.data}
    assert len(groups) == result.n_clusters
    drawn = _drawn_means(canvas)
    normalized = normalize_waveforms(raw)
    for k in range(result.n_clusters):
        np.testing.assert_allclose(drawn[k], normalized[result.labels == k].mean(axis=0),
                                   rtol=1e-12)


@pytest.mark.parametrize("n_clusters", [8, 9, 12, 24])
def test_every_cluster_keeps_its_own_colour_beyond_seven(n_clusters):
    """More clusters than the 7 Nature accents: a static export has no hover text, so a reused
    colour would merge two clusters in both panels (Lee et al. 2021 report 8)."""
    labels = np.repeat(np.arange(n_clusters), 3)
    waveforms = np.random.default_rng(2).standard_normal((labels.size, 48))
    assert np.unique(labels).size > 7, "fixture must exceed the seven Nature accents"
    canvas = plot_wavemap(_result(labels), waveforms)
    colours = {}
    for trace in canvas.fig.data:
        colour = trace.marker.color if trace.xaxis == "x" else trace.line.color
        colours.setdefault(trace.legendgroup, set()).add(colour)
    assert len(colours) == n_clusters
    assert all(len(c) == 1 for c in colours.values()), colours
    assert len({next(iter(c)) for c in colours.values()}) == n_clusters, "clusters share a colour"


def test_more_clusters_than_distinct_colours_is_refused():
    labels = np.repeat(np.arange(25), 2)
    waveforms = np.random.default_rng(3).standard_normal((labels.size, 48))
    with pytest.raises(ValueError, match="25 clusters exceed the 24 distinct colors"):
        plot_wavemap(_result(labels), waveforms)
