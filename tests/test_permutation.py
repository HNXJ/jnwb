"""Unit tests for jnwb.permutation.permute_labels -- the canonical exchangeability-scheme
primitive added 2026-08-10 to fix the naive-global-permutation-null bug found in
decode_identity_cycle_deconfound (artifacts/.lab/agent-harness-audit-20260810.json).

Added to jnwb.__all__ 2026-08-22 (normalization Batch 2, item 1) after independent
verification: experiment-independent semantics, no embedded omission condition
names/constants, stable signature since 2026-08-10, and every existing caller already
uses the intended `from jnwb.permutation import permute_labels` interface."""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.permutation import permute_labels, build_permutation_plan


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        """The public surface is `from jnwb import permute_labels`, not just the submodule path."""
        from jnwb import permute_labels as public_permute_labels

        assert public_permute_labels is permute_labels

    def test_listed_in_jnwb_all(self):
        import jnwb

        assert "permute_labels" in jnwb.__all__
        assert "build_permutation_plan" in jnwb.__all__

    def test_build_permutation_plan_importable_from_top_level_jnwb(self):
        import jnwb

        assert jnwb.build_permutation_plan is build_permutation_plan

    def test_omission_structured_identity_delegates_to_jnwb(self):
        si = pytest.importorskip("omission.jnwb_ext.structured_identity")
        assert si.build_permutation_plan is build_permutation_plan


class TestPermuteLabelsContract:
    def test_requires_explicit_scheme(self):
        rng = np.random.default_rng(0)
        with pytest.raises(TypeError):
            permute_labels(np.array([0, 1, 0, 1]), rng=rng)  # missing scheme, keyword-only

    def test_rejects_unknown_scheme(self):
        rng = np.random.default_rng(0)
        with pytest.raises(ValueError, match="scheme"):
            permute_labels(np.array([0, 1]), scheme="bogus", rng=rng)

    def test_within_group_requires_groups(self):
        rng = np.random.default_rng(0)
        with pytest.raises(ValueError, match="groups"):
            permute_labels(np.array([0, 1, 0, 1]), scheme="within_group", rng=rng)

    def test_rejects_non_generator_rng(self):
        with pytest.raises(TypeError, match="Generator"):
            permute_labels(np.array([0, 1]), scheme="global", rng=42)

    def test_groups_length_mismatch_raises(self):
        rng = np.random.default_rng(0)
        with pytest.raises(ValueError, match="length"):
            permute_labels(
                np.array([0, 1, 0, 1]), groups=np.array([0, 0, 1]), scheme="within_group", rng=rng
            )


class TestWithinGroupPreservesGroupComposition:
    def test_per_group_label_counts_unchanged(self):
        rng = np.random.default_rng(42)
        labels = np.array([0, 0, 1, 1, 0, 1, 1, 1])
        groups = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        perm = permute_labels(labels, groups=groups, scheme="within_group", rng=rng)
        for g in np.unique(groups):
            m = groups == g
            assert sorted(perm[m].tolist()) == sorted(labels[m].tolist())

    def test_output_differs_from_input_with_high_probability(self):
        rng = np.random.default_rng(1)
        labels = np.arange(20) % 2
        groups = np.zeros(20, dtype=int)
        perm = permute_labels(labels, groups=groups, scheme="within_group", rng=rng)
        assert not np.array_equal(perm, labels)

    def test_single_member_group_is_a_no_op_for_that_group(self):
        rng = np.random.default_rng(0)
        labels = np.array([0, 1, 1, 0])
        groups = np.array([0, 1, 1, 1])
        perm = permute_labels(labels, groups=groups, scheme="within_group", rng=rng)
        assert perm[0] == labels[0]  # only member of group 0 -- nothing to permute against

    def test_deterministic_given_seed(self):
        labels = np.arange(12) % 3
        groups = np.repeat([0, 1, 2], 4)
        perm_a = permute_labels(labels, groups=groups, scheme="within_group", rng=np.random.default_rng(7))
        perm_b = permute_labels(labels, groups=groups, scheme="within_group", rng=np.random.default_rng(7))
        np.testing.assert_array_equal(perm_a, perm_b)


class TestGlobalScheme:
    def test_global_ignores_groups_argument(self):
        rng = np.random.default_rng(3)
        labels = np.arange(10)
        perm = permute_labels(labels, groups=np.zeros(10), scheme="global", rng=rng)
        assert sorted(perm.tolist()) == sorted(labels.tolist())

    def test_global_can_move_labels_across_group_boundaries(self):
        """The whole point of 'global' vs 'within_group': unlike within_group, global
        permutation is not constrained to preserve each group's own label composition."""
        rng = np.random.default_rng(2)
        labels = np.array([0] * 10 + [1] * 10)
        groups = np.array([0] * 10 + [1] * 10)
        perm = permute_labels(labels, groups=groups, scheme="global", rng=rng)
        # overall multiset is preserved (still a valid permutation)...
        assert sorted(perm.tolist()) == sorted(labels.tolist())
        # ...but group 0's slice is not guaranteed to still be all-0s the way within_group
        # would force it to be -- with this seed it demonstrably is not.
        assert sorted(perm[:10].tolist()) != sorted(labels[:10].tolist())


class TestBuildPermutationPlan:
    def test_rejects_mismatched_lengths(self):
        with pytest.raises(ValueError, match="equally sized"):
            build_permutation_plan([0, 1, 0], [0, 0], n_permutations=2, seed=0)

    def test_rejects_nonpositive_n_permutations(self):
        with pytest.raises(ValueError, match="positive"):
            build_permutation_plan([0, 1], [0, 0], n_permutations=0, seed=0)

    def test_draw_manifest_has_one_row_per_permutation(self):
        plan = build_permutation_plan(
            [0, 0, 1, 1, 0, 1, 1, 1], [0, 0, 0, 0, 1, 1, 1, 1], n_permutations=5, seed=1
        )
        assert len(plan["draw_manifest"]) == 5
        assert plan["scheme"] == "within_group"
        assert plan["n_permutations"] == 5
        assert plan["group_composition_preserved"] is True

    def test_seeds_are_sequential_from_base(self):
        plan = build_permutation_plan([0, 1, 0, 1], [0, 0, 1, 1], n_permutations=3, seed=100)
        assert plan["draw_manifest"]["seed"].tolist() == [100, 101, 102]

    def test_deterministic_digests_given_seed(self):
        labels, groups = [0, 0, 1, 1, 0, 1], [0, 0, 0, 1, 1, 1]
        plan_a = build_permutation_plan(labels, groups, n_permutations=3, seed=7)
        plan_b = build_permutation_plan(labels, groups, n_permutations=3, seed=7)
        assert (
            plan_a["draw_manifest"]["label_digest"].tolist()
            == plan_b["draw_manifest"]["label_digest"].tolist()
        )

    def test_manifest_records_sample_and_group_counts(self):
        plan = build_permutation_plan([0, 0, 1, 1], [0, 0, 1, 1], n_permutations=1, seed=0)
        row = plan["draw_manifest"].iloc[0]
        assert row["n_samples"] == 4
        assert row["n_groups"] == 2
