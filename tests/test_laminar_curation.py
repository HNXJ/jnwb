"""Tests for jnwb.laminar_curation: bad contacts, interpolation, CSD sink, fusion, labelling."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import signal
from scipy.ndimage import gaussian_filter1d

import jnwb

FS = 500.0
PITCH = 25.0
MARK = {"na": ".", "deep": "d", "input": "i", "superficial": "s", "WM": "W", "outside_cortex": "O"}


def _band(rng, shape, lo, hi):
    sos = signal.butter(4, [lo, hi], btype="band", fs=FS, output="sos")
    z = rng.standard_normal(shape[:-1] + (shape[-1] + 200,))
    z = gaussian_filter1d(z, 1.5, axis=0)
    z = signal.sosfiltfilt(sos, z, axis=-1)[..., 100:-100]
    return z / z.std()


def synth(n=48, n_ep=40, n_s=1000, cross=24.0, sup_up=True, seed=0):
    """Spatially smooth alpha-beta and gamma sources whose weights swap at ``cross``."""
    rng = np.random.default_rng(seed)
    sup = 1 / (1 + np.exp(-(np.arange(n) - cross) / 3.0))
    sup = sup if sup_up else 1 - sup
    shape = (n, n_ep, n_s)
    x = ((0.15 + 0.85 * (1 - sup))[:, None, None] * _band(rng, shape, 10, 19)
         + (0.15 + 0.85 * sup)[:, None, None] * 0.6 * _band(rng, shape, 75, 150))
    return x + 0.05 * gaussian_filter1d(rng.standard_normal(shape), 1.0, axis=0)


def word(result):
    return "".join(MARK[s] for s in result.labels)


@pytest.fixture(scope="module")
def clean():
    x = synth()
    return x, jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False)


class TestDetectBadChannels:
    def test_a_decorrelated_contact_is_flagged(self):
        x = synth()
        x[20] = np.random.default_rng(9).standard_normal(x[20].shape) * x.std()
        out = jnwb.detect_bad_channels(x, FS)
        assert out["bad_mask"][20]
        assert not out["bad_mask"][10:20].any() and not out["bad_mask"][21:40].any()

    def test_an_outlying_power_contact_is_flagged(self):
        x = synth()
        x[30] *= 1e3
        assert jnwb.detect_bad_channels(x, FS)["bad_mask"][30]

    def test_shapes_and_two_dimensional_input(self):
        out = jnwb.detect_bad_channels(synth(n=24, n_ep=1, n_s=4000)[:, 0], FS)
        assert out["bad_mask"].shape == out["neighbor_correlation"].shape == out["log_power"].shape == (24,)

    def test_scale_leaves_the_flags_unchanged_and_shifts_log_power(self):
        x = synth(n=24)
        a, b = jnwb.detect_bad_channels(x, FS), jnwb.detect_bad_channels(10.0 * x, FS)
        assert np.array_equal(a["bad_mask"], b["bad_mask"])
        assert np.allclose(b["log_power"] - a["log_power"], 2.0)

    def test_refuses_nonfinite_and_bad_band_and_short_shaft(self):
        x = synth(n=24)
        bad = x.copy()
        bad[0, 0, 0] = np.nan
        with pytest.raises(ValueError, match="non-finite"):
            jnwb.detect_bad_channels(bad, FS)
        with pytest.raises(ValueError, match="power_band_hz"):
            jnwb.detect_bad_channels(x, FS, power_band_hz=(1.0, 300.0))
        with pytest.raises(ValueError, match="at least 3"):
            jnwb.detect_bad_channels(x[:2], FS)

    def test_the_input_and_the_global_random_state_are_untouched(self):
        x = synth(n=24)
        before, state = x.copy(), np.random.get_state()[1].copy()
        jnwb.detect_bad_channels(x, FS)
        assert np.array_equal(x, before)
        assert np.array_equal(np.random.get_state()[1], state)


class TestInterpolateChannelRuns:
    def test_a_short_run_is_linear_between_its_neighbors(self):
        data = np.arange(10.0)[:, None] * np.ones((1, 3))
        data[4:6] = 99.0
        bad = np.zeros(10, bool)
        bad[4:6] = True
        out = jnwb.interpolate_channel_runs(data, bad)
        assert np.allclose(out["data"], np.arange(10.0)[:, None])
        assert out["interpolated_mask"].sum() == 2 and not out["unresolved_mask"].any()

    def test_long_edge_and_blocked_runs_stay_unresolved(self):
        data = np.arange(12.0)
        bad = np.zeros(12, bool)
        bad[[0, 3, 4, 5, 6, 9]] = True
        blocked = np.zeros(12, bool)
        blocked[10] = True
        out = jnwb.interpolate_channel_runs(data, bad, max_run=3, blocked_mask=blocked)
        assert out["unresolved_mask"][[0, 3, 4, 5, 6, 9]].all()      # edge, run of 4, blocked neighbor
        assert not out["interpolated_mask"].any()

    def test_the_input_is_copied_and_masks_are_checked(self):
        data = np.arange(8.0)
        bad = np.zeros(8, bool)
        bad[3] = True
        out = jnwb.interpolate_channel_runs(data, bad)
        assert data[3] == 3.0 and out["data"] is not data
        with pytest.raises(ValueError, match="shape"):
            jnwb.interpolate_channel_runs(data, bad[:5])


def _sink_erp(n=32, pitch=PITCH, at=20, sigma_um=75.0, t_peak=60.0):
    t = np.arange(-100.0, 300.0, 2.0)
    c = np.arange(n)
    spatial = -np.exp(-0.5 * ((c - at) * pitch / sigma_um) ** 2)
    temporal = np.exp(-0.5 * ((t - t_peak) / 15.0) ** 2)
    return spatial[:, None] * temporal[None, :], t


class TestEvokedCsdSink:
    def test_locates_a_planted_sink(self):
        erp, t = _sink_erp()
        out = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH)
        assert abs(out["strongest_contact"] - 20) <= 1
        assert abs(out["earliest_contact"] - 20) <= 2
        assert 25.0 <= out["earliest_onset_ms"] < 60.0
        assert out["strongest_position_um"] == out["strongest_contact"] * PITCH

    def test_a_source_is_not_a_sink(self):
        erp, t = _sink_erp()
        out = jnwb.evoked_csd_sink(-erp, t, pitch_um=PITCH)
        assert not out["strongest_contact"] == 20 and not abs(out["strongest_contact"] - 20) <= 1

    def test_scale_does_not_move_the_sink_and_pitch_scales_the_position(self):
        erp, t = _sink_erp()
        a = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH)
        b = jnwb.evoked_csd_sink(7.0 * erp, t, pitch_um=PITCH)
        c = jnwb.evoked_csd_sink(erp, t, pitch_um=2 * PITCH)
        assert a["strongest_contact"] == b["strongest_contact"]
        assert c["strongest_position_um"] == c["strongest_contact"] * 2 * PITCH

    def test_too_few_usable_contacts_gives_nan(self):
        erp, t = _sink_erp()
        mask = np.zeros(erp.shape[0], bool)
        mask[:5] = True
        out = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH, usable_mask=mask)
        assert all(np.isnan(v) for v in out.values())

    def test_refuses_no_baseline_and_bad_pitch(self):
        erp, t = _sink_erp()
        with pytest.raises(ValueError, match="before 0"):
            jnwb.evoked_csd_sink(erp, np.abs(t) + 1.0, pitch_um=PITCH)
        with pytest.raises(ValueError, match="pitch_um"):
            jnwb.evoked_csd_sink(erp, t, pitch_um=0.0)


class TestFuseLaminarAnchors:
    WIN = np.array([600.0, 610.0, 590.0, 605.0])

    @pytest.mark.parametrize("kwargs, grade", [
        (dict(vflip_um=600.0, window_um=WIN, consistency_deep=0.9, consistency_superficial=0.8), "A"),
        (dict(vflip_um=600.0, window_um=WIN, consistency_deep=0.9, consistency_superficial=0.65), "B"),
        (dict(vflip_um=600.0, window_um=WIN, consistency_deep=0.9, consistency_superficial=0.3), "C"),
        (dict(vflip_um=600.0, window_um=np.array([300.0, 900.0, 600.0, 100.0]),
              consistency_deep=0.9, consistency_superficial=0.9), "C"),
        (dict(motif_um=600.0, window_um=WIN, consistency_deep=0.9, consistency_superficial=0.9), "D"),
        (dict(motif_um=600.0, window_um=WIN, consistency_deep=0.9, consistency_superficial=0.5), "F"),
        (dict(), "F"),
    ])
    def test_grade_table(self, kwargs, grade):
        assert jnwb.fuse_laminar_anchors(**kwargs)["grade"] == grade

    def test_xflip_and_csd_are_reported_and_never_move_the_anchor(self):
        base = dict(vflip_um=600.0, window_um=self.WIN, consistency_deep=0.9, consistency_superficial=0.9)
        a = jnwb.fuse_laminar_anchors(**base)
        b = jnwb.fuse_laminar_anchors(**base, xflip_um=1000.0, csd_um=100.0)
        assert a["anchor_um"] == b["anchor_um"] == 600.0 and a["grade"] == b["grade"]
        assert b["distance_um"] == {"xflip": 400.0, "csd": 500.0}
        assert np.isnan(a["distance_um"]["xflip"])

    def test_motif_anchor_is_the_fallback_and_too_few_windows_is_unstable(self):
        out = jnwb.fuse_laminar_anchors(motif_um=500.0, window_um=np.array([500.0, np.nan, np.nan, 500.0]),
                                        consistency_deep=1.0, consistency_superficial=1.0)
        assert out["anchor_source"] == "motif" and out["n_windows_ok"] == 2 and not out["stable"]


class TestCurateAndLabel:
    def test_recovers_the_crossover_and_orders_the_labels(self, clean):
        _, r = clean
        assert r.grade == "A" and r.anchor_source == "vflip" and r.superficial_at_high_index is True
        assert abs(r.anchor_um - 24 * PITCH) <= 4 * PITCH
        w = word(r).strip(".")
        assert w == "d" * w.count("d") + "i" * w.count("i") + "s" * w.count("s")
        assert w.count("d") > 5 and w.count("i") > 5 and w.count("s") > 5
        assert abs(w.count("i") * PITCH - 400.0) <= 2 * PITCH         # the 400 um granular zone

    def test_the_labels_mirror_when_the_shaft_is_reversed(self, clean):
        x, r = clean
        m = jnwb.curate_and_label(x[::-1].copy(), FS, pitch_um=PITCH, compute_xflip=False)
        assert m.superficial_at_high_index is False and m.grade == r.grade
        assert word(m)[::-1].strip(".") == word(r).strip(".")

    def test_widths_follow_the_pitch(self, clean):
        x, r = clean
        wide = jnwb.curate_and_label(x, FS, pitch_um=2 * PITCH, compute_xflip=False)
        assert wide.anchor_um == pytest.approx(2 * r.anchor_um, rel=1e-6)
        assert wide.labels.tolist().count("input") < r.labels.tolist().count("input")

    def test_a_dead_contact_is_interpolated_and_the_label_run_is_unbroken(self):
        x = synth()
        x[20] = np.random.default_rng(9).standard_normal(x[20].shape) * x.std()
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False)
        assert r.bad_mask[20] and r.interpolated_mask[20] and not r.unusable_mask[20]
        assert r.labels[20] != "na"

    def test_noise_is_never_labelled(self):
        x = np.random.default_rng(3).standard_normal((32, 20, 1000))
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False)
        assert r.grade == "F" and set(r.labels) == {"na"} and np.isnan(r.anchor_um)

    def test_a_silent_deep_end_is_white_matter(self):
        x = synth(n=64, cross=36.0)
        x[:8] *= 0.3
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False)
        assert set(r.labels[2:8]) == {"WM"} and r.labels[20] == "deep"   # contacts 0-1 are end-of-shaft artifacts

    def test_a_silent_superficial_end_is_outside_cortex(self):
        x = synth(n=64, cross=28.0)
        x[-8:] *= 0.3
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False)
        assert set(r.labels[-8:-2]) == {"outside_cortex"}                # the last two are end artifacts

    def test_the_csd_and_xflip_are_reported_only(self, clean):
        x, r = clean
        erp, t = _sink_erp(n=x.shape[0], at=5)
        full = jnwb.curate_and_label(x, FS, pitch_um=PITCH, erp=erp, erp_times_ms=t,
                                     xflip_n_surrogates=20)
        assert full.anchor_um == r.anchor_um and np.array_equal(full.labels, r.labels)
        assert full.csd is not None and np.isfinite(full.csd_distance_um)
        assert np.isfinite(full.xflip_distance_um)

    def test_the_result_reads_like_a_dict_and_round_trips(self, clean):
        _, r = clean
        d = r.to_dict()
        assert r["grade"] == d["grade"] == "A" and "labels" in r and set(d["labels"]) <= set(jnwb.laminar_curation.LABELS)
        assert d["vflip"]["accepted"] is True and d["parameters"]["granular_thickness_um"] == 400.0

    def test_the_input_and_the_global_random_state_are_untouched(self):
        x = synth(n=24, n_ep=8)
        before, state = x.copy(), np.random.get_state()[1].copy()
        jnwb.curate_and_label(x, FS, pitch_um=PITCH, xflip_n_surrogates=10)
        assert np.array_equal(x, before)
        assert np.array_equal(np.random.get_state()[1], state)

    def test_the_xflip_surrogates_follow_the_seed(self):
        x = synth(n=32, n_ep=8)
        a = jnwb.curate_and_label(x, FS, pitch_um=PITCH, xflip_n_surrogates=20, rng=1)
        b = jnwb.curate_and_label(x, FS, pitch_um=PITCH, xflip_n_surrogates=20, rng=1)
        assert (a.xflip_distance_um == b.xflip_distance_um) or (np.isnan(a.xflip_distance_um)
                                                                 and np.isnan(b.xflip_distance_um))

    def test_refusals(self):
        x = synth(n=24, n_ep=4)
        with pytest.raises(ValueError, match="pitch_um"):
            jnwb.curate_and_label(x, FS, pitch_um=-1.0)
        with pytest.raises(ValueError, match="n_windows"):
            jnwb.curate_and_label(x, FS, pitch_um=PITCH, n_windows=9)
        with pytest.raises(ValueError, match="erp_times_ms"):
            jnwb.curate_and_label(x, FS, pitch_um=PITCH, erp=np.zeros((24, 10)))
        with pytest.raises(ValueError, match="dimensions"):
            jnwb.curate_and_label(x[0], FS, pitch_um=PITCH)
