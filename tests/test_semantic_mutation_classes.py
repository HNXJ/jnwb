"""Fourteen semantic mutation classes, exercised over the ruled composition subset.

06-27. The deliverable is a **class list, not a mutation score**: each of the fourteen classes
the item names is either demonstrated against the ten chains of
``artifacts/evidence/0.2.6/composition_subset_0.2.6.md`` or recorded here as not applicable with a reason. No
aggregate count stands in for the list, and no test in this file asserts one.

A class is demonstrated by a real mutation: the anchor is substituted in library source, the
selector that is supposed to catch it is proven to collect *and pass* on the unmutated tree
first, the named test is observed to FAIL, and the file is restored and verified by sha256. All
of that is enforced by ``scripts/mutation_harness.py`` (06-28), which is used rather than
reimplemented -- a second harness is a second set of the same eight mistakes.

What would make this file pass while the invariant it names is violated, and what is done
about each:

* **A selector that collects nothing.** ``pytest`` exits non-zero on an empty selection and that
  exit code is indistinguishable from a kill; six mutants were reported dead that way in 0.2.5.
  The harness refuses a verdict without a ``SelectorProof``, and this file asserts the proof's
  own contents per class -- the pristine exit was 0, and every ``must_fail`` node was among the
  nodes actually collected on the pristine tree. Writing that second assertion found a real
  defect while this file was being built: ``test_cluster_permutation_test_keeps_its_own_
  different_default`` was cited under the wrong class, and the case was refused rather than
  scored.
* **A mutation that changes nothing.** A replacement that leaves the file byte-identical, or an
  anchor that occurs zero or several times, makes the "mutant" the pristine tree. The harness
  refuses both, and each class here asserts ``mutant_digest != pristine_digest``.
* **A red run credited to the wrong test.** A module that stops importing is red for a reason
  that has nothing to do with the semantics. The harness requires the named node to appear as
  ``FAILED``; an ``ERROR`` is not an observation, because the test body never ran. That guard
  fired for real here too: a first attempt at "generator ignored" passed an ``int`` where a
  ``Generator`` was required, every test in the fixture's class ERRORed, and the case was
  refused instead of counted.
* **A mutant left live on disk.** Verified in bytes after every case, in the harness's
  ``finally``, and again here: after the run, every target file is re-hashed against the digest
  taken before it.
* **Mutating the tree the suite is running in.** The suite runs under ``-n auto``. A mutation
  applied to ``jnwb/spectral.py`` in the shared checkout would be visible for its whole lifetime
  to every other worker -- including the tests that read library source as text. Every case here
  runs in a private ``git clone`` of the checkout, torn down afterwards, so no other worker can
  observe a mutant. The clone is only evidence about this checkout if it carries the same bytes,
  so each target file's sha256 is compared across the two before the session starts.
* **A clone that imports somebody else's ``jnwb``.** A stale copy in ``site-packages`` would make
  every mutant invisible and every case a survivor -- or, worse, make a kill mean nothing.
  :func:`_assert_the_clone_imports_its_own_jnwb` runs a probe inside the clone and reads the
  resolved ``jnwb.__file__`` back before any case runs.
* **One class quietly dropped.** :func:`test_the_fourteen_classes_are_the_ones_the_item_declares`
  pins the names, and every class has its own static test, so a class that stops being exercised
  fails by name rather than shrinking a total.
* **A chain invented instead of cited.** Every case names a chain, and
  :func:`test_every_case_names_a_chain_the_ruled_subset_declares` resolves those names against
  the ruled subset file rather than against a list retyped here.

This module is slow -- roughly five minutes -- because each case costs four ``pytest``
subprocesses (collect and run, pristine and mutant) and there are seventeen of them. The cases
are driven from a single test for the same reason the clone exists: under ``--dist load`` a
module-scoped fixture is rebuilt in every worker that receives one of its tests, so fourteen
parametrized tests would mean up to fourteen clones and fourteen full runs. The per-class
verdicts are still asserted one at a time inside that test, and every failing class is reported
together -- a gate that aborts at the first leaves the rest unrun and looking fine.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended: prepending would put this checkout's packages ahead of an installed
# copy and silently redirect a wheel-qualification run back to the source tree.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.mutation_harness import (  # noqa: E402
    MutationCase,
    MutationHarnessError,
    MutationSession,
    Verdict,
    sha256_file,
)

HARNESS_SOURCE = REPO_ROOT / "scripts" / "mutation_harness.py"

#: The ruled subset. Chains are read out of it rather than retyped, so a chain struck from the
#: ruling cannot go on being cited here.
SUBSET_DOC = REPO_ROOT / "artifacts" / "evidence" / "0.2.6" / "composition_subset_0.2.6.md"

#: The fourteen classes, in the order 06-27 lists them. This is the deliverable.
CLASSES: tuple[str, ...] = (
    "unit scaling",
    "axis swap",
    "sign flip",
    "conjugation",
    "density against spectrum",
    "mean against median and sum",
    "log before aggregate",
    "permutation p-value substitution",
    "generator ignored",
    "support gate removed",
    "failure converted to a default",
    "identity restoration removed",
    "result key deleted",
    "signature drift",
)

#: Classes with no site in the declared subset, each with the reason. Empty: all fourteen were
#: placed. The mechanism stays because "not applicable, and here is why" is a real outcome of
#: this item and must not be spelled as a silent absence from :data:`CASES`.
NOT_APPLICABLE: dict[str, str] = {}


@dataclass(frozen=True)
class SemanticMutation:
    """One mutation class, the chain it is exercised on, and the case that demonstrates it."""

    mutation_class: str
    chain: str
    case: MutationCase


def _case(
    mutation_class: str,
    chain: str,
    name: str,
    path: str,
    original: str,
    replacement: str,
    selector: tuple[str, ...],
    must_fail: tuple[str, ...],
    semantic_property: str,
) -> SemanticMutation:
    return SemanticMutation(
        mutation_class=mutation_class,
        chain=chain,
        case=MutationCase(
            name=f"{mutation_class} | {chain} | {name}",
            path=path,
            original=original,
            replacement=replacement,
            selector=selector,
            must_fail=must_fail,
            semantic_property=semantic_property,
        ),
    )


CASES: tuple[SemanticMutation, ...] = (
    # ---------------------------------------------------------------- unit scaling
    _case(
        "unit scaling",
        "H2",
        "pitch-in-micrometres-read-as-millimetres",
        "jnwb/spectral.py",
        "    pitch_m = pitch_um * 1e-6\n",
        "    pitch_m = pitch_um * 1e-3\n",
        ("tests/test_spectral.py::TestVoltageCurvatureAndCSD",),
        (
            "tests/test_spectral.py::TestVoltageCurvatureAndCSD"
            "::test_known_quadratic_potential_curvature",
        ),
        "the second spatial derivative is per metre squared; micrometres are not millimetres",
    ),
    _case(
        "unit scaling",
        "H6",
        "amplitude-decibels-for-a-power-ratio",
        "jnwb/spectral.py",
        "        return 10.0 * np.log10(ratio)\n",
        "        return 20.0 * np.log10(ratio)\n",
        ("tests/test_composition_aggregation_order.py::TestH6AccumulatorToDecibels",),
        (
            "tests/test_composition_aggregation_order.py::TestH6AccumulatorToDecibels"
            "::test_the_accumulator_route_computes_ratio_of_means",
        ),
        "a power ratio converts at 10*log10; 20*log10 is the amplitude convention",
    ),
    # ---------------------------------------------------------------- axis swap
    _case(
        "axis swap",
        "H4",
        "correlation-taken-over-samples-not-channels",
        "jnwb/artifact_detection.py",
        # Re-anchored: `channel_correlation_matrix` gained the N1 orientation guard, so the
        # call now passes the coerced `arr` rather than the raw argument. The anchor matched
        # zero times for one commit, and **a case whose anchor matches nothing exits non-zero
        # and reads exactly like a kill** -- the failure `scripts/mutation_harness.py` exists
        # to prevent, reintroduced from outside it by an edit to the mutated file.
        #
        # The mutant transposes AFTER the guard on purpose: the guard rejects a time-major
        # *argument*, and this class asks whether anything notices the axes being swapped
        # underneath a correctly-shaped one. A mutant the guard caught would prove the guard
        # works, not that the verdict's shape is checked.
        "    return _pearson_rows(arr)\n",
        "    return _pearson_rows(arr.T)\n",
        (
            "tests/test_composition_axis.py"
            "::test_h4_the_channel_major_verdict_has_one_entry_per_channel_and_finds_bad_ones",
        ),
        (
            "tests/test_composition_axis.py"
            "::test_h4_the_channel_major_verdict_has_one_entry_per_channel_and_finds_bad_ones",
        ),
        "the QC verdict is one entry per channel; transposing makes it one per time sample",
    ),
    # ---------------------------------------------------------------- sign flip
    _case(
        "sign flip",
        "H2",
        "csd-sign-convention-dropped",
        "jnwb/spectral.py",
        "    return -conductivity_s_per_m * curvature\n",
        "    return conductivity_s_per_m * curvature\n",
        ("tests/test_spectral.py::TestVoltageCurvatureAndCSD",),
        (
            "tests/test_spectral.py::TestVoltageCurvatureAndCSD"
            "::test_known_quadratic_potential_curvature",
        ),
        "a sink is negative CSD; dropping the minus reports every sink as a source",
    ),
    # ---------------------------------------------------------------- conjugation
    _case(
        "conjugation",
        "H3",
        "psi-cross-spectrum-conjugated-on-the-other-factor",
        "jnwb/connectivity.py",
        "    return float(np.sum(np.imag(np.conj(c[:-1]) * c[1:])))\n",
        "    return float(np.sum(np.imag(c[:-1] * np.conj(c[1:]))))\n",
        (
            "tests/test_connectivity.py::TestPsiInferenceIsNotOverstated"
            "::test_the_sign_convention_is_unchanged",
        ),
        (
            "tests/test_connectivity.py::TestPsiInferenceIsNotOverstated"
            "::test_the_sign_convention_is_unchanged",
        ),
        "which factor carries the conjugate decides which signal is reported as leading",
    ),
    # ---------------------------------------------------------------- density vs spectrum
    _case(
        "density against spectrum",
        "H5",
        "welch-returns-a-spectrum-not-a-density",
        "jnwb/spectral.py",
        "        return signal.welch(trace, fs=fs, nperseg=nperseg)\n",
        '        return signal.welch(trace, fs=fs, nperseg=nperseg, scaling="spectrum")\n',
        ("tests/test_spectral.py::TestBandPowerEstimandIsDocumented",),
        (
            "tests/test_spectral.py::TestBandPowerEstimandIsDocumented"
            "::test_band_power_is_the_mean_psd_over_the_band[band0]",
            "tests/test_spectral.py::TestBandPowerEstimandIsDocumented"
            "::test_band_power_is_the_mean_psd_over_the_band[band1]",
            "tests/test_spectral.py::TestBandPowerEstimandIsDocumented"
            "::test_band_power_is_the_mean_psd_over_the_band[band2]",
        ),
        "band_power is documented in units^2/Hz; a spectrum scaling returns units^2 per bin",
    ),
    # ---------------------------------------------------------------- mean / median / sum
    _case(
        "mean against median and sum",
        "H5",
        "aggregate-to-db-takes-the-median-of-the-ratios",
        "jnwb/spectral.py",
        '    mean = np.nanmean if nan_policy == "omit" else np.mean\n',
        '    mean = np.nanmedian if nan_policy == "omit" else np.median\n',
        ("tests/test_composition_aggregation_order.py::TestH5BandPowerToAggregateToDb",),
        (
            "tests/test_composition_aggregation_order.py::TestH5BandPowerToAggregateToDb"
            "::test_the_composed_value_is_the_documented_log_last_value",
        ),
        "mean_of_ratios names the arithmetic mean of the ratios, not their median",
    ),
    _case(
        "mean against median and sum",
        "H5",
        "band-power-integrates-instead-of-averaging",
        "jnwb/spectral.py",
        "    band_power_val = float(np.mean(pxx[mask]))\n",
        "    band_power_val = float(np.sum(pxx[mask]))\n",
        ("tests/test_spectral.py::TestBandPowerEstimandIsDocumented",),
        (
            "tests/test_spectral.py::TestBandPowerEstimandIsDocumented"
            "::test_band_power_is_the_mean_psd_over_the_band[band0]",
            "tests/test_spectral.py::TestBandPowerEstimandIsDocumented"
            "::test_band_power_is_the_mean_psd_over_the_band[band1]",
            "tests/test_spectral.py::TestBandPowerEstimandIsDocumented"
            "::test_band_power_is_the_mean_psd_over_the_band[band2]",
        ),
        "the within-band statistic is a mean; a sum is an integrated power and scales with "
        "bandwidth",
    ),
    # ---------------------------------------------------------------- log before aggregate
    _case(
        "log before aggregate",
        "H5",
        "decibels-averaged-instead-of-ratios",
        "jnwb/spectral.py",
        "            aggregated = mean(p / b, axis=aggregate_over)\n",
        "            aggregated = np.power(10.0, mean(to_db(p / b), axis=aggregate_over) / 10.0)\n",
        ("tests/test_composition_aggregation_order.py::TestH5BandPowerToAggregateToDb",),
        (
            "tests/test_composition_aggregation_order.py::TestH5BandPowerToAggregateToDb"
            "::test_log_last_is_separated_from_averaging_decibels",
        ),
        "10*log10 is taken once, after aggregation: mean(log x) != log(mean x)",
    ),
    # ---------------------------------------------------------------- permutation p substituted
    _case(
        "permutation p-value substitution",
        "H9b",
        "granger-reports-the-analytic-f-test-p",
        "jnwb/connectivity.py",
        '        p_xy = float((1 + np.sum(null_xy >= fit_xy["gc"])) / (n_surrogates + 1))\n'
        '        p_yx = float((1 + np.sum(null_yx >= fit_yx["gc"])) / (n_surrogates + 1))\n',
        '        p_xy = fit_xy["p_f"]\n        p_yx = fit_yx["p_f"]\n',
        (
            "tests/test_composition_randomness.py"
            "::TestDirectedNetworkSurrogatesFollowTheCallerSeed",
        ),
        (
            "tests/test_composition_randomness.py"
            "::TestDirectedNetworkSurrogatesFollowTheCallerSeed"
            "::test_two_different_seeds_give_different_p_values[granger]",
        ),
        "with n_surrogates > 0 the reported p is the surrogate rank, not the analytic F-test p",
    ),
    # ---------------------------------------------------------------- generator ignored
    _case(
        "generator ignored",
        "H9b",
        "cluster-null-ignores-the-caller-generator",
        "jnwb/statistics.py",
        "    permutation_seeds = spawn_seeds(rng, n_permutations)\n",
        "    permutation_seeds = spawn_seeds(np.random.default_rng(0), n_permutations)\n",
        (
            "tests/test_composition_randomness.py"
            "::TestClusterPermutationNullFollowsTheCallerSeed",
        ),
        (
            "tests/test_composition_randomness.py"
            "::TestClusterPermutationNullFollowsTheCallerSeed"
            "::test_two_different_seeds_give_different_nulls",
        ),
        "the caller's generator reaches the permutation draw, so two seeds give two nulls",
    ),
    # ---------------------------------------------------------------- support gate removed
    _case(
        "support gate removed",
        "H9a",
        "nested-design-no-longer-refused",
        "jnwb/permutation.py",
        "    if not permutable:\n",
        "    if False:\n",
        (
            "tests/test_permutation.py::TestBuildPermutationPlan"
            "::test_a_nested_design_is_refused_rather_than_returning_a_vacuous_null",
        ),
        (
            "tests/test_permutation.py::TestBuildPermutationPlan"
            "::test_a_nested_design_is_refused_rather_than_returning_a_vacuous_null",
        ),
        "a design where no group holds two labels has no within-group exchangeability and is "
        "refused instead of returning a null that is a point mass",
    ),
    # ---------------------------------------------------------------- failure -> default
    _case(
        "failure converted to a default",
        "H7",
        "boundary-nan-repaired-instead-of-refused",
        "jnwb/spectral.py",
        "    if not np.all(np.isfinite(arr)):\n"
        "        raise ValueError(\n"
        '            f"{func_name}: {name} must be finite; remove or repair NaN or Inf samples '
        'first."\n'
        "        )\n",
        "    if not np.all(np.isfinite(arr)):\n"
        "        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)\n",
        ("tests/test_composition_failure_propagation.py",),
        (
            "tests/test_composition_failure_propagation.py"
            "::test_spectral_consumers_refuse_an_epoch_truncated_by_the_record_end[band_power]",
            "tests/test_composition_failure_propagation.py"
            "::test_spectral_consumers_refuse_an_epoch_truncated_by_the_record_end[compute_psd]",
            "tests/test_composition_failure_propagation.py"
            "::test_spectral_consumers_refuse_an_epoch_truncated_by_the_record_end[spectral_tilt]",
        ),
        "an epoch truncated by the end of the record is refused, not silently zero-filled",
    ),
    # ---------------------------------------------------------------- identity restoration
    _case(
        "identity restoration removed",
        "H1",
        "layer-labels-follow-row-position-not-shaft-rank",
        "jnwb/laminar.py",
        "        rank[order] = np.arange(n_geom_channels, dtype=float)\n",
        "        rank = np.arange(n_geom_channels, dtype=float)\n",
        (
            "tests/test_composition_identifier_survival.py"
            "::test_geometry_at_both_ends_recovers_the_depth_ordered_labels",
        ),
        (
            "tests/test_composition_identifier_survival.py"
            "::test_geometry_at_both_ends_recovers_the_depth_ordered_labels",
        ),
        "the inverse permutation carries a shaft-ordered result back into table-row order",
    ),
    _case(
        "identity restoration removed",
        "H8",
        "area-joined-by-row-position-not-channel-identifier",
        "jnwb/addressing.py",
        "        df['area'] = df['peak_channel_id'].apply("
        "lambda x: map_peak_channel_to_area(x, electrodes_df))\n",
        "        df['area'] = [map_peak_channel_to_area(electrodes_df.index[i], electrodes_df) "
        "for i in range(len(df))]\n",
        (
            "tests/test_composition_identifier_survival.py"
            "::test_area_and_layer_follow_the_channel_identifier_not_the_electrode_row_position",
        ),
        (
            "tests/test_composition_identifier_survival.py"
            "::test_area_and_layer_follow_the_channel_identifier_not_the_electrode_row_position",
        ),
        "a unit's area follows its peak channel identifier, not the electrode table's row order",
    ),
    # ---------------------------------------------------------------- result key deleted
    _case(
        "result key deleted",
        "H9a",
        "plan-stops-reporting-how-much-null-it-has",
        "jnwb/permutation.py",
        '        "n_permutable_groups": int(sum(\n'
        "            len(np.unique(y[group_array == g])) > 1 for g in np.unique(group_array)\n"
        "        )),\n",
        "",
        (
            "tests/test_permutation.py::TestBuildPermutationPlan"
            "::test_the_plan_reports_how_much_null_it_actually_has",
        ),
        (
            "tests/test_permutation.py::TestBuildPermutationPlan"
            "::test_the_plan_reports_how_much_null_it_actually_has",
        ),
        "the plan reports how many groups are actually permutable, not just how many rows it "
        "emitted",
    ),
    # ---------------------------------------------------------------- signature drift
    _case(
        "signature drift",
        "H9b",
        "cluster-permutation-default-seed-moves",
        "jnwb/statistics.py",
        "    rng: RNGLike = 0,\n",
        "    rng: RNGLike = 42,\n",
        ("tests/test_rng_control.py::TestNoRandomizedFunctionHidesItsSeed",),
        (
            "tests/test_rng_control.py::TestNoRandomizedFunctionHidesItsSeed"
            "::test_cluster_permutation_test_keeps_its_own_different_default",
        ),
        "the default seed is part of the declared signature every unseeded caller depends on",
    ),
)


# =========================================================================================
# static statements about the list -- no mutation, no subprocess
# =========================================================================================


def test_the_fourteen_classes_are_the_ones_the_item_declares() -> None:
    """The list is the deliverable, so it is pinned by name and by length.

    Asserting only the count would let a class be renamed into a duplicate of another and keep
    the total at fourteen.
    """
    assert len(CLASSES) == 14
    assert len(set(CLASSES)) == 14, "a class name is repeated, so one of the fourteen is missing"
    assert CLASSES == (
        "unit scaling",
        "axis swap",
        "sign flip",
        "conjugation",
        "density against spectrum",
        "mean against median and sum",
        "log before aggregate",
        "permutation p-value substitution",
        "generator ignored",
        "support gate removed",
        "failure converted to a default",
        "identity restoration removed",
        "result key deleted",
        "signature drift",
    )


@pytest.mark.parametrize("mutation_class", CLASSES, ids=lambda c: c.replace(" ", "_"))
def test_every_class_is_either_exercised_or_excused(mutation_class: str) -> None:
    """Exercised over the subset, or excused with a reason. Never absent, never both.

    "Unknown is not a pass" is the subset's own rule. A class that is simply missing from
    :data:`CASES` and from :data:`NOT_APPLICABLE` would disappear from this file without any
    test going red, which is the shape this whole item exists to prevent.
    """
    exercised = [m for m in CASES if m.mutation_class == mutation_class]
    excuse = NOT_APPLICABLE.get(mutation_class)

    assert exercised or excuse, (
        f"{mutation_class!r} is neither exercised over the declared subset nor recorded as not "
        "applicable to it. An absent class is not a passing class."
    )
    assert not (exercised and excuse), (
        f"{mutation_class!r} carries {len(exercised)} case(s) and an excuse "
        f"({excuse!r}); one of the two is stale."
    )
    if excuse:
        assert len(excuse.split()) >= 5, (
            f"{mutation_class!r} is excused by {excuse!r}, which does not say why"
        )


def test_no_class_outside_the_declared_fourteen_is_smuggled_in() -> None:
    """A case for a fifteenth class would quietly widen the item's scope."""
    unknown = sorted({m.mutation_class for m in CASES} - set(CLASSES))
    assert not unknown, f"cases name classes the item does not declare: {unknown}"
    stray = sorted(set(NOT_APPLICABLE) - set(CLASSES))
    assert not stray, f"excuses name classes the item does not declare: {stray}"


def _declared_chains() -> tuple[str, ...]:
    """Chain identifiers read out of the ruled subset, not retyped here.

    The ruling's own table is the authority. Retyping the ten names would make this file agree
    with itself after a chain was struck from the ruling.
    """
    text = SUBSET_DOC.read_text(encoding="utf-8")
    chains = tuple(dict.fromkeys(re.findall(r"^\| (H\d+[ab]?) \|", text, flags=re.MULTILINE)))
    assert len(chains) == 10, (
        f"{SUBSET_DOC} did not parse into ten chains; got {list(chains)}. The subset moved, or "
        "this parser no longer matches its table."
    )
    return chains


def test_every_case_names_a_chain_the_ruled_subset_declares() -> None:
    """06-27 cites chains from the ruled subset and adds none of its own."""
    declared = set(_declared_chains())
    invented = sorted({m.chain for m in CASES} - declared)
    assert not invented, (
        f"these cases name chains the ruling does not declare: {invented}. The subset is at "
        f"{SUBSET_DOC}; a chain not in it is a chain this item may not add."
    )


def test_every_declared_chain_carries_at_least_one_case() -> None:
    """All ten, so "over the declared subset" is the whole subset rather than the easy part."""
    covered = {m.chain for m in CASES}
    missing = sorted(set(_declared_chains()) - covered)
    assert not missing, f"no mutation class is exercised on {missing}"


def test_every_case_is_well_formed_and_distinct() -> None:
    """Each case names a file that exists, and no two cases are the same mutation twice."""
    names = [m.case.name for m in CASES]
    assert len(names) == len(set(names)), "two cases share a name, so one verdict overwrites the other"

    seen: set[tuple[str, str]] = set()
    for mutation in CASES:
        case = mutation.case
        target = REPO_ROOT / case.path
        assert target.is_file(), f"{case.name}: {case.path} does not exist"
        key = (case.path, case.original)
        assert key not in seen, f"{case.name}: this anchor is already mutated by another case"
        seen.add(key)
        assert case.original != case.replacement
        # The harness enforces this at run time; asserting it here means a bad anchor is a
        # cheap failure rather than one that costs four pytest subprocesses to discover.
        assert target.read_bytes().count(case.original.encode("utf-8")) == 1, (
            f"{case.name}: the anchor does not occur exactly once in {case.path}"
        )


def test_the_harness_is_the_repository_harness() -> None:
    """The cases run through ``scripts/mutation_harness.py``, not a local reimplementation."""
    import scripts.mutation_harness as harness

    assert Path(harness.__file__).resolve() == HARNESS_SOURCE.resolve()


# =========================================================================================
# the isolated clone
# =========================================================================================


def _rmtree(path: Path) -> None:
    """Remove a tree that contains a ``.git`` directory on Windows.

    Git marks pack files read-only, and ``shutil.rmtree`` raises on those rather than clearing
    the bit. A leftover clone would be found by the next run's ``git status`` comparison, so
    this is cleanup that has to actually work.
    """

    def _clear_readonly(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_readonly)
    else:  # pragma: no cover - the floor is 3.12, kept so a backport does not crash
        shutil.rmtree(path, onerror=lambda f, t, e: _clear_readonly(f, t, e))


def _clone_the_checkout(destination: Path) -> None:
    proc = subprocess.run(
        ["git", "clone", "--local", str(REPO_ROOT), str(destination)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, (
        f"could not clone {REPO_ROOT} into {destination}: {proc.stderr.strip()}"
    )


def _assert_the_clone_carries_this_checkouts_bytes(clone: Path) -> None:
    """A kill in the clone is evidence about this checkout only if the bytes agree.

    The clone is made from ``HEAD``. An uncommitted edit to a target file would make every
    verdict below a statement about the committed version instead, with nothing to say so.
    """
    drifted = []
    for mutation in CASES:
        rel = mutation.case.path
        here, there = sha256_file(REPO_ROOT / rel), sha256_file(clone / rel)
        if here != there:
            drifted.append(f"{rel}: checkout {here} != clone {there}")
    assert not drifted, (
        "the clone does not carry this checkout's bytes, so a mutation in it says nothing "
        "about this tree. Commit or revert the target files first:\n" + "\n".join(drifted)
    )


#: Written into the clone, run, and deleted before the session opens -- the session compares
#: ``git status`` at entry and exit, and a probe file left behind would look like drift.
_PROVENANCE_PROBE = '''import pathlib

import jnwb


def test_provenance():
    print("RESOLVED_JNWB=" + str(pathlib.Path(jnwb.__file__).resolve()))
'''


def _assert_the_clone_imports_its_own_jnwb(clone: Path) -> str:
    """Prove the mutated source is the source the selector runs against.

    Without this the whole file is theatre: a stale copy in ``site-packages`` would be imported
    instead, every mutant would be invisible, and each case would be reported as a survivor --
    or a green run here would mean nothing at all. The suite already qualifies an installed copy
    in CI, so "which jnwb" is a live question, not a hypothetical one.
    """
    probe = clone / "tests" / "test_zz_clone_provenance_probe.py"
    probe.write_text(_PROVENANCE_PROBE, encoding="utf-8", newline="\n")
    try:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [
                sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-s",
                "tests/test_zz_clone_provenance_probe.py::test_provenance",
            ],
            cwd=str(clone),
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
    finally:
        probe.unlink(missing_ok=True)

    assert proc.returncode == 0, f"the provenance probe did not run in {clone}:\n{proc.stdout}"
    resolved = [
        line.split("=", 1)[1].strip()
        for line in proc.stdout.splitlines()
        if line.startswith("RESOLVED_JNWB=")
    ]
    assert len(resolved) == 1, f"the probe printed no resolved path:\n{proc.stdout}"
    imported = Path(resolved[0]).resolve()
    assert imported.is_relative_to(clone.resolve()), (
        f"a pytest run rooted at the clone imported {imported}, which is outside {clone}. "
        "Every mutation below would have been applied to a file nothing imports."
    )
    return str(imported)


# =========================================================================================
# the demonstration
# =========================================================================================


def _describe(mutation: SemanticMutation, verdict: Verdict) -> list[str]:
    """Everything wrong with one verdict, as a list. One reason does not hide the next."""
    case = mutation.case
    problems: list[str] = []

    proof = verdict.proof
    if proof.pristine_exit != 0:
        problems.append(f"the selector did not pass pristine (exit {proof.pristine_exit})")
    if not proof.collected:
        problems.append("the selector collected nothing on the pristine tree")
    uncollected = [n for n in case.must_fail if n not in proof.collected]
    if uncollected:
        problems.append(
            f"{uncollected} were never collected on the pristine tree, so their failure under "
            "the mutant could not have been an observation of it"
        )
    if verdict.mutant_digest == verdict.pristine_digest:
        problems.append("the mutant is byte-identical to the pristine file")
    if verdict.restored_digest != verdict.pristine_digest:
        problems.append(
            f"the restore is not byte-exact: {verdict.restored_digest} != "
            f"{verdict.pristine_digest}"
        )
    if not verdict.killed:
        problems.append(
            f"SURVIVED: {list(case.must_fail)} did not fail, so nothing in the selector "
            f"notices that {case.semantic_property}"
        )
    return problems


def test_every_class_is_demonstrated_over_the_declared_subset(tmp_path_factory) -> None:
    """Each class, on its chain: selector proven pristine, mutant observed, restore in bytes.

    One test rather than fourteen because the cases share their clones and harness sessions,
    and under ``--dist load`` a module-scoped fixture is rebuilt in every worker that receives
    one of its tests. Every class is still asserted separately, and every failure is collected
    before anything is raised: a gate that stops at the first leaves the rest unrun.

    The cases are dealt round-robin over up to four clones, each with its own session, run at
    once. Serially this one test was 347 s of a 1241 s suite; each case still runs its pristine
    selector, its mutant and its restore in one clone, so no verdict depends on another group.
    """
    root = Path(tempfile.mkdtemp(prefix="jnwb-semantic-mutation-",
                                 dir=str(tmp_path_factory.mktemp("mutation"))))
    n_groups = max(1, min(4, os.cpu_count() or 1, len(CASES)))
    groups = [CASES[i::n_groups] for i in range(n_groups)]

    def run_group(index: int, cases) -> tuple[dict, dict, list]:
        clone = root / f"checkout{index}"
        _clone_the_checkout(clone)
        _assert_the_clone_carries_this_checkouts_bytes(clone)
        imported = _assert_the_clone_imports_its_own_jnwb(clone)
        print(f"\nmutation target {index}: {imported}")
        pre_run = {m.case.path: sha256_file(clone / m.case.path) for m in cases}
        verdicts: dict[str, Verdict] = {}
        rejections: dict[str, str] = {}
        with MutationSession(clone) as session:
            for mutation in cases:
                try:
                    verdicts[mutation.case.name] = session.run_case(mutation.case)
                except MutationHarnessError as exc:
                    # Recorded, not raised: one refused case must not hide the ones after it.
                    rejections[mutation.case.name] = str(exc)
        # The restore, in bytes, independently of the harness's own receipt.
        left_behind = [
            f"{rel}: {sha256_file(clone / rel)} != {digest}"
            for rel, digest in pre_run.items()
            if sha256_file(clone / rel) != digest
        ]
        return verdicts, rejections, left_behind

    try:
        with ThreadPoolExecutor(max_workers=n_groups) as pool:
            results = list(pool.map(run_group, range(n_groups), groups))
        verdicts: dict[str, Verdict] = {}
        rejections: dict[str, str] = {}
        left_behind: list[str] = []
        for group_verdicts, group_rejections, group_left in results:
            verdicts.update(group_verdicts)
            rejections.update(group_rejections)
            left_behind.extend(group_left)
        assert set(verdicts) | set(rejections) == {m.case.name for m in CASES}, (
            "a case was dealt to no group"
        )
        assert not left_behind, (
            "a mutant is still on disk after the run: " + "; ".join(left_behind)
        )

        failures: list[str] = []
        for mutation_class in CLASSES:
            cases = [m for m in CASES if m.mutation_class == mutation_class]
            if not cases:
                # Excused; test_every_class_is_either_exercised_or_excused holds the reason.
                continue
            for mutation in cases:
                name = mutation.case.name
                if name in rejections:
                    failures.append(f"[{mutation_class}] {name} never reached a verdict: "
                                    f"{rejections[name]}")
                    continue
                for problem in _describe(mutation, verdicts[name]):
                    failures.append(f"[{mutation_class}] {name}: {problem}")

        # Checked here rather than in a test of its own: under ``--dist load`` a separate test
        # could run before this one and prove nothing about the run it claims to be checking.
        _assert_the_checkout_was_never_written()

        assert not failures, (
            f"{len(failures)} of the fourteen semantic mutation classes are not demonstrated "
            "over the declared subset:\n  " + "\n  ".join(failures)
        )
    finally:
        _rmtree(root)


def _assert_the_checkout_was_never_written() -> None:
    """The cases run in a clone; this tree is read, never written.

    The invariant the rest of the suite depends on: the suite runs under ``-n auto``, and a
    mutant living for fifteen seconds in the shared checkout is visible to every other worker,
    including the tests that read library source as text.
    """
    paths = sorted({m.case.path for m in CASES})
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"git status failed in {REPO_ROOT}: {proc.stderr.strip()}"
    assert not proc.stdout.strip(), (
        "the mutation targets are modified in this checkout:\n" + proc.stdout
    )


def test_the_mutation_targets_are_clean_in_this_checkout() -> None:
    """A precondition, named as one: a dirty target makes the clone the wrong bytes.

    This says nothing about whether a run happened -- it is the state the clone is built from.
    The postcondition is asserted inside
    :func:`test_every_class_is_demonstrated_over_the_declared_subset`, where the ordering is
    guaranteed.
    """
    _assert_the_checkout_was_never_written()
