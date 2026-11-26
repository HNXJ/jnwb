"""Does _require_finite_nonempty_pair(x, y, f) equal trace(x) + trace(y) on the inputs its callers can pass?"""
import sys
import warnings

import numpy as np

import jnwb
from jnwb.spectral._common import _require_finite_nonempty_trace as trace
from jnwb.spectral._coupling import _require_finite_nonempty_pair as pair
from jnwb.spectral import cross_area_coherence, partial_coherence

print("jnwb from", jnwb.__file__)


def outcome(fn):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            fn()
            r = "ok"
        except Exception as e:  # noqa: BLE001
            r = f"{type(e).__name__}: {str(e)[:90]}"
    return r + (f"  [warn {w[0].category.__name__}]" if w else "")


def via_trace(x, y):
    trace(x, "f", "x")
    trace(y, "f", "y")


good = np.arange(64.0)
cases = {
    "x NaN": (np.r_[np.nan, good[1:]], good),
    "both empty": (np.array([]), np.array([])),
    "x ok, y empty": (good, np.array([])),
    "strings": (np.array(["a", "b"]), np.array(["c", "d"])),
    "complex": (good + 1j, good + 0j),
    "0-d": (np.float64(1.0), np.float64(2.0)),
}
for name, (x, y) in cases.items():
    print(f"{name:14s} pair : {outcome(lambda: pair(x, y, 'f'))}")
    print(f"{name:14s} trace: {outcome(lambda: via_trace(x, y))}")

rng = np.random.default_rng(0)
a = rng.standard_normal(512)
print("cross_area_coherence(str):", outcome(lambda: cross_area_coherence(
    np.array(["a"] * 64), np.array(["b"] * 64), fs=1000.0, freq_bands="canonical", n_surrogates=1)))
print("cross_area_coherence(a, []):", outcome(lambda: cross_area_coherence(
    a, np.array([]), fs=1000.0, freq_bands="canonical", n_surrogates=1)))
print("partial_coherence(str):", outcome(lambda: partial_coherence(
    np.array(["a"] * 64), np.array(["b"] * 64), np.array(["c"] * 64), fs=1000.0,
    freq_bands="canonical", n_surrogates=1)))
sys.exit(0)
