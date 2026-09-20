"""06-15: the jrsa correction fallback recorded a run as corrected a way it was not.

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

SUBSTITUTED_METHODS = sorted(set(_CORRECTION_METHOD_MAP) - {"bonferroni"})


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
    """THE DISCRIMINATOR for 06-15.

    With the fallback restored, `holm` returns exactly the Benjamini-Hochberg q-values
    under the label `holm`, and this fails. With the repair it raises instead, and returns
    no values to compare.
    """
    q_bh_fallback = StatisticalAnalysis.fdr_correct(P_SEEDED, method="bh")

    with statsmodels_unimportable():
        try:
            q_holm = _multiple_correction(P_SEEDED, "holm", ALPHA)
        except ImportError:
            return  # refused to compute: it cannot have mislabelled anything

    assert not np.any(q_holm == np.asarray(q_bh_fallback)), (
        "correction='holm' returned Benjamini-Hochberg values under the label 'holm': "
        f"holm={q_holm.tolist()} bh={np.asarray(q_bh_fallback).tolist()}"
    )


@pytest.mark.parametrize("method", SUBSTITUTED_METHODS)
def test_an_unavailable_estimator_raises_instead_of_substituting(method):
    with statsmodels_unimportable():
        with pytest.raises(ImportError, match="statsmodels"):
            _multiple_correction(P_SEEDED, method, ALPHA)


def test_bonferroni_still_computes_without_statsmodels():
    """Bonferroni is not a substitution: p*m clipped at 1 is Bonferroni, so the label
    stays true and the fallback is kept."""
    with statsmodels_unimportable():
        q = _multiple_correction(P_SEEDED, "bonferroni", ALPHA)
    np.testing.assert_array_equal(q, np.asarray(Q_STATSMODELS_PRESENT["bonferroni"]))


def test_the_raise_is_catchable_and_carries_its_cause():
    with statsmodels_unimportable():
        with pytest.raises(ImportError) as info:
            _multiple_correction(P_SEEDED, "holm", ALPHA)
    assert isinstance(info.value.__cause__, ImportError)


@pytest.mark.parametrize("method", sorted(Q_STATSMODELS_PRESENT))
def test_statsmodels_present_values_are_unchanged(method):
    """The repair touches only the branch where statsmodels is missing."""
    q = _multiple_correction(P_SEEDED, method, ALPHA)
    np.testing.assert_array_equal(q, np.asarray(Q_STATSMODELS_PRESENT[method]))
    assert q.dtype == np.float64
    assert q.shape == P_SEEDED.shape


def test_shape_and_dtype_survive_a_two_dimensional_input():
    q = _multiple_correction(P_SEEDED.reshape(2, 4), "holm", ALPHA)
    assert q.shape == (2, 4)
    assert q.dtype == np.float64
    np.testing.assert_array_equal(
        q.ravel(), np.asarray(Q_STATSMODELS_PRESENT["holm"])
    )
