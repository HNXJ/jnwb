"""Canonical label-permutation primitive for null construction.

Added 2026-08-10 after an audit found a downstream decoder using leave-one-cycle-out CV for
its observed statistic but a naive, ungrouped `rng.permutation(y)` for its null -- an
exchangeability mismatch between the
test statistic and the null it was compared against. This module provides a single, shared,
explicit-scheme primitive so grouped nulls cannot silently fall back to ungrouped shuffles.

Every call site MUST name a `scheme` explicitly -- there is no default. A bare
`rng.permutation(y)` inside grouped/session-structured decoding is what created this bug in the
first place; `tests/test_permutation_lint.py` greps the decoding-relevant modules and fails if
one shows up outside this module's own `scheme="global"` path.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

import numpy as np

from ._rng import Default, REQUIRED, RNGLike, resolve_seed_alias
import pandas as pd

SCHEMES = ("within_group", "global")


def permute_labels(
    y,
    *,
    groups=None,
    scheme: str,
    rng: np.random.Generator,
):
    """Permute labels under an explicitly named exchangeability scheme.

    Args:
        y: label array, any dtype, shape (n,).
        groups: group id per sample (e.g. cycle_id), shape (n,). Required for
            scheme="within_group": within-group permutation preserves each group's own label
            composition and is exchangeable under the null that labels are unrelated to the
            outcome CONDITIONAL on group membership -- the correct null when the CV scheme
            itself holds out whole groups (leave-one-group-out), since it never lets a
            permutation draw create a label pattern that couldn't have arisen from the real
            per-group structure.
        scheme: "within_group" (permute inside each group independently, group composition
            preserved) or "global" (permute across all samples, ignoring groups -- only valid
            when there is no grouping structure the CV scheme depends on; passing this scheme
            for grouped/LOCO-style CV reproduces the audit-flagged bug and should be treated as
            a code-review red flag, not a default).
        rng: an explicit numpy.random.Generator -- no implicit global RNG state.

    Returns:
        A permuted copy of `y`, same shape and dtype.
    """
    y = np.asarray(y)
    if scheme not in SCHEMES:
        raise ValueError(f"scheme must be one of {SCHEMES}, got {scheme!r}")
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be an explicit numpy.random.Generator (e.g. np.random.default_rng(seed))")

    if scheme == "global":
        return rng.permutation(y)

    # scheme == "within_group"
    if groups is None:
        raise ValueError("scheme='within_group' requires groups")
    groups = np.asarray(groups)
    if groups.shape[0] != y.shape[0]:
        raise ValueError(f"groups length {groups.shape[0]} != y length {y.shape[0]}")
    # A group holding a single distinct label cannot be permuted: rng.permutation of a
    # constant is that constant. If NO group holds two distinct labels -- the nested design
    # where each group carries exactly one condition -- every draw is the original labelling
    # and the null is a point mass, so any test built on it returns p = 1.0 by construction.
    # This used to happen silently: 1000 of 1000 draws came back identical, and
    # build_permutation_plan emitted a 500-row manifest carrying a single distinct digest.
    # Within-group exchangeability genuinely does not exist for that design, so say so
    # instead of returning a vacuous null.
    permutable = [g for g in np.unique(groups)
                  if len(np.unique(y[groups == g])) > 1]
    if not permutable:
        raise ValueError(
            "scheme='within_group' has no exchangeability for this design: every group "
            "carries a single distinct label, so every permutation is the identity and any "
            "p-value computed from it would be 1.0 by construction. Labels are nested "
            "within groups here; permute at the group level instead (permute the labels "
            "attached to whole groups), or use scheme='global' if no grouping structure "
            "constrains the analysis."
        )

    out = y.copy()
    for g in permutable:
        idx = np.flatnonzero(groups == g)
        out[idx] = rng.permutation(y[idx])
    return out


def build_permutation_plan(
    labels: Iterable[object],
    groups: Iterable[object],
    *,
    n_permutations: int,
    rng: int = Default(REQUIRED),
    seed: Any = Default(REQUIRED),
) -> dict:
    """Create an explicit within-group null plan (a manifest of digested draws); no model
    fitting occurs.

    Sibling to ``permute_labels``: wraps that primitive with a reproducible manifest (per-draw
    seed and label digest).

    Args:
        labels: label array, any dtype.
        groups: group id per sample, same length as ``labels``.
        n_permutations: number of permutation draws to generate.
        rng: base seed, an ``int``. Unlike the rest of the package this one cannot take a
            ``Generator`` or ``None``: the plan's whole product is a manifest of integer
            per-draw seeds, ``rng + i``, which a Generator cannot name and fresh entropy
            would make unreproducible. (``seed`` is the old spelling and still works.)

    Returns:
        dict with ``draw_manifest`` (DataFrame: permutation, seed, label_digest, n_samples,
        n_groups), ``scheme`` (always "within_group"), ``seed``, ``n_permutations``, and
        ``group_composition_preserved`` (always True).
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed',
                              func_name='build_permutation_plan')
    if not isinstance(seed, (int, np.integer)) or isinstance(seed, bool):
        raise TypeError(
            "build_permutation_plan: rng must be an int base seed, because the plan "
            "records the integer seed `rng + i` of every draw; got "
            f"{type(seed).__name__}."
        )
    y = np.asarray(list(labels))
    group_array = np.asarray(list(groups))
    if y.ndim != 1 or group_array.shape != y.shape:
        raise ValueError("labels and groups must be one-dimensional and equally sized")
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive")
    draws = []
    for permutation in range(n_permutations):
        draw_seed = int(seed + permutation)
        permuted = permute_labels(
            y,
            groups=group_array,
            scheme="within_group",
            rng=np.random.default_rng(draw_seed),
        )
        digest = hashlib.sha256(np.ascontiguousarray(permuted).tobytes()).hexdigest()
        draws.append(
            {
                "permutation": permutation,
                "seed": draw_seed,
                "label_digest": digest,
                "n_samples": int(len(y)),
                "n_groups": int(len(np.unique(group_array))),
            }
        )
    manifest = pd.DataFrame(draws)
    return {
        "draw_manifest": manifest,
        "scheme": "within_group",
        "seed": int(seed),
        "n_permutations": int(n_permutations),
        "group_composition_preserved": True,
        # How much null there actually is. A manifest of n_permutations rows says nothing
        # about whether the draws differ from each other or from the observed labelling.
        "n_permutable_groups": int(sum(
            len(np.unique(y[group_array == g])) > 1 for g in np.unique(group_array)
        )),
        "n_distinct_draws": int(manifest["label_digest"].nunique()),
    }
