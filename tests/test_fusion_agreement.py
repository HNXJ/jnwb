"""Fusion agreement (15-18): `fuse_laminar_anchors` reports agreement and caps the grade.

Until roadmap 15-19 calibrates a threshold, two present landmarks read `'unresolved'`
with the grade capped at `'B'`; a missing secondary reads `'unavailable'`; `'agree'`
and `'disagree'` are never emitted.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy import signal
from scipy.ndimage import gaussian_filter1d

import jnwb

FS = 500.0
PITCH = 25.0
WIN = np.array([600.0, 610.0, 590.0, 605.0])
# Stable windows with consistency 0.8: grades 'A' at baseline with one landmark.
A_KW = dict(window_um=WIN, consistency_deep=0.9, consistency_superficial=0.8)


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


def test_far_apart_landmarks_are_unresolved_and_capped():
    out = jnwb.fuse_laminar_anchors(vflip2_um=0.0, vflip_um=1000.0, contact_spacing_um=100,
                                    **A_KW)
    assert out["anchor_source"] == "vflip2" and out["anchor_um"] == 0.0
    assert out["agreement"] == "unresolved" and out["grade"] == "B"
    assert out["separation_contacts"] == 10.0
    assert out["distance_um"]["vflip"] == 1000.0 and out["distance_um"]["vflip2"] == 0.0


def test_equal_landmarks_are_still_unresolved_and_capped():
    out = jnwb.fuse_laminar_anchors(vflip2_um=600.0, vflip_um=600.0,
                                    contact_spacing_um=100, **A_KW)
    assert out["agreement"] == "unresolved" and out["grade"] == "B"
    assert out["separation_contacts"] == 0.0


def test_only_vflip_is_unavailable_with_the_grade_unchanged():
    out = jnwb.fuse_laminar_anchors(vflip_um=600.0, **A_KW)
    assert out["agreement"] == "unavailable" and out["grade"] == "A"
    assert np.isnan(out["separation_contacts"])


def test_only_vflip2_is_unavailable_with_the_grade_unchanged():
    out = jnwb.fuse_laminar_anchors(vflip2_um=600.0, **A_KW)
    assert out["anchor_source"] == "vflip2"
    assert out["agreement"] == "unavailable" and out["grade"] == "A"


def test_motif_only_is_unavailable_with_the_grade_unchanged():
    out = jnwb.fuse_laminar_anchors(motif_um=500.0, window_um=WIN,
                                    consistency_deep=1.0, consistency_superficial=1.0)
    assert out["anchor_source"] == "motif"
    assert out["agreement"] == "unavailable" and out["grade"] == "D"
    assert np.isnan(out["separation_contacts"])


def test_without_a_spacing_the_separation_is_nan_but_the_cap_applies():
    out = jnwb.fuse_laminar_anchors(vflip2_um=0.0, vflip_um=1000.0, **A_KW)
    assert out["agreement"] == "unresolved" and out["grade"] == "B"
    assert np.isnan(out["separation_contacts"])


@pytest.mark.parametrize("spacing", [0.0, -25.0, float("nan"), float("inf")])
def test_a_bad_spacing_is_refused(spacing):
    with pytest.raises(ValueError, match="contact_spacing_um"):
        jnwb.fuse_laminar_anchors(vflip2_um=0.0, vflip_um=1000.0,
                                  contact_spacing_um=spacing, **A_KW)


def test_curate_and_label_keeps_its_baseline_grade_and_anchor():
    # curate_and_label passes no vflip2 crossover, so agreement is 'unavailable'
    # and the cap never applies: the TestCurateAndLabel baseline pins grade and anchor.
    r = jnwb.curate_and_label(synth(), FS, pitch_um=PITCH, compute_xflip=False)
    assert r.grade == "A" and r.anchor_source == "vflip"
    assert abs(r.anchor_um - 24 * PITCH) <= 4 * PITCH
