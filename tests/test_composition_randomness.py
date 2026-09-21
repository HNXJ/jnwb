"""Randomness propagation across two composition boundaries (06-23, chains H9a and H9b).

Both chains are correct today. Neither was protected by a test that could fail, which is
why they are in the ruled subset of `artifacts/composition_subset_0.2.6.md` as regression
guards rather than as repairs.

H9a  `build_permutation_plan` -> `permute_labels`. The plan emits a `draw_manifest` whose
     rows carry a per-draw integer seed and a `label_digest`. That manifest is a provenance
     record, and a provenance record is worth what it can be redeemed for. The existing
     `tests/test_permutation.py::TestBuildPermutationPlan::test_deterministic_digests_given_seed`
     builds two plans from the same seed and compares their digests -- it re-runs the same
     internal loop, so it agrees with any self-consistent digest, including one spelled over
     the wrong bytes. What is asserted here instead is redemption: the digest is recomputed
     **outside** the builder, by replaying `permute_labels` at the seed the row records and
     hashing the result independently.

H9b  caller `rng`/`seed` -> `cluster_permutation_test`, and `directed_network` -> `granger`
     / `transfer_entropy`. Three legs, and all three are required:

       1. two different caller seeds give different surrogate nulls;
       2. one seed reproduces byte-identically;
       3. `n_jobs` does not move a digit.

     Leg 2 alone is what a stochastic child that reseeds itself would pass: it would be
     perfectly reproducible and perfectly deaf to the caller. Leg 1 is the half nothing in
     the suite asserted. `tests/test_statistics_api_split.py` pins same-seed reproducibility
     for the cluster test; `tests/test_parallel.py` pins `n_jobs` invariance for
     `directed_network` but passes no `rng`/`seed` at all and leaves `n_surrogates` at its
     default of 0. Measured: at that default the `p_matrix` holds analytic F-test p-values
     and no randomness is drawn, so `seed=7` and `seed=99` return the same matrix. Its
     `n_jobs` invariance is therefore the invariance of a deterministic quantity, and says
     nothing about a surrogate null.

Two traps this module is written around, both of which produce a green test over an
unchecked invariant:

  * `p_matrix` carries a NaN diagonal, and `np.array_equal` without `equal_nan=True`
    returns False for *any* pair of such matrices. Spelling leg 1 as
    `assert not np.array_equal(p_a, p_b)` therefore passes whether or not the seed
    propagates -- it passes on two identical matrices. Every comparison below is made on
    the finite entries, with the non-finite mask asserted equal separately.
  * a null of all-NaN or a manifest of one repeated digest satisfies a difference assertion
    for free. Each leg first establishes that the quantity it compares actually varies.

Import provenance is deliberately not asserted here. `tests/test_import_provenance.py` is
the designated harness for it -- it honours `JNWB_EXPECTED_PACKAGE_ROOT` and so qualifies an
installed copy as readily as a checkout, and
`tests/test_the_suite_can_qualify_an_installed_copy.py` reserves the assertion to that one
module.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from jnwb.connectivity import directed_network
from jnwb.permutation import build_permutation_plan, permute_labels
from jnwb.statistics import cluster_permutation_test

# Two caller seeds, used for every leg 1 below. Nothing depends on their values beyond
# being different from each other.
SEED_A = 7
SEED_B = 99


# --------------------------------------------------------------------------- H9a


#: Four groups of three, every group carrying both labels, so every group is permutable
#: and the within-group null is not a point mass.
PLAN_LABELS = np.array([0, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1, 0])
PLAN_GROUPS = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3])
PLAN_BASE_SEED = 11
PLAN_DRAWS = 4


def _digest_of(labels: np.ndarray) -> str:
    """sha256 over the label bytes, computed here rather than asked of the builder."""
    return hashlib.sha256(np.ascontiguousarray(labels).tobytes()).hexdigest()


def _replay(seed: int, scheme: str) -> np.ndarray:
    """The draw the manifest row claims was taken, taken again from the recorded seed."""
    return permute_labels(
        PLAN_LABELS,
        groups=PLAN_GROUPS,
        scheme=scheme,
        rng=np.random.default_rng(int(seed)),
    )


@pytest.fixture(scope="module")
def plan() -> dict:
    return build_permutation_plan(
        PLAN_LABELS, PLAN_GROUPS, n_permutations=PLAN_DRAWS, rng=PLAN_BASE_SEED
    )


class TestTheDrawManifestCanBeRedeemed:
    """The recorded digest has to describe the draw `permute_labels` actually produces."""

    def test_the_manifest_is_large_enough_and_varied_enough_to_falsify(self, plan) -> None:
        """A one-row manifest, or one repeated digest, makes the replay below cheap.

        `n_distinct_draws` is the builder's own count and is not trusted for this; the
        digests are counted here.
        """
        manifest = plan["draw_manifest"]
        assert len(manifest) == PLAN_DRAWS
        assert manifest["seed"].tolist() == [
            PLAN_BASE_SEED + i for i in range(PLAN_DRAWS)
        ]
        assert manifest["label_digest"].nunique() == PLAN_DRAWS, (
            "the draws are not all distinct, so a replay check could be satisfied by a "
            "manifest that recorded one frozen draw four times"
        )

    def test_every_row_replays_to_its_recorded_digest(self, plan) -> None:
        """The discriminator for H9a.

        What would make this pass while the invariant is violated: comparing the plan
        against a second plan, which re-runs the builder's own loop and so agrees with a
        digest spelled over the wrong bytes. The digest here is recomputed outside the
        builder from an independently seeded replay, so the builder's loop is not on both
        sides of the comparison.
        """
        manifest = plan["draw_manifest"]
        mismatches = []
        for _, row in manifest.iterrows():
            replayed = _digest_of(_replay(row["seed"], plan["scheme"]))
            if replayed != row["label_digest"]:
                mismatches.append(
                    f"seed={int(row['seed'])}: manifest {row['label_digest'][:16]} != "
                    f"independent replay {replayed[:16]}"
                )
        assert not mismatches, (
            "the draw manifest does not describe the draws `permute_labels` produces at "
            f"the seeds it records: {mismatches}"
        )

    def test_the_digest_is_seed_sensitive_so_the_replay_could_have_failed(self, plan) -> None:
        """Establishes the replay above has discriminating power.

        If the digest did not depend on the seed, every row would replay against every
        seed and the test above would hold for a builder that ignored its seed entirely.
        """
        manifest = plan["draw_manifest"]
        wrong_seed_matches = [
            int(row["seed"])
            for _, row in manifest.iterrows()
            if _digest_of(_replay(row["seed"] + PLAN_DRAWS, plan["scheme"]))
            == row["label_digest"]
        ]
        assert not wrong_seed_matches, (
            "a digest recorded against one seed replays from a different seed, so the "
            f"replay check cannot detect a drifted draw: seeds {wrong_seed_matches}"
        )

    def test_the_digest_is_over_the_permuted_labels_not_the_originals(self, plan) -> None:
        """`group_composition_preserved` makes the two easy to confuse.

        Every draw preserves the label multiset, so a builder that hashed the input
        labels would produce a manifest that still looked plausible -- constant, but
        plausible.
        """
        unpermuted = _digest_of(PLAN_LABELS)
        assert unpermuted not in set(plan["draw_manifest"]["label_digest"]), (
            "a manifest row carries the digest of the unpermuted labels"
        )

    def test_each_replayed_draw_honours_the_scheme_the_plan_names(self, plan) -> None:
        """The plan claims `scheme='within_group'` and `group_composition_preserved=True`.

        Checked against the documented contract rather than against the implementation:
        each group's own label multiset survives the draw. A global shuffle would move
        labels between groups and still produce a self-consistent manifest.
        """
        assert plan["scheme"] == "within_group"
        assert plan["group_composition_preserved"] is True
        for _, row in plan["draw_manifest"].iterrows():
            replayed = _replay(row["seed"], plan["scheme"])
            for group in np.unique(PLAN_GROUPS):
                inside = PLAN_GROUPS == group
                assert sorted(replayed[inside]) == sorted(PLAN_LABELS[inside]), (
                    f"seed {int(row['seed'])} moved labels across group {group}, so "
                    "`group_composition_preserved=True` is not what the draw did"
                )


# --------------------------------------------------------------------------- H9b


def _finite_mask(a: np.ndarray) -> np.ndarray:
    return np.isfinite(a)


def _assert_same_support(a: np.ndarray, b: np.ndarray, what: str) -> np.ndarray:
    """Both arrays are finite in the same places, and somewhere. Returns that mask.

    Without this, every comparison below could be made over an empty selection, which
    satisfies "identical" trivially and makes "differs" impossible to state honestly.
    """
    mask_a, mask_b = _finite_mask(a), _finite_mask(b)
    np.testing.assert_array_equal(
        mask_a, mask_b, err_msg=f"{what}: the two runs are finite in different places"
    )
    assert mask_a.any(), f"{what}: nothing is finite, so there is nothing to compare"
    return mask_a


def _assert_identical(a: np.ndarray, b: np.ndarray, what: str) -> None:
    """Byte-identical on the finite entries, with the non-finite pattern also equal."""
    mask = _assert_same_support(a, b, what)
    assert a[mask].tobytes() == b[mask].tobytes(), (
        f"{what}: expected byte-identical values, got max abs difference "
        f"{np.max(np.abs(a[mask] - b[mask]))}"
    )


def _assert_differs(a: np.ndarray, b: np.ndarray, what: str) -> None:
    """Differs somewhere among the entries that are finite in both.

    Stated on the finite entries on purpose: `np.array_equal` on a matrix with a NaN
    diagonal is False no matter what the finite entries say, so the negation of it is a
    difference assertion that passes on two identical matrices.
    """
    mask = _assert_same_support(a, b, what)
    assert np.any(a[mask] != b[mask]), (
        f"{what}: two different caller seeds produced an identical result across all "
        f"{int(mask.sum())} finite entries, so the caller's seed does not reach the "
        "surrogate draw"
    )


# ---- cluster_permutation_test


@pytest.fixture(scope="module")
def cluster_runs() -> dict:
    gen = np.random.default_rng(0)
    X = gen.normal(size=(14, 20))
    Y = gen.normal(size=(14, 20))
    Y[:, 5:10] += 1.1

    def run(seed: int, n_jobs: int = 1) -> np.ndarray:
        return cluster_permutation_test(
            X, Y, n_permutations=64, threshold=2.0, rng=seed, n_jobs=n_jobs
        )["max_null_stats"]

    return {
        "a": run(SEED_A),
        "a_again": run(SEED_A),
        "b": run(SEED_B),
        "a_parallel": run(SEED_A, n_jobs=4),
    }


class TestClusterPermutationNullFollowsTheCallerSeed:
    def test_the_null_is_finite_and_not_degenerate(self, cluster_runs) -> None:
        """A null of all-NaN makes `a != b` true everywhere and leg 1 vacuous."""
        null = cluster_runs["a"]
        assert null.shape == (64,)
        assert np.isfinite(null).all(), "a non-finite null makes every comparison free"
        assert np.unique(null).size > 1, "the null is a point mass; it carries no draw"

    def test_two_different_seeds_give_different_nulls(self, cluster_runs) -> None:
        _assert_differs(cluster_runs["a"], cluster_runs["b"], "cluster max_null_stats")

    def test_one_seed_reproduces_byte_identically(self, cluster_runs) -> None:
        _assert_identical(
            cluster_runs["a"], cluster_runs["a_again"], "cluster max_null_stats"
        )

    def test_n_jobs_does_not_move_a_digit(self, cluster_runs) -> None:
        _assert_identical(
            cluster_runs["a"], cluster_runs["a_parallel"], "cluster max_null_stats n_jobs"
        )


# ---- directed_network -> granger / transfer_entropy


#: `granger` defaults to `n_surrogates=0`, where the `p_matrix` holds analytic F-test
#: p-values and no randomness is drawn at all. Both methods are run with surrogates on, or
#: there is no null for the caller's seed to reach.
NETWORK_METHODS = {
    "granger": dict(n_surrogates=24, order=2),
    "transfer_entropy": dict(n_surrogates=24, bins=3),
}


@pytest.fixture(scope="module", params=sorted(NETWORK_METHODS))
def network_runs(request) -> dict:
    method = request.param
    kwargs = NETWORK_METHODS[method]
    gen = np.random.default_rng(4)
    signals = gen.normal(size=(3, 6, 260))
    signals[1, :, 3:] += 0.7 * signals[0, :, :-3]

    def run(seed: int, n_jobs: int = 1) -> np.ndarray:
        return directed_network(
            signals, method=method, fdr=False, n_jobs=n_jobs, seed=seed, **kwargs
        )["p_matrix"]

    return {
        "method": method,
        "a": run(SEED_A),
        "a_again": run(SEED_A),
        "b": run(SEED_B),
        "a_parallel": run(SEED_A, n_jobs=4),
    }


class TestDirectedNetworkSurrogatesFollowTheCallerSeed:
    """Run for both methods. Only `granger` is composed through `directed_network`
    anywhere else in `tests/`, so `transfer_entropy` reaches this boundary here first."""

    def test_the_p_matrix_has_a_real_off_diagonal_to_compare(self, network_runs) -> None:
        p = network_runs["a"]
        off = ~np.eye(p.shape[0], dtype=bool)
        assert np.isnan(np.diag(p)).all(), "the diagonal is supposed to be NaN"
        assert np.isfinite(p[off]).all(), (
            f"{network_runs['method']}: off-diagonal p-values are not all finite, so a "
            "comparison over them would silently shrink"
        )
        assert int(off.sum()) == 6

    def test_two_different_seeds_give_different_p_values(self, network_runs) -> None:
        _assert_differs(
            network_runs["a"], network_runs["b"], f"{network_runs['method']} p_matrix"
        )

    def test_one_seed_reproduces_byte_identically(self, network_runs) -> None:
        _assert_identical(
            network_runs["a"],
            network_runs["a_again"],
            f"{network_runs['method']} p_matrix",
        )

    def test_n_jobs_does_not_move_a_digit(self, network_runs) -> None:
        _assert_identical(
            network_runs["a"],
            network_runs["a_parallel"],
            f"{network_runs['method']} p_matrix n_jobs",
        )
