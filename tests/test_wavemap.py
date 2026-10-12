"""WaveMAP: the window, the normalization and the clustering recover planted structure.

`align_waveforms` and `normalize_waveforms` need only NumPy and run everywhere. The clustering
tests need the ``wavemap`` extra (umap-learn, networkx) and skip naming it; CI installs it. The
resolution-convention tests need only networkx, which they call through the module's private
`_louvain` on a graph built here, so the convention is checked without UMAP.
"""

from __future__ import annotations

import builtins
import importlib
import importlib.util

import numpy as np
import pytest

import jnwb

wm = importlib.import_module("jnwb.wavemap")   # the module; `jnwb.wavemap` is the function

FS = 30000.0
HAVE_NETWORKX = importlib.util.find_spec("networkx") is not None
HAVE_EXTRA = HAVE_NETWORKX and importlib.util.find_spec("umap") is not None
needs_extra = pytest.mark.skipif(not HAVE_EXTRA, reason="needs the wavemap extra: pip install jnwb[wavemap]")
needs_networkx = pytest.mark.skipif(not HAVE_NETWORKX, reason="needs networkx (the wavemap extra)")


def spike(trough_at=20, n=82, width=3.0, amp=-80.0, rebound=25.0):
    """A trough of depth `amp` on `trough_at` and a rebound 10 samples later."""
    t = np.arange(n, dtype=float)
    return (amp * np.exp(-0.5 * ((t - trough_at) / width) ** 2)
            + rebound * np.exp(-0.5 * ((t - trough_at - 10) / (2 * width)) ** 2))


def two_shapes(n_each=60, noise=2.0, seed=0):
    """`n_each` narrow and `n_each` broad spikes, aligned and normalized, and their truth."""
    rng = np.random.default_rng(seed)
    w = np.vstack([np.tile(spike(width=1.5), (n_each, 1)),
                   np.tile(spike(width=4.0, rebound=40.0), (n_each, 1))])
    w = w + rng.normal(0.0, noise, w.shape)
    aligned, valid = jnwb.align_waveforms(w, FS)
    assert valid.all()
    return jnwb.normalize_waveforms(aligned), np.repeat([0, 1], n_each)


# --- align_waveforms --------------------------------------------------------------------------

class TestAlign:
    def test_the_default_window_is_the_published_one(self):
        aligned, valid = jnwb.align_waveforms(spike(20)[None], FS)
        assert aligned.shape == (1, 48)                    # 1.6 ms at 30 kHz
        assert valid.tolist() == [True]
        assert int(np.argmin(aligned[0])) == 12            # 0.4 ms before the trough

    def test_identity_a_cut_window_is_the_samples_around_the_trough(self):
        w = spike(30)
        aligned, _ = jnwb.align_waveforms(w[None], FS)
        np.testing.assert_array_equal(aligned[0], w[30 - 12:30 + 36])

    def test_the_window_follows_fs_and_the_arguments(self):
        aligned, _ = jnwb.align_waveforms(spike(30)[None], 10000.0, pre_s=0.001, post_s=0.002)
        assert aligned.shape == (1, 30)
        assert int(np.argmin(aligned[0])) == 10

    def test_boundary_a_window_that_just_fits_is_kept_and_one_sample_more_is_dropped(self):
        n = 82
        fits = jnwb.align_waveforms(np.vstack([spike(12, n), spike(n - 36, n)]), FS)[1]
        leaves = jnwb.align_waveforms(np.vstack([spike(11, n), spike(n - 35, n)]), FS)[1]
        assert fits.tolist() == [True, True]
        assert leaves.tolist() == [False, False]

    def test_an_invalid_row_is_nan_and_never_padded(self):
        bad = spike(20)
        bad[5] = np.nan
        aligned, valid = jnwb.align_waveforms(np.vstack([spike(3), bad, spike(20)]), FS)
        assert valid.tolist() == [False, False, True]
        assert np.isnan(aligned[:2]).all() and np.isfinite(aligned[2]).all()

    def test_scale_and_offset_do_not_move_the_window(self):
        a = jnwb.align_waveforms(spike(25)[None], FS)[0]
        b = jnwb.align_waveforms((7.0 * spike(25) + 3.0)[None], FS)[0]
        np.testing.assert_allclose(b, 7.0 * a + 3.0)

    def test_the_input_is_not_modified(self):
        w = np.vstack([spike(20), spike(30)])
        before = w.copy()
        jnwb.align_waveforms(w, FS)
        np.testing.assert_array_equal(w, before)

    @pytest.mark.parametrize("bad", [np.zeros(82), np.zeros((2, 1)), np.zeros((0, 82))])
    def test_a_wrong_shape_is_refused(self, bad):
        with pytest.raises(ValueError, match="align_waveforms"):
            jnwb.align_waveforms(bad, FS)

    @pytest.mark.parametrize("kw", [{"fs": 0.0}, {"fs": np.nan}, {"fs": FS, "pre_s": -1e-4},
                                    {"fs": FS, "post_s": np.inf}, {"fs": 1.0, "pre_s": 0.1,
                                                                    "post_s": 0.1}])
    def test_an_undefined_window_is_refused(self, kw):
        with pytest.raises(ValueError, match="align_waveforms"):
            jnwb.align_waveforms(spike()[None], **kw)


# --- normalize_waveforms ----------------------------------------------------------------------

class TestNormalize:
    def test_each_row_has_zero_mean_and_largest_absolute_value_one(self):
        x = jnwb.normalize_waveforms(np.vstack([spike(), spike(width=4.0)]))
        np.testing.assert_allclose(x.mean(axis=1), 0.0, atol=1e-12)
        np.testing.assert_allclose(np.abs(x).max(axis=1), 1.0)

    def test_scale_and_offset_are_removed(self):
        x = jnwb.normalize_waveforms(np.vstack([spike(), 5.0 * spike() + 7.0]))
        np.testing.assert_allclose(x[0], x[1], atol=1e-12)

    def test_sign_is_kept(self):
        x = jnwb.normalize_waveforms(np.vstack([spike(), -spike()]))
        np.testing.assert_allclose(x[1], -x[0], atol=1e-12)

    def test_identity_normalising_twice_changes_nothing(self):
        x = jnwb.normalize_waveforms(spike()[None])
        np.testing.assert_allclose(jnwb.normalize_waveforms(x), x, atol=1e-12)

    def test_without_mean_subtraction_only_the_scale_changes(self):
        w = spike()[None] + 10.0
        np.testing.assert_allclose(jnwb.normalize_waveforms(w, subtract_mean=False),
                                   w / np.abs(w).max())

    def test_each_unit_is_normalized_on_its_own_not_each_time_point(self):
        # Lee et al. 2023's printed code transposes first; per time point, a column would be
        # scaled by the other units, and adding a unit would change the first row.
        one = jnwb.normalize_waveforms(spike()[None])
        two = jnwb.normalize_waveforms(np.vstack([spike(), 40.0 * spike(width=5.0)]))
        np.testing.assert_allclose(two[0], one[0])

    def test_a_constant_or_non_finite_row_is_nan(self):
        w = np.vstack([np.full(48, 3.0), spike(n=48), spike(n=48)])
        w[2, 4] = np.inf
        x = jnwb.normalize_waveforms(w)
        assert np.isnan(x[0]).all() and np.isfinite(x[1]).all() and np.isnan(x[2]).all()

    def test_every_constant_row_is_nan_whatever_its_rounding_residue(self):
        w = np.repeat(np.random.default_rng(0).uniform(-5.0, 5.0, 1001)[:, None], 82, axis=1)
        residue = np.abs(w - w.mean(axis=1, keepdims=True)).max(axis=1)
        assert (residue > 0).sum() > 100, "fixture must leave rounding residue"
        assert np.isnan(jnwb.normalize_waveforms(w)).all()

    def test_without_mean_subtraction_only_a_row_of_zeros_is_nan(self):
        x = jnwb.normalize_waveforms(np.vstack([np.full(48, -3.0), np.zeros(48)]),
                                     subtract_mean=False)
        assert np.array_equal(x[0], np.full(48, -1.0)) and np.isnan(x[1]).all()


# --- the resolution convention, on a graph built here (networkx only) -------------------------

def _ring_of_cliques(n_cliques=12, size=6):
    """Cliques joined in a ring by single edges; a scipy CSR adjacency."""
    import scipy.sparse as sp

    n = n_cliques * size
    a = np.zeros((n, n))
    for c in range(n_cliques):
        idx = np.arange(c * size, (c + 1) * size)
        a[np.ix_(idx, idx)] = 1.0
        nxt = ((c + 1) % n_cliques) * size
        a[idx[-1], nxt] = a[nxt, idx[-1]] = 1.0
    np.fill_diagonal(a, 0.0)
    return sp.csr_matrix(a)


@needs_networkx
class TestResolutionConvention:
    def test_a_larger_resolution_gives_fewer_clusters(self):
        g = _ring_of_cliques()
        counts = [wm._louvain(g, t, seed=0)[0].max() + 1 for t in (0.2, 1.0, 5.0, 50.0)]
        assert counts == sorted(counts, reverse=True)
        assert counts[0] > counts[-1]

    def test_resolution_one_finds_the_cliques(self):
        labels, q = wm._louvain(_ring_of_cliques(), 1.0, seed=0)
        assert labels.max() + 1 == 12
        assert all(np.unique(labels[c * 6:(c + 1) * 6]).size == 1 for c in range(12))
        assert 0.0 < q < 1.0

    def test_resolution_t_is_networkx_gamma_one_over_t(self):
        import networkx as nx

        g = _ring_of_cliques()
        G = nx.from_scipy_sparse_array(g)
        for t in (0.5, 2.0, 8.0):
            mine = wm._louvain(g, t, seed=3)[0]
            theirs = nx.community.louvain_communities(G, weight="weight", resolution=1.0 / t,
                                                      seed=3)
            assert sorted(sorted(c) for c in theirs) == sorted(
                sorted(np.flatnonzero(mine == k).tolist()) for k in range(mine.max() + 1))

    def test_labels_are_ordered_by_size(self):
        import scipy.sparse as sp

        g = _ring_of_cliques(4, 6).toarray()
        g[:6, :6] = 0.0
        big = np.ones((12, 12)) - np.eye(12)
        graph = sp.csr_matrix(sp.block_diag([big, g]))
        labels = wm._louvain(graph, 1.0, seed=0)[0]
        sizes = np.bincount(labels)
        assert list(sizes) == sorted(sizes, reverse=True)


# --- wavemap and the sweep (the wavemap extra) ------------------------------------------------

def test_the_name_is_the_function_after_the_module_is_imported():
    import jnwb.wavemap  # noqa: F401  (binds nothing new: the module is already loaded)

    assert callable(jnwb.wavemap) and jnwb.wavemap is wm.wavemap


class TestRefusals:
    def test_nan_rows_are_refused_before_the_extra_is_needed(self):
        x, _ = two_shapes()
        x[0, 0] = np.nan
        with pytest.raises(ValueError, match="NaN"):
            jnwb.wavemap(x, resolution=1.5)

    def test_too_few_units_are_refused(self):
        x, _ = two_shapes(n_each=5)
        with pytest.raises(ValueError, match="n_neighbors"):
            jnwb.wavemap(x, resolution=1.5)

    @pytest.mark.parametrize("bad", [0.0, -1.0, np.nan, np.inf, "x"])
    def test_an_undefined_resolution_is_refused(self, bad):
        with pytest.raises(ValueError, match="resolution"):
            jnwb.wavemap(two_shapes()[0], resolution=bad)

    def test_resolution_has_no_default(self):
        with pytest.raises(TypeError):
            jnwb.wavemap(two_shapes()[0])

    @pytest.mark.parametrize("kw", [{"resolutions": []}, {"resolutions": [1.0], "n_runs": 0},
                                    {"resolutions": [1.0], "fraction": 0.0},
                                    {"resolutions": [1.0], "fraction": 1.5},
                                    {"resolutions": [1.0], "fraction": 0.1}])
    def test_the_sweep_refuses_an_undefined_design(self, kw):
        with pytest.raises(ValueError, match="wavemap_resolution_sweep"):
            jnwb.wavemap_resolution_sweep(two_shapes()[0], **kw)

    def test_a_float_seed_is_refused(self):
        with pytest.raises(TypeError):
            jnwb.wavemap(two_shapes()[0], resolution=1.5, rng=2.7)

    def test_without_the_extra_the_call_names_it(self, monkeypatch):
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "umap" or name.startswith("umap."):
                raise ImportError("blocked for the test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        with pytest.raises(ImportError, match=r"jnwb\[wavemap\]"):
            jnwb.wavemap(two_shapes()[0], resolution=1.5)
        with pytest.raises(ImportError, match=r"jnwb\[wavemap\]"):
            jnwb.wavemap_resolution_sweep(two_shapes()[0], [1.5], n_runs=1)


@needs_extra
class TestWaveMAP:
    def test_two_planted_shapes_are_never_mixed(self):
        x, truth = two_shapes()
        res = jnwb.wavemap(x, resolution=1.5, rng=0)
        assert isinstance(res, jnwb.WaveMAPResult)
        assert res.labels.shape == (120,) and res.n_clusters == res.labels.max() + 1
        for c in range(res.n_clusters):
            assert np.unique(truth[res.labels == c]).size == 1
        for shape in (0, 1):     # measured: one cluster of 60 and two of 38 and 22; singletons give 60
            assert np.unique(res.labels[truth == shape]).size <= 5
        assert res.embedding.shape == (120, 2)
        assert res.graph.shape == (120, 120)
        assert -0.5 <= res.modularity <= 1.0

    def test_resolution_orders_the_cluster_count(self):
        x, truth = two_shapes()
        fine = jnwb.wavemap(x, resolution=0.2, embedding=False, rng=0)
        mid = jnwb.wavemap(x, resolution=1.5, embedding=False, rng=0)
        coarse = jnwb.wavemap(x, resolution=20.0, embedding=False, rng=0)
        assert fine.n_clusters > mid.n_clusters >= coarse.n_clusters   # measured: 27, 3, 3
        assert np.array_equal(mid.graph.toarray(), coarse.graph.toarray())   # one UMAP graph

    def test_labels_are_ordered_by_size(self):
        res = jnwb.wavemap(two_shapes()[0], resolution=0.5, embedding=False, rng=0)
        sizes = np.bincount(res.labels)
        assert list(sizes) == sorted(sizes, reverse=True)

    def test_an_int_seed_repeats_the_result_and_the_input_is_kept(self):
        x, _ = two_shapes()
        before = x.copy()
        a = jnwb.wavemap(x, resolution=1.5, embedding=False, rng=11)
        b = jnwb.wavemap(x, resolution=1.5, embedding=False, rng=11)
        np.testing.assert_array_equal(a.labels, b.labels)
        assert a.parameters == b.parameters
        np.testing.assert_array_equal(x, before)

    def test_a_generator_advances_and_records_its_seeds(self):
        x, _ = two_shapes()
        gen = np.random.default_rng(5)
        a = jnwb.wavemap(x, resolution=1.5, embedding=False, rng=gen)
        b = jnwb.wavemap(x, resolution=1.5, embedding=False, rng=gen)
        assert a.parameters["umap_seed"] != b.parameters["umap_seed"]
        assert set(a.parameters) == {"n_neighbors", "min_dist", "metric", "umap_seed",
                                     "louvain_seed"}

    def test_no_embedding_when_not_asked(self):
        assert jnwb.wavemap(two_shapes()[0], resolution=1.5, embedding=False).embedding is None

    def test_the_sweep_shapes_and_its_smallest_cluster(self, monkeypatch):
        x, _ = two_shapes()
        rows = []
        umap_call = wm._umap
        monkeypatch.setattr(wm, "_umap", lambda *a: rows.append(a[0].shape[0]) or umap_call(*a))
        out = jnwb.wavemap_resolution_sweep(x, [0.5, 1.5, 5.0], n_runs=3, fraction=0.8, rng=0)
        assert rows == [96] * 3                                              # floor(0.8 * 120)
        assert set(out) == {"resolution", "modularity", "n_clusters", "min_cluster_size",
                            "units", "umap_seed", "louvain_seed"}
        for key in ("modularity", "n_clusters", "min_cluster_size"):
            assert out[key].shape == (3, 3)
        assert np.all(out["min_cluster_size"] >= 1)
        assert np.all(out["min_cluster_size"] * out["n_clusters"] <= 96)    # floor(0.8 * 120)
        assert np.all(out["n_clusters"][0] >= out["n_clusters"][-1])         # one graph per run

    def test_the_sweep_repeats_with_an_int_seed(self):
        x, _ = two_shapes()
        a = jnwb.wavemap_resolution_sweep(x, [1.5], n_runs=2, rng=4)
        b = jnwb.wavemap_resolution_sweep(x, [1.5], n_runs=2, rng=4)
        for key in a:
            np.testing.assert_array_equal(a[key], b[key])

    def test_two_sweep_seeds_change_the_subsets_and_the_scores(self):
        x, _ = two_shapes()
        a = jnwb.wavemap_resolution_sweep(x, [0.5], n_runs=3, rng=4)
        b = jnwb.wavemap_resolution_sweep(x, [0.5], n_runs=3, rng=5)
        assert not np.array_equal(a["units"], b["units"])
        assert not np.array_equal(a["modularity"], b["modularity"])

    def test_the_recorded_units_and_seeds_repeat_a_run(self):
        x, _ = two_shapes()
        out = jnwb.wavemap_resolution_sweep(x, [0.5, 1.5], n_runs=2, rng=None)
        assert out["units"].shape == (2, 96) and out["umap_seed"].shape == (2,)
        assert out["umap_seed"][0] != out["umap_seed"][1]          # a fresh UMAP seed per run
        assert out["louvain_seed"][0] != out["louvain_seed"][1]
        for r in range(2):
            graph = wm._umap(x[out["units"][r]], 20, 0.1, "euclidean",
                             int(out["umap_seed"][r])).graph_
            for i, t in enumerate(out["resolution"]):
                labels, q = wm._louvain(graph, float(t), int(out["louvain_seed"][r]))
                np.testing.assert_allclose(q, out["modularity"][i, r], rtol=1e-12)
                assert np.bincount(labels).size == out["n_clusters"][i, r]

    def test_the_sweep_builds_its_graph_with_the_metric_wavemap_takes(self, monkeypatch):
        x, _ = two_shapes()
        seen = []
        umap_call = wm._umap
        monkeypatch.setattr(wm, "_umap", lambda *a: seen.append(a[3]) or umap_call(*a))
        euclid = jnwb.wavemap_resolution_sweep(x, [0.5, 1.5], n_runs=2, rng=4)
        cosine = jnwb.wavemap_resolution_sweep(x, [0.5, 1.5], n_runs=2, metric="cosine", rng=4)
        assert seen == ["euclidean"] * 2 + ["cosine"] * 2
        assert not np.array_equal(euclid["modularity"], cosine["modularity"])

@needs_extra
def test_two_seeds_change_the_embedding():
    x, _ = two_shapes()
    a = jnwb.wavemap(x, resolution=1.0, rng=0)
    b = jnwb.wavemap(x, resolution=1.0, rng=1)
    assert a.embedding is not None and not np.allclose(a.embedding, b.embedding)
