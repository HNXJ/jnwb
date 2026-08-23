"""Canonical label-permutation primitive for null construction.

Added 2026-08-10 per the agent-harness audit (artifacts/.lab/agent-harness-audit-20260810.json,
claim-p0-deconfound-null-ignores-cycle-grouping): `omission.jnwb_ext.omission_identity
.decode_identity_cycle_deconfound` used leave-one-cycle-out CV for its observed statistic but a
naive, ungrouped `rng.permutation(y)` for its null -- an exchangeability mismatch between the
test statistic and the null it was compared against. `scripts/compute_omission_identity_
leakage_safe.py` had already solved this correctly with a private `_within_cycle_permutation`
helper; this module promotes that fix to a single, shared, explicit-scheme primitive so the
same bug cannot recur silently under a different filename.

Every call site MUST name a `scheme` explicitly -- there is no default. A bare
`rng.permutation(y)` inside grouped/session-structured decoding is what created this bug in the
first place; `tests/test_permutation_lint.py` greps the decoding-relevant modules and fails if
one shows up outside this module's own `scheme="global"` path.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np
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
    out = y.copy()
    for g in np.unique(groups):
        idx = np.flatnonzero(groups == g)
        out[idx] = rng.permutation(y[idx])
    return out


def build_permutation_plan(
    labels: Iterable[object],
    groups: Iterable[object],
    *,
    n_permutations: int,
    seed: int,
) -> dict:
    """Create an explicit within-group null plan (a manifest of digested draws); no model
    fitting occurs.

    PROMOTED 2026-08-23 from omission.jnwb_ext.structured_identity (99%-jnwb-sufficiency
    normalization) as a sibling to ``permute_labels``: it wraps that primitive with a
    reproducible manifest (per-draw seed and label digest) and never references omission's
    condition or trial semantics.

    Args:
        labels: label array, any dtype.
        groups: group id per sample, same length as ``labels``.
        n_permutations: number of permutation draws to generate.
        seed: base seed; draw ``i`` uses ``seed + i``.

    Returns:
        dict with ``draw_manifest`` (DataFrame: permutation, seed, label_digest, n_samples,
        n_groups), ``scheme`` (always "within_group"), ``seed``, ``n_permutations``, and
        ``group_composition_preserved`` (always True).
    """
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
    return {
        "draw_manifest": pd.DataFrame(draws),
        "scheme": "within_group",
        "seed": int(seed),
        "n_permutations": int(n_permutations),
        "group_composition_preserved": True,
    }
