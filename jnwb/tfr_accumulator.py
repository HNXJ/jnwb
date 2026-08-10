"""Poolable sufficient-statistics accumulator for complex TFR data.

Implements C:/workspace/nwb_tfr_storage_spec.md Part 2 and 3 verbatim: accumulate ``n``,
``mean``, ``M2`` (Chan/Golub/LeVeque parallel Welford merge -- numerically stable, no
catastrophic cancellation on TFR power's large-mean/small-variance profile) alongside the two
complex accumulators ``sum_z`` (evoked power) and ``sum_unit_z`` (ITC), decided up front because
phase cannot be recovered from power after the fact.

The property the whole design rests on, per the spec's own checklist: ``merge(A, B) ==
summarize(A ∪ B)`` to floating-point tolerance. Tested in tests/test_tfr_accumulator.py.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np


class TFRAccumulator:
    """Poolable sufficient statistics for complex TFR. Accumulate in float64/complex128."""

    def __init__(self, shape: tuple):
        # shape = (n_channels, n_freqs, n_times)
        self.n = np.zeros(shape, np.int64)
        self.mean = np.zeros(shape, np.float64)  # of |z|^2
        self.M2 = np.zeros(shape, np.float64)
        self.sum_z = np.zeros(shape, np.complex128)
        self.sum_unit_z = np.zeros(shape, np.complex128)

    @property
    def shape(self) -> tuple:
        return self.n.shape

    def add_trial(self, z: np.ndarray, valid: Optional[np.ndarray] = None) -> None:
        """z: complex (n_ch, n_freq, n_time) for ONE trial. valid: bool mask, same shape."""
        if valid is None:
            valid = np.isfinite(z.real) & np.isfinite(z.imag)
        p = np.abs(z) ** 2

        # Welford update, masked
        n_new = self.n + valid
        delta = np.where(valid, p - self.mean, 0.0)
        inc = np.divide(delta, n_new, out=np.zeros_like(delta), where=n_new > 0)
        self.mean += inc
        self.M2 += np.where(valid, delta * (p - self.mean), 0.0)
        self.n = n_new

        mag = np.abs(z)
        self.sum_z += np.where(valid, z, 0)
        self.sum_unit_z += np.where(
            valid & (mag > 0), np.divide(z, mag, out=np.zeros_like(z), where=mag > 0), 0
        )

    def merge(self, other: "TFRAccumulator") -> "TFRAccumulator":
        """Exact pooling. merge(A, B) == summarize(A union B)."""
        n = self.n + other.n
        delta = other.mean - self.mean
        w = np.divide(other.n, n, out=np.zeros_like(delta), where=n > 0)
        mean = self.mean + delta * w
        M2 = self.M2 + other.M2 + delta**2 * np.divide(
            self.n * other.n, n, out=np.zeros_like(delta), where=n > 0
        )
        out = TFRAccumulator(self.shape)
        out.n, out.mean, out.M2 = n, mean, M2
        out.sum_z = self.sum_z + other.sum_z
        out.sum_unit_z = self.sum_unit_z + other.sum_unit_z
        return out

    # ---- derived quantities ----
    def power(self) -> np.ndarray:
        return self.mean

    def var(self) -> np.ndarray:
        return np.divide(self.M2, self.n - 1, out=np.full_like(self.M2, np.nan), where=self.n > 1)

    def sem(self) -> np.ndarray:
        return np.sqrt(
            np.divide(self.var(), self.n, out=np.full_like(self.M2, np.nan), where=self.n > 0)
        )

    def evoked(self) -> np.ndarray:
        return (
            np.abs(np.divide(self.sum_z, self.n, out=np.zeros_like(self.sum_z), where=self.n > 0))
            ** 2
        )

    def itc(self) -> np.ndarray:
        return np.abs(
            np.divide(self.sum_unit_z, self.n, out=np.zeros_like(self.sum_unit_z), where=self.n > 0)
        )

    def write(self, h5group, meta: Dict) -> None:
        ch = (min(4, self.n.shape[0]), self.n.shape[1], min(256, self.n.shape[2]))
        filt = dict(compression="gzip", compression_opts=1, shuffle=True)
        h5group.create_dataset("n", data=self.n.astype(np.int32), chunks=ch, **filt)
        h5group.create_dataset("mean", data=self.mean.astype(np.float32), chunks=ch, **filt)
        h5group.create_dataset("M2", data=self.M2.astype(np.float32), chunks=ch, **filt)
        h5group.create_dataset("sum_z", data=self.sum_z.astype(np.complex64), chunks=ch, **filt)
        h5group.create_dataset(
            "sum_unit_z", data=self.sum_unit_z.astype(np.complex64), chunks=ch, **filt
        )
        for k, v in meta.items():
            h5group.attrs[k] = v


#: Provenance attributes that must match before two summary groups may be merged. Refusing to
#: merge on mismatch is a hard assertion per the spec, not a convention -- see the doctrine
#: rule that a registry/summary with no provenance is unpoolable.
REQUIRED_MATCH = (
    "freqs", "times", "baseline_window", "baseline_method",
    "tfr_method", "preproc_version", "unit", "log_scaled",
)


def assert_mergeable(attrs_a: Dict, attrs_b: Dict) -> None:
    for k in REQUIRED_MATCH:
        if k not in attrs_a or k not in attrs_b:
            raise KeyError(f"missing required provenance attribute: {k}")
        if not np.array_equal(attrs_a[k], attrs_b[k]):
            raise ValueError(
                f"refusing to merge: {k} differs ({attrs_a[k]!r} vs {attrs_b[k]!r})"
            )
