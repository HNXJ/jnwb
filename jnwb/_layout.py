"""Physical bounds that distinguish a channel-major array from a transposed one.

Three consumers accepted a time-major array and returned finite nonsense rather than raising:

* ``current_source_density_1d`` defaults ``axis=0`` while ``bandpass_filter`` defaults
  ``axis=-1``, so the obvious two-call chain produced a "CSD" that is a second derivative
  along *time* divided by a pitch in micrometres. Measured on 64x6000: RMS ratio 0.108993, a
  9.17x discrepancy, shapes 62x6000 against 5998x64. The ratio is fixture-dependent and the
  spectrum is load-bearing -- on temporally white noise it is 1.86 and the defect looks mild,
  while on the physically correct 1/f shape it is 0.109.
* ``channel_correlation_matrix`` on a ``(6000, 64)`` array returns a (6000, 6000) matrix, and
  ``bad_channels_from_correlation`` then returns a 6000-entry verdict flagging 0 "channels".
  A safety check that cannot fail is worse than none, because it is read as evidence the data
  is clean.

There is no invariant *inside* such a call that separates ``(64, 6000)`` from ``(6000, 64)``
by shape alone -- both are well-formed 2-D arrays. What does separate them is physics: a
laminar probe has a bounded number of contacts and a bounded shank length. Both bounds below
are properties of the hardware, not tuned thresholds, and neither can refuse a real laminar
recording: the most contact-dense device in wide use puts 384 simultaneously recorded sites on
a shank 10 mm long. The bounds are set an order of magnitude beyond that, so they fire only on
an array whose channel axis holds samples.

A bound is deliberately *not* a guess at the caller's intent. These helpers refuse and name the
suspected transposition; they never transpose the array themselves, because silently correcting
an orientation would replace a loud wrong answer with a quiet right-looking one and destroy the
caller's ability to notice that their pipeline disagrees with itself.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

#: Largest contact count this package will accept on a single laminar axis. Neuropixels 1.0
#: reads 384 sites at once; 2.0 exposes 5120 sites but still records 384 per shank. 1024 leaves
#: room for a denser future device while staying far below any plausible sample count.
MAX_LAMINAR_CHANNELS = 1024

#: Longest laminar shank this package will accept, in micrometres. A Neuropixels shank is
#: 10 mm; 100 mm is longer than any mammalian brain, so a span above it is not a probe.
MAX_PROBE_SPAN_UM = 100_000.0


def require_channel_major(
    arr: np.ndarray,
    axis: int,
    func_name: str,
    *,
    pitch_um: Optional[float] = None,
    argument: str = "lfp_matrix",
) -> None:
    """Refuse an array whose ``axis`` cannot be a probe's channel axis.

    Checks two independent physical bounds, so a transposition is caught whatever the pitch:
    the contact count, and -- when ``pitch_um`` is known -- the implied shank span. Raises
    ``ValueError`` naming the shape, the bound it broke, and the argument that fixes it.
    """
    n_ch = int(arr.shape[axis])
    if n_ch > MAX_LAMINAR_CHANNELS:
        other = [d for i, d in enumerate(arr.shape) if i != axis % arr.ndim]
        hint = (
            f" The array is {arr.shape} and axis={axis} selects {n_ch}; "
            f"{other} along the other axis would be a plausible contact count, so this looks "
            f"like a time-major array. Pass the channel axis explicitly (axis=...) or "
            f"transpose {argument} before calling."
            if other and min(other) <= MAX_LAMINAR_CHANNELS
            else ""
        )
        raise ValueError(
            f"{func_name}: {argument} has {n_ch} entries along axis={axis}, above the "
            f"{MAX_LAMINAR_CHANNELS}-contact limit for a laminar axis.{hint}"
        )
    if pitch_um is not None and n_ch > 1:
        span = float(pitch_um) * (n_ch - 1)
        if span > MAX_PROBE_SPAN_UM:
            raise ValueError(
                f"{func_name}: {n_ch} contacts at {pitch_um} um pitch implies a shank "
                f"{span / 1000.0:.1f} mm long, above the "
                f"{MAX_PROBE_SPAN_UM / 1000.0:.0f} mm limit for a laminar probe. Either "
                f"{argument} is time-major along axis={axis}, or pitch_um is in the wrong unit."
            )


#: Design rows a single trial must contribute before a lagged estimate is worth forming. One
#: row is enough to be *defined* and nowhere near enough to be *estimated*: with a handful of
#: samples per trial the within-trial structure the estimator models is not present at all.
MIN_DESIGN_ROWS_PER_TRIAL = 10


def require_trial_length(
    trials: np.ndarray,
    history: int,
    func_name: str,
    *,
    history_name: str,
    time_axis: int,
) -> None:
    """Refuse trials too short to support ``history`` samples of lag structure.

    Three of four directed-connectivity estimators read a transposed ``(n_times, n_trials)``
    array under the default ``time_axis=-1`` as ``n_times`` trials of ``n_trials`` samples,
    and returned a number rather than raising. Measured at 7x400: ``x_to_y`` 1.90 on the good
    layout against 1.1e-07 to 3.7e-04 transposed -- an understatement of 5,147x to 17,716,885x
    over six seeds -- and ``transfer_entropy`` returned -0.005149, which is impossible for a
    quantity non-negative by construction. **The failure direction is the one that looks
    safe**, because near-zero reads as an honest negative result.

    Pooling is why the estimators stayed quiet: 400 trials of 7 samples supply thousands of
    lag-design rows in total, so nothing downstream is short of data. What is missing is
    *within-trial* extent, and that is what this checks. ``phase_slope_index`` was already
    loud for exactly this reason -- its segment length comes from the time axis, so it refused
    by name -- and this brings the other three to the same standard rather than lowering it.

    This is a statistical floor, not orientation detection: a genuinely short-trial design is
    refused too, and told which argument to change. Guessing the caller's intended layout and
    transposing for them would replace a loud wrong answer with a quiet right-looking one.
    """
    n_trials, n_times = int(trials.shape[0]), int(trials.shape[1])
    needed = int(history) + MIN_DESIGN_ROWS_PER_TRIAL
    if n_times >= needed:
        return
    rows = max(n_times - int(history), 0)
    raise ValueError(
        f"{func_name}: each trial has {n_times} samples, which supports {rows} design row(s) "
        f"against a lag structure of {history} ({history_name}); at least "
        f"{MIN_DESIGN_ROWS_PER_TRIAL} per trial are required, so {needed} samples. The input "
        f"was read as {n_trials} trials of {n_times} samples under time_axis={time_axis}. If "
        f"it is really {n_times} trials of {n_trials} samples, pass the time axis explicitly "
        f"(time_axis={0 if time_axis in (-1, 1) else -1}); if the trials are genuinely this "
        f"short, reduce {history_name}."
    )
