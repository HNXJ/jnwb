"""A failed aperiodic fit records why it failed (fact S9).

The fit used to return accepted=False with every estimate None and the exception dropped, so a
non-converging fit read the same as a rejected one with no cause.
"""

import numpy as np
from scipy import optimize

from jnwb.spectral import aperiodic_fit


def _spectrum():
    freqs = np.linspace(1.0, 100.0, 200)
    return freqs, 1.0 / freqs


def test_a_failed_knee_fit_records_the_exception_class_and_text(monkeypatch):
    freqs, psd = _spectrum()

    def no_convergence(*args, **kwargs):
        raise RuntimeError("Optimal parameters not found: maxfev reached")

    monkeypatch.setattr(optimize, "curve_fit", no_convergence)
    result = aperiodic_fit(freqs, psd, (1.0, 100.0), mode="knee")
    assert result.accepted is False
    assert result.reason == "RuntimeError: Optimal parameters not found: maxfev reached"
    assert result.to_dict()["reason"] == result.reason


def test_an_accepted_fit_has_no_reason():
    freqs, psd = _spectrum()
    result = aperiodic_fit(freqs, psd, (1.0, 100.0), mode="fixed")
    assert result.accepted is True
    assert result.reason is None
