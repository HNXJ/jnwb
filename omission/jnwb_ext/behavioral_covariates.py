"""omission.jnwb_ext.behavioral_covariates -- pre-event-only pupil/gaze nuisance covariates.

Gated by ``omission/artifacts/.lab/pupil-gaze-semantics-audit-20260828.json`` (Task 1 semantics
audit, 2026-08-28, Hamm). Read that receipt before trusting anything below at face value; the
summary here is a pointer, not a substitute. Key findings that shape this module's design:

  - ``pupil_1_tracking`` / ``eye_1_tracking`` are ALREADY-TRANSFORMED signals in every session
    probed (value range approximately -5.0..+5.0, negative mean for pupil, ``unit`` attribute
    reading "unknown" for C31o/V198o and "arbitrary units"/"meters" for V182o). This range is
    incompatible with raw pupil diameter (which cannot be negative) and, for gaze, the "meters"
    label is incompatible with a screen at ~1.13 m producing a +/-5 m excursion. The stored
    values are therefore an UNKNOWN prior transform (z-scoring, clipping, or some other
    normalization applied upstream, mechanism not recoverable from NWB metadata alone) -- NOT
    calibrated physical units. Treat every feature this module returns as an unnormalized,
    dataset-specific-scale proxy: safe for within-session/within-subject relative comparison
    (e.g. z-scoring across trials of the same session), unsafe for cross-subject or
    cross-session comparison of raw magnitude, and NOT a real physical diameter/mm or
    degrees-of-visual-angle quantity.
  - No explicit invalid-sample/blink/track-loss/quality channel exists anywhere in
    ``acquisition/`` for any of the 6 sessions read at the value level (2 per subject) or the 22
    sessions read at the metadata level -- missingness is NOT flagged in the stored signal itself
    (0 NaN found anywhere sampled). QC in this module (see ``qc_behavioral_trials``) therefore
    uses a STATED STATISTICAL HEURISTIC (proximity to the corpus-wide observed clip bound,
    plus large sample-to-sample jumps) as a proxy for invalidity -- it is not a ground-truth
    validity read, and is reported as such.
  - C31o/V198o's group `description` attribute reads "Reconstructed pupil_1_tracking" /
    "Reconstructed eye_1_tracking". Some upstream reconstruction (plausibly gap/blink
    interpolation) was applied before these files were built. Whether that reconstruction only
    used past samples, or a centered/acausal window reaching into the future relative to any
    given sample, could NOT be determined from NWB metadata alone -- this is a real,
    UNRESOLVED, documented leakage risk (see the audit receipt's task1 item 10). This module
    cannot undo an upstream transform it cannot see; as a structural (not curative) mitigation it
    enforces ``window_ms`` to end at or before the trial's alignment anchor (t=0, hard assertion
    in ``load_behavioral_epochs``), exactly mirroring the pre-event safety argument already
    established for ``common_driver_control.estimate_amplitude_covariate``.
  - V182o's ``eye_1_tracking`` group description states "Actual sampling rate = 500 Hz
    (Reported=1kHz)" for all 10/10 V182o sessions -- this directly contradicts the file's own
    ``rate=1000.0`` TimeSeries attribute (which this module still uses for sample-index
    arithmetic, matching ``jnwb_ext.analog``'s existing convention, since there is no
    machine-readable alternative rate to act on) and the prior inventory receipt's blanket
    "1000 Hz confirmed" claim for pupil/gaze. Callers computing slope/variability on V182o gaze
    should treat effective temporal resolution as ~2 ms, not 1 ms -- a genuine per-subject
    corpus caveat, not a bug in this module.
  - No corpus-wide, verified fixation-center coordinate convention could be established from
    the design-time ``x_position``/``y_position``/``fixation_window`` intervals columns (mostly
    NaN, occasional 0.0 -- suggestive of a screen-center-at-origin convention for the TASK's
    stimulus placement, but the numerical relationship between those design columns and the
    continuously-recorded, already-transformed ``eye_1_tracking`` x/y is not established). This
    module therefore defaults ``fixation_center`` to the SESSION's own median pre-event gaze
    position (a data-driven, defensible proxy) rather than assuming (0, 0); a caller who wants
    the (0, 0)-at-screen-center assumption may pass ``fixation_center=(0.0, 0.0)`` explicitly.

Only pupil diameter and (x, y) gaze position pass Task 1's audit as legitimately extractable,
pre-event, common-cause-proxy behavioral covariates for this corpus -- saccade/microsaccade,
accelerometry, and a measured (non-design) fixation-quality signal are ABSENT from the corpus
entirely (see the audit receipt) and are not attempted here.

Architecture note: trial onsets are read via the SAME h5py-based, PyNWB-free machinery already
used by ``omission.jnwb_ext.analog`` (``_trial_table``), reused directly rather than
reimplemented, because several omission sessions contain PyNWB Device metadata that blocks a
full ``OmissionSession``/PyNWB build -- see ``analog.py``'s own module docstring. The returned
``BehavioralEpochBatch`` intentionally mirrors ``analog.EpochBatch``'s shape/field contract
((trial, channel, time) data, explicit time_ms, trial_metadata, manifest) so downstream code
already written against the LFP/MUAe accessor generalizes with minimal changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

import h5py
import numpy as np
import pandas as pd

from .analog import (
    _dataset,
    _float,
    _git_sha,
    _rate_and_start,
    _resolve_source,
    _scalar,
    _subject_from_stem,
    _trial_table,
)
from .sequence_layout import EPOCH_ONSETS_MS
from .unit_classification import OM_BASE_GAP_MS, OM_BASE_LEAD_MS

# Default pre-event windows, reusing existing corpus-wide constants verbatim rather than
# re-deriving them (per omission-data skill's reuse doctrine):
#   p1-anchored: the corpus's own fx baseline, (-500, 0) ms relative to p1 onset
#     (jnwb_ext.unit_classification.BASELINE_MS).
#   omission-slot-anchored: the same local pre-omission baseline window matched_empty.py already
#     uses for its "local_pre_omission_delay" comparator, (-250, -50) ms relative to the omitted
#     slot's own onset (OM_BASE_LEAD_MS / OM_BASE_GAP_MS).
DEFAULT_WINDOW_MS_BY_ANCHOR: dict[str, tuple[float, float]] = {
    "p1": (-500.0, 0.0),
    "omission": (-OM_BASE_LEAD_MS, -OM_BASE_GAP_MS),
}

# Corpus-wide observed clip-proximity bound for the QC heuristic (see module docstring; no
# ground-truth invalid-value marker exists, so this is a STATED heuristic, not a fact about the
# signal). Derived from a direct value-level read of 6 sessions (2 per subject) 2026-08-28:
# observed |value| max ranged 5.005-5.036 across pupil and both gaze channels, consistently
# clustered just above 5.0 -- never below 4.6. 5.0 is used as the round, slightly conservative
# clip-proximity threshold (a real sample at or above this bound is flagged QC-invalid).
#
# The independent verification of 2026-08-28 identified the physical mechanism behind this bound:
# every subject's pupil/gaze samples share a uniform 3.125e-4 = 10/32000 quantization step, i.e.
# these are uncalibrated analog-input volts on a +/-5 V full-scale converter. |v| >= 5 V is
# therefore RAIL SATURATION -- a genuine physical bound on the encoding, not a statistical guess.
CLIP_PROXIMITY_ABS = 5.0
RAIL_ABS_V = 5.0
ADC_FULL_SCALE_V = 10.0
ADC_QUANTIZATION_STEP_V = 10.0 / 32000.0  # 3.125e-4 V, measured, all 3 subjects

# ------------------------------------------------------------------------------------------
# QC thresholds. Every one of these is a STATED choice with a receipted rationale; see
# omission/artifacts/.lab/behavioral-qc-repair-20260829.json for the 22-session distribution
# audit each was calibrated against. Summary of the rationale (do not restate without re-reading
# the receipt):
#
#   QC_BLOCK_MS = 8.0
#     Discontinuity is measured between means of consecutive 8 ms blocks, NOT between adjacent
#     1 ms samples. Reason: the raw sample-to-sample difference measures ACQUISITION STRUCTURE,
#     not data quality. V198o's pupil channel carries a quasi-periodic large step every ~4
#     samples (modal inter-jump gap = 4 in 5/5 V198o sessions), i.e. an effective ~250 Hz update
#     rate stored at 1000 Hz; C31o's diff distribution is heavy-tailed; V182o's noise floor is
#     ~10x C31o's. Under a raw-sample criterion these three subjects are not commensurate at any
#     threshold (this is exactly why the previous window-local-SD version reported "V182o 0% vs
#     V198o 47-84% discontinuities" -- a subject-difference in acquisition, mis-read as quality).
#     At 8 ms (125 Hz) the block-jump statistic becomes commensurate across all three subjects
#     (per-session median 1.6-2.6, p99 2.6-6.4 session-scale units, 22/22 sessions), and 125 Hz
#     remains an order of magnitude above pupil dynamics bandwidth (< 10 Hz), so no genuine
#     pupil signal is discarded.
#
#   QC_MAX_JUMP_Z = 10.0
#     A block jump fails if it exceeds 10x the SESSION's OWN robust scale (1.4826 * MAD of all
#     that batch's block-to-block differences). Session-relative, per the audited finding that
#     noise floors are strongly subject-dependent, so no universal raw threshold is defensible.
#     10 is chosen to sit far above the bulk in EVERY session: the per-session p99 of this
#     statistic is <= 6.4 in 22/22 sessions and <= 5.7 in 21/22.
#
#   QC_ABS_JUMP_V = 0.5
#     Absolute floor, applied in OR with the relative criterion, so that a wholly corrupt session
#     cannot inflate its own scale until nothing is flagged. 0.5 V is 5% of ADC full scale in
#     8 ms.
#     CORRECTED 2026-08-29: an earlier draft of this comment claimed the maximum block jump on
#     non-flagged data was 0.1494 V ("roughly 3x margin"). Re-derivation across all 22 sessions
#     (behavioral-qc-repair-20260829.json, summary.max_block_jump_v_on_passing_trials_corpus)
#     measures 0.4623 V. The criterion still separates -- no passing trial exceeds the threshold --
#     but the true margin is ~1.08x, NOT 3x, so this floor sits close to the top of the normal
#     range rather than far above it. Treat 0.5 V as near-binding: a modest tightening would begin
#     excluding ordinary trials, and a modest loosening would stop catching the flagged ones.
#
#   QC_MAX_EXCURSION_Z = 10.0
#     Gaze only. There is NO calibrated screen boundary in this corpus (uncalibrated volts, no
#     verified fixation-center convention), so "gaze off screen" is NOT determinable and is not
#     attempted. This is a session-relative robust-z outlier flag on the trial's mean distance
#     from the batch's own median gaze position -- a flag, not a physical off-screen test.
#     Per-session p95 of this z is 2.0-5.1 and per-session max 4.2-33.5 across 22 sessions, so 10
#     flags only a genuine tail (0-0.6% of trials per session).
#
#   NO jump criterion is applied to GAZE. At 8 ms, large gaze steps are SACCADES -- normal
#     behaviour, present on 7-48% of trials in every session and every subject. Excluding them
#     would exclude ordinary data for doing what eyes do. Gaze jump magnitudes are still reported
#     as diagnostics so a caller can apply their own criterion knowingly.
#
#   QC_MIN_VALID_FRAC = 0.5 / QC_MIN_SESSION_FRAC = 0.5
#     Retained, stated, not derived: at least half a window's samples must be valid for its mean
#     to be a meaningful pre-event summary, and at least half a session's trials must carry usable
#     behavior for a session-level gate to read as available.
# ------------------------------------------------------------------------------------------
QC_BLOCK_MS = 8.0
QC_MAX_JUMP_Z = 10.0
QC_ABS_JUMP_V = 0.5
QC_MAX_EXCURSION_Z = 10.0
QC_MIN_VALID_FRAC = 0.5
QC_MIN_SESSION_FRAC = 0.5
# Below this many base-passing trials the session-relative scales (block-diff MAD, gaze-excursion
# MAD) are too unstable to threshold against; the relative criteria are then SKIPPED (reported as
# NaN and not counted as a failure) rather than applied to an unreliable scale. Conservative
# by design: this module flags, it does not guess.
QC_MIN_TRIALS_FOR_RELATIVE_SCALE = 8


@dataclass(frozen=True)
class BehavioralEpochBatch:
    """Trial-aligned pupil/gaze epochs and explicit provenance.

    ``data`` is always ``(trial, channel, time)`` -- pupil has 1 channel ("pupil_diameter"),
    gaze has 2 ("gaze_x", "gaze_y") -- matching ``analog.EpochBatch``'s shape contract.
    """

    data: np.ndarray
    time_ms: np.ndarray
    channel_names: tuple[str, ...]
    trial_metadata: pd.DataFrame
    manifest: dict[str, Any]


def _behavioral_dataset(handle: h5py.File, signal_class: str) -> dict[str, Any]:
    signal_class = signal_class.lower()
    if signal_class not in {"pupil", "gaze"}:
        raise ValueError("signal_class must be 'pupil' or 'gaze'")
    acquisition_key = "pupil_1_tracking" if signal_class == "pupil" else "eye_1_tracking"
    acquisition = handle.get("acquisition")
    if acquisition is None or acquisition_key not in acquisition:
        raise ValueError(f"NWB has no acquisition/{acquisition_key} group")
    root = acquisition[acquisition_key]
    data_path, data = _dataset(root, "data")
    if data is None:
        raise ValueError(f"{acquisition_key} does not expose a data dataset")
    rate, start, time_base = _rate_and_start(root, data)
    if signal_class == "pupil":
        if data.ndim != 1:
            raise ValueError(f"{acquisition_key} data expected 1-D, got shape {data.shape}")
        channel_names: tuple[str, ...] = ("pupil_diameter",)
    else:
        if data.ndim != 2 or data.shape[1] != 2:
            raise ValueError(f"{acquisition_key} data expected (n, 2), got shape {data.shape}")
        channel_names = ("gaze_x", "gaze_y")
    return {
        "object_path": f"acquisition/{acquisition_key}",
        "dataset_path": f"acquisition/{acquisition_key}/{data_path}",
        "n_samples": int(data.shape[0]),
        "channel_names": channel_names,
        "sampling_rate_hz": rate,
        "starting_time_s": start,
        "time_base": time_base,
        "units": str(_scalar(data.attrs.get("unit", "unknown"))),
        "data": data,
    }


def load_behavioral_epochs(
    source: Any,
    *,
    signal_class: str,
    condition: str | Sequence[str] | None = None,
    slot_keys: Sequence[str] | None = None,
    window_ms: tuple[float, float] | None = None,
    alignment: str = "p1",
    correct_only: bool = True,
    missing_data: str = "drop",
    max_trials: int | None = None,
) -> BehavioralEpochBatch:
    """Load trial-aligned pupil or gaze epochs, strictly pre-event by construction.

    ``window_ms`` defaults per ``alignment`` (see ``DEFAULT_WINDOW_MS_BY_ANCHOR``); a caller may
    narrow it but ``hi_ms`` (the window's later edge) can never be positive -- enforced with a
    hard assertion, not a convention, so a future caller cannot silently pull in a post-event
    sample. ``missing_data`` defaults to ``"drop"`` here (unlike ``analog.load_analog_epochs``'s
    ``"raise"`` default) because edge-of-recording trial drops are expected and routine for a
    pre-event-only window near a session boundary, not a signal of a broken extraction.
    """
    signal_class = signal_class.lower()
    if signal_class not in {"pupil", "gaze"}:
        raise ValueError("signal_class must be 'pupil' or 'gaze'")
    if alignment not in {"p1", "omission"}:
        raise ValueError("alignment must be 'p1' or 'omission'")
    if missing_data not in {"raise", "drop"}:
        raise ValueError("missing_data must be 'raise' or 'drop'")
    if window_ms is None:
        window_ms = DEFAULT_WINDOW_MS_BY_ANCHOR[alignment]
    lo_ms, hi_ms = map(float, window_ms)
    if not hi_ms > lo_ms:
        raise ValueError("window_ms must have hi > lo")
    if hi_ms > 0.0:
        raise ValueError(
            "window_ms's later edge must be <= 0 (at or before the alignment anchor) -- "
            "this accessor is pre-event-only by contract, no exceptions"
        )

    path = _resolve_source(source)
    stem = path.stem
    with h5py.File(path, "r") as handle:
        trials = _trial_table(handle, stem, condition, slot_keys, correct_only)
        if alignment == "omission":
            trials = trials[trials["omission_position"].notna()].copy()
            if trials.empty:
                raise ValueError("omission alignment requires omission trials")
        trials = trials.sort_values("start_time").reset_index(drop=True)
        if max_trials is not None:
            if max_trials < 1:
                raise ValueError("max_trials must be positive")
            trials = trials.iloc[:max_trials].copy()

        series = _behavioral_dataset(handle, signal_class)
        rate = series["sampling_rate_hz"]
        n_samples_float = (hi_ms - lo_ms) / 1000.0 * rate
        n_samples = int(round(n_samples_float))
        if not np.isclose(n_samples_float, n_samples):
            raise ValueError("window duration does not map to an integral sample count")
        time_ms = lo_ms + np.arange(n_samples, dtype=float) * 1000.0 / rate

        data_ds = series["data"]
        n_channels = len(series["channel_names"])
        epoch_parts: list[np.ndarray] = []
        kept_rows: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []
        for _, row in trials.iterrows():
            if alignment == "p1":
                anchor_s = float(row["start_time"])
            else:
                anchor_s = float(row["start_time"]) + (
                    EPOCH_ONSETS_MS[str(row["omission_position"])] / 1000.0
                )
            start_index = int(round((anchor_s + lo_ms / 1000.0 - series["starting_time_s"]) * rate))
            stop_index = start_index + n_samples
            if start_index < 0 or stop_index > series["n_samples"]:
                reason = f"OUT_OF_BOUNDS:{series['object_path']}:{start_index}:{stop_index}/{series['n_samples']}"
                dropped.append({"trial_id": row["trial_id"], "reason": reason})
                if missing_data == "raise":
                    raise ValueError(f"behavioral epoch extraction blocked: {reason}")
                continue
            if n_channels == 1:
                chunk = np.asarray(data_ds[start_index:stop_index], dtype=np.float64).reshape(1, -1)
            else:
                chunk = np.asarray(data_ds[start_index:stop_index, :], dtype=np.float64).T
            if chunk.shape != (n_channels, n_samples):
                reason = f"SHAPE_MISMATCH:{chunk.shape}"
                dropped.append({"trial_id": row["trial_id"], "reason": reason})
                if missing_data == "raise":
                    raise ValueError(f"behavioral epoch extraction blocked: {reason}")
                continue
            epoch_parts.append(chunk)
            kept = row.to_dict()
            kept.update({"anchor": alignment, "anchor_onset_s": anchor_s,
                         "source_onset_s": float(row["start_time"])})
            kept_rows.append(kept)
        if not epoch_parts:
            raise ValueError("all requested behavioral epochs were unavailable")
        data = np.stack(epoch_parts, axis=0)
        manifest = {
            "artifact_schema_version": 1,
            "signal_class": signal_class,
            "source_nwb": str(path),
            "source_nwb_size_bytes": int(path.stat().st_size),
            "source_nwb_mtime_ns": int(path.stat().st_mtime_ns),
            "source_object_path": series["object_path"],
            "source_dataset_path": series["dataset_path"],
            "source_units_attr": series["units"],
            "source_units_attr_caveat": (
                "NOT trusted as calibrated physical units -- see module docstring; "
                "'unknown'/'arbitrary units'/'meters' are all observed and none is verified"
            ),
            "sampling_rate_hz": rate,
            "time_base": series["time_base"],
            "alignment_event": alignment,
            "window_ms": [lo_ms, hi_ms],
            "pre_event_only_enforced": True,
            "time_vector_ms": time_ms.tolist(),
            "shape": list(data.shape),
            "dtype": str(data.dtype),
            "missing_data_policy": missing_data,
            "dropped_trials": dropped,
            "trial_id_join_key": "trial_id",
            "repo_sha": _git_sha(),
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
    return BehavioralEpochBatch(
        data=data,
        time_ms=time_ms,
        channel_names=series["channel_names"],
        trial_metadata=pd.DataFrame(kept_rows).reset_index(drop=True),
        manifest=manifest,
    )


def load_pupil_epochs(source: Any, **kwargs: Any) -> BehavioralEpochBatch:
    """Load pre-event-only pupil-diameter epochs under the canonical behavioral contract."""
    return load_behavioral_epochs(source, signal_class="pupil", **kwargs)


def load_gaze_epochs(source: Any, **kwargs: Any) -> BehavioralEpochBatch:
    """Load pre-event-only (x, y) gaze epochs under the canonical behavioral contract."""
    return load_behavioral_epochs(source, signal_class="gaze", **kwargs)


# ------------------------------------------------------------------------------------------
# QC: per-sample invalidity heuristic (STATED heuristic, not a ground-truth read -- see docstring)
# ------------------------------------------------------------------------------------------

def _invalid_sample_mask(x: np.ndarray, clip_bound: float = CLIP_PROXIMITY_ABS) -> np.ndarray:
    """True where a sample is NaN or at/beyond the corpus-observed clip-proximity bound.

    No dedicated blink/track-loss/validity channel exists in this corpus (Task 1 audit) -- this
    is the best available proxy, not a confirmed invalid-value encoding. Callers should treat
    the resulting "valid fraction" as a QC diagnostic, not a precise missingness count.
    """
    return ~np.isfinite(x) | (np.abs(x) >= clip_bound)


def valid_fraction(window: np.ndarray, clip_bound: float = CLIP_PROXIMITY_ABS) -> float:
    """Fraction of samples in a 1-D pre-event window judged valid by ``_invalid_sample_mask``."""
    if window.size == 0:
        return 0.0
    return float(1.0 - np.mean(_invalid_sample_mask(window, clip_bound)))


def discontinuity_count(window: np.ndarray, threshold_sd: float = 5.0) -> int:
    """DEPRECATED as a QC criterion -- retained only as a descriptive statistic.

    Count of sample-to-sample jumps exceeding ``threshold_sd`` times the WINDOW's own
    sample-to-sample diff SD. Returns 0 for an all-NaN or fewer-than-3-sample window.

    Do NOT gate trials on this. Two independently receipted defects make it unusable as a
    validity criterion, and it is deliberately NOT wired into ``qc_pass``:

    1. It self-normalizes by the window's own diff SD, a non-robust scale INFLATED by the very
       jumps it is trying to detect, estimated from a few hundred samples of one trial.
    2. At the raw 1 ms sample grid it measures acquisition structure, not quality. V198o's pupil
       channel steps every ~4 samples (~250 Hz effective update rate stored at 1000 Hz), so it
       reports 47-95% of V198o trials as "discontinuous" while reporting 0% for V182o, whose
       noise floor is ~10x higher. That contrast is a per-subject acquisition difference, not a
       data-quality difference (verification receipt
       ``independent-verification-behavioral-covariates-20260828.json``, item V6).

    Use ``block_jump_diagnostics`` / the ``max_block_jump_z`` column instead.
    """
    finite = window[np.isfinite(window)]
    if finite.size < 3:
        return 0
    d = np.diff(finite)
    sd = np.std(d)
    if sd == 0:
        return 0
    return int(np.sum(np.abs(d) > threshold_sd * sd))


def robust_scale(x: np.ndarray) -> float:
    """1.4826 * median-absolute-deviation about the median (consistent sigma estimate under
    normality, and unlike SD not inflated by the outliers it is used to detect). NaN if fewer
    than 2 finite values."""
    finite = np.asarray(x, dtype=float).ravel()
    finite = finite[np.isfinite(finite)]
    if finite.size < 2:
        return float("nan")
    return float(1.4826 * np.median(np.abs(finite - np.median(finite))))


def _block_means(A: np.ndarray, block_samples: int) -> np.ndarray:
    """(trial, time) -> (trial, n_block) block means; trailing partial block is discarded."""
    if block_samples < 1:
        raise ValueError("block_samples must be >= 1")
    n = A.shape[1] // block_samples * block_samples
    if n < 2 * block_samples:
        return np.empty((A.shape[0], 0), dtype=float)
    return A[:, :n].reshape(A.shape[0], -1, block_samples).mean(axis=2)


def block_jump_diagnostics(
    data: np.ndarray,
    *,
    sampling_rate_hz: float,
    block_ms: float = QC_BLOCK_MS,
    max_jump_z: float = QC_MAX_JUMP_Z,
    abs_jump_v: float = QC_ABS_JUMP_V,
    scale: float | None = None,
) -> dict[str, Any]:
    """Per-trial discontinuity diagnostics on a ``(trial, time)`` array, measured between means
    of consecutive ``block_ms`` blocks and normalized by the BATCH's own robust scale.

    Returns a dict with ``session_block_diff_scale`` (the 1.4826*MAD scale, in the signal's own
    volts) and per-trial arrays ``max_jump_v``, ``max_jump_z``, ``n_jumps`` (jumps exceeding
    EITHER the relative or the absolute criterion). All-NaN arrays and ``scale=nan`` are returned
    when the window is too short to hold two blocks -- a "cannot measure", never a silent pass.

    ``scale`` may be supplied to reuse a scale estimated over a larger pool (e.g. a whole
    session) instead of this batch's own.
    """
    A = np.asarray(data, dtype=float)
    n_trials = A.shape[0]
    block_samples = int(round(block_ms / 1000.0 * float(sampling_rate_hz)))
    block_samples = max(block_samples, 1)
    B = _block_means(A, block_samples)
    nan = np.full(n_trials, np.nan)
    if B.shape[1] < 2:
        return {"session_block_diff_scale": float("nan"), "block_samples": block_samples,
                "max_jump_v": nan, "max_jump_z": nan.copy(),
                "n_jumps": np.zeros(n_trials, dtype=int), "measurable": False}
    d = np.diff(B, axis=1)
    sc = robust_scale(d) if scale is None else float(scale)
    # A wholly invalid trial (every sample NaN, e.g. full rail saturation) yields an all-NaN
    # difference row. np.nanmax warns on that and still returns NaN, which is the answer we
    # want -- "no measurable jump" -- so suppress the warning rather than special-casing, and
    # let the separate valid-fraction criterion be what actually fails such a trial.
    all_nan_rows = np.all(~np.isfinite(d), axis=1)
    max_v = np.full(n_trials, np.nan)
    if not np.all(all_nan_rows):
        max_v[~all_nan_rows] = np.nanmax(np.abs(d[~all_nan_rows]), axis=1)
    if np.isfinite(sc) and sc > 0 and n_trials >= QC_MIN_TRIALS_FOR_RELATIVE_SCALE:
        max_z = max_v / sc
        n_jumps = np.sum((np.abs(d) > max_jump_z * sc) | (np.abs(d) > abs_jump_v), axis=1)
    else:
        # scale unusable (degenerate or too few trials) -- relative criterion is SKIPPED, the
        # absolute physical floor still applies.
        max_z = nan.copy()
        n_jumps = np.sum(np.abs(d) > abs_jump_v, axis=1)
    return {"session_block_diff_scale": sc, "block_samples": block_samples,
            "max_jump_v": max_v, "max_jump_z": max_z,
            "n_jumps": n_jumps.astype(int), "measurable": True}


# ------------------------------------------------------------------------------------------
# Task 2: per-trial scalar feature extraction (pre-event-only, PC's window already enforced by
# the loader -- these functions never see a post-anchor sample by construction).
# ------------------------------------------------------------------------------------------

def _safe_slope(y: np.ndarray) -> float:
    """OLS slope of ``y`` against its own sample index; NaN if fewer than 2 finite points."""
    finite = np.isfinite(y)
    if finite.sum() < 2:
        return float("nan")
    x = np.arange(len(y))[finite]
    yy = y[finite]
    return float(np.polyfit(x, yy, 1)[0])


def _batch_rate(batch: BehavioralEpochBatch) -> float:
    rate = float(batch.manifest.get("sampling_rate_hz", float("nan")))
    if not np.isfinite(rate) or rate <= 0:
        raise ValueError("batch.manifest lacks a usable sampling_rate_hz; QC cannot be timed")
    return rate


def extract_pupil_features(
    batch: BehavioralEpochBatch,
    *,
    min_valid_frac: float = QC_MIN_VALID_FRAC,
    clip_bound: float = RAIL_ABS_V,
    block_ms: float = QC_BLOCK_MS,
    max_jump_z: float = QC_MAX_JUMP_Z,
    abs_jump_v: float = QC_ABS_JUMP_V,
) -> pd.DataFrame:
    """Pre-event pupil features + per-trial QC, one row per KEPT trial in ``batch`` (batch is
    already pre-event-only by the loader's contract; no future sample is ever touched here).

    ``qc_pass`` is a conjunction of four criteria, each with its own diagnostic column so a
    caller can always see WHY a trial failed (never an opaque boolean):

      1. ``valid_frac >= min_valid_frac``  -- diagnostics ``valid_frac``, ``rail_frac``,
         ``nonfinite_frac``. A sample is invalid if non-finite or at/beyond the +/-5 V ADC rail.
      2. ``n_valid >= 2``                  -- diagnostic ``n_valid``.
      3. no block discontinuity            -- diagnostics ``max_block_jump_v``,
         ``max_block_jump_z``, ``n_block_jumps``. Fails when the largest ``block_ms``-block-mean
         step exceeds EITHER ``max_jump_z`` x this batch's own robust scale OR ``abs_jump_v``
         volts absolute. See this module's QC-threshold block for the calibration receipt.
      4. channel not flat/stuck            -- diagnostic ``is_flat`` (the trial's own robust
         successive-difference scale is exactly zero, i.e. a dead or held channel).

    ``qc_fail_reasons`` carries a ``|``-joined string of the criteria a trial failed (empty
    string when it passed), for direct audit.

    Feature columns: mean, median, sd, slope (linear trend across the window), prev_trial_diff
    (this trial's mean minus the IMMEDIATELY PRECEDING trial's mean, in this batch's own
    onset-time order -- "preceding" means the previous physical trial in the session timeline,
    regardless of condition; NaN for the first trial and whenever the previous row's own qc_pass
    is False, since the delta would be contaminated by an ill-defined previous mean).

    Nothing is imputed: a failing trial keeps its computed feature values (so the failure can be
    inspected) and is simply marked ``qc_pass=False``; no missing region is ever filled in.

    ``batch`` must be a pupil batch (``channel_names == ("pupil_diameter",)``); raises otherwise.
    """
    if batch.channel_names != ("pupil_diameter",):
        raise ValueError(f"extract_pupil_features requires a pupil batch, got channels {batch.channel_names}")
    A = np.asarray(batch.data[:, 0, :], dtype=float)
    n_trials = A.shape[0]
    jumps = block_jump_diagnostics(A, sampling_rate_hz=_batch_rate(batch), block_ms=block_ms,
                                   max_jump_z=max_jump_z, abs_jump_v=abs_jump_v)

    rows: list[dict[str, Any]] = []
    means = np.full(n_trials, np.nan)
    for i in range(n_trials):
        window = A[i]
        invalid = _invalid_sample_mask(window, clip_bound)
        valid_mask = ~invalid
        clean = window[valid_mask]
        vfrac = valid_fraction(window, clip_bound)
        is_flat = bool(window.size >= 3 and robust_scale(np.diff(window)) == 0.0)
        jump_fail = bool(jumps["n_jumps"][i] > 0)

        reasons: list[str] = []
        if vfrac < min_valid_frac:
            reasons.append("low_valid_frac")
        if clean.size < 2:
            reasons.append("too_few_valid_samples")
        if jump_fail:
            reasons.append("block_discontinuity")
        if is_flat:
            reasons.append("flat_channel")
        qc_pass = not reasons

        mean = float(np.mean(clean)) if clean.size else float("nan")
        means[i] = mean if qc_pass else np.nan
        rows.append({
            "trial_id": batch.trial_metadata.loc[i, "trial_id"],
            "n_samples": int(window.size),
            "n_valid": int(clean.size),
            "valid_frac": vfrac,
            "rail_frac": float(np.mean(np.abs(window) >= clip_bound)),
            "nonfinite_frac": float(np.mean(~np.isfinite(window))),
            "max_block_jump_v": float(jumps["max_jump_v"][i]),
            "max_block_jump_z": float(jumps["max_jump_z"][i]),
            "n_block_jumps": int(jumps["n_jumps"][i]),
            "is_flat": is_flat,
            "qc_pass": bool(qc_pass),
            "qc_fail_reasons": "|".join(reasons),
            "mean": mean,
            "median": float(np.median(clean)) if clean.size else float("nan"),
            "sd": float(np.std(clean)) if clean.size >= 2 else float("nan"),
            "slope": _safe_slope(np.where(valid_mask, window, np.nan)),
        })
    frame = pd.DataFrame(rows)
    frame["session_block_diff_scale"] = jumps["session_block_diff_scale"]
    prev_mean = np.roll(means, 1)
    prev_mean[0] = np.nan
    frame["prev_trial_diff"] = frame["mean"].to_numpy() - prev_mean
    frame.loc[~frame["qc_pass"], "prev_trial_diff"] = np.nan
    return frame


def extract_gaze_features(
    batch: BehavioralEpochBatch,
    *,
    min_valid_frac: float = QC_MIN_VALID_FRAC,
    clip_bound: float = RAIL_ABS_V,
    fixation_center: tuple[float, float] | None = None,
    max_excursion_z: float = QC_MAX_EXCURSION_Z,
    block_ms: float = QC_BLOCK_MS,
) -> pd.DataFrame:
    """Pre-event gaze features + per-trial QC, one row per KEPT trial in ``batch``.

    ``fixation_center`` defaults to this batch's OWN median (x, y) across the valid pre-event
    samples of trials that pass the sample-level criteria -- a data-driven proxy, used because no
    corpus-verified (0, 0)-at-screen-center convention could be confirmed for the
    continuously-recorded, already-transformed ``eye_1_tracking`` channel (see module docstring).
    Pass an explicit ``fixation_center`` to override with a specific assumption. (Before
    2026-08-29 this default was computed with ``np.mean`` while the docstring said "median"; it
    is now the median in fact, both to match the stated contract and because the excursion
    criterion below needs a breakdown-resistant center.)

    ``qc_pass`` is a conjunction of three criteria, each with its own diagnostic column:

      1. ``min(valid_frac_x, valid_frac_y) >= min_valid_frac`` -- diagnostics ``valid_frac_x``,
         ``valid_frac_y``, ``rail_frac_x``, ``rail_frac_y``. Invalid = non-finite or at/beyond
         the +/-5 V ADC rail.
      2. ``n_valid >= 2``                                      -- diagnostic ``n_valid``.
      3. gaze excursion not an outlier                         -- diagnostic ``excursion_z``, the
         robust z of ``dist_from_center`` against the median and 1.4826*MAD of the trials passing
         (1) and (2). This is a SESSION-RELATIVE OUTLIER FLAG, not an off-screen test: this
         corpus carries no calibrated screen geometry, so "gaze left the screen" is not
         determinable and is not claimed. Because the center and scale are estimated from the
         same trials being screened, this criterion is deliberately conservative and must NOT be
         used to make claims about the excursion distribution itself (criterion circularity).
         It is skipped -- ``excursion_z`` NaN, no failure -- when fewer than
         ``QC_MIN_TRIALS_FOR_RELATIVE_SCALE`` trials pass (1)-(2) or the scale is degenerate.

    NO discontinuity/jump criterion is applied to gaze: at the 8 ms QC block scale, large gaze
    steps are saccades (present on 7-48% of trials in every one of the 22 sessions audited), i.e.
    normal behaviour. ``max_block_jump_v``/``max_block_jump_z`` for x and y are still reported as
    DIAGNOSTICS so a caller may apply their own criterion knowingly.

    ``qc_fail_reasons`` carries a ``|``-joined string of failed criteria (empty when passing).
    Nothing is imputed; failing trials keep their computed values and are marked, not filled.
    """
    if batch.channel_names != ("gaze_x", "gaze_y"):
        raise ValueError(f"extract_gaze_features requires a gaze batch, got channels {batch.channel_names}")
    n_trials = batch.data.shape[0]
    X = np.asarray(batch.data[:, 0, :], dtype=float)
    Y = np.asarray(batch.data[:, 1, :], dtype=float)
    rate = _batch_rate(batch)
    jx = block_jump_diagnostics(X, sampling_rate_hz=rate, block_ms=block_ms)
    jy = block_jump_diagnostics(Y, sampling_rate_hz=rate, block_ms=block_ms)

    rows: list[dict[str, Any]] = []
    base_pass = np.zeros(n_trials, dtype=bool)
    all_valid_x: list[np.ndarray] = []
    all_valid_y: list[np.ndarray] = []
    for i in range(n_trials):
        wx, wy = X[i], Y[i]
        vfrac_x = valid_fraction(wx, clip_bound)
        vfrac_y = valid_fraction(wy, clip_bound)
        mask = ~_invalid_sample_mask(wx, clip_bound) & ~_invalid_sample_mask(wy, clip_bound)
        clean_x, clean_y = wx[mask], wy[mask]
        reasons: list[str] = []
        if min(vfrac_x, vfrac_y) < min_valid_frac:
            reasons.append("low_valid_frac")
        if clean_x.size < 2:
            reasons.append("too_few_valid_samples")
        base_pass[i] = not reasons
        mean_x = float(np.mean(clean_x)) if clean_x.size else float("nan")
        mean_y = float(np.mean(clean_y)) if clean_y.size else float("nan")
        if base_pass[i]:
            all_valid_x.append(clean_x)
            all_valid_y.append(clean_y)
        rows.append({
            "trial_id": batch.trial_metadata.loc[i, "trial_id"],
            "n_samples": int(wx.size),
            "n_valid": int(clean_x.size),
            "valid_frac_x": vfrac_x,
            "valid_frac_y": vfrac_y,
            "rail_frac_x": float(np.mean(np.abs(wx) >= clip_bound)),
            "rail_frac_y": float(np.mean(np.abs(wy) >= clip_bound)),
            "max_block_jump_v_x": float(jx["max_jump_v"][i]),
            "max_block_jump_z_x": float(jx["max_jump_z"][i]),
            "max_block_jump_v_y": float(jy["max_jump_v"][i]),
            "max_block_jump_z_y": float(jy["max_jump_z"][i]),
            "mean_x": mean_x,
            "mean_y": mean_y,
            "sd_x": float(np.std(clean_x)) if clean_x.size >= 2 else float("nan"),
            "sd_y": float(np.std(clean_y)) if clean_y.size >= 2 else float("nan"),
            "slope_x": _safe_slope(np.where(mask, wx, np.nan)),
            "slope_y": _safe_slope(np.where(mask, wy, np.nan)),
            "_base_reasons": reasons,
        })
    frame = pd.DataFrame(rows)

    if fixation_center is None:
        if all_valid_x:
            fixation_center = (float(np.median(np.concatenate(all_valid_x))),
                               float(np.median(np.concatenate(all_valid_y))))
        else:
            fixation_center = (float("nan"), float("nan"))
    frame["fixation_center_x"] = fixation_center[0]
    frame["fixation_center_y"] = fixation_center[1]
    dist = np.hypot(frame["mean_x"].to_numpy() - fixation_center[0],
                    frame["mean_y"].to_numpy() - fixation_center[1])
    frame["dist_from_center"] = dist

    # Criterion 3: session-relative robust-z excursion flag, calibrated on base-passing trials.
    excursion_z = np.full(n_trials, np.nan)
    ref = dist[base_pass]
    ref = ref[np.isfinite(ref)]
    scale = robust_scale(ref) if ref.size >= QC_MIN_TRIALS_FOR_RELATIVE_SCALE else float("nan")
    if np.isfinite(scale) and scale > 0:
        excursion_z = (dist - np.median(ref)) / scale
    frame["excursion_z"] = excursion_z
    frame["excursion_scale"] = scale

    reasons_col: list[str] = []
    qc = np.zeros(n_trials, dtype=bool)
    for i in range(n_trials):
        rs_ = list(frame.loc[i, "_base_reasons"])
        if np.isfinite(excursion_z[i]) and excursion_z[i] > max_excursion_z:
            rs_.append("gaze_excursion_outlier")
        qc[i] = not rs_
        reasons_col.append("|".join(rs_))
    frame = frame.drop(columns=["_base_reasons"])
    frame["qc_pass"] = qc
    frame["qc_fail_reasons"] = reasons_col

    # prev_dist = the PRECEDING physical trial's own dist_from_center, masked out (set NaN)
    # whenever that preceding trial itself failed QC (an ill-defined "prior state" otherwise).
    prev_dist = np.roll(dist, 1)
    prev_dist[0] = np.nan
    prev_qc = np.roll(qc, 1)
    prev_qc[0] = False
    prev_dist[~prev_qc] = np.nan
    frame["prev_trial_dist_diff"] = dist - prev_dist
    frame.loc[~frame["qc_pass"], "prev_trial_dist_diff"] = np.nan
    return frame


# ------------------------------------------------------------------------------------------
# Task 5(a): genuine, receipted behavioral-coverage check for matched_empty.py
# ------------------------------------------------------------------------------------------

def trial_has_valid_behavior(
    source: Any,
    *,
    condition: str | Sequence[str] | None = None,
    slot_keys: Sequence[str] | None = None,
    alignment: str = "p1",
    min_valid_frac: float = QC_MIN_VALID_FRAC,
    correct_only: bool = True,
    max_jump_z: float = QC_MAX_JUMP_Z,
    abs_jump_v: float = QC_ABS_JUMP_V,
    max_excursion_z: float = QC_MAX_EXCURSION_Z,
    block_ms: float = QC_BLOCK_MS,
) -> pd.DataFrame:
    """Real per-trial pupil+gaze coverage check, keyed by ``trial_id``, for wiring a genuine
    ``behavior_available`` flag (replaces the previously-hardcoded ``False`` claim in
    ``matched_empty.py`` -- see that module's updated docstring and
    ``session_behavior_coverage`` below).

    A trial passes (``behavior_available=True``) only if BOTH its pupil and its gaze pre-event
    window pass the full per-trial QC conjunction documented on ``extract_pupil_features`` /
    ``extract_gaze_features`` -- valid-sample fraction, minimum valid samples, pupil block
    discontinuity, flat-channel, and gaze excursion -- not merely "the channel exists in this
    file" (true for 22/22 sessions and therefore not a real gate), and no longer merely the
    valid-fraction test (which excluded 0 of 960 trials on the session where this defect was
    caught, verification receipt ``independent-verification-behavioral-covariates-20260828.json``
    item V6).

    The returned frame carries the per-trial DIAGNOSTICS behind each decision
    (``pupil_qc_fail_reasons``, ``gaze_qc_fail_reasons``, ``pupil_valid_frac``,
    ``pupil_max_block_jump_z``, ``pupil_max_block_jump_v``, ``pupil_n_block_jumps``,
    ``gaze_valid_frac_min``, ``gaze_excursion_z``) so a caller can audit why a trial failed
    rather than reading an opaque boolean.

    Returns an empty frame (not an error) if extraction fails for a structural reason (e.g. no
    trials for the requested condition/slot in this session) -- callers should treat a missing
    trial_id as behavior_available=False, not silently skip it.
    """
    try:
        pupil_batch = load_pupil_epochs(source, condition=condition, slot_keys=slot_keys,
                                         alignment=alignment, correct_only=correct_only,
                                         missing_data="drop")
        gaze_batch = load_gaze_epochs(source, condition=condition, slot_keys=slot_keys,
                                       alignment=alignment, correct_only=correct_only,
                                       missing_data="drop")
    except ValueError:
        return pd.DataFrame(columns=["trial_id", "behavior_available"])

    pupil_feat = extract_pupil_features(pupil_batch, min_valid_frac=min_valid_frac,
                                        block_ms=block_ms, max_jump_z=max_jump_z,
                                        abs_jump_v=abs_jump_v)
    gaze_feat = extract_gaze_features(gaze_batch, min_valid_frac=min_valid_frac,
                                      max_excursion_z=max_excursion_z, block_ms=block_ms)
    pupil_cols = pupil_feat[[
        "trial_id", "qc_pass", "qc_fail_reasons", "valid_frac",
        "max_block_jump_z", "max_block_jump_v", "n_block_jumps", "is_flat",
    ]].rename(columns={
        "qc_pass": "pupil_qc_pass", "qc_fail_reasons": "pupil_qc_fail_reasons",
        "valid_frac": "pupil_valid_frac", "max_block_jump_z": "pupil_max_block_jump_z",
        "max_block_jump_v": "pupil_max_block_jump_v", "n_block_jumps": "pupil_n_block_jumps",
        "is_flat": "pupil_is_flat",
    })
    gaze_cols = gaze_feat[["trial_id", "qc_pass", "qc_fail_reasons", "excursion_z"]].copy()
    gaze_cols["gaze_valid_frac_min"] = np.minimum(gaze_feat["valid_frac_x"], gaze_feat["valid_frac_y"])
    gaze_cols = gaze_cols.rename(columns={
        "qc_pass": "gaze_qc_pass", "qc_fail_reasons": "gaze_qc_fail_reasons",
        "excursion_z": "gaze_excursion_z",
    })
    merged = pupil_cols.merge(gaze_cols, on="trial_id", how="outer")
    merged["pupil_qc_pass"] = merged["pupil_qc_pass"].fillna(False).astype(bool)
    merged["gaze_qc_pass"] = merged["gaze_qc_pass"].fillna(False).astype(bool)
    merged["pupil_qc_fail_reasons"] = merged["pupil_qc_fail_reasons"].fillna("pupil_epoch_missing")
    merged["gaze_qc_fail_reasons"] = merged["gaze_qc_fail_reasons"].fillna("gaze_epoch_missing")
    merged["behavior_available"] = merged["pupil_qc_pass"] & merged["gaze_qc_pass"]
    ordered = ["trial_id", "behavior_available", "pupil_qc_pass", "gaze_qc_pass",
               "pupil_qc_fail_reasons", "gaze_qc_fail_reasons", "pupil_valid_frac",
               "pupil_max_block_jump_z", "pupil_max_block_jump_v", "pupil_n_block_jumps",
               "pupil_is_flat", "gaze_valid_frac_min", "gaze_excursion_z"]
    return merged[ordered]


def session_behavior_coverage(
    source: Any,
    *,
    alignment: str = "p1",
    min_valid_frac: float = QC_MIN_VALID_FRAC,
    correct_only: bool = True,
    min_session_frac: float = QC_MIN_SESSION_FRAC,
    max_jump_z: float = QC_MAX_JUMP_Z,
    abs_jump_v: float = QC_ABS_JUMP_V,
    max_excursion_z: float = QC_MAX_EXCURSION_Z,
    block_ms: float = QC_BLOCK_MS,
) -> dict[str, Any]:
    """Session-level summary of real behavioral coverage across every omission-carrying
    condition/slot cell (mirrors ``matched_empty``'s own event enumeration), for a session-level
    ``behavior_available`` gate.

    ``session_behavior_available`` is ``fraction_available >= min_session_frac``, and can return
    True or False for real inputs: it is now driven by the repaired per-trial conjunction rather
    than by a valid-fraction test that excluded no trial in the corpus. ``fail_reason_counts``
    reports how many trials failed on each named criterion, so a low fraction can be attributed
    rather than merely observed. ``criteria`` echoes the thresholds actually in force.
    """
    from .unit_classification import omission_events

    all_frames = []
    for cond, slot in omission_events():
        frame = trial_has_valid_behavior(source, condition=cond, slot_keys=None,
                                          alignment=alignment, min_valid_frac=min_valid_frac,
                                          correct_only=correct_only, max_jump_z=max_jump_z,
                                          abs_jump_v=abs_jump_v, max_excursion_z=max_excursion_z,
                                          block_ms=block_ms)
        if not frame.empty:
            frame = frame.copy()
            frame["condition"] = cond
            frame["omission_slot"] = slot
            all_frames.append(frame)
    criteria = {
        "min_valid_frac": min_valid_frac, "min_session_frac": min_session_frac,
        "block_ms": block_ms, "max_jump_z": max_jump_z, "abs_jump_v": abs_jump_v,
        "max_excursion_z": max_excursion_z, "rail_abs_v": RAIL_ABS_V,
    }
    if not all_frames:
        return {"n_trials": 0, "n_available": 0, "fraction_available": float("nan"),
                "session_behavior_available": False, "fail_reason_counts": {},
                "criteria": criteria}
    pooled = pd.concat(all_frames, ignore_index=True)
    n_trials = len(pooled)
    n_available = int(pooled["behavior_available"].sum())
    frac = n_available / n_trials if n_trials else float("nan")
    counts: dict[str, int] = {}
    for col, prefix in (("pupil_qc_fail_reasons", "pupil"), ("gaze_qc_fail_reasons", "gaze")):
        for cell in pooled[col].fillna(""):
            for reason in str(cell).split("|"):
                if reason:
                    counts[f"{prefix}:{reason}"] = counts.get(f"{prefix}:{reason}", 0) + 1
    return {
        "n_trials": n_trials,
        "n_available": n_available,
        "fraction_available": frac,
        "fail_reason_counts": counts,
        "criteria": criteria,
        # session-level gate: at least min_session_frac of trials must carry usable behavior for
        # the session to be treated as behavior_available in a matched_empty-style trial table.
        # Threshold is a stated, documented choice -- not derived -- consistent with
        # min_valid_frac's own per-trial default.
        "session_behavior_available": bool(frac >= min_session_frac),
    }


__all__ = [
    "BehavioralEpochBatch",
    "load_behavioral_epochs",
    "load_pupil_epochs",
    "load_gaze_epochs",
    "valid_fraction",
    "discontinuity_count",
    "robust_scale",
    "block_jump_diagnostics",
    "extract_pupil_features",
    "extract_gaze_features",
    "trial_has_valid_behavior",
    "session_behavior_coverage",
    "DEFAULT_WINDOW_MS_BY_ANCHOR",
    "CLIP_PROXIMITY_ABS",
    "RAIL_ABS_V",
    "ADC_FULL_SCALE_V",
    "ADC_QUANTIZATION_STEP_V",
    "QC_BLOCK_MS",
    "QC_MAX_JUMP_Z",
    "QC_ABS_JUMP_V",
    "QC_MAX_EXCURSION_Z",
    "QC_MIN_VALID_FRAC",
    "QC_MIN_SESSION_FRAC",
    "QC_MIN_TRIALS_FOR_RELATIVE_SCALE",
]
