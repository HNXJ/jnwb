"""The jrsa correction fallback recorded a run as corrected a way it was not.

`_multiple_correction` routed every method but `bonferroni` to Benjamini-Hochberg when
`statsmodels` could not be imported, while `parameters['correction']` kept echoing the
method the caller asked for. A `holm`-corrected result was labelled `holm` and was in fact
`fdr_bh`, and nothing was raised or warned.

`statsmodels` is a declared hard dependency of jnwb, so the branch is reachable only where
a declared dependency is absent. These tests reach it by simulating the import failure --
never by changing the installed environment.

The discriminator is `test_holm_never_returns_the_benjamini_hochberg_values`. Restoring the
fallback makes it fail; the repair makes it pass. `test_holm_and_fdr_bh_genuinely_differ`
exists so the discriminator cannot pass for the wrong reason: if the seeded p-vector were
one on which the two methods happen to agree, the discriminator would be vacuous.

06-76 adds the second half. `'none'` was not a key of `_CORRECTION_METHOD_MAP`, so the same
substitution ran on the label `'none'` -- Benjamini-Hochberg with statsmodels present, and
an `ImportError` demanding statsmodels without it. The case set here was derived from that
map, so it could not reach a value the map was missing. `ACCEPTED_CORRECTIONS` is now a
literal and the map is checked against it.

P-181 corrects how the frozen vectors are compared. They were asserted with
`assert_array_equal`, which on a value computed through `pow` is a bit-exactness assertion
across platforms; the ubuntu legs of CI failed it by one and two ulp. The comparison is now
chosen per method -- tolerant only where a libm transcendental is in the path, exact
everywhere else -- and `test_the_ubuntu_measured_holm_sidak_vector_is_accepted` is the
discriminator, which reproduces the Linux failure on any platform.
"""

from __future__ import annotations

import contextlib
import sys

import numpy as np
import pytest

from jnwb.jrsa import _CORRECTION_METHOD_MAP, _multiple_correction
from jnwb.statistics import StatisticalAnalysis

ALPHA = 0.05

# Seeded, and pinned as a literal so the vector cannot drift with a NumPy RNG change.
# Produced by ``np.sort(np.random.default_rng(20615).uniform(0.001, 0.30, size=8))``.
P_SEEDED = np.array([
    0.06481467068559237,
    0.08142696682553835,
    0.10289033343814798,
    0.12915810801036298,
    0.15482611444191915,
    0.17419132734967072,
    0.25413064195097040,
    0.27595295241047440,
])

# Frozen with statsmodels present, before the repair. These are the values the repair must
# not move.
Q_STATSMODELS_PRESENT = {
    "fdr_bh": [
        0.2322551031328943, 0.2322551031328943, 0.2322551031328943,
        0.2322551031328943, 0.2322551031328943, 0.2322551031328943,
        0.2759529524104744, 0.2759529524104744,
    ],
    "fdr_by": [
        0.6312361910147591, 0.6312361910147591, 0.6312361910147591,
        0.6312361910147591, 0.6312361910147591, 0.6312361910147591,
        0.7500007028013250, 0.7500007028013250,
    ],
    "bonferroni": [
        0.5185173654847389, 0.6514157346043068, 0.8231226675051838,
        1.0, 1.0, 1.0, 1.0, 1.0,
    ],
    "holm": [
        0.5185173654847389, 0.5699887677787685, 0.6173420006288879,
        0.6457905400518149, 0.6457905400518149, 0.6457905400518149,
        0.6457905400518149, 0.6457905400518149,
    ],
    "holm-sidak": [
        0.41496549425878726, 0.4481820278730368, 0.4787174129915805,
        0.4991628178860116, 0.4991628178860116, 0.4991628178860116,
        0.4991628178860116, 0.4991628178860116,
    ],
}

# P-181. The frozen vectors above were recorded on Windows, so they encode this machine's
# libm. `holm-sidak` computes ``1 - (1 - p)**n``, and `pow` is a libm function that glibc
# and MSVC round differently in the last place: GitHub Actions run 35632380292 failed this
# file on all three ubuntu legs and no windows leg, at 2 of 8 elements, by 1 and 2 ulp.
#
# `np.testing.assert_array_equal` on a value computed through `pow` asserts bit-exactness
# across platforms. That is not a property this repository can hold and not the property
# the test is named for: the invariant is that the fallback agrees with statsmodels, and
# agreement to floating-point precision is what that means.
#
# Only the methods that route through a transcendental are relaxed. The others are
# multiply-and-compare in IEEE-754 double, which every conforming platform rounds
# identically, and weakening a correctly-exact assertion would be a blind spot, not a fix:
#
#   bonferroni  `p * 8.0` clipped at 1. 8 is a power of two, so the multiply only shifts
#               the exponent -- exact for every input, no rounding at all.
#   holm        `p_sorted * arange(m, 0, -1)`, running maximum, clip. Multiplies by small
#               integers; each is a single correctly-rounded IEEE operation.
#   fdr_bh      `p_sorted * m / arange(1, m+1)`, running minimum. Multiply and divide only.
#   fdr_by      fdr_bh scaled by `sum(1/arange(1, m+1))`. Reciprocals and an 8-element sum.
#               Deterministic per IEEE; the three ubuntu legs agreed with the frozen bytes.
#   none        returns a copy of the input. No arithmetic.
#
TRANSCENDENTAL_METHODS = frozenset({"holm-sidak"})

# Budget, in ulps of the result, for one pow evaluated by two different libms:
#   - each implementation is within 1 ulp of the correctly-rounded `pow`, so the two can
#     disagree by 2 ulp in `(1 - p)**n`;
#   - `1 - x` amplifies that relative error by `x / (1 - x)`, which over this p-vector
#     peaks at 2.63 (measured, at p=0.2760, n=1), giving 5.3 ulp;
#   - the subtraction and the running maximum add at most 1 ulp more.
# That is 6.3 ulp. `4 * eps` is 6.6 ulp at 0.415 and 8.0 ulp at 0.499 -- the smallest round
# multiple of eps above the budget. `3 * eps` (5.0-6.0 ulp) would sit under it.
#
# The measured cross-platform divergence is 2.48e-16, so this bound is 3.6x it. What it
# still catches: the nearest genuinely-wrong result that can be constructed here -- one
# element with the step-down exponent off by one -- differs by 9.77e-2 relative, 1.1e14
# times this tolerance. Substituting any other correction method differs by 0.29 to 1.00.
LIBM_RTOL = 4 * np.finfo(np.float64).eps


def assert_agrees_with_statsmodels(actual, expected, method):
    """Compare against a frozen statsmodels vector at the precision the method warrants.

    Exact for everything computed by multiplication; tolerant only where a libm
    transcendental is in the path. `atol=0` deliberately: these q-values are all of order
    0.2 to 1.0, so a relative bound is the whole bound, and a non-zero `atol` would admit
    an absolute error near zero that `rtol` was chosen to forbid.
    """
    expected = np.asarray(expected)
    if method in TRANSCENDENTAL_METHODS:
        np.testing.assert_allclose(actual, expected, rtol=LIBM_RTOL, atol=0.0)
    else:
        np.testing.assert_array_equal(actual, expected)

# Every accepted value of `correction`, written out. This used to be spelled
# `set(_CORRECTION_METHOD_MAP) - {"bonferroni"}`, which derives the case set from the same
# structure that held the defect: a set generated by the map cannot reach a value the map is
# missing, and `'none'` was missing (P-50). The map is now checked against this literal
# rather than generating it.
#
# `jrsa`'s `correction` docstring also lists `cluster` and `maxT`. Neither is implemented --
# both raise `ValueError` -- so neither is an accepted value. That mismatch is a separate
# finding and is deliberately not decided here.
ACCEPTED_CORRECTIONS = (
    "bonferroni",
    "fdr_bh",
    "fdr_by",
    "holm",
    "holm-sidak",
    "none",
)

# The methods that cannot be computed at all without statsmodels. `bonferroni` is excluded
# because jnwb computes it itself; `none` because it computes nothing.
SUBSTITUTED_METHODS = sorted(set(ACCEPTED_CORRECTIONS) - {"bonferroni", "none"})


@contextlib.contextmanager
def statsmodels_unimportable():
    """Make ``import statsmodels...`` raise, without touching the environment.

    A cached submodule would satisfy ``from statsmodels.stats.multitest import ...`` from
    ``sys.modules`` and the branch under test would never run, so every cached
    ``statsmodels`` entry is masked, not just the top-level package.
    """
    saved = {
        name: mod for name, mod in sys.modules.items()
        if name == "statsmodels" or name.startswith("statsmodels.")
    }
    for name in saved:
        sys.modules[name] = None  # type: ignore[assignment]
    sys.modules["statsmodels"] = None  # type: ignore[assignment]
    try:
        yield
    finally:
        for name in [n for n in sys.modules
                     if n == "statsmodels" or n.startswith("statsmodels.")]:
            del sys.modules[name]
        sys.modules.update(saved)


def test_the_simulation_actually_blocks_the_import():
    """A simulation that silently fails to block would make every test below vacuous."""
    with statsmodels_unimportable():
        with pytest.raises(ImportError):
            from statsmodels.stats.multitest import multipletests  # noqa: F401
    from statsmodels.stats.multitest import multipletests  # noqa: F401  # restored


def test_holm_and_fdr_bh_genuinely_differ():
    """The discriminator's premise: on this vector the two methods disagree everywhere.

    Without this, a discriminator asserting they are unequal could pass on a repair that
    does nothing.
    """
    q_holm = _multiple_correction(P_SEEDED, "holm", ALPHA)
    q_bh = _multiple_correction(P_SEEDED, "fdr_bh", ALPHA)
    assert not np.any(q_holm == q_bh), (
        "seeded p-vector is unsuitable: holm and fdr_bh agree on at least one element, "
        "so the discriminator would pass without discriminating"
    )


def test_holm_never_returns_the_benjamini_hochberg_values():
    """THE DISCRIMINATOR for 06-15, asserting on both outcomes.

    With the fallback restored, `holm` returns exactly the Benjamini-Hochberg q-values
    under the label `holm`, and this fails. With the repair it raises instead.

    The refusal branch used to `return` before reaching any assertion, so on the repaired
    code the test enforced nothing while its name claimed enforcement (P-51). A refusal is
    an outcome to check: one that does not name the method it refused could be mistaken for
    another method's, which is the same mislabelling this test exists to forbid.
    """
    q_bh_fallback = np.asarray(StatisticalAnalysis.fdr_correct(P_SEEDED, method="bh"))

    with statsmodels_unimportable():
        try:
            q_holm = _multiple_correction(P_SEEDED, "holm", ALPHA)
        except ImportError as exc:
            assert "'holm'" in str(exc), (
                f"refusal does not name the method it refused: {exc}"
            )
            return

    assert not np.any(q_holm == q_bh_fallback), (
        "correction='holm' returned Benjamini-Hochberg values under the label 'holm': "
        f"holm={q_holm.tolist()} bh={q_bh_fallback.tolist()}"
    )


@pytest.mark.parametrize("method", SUBSTITUTED_METHODS)
def test_an_unavailable_estimator_raises_instead_of_substituting(method):
    with statsmodels_unimportable():
        with pytest.raises(ImportError, match="statsmodels"):
            _multiple_correction(P_SEEDED, method, ALPHA)


def test_the_map_offers_exactly_the_accepted_corrections():
    """The enumeration is the contract; the map must match it in both directions.

    Asserted against a literal. Against `_CORRECTION_METHOD_MAP` itself this would be a
    tautology -- it would agree with the map whatever the map said, including when an
    accepted value is missing from it, which is exactly how `'none'` went uncovered.
    """
    assert sorted(_CORRECTION_METHOD_MAP) == sorted(ACCEPTED_CORRECTIONS), (
        f"the map offers {sorted(_CORRECTION_METHOD_MAP)}, "
        f"the contract is {sorted(ACCEPTED_CORRECTIONS)}"
    )


@pytest.mark.parametrize("method", ACCEPTED_CORRECTIONS)
def test_every_accepted_correction_computes(method):
    """The case set the old derived spelling could not produce: it had no `'none'` case."""
    q = _multiple_correction(P_SEEDED, method, ALPHA)
    assert q.shape == P_SEEDED.shape
    assert q.dtype == np.float64
    assert np.all(np.isfinite(q))


def test_none_returns_the_p_values_uncorrected():
    """`'none'` means no correction. It used to mean Benjamini-Hochberg: `'none'` was not a
    key of the map, and `.get('none', 'fdr_bh')` returned BH q-values under the label."""
    q = _multiple_correction(P_SEEDED, "none", ALPHA)
    np.testing.assert_array_equal(q, P_SEEDED)
    assert q.dtype == np.float64
    assert q.shape == P_SEEDED.shape


def test_none_is_not_the_benjamini_hochberg_values():
    """Names the substitution directly. Element-wise inequality would be the wrong
    assertion here: Benjamini-Hochberg leaves the largest p-value unchanged."""
    q_none = _multiple_correction(P_SEEDED, "none", ALPHA)
    q_bh = _multiple_correction(P_SEEDED, "fdr_bh", ALPHA)
    assert not np.array_equal(q_none, q_bh), (
        f"correction='none' returned the Benjamini-Hochberg q-values: {q_none.tolist()}"
    )


def test_none_does_not_require_statsmodels():
    """Asking for no correction must not require the library that does correction. It used
    to raise `ImportError` here, demanding statsmodels in order to do nothing."""
    with statsmodels_unimportable():
        q = _multiple_correction(P_SEEDED, "none", ALPHA)
    np.testing.assert_array_equal(q, P_SEEDED)


def test_none_returns_a_copy_rather_than_the_callers_array():
    q = _multiple_correction(P_SEEDED, "none", ALPHA)
    q[0] = -1.0
    assert P_SEEDED[0] != -1.0, "correction='none' handed back the caller's own array"


def test_none_preserves_shape_on_a_two_dimensional_input():
    q = _multiple_correction(P_SEEDED.reshape(2, 4), "none", ALPHA)
    assert q.shape == (2, 4)
    np.testing.assert_array_equal(q.ravel(), P_SEEDED)


def test_bonferroni_still_computes_without_statsmodels():
    """Bonferroni is not a substitution: p*m clipped at 1 is Bonferroni, so the label
    stays true and the fallback is kept."""
    with statsmodels_unimportable():
        q = _multiple_correction(P_SEEDED, "bonferroni", ALPHA)
    np.testing.assert_array_equal(q, np.asarray(Q_STATSMODELS_PRESENT["bonferroni"]))


def test_the_bonferroni_multiplier_is_a_float_not_the_array_dtype():
    """`p_flat * len(p_flat)` kept the p-array's integer dtype, so the multiplier had to fit
    in it. Measured on NumPy 2.4.6: int8 with 200 tests raises `OverflowError: Python
    integer 200 out of bounds for int8`. The float multiplier is correct for every dtype and
    is bit-identical to the int multiplier on float input."""
    p_int = np.zeros(200, dtype=np.int8)
    p_int[0] = 1
    with statsmodels_unimportable():
        q = _multiple_correction(p_int, "bonferroni", ALPHA)
    expected = np.zeros(200, dtype=np.float64)
    expected[0] = 1.0
    np.testing.assert_array_equal(q, expected)
    assert q.dtype == np.float64


def test_the_raise_is_catchable_and_carries_its_cause():
    with statsmodels_unimportable():
        with pytest.raises(ImportError) as info:
            _multiple_correction(P_SEEDED, "holm", ALPHA)
    assert isinstance(info.value.__cause__, ImportError)


@pytest.mark.parametrize("method", sorted(Q_STATSMODELS_PRESENT))
def test_statsmodels_present_values_are_unchanged(method):
    """The repair touches only the branch where statsmodels is missing."""
    q = _multiple_correction(P_SEEDED, method, ALPHA)
    assert_agrees_with_statsmodels(q, Q_STATSMODELS_PRESENT[method], method)
    assert q.dtype == np.float64
    assert q.shape == P_SEEDED.shape


def test_shape_and_dtype_survive_a_two_dimensional_input():
    q = _multiple_correction(P_SEEDED.reshape(2, 4), "holm", ALPHA)
    assert q.shape == (2, 4)
    assert q.dtype == np.float64
    # `holm` is multiply-and-compare, so this stays bit-exact. Routed through the helper
    # so that the exactness is a stated classification rather than an accident of which
    # assertion was typed here.
    assert_agrees_with_statsmodels(
        q.ravel(), Q_STATSMODELS_PRESENT["holm"], "holm"
    )


# The values GitHub Actions measured on ubuntu-latest at 30c425cf, run 35632380292. Six of
# eight elements matched the frozen vector; the two that did not are quoted in the failure
# report and are written out here. This is the CI failure, reproducible on Windows.
Q_HOLM_SIDAK_AS_UBUNTU_MEASURED = (
    [0.4149654942587872, 0.4481820278730369]
    + Q_STATSMODELS_PRESENT["holm-sidak"][2:]
)


def test_the_ubuntu_measured_holm_sidak_vector_is_accepted():
    """THE DISCRIMINATOR for P-181, and it runs on Windows.

    This machine is one of the two configurations where the bug does not reproduce, so the
    failure cannot be provoked by running the fallback. It is provoked instead by feeding
    the numbers the ubuntu legs actually produced through the comparison the file uses: the
    bit-exact form rejects them with exactly the CI error, the tolerant form accepts them.
    Restore `assert_array_equal` here and this fails.
    """
    frozen = np.asarray(Q_STATSMODELS_PRESENT["holm-sidak"])
    ubuntu = np.asarray(Q_HOLM_SIDAK_AS_UBUNTU_MEASURED)
    assert not np.array_equal(ubuntu, frozen), (
        "the ubuntu vector is bit-identical to the frozen one, so this test would pass "
        "without discriminating"
    )
    assert_agrees_with_statsmodels(ubuntu, frozen, "holm-sidak")


def test_the_tolerance_admits_a_few_ulps_and_nothing_larger():
    """The tolerance's two-sided property, stated as a test rather than as a comment.

    A tolerance that cannot fail is worse than the bit-exact assertion it replaces, so the
    upper half matters as much as the lower: nudging the frozen vector by `np.nextafter`
    must pass, and every genuinely different correction must still be killed.
    """
    frozen = np.asarray(Q_STATSMODELS_PRESENT["holm-sidak"])

    nudged = np.nextafter(frozen, np.inf)
    nudged[1] = np.nextafter(nudged[1], np.inf)  # 2 ulp, as ubuntu measured at [1]
    with pytest.raises(AssertionError):
        np.testing.assert_array_equal(nudged, frozen)  # the assertion being replaced
    assert_agrees_with_statsmodels(nudged, frozen, "holm-sidak")

    # A wrong fallback is not a rounding difference. Every other correction method, and the
    # nearest constructible arithmetic error, must still fail.
    for other in ("holm", "fdr_bh", "fdr_by", "bonferroni"):
        with pytest.raises(AssertionError):
            assert_agrees_with_statsmodels(
                np.asarray(Q_STATSMODELS_PRESENT[other]), frozen, "holm-sidak"
            )

    exponent_off_by_one = frozen.copy()
    exponent_off_by_one[0] = 1.0 - (1.0 - P_SEEDED[0]) ** (P_SEEDED.size - 1)
    with pytest.raises(AssertionError):
        assert_agrees_with_statsmodels(exponent_off_by_one, frozen, "holm-sidak")


def test_only_the_transcendental_methods_are_relaxed():
    """The classification is the point: relaxing a correctly-exact comparison would hide a
    real regression. `bonferroni` multiplies by 8, a power of two, so it does not round at
    all; `holm`, `fdr_bh` and `fdr_by` are multiplies and divides; `none` copies."""
    assert TRANSCENDENTAL_METHODS == {"holm-sidak"}
    assert TRANSCENDENTAL_METHODS <= set(ACCEPTED_CORRECTIONS)

    for method in set(Q_STATSMODELS_PRESENT) - TRANSCENDENTAL_METHODS:
        frozen = np.asarray(Q_STATSMODELS_PRESENT[method])
        with pytest.raises(AssertionError):
            assert_agrees_with_statsmodels(np.nextafter(frozen, np.inf), frozen, method)

    # And the exactness claimed for bonferroni is arithmetic, not a measurement: p*8 shifts
    # the exponent and cannot round.
    np.testing.assert_array_equal(
        np.minimum(P_SEEDED * 8.0, 1.0),
        np.asarray(Q_STATSMODELS_PRESENT["bonferroni"]),
    )
