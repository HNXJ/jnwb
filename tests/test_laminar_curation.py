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


def blocked(n=32, n_ep=8, amp=2.0, seed=0):
    """``synth`` plus one independent 2-6 Hz source per half of the shaft: two correlation blocks."""
    x = synth(n=n, n_ep=n_ep, seed=seed)
    sos = signal.butter(4, [2, 6], btype="band", fs=FS, output="sos")
    s = signal.sosfiltfilt(sos, np.random.default_rng(seed + 100).standard_normal((2, n_ep, x.shape[-1])),
                           axis=-1)
    x[: n // 2] += amp * s[0] / s.std()
    x[n // 2:] += amp * s[1] / s.std()
    return x


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

    def test_a_run_of_exactly_max_run_is_interpolated(self):
        bad = np.zeros(10, bool)
        bad[3:6] = True
        out = jnwb.interpolate_channel_runs(np.arange(10.0), bad, max_run=3)
        assert out["interpolated_mask"][3:6].all() and np.allclose(out["data"], np.arange(10.0))

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

    def test_a_sink_at_exactly_min_sink_z_is_reported(self):
        erp, t = _sink_erp()
        z = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH)["strongest_z"]
        assert jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH, min_sink_z=z)["strongest_contact"] == 20

    def test_a_dip_shorter_than_the_onset_duration_is_no_onset(self):
        erp, t = _sink_erp()
        onset = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH)["earliest_onset_ms"]
        erp[8, t == onset] -= 50.0      # one 2 ms sample at the sink's onset, far deeper than it
        out = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH, onset_min_duration_ms=5.0)
        assert abs(out["earliest_contact"] - 20) <= 2
        brief = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH, onset_min_duration_ms=2.0)
        assert abs(brief["earliest_contact"] - 8) <= 1 and brief["earliest_onset_ms"] == onset

    def test_the_csd_is_the_public_voltage_curvature(self, monkeypatch):
        import jnwb.laminar_curation as lc
        calls = []

        def spy(*args, **kwargs):
            calls.append(1)
            return jnwb.voltage_curvature_1d(*args, **kwargs)

        erp, t = _sink_erp()
        before = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH)
        monkeypatch.setattr(lc, "voltage_curvature_1d", spy)
        assert jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH) == before and calls

    def test_too_few_usable_contacts_gives_nan(self):
        erp, t = _sink_erp()
        mask = np.zeros(erp.shape[0], bool)
        mask[:5] = True
        out = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH, usable_mask=mask)
        assert all(np.isnan(v) for v in out.values())

    def test_exactly_min_contacts_usable_is_enough(self):
        erp, t = _sink_erp()
        mask = np.zeros(erp.shape[0], bool)
        mask[12:28] = True
        out = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH, usable_mask=mask, min_contacts=16)
        assert abs(out["strongest_contact"] - 20) <= 1
        short = jnwb.evoked_csd_sink(erp, t, pitch_um=PITCH, usable_mask=mask, min_contacts=17)
        assert all(np.isnan(v) for v in short.values())

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

    def test_each_threshold_admits_its_boundary_value(self):
        # SD exactly stable_sd_um, exactly min_ok_windows windows, consistency exactly consistency_a
        out = jnwb.fuse_laminar_anchors(vflip_um=600.0, window_um=np.array([525.0, 675.0, np.nan, 600.0]),
                                        consistency_deep=0.75, consistency_superficial=0.9,
                                        stable_sd_um=float(np.nanstd([525.0, 675.0, 600.0])),
                                        min_ok_windows=3, consistency_a=0.75)
        assert out["n_windows_ok"] == 3 and out["stable"] and out["grade"] == "A"

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

    def test_the_csd_and_xflip_are_reported_only(self):
        x = blocked()
        erp, t = _sink_erp(n=x.shape[0], at=5)
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False)
        full = jnwb.curate_and_label(x, FS, pitch_um=PITCH, erp=erp, erp_times_ms=t,
                                     xflip_n_surrogates=20, rng=1)
        assert full.xflip.accepted and np.isfinite(full.xflip_distance_um)
        assert full.anchor_um == r.anchor_um and np.array_equal(full.labels, r.labels)
        assert full.csd is not None and np.isfinite(full.csd_distance_um)

    def test_a_rejected_xflip_reports_no_distance_and_says_why(self, clean):
        x, _ = clean                                   # smooth correlations: no block structure
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, xflip_n_surrogates=20)
        assert r.xflip is not None and not r.xflip.accepted and r.xflip.rejection_reason
        assert np.isnan(r.xflip_distance_um) and r.to_dict()["xflip"]["accepted"] is False

    def test_the_motif_crossing_anchors_when_vflip_rejects(self, clean, monkeypatch):
        import dataclasses
        import jnwb.laminar_curation as lc
        orig = lc._vflip_on

        def rejected(*args):
            _, v = orig(*args)
            return float("nan"), dataclasses.replace(v, accepted=False, crossover_contact=None)

        monkeypatch.setattr(lc, "_vflip_on", rejected)
        x, _ = clean
        fwd = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False)
        rev = jnwb.curate_and_label(x[::-1].copy(), FS, pitch_um=PITCH, compute_xflip=False)
        assert fwd.anchor_source == rev.anchor_source == "motif" and fwd.grade == rev.grade == "D"
        assert fwd.superficial_at_high_index is True and rev.superficial_at_high_index is False
        assert abs(fwd.anchor_um - 24 * PITCH) <= 4 * PITCH
        assert fwd.labels[5] == "deep" and fwd.labels[-5] == "superficial"

    def test_the_bands_reach_the_motif_profiles(self, clean):
        x, r = clean
        assert len(r.crossings_um) == 1 and r.consistency_deep == 1.0
        moved = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False, band_high_hz=(20.0, 40.0))
        assert moved.crossings_um == () and moved.consistency_deep < 0.75

    def test_a_band_above_150_hz_is_used_whole(self):
        import jnwb.laminar_curation as lc
        freqs = np.arange(0.0, 251.0)
        psd = np.ones((10, freqs.size))
        psd[:, freqs > 150] = np.arange(10.0)[:, None] + 1.0   # depth gradient only above 150 Hz
        _, hi = lc._band_profiles(psd, freqs, np.ones(10, bool), (10.0, 19.0), (160.0, 240.0))
        assert np.allclose(hi, np.arange(10.0) / 9.0)

    def test_the_call_is_recorded(self):
        x = blocked()
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, xflip_n_surrogates=20, rng=1)
        p = r.parameters
        assert "_" not in p and p["fs"] == FS and p["rng"] == 1 and p["nperseg"] == 512
        assert r.xflip.surrogate_seed_entropy is not None
        assert p["xflip_surrogate_seed_entropy"] == r.xflip.surrogate_seed_entropy
        assert jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False,
                                     rng=np.random.default_rng(0)).parameters["rng"] == "Generator"

    def test_a_low_sampling_rate_is_refused_naming_the_band(self):
        x = synth(n=24, n_ep=4)
        with pytest.raises(ValueError, match=r"band_high_hz=\(75\.0, 150\.0\).*power_band_hz=\(1\.0, 150\.0\)"):
            jnwb.curate_and_label(x, 250.0, pitch_um=PITCH, compute_xflip=False)
        with pytest.raises(ValueError, match=r"^power_band_hz"):
            jnwb.curate_and_label(x, 250.0, pitch_um=PITCH, compute_xflip=False,
                                  band_low_hz=(10.0, 19.0), band_high_hz=(75.0, 120.0))

    def test_the_named_thresholds_reach_their_consumers(self, clean):
        x, r = clean
        assert jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False, nperseg=256
                                     ).vflip.support_score != r.vflip.support_score
        few = jnwb.curate_and_label(x, FS, pitch_um=PITCH, min_contacts=x.shape[0] + 1)
        assert not few.vflip.accepted and few.xflip is None
        dead = x.copy()
        dead[20:24] = np.random.default_rng(9).standard_normal(dead[20:24].shape) * x.std()
        short = jnwb.curate_and_label(dead, FS, pitch_um=PITCH, compute_xflip=False)
        long = jnwb.curate_and_label(dead, FS, pitch_um=PITCH, compute_xflip=False, max_interpolate_run=4)
        assert short.bad_mask[20:24].all() and short.unusable_mask[20:24].all()
        assert long.interpolated_mask[20:24].all()

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
        x = blocked()
        a = jnwb.curate_and_label(x, FS, pitch_um=PITCH, xflip_n_surrogates=20, rng=1)
        b = jnwb.curate_and_label(x, FS, pitch_um=PITCH, xflip_n_surrogates=20, rng=1)
        c = jnwb.curate_and_label(x, FS, pitch_um=PITCH, xflip_n_surrogates=20, rng=2)
        assert np.isfinite(a.xflip_distance_um) and a.xflip_distance_um == b.xflip_distance_um
        assert a.xflip.p_values == b.xflip.p_values
        assert a.xflip.surrogate_seed_entropy != c.xflip.surrogate_seed_entropy

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


def _synth_in_bands(low, high, n=48, n_ep=40, n_s=1000, cross=24.0, seed=0):
    """``synth`` with the alpha-beta source in ``low`` Hz and the gamma source in ``high`` Hz."""
    rng = np.random.default_rng(seed)
    sup = 1 / (1 + np.exp(-(np.arange(n) - cross) / 3.0))
    shape = (n, n_ep, n_s)
    x = ((0.15 + 0.85 * (1 - sup))[:, None, None] * _band(rng, shape, *low)
         + (0.15 + 0.85 * sup)[:, None, None] * 0.6 * _band(rng, shape, *high))
    return x + 0.05 * gaussian_filter1d(rng.standard_normal(shape), 1.0, axis=0)


def _edge_shaft(n=100, block=6, seed=5):
    """``synth`` whose top ``block`` contacts share one independent 2-6 Hz source: a decorrelation
    jump between the shaft and its superficial end."""
    x = synth(n=n, n_ep=8, cross=n // 2 - 2.0)
    sos = signal.butter(4, [2, 6], btype="band", fs=FS, output="sos")
    s = signal.sosfiltfilt(sos, np.random.default_rng(seed).standard_normal((8, x.shape[-1])), axis=-1)
    x[-block:] += 3.0 * s / s.std()
    return x


class TestParametersReachTheirConsumers:
    def test_nperseg_reaches_the_power_criterion_welch(self):
        x = synth(n=24, n_ep=4)
        out = jnwb.detect_bad_channels(x, FS, nperseg=128)
        f, p = signal.welch(x, fs=FS, nperseg=128, axis=-1)
        sel = (f >= 1.0) & (f <= 150.0)
        expected = np.log10(p.mean(axis=1)[:, sel].mean(axis=1))
        assert np.allclose(out["log_power"], expected, rtol=1e-12)
        assert not np.allclose(out["log_power"], jnwb.detect_bad_channels(x, FS)["log_power"], rtol=1e-6)

    @pytest.mark.parametrize("high, refused", [(249.9, False), (250.0, True), (250.1, True)])
    def test_detect_bad_channels_refuses_a_band_ending_at_nyquist(self, high, refused):
        x = synth(n=24, n_ep=4)
        if refused:
            with pytest.raises(ValueError, match="power_band_hz must satisfy"):
                jnwb.detect_bad_channels(x, FS, power_band_hz=(1.0, high))
        else:
            assert jnwb.detect_bad_channels(x, FS, power_band_hz=(1.0, high))["bad_mask"].shape == (24,)

    @pytest.mark.parametrize("high, refused", [(124.9, False), (125.0, True), (125.1, True)])
    def test_a_motif_band_ending_at_nyquist_is_refused(self, high, refused):
        x = synth(n=24, n_ep=4)
        kw = dict(pitch_um=PITCH, compute_xflip=False, band_low_hz=(10.0, 19.0), power_band_hz=(1.0, 100.0))
        if refused:
            with pytest.raises(ValueError, match=rf"^band_high_hz=\(75\.0, {high}\) must end below fs/2"):
                jnwb.curate_and_label(x, 250.0, band_high_hz=(75.0, high), **kw)
        else:
            assert jnwb.curate_and_label(x, 250.0, band_high_hz=(75.0, high), **kw).labels.shape == (24,)

    @pytest.mark.parametrize("high, refused", [(124.9, False), (125.0, True), (125.1, True)])
    def test_a_low_motif_band_ending_at_nyquist_is_refused(self, high, refused):
        x = synth(n=24, n_ep=4)
        kw = dict(pitch_um=PITCH, compute_xflip=False, band_high_hz=(75.0, 120.0), power_band_hz=(1.0, 100.0))
        if refused:
            with pytest.raises(ValueError, match=rf"^band_low_hz=\(10\.0, {high}\) must end below fs/2"):
                jnwb.curate_and_label(x, 250.0, band_low_hz=(10.0, high), **kw)
        else:
            assert jnwb.curate_and_label(x, 250.0, band_low_hz=(10.0, high), **kw).labels.shape == (24,)

    @pytest.mark.parametrize("high, refused", [(124.9, False), (125.0, True), (125.1, True)])
    def test_a_power_band_ending_at_nyquist_is_refused(self, high, refused):
        x = synth(n=24, n_ep=4)
        kw = dict(pitch_um=PITCH, compute_xflip=False, band_high_hz=(75.0, 120.0), power_band_hz=(1.0, high))
        if refused:
            with pytest.raises(ValueError, match=rf"^power_band_hz=\(1\.0, {high}\) must end below fs/2"):
                jnwb.curate_and_label(x, 250.0, **kw)
        else:
            assert jnwb.curate_and_label(x, 250.0, **kw).labels.shape == (24,)

    def test_min_contacts_reaches_the_csd(self):
        x = blocked()
        erp, t = _sink_erp(n=x.shape[0], at=5)
        kw = dict(pitch_um=PITCH, compute_xflip=False, erp=erp, erp_times_ms=t)
        assert np.isfinite(jnwb.curate_and_label(x, FS, **kw).csd["strongest_contact"])
        few = jnwb.curate_and_label(x, FS, min_contacts=x.shape[0] + 1, **kw)
        assert all(np.isnan(v) for v in few.csd.values()) and np.isnan(few.csd_distance_um)

    def test_curate_and_label_passes_nperseg_to_the_bad_channel_detector(self, monkeypatch):
        import jnwb.laminar_curation as lc
        seen = []

        def spy(*args, **kwargs):
            seen.append(kwargs.get("nperseg"))
            return jnwb.detect_bad_channels(*args, **kwargs)

        monkeypatch.setattr(lc, "detect_bad_channels", spy)
        x = synth(n=24, n_ep=4)
        jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False, nperseg=128)
        jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False)
        assert seen == [128, 512]

    def test_the_csd_contact_count_boundary_is_exact(self):
        x = blocked()
        erp, t = _sink_erp(n=x.shape[0], at=5)
        kw = dict(pitch_um=PITCH, compute_xflip=False, erp=erp, erp_times_ms=t)
        k = int((~jnwb.curate_and_label(x, FS, **kw).unusable_mask).sum())
        assert 0 < k <= x.shape[0]
        at = jnwb.curate_and_label(x, FS, min_contacts=k, **kw)
        assert np.isfinite(at.csd["strongest_contact"])
        over = jnwb.curate_and_label(x, FS, min_contacts=k + 1, **kw)
        assert all(np.isnan(v) for v in over.csd.values())

    def test_min_contacts_reaches_every_vflip_call(self, monkeypatch):
        import jnwb.laminar_curation as lc
        seen = []

        def spy(*args, **kwargs):
            seen.append(kwargs["min_channels"])
            return jnwb.vflip(*args, **kwargs)

        monkeypatch.setattr(lc, "vflip", spy)
        jnwb.curate_and_label(synth(n=24, n_ep=8), FS, pitch_um=PITCH, compute_xflip=False,
                              n_windows=4, min_contacts=6)
        assert seen == [6] * 5                      # the pooled spectrum and each of 4 windows

    def test_max_interpolate_run_reaches_the_erp(self):
        x = synth()
        x[20:24] = np.random.default_rng(9).standard_normal(x[20:24].shape) * x.std()
        erp, t = _sink_erp(n=x.shape[0], at=5)
        erp[20:24] -= 50.0 * np.exp(-0.5 * ((t - 60.0) / 15.0) ** 2)   # a far deeper sink on the dead contacts
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False, erp=erp, erp_times_ms=t,
                                  max_interpolate_run=4)
        assert r.interpolated_mask[20:24].all()
        assert abs(r.csd["strongest_contact"] - 5) <= 2

    def test_min_edge_contacts_gates_the_edge_search(self):
        x = _edge_shaft()
        found = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False, min_edge_contacts=98)
        assert (~found.unusable_mask).sum() == 98 and "WM" not in found.labels   # the cortex it counts
        assert set(found.labels[-6:]) == {"outside_cortex"} and found.labels[70] == "superficial"
        none = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False, min_edge_contacts=99)
        assert "outside_cortex" not in none.labels and set(none.labels[-6:-2]) == {"superficial"}

    def test_the_window_bands_reach_the_window_motif_profiles(self, monkeypatch):
        import dataclasses
        import jnwb.laminar_curation as lc
        orig = lc._vflip_on

        def rejected(*args):
            _, v = orig(*args)
            return float("nan"), dataclasses.replace(v, accepted=False, crossover_contact=None)

        monkeypatch.setattr(lc, "_vflip_on", rejected)
        x = _synth_in_bands((25, 35), (200, 240))
        r = jnwb.curate_and_label(x, FS, pitch_um=PITCH, compute_xflip=False,
                                  band_low_hz=(25.0, 35.0), band_high_hz=(200.0, 240.0))
        assert r.anchor_source == "motif" and abs(r.anchor_um / PITCH - 24) <= 1
        assert np.all(np.abs(r.window_anchor_um / PITCH - 24) <= 1)    # every window sits on the planted crossing


class TestWindowsUseTheirOwnSpectra:
    """Two halves of the recording with the crossing planted at 18 and at 30 contacts."""

    @staticmethod
    def _two_halves():
        return np.concatenate([synth(n=48, n_ep=20, cross=18.0, seed=0),
                               synth(n=48, n_ep=20, cross=30.0, seed=1)], axis=1)

    def test_each_window_has_its_own_vflip_anchor(self):
        r = jnwb.curate_and_label(self._two_halves(), FS, pitch_um=PITCH, compute_xflip=False, n_windows=2)
        assert r.anchor_source == "vflip"
        assert abs(r.window_anchor_um[0] / PITCH - 18) <= 2
        assert abs(r.window_anchor_um[1] / PITCH - 30) <= 2

    def test_each_window_has_its_own_motif_anchor(self, monkeypatch):
        import dataclasses
        import jnwb.laminar_curation as lc
        orig = lc._vflip_on

        def rejected(*args):
            _, v = orig(*args)
            return float("nan"), dataclasses.replace(v, accepted=False, crossover_contact=None)

        monkeypatch.setattr(lc, "_vflip_on", rejected)
        r = jnwb.curate_and_label(self._two_halves(), FS, pitch_um=PITCH, compute_xflip=False, n_windows=2)
        assert r.anchor_source == "motif"
        assert abs(r.window_anchor_um[0] / PITCH - 18) <= 2
        assert abs(r.window_anchor_um[1] / PITCH - 30) <= 2


class TestGradeBoundaries:
    WIN = np.array([600.0, 610.0, 590.0, 605.0])

    @pytest.mark.parametrize("source, cmin, grade", [
        ("vflip_um", 0.6, "B"), ("vflip_um", 0.6 - 1e-9, "C"),
        ("motif_um", 0.75, "D"), ("motif_um", 0.75 - 1e-9, "F"),
    ])
    def test_the_consistency_boundary_of_grades_b_and_d(self, source, cmin, grade):
        out = jnwb.fuse_laminar_anchors(**{source: 600.0}, window_um=self.WIN,
                                        consistency_deep=0.95, consistency_superficial=cmin)
        assert out["stable"] and out["consistency"] == cmin and out["grade"] == grade
