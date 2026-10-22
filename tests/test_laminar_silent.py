"""A singular partial-correlation covariance says the pseudo-inverse was used (fact S9).

The pseudo-inverse of a singular covariance returns a number that looks like a partial
correlation. The call now warns once, and names the window it was used for.
"""

import numpy as np
import pytest

from jnwb.laminar import xflip


def _singular_inverse(monkeypatch):
    def singular(*args, **kwargs):
        raise np.linalg.LinAlgError("Singular matrix")

    monkeypatch.setattr(np.linalg, "inv", singular)


def test_a_singular_covariance_warns_once_naming_the_window(monkeypatch):
    _singular_inverse(monkeypatch)
    data = np.random.default_rng(0).standard_normal((6, 200))
    with pytest.warns(UserWarning, match="pseudo-inverse") as record:
        xflip(data, method="partial", n_surrogates=0, window=(0, 5))
    messages = [str(w.message) for w in record if "pseudo-inverse" in str(w.message)]
    assert len(messages) == 1
    assert "window rows 0 to 5" in messages[0]


def test_an_ill_conditioned_covariance_warns_naming_its_condition_number():
    data = np.random.default_rng(2).standard_normal((5, 300))
    data[4] = data[0] + data[1]
    assert np.linalg.cond(np.cov(data)) > 1e12, "fixture must be rank-deficient"
    with pytest.warns(UserWarning, match="condition number"):
        xflip(data, method="partial", n_surrogates=0)


def test_a_nonsingular_partial_correlation_warns_nothing(recwarn):
    data = np.random.default_rng(1).standard_normal((4, 300))
    xflip(data, method="partial", n_surrogates=0)
    assert not [w for w in recwarn if "pseudo-inverse" in str(w.message)]
