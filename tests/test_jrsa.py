"""The `jrsa` public surface: result-field shapes, and the documented correction set.

Two defects on the public surface, both measured against the tree before repair.

P-83. `docs/quickstart.md` prints ``float(jrsa_res.p)``. That raised `TypeError: only
0-dimensional arrays can be converted to Python scalars`, because `p` and `q` came back
as shape ``(1,)`` while their siblings `value`, `statistic` and `effect` were 0-d. The
asymmetry, not the page, was the defect: `_p_from_null` wrapped its single scalar in
`np.atleast_1d`. Patching the page would have left the next reader to write the same line.
`pyproject.toml` declares ``numpy>=1.26.0`` and `float()` on a one-element array raises
under NumPy>=2, so the documented line was unrunnable on the declared floor.

P-85. The `correction` docstring listed ``cluster`` and ``maxT``. Neither exists; both
raise. Public documentation that causes wrong use.

The shape assertions here compare `p` against `value` rather than against a literal
``()``, so they hold for the multi-lag case too, where a vector-valued `p` is real. The
correction assertions derive the documented set by parsing the docstring and the accepted
set from the implementation, in both directions; neither side is written out here. A
literal list on both sides is a fixed point that agrees with itself whatever the code says
(P-151).
"""

import re

import numpy as np
import pytest

import jnwb
from jnwb.jrsa import _CORRECTION_METHOD_MAP


# ---------------------------------------------------------------------------
# P-83 -- the scalar result carries scalar fields
# ---------------------------------------------------------------------------

SCALAR_SIBLINGS = ("value", "statistic", "effect")


@pytest.fixture(scope="module")
def quickstart_inputs():
    """The exact tensors `docs/quickstart.md` builds for its jRSA block."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(6, 16, 50))
    Y = X + 0.3 * rng.normal(size=(6, 16, 50))
    return X, Y


def test_the_documented_quickstart_line_runs(quickstart_inputs):
    """The literal line from `docs/quickstart.md`, executed rather than read.

    This is the discriminator for P-83. Before the repair it raised `TypeError`.
    """
    X, Y = quickstart_inputs
    jrsa_res = jnwb.jrsa(X, Y, metric="rsa", stats=True, permutations=100, rng=0)
    line = f"jRSA alignment: {jrsa_res.value:.4f}, p-value: {float(jrsa_res.p):.4f}"
    assert line.startswith("jRSA alignment: ")
    assert 0.0 < float(jrsa_res.p) <= 1.0


@pytest.mark.parametrize("correction", ["none", "fdr_bh", "bonferroni"])
def test_p_and_q_have_the_same_shape_as_value(quickstart_inputs, correction):
    """`p` and `q` are shaped like their siblings, whatever that shape is.

    Derived, not asserted against ``()``: the same statement holds for the multi-lag
    case below, where the shape is ``(n_lags,)``.
    """
    X, Y = quickstart_inputs
    res = jnwb.jrsa(
        X, Y, metric="rsa", stats=True, permutations=100, rng=0, correction=correction
    )
    expected = np.shape(res.value)
    for sibling in SCALAR_SIBLINGS:
        assert np.shape(getattr(res, sibling)) == expected, (
            f"{sibling} is shaped {np.shape(getattr(res, sibling))}, value is {expected}"
        )
    assert np.shape(res.p) == expected, (
        f"p is shaped {np.shape(res.p)} against value {expected}"
    )
    if res.q is not None:
        assert np.shape(res.q) == expected, (
            f"q is shaped {np.shape(res.q)} against value {expected}"
        )


def test_float_of_p_does_not_raise(quickstart_inputs):
    """`float()` on a one-element array raises under NumPy>=2, the declared floor."""
    X, Y = quickstart_inputs
    res = jnwb.jrsa(X, Y, metric="rsa", stats=True, permutations=100, rng=0)
    assert isinstance(float(res.p), float)
    assert isinstance(float(res.q), float)


def test_the_parametric_path_already_agreed(quickstart_inputs):
    """With `permutations=0` the metric's own p was always 0-d.

    Pins the half of the surface that was never broken, so a repair that made everything
    shape ``(1,)`` instead would fail here rather than pass.
    """
    X, Y = quickstart_inputs
    res = jnwb.jrsa(X, Y, metric="rsa", stats=True, permutations=0, rng=0)
    assert np.shape(res.p) == np.shape(res.value) == ()


def test_multiple_lags_still_give_a_vector_p():
    """A vector-valued `p` is real where it is real, and matches `value` there.

    Before the repair this was ``(n_lags, 1)`` against a ``(n_lags,)`` `value` -- the same
    stray axis, one dimension up.
    """
    rng = np.random.default_rng(3)
    a = rng.normal(size=(40, 6))
    b = a + 0.4 * rng.normal(size=(40, 6))
    lags = [0, 1, 2]
    res = jnwb.jrsa(a, b, metric="pearson", stats=True, permutations=50, rng=0, lag=lags)
    assert np.shape(res.value) == (len(lags),)
    assert np.shape(res.p) == np.shape(res.value)
    assert np.asarray(res.p).ndim == 1


def test_a_nonfinite_input_still_reports_a_scalar_nan():
    """The early-return branch of `_p_from_null` carried the same `atleast_1d`."""
    from jnwb.jrsa import _p_from_null

    p = _p_from_null(np.float64(np.nan), np.arange(10.0), "two-sided")
    assert np.shape(p) == ()
    assert np.isnan(float(p))


# ---------------------------------------------------------------------------
# P-85 -- the documented correction set is the accepted correction set
# ---------------------------------------------------------------------------

def _documented_corrections():
    """Parse the accepted values out of `jrsa`'s own `correction` docstring.

    Independent of the implementation: this reads prose, and the tests below compare it
    against the live map and against behaviour.
    """
    doc = jnwb.jrsa.__doc__
    assert doc, "jrsa has no docstring to check"
    match = re.search(
        r"Multiple-comparison correction:\s*(.+?)\.", doc, re.DOTALL
    )
    assert match, "the `correction` docstring no longer states its accepted values"
    listed = [tok.strip() for tok in match.group(1).split("|")]
    listed = [tok for tok in (t.replace("\n", " ").strip() for t in listed) if tok]
    assert listed, "parsed an empty correction list out of the docstring"
    return listed


def test_the_docstring_parser_finds_a_plausible_list():
    """Guard the parser itself: a regex that matches nothing would vacate both tests.

    Without this, a docstring edit that broke the pattern would turn the two tests below
    into assertions over an empty set, which pass for the wrong reason.
    """
    listed = _documented_corrections()
    assert len(listed) >= 2, listed
    # Deliberately case-insensitive. A guard that rejected `maxT` on its capital letter
    # would fail on the withdrawn methods for a reason unrelated to whether they exist,
    # and would then read as a kill when it was only a spelling complaint.
    assert all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", tok) for tok in listed), listed
    assert len(set(listed)) == len(listed), f"duplicate entries: {listed}"


@pytest.mark.parametrize("method", _documented_corrections())
def test_every_documented_correction_is_actually_accepted(method):
    """Discriminator for P-85, run against behaviour rather than against the map.

    `cluster` and `maxT` were documented and raised `ValueError`. Parametrised over the
    parsed docstring, so a future addition to the prose is checked the moment it is made.
    """
    rng = np.random.default_rng(0)
    X = rng.normal(size=(6, 8, 20))
    Y = X + 0.3 * rng.normal(size=(6, 8, 20))
    res = jnwb.jrsa(
        X, Y, metric="rsa", stats=True, permutations=10, rng=0, correction=method
    )
    assert res.parameters["correction"] == method


def test_every_implemented_correction_is_documented():
    """The other direction: nothing the implementation accepts is left out of the prose.

    The half of P-85 claiming `bonferroni`, `holm` and `none` were omitted is refuted --
    all three are present at the baseline and this test says so by construction.
    """
    documented = set(_documented_corrections())
    implemented = set(_CORRECTION_METHOD_MAP)
    assert implemented <= documented, (
        f"accepted but undocumented: {sorted(implemented - documented)}"
    )


def test_the_two_sets_are_equal():
    """Both directions at once, so neither can drift while the other holds."""
    assert set(_documented_corrections()) == set(_CORRECTION_METHOD_MAP)


@pytest.mark.parametrize("method", ["cluster", "maxT"])
def test_the_withdrawn_methods_raise_rather_than_falling_back(method):
    """They were never implemented. Removing them from the prose must not add them."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(6, 8, 20))
    Y = X + 0.3 * rng.normal(size=(6, 8, 20))
    with pytest.raises(ValueError, match="Unrecognized correction method"):
        jnwb.jrsa(
            X, Y, metric="rsa", stats=True, permutations=10, rng=0, correction=method
        )
    assert method not in _documented_corrections()
