"""Reported statistics must describe what actually ran.

Two defects of the same class: a field whose name is a statistical claim, holding
a number that was computed some other way. A reader quotes the field, not the
code path.

What would make these pass while the invariant is still violated: asserting a
literal (``fdr_family_size == 12``) rather than tying the field to the array it
describes. Every assertion here compares the reported field against the thing it
names, recomputed from the returned matrices.
"""

import numpy as np
import pytest

import jnwb.connectivity as C
from jnwb.connectivity import directed_network, granger, transfer_entropy

# Which jnwb is under test is asserted once, in tests/test_import_provenance.py, which honours
# JNWB_EXPECTED_PACKAGE_ROOT; asserting the checkout here failed the installed-wheel CI leg.


@pytest.fixture(scope="module")
def series():
    rng = np.random.default_rng(0)
    n_nodes, n_trials, n_times = 4, 4, 200
    x = rng.standard_normal((n_nodes, n_trials, n_times))
    for i in range(1, n_nodes):
        x[i, :, 1:] += 0.6 * x[i - 1, :, :-1]
    return {f"n{i}": x[i] for i in range(n_nodes)}


@pytest.fixture(scope="module")
def pair(series):
    return series["n0"], series["n1"]


# --- defect 1: fdr_family_size counted cells that were never corrected -------


@pytest.mark.parametrize("n_surrogates", [0, 10])
def test_fdr_family_size_equals_the_family_actually_corrected(series, n_surrogates):
    out = directed_network(
        series, method="te", fdr=True, n_surrogates=n_surrogates, seed=1
    )
    corrected = int(np.isfinite(out["q_matrix"]).sum())
    assert out["fdr_family_size"] == corrected, (
        f"reported family {out['fdr_family_size']} but {corrected} cells hold a q-value"
    )


def test_no_surrogates_means_no_correction_and_an_empty_family(series):
    """The measured row: TE without surrogates yields no p-values at all."""
    out = directed_network(series, method="te", fdr=True, n_surrogates=0, seed=1)
    assert not np.isfinite(out["q_matrix"]).any()
    assert out["fdr_family_size"] == 0


def test_family_size_is_full_off_diagonal_when_every_pair_yields_a_p(series):
    """With surrogates the family is the whole off-diagonal -- n*(n-1) is right
    here, which is why the old expression looked correct."""
    out = directed_network(series, method="te", fdr=True, n_surrogates=10, seed=1)
    n = out["n_nodes"]
    assert out["fdr_family_size"] == n * (n - 1)
    assert int(np.isfinite(out["q_matrix"]).sum()) == n * (n - 1)


def test_family_size_excludes_non_finite_p_values(series, monkeypatch):
    """A partially-NaN p_matrix must shrink the reported family.

    One pair is made to return ``p_x_to_y=None`` the way an estimate that failed
    would. Two of the 12 off-diagonal cells then hold no p-value, so 10 are
    corrected. The old expression reported 12 regardless.
    """
    real_te = C.DIRECTED_METHODS["te"]
    seen = []

    def drop_first_pair_p(x, y, **kwargs):
        res = real_te(x, y, **kwargs)
        seen.append(1)
        if len(seen) == 1:
            res.p_x_to_y = None
            res.p_y_to_x = None
        return res

    monkeypatch.setitem(C.DIRECTED_METHODS, "te", drop_first_pair_p)
    out = directed_network(series, method="te", fdr=True, n_surrogates=10, seed=1)

    n = out["n_nodes"]
    corrected = int(np.isfinite(out["q_matrix"]).sum())
    assert corrected == n * (n - 1) - 2, "fixture must hole exactly one pair"
    assert out["fdr_family_size"] == corrected
    assert out["fdr_family_size"] != n * (n - 1), "the old expression reported this"


def test_fdr_disabled_reports_an_empty_family(series):
    out = directed_network(series, method="te", fdr=False, n_surrogates=10, seed=1)
    assert out["fdr_family_size"] == 0
    assert not np.isfinite(out["q_matrix"]).any()


# --- defect 2: bias_corrected_* held the uncorrected value -------------------


def test_te_omits_bias_corrected_keys_without_surrogates(pair):
    x, y = pair
    diag = transfer_entropy(x, y, n_surrogates=0, seed=1).diagnostics
    assert "bias_corrected_x_to_y" not in diag
    assert "bias_corrected_y_to_x" not in diag
    assert "bias_corrected_x_to_y" not in diag["surrogates"]
    assert "bias_corrected_y_to_x" not in diag["surrogates"]


def test_te_matches_granger_key_shape_without_surrogates(pair):
    """Granger simply does not expose the pair without surrogates; TE now agrees."""
    x, y = pair
    te_diag = transfer_entropy(x, y, n_surrogates=0, seed=1).diagnostics
    gc_diag = granger(x, y, n_surrogates=0, seed=1).diagnostics
    key = "bias_corrected_x_to_y"
    assert (key in te_diag) == (key in gc_diag) is False
    assert (key in te_diag["surrogates"]) == (key in gc_diag["surrogates"]) is False


def test_no_reported_bias_correction_ever_equals_the_raw_estimate(pair):
    """The substitution this repair closes: a corrected name holding a raw value."""
    x, y = pair
    res = transfer_entropy(x, y, n_surrogates=0, seed=1)
    for container in (res.diagnostics, res.diagnostics["surrogates"]):
        for key, value in container.items():
            if key.startswith("bias_corrected"):
                assert value != pytest.approx(res.x_to_y), (
                    f"{key} holds the uncorrected estimate"
                )


# --- P-94 regression guard: the surrogate debias is real and must survive ----


@pytest.mark.parametrize("estimator", ["granger", "te"])
def test_surrogate_debias_is_exactly_raw_minus_null_mean(pair, estimator):
    """P-94 calls ``bias_corrected_*`` a mislabel in general. It is not: on the
    ``n_surrogates > 0`` path the value is the raw estimate minus the surrogate
    null mean. This test fails if a repair to the n_surrogates=0 path ever
    disturbs the correction that does run.
    """
    x, y = pair
    fn = granger if estimator == "granger" else transfer_entropy
    res = fn(x, y, n_surrogates=30, seed=7)
    surr = res.diagnostics["surrogates"]

    assert surr["bias_corrected_x_to_y"] == pytest.approx(
        res.x_to_y - surr["null_mean_x_to_y"], rel=0, abs=1e-12
    )
    assert surr["bias_corrected_y_to_x"] == pytest.approx(
        res.y_to_x - surr["null_mean_y_to_x"], rel=0, abs=1e-12
    )
    # And it is a real correction, not a no-op rename. The null mean may be of
    # either sign -- _te_one_direction applies its own bias_correction to the
    # surrogates too -- so the claim is that it is nonzero and moves the value,
    # not that it lowers it.
    assert surr["null_mean_x_to_y"] != 0.0
    assert surr["bias_corrected_x_to_y"] != pytest.approx(res.x_to_y, abs=1e-12)


def test_te_still_exposes_bias_corrected_at_top_level_with_surrogates(pair):
    """The key stays where callers found it whenever it is true."""
    x, y = pair
    diag = transfer_entropy(x, y, n_surrogates=20, seed=7).diagnostics
    assert diag["bias_corrected_x_to_y"] == diag["surrogates"]["bias_corrected_x_to_y"]
    assert diag["bias_corrected_y_to_x"] == diag["surrogates"]["bias_corrected_y_to_x"]
