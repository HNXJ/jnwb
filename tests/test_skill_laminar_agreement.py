"""The agreement vocabulary and the A-grade cap that the laminar skill reference states."""

from __future__ import annotations

import numpy as np

import jnwb

WINDOWS = np.array([100.0, 101.0, 102.0, 101.5])
STABLE = dict(window_um=WINDOWS, consistency_deep=1.0, consistency_superficial=1.0)


def test_agreement_reads_agree_disagree_or_unresolved_and_caps_a_unless_agree():
    agree = jnwb.fuse_laminar_anchors(vflip_um=100.0, vflip2_um=100.0,
                                      contact_spacing_um=10.0, **STABLE)
    assert agree["agreement"] == "agree"
    assert agree["grade"] == "A"

    disagree = jnwb.fuse_laminar_anchors(vflip_um=100.0, vflip2_um=10000.0,
                                         contact_spacing_um=10.0, **STABLE)
    assert disagree["agreement"] == "disagree"
    assert disagree["grade"] == "B"

    one_landmark = jnwb.fuse_laminar_anchors(vflip_um=100.0, contact_spacing_um=10.0, **STABLE)
    assert one_landmark["agreement"] == "unresolved"
    assert one_landmark["grade"] == "A"

    no_spacing = jnwb.fuse_laminar_anchors(vflip_um=100.0, vflip2_um=100.0, **STABLE)
    assert no_spacing["agreement"] == "unresolved"
    assert no_spacing["grade"] == "B"

    seen = {agree["agreement"], disagree["agreement"], one_landmark["agreement"],
            no_spacing["agreement"]}
    assert "unavailable" not in seen
