"""`bin_ms` selects between two estimators, and the skill claimed only one.

`skills/jnwb-connectivity/SKILL.md` routed `cross_modal_comparison` as a best-lag
correlation, showed `bin_ms=None` in the routing signature, and told the reader to "Read
`lag_corrected_pvalue`, not the parametric p, which pays nothing for the lag search". Called
exactly as routed, the function returns five keys and `lag_corrected_pvalue` is not among
them: without a bin width there is no way to convert `lag_range_ms` into a sample shift, so
a single zero-lag correlation is computed instead and `n_permutations` and `rng` go unused.

An agent following the skill therefore reached for a key that was absent, having been told
in the same sentence not to trust the one that was present.

The function's own docstring and its `interpretation` field were both already explicit about
this -- the disagreement was between two faces, not inside the code -- so what is pinned here
is the behaviour each face has to describe, and the skill line is checked against it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "jnwb-connectivity" / "SKILL.md"

BIN_MS = 10.0
N_PERMUTATIONS = 200


@pytest.fixture(scope="module")
def coupled_series():
    """A spike series lagging the LFP series by three samples, i.e. -30 ms at 10 ms bins."""
    rng = np.random.default_rng(0)
    tfr = rng.standard_normal((12, 200))
    spikes = 0.5 * np.roll(tfr, 3, axis=1) + rng.standard_normal((12, 200))
    return tfr, spikes


def skill_row() -> str:
    text = SKILL.read_text(encoding="utf-8")
    return next(ln for ln in text.splitlines() if "cross_modal_comparison" in ln)


def skill_prose() -> str:
    """The row with its leading signature removed.

    Every routing row opens with the call signature, so `bin_ms` appears in this row
    whatever the prose says -- it is one of the arguments. Asserting against the whole row
    therefore passes on the wording this module was written about, which is how the first
    version of the test below constrained nothing.
    """
    row = skill_row()
    return row.split("`: ", 1)[1] if "`: " in row else row


class TestTheDefaultCallIsNotTheLagSearch:
    def test_no_corrected_p_value_is_returned(self, coupled_series):
        tfr, spikes = coupled_series
        out = jnwb.cross_modal_comparison(
            tfr, spikes, n_permutations=N_PERMUTATIONS, rng=np.random.default_rng(1))
        assert "lag_corrected_pvalue" not in out, (
            "the skill told the reader to read this key from a call written exactly as "
            "routed; if it now exists, the skill line needs rewriting again"
        )

    def test_the_lag_is_reported_as_zero_rather_than_omitted(self, coupled_series):
        """The field exists so that the zero-lag case is explicit rather than silent."""
        tfr, spikes = coupled_series
        assert jnwb.cross_modal_comparison(tfr, spikes)["lag_ms"] == 0.0

    def test_the_interpretation_says_which_estimator_ran(self, coupled_series):
        tfr, spikes = coupled_series
        assert "Zero-lag" in jnwb.cross_modal_comparison(tfr, spikes)["interpretation"]

    def test_the_seed_and_permutation_count_change_nothing(self, coupled_series):
        """Accepted and unused: no permutation is run on this branch.

        Asserted rather than repaired. The arguments are part of one signature serving two
        estimators, and `interpretation` already reports which one ran.
        """
        tfr, spikes = coupled_series
        first = jnwb.cross_modal_comparison(
            tfr, spikes, n_permutations=10, rng=np.random.default_rng(1))
        second = jnwb.cross_modal_comparison(
            tfr, spikes, n_permutations=5000, rng=np.random.default_rng(999))
        assert (first["correlation"]["parametric"]["pval"]
                == second["correlation"]["parametric"]["pval"])


class TestSupplyingBinMsRunsTheLagSearch:
    def test_the_corrected_p_value_appears(self, coupled_series):
        tfr, spikes = coupled_series
        out = jnwb.cross_modal_comparison(
            tfr, spikes, bin_ms=BIN_MS, n_permutations=N_PERMUTATIONS,
            rng=np.random.default_rng(1))
        assert "lag_corrected_pvalue" in out
        assert 0.0 <= out["lag_corrected_pvalue"] <= 1.0

    def test_the_recovered_lag_has_the_sign_the_skill_describes(self, coupled_series):
        """The spikes lag the LFP by three bins, and the skill says the LFP leading is
        negative."""
        tfr, spikes = coupled_series
        out = jnwb.cross_modal_comparison(tfr, spikes, bin_ms=BIN_MS,
                                          n_permutations=N_PERMUTATIONS,
                                          rng=np.random.default_rng(1))
        assert out["lag_ms"] == pytest.approx(-30.0)

    def test_the_seed_moves_the_corrected_p_value(self, coupled_series):
        """This branch really does permute, which is what makes the other branch notable."""
        tfr, spikes = coupled_series
        values = {
            jnwb.cross_modal_comparison(
                tfr, spikes, bin_ms=BIN_MS, n_permutations=N_PERMUTATIONS,
                rng=np.random.default_rng(seed))["lag_corrected_pvalue"]
            for seed in (1, 2, 3)
        }
        assert len(values) > 1, "the corrected p is identical across seeds"

    def test_the_same_seed_reproduces(self, coupled_series):
        tfr, spikes = coupled_series
        results = [
            jnwb.cross_modal_comparison(
                tfr, spikes, bin_ms=BIN_MS, n_permutations=N_PERMUTATIONS,
                rng=np.random.default_rng(4))["lag_corrected_pvalue"]
            for _ in range(2)
        ]
        assert results[0] == results[1]

    def test_the_interpretation_says_which_estimator_ran(self, coupled_series):
        tfr, spikes = coupled_series
        out = jnwb.cross_modal_comparison(tfr, spikes, bin_ms=BIN_MS,
                                          n_permutations=N_PERMUTATIONS,
                                          rng=np.random.default_rng(1))
        assert "Best-lag" in out["interpretation"]


class TestTheSkillDescribesBothEstimators:
    def test_it_names_the_argument_that_selects_between_them(self):
        assert "bin_ms" in skill_prose(), (
            "the routing row's prose does not mention the argument that decides which "
            "estimator runs, so a reader takes the default and gets the other one"
        )

    def test_it_does_not_promise_the_corrected_p_unconditionally(self):
        """The defect was a sentence true only of the branch the default does not take.

        Position matters, not mere presence: the row has to say the default produces no
        such key before it tells the reader to read one.
        """
        row = skill_row()
        absent = "there is no `lag_corrected_pvalue` key"
        instruction = "you read `lag_corrected_pvalue`"
        assert absent in row, (
            "the row does not say that the default call returns no corrected p value")
        assert instruction in row, "the row no longer says which p value to read"
        assert row.index(absent) < row.index(instruction), (
            "the row tells the reader to read the corrected p before saying that the "
            "default call does not produce it"
        )

    def test_it_still_carries_the_sign_convention(self):
        assert "negative when the LFP leads spikes" in skill_row()
