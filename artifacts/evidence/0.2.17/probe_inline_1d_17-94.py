"""Probe of the 1-D routing in partial_coherence and the shared 1-D helper.

Run by path with cwd at a checkout: `python <this file> <checkout>`. Prints, per public
function and bad input, the exception type and message; per valid input, a sha256 over the
returned values. Run once at the baseline and once at the head, each in its own clone, and
diff the outputs: types and hashes must match; message lines may differ only where listed.
Section B prints the helper-level differences between the inventory's REDUNDANT-WITH pairs.
"""

import hashlib
import sys
import warnings

sys.path.insert(0, sys.argv[1])

import numpy as np  # noqa: E402

import jnwb  # noqa: E402
from jnwb.spectral import imaginary_coherency, partial_coherence, wpli  # noqa: E402

assert jnwb.__file__.replace("\\", "/").startswith(sys.argv[1].replace("\\", "/")), jnwb.__file__

FS = 1000.0
gen = np.random.default_rng(7)
A = gen.standard_normal(2048)
B = 0.5 * A + gen.standard_normal(2048)
C = gen.standard_normal(2048)
BANDS = {"low": (4.0, 30.0), "high": (30.0, 90.0)}


def digest(value):
    h = hashlib.sha256()

    def feed(v):
        if isinstance(v, dict):
            for k in sorted(v):
                h.update(repr(k).encode())
                feed(v[k])
        elif isinstance(v, (tuple, list)):
            for item in v:
                feed(item)
        elif isinstance(v, np.ndarray):
            h.update(str(v.dtype).encode() + repr(v.shape).encode() + v.tobytes())
        else:
            h.update(repr(v).encode())

    feed(value)
    return h.hexdigest()


CALLS = {
    "partial_coherence": lambda x, y, z: partial_coherence(
        x, y, z, fs=FS, freq_bands=BANDS, nperseg=256, n_surrogates=20, rng=3),
    "wpli": lambda x, y, z: wpli(x, y, fs=FS, nperseg=256),
    "imaginary_coherency": lambda x, y, z: imaginary_coherency(
        x, y, fs=FS, nperseg=256, signal_class="lfp"),
}

two_d = np.stack([A, B])
nan = A.copy()
nan[5] = np.nan
BAD = {
    "x 2-D": (two_d, B, C),
    "y 2-D": (A, two_d, C),
    "z 2-D": (A, B, two_d),
    "x 0-d": (np.float64(1.0), B, C),
    "z 0-d": (A, B, np.float64(1.0)),
    "both empty": (np.array([]), np.array([]), np.array([])),
    "x empty": (np.array([]), B, C),
    "y empty": (A, np.array([]), C),
    "z empty": (A, B, np.array([])),
    "length mismatch": (A, B[:-1], C),
    "z length mismatch": (A, B, C[:-1]),
    "string x": ("abc", B, C),
    "string array x": (np.array(["a"] * 2048), B, C),
    "NaN x": (nan, B, C),
    "NaN z": (A, B, nan),
}

print("== A: public functions")
for fname, call in CALLS.items():
    for case, args in BAD.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                out = call(*args)
            print(f"{fname} | {case} | ACCEPTED | {digest(out)}")
        except Exception as exc:  # noqa: BLE001 - the type is the observable
            print(f"{fname} | {case} | {type(exc).__name__} | {exc}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        print(f"{fname} | valid | ACCEPTED | {digest(call(A, B, C))}")

print("== B: helper-level differences (unchanged helpers)")
from jnwb.jrsa._inference import _require_alternative_exact  # noqa: E402
from jnwb.jrsa._metrics import _require_same_rows  # noqa: E402
from jnwb.spectral._coupling import _require_equal_lengths  # noqa: E402
from jnwb.statistics._analysis import _require_draws  # noqa: E402
from jnwb.statistics._tests import _require_alternative_casefold, _require_shuffle_inputs  # noqa: E402


def outcome(f):
    try:
        r = f()
        return f"ok {r!r}"
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__


for alt in ("greater", "GREATER", " less ", "bogus", 1):
    print(f"alternative {alt!r}: exact={outcome(lambda: _require_alternative_exact(alt))} "
          f"casefold={outcome(lambda: _require_alternative_casefold(alt, 'p'))}")
for label, x, y in (("2-D equal", np.zeros((3, 2)), np.zeros((3, 4))),
                    ("2-D unequal", np.zeros((3, 2)), np.zeros((4, 2))),
                    ("0-d", np.float64(0.0), np.float64(0.0)),
                    ("lists", [1, 2], [1, 2])):
    print(f"rows {label}: same_rows={outcome(lambda: _require_same_rows('m', x, y))} "
          f"equal_lengths={outcome(lambda: _require_equal_lengths(x, y, 'f'))}")
one = np.zeros(3)
for count in (1, 0, True, 1.5, np.int64(2), "3"):
    print(f"count {count!r}: draws={outcome(lambda: _require_draws(count, 'f', 'n'))} "
          f"shuffle_arm={outcome(lambda: _require_shuffle_inputs(one, one, count, 'f'))}")
