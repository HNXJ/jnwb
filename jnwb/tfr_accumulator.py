"""Poolable sufficient-statistics accumulator for complex TFR data.

Accumulates ``n``, ``mean``, ``M2`` (Chan/Golub/LeVeque parallel Welford merge -- numerically
stable, no catastrophic cancellation on TFR power's large-mean/small-variance profile) alongside
the two complex accumulators ``sum_z`` (evoked power) and ``sum_unit_z`` (ITC), decided up front
because phase cannot be recovered from power after the fact. When each trial is added with its
own baseline, ``sum_ratio`` sums the per-trial power ratios for the same reason: a mean of
ratios cannot be recovered from the trial means.

The property the whole design rests on: ``merge(A, B) == summarize(A ∪ B)`` to floating-point
tolerance. Tested in tests/test_tfr_accumulator.py.

In memory the accumulators are float64 and complex128. ``write`` halves that on the way to
disk -- ``mean``, ``M2`` and ``sum_ratio`` to float32, ``sum_z`` and ``sum_unit_z`` to complex64, ``n`` to
int32 -- so a summary that has been through HDF5 carries single-precision sufficient
statistics, and merges of reloaded groups hold to that tolerance rather than to float64's.
The downcast is deliberate: these arrays are (channels, freqs, times) and the storage is
the binding cost. Nothing here promised otherwise, but nothing said it either.
"""

from __future__ import annotations

import weakref
from typing import Dict, Optional

import numpy as np

from ._precision import (
    WELFORD_32_BIT_TOLERANCE_BREACH,
    PrecisionNotSupportedError,
)


class _TrialAveragedPower(np.ndarray):
    """Power that has already been averaged over trials.

    ``TFRAccumulator.power()`` and ``TFRAccumulator.mean`` return the mean as this view so that
    ``aggregate_to_db`` can refuse ``how="mean_of_ratios"`` on it: a ratio of trial means is
    ratio-of-means, whatever the call names. Values are unchanged. The mark survives ufuncs,
    methods, numpy functions (``np.stack``, ``np.copy``, ...) and ``tolist()``. A plain array
    that shares memory with the registered buffer (``np.asarray``, a view through a
    ``memoryview`` or ``as_strided``) is still recognised by :func:`_is_trial_averaged`. A copy numpy makes without dispatch (``np.array``, a cast in
    ``np.asarray``, assignment into another array) and a read back from :meth:`write` carry
    no mark.
    """

    def __array_function__(self, func, types, args, kwargs):
        result = super().__array_function__(func, types, args, kwargs)
        if type(result) is np.ndarray and result.dtype.kind in "fc":
            return result.view(_TrialAveragedPower)
        return result

    def tolist(self):
        listed = super().tolist()
        return _TrialAveragedList(listed) if isinstance(listed, list) else listed


class _TrialAveragedList(list):
    """``tolist()`` of trial-averaged power, marked for the same refusal."""


# Buffers that hold an accumulator's trial mean, by id. Any array sharing memory with one is
# recognised, whatever its type and however it was reached.
_TRIAL_AVERAGED_BUFFERS: "weakref.WeakValueDictionary[int, np.ndarray]" = (
    weakref.WeakValueDictionary()
)


def _register_trial_averaged(buffer: np.ndarray) -> np.ndarray:
    if buffer.base is not None:
        raise ValueError("only a buffer that owns its memory can be registered")
    _TRIAL_AVERAGED_BUFFERS[id(buffer)] = buffer
    return buffer


def _is_trial_averaged(obj) -> bool:
    """True for accumulator trial-mean power in any form that can carry a mark."""
    if isinstance(obj, (_TrialAveragedPower, _TrialAveragedList)):
        return True
    if isinstance(obj, (list, tuple)):
        return any(
            isinstance(item, (np.ndarray, _TrialAveragedList)) and _is_trial_averaged(item)
            for item in obj
        )
    if not isinstance(obj, np.ndarray):
        obj = np.asarray(obj)  # a buffer-protocol object (memoryview, ...) becomes a view
    # Memory overlap, not the `.base` chain: a view reached through a memoryview or
    # `as_strided` has a base that is not an ndarray. `may_share_memory` compares byte bounds,
    # O(ndim) per buffer, so the check is O(number of live registered buffers). Each registered
    # buffer owns one contiguous allocation, so bounds overlap means shared memory.
    return any(np.may_share_memory(obj, buffer) for buffer in list(_TRIAL_AVERAGED_BUFFERS.values()))


class TFRAccumulator:
    """Poolable sufficient statistics for complex TFR. Accumulate in float64/complex128.

    Registered ``double_only`` in :data:`jnwb._precision.PRECISION_POLICY`. A 32-bit
    request is refused rather than honoured: see :meth:`__init__`.
    """

    def __init__(self, shape: tuple, *, dtype=None):
        """Allocate the accumulators.

        Args:
            shape: ``(n_channels, n_freqs, n_times)``.
            dtype: the precision requested for accumulation. ``None`` (default) accumulates
                in float64/complex128, unchanged from before this parameter existed. A
                double request -- ``np.float64`` or ``np.complex128`` -- is accepted and is
                the same thing said explicitly. A single-precision request is **refused**.

        Raises:
            PrecisionNotSupportedError: if a 32-bit precision is requested. Welford's
                update subtracts two nearly equal numbers, and at 32 bits the surviving
                variance misses the ``rtol=1e-8`` that ``tests/test_tfr_accumulator.py``
                holds :meth:`var` to. Refusing is deliberate: returning float64 from a
                float32 request would silently substitute one precision for another, and
                offering a 32-bit path would ship a documented
                tolerance the code cannot meet.
        """
        if dtype is not None:
            requested = np.dtype(dtype)
            if requested not in (np.dtype(np.float64), np.dtype(np.complex128)):
                low, high = WELFORD_32_BIT_TOLERANCE_BREACH
                raise PrecisionNotSupportedError(
                    f"TFRAccumulator cannot accumulate in {requested.name}: it is "
                    "64-bit only. A 32-bit Welford update loses the variance to "
                    "cancellation -- measured against the 64-bit reference, the relative "
                    f"error exceeds the documented rtol=1e-8 of var() by {low}x to "
                    f"{high}x across mean-to-standard-deviation ratios of 1 to 10000, so "
                    "the breach does not depend on an unfavourable regime. Pass "
                    "dtype=np.float64, or None, and downcast after summarising; write() "
                    "already stores float32/complex64 on the way to disk."
                )
        # shape = (n_channels, n_freqs, n_times)
        self.n = np.zeros(shape, np.int64)
        self._mean = _register_trial_averaged(np.zeros(shape, np.float64))  # of |z|^2
        self.M2 = np.zeros(shape, np.float64)
        self.sum_z = np.zeros(shape, np.complex128)
        self.sum_unit_z = np.zeros(shape, np.complex128)
        # Sum of per-trial power / baseline ratios, allocated by the first add_trial that
        # passes a baseline. None means no trial carried one.
        self.sum_ratio: Optional[np.ndarray] = None

    @property
    def shape(self) -> tuple:
        return self.n.shape

    @property
    def mean(self) -> np.ndarray:
        """Trial-mean power, the same values as :meth:`power`.

        Returns a copy, NaN where no trial was valid, so ``acc.mean[...] = x`` does not write
        through; assign the whole array instead. The setter stores what it is given, so a
        reload may set ``mean`` before or after ``n``; :meth:`add_trial` and :meth:`merge` start
        a cell with no valid trial from zero, so ``acc.mean = acc.mean`` leaves it fillable.
        """
        return self.power()

    @mean.setter
    def mean(self, value) -> None:
        self._mean = _register_trial_averaged(np.array(value, dtype=np.float64))

    def add_trial(
        self,
        z: np.ndarray,
        valid: Optional[np.ndarray] = None,
        *,
        baseline: Optional[np.ndarray] = None,
    ) -> None:
        """Add ONE trial.

        Args:
            z: complex ``(n_ch, n_freq, n_time)`` coefficients of this trial.
            valid: bool mask, same shape. ``None`` marks every finite coefficient valid.
            baseline: this trial's own baseline power, ratio-scale and non-negative,
                broadcastable to the accumulator's shape -- for example ``(n_ch, n_freq, 1)``
                from the trial's baseline window, or a full ``abs(z_baseline) ** 2``. When
                given, the trial's ``abs(z) ** 2 / baseline`` is added to :attr:`sum_ratio`
                at the cells ``valid`` marks, so :meth:`mean_of_ratios` can form the
                per-trial ratio mean without holding the trials. Either every trial carries
                a baseline or none does. A zero or NaN baseline at a valid cell propagates
                ``inf`` or NaN into that cell's mean, as ``aggregate_to_db`` does with
                ``nan_policy="propagate"``.

        Raises:
            ValueError: if ``baseline`` is complex (pass power, not coefficients), negative,
                not broadcastable, or if this trial and earlier ones disagree on carrying a
                baseline.
        """
        if valid is None:
            valid = np.isfinite(z.real) & np.isfinite(z.imag)
        p = np.abs(z) ** 2
        if baseline is not None:
            b = np.asarray(baseline)
            if np.iscomplexobj(b):
                raise ValueError(
                    "baseline is complex; pass baseline power (abs(z_baseline) ** 2), not "
                    "coefficients"
                )
            b = np.broadcast_to(b.astype(np.float64, copy=False), self.shape)
            if np.any(b < 0):
                raise ValueError(
                    "baseline contains negative values, so it is not ratio-scale power; "
                    "decibels are never accumulated"
                )
            if self.sum_ratio is None:
                if np.any(self.n > 0):
                    raise ValueError(
                        "earlier trials were added without a baseline, so a per-trial ratio "
                        "mean over all trials cannot be formed; pass baseline= to every trial"
                    )
                self.sum_ratio = np.zeros(self.shape, np.float64)
            with np.errstate(divide="ignore", invalid="ignore"):
                self.sum_ratio += np.where(valid, p / b, 0.0)
        elif self.sum_ratio is not None:
            raise ValueError(
                "earlier trials carried a baseline; pass baseline= to every trial so the "
                "per-trial ratio mean covers the same trials as power()"
            )

        # Welford update, masked; an empty cell's running mean starts from zero whatever was
        # assigned to it.
        self._mean[self.n == 0] = 0.0
        n_new = self.n + valid
        delta = np.where(valid, p - self._mean, 0.0)
        inc = np.divide(delta, n_new, out=np.zeros_like(delta), where=n_new > 0)
        self._mean += inc
        self.M2 += np.where(valid, delta * (p - self._mean), 0.0)
        self.n = n_new

        mag = np.abs(z)
        self.sum_z += np.where(valid, z, 0)
        self.sum_unit_z += np.where(
            valid & (mag > 0), np.divide(z, mag, out=np.zeros_like(z), where=mag > 0), 0
        )

    def merge(self, other: "TFRAccumulator") -> "TFRAccumulator":
        """Exact pooling. merge(A, B) == summarize(A union B)."""
        n = self.n + other.n
        mine = np.where(self.n > 0, self._mean, 0.0)
        delta = np.where(other.n > 0, other._mean, 0.0) - mine
        w = np.divide(other.n, n, out=np.zeros_like(delta), where=n > 0)
        mean = mine + delta * w
        M2 = self.M2 + other.M2 + delta**2 * np.divide(
            self.n * other.n, n, out=np.zeros_like(delta), where=n > 0
        )
        out = TFRAccumulator(self.shape)
        out.n, out.M2 = n, M2
        out._mean = _register_trial_averaged(mean)
        out.sum_z = self.sum_z + other.sum_z
        out.sum_unit_z = self.sum_unit_z + other.sum_unit_z
        if self.sum_ratio is not None or other.sum_ratio is not None:
            for acc in (self, other):
                if acc.sum_ratio is None and np.any(acc.n > 0):
                    raise ValueError(
                        "refusing to merge: one accumulator carries per-trial ratios and the "
                        "other holds trials added without a baseline"
                    )
            none = np.zeros(self.shape, np.float64)
            out.sum_ratio = (
                (none if self.sum_ratio is None else self.sum_ratio)
                + (none if other.sum_ratio is None else other.sum_ratio)
            )
        return out

    # ---- derived quantities ----
    # A cell no valid trial reached has no estimate, so power, evoked power and ITC are NaN
    # there, as var() and sem() already were. Zero read as measured silence and entered
    # every downstream mean.
    def power(self) -> np.ndarray:
        """Trial-mean power; NaN where no trial was valid."""
        out = _register_trial_averaged(np.where(self.n > 0, self._mean, np.nan))
        return out.view(_TrialAveragedPower)

    def mean_of_ratios(self) -> np.ndarray:
        """Mean over trials of each trial's ``abs(z) ** 2 / baseline``; NaN where no trial was valid.

        This is the ``how="mean_of_ratios"`` estimand of ``aggregate_to_db``, formed per trial
        as the trials stream in, so its decibels are ``to_db(acc.mean_of_ratios())``: the
        logarithm is taken once, after the mean. :meth:`power` cannot give this estimand,
        because a ratio of trial means is a ratio of means.

        Raises:
            ValueError: if no trial was added with ``baseline=``.
        """
        if self.sum_ratio is None:
            raise ValueError(
                "no trial carried a baseline; pass add_trial(z, valid, baseline=...) for "
                "every trial to form the per-trial ratio mean"
            )
        return np.divide(
            self.sum_ratio, self.n, out=np.full_like(self.sum_ratio, np.nan), where=self.n > 0
        )

    def var(self) -> np.ndarray:
        return np.divide(self.M2, self.n - 1, out=np.full_like(self.M2, np.nan), where=self.n > 1)

    def sem(self) -> np.ndarray:
        return np.sqrt(
            np.divide(self.var(), self.n, out=np.full_like(self.M2, np.nan), where=self.n > 0)
        )

    def evoked(self) -> np.ndarray:
        """Power of the trial-mean ``z``; NaN where no trial was valid."""
        return (
            np.abs(np.divide(self.sum_z, self.n, out=np.full_like(self.sum_z, np.nan), where=self.n > 0))
            ** 2
        )

    def itc(self) -> np.ndarray:
        """Inter-trial phase coherence; NaN where no trial was valid."""
        return np.abs(
            np.divide(
                self.sum_unit_z, self.n, out=np.full_like(self.sum_unit_z, np.nan), where=self.n > 0
            )
        )

    def write(self, h5group, meta: Dict) -> None:
        ch = (min(4, self.n.shape[0]), self.n.shape[1], min(256, self.n.shape[2]))
        filt = dict(compression="gzip", compression_opts=1, shuffle=True)
        h5group.create_dataset("n", data=self.n.astype(np.int32), chunks=ch, **filt)
        h5group.create_dataset("mean", data=self._mean.astype(np.float32), chunks=ch, **filt)
        h5group.create_dataset("M2", data=self.M2.astype(np.float32), chunks=ch, **filt)
        h5group.create_dataset("sum_z", data=self.sum_z.astype(np.complex64), chunks=ch, **filt)
        h5group.create_dataset(
            "sum_unit_z", data=self.sum_unit_z.astype(np.complex64), chunks=ch, **filt
        )
        if self.sum_ratio is not None:
            h5group.create_dataset(
                "sum_ratio", data=self.sum_ratio.astype(np.float32), chunks=ch, **filt
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
