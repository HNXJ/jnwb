"""Fusion agreement: `fuse_laminar_anchors` reports agreement from a threshold.

Two present landmarks are compared against ``VFLIP2_VFLIP_AGREEMENT_T_CONTACTS``, the
95th percentile of the ``|vFLIP2 - vFLIP|`` gap on a null probe
(``scripts/calibrate_vflip2_separation.py``): ``'agree'`` at or below T keeps the
grade, ``'disagree'`` above it caps an ``'A'`` at ``'B'``. A missing landmark, or both
present with no ``contact_spacing_um``, reads ``'unresolved'``; the cap applies only
while both landmarks are present, so a lone landmark grades exactly as before.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np
import pytest
from scipy import signal
from scipy.ndimage import gaussian_filter1d

import jnwb
from jnwb.laminar_curation import VFLIP2_VFLIP_AGREEMENT_T_CONTACTS as T

FS = 500.0
PITCH = 25.0
WIN = np.array([600.0, 610.0, 590.0, 605.0])
# Stable windows with consistency 0.8: grades 'A' at baseline with one landmark.
A_KW = dict(window_um=WIN, consistency_deep=0.9, consistency_superficial=0.8)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts.calibrate_vflip2_separation import gap_for_seed, run, threshold  # noqa: E402

RAW = REPO_ROOT / "artifacts" / "benchmarks" / "calibration" / "vflip2_separation_0.2.14_raw.json"


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


def test_equal_landmarks_agree_and_keep_the_grade():
    out = jnwb.fuse_laminar_anchors(vflip2_um=600.0, vflip_um=600.0,
                                    contact_spacing_um=1.0, **A_KW)
    assert out["anchor_source"] == "vflip2" and out["anchor_um"] == 600.0
    assert out["agreement"] == "agree" and out["grade"] == "A"
    assert out["separation_contacts"] == 0.0


def test_separation_at_the_threshold_agrees():
    # spacing 1.0 um keeps the arithmetic exact: |T - 0| / 1 is T itself.
    out = jnwb.fuse_laminar_anchors(vflip2_um=T, vflip_um=0.0,
                                    contact_spacing_um=1.0, **A_KW)
    assert out["separation_contacts"] == T
    assert out["agreement"] == "agree" and out["grade"] == "A"


def test_separation_above_the_threshold_disagrees_and_caps():
    out = jnwb.fuse_laminar_anchors(vflip2_um=T + 1.0, vflip_um=0.0,
                                    contact_spacing_um=1.0, **A_KW)
    assert out["separation_contacts"] == T + 1.0
    assert out["agreement"] == "disagree" and out["grade"] == "B"


def test_planted_far_apart_landmarks_disagree_and_cap():
    out = jnwb.fuse_laminar_anchors(vflip2_um=0.0, vflip_um=3000.0,
                                    contact_spacing_um=100, **A_KW)
    assert out["anchor_source"] == "vflip2" and out["anchor_um"] == 0.0
    assert out["agreement"] == "disagree" and out["grade"] == "B"
    assert out["separation_contacts"] == 30.0
    assert out["distance_um"]["vflip"] == 3000.0 and out["distance_um"]["vflip2"] == 0.0


def test_only_vflip_is_unresolved_with_the_grade_unchanged():
    out = jnwb.fuse_laminar_anchors(vflip_um=600.0, contact_spacing_um=1.0, **A_KW)
    assert out["agreement"] == "unresolved" and out["grade"] == "A"
    assert np.isnan(out["separation_contacts"])


def test_only_vflip2_is_unresolved_with_the_grade_unchanged():
    out = jnwb.fuse_laminar_anchors(vflip2_um=600.0, contact_spacing_um=1.0, **A_KW)
    assert out["anchor_source"] == "vflip2"
    assert out["agreement"] == "unresolved" and out["grade"] == "A"


def test_motif_only_is_unresolved_with_the_grade_unchanged():
    out = jnwb.fuse_laminar_anchors(motif_um=500.0, window_um=WIN,
                                    consistency_deep=1.0, consistency_superficial=1.0)
    assert out["anchor_source"] == "motif"
    assert out["agreement"] == "unresolved" and out["grade"] == "D"
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


def test_the_shipped_constant_is_the_receipt_threshold():
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    assert raw["threshold_contacts"] == T


def test_the_threshold_is_the_95th_percentile_of_the_defined_gaps():
    gaps = [0.0, 4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0]
    assert threshold(gaps) == float(np.percentile(gaps, 95.0))
    assert math.isnan(threshold([]))


def test_one_null_draw_reproduces_its_gap():
    first, second = gap_for_seed(11), gap_for_seed(11)
    assert first == second
    assert first["gap_contacts"] is None or isinstance(first["gap_contacts"], float)


def test_small_runs_reproduce_the_threshold_and_trials():
    first, second = run(0, 32), run(0, 32)
    assert first["threshold_contacts"] == second["threshold_contacts"]
    assert first["trials"] == second["trials"]


def test_curate_and_label_keeps_its_baseline_grade_and_anchor():
    # curate_and_label passes no vflip2 crossover, so agreement is 'unresolved'
    # and the cap never applies without both landmarks: the TestCurateAndLabel
    # baseline pins grade and anchor.
    r = jnwb.curate_and_label(synth(), FS, pitch_um=PITCH, compute_xflip=False)
    assert r.grade == "A" and r.anchor_source == "vflip"
    assert abs(r.anchor_um - 24 * PITCH) <= 4 * PITCH
