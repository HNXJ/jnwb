"""Canonical label-permutation primitive for null construction.

A decoder scored with grouped cross-validation (for example leave-one-cycle-out) but compared
against an ungrouped `rng.permutation(y)` null has an exchangeability mismatch between the test
statistic and its null. This module provides a single, shared, explicit-scheme primitive so
grouped nulls cannot silently fall back to ungrouped shuffles.

Every call site MUST name a `scheme` explicitly -- there is no default. A bare
`rng.permutation(y)` inside grouped/session-structured decoding produces that mismatch.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable, Optional

import numpy as np

from ._rng import (
    Default, REQUIRED, RNGLike, resolve_rng, resolve_seed_alias, sklearn_random_state,
)
import pandas as pd

SCHEMES = ("within_group", "global")

#: Relative width within which a null draw equals the observed statistic: 100 machine
#: epsilons of the observed value, the tolerance ``scipy.stats.permutation_test`` uses to
#: detect "numerically distinct but theoretically equal values in the null distribution".
_TIE_RTOL = 100.0 * float(np.finfo(float).eps)

_TAILS = ("greater", "less", "two-sided")


def _count_at_least_as_extreme(null, observed, alternative: str, *, atol: float = 0.0) -> int:
    """Number of null draws at least as extreme as ``observed``, ties within round-off included.

    A draw that reproduces the observed statistic, such as a permutation that swaps tied
    values, computes the same number with its terms summed in another order and can land an
    ulp on the wrong side of it. A bare ``>=`` then skips the draw and the p-value
    ``(1 + k) / (B + 1)`` comes out too small. A draw counts when it is within
    ``tol = max(atol, _TIE_RTOL * |observed|)`` of the observed value on the extreme side:

    - ``'greater'``: ``null >= observed - tol``;
    - ``'less'``: ``null <= observed + tol``;
    - ``'two-sided'``: the smaller of those two counts. The two-sided p is twice the p of
      that tail, capped at 1; :func:`_p_from_count` forms it.

    ``_TIE_RTOL`` is 100 machine epsilons, scipy's width. It is round-off: a draw of untied
    continuous data lands that close to the observed value with probability of order
    1e-14, so such data count the same draws as a bare comparison. ``atol`` is for a
    caller that can bound the round-off of a statistic that cancels towards zero, where a
    width relative to the value is too narrow; the mean differences of
    :mod:`jnwb.statistics` pass one. NaN draws never count.
    """
    if alternative not in _TAILS:
        raise ValueError(f"alternative must be one of {list(_TAILS)}; got {alternative!r}")
    null = np.asarray(null, dtype=float)
    obs = float(observed)
    tol = _tie_width(obs, atol)
    upper = int(np.count_nonzero(null >= obs - tol))
    lower = int(np.count_nonzero(null <= obs + tol))
    if alternative == "greater":
        return upper
    elif alternative == "less":
        return lower
    else:
        return min(upper, lower)


def _p_from_count(count, n_draws: int, alternative: str) -> float:
    """Permutation p from a count of :func:`_count_at_least_as_extreme` over ``n_draws`` draws.

    One-sided: ``(1 + count) / (n_draws + 1)``. Two-sided: ``min(1, 2 min(p_greater, p_less))``,
    which is ``min(1, 2 (1 + count) / (n_draws + 1))`` for the smaller-tail count that
    ``'two-sided'`` returns. ``n_draws`` is the number of draws the count was taken over;
    `_p_from_null` in :mod:`jnwb.jrsa` passes the draws that are not NaN.
    """
    if alternative not in _TAILS:
        raise ValueError(f"alternative must be one of {list(_TAILS)}; got {alternative!r}")
    p = (1.0 + count) / (n_draws + 1.0)
    return min(1.0, 2.0 * p) if alternative == "two-sided" else float(p)


def _tie_width(observed, atol: float = 0.0):
    """``max(atol, _TIE_RTOL * |observed|)``, elementwise for an array."""
    return np.maximum(float(atol), _TIE_RTOL * np.abs(observed))


def _count_each_at_least_as_extreme(values, *, atol: float = 0.0) -> np.ndarray:
    """For every element ``v`` of ``values``, the number of elements at least ``v`` by the
    rule of ``_count_at_least_as_extreme(values, v, 'greater', atol=atol)``.

    One sort and one binary search per element, O(n log n) where calling that function once
    per element is O(n^2); the counts are the same integers. ``values`` must be finite.
    """
    values = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("values must be finite")
    thresholds = values - _tie_width(values, atol)
    ordered = np.sort(values)
    return values.size - np.searchsorted(ordered, thresholds, side="left")


def _refuse_missing_groups(groups, func_name: str) -> None:
    """Refuse a group array holding NaN or None: a missing id equals no group, so its samples
    would keep their labels unpermuted and nothing would say so."""
    missing = int(np.count_nonzero(pd.isna(np.asarray(groups))))
    if missing:
        raise ValueError(
            f"{func_name}: groups holds {missing} missing label(s) (NaN or None); every sample "
            "needs a group id, since a missing id matches no group and its sample is never permuted."
        )


def permute_labels(
    y,
    *,
    groups=None,
    scheme: str,
    rng: RNGLike,
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
            for grouped/LOCO-style CV reproduces the exchangeability mismatch and should be
            treated as a code-review red flag, not a default).
        rng: required. An int seed, a numpy.random.Generator (advanced in place), or None
            for fresh OS entropy; NumPy's global state is never read.

    Returns:
        A permuted copy of `y`, same shape and dtype.

    Raises:
        ValueError: If ``scheme='within_group'`` and ``groups`` holds a NaN or None id.
    """
    y = np.asarray(y)
    if scheme not in SCHEMES:
        raise ValueError(f"scheme must be one of {SCHEMES}, got {scheme!r}")
    rng = resolve_rng(rng, func_name="permute_labels")

    if scheme == "global":
        return rng.permutation(y)

    # scheme == "within_group"
    if groups is None:
        raise ValueError("scheme='within_group' requires groups")
    groups = np.asarray(groups)
    if groups.shape[0] != y.shape[0]:
        raise ValueError(f"groups length {groups.shape[0]} != y length {y.shape[0]}")
    _refuse_missing_groups(groups, "permute_labels")
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


def _block_structure(labels, groups, blocks):
    """Block code per sample, and the first sample of each block, in code order.

    A block must carry one label and lie inside one group. A block that breaks either rule is
    refused by name, before any draw.
    """
    codes, uniques = pd.factorize(blocks, sort=False, use_na_sentinel=False)
    by_block = pd.DataFrame({"block": codes, "label": labels, "group": groups}).groupby("block")
    block_ids = np.asarray(uniques).tolist()
    multi = np.flatnonzero(by_block["label"].nunique(dropna=False).to_numpy() > 1)
    if multi.size:
        raise ValueError(
            f"build_permutation_plan: blocks={block_ids[multi[0]]!r} holds more than one label; "
            "a label that varies inside a block cannot be permuted as one unit."
        )
    spanning = np.flatnonzero(by_block["group"].nunique(dropna=False).to_numpy() > 1)
    if spanning.size:
        raise ValueError(
            f"build_permutation_plan: blocks={block_ids[spanning[0]]!r} spans more than one "
            "group; a block must lie inside one group."
        )
    _, first = np.unique(codes, return_index=True)
    return codes, first


def _permute_blocks(labels, groups, codes, first, rng):
    """One draw of block-constant labels: the block labels are permuted among the blocks of
    each group by :func:`permute_labels`, then every sample takes its block's new label."""
    block_labels = permute_labels(
        labels[first], groups=groups[first], scheme="within_group", rng=rng
    )
    return block_labels[codes]


def build_permutation_plan(
    labels: Iterable[object],
    groups: Iterable[object],
    *,
    n_permutations: int,
    rng: RNGLike = Default(REQUIRED),
    seed: Any = Default(REQUIRED),
    blocks: Optional[Iterable[object]] = None,
) -> dict:
    """Create an explicit within-group null plan (a manifest of digested draws); no model
    fitting occurs.

    Sibling to ``permute_labels``: wraps that primitive with a reproducible manifest (per-draw
    seed and label digest).

    Args:
        labels: label array, any dtype.
        groups: group id per sample, same length as ``labels``.
        n_permutations: number of permutation draws to generate.
        rng: required. An ``int`` base seed, a ``Generator`` or ``None`` for fresh OS
            entropy. Draw ``i`` is seeded with ``base + i``. An int is the base itself; a
            Generator gives one int drawn from it and ``None`` one int from a fresh
            ``default_rng()``. The base used is returned as ``seed``, and passing it back
            as ``rng`` reproduces the plan. (``seed`` is the old spelling and still works.)
        blocks: optional block id per sample, same length as ``labels``. A block is permuted
            as one unit: the block labels of each group are permuted among that group's
            blocks, and every sample takes its block's new label. A block must carry one
            label and lie inside one group.

    Returns:
        dict with ``draw_manifest`` (DataFrame: permutation, seed, label_digest, n_samples,
        n_groups), ``scheme`` (always "within_group"), ``seed`` (the int base seed used),
        ``n_permutations``, and ``group_composition_preserved`` (always True).

    Raises:
        TypeError: If ``rng`` is not an int, a Generator or None, or ``groups`` is None.
        ValueError: If ``blocks`` has the wrong length, ``groups`` holds a NaN or None, a
            block holds more than one label or spans more than one group, or ``seed`` is given
            with a different value from ``rng``. A float ``rng`` with no ``seed`` is a TypeError.
    """
    if groups is None:
        raise TypeError(
            "build_permutation_plan: groups is required, one group id per label; the plan "
            "permutes labels within groups. Give every label the same id to permute across "
            "all of them."
        )
    seed = resolve_seed_alias(rng, seed, alias_name='seed',
                              func_name='build_permutation_plan')
    # The manifest names every draw by an integer seed, so a Generator or None is turned
    # into one int base seed first, and an int is used as given.
    seed = sklearn_random_state(seed, func_name="build_permutation_plan")
    y = np.asarray(list(labels))
    group_array = np.asarray(list(groups))
    if y.ndim != 1 or group_array.shape != y.shape:
        raise ValueError("labels and groups must be one-dimensional and equally sized")
    _refuse_missing_groups(group_array, "build_permutation_plan")
    block_plan = None
    if blocks is not None:
        block_array = np.asarray(list(blocks))
        if block_array.ndim != 1 or block_array.shape != y.shape:
            raise ValueError(
                "build_permutation_plan: blocks must be one-dimensional with one block id per "
                f"label; got shape {block_array.shape} for {len(y)} labels."
            )
        block_plan = _block_structure(y, group_array, block_array)
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive")
    draws = []
    for permutation in range(n_permutations):
        draw_seed = int(seed + permutation)
        draw_rng = np.random.default_rng(draw_seed)
        if block_plan is None:
            permuted = permute_labels(
                y,
                groups=group_array,
                scheme="within_group",
                rng=draw_rng,
            )
        else:
            permuted = _permute_blocks(y, group_array, *block_plan, draw_rng)
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
