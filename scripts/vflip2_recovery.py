"""vFLIP2 recovery on planted probes: a window-specific oracle, five runs and six measures.

    python scripts/vflip2_recovery.py [--n N] [--oracle-only] [--write] [--oracle-file PATH] [--verify]

Probes come from jnwb.testing.synth_vflip2_crossover; the contract is
artifacts/evidence/0.2.13/vflip2_generator_design.md. The oracle PSD is the mean of the estimator's
own front end over N one-second trials (two-second trials for the grid) from dedicated SeedSequence
children, for N in 200, 800 and 3200, as independent pairs A and B. Every window vflip2 visits gets its
crossovers recorded from the PSD. A window is defined unless every one of its rows is clipped at the
same weight bound; undefined windows carry null crossovers and enter no localization measure. The
frozen count is the smallest N at which the planted-band crossovers of A and B agree within one contact
in every defined window, at every depth. The picked-band crossovers are reported as uncertainty only.
A plain-numpy recomputation must reproduce every recorded crossover. If no count passes, the script
stops before any measured run.

--write freezes artifacts/evidence/0.2.13/vflip2_oracle.json (written once; a later run must reproduce
it exactly) and writes vflip2_recovery.md and vflip2_recovery.json. Without --write the same text is
printed. --n sets the probe count per run (default 100, the contract's value). A smoke run (n below
100) uses 200 trials only, prints only, and cannot be written.
"""

from __future__ import annotations

import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_var] = "1"

import argparse  # noqa: E402
import concurrent.futures as futures  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pathlib  # noqa: E402
import sys  # noqa: E402
from collections import Counter  # noqa: E402
from typing import Dict, List, Optional, Sequence, Tuple  # noqa: E402

import numpy as np  # noqa: E402
from scipy import signal, stats  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Under JNWB_EXPECTED_PACKAGE_ROOT (CI's installed-wheel leg) the checkout stays off the path,
# so the import below reaches the copy the variable names.
if not os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

import jnwb  # noqa: E402

_EXPECTED = pathlib.Path(os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") or ROOT).resolve()
if _EXPECTED not in pathlib.Path(jnwb.__file__).resolve().parents:
    raise SystemExit(f"jnwb was imported from {jnwb.__file__}, not from {_EXPECTED}; "
                     "run this script from its own repository")

from jnwb.laminar import _vflip2 as V  # noqa: E402
from jnwb.testing.synth import (  # noqa: E402
    VFLIP2_HIGH_BAND_HZ,
    VFLIP2_LOW_BAND_HZ,
    synth_vflip2_crossover,
)

N_CONTACTS = 32
PITCH_UM = 100.0
FS = 1000.0
N_SAMPLES = 5000          # five one-second trials per probe
GRID_SAMPLES = 10000      # five two-second trials per grid probe
GRID_NFFT = 2000          # two-second trials at 1 kHz: 0.5 Hz bins
GRID_CHUNK = 400          # trials per periodogram block (memory)
SNR = 4.0
Z0_FIRST, N_Z0 = 8, 16    # planted depths 8..23
ENTROPY = 0x1511
COUNTS = (200, 800, 3200)  # trials per oracle record
SMOKE_COUNTS = (200,)
KINDS = ("s1", "s2")       # s1: one-second trials; s2: two-second trials (grid run)
N_PROBES = 100
TOLERANCE_CONTACTS = 1
CLIP_LO, CLIP_HI = 0.05, 0.95
ORIENT_CODE = {"upright": 1, "inverted": -1}
PLANTED_ORIENTATION = 1   # the low band rises with contact index: upright
CHILD_CONTROL, CHILD_MEASURED, CHILD_GRID = 0, 16, 116
ORACLE_CHILD: Dict[Tuple[str, int, str], int] = {}
_next_child = 216
for _kind in KINDS:
    for _count in COUNTS:
        for _letter in ("A", "B"):
            ORACLE_CHILD[(_kind, _count, _letter)] = _next_child
            _next_child += 1
N_BACKGROUND_CHILDREN = _next_child  # 228: the background-on oracle and the measured runs
CONTROL_ORACLE_COUNT = 800            # one-second trials per background-off record
CONTROL_ORACLE_CHILD: Dict[Tuple[str, int], int] = {}
for _i, _z0 in enumerate(range(Z0_FIRST, Z0_FIRST + N_Z0)):
    for _j, _letter in enumerate(("A", "B")):
        CONTROL_ORACLE_CHILD[(_letter, _z0)] = N_BACKGROUND_CHILDREN + 2 * _i + _j
# Appended after the background-on children, so every earlier child index keeps its seed.
N_CHILDREN = N_BACKGROUND_CHILDREN + 2 * N_Z0  # 260
EVIDENCE = ROOT / "artifacts" / "evidence" / "0.2.13"
ORACLE_PATH = EVIDENCE / "vflip2_oracle.json"
MD_PATH = EVIDENCE / "vflip2_recovery.md"
JSON_PATH = EVIDENCE / "vflip2_recovery.json"


def children() -> list:
    """SeedSequence(ENTROPY).spawn(N_CHILDREN); child i has spawn_key (i,)."""
    return np.random.SeedSequence(ENTROPY).spawn(N_CHILDREN)


def z0_for(i: int) -> int:
    return Z0_FIRST + i % N_Z0


def needed_z0(n: int) -> List[int]:
    return sorted({Z0_FIRST + i % N_Z0 for i in range(n)}
                  | {Z0_FIRST + i for i in range(min(n, N_Z0))})


def _none(x) -> Optional[float]:
    """A float for JSON; None for None, NaN and infinities (omega is -inf when goodness is 0)."""
    if x is None or not math.isfinite(float(x)):
        return None
    return float(x)


def _num(x: float):
    return None if math.isinf(x) or math.isnan(x) else round(float(x), 6)


def _in_band(freqs: np.ndarray, band: Tuple[float, float]) -> np.ndarray:
    lo, hi = band
    return (freqs >= lo) & (freqs <= hi)


def window_defined(low_weight: np.ndarray, p: int, d: int) -> bool:
    """Defined unless every row of rows p..d (1-based) is clipped at the same bound."""
    w = low_weight[p - 1:d]
    return not (bool(np.all(w == CLIP_HI)) or bool(np.all(w == CLIP_LO)))


def low_weight_for(z0: int) -> np.ndarray:
    """The planted low-band weight at depth z0, from the generator's own rule (no draw depends on it)."""
    return synth_vflip2_crossover(N_CONTACTS, 64, FS, z0=z0, snr=SNR, rng=0).low_weight


def grid_psd(trials: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Hann periodograms of two-second trials, averaged over trials, on the 1..150 Hz 0.5 Hz grid.

    `trials` is (n_channels, n_trials, 2000). scipy's periodogram removes each trial's mean
    (detrend='constant'), as _psd_hanning does. Trials are processed in blocks to bound memory.
    """
    n_trials = trials.shape[1]
    total = None
    freqs = None
    for start in range(0, n_trials, GRID_CHUNK):
        f, pxx = signal.periodogram(trials[:, start:start + GRID_CHUNK], fs=FS, window="hann",
                                    nfft=GRID_NFFT, axis=-1)
        keep = (f >= 1.0 - 1e-9) & (f <= 150.0 + 1e-9)
        if freqs is None:
            freqs = f[keep]
            if not np.allclose(np.diff(freqs), 0.5):
                raise ValueError("the grid is not 0.5 Hz")
        part = pxx[..., keep].sum(axis=1)
        total = part if total is None else total + part
    return total / n_trials, freqs


# ---------------------------------------------------------------- estimator-helper window table

def window_table(psd: np.ndarray, freqs: np.ndarray, low_weight: np.ndarray) -> List[dict]:
    """Every window vflip2 visits (`_vflip2.py:324-327`), with the helpers of its loop (`:328-365`).

    Crossovers are 0-based absolute rows (vflip2's `crossover_channel`). They are NaN where the
    crossover is undefined or absent; in undefined windows both crossovers are null by rule.
    """
    n_rows = psd.shape[0]
    intdist = PITCH_UM / 1000.0
    step = V._matlab_round(0.1 / intdist)
    minrange = int(math.ceil(V.LAYER4_THICKNESS_MM / intdist))
    binsize = float(freqs[1] - freqs[0])
    low_planted = _in_band(freqs, VFLIP2_LOW_BAND_HZ)
    high_planted = _in_band(freqs, VFLIP2_HIGH_BAND_HZ)
    rows: List[dict] = []
    for p in range(1, n_rows - minrange + 2, step):
        for d in range(p + minrange, n_rows + 1, step):
            defined = window_defined(low_weight, p, d)
            with np.errstate(divide="ignore", invalid="ignore"):
                window = psd[p - 1:d]
                rel = window / window.max(axis=0)
                half = (d - p) // 2
                s1 = V._movmean5(rel[:half].mean(axis=0))
                s2 = V._movmean5(rel[-half:].mean(axis=0))
                deep, sup, orient = V._freqbands(freqs, s1, s2)
                planted_cross = V._crossover(rel[:, low_planted].mean(axis=1),
                                             rel[:, high_planted].mean(axis=1),
                                             p, PLANTED_ORIENTATION)
                row = {"p": p, "d": d, "defined": defined,
                       "z_planted": float(planted_cross) - 1.0 if defined else math.nan,
                       "z_picked": math.nan, "bands": None, "orient": 0, "omega": math.nan,
                       "good_no_omega": False, "good": False}
                if deep.size and sup.size:
                    lowband = rel[:, np.isin(freqs, deep)].mean(axis=1)
                    highband = rel[:, np.isin(freqs, sup)].mean(axis=1)
                    ps_dist = float(np.sqrt(np.sum((s1 - s2) ** 2)))
                    band_dist = float(np.sqrt(np.sum((lowband - highband) ** 2)))
                    goodness = V._goodness(lowband, highband)
                    ch_span = abs(p - d) * (intdist / 0.1)
                    f_span = deep.size * sup.size * binsize ** 2
                    omega = float(np.log(ps_dist * band_dist * abs(goodness) * ch_span * f_span))
                    cross = V._crossover(lowband, highband, p, orient)
                    high_peak = V._first_max(highband) + p
                    low_peak = V._first_max(lowband) + p
                    peaks = (V._peak_check(lowband, p, d, 1, n_rows, half)
                             and V._peak_check(highband, p, d, 1, n_rows, half))
                    between = (not np.isnan(cross)) and (
                        (low_peak < cross < high_peak) or (low_peak > cross > high_peak))
                    distinct = low_peak != cross and cross != high_peak and low_peak != high_peak
                    span = abs(high_peak - low_peak) >= minrange
                    good_no_omega = bool(peaks and between and distinct and span)
                    row.update(
                        z_picked=float(cross) - 1.0 if defined else math.nan,
                        bands=[float(deep[0]), float(deep[-1]), float(sup[0]), float(sup[-1])],
                        orient=int(orient), omega=omega, good_no_omega=good_no_omega,
                        good=bool(omega != 0 and good_no_omega))
            rows.append(row)
    return rows


def best_window(rows: List[dict]) -> Optional[int]:
    """vflip2's selection (`:366`): the first good window with the strictly largest omega."""
    best, best_omega = None, -math.inf
    for k, row in enumerate(rows):
        if row["good"] and row["omega"] > best_omega:
            best, best_omega = k, row["omega"]
    return best


def tie_count(rows: List[dict], best: Optional[int]) -> int:
    """Good windows whose omega equals the selected window's omega exactly."""
    if best is None:
        return 0
    omega = rows[best]["omega"]
    return sum(1 for r in rows if r["good"] and r["omega"] == omega)


def oracle_z(psd: np.ndarray, freqs: np.ndarray, p: int, d: int,
             low_hz: Sequence[float], high_hz: Sequence[float], orient: int) -> float:
    """0-based crossover of window (p, d) for the given bands and orientation, from one PSD."""
    with np.errstate(divide="ignore", invalid="ignore"):
        window = psd[p - 1:d]
        rel = window / window.max(axis=0)
        low = rel[:, _in_band(freqs, tuple(low_hz))].mean(axis=1)
        high = rel[:, _in_band(freqs, tuple(high_hz))].mean(axis=1)
        return float(V._crossover(low, high, p, orient)) - 1.0


# ---------------------------------------------------------------- plain-numpy recomputation

def _plain_movmean5(x: np.ndarray) -> np.ndarray:
    n = x.size
    out = np.full(n, math.nan)
    for i in range(n):
        vals = [x[k] for k in range(max(0, i - 2), min(n, i + 3)) if not np.isnan(x[k])]
        if vals:
            out[i] = np.mean(np.asarray(vals))
    return out


def _plain_runs(mask: np.ndarray) -> List[int]:
    """Indices of the first longest run of True."""
    best: List[int] = []
    k, n = 0, mask.size
    while k < n:
        if mask[k]:
            j = k
            while j + 1 < n and mask[j + 1]:
                j += 1
            if j - k + 1 > len(best):
                best = list(range(k, j + 1))
            k = j + 1
        else:
            k += 1
    return best


def _plain_bands(freqs: np.ndarray, s1: np.ndarray, s2: np.ndarray):
    low = (freqs > 4) & (freqs < 70)
    high = (freqs > 40) & (freqs < 150)
    run1 = _plain_runs((s1 > s2) & low)
    run2 = _plain_runs((s1 < s2) & low)
    deep: List[float] = []
    sup: List[float] = []
    orient = 0
    ind_high = None
    if len(run1) >= 5 and len(run2) >= 5:
        if freqs[run1].min() < freqs[run2].min():
            deep, orient, ind_high = list(freqs[run1]), -1, (s1 < s2) & high
        else:
            deep, orient, ind_high = list(freqs[run2]), 1, (s1 > s2) & high
    elif len(run1) >= 5:
        deep, orient, ind_high = list(freqs[run1]), -1, (s1 < s2) & high
    elif len(run2) >= 5:
        deep, orient, ind_high = list(freqs[run2]), 1, (s1 > s2) & high
    if orient != 0:
        sup_run = _plain_runs(ind_high)
        sup = list(freqs[sup_run]) if sup_run else []
        if len(sup) < 20 or sup[-1] < 70:
            sup = []
    return deep, sup, orient


def _plain_peak_ok(band: np.ndarray, proximal: int, distal: int, startrow: int, endrow: int,
                   half: int) -> bool:
    n = band.size
    top = max(v for v in band if not np.isnan(v))
    locs = [k + 1 for k in range(n) if band[k] == top]
    peak = max(locs) if sum(locs) / len(locs) > n / 2 else min(locs)
    q = peak - 1
    if peak == 1:
        ok = proximal == startrow and band[0] > band[1]
    elif peak == n:
        ok = distal == endrow and band[n - 1] > band[n - 2]
    else:
        ok = band[q] > band[q + 1] and band[q] > band[q - 1]
    idx = min(k for k in range(n) if band[k] == top) + 1
    return bool(ok and (idx <= half or idx >= n - (half - 1)))


def _plain_crossover(low: np.ndarray, high: np.ndarray, proximal: int, orientation: int) -> float:
    """0-based absolute row where the band profiles cross, or NaN; a plain transcription."""
    diff = np.abs(high - low)
    n = low.size

    def cross(i, b1, b2):  # i is 1-based, as in vFLIP2.m
        if b1[i - 1] > b2[i - 1] and b2[i] > b1[i]:
            return i if abs(diff[i - 1]) <= abs(diff[i]) else i + 1
        if b1[i - 1] > b2[i - 1] and b1[i] == b2[i] and b2[i + 1] > b1[i + 1]:
            return i + 1
        return None

    found = []
    for i in range(1, n - 1):
        c = cross(i, high, low) if orientation > 0 else cross(i, low, high)
        if c is not None:
            found.append(c)
    if not found:
        return math.nan
    if len(found) == 1:
        chosen = found[0]
    else:
        ratings = [diff[:c].sum() - diff[c - 1:].sum() for c in found]
        chosen = found[int(np.argmax(ratings))]
    return float(chosen + proximal - 1) - 1.0


def _plain_band_regress(band: np.ndarray) -> Tuple[float, float, float]:
    """(slope at the midpoint, R-squared, p) of a quadratic fit of the band on contacts 1..n."""
    n_all = band.size
    x = np.arange(1, n_all + 1, dtype=float)
    design = np.column_stack((x ** 2, x, np.ones(n_all)))
    keep = ~np.isnan(band)
    y, design = band[keep], design[keep]
    n = y.size
    coef = np.linalg.lstsq(design, y, rcond=None)[0]
    rank = int(np.linalg.matrix_rank(design))
    fitted = design @ coef
    sse = float(np.sum((y - fitted) ** 2))
    tss = float(np.sum((y - y.mean()) ** 2))
    rss = float(np.sum((fitted - y.mean()) ** 2))
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = 1.0 - sse / tss if tss else (np.nan if sse == 0 else -np.inf)
        nu = max(0, n - rank)
        s2 = sse / nu if nu else np.nan
        f = (rss / (rank - 1)) / s2 if rank > 1 else np.nan
    p = float(stats.f.sf(f, rank - 1, nu)) if np.isfinite(f) and nu > 0 else np.nan
    midpoint = int(math.floor(n_all / 2 + 0.5))
    slope = 2 * coef[0] * midpoint + coef[1]
    return float(slope), float(r2), p


def _plain_goodness(lowband: np.ndarray, highband: np.ndarray) -> float:
    """The goodness of a deep and a superficial band: R-squared products, signed by the two slopes,
    zero unless both quadratic fits are significant at 0.05."""
    low_slope, low_r2, low_p = _plain_band_regress(lowband)
    high_slope, high_r2, high_p = _plain_band_regress(highband)
    significant = bool(low_p < 0.05 and high_p < 0.05)
    if low_slope > 0 and high_slope < 0:
        sign = 1
    elif low_slope < 0 and high_slope > 0:
        sign = -1
    else:
        sign = 0
    return high_r2 * low_r2 * significant * sign


def plain_rows(psd: np.ndarray, freqs: np.ndarray, low_weight: np.ndarray) -> List[dict]:
    """The window table from plain numpy only: no helper of _vflip2 is called."""
    n_rows = psd.shape[0]
    intdist = PITCH_UM / 1000.0
    step = int(math.floor(abs(0.1 / intdist) + 0.5))
    minrange = int(math.ceil(V.LAYER4_THICKNESS_MM / intdist))
    binsize = float(freqs[1] - freqs[0])
    low_planted = _in_band(freqs, VFLIP2_LOW_BAND_HZ)
    high_planted = _in_band(freqs, VFLIP2_HIGH_BAND_HZ)
    rows: List[dict] = []
    for p in range(1, n_rows - minrange + 2, step):
        for d in range(p + minrange, n_rows + 1, step):
            defined = window_defined(low_weight, p, d)
            with np.errstate(divide="ignore", invalid="ignore"):
                window = psd[p - 1:d]
                rel = window / window.max(axis=0)
                half = (d - p) // 2
                s1 = _plain_movmean5(rel[:half].mean(axis=0))
                s2 = _plain_movmean5(rel[-half:].mean(axis=0))
                deep, sup, orient = _plain_bands(freqs, s1, s2)
                planted_cross = _plain_crossover(rel[:, low_planted].mean(axis=1),
                                                 rel[:, high_planted].mean(axis=1), p,
                                                 PLANTED_ORIENTATION)
                row = {"p": p, "d": d, "defined": defined,
                       "z_planted": planted_cross if defined else math.nan,
                       "z_picked": math.nan, "bands": None, "orient": 0, "omega": math.nan,
                       "good_no_omega": False, "good": False}
                if len(deep) and len(sup):
                    low = rel[:, np.isin(freqs, deep)].mean(axis=1)
                    high = rel[:, np.isin(freqs, sup)].mean(axis=1)
                    cross = _plain_crossover(low, high, p, orient)
                    low_peak = int(np.argmax(low)) + p
                    high_peak = int(np.argmax(high)) + p
                    peaks = (_plain_peak_ok(low, p, d, 1, n_rows, half)
                             and _plain_peak_ok(high, p, d, 1, n_rows, half))
                    cross_row = cross + 1.0
                    between = (not math.isnan(cross)) and (
                        (low_peak < cross_row < high_peak) or (low_peak > cross_row > high_peak))
                    distinct = (low_peak != cross_row and cross_row != high_peak
                                and low_peak != high_peak)
                    span = abs(high_peak - low_peak) >= minrange
                    good_no_omega = bool(peaks and between and distinct and span)
                    ps_dist = float(np.sqrt(np.sum((s1 - s2) ** 2)))
                    band_dist = float(np.sqrt(np.sum((low - high) ** 2)))
                    goodness = _plain_goodness(low, high)
                    ch_span = abs(p - d) * (intdist / 0.1)
                    f_span = len(deep) * len(sup) * binsize ** 2
                    with np.errstate(divide="ignore", invalid="ignore"):
                        omega = float(np.log(ps_dist * band_dist * abs(goodness) * ch_span * f_span))
                    row.update(
                        z_picked=cross if defined else math.nan,
                        bands=[float(deep[0]), float(deep[-1]), float(sup[0]), float(sup[-1])],
                        orient=int(orient), omega=omega, good_no_omega=good_no_omega,
                        good=bool(omega != 0 and good_no_omega))
            rows.append(row)
    return rows


def _same(x: float, y: float) -> bool:
    if math.isnan(x) or math.isnan(y):
        return math.isnan(x) and math.isnan(y)
    return x == y


def _same_bands(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return all(_same(u, v) for u, v in zip(a, b))


def compare_rows(helper: List[dict], plain: List[dict]) -> List[tuple]:
    """Windows where the helper table and the plain table disagree (empty when they agree)."""
    mismatches: List[tuple] = []
    if len(helper) != len(plain):
        mismatches.append(("count", len(helper), len(plain)))
    for h, q in zip(helper, plain):
        ok = ((h["p"], h["d"]) == (q["p"], q["d"])
              and h["defined"] == q["defined"]
              and _same(h["z_planted"], q["z_planted"])
              and _same(h["z_picked"], q["z_picked"])
              and _same_bands(h["bands"], q["bands"])
              and h["orient"] == q["orient"]
              and _same(h["omega"], q["omega"])
              and h["good_no_omega"] == q["good_no_omega"]
              and h["good"] == q["good"])
        if not ok:
            mismatches.append((h["p"], h["d"]))
    return mismatches


def _diff(x: float, y: float) -> float:
    """|x - y| in contacts; 0 when both are NaN, infinity when only one is."""
    if math.isnan(x) and math.isnan(y):
        return 0.0
    if math.isnan(x) or math.isnan(y):
        return math.inf
    return abs(x - y)


def choose_count(passes: Dict[int, bool], counts: Sequence[int]) -> Optional[int]:
    """The smallest trial count at which the planted-band check passes, or None."""
    for count in sorted(counts):
        if passes.get(count):
            return count
    return None


# ---------------------------------------------------------------- workers

def oracle_job(job):
    """One oracle record: (kind, trial count, pair letter, depth, child index, child)."""
    kind, count, letter, z0, child_index, child = job
    per_trial = 2000 if kind == "s2" else 1000
    rec = synth_vflip2_crossover(N_CONTACTS, count * per_trial, FS, z0=z0, snr=SNR,
                                 rng=np.random.default_rng(child))
    trials = rec.lfp.reshape(N_CONTACTS, count, per_trial)
    if kind == "s2":
        psd, freqs = grid_psd(trials)
    else:
        psd = V._psd_hanning(trials.transpose(0, 2, 1), FS)
        freqs = np.arange(1, psd.shape[1] + 1, dtype=float)
    w = rec.low_weight
    rows = window_table(psd, freqs, w)
    plain = plain_rows(psd, freqs, w)
    out = {"kind": kind, "count": count, "letter": letter, "z0": z0, "child": child_index,
           "psd": psd, "freqs": freqs, "rows": rows,
           "plain_mismatches": compare_rows(rows, plain),
           "rows_reversed": window_table(psd[::-1], freqs, w[::-1])}
    return out


def control_oracle_job(job):
    """One background-off oracle record at one depth: (pair letter, depth, child index, child)."""
    letter, z0, child_index, child = job
    per_trial = 1000
    rec = synth_vflip2_crossover(N_CONTACTS, CONTROL_ORACLE_COUNT * per_trial, FS, z0=z0, snr=SNR,
                                 background=False, rng=np.random.default_rng(child))
    trials = rec.lfp.reshape(N_CONTACTS, CONTROL_ORACLE_COUNT, per_trial)
    psd = V._psd_hanning(trials.transpose(0, 2, 1), FS)
    freqs = np.arange(1, psd.shape[1] + 1, dtype=float)
    rows = window_table(psd, freqs, rec.low_weight)
    return {"letter": letter, "z0": z0, "child": child_index, "psd": psd, "freqs": freqs, "rows": rows,
            "plain_mismatches": compare_rows(rows, plain_rows(psd, freqs, rec.low_weight))}


def probe_job(job):
    """One probe through the estimator: kind, index, depth, child index and SeedSequence child."""
    kind, index, z0, child_index, child = job
    rng = np.random.default_rng(child)
    table = False
    if kind == "grid":
        rec = synth_vflip2_crossover(N_CONTACTS, GRID_SAMPLES, FS, z0=z0, snr=SNR, rng=rng)
        psd, freqs = grid_psd(rec.lfp.reshape(N_CONTACTS, GRID_SAMPLES // 2000, 2000))
        result = jnwb.vflip2(psd, freqs, contact_spacing=PITCH_UM)
        table = True
        weights = rec.low_weight
    else:
        snr = 0.0 if kind == "null" else SNR
        rec = synth_vflip2_crossover(N_CONTACTS, N_SAMPLES, FS, z0=z0, snr=snr,
                                     background=kind != "noiseless", rng=rng)
        lfp = rec.lfp[::-1] if kind == "reversal" else rec.lfp
        weights = rec.low_weight[::-1] if kind == "reversal" else rec.low_weight
        result = jnwb.vflip2_from_lfp(lfp, FS, contact_spacing=PITCH_UM)
        if kind in ("primary", "reversal", "noiseless"):
            psd = V._psd_hanning(lfp.reshape(N_CONTACTS, N_SAMPLES // 1000, 1000).transpose(0, 2, 1),
                                 FS)
            freqs = np.arange(1, psd.shape[1] + 1, dtype=float)
        if kind in ("primary", "reversal"):
            table = True
    out = {
        "kind": kind, "index": index, "z0": z0, "child": child_index,
        "accepted": bool(result.accepted),
        "omega": _none(result.omega),
        "window": None if result.proximal_channel is None
        else [int(result.proximal_channel), int(result.distal_channel)],
        "zhat": _none(result.crossover_channel),
        "orientation": result.orientation,
        "low_hz": None if result.low_band_hz is None else [float(v) for v in result.low_band_hz],
        "high_hz": None if result.high_band_hz is None else [float(v) for v in result.high_band_hz],
    }
    if table:
        rows = window_table(psd, freqs, weights)
        best = best_window(rows)
        out["n_ties"] = tie_count(rows, best)
        out["table_agrees"] = _table_agrees(rows, best, result)
    if kind == "noiseless":
        # The control's own estimand: the crossover of this probe's own PSD in the window vflip2 chose.
        out["defined"] = None
        out["own_zstar"] = None
        if result.accepted:
            p, d = result.proximal_channel + 1, result.distal_channel + 1
            out["defined"] = window_defined(weights, p, d)
            if out["defined"]:
                out["own_zstar"] = _none(oracle_z(psd, freqs, p, d, result.low_band_hz,
                                                  result.high_band_hz,
                                                  ORIENT_CODE[result.orientation]))
    return out


def _table_agrees(rows: List[dict], best: Optional[int], result) -> bool:
    if best is None:
        return result.omega is None
    row = rows[best]
    return (result.omega is not None
            and row["p"] - 1 == result.proximal_channel
            and row["d"] - 1 == result.distal_channel
            and math.isclose(row["omega"], result.omega, rel_tol=1e-12, abs_tol=0.0))


# ---------------------------------------------------------------- oracle stage

def indeterminate_windows(rows_a: List[dict], rows_b: List[dict]) -> set:
    """(p, d) of the defined windows where exactly one oracle of a pair finds a planted crossover."""
    return {(ra["p"], ra["d"]) for ra, rb in zip(rows_a, rows_b)
            if ra["defined"] and math.isnan(ra["z_planted"]) != math.isnan(rb["z_planted"])}


def look_for(tables: Dict[tuple, dict], kind: str, count: int, z0: int) -> dict:
    """The A record at one depth, with its windows that are indeterminate in either frame."""
    a = tables[(kind, count, "A", z0)]
    b = tables[(kind, count, "B", z0)]
    return dict(a, indeterminate=indeterminate_windows(a["rows"], b["rows"]),
                indeterminate_reversed=indeterminate_windows(a["rows_reversed"], b["rows_reversed"]))


def pair_stats(kind: str, count: int, z0s: List[int], tables: Dict[tuple, dict]) -> dict:
    """The disagreement between the A and B records at one count, over all depths.

    Gated: a defined window where both oracles find a planted crossover must agree within one
    contact. Indeterminate: a defined window where exactly one finds one (ruled; not gated).
    Uncertainty only: the picked crossovers, the picked bands and their edge shifts.
    """
    n_windows = n_defined = n_indet = planted_bad = planted_nan_both = picked_bad = 0
    bands_mismatch = bands_mismatch_defined = plain_mismatch = 0
    planted_max = picked_max = 0.0
    edge_shifts: List[float] = []
    per_z0 = {}
    for z0 in z0s:
        a = tables[(kind, count, "A", z0)]
        b = tables[(kind, count, "B", z0)]
        plain_mismatch += len(a["plain_mismatches"]) + len(b["plain_mismatches"])
        bad_here = 0
        for ra, rb in zip(a["rows"], b["rows"]):
            n_windows += 1
            same_bands = _same_bands(ra["bands"], rb["bands"])
            if not same_bands:
                bands_mismatch += 1
            if ra["bands"] is not None and rb["bands"] is not None:
                edge_shifts.extend(abs(u - v) for u, v in zip(ra["bands"], rb["bands"]))
            if not ra["defined"]:
                continue
            n_defined += 1
            if not same_bands:
                bands_mismatch_defined += 1
            na, nb = math.isnan(ra["z_planted"]), math.isnan(rb["z_planted"])
            if na != nb:
                n_indet += 1
            elif na:
                planted_nan_both += 1
            else:
                dp = abs(ra["z_planted"] - rb["z_planted"])
                planted_max = max(planted_max, dp)
                if dp > TOLERANCE_CONTACTS:
                    planted_bad += 1
                    bad_here += 1
            dk = _diff(ra["z_picked"], rb["z_picked"])
            if dk > TOLERANCE_CONTACTS:
                picked_bad += 1
            if math.isfinite(dk):
                picked_max = max(picked_max, dk)
        per_z0[str(z0)] = bad_here
    shifts = np.asarray(edge_shifts, dtype=float)
    return {"kind": kind, "count": count, "n_windows": n_windows, "n_defined": n_defined,
            "indeterminate": n_indet, "planted_bad": planted_bad, "planted_max": _num(planted_max),
            "planted_nan_both": planted_nan_both, "picked_bad": picked_bad,
            "picked_max": _num(picked_max), "bands_mismatch": bands_mismatch,
            "bands_mismatch_defined": bands_mismatch_defined,
            "edge_shift_edges": int(shifts.size),
            "edge_shift_median_hz": _num(float(np.median(shifts))) if shifts.size else None,
            "edge_shift_max_hz": _num(float(shifts.max())) if shifts.size else None,
            "plain_mismatches": plain_mismatch, "passes": planted_bad == 0 and plain_mismatch == 0,
            "planted_bad_per_depth": per_z0}


def build_oracle(z0s: List[int], counts: Sequence[int], pool):
    kids = children()
    jobs = [(kind, count, letter, z0, ORACLE_CHILD[(kind, count, letter)],
             kids[ORACLE_CHILD[(kind, count, letter)]])
            for kind in KINDS for count in counts for letter in ("A", "B") for z0 in z0s]
    results = list(pool.map(oracle_job, jobs))
    tables = {(r["kind"], r["count"], r["letter"], r["z0"]): r for r in results}
    stats = {(kind, count): pair_stats(kind, count, z0s, tables)
             for kind in KINDS for count in counts}
    return stats, tables


def build_control_oracle(pool):
    """The background-off control oracle: an A/B pair of CONTROL_ORACLE_COUNT records at each depth,
    gated with the same rule as the background-on oracle (`pair_stats`)."""
    kids = children()
    z0s = list(range(Z0_FIRST, Z0_FIRST + N_Z0))
    jobs = [(letter, z0, CONTROL_ORACLE_CHILD[(letter, z0)], kids[CONTROL_ORACLE_CHILD[(letter, z0)]])
            for z0 in z0s for letter in ("A", "B")]
    results = list(pool.map(control_oracle_job, jobs))
    tables = {("ctrl", CONTROL_ORACLE_COUNT, r["letter"], r["z0"]): r for r in results}
    return pair_stats("ctrl", CONTROL_ORACLE_COUNT, z0s, tables), tables


def _stats_line(s: dict) -> str:
    return (f"{s['kind']}, {s['count']} trials: defined windows {s['n_defined']} of {s['n_windows']} "
            f"(all depths); indeterminate {s['indeterminate']}; planted beyond 1 contact where both find a "
            f"crossover {s['planted_bad']} (max {s['planted_max']}, both no crossover "
            f"{s['planted_nan_both']}); picked beyond 1 contact {s['picked_bad']} (max {s['picked_max']}); "
            f"picked bands differ {s['bands_mismatch']} (defined {s['bands_mismatch_defined']}); edge shift "
            f"median {s['edge_shift_median_hz']} Hz, max {s['edge_shift_max_hz']} Hz; plain mismatches "
            f"{s['plain_mismatches']}; planted gate {'passes' if s['passes'] else 'fails'}")


# ---------------------------------------------------------------- probes and measures

def plan_jobs(n: int) -> dict:
    kids = children()
    n_control = min(n, N_Z0)
    control = [("noiseless", i, Z0_FIRST + i, CHILD_CONTROL + i, kids[CHILD_CONTROL + i])
               for i in range(n_control)]
    primary = [("primary", i, z0_for(i), CHILD_MEASURED + i, kids[CHILD_MEASURED + i])
               for i in range(n)]
    null = [("null", i, z0_for(i), CHILD_MEASURED + i, kids[CHILD_MEASURED + i]) for i in range(n)]
    reversal = [("reversal", i, z0_for(i), CHILD_MEASURED + i, kids[CHILD_MEASURED + i])
                for i in range(n)]
    grid = [("grid", i, z0_for(i), CHILD_GRID + i, kids[CHILD_GRID + i]) for i in range(n)]
    return {"control": control, "primary": primary, "null": null, "reversal": reversal,
            "grid": grid}


def _ci(k: int, n: int):
    if n == 0:
        return None
    lo, hi = jnwb.clopper_pearson(k, n)
    return [round(float(lo), 4), round(float(hi), 4)]


def score_run(outs: List[dict], look: Dict[int, dict], reverse: bool = False) -> List[dict]:
    """Per-probe scoring against the frozen oracle of the probe's own depth."""
    scored = []
    for o in outs:
        z_ref = N_CONTACTS - 1 - o["z0"] if reverse else o["z0"]
        rec = {"index": o["index"], "z0": o["z0"], "z_ref": z_ref, "child": o["child"],
               "accepted": o["accepted"], "window": o["window"], "zhat": o["zhat"],
               "orientation": o["orientation"], "defined": None, "indeterminate": None,
               "status": None, "zstar": None, "zstar_own": None, "within_picked": False,
               "within_own": False, "edge_shift": None, "err_planted": None}
        if o["accepted"] and o["window"] is not None:
            e = look[o["z0"]]
            psd = e["psd"][::-1] if reverse else e["psd"]
            rows = e["rows_reversed"] if reverse else e["rows"]
            freqs = e["freqs"]
            p, d = o["window"][0] + 1, o["window"][1] + 1
            own = next(r for r in rows if r["p"] == p and r["d"] == d)
            rec["defined"] = bool(own["defined"])
            rec["indeterminate"] = (p, d) in (e["indeterminate_reversed"] if reverse
                                              else e["indeterminate"])
            rec["err_planted"] = int(round(abs(o["zhat"] - z_ref)))
            rec["status"] = ("undefined" if not rec["defined"]
                             else "indeterminate" if rec["indeterminate"] else "scored")
            if rec["status"] == "scored":
                zstar = oracle_z(psd, freqs, p, d, o["low_hz"], o["high_hz"],
                                 ORIENT_CODE[o["orientation"]])
                rec["zstar"] = _none(zstar)
                rec["zstar_own"] = _none(own["z_picked"])
                rec["within_picked"] = bool(abs(o["zhat"] - zstar) <= TOLERANCE_CONTACTS)
                rec["within_own"] = bool(not math.isnan(own["z_picked"])
                                         and abs(o["zhat"] - own["z_picked"]) <= TOLERANCE_CONTACTS)
                if own["bands"] is not None and o["low_hz"] is not None:
                    # Largest shift of the four band edges (Hz) from the oracle's own bands.
                    rec["edge_shift"] = max(abs(u - v)
                                            for u, v in zip(o["low_hz"] + o["high_hz"], own["bands"]))
        scored.append(rec)
    return scored


def _edge_block(shifts: List[float]) -> dict:
    """Band-edge shifts (Hz) of the scored probes: median and max, and the count with every edge
    within 1 Hz."""
    within = sum(v <= 1.0 for v in shifts)
    return {"n": len(shifts),
            "median_hz": _num(float(np.median(shifts))) if shifts else None,
            "max_hz": _num(float(max(shifts))) if shifts else None,
            "within_1hz": {"k": within, "n": len(shifts), "ci95": _ci(within, len(shifts))}}


def score_control(outs: List[dict], ctrl: Dict[int, dict]) -> List[dict]:
    """Noiseless probes scored against the background-off oracle's planted-band crossover of the
    selected window. Scored: defined, determinate (both oracles find one or neither), and a crossover."""
    scored = []
    for o in outs:
        rec = {"index": o["index"], "z0": o["z0"], "accepted": o["accepted"], "window": o["window"],
               "zhat": o["zhat"], "status": None, "zstar": None, "within": False}
        if o["accepted"] and o["window"] is not None:
            c = ctrl[o["z0"]]
            p, d = o["window"][0] + 1, o["window"][1] + 1
            row = next(r for r in c["rows"] if r["p"] == p and r["d"] == d)
            if not row["defined"]:
                rec["status"] = "undefined"
            elif (p, d) in c["indeterminate"]:
                rec["status"] = "indeterminate"
            elif math.isnan(row["z_planted"]):
                rec["status"] = "no_crossover"
            else:
                rec["status"] = "scored"
                rec["zstar"] = row["z_planted"]
                rec["within"] = bool(abs(o["zhat"] - row["z_planted"]) <= TOLERANCE_CONTACTS)
        scored.append(rec)
    return scored


def _control_block(sc: List[dict]) -> dict:
    acc = [s for s in sc if s["accepted"]]
    scored = [s for s in acc if s["status"] == "scored"]
    k = sum(s["within"] for s in scored)
    return {"n": len(sc), "accepted": len(acc),
            "undefined": sum(s["status"] == "undefined" for s in acc),
            "indeterminate": sum(s["status"] == "indeterminate" for s in acc),
            "no_crossover": sum(s["status"] == "no_crossover" for s in acc),
            "scored": len(scored), "within_one_contact": k, "ci95": _ci(k, len(scored)),
            # Misses beyond one contact: the estimate minus the background-off crossover, in contacts.
            "misses": [{"z0": s["z0"], "diff_contacts": int(round(s["zhat"] - s["zstar"]))}
                       for s in scored if not s["within"]]}


def _block(sc: List[dict], n_runs: int) -> dict:
    acc = [s for s in sc if s["accepted"]]
    acc_def = [s for s in acc if s["status"] == "scored"]
    n_undef = sum(s["status"] == "undefined" for s in acc)
    n_indet = sum(s["status"] == "indeterminate" for s in acc)
    k1 = len(acc)
    k2 = sum(s["within_picked"] for s in acc_def)
    k2_own = sum(s["within_own"] for s in acc_def)
    shifts = [s["edge_shift"] for s in acc_def if s["edge_shift"] is not None]
    k3 = sum(bool(s["status"] == "scored" and s["within_picked"]) for s in sc)
    hist = Counter(s["err_planted"] for s in acc)
    with_window = [s for s in sc if s["window"] is not None]
    inside = sum(s["window"][0] <= s["z_ref"] <= s["window"][1] for s in with_window)
    wins = Counter(tuple(s["window"]) for s in with_window)
    return {
        "1_detection": {"k": k1, "n": n_runs, "ci95": _ci(k1, n_runs)},
        "2_conditional_localization": {
            "k": k2, "n": len(acc_def), "ci95": _ci(k2, len(acc_def)),
            "with_own_bands": {"k": k2_own, "n": len(acc_def), "ci95": _ci(k2_own, len(acc_def))},
            "band_edge_shift": _edge_block(shifts),
            "accepted_undefined_window": n_undef, "accepted_indeterminate_oracle": n_indet},
        "3_unconditional_recovery": {"k": k3, "n": n_runs, "ci95": _ci(k3, n_runs),
                                     "accepted_undefined_window": n_undef,
                                     "accepted_indeterminate_oracle": n_indet},
        "4_error_histogram": {str(key): int(hist[key]) for key in sorted(hist)},
        "5_window_selection": {
            "n_with_window": len(with_window), "z0_inside": inside,
            "distinct_windows": len(wins),
            "most_common": [[list(w), int(c)] for w, c in wins.most_common(3)]},
    }


def run_measures(outs: Dict[str, List[dict]], looks: Dict[str, Dict[int, dict]], n: int,
                 ctrl: Dict[int, dict]) -> dict:
    primary, null, reversal, grid, control = (outs["primary"], outs["null"], outs["reversal"],
                                              outs["grid"], outs["control"])
    prim = _block(score_run(primary, looks["s1"]), n)
    prim["3_unconditional_recovery"]["target"] = "at least 90 of 100 (descriptive)"
    prim["3_unconditional_recovery"]["target_met"] = (
        bool(prim["3_unconditional_recovery"]["k"] >= 90) if n == N_PROBES else None)
    k_null = sum(o["accepted"] for o in null)
    null_block = {"k": k_null, "n": len(null), "ci95": _ci(k_null, len(null)),
                  "target": "at most 5 of 100 (descriptive)",
                  "target_met": bool(k_null <= 5) if len(null) == N_PROBES else None}
    rev = _block(score_run(reversal, looks["s1"], reverse=True), len(reversal))
    rev_both = [(a, b) for a, b in zip(primary, reversal) if a["accepted"] and b["accepted"]]
    mirror = sum(b["window"][0] == N_CONTACTS - 1 - a["window"][1]
                 and b["window"][1] == N_CONTACTS - 1 - a["window"][0] for a, b in rev_both)
    flipped = sum(b["orientation"] != a["orientation"] for a, b in rev_both)
    ties_p = sum(o.get("n_ties", 0) >= 2 for o in primary if o["accepted"])
    ties_r = sum(o.get("n_ties", 0) >= 2 for o in reversal if o["accepted"])
    grd = _block(score_run(grid, looks["s2"]), len(grid))
    sc_c = score_run(control, looks["s1"])
    c_acc = [s for s in sc_c if s["accepted"]]
    c_def = [s for s in c_acc if s["status"] == "scored"]
    c_within = sum(s["within_picked"] for s in c_def)
    bg_off = _control_block(score_control(control, ctrl))
    tables_ok = all(o.get("table_agrees", True) for o in primary + reversal + grid)
    return {
        "primary": prim,
        "null": {"6_null_acceptance": null_block},
        "reversal": {"block": rev,
                     "mirror": {"k": mirror, "n": len(rev_both), "ci95": _ci(mirror, len(rev_both))},
                     "orientation_flipped": {"k": flipped, "n": len(rev_both),
                                             "ci95": _ci(flipped, len(rev_both))},
                     "ties_primary": {"k": ties_p, "n": sum(o["accepted"] for o in primary)},
                     "ties_reversal": {"k": ties_r, "n": sum(o["accepted"] for o in reversal)}},
        "grid": grd,
        "control": {"background_off": bg_off,
                    "model_mismatch_background_on": {"n": len(control), "accepted": len(c_acc),
                                                     "scored": len(c_def),
                                                     "within_one_contact": c_within,
                                                     "ci95": _ci(c_within, len(c_def))}},
        "estimator_agrees_with_table": tables_ok,
    }


# ---------------------------------------------------------------- output

def render(n: int, measures: dict, stats: dict, chosen: dict, counts, smoke: bool,
           pool_ok: bool, jobs_info: str) -> str:
    prim, nul, rev = measures["primary"], measures["null"], measures["reversal"]
    grd, ctl = measures["grid"], measures["control"]
    p1, p2, p3 = prim["1_detection"], prim["2_conditional_localization"], prim["3_unconditional_recovery"]
    p4, p5 = prim["4_error_histogram"], prim["5_window_selection"]
    p6 = nul["6_null_acceptance"]
    be = p2["band_edge_shift"]
    bo = ctl["background_off"]
    bo_block = {"k": bo["within_one_contact"], "n": bo["scored"], "ci95": bo["ci95"]}
    mm = ctl["model_mismatch_background_on"]
    mm_block = {"k": mm["within_one_contact"], "n": mm["scored"], "ci95": mm["ci95"]}
    miss_list = ", ".join(f"z0 {m['z0']} {m['diff_contacts']:+d}" for m in bo["misses"]) or "none"
    miss_sizes = ", ".join(f"{size} contacts: {count}" for size, count
                           in sorted(Counter(abs(m["diff_contacts"]) for m in bo["misses"]).items())) or "none"

    def fmt(block: dict) -> str:
        ci = block.get("ci95")
        ci_s = "none" if ci is None else f"[{ci[0]}, {ci[1]}]"
        return f"{block['k']} of {block['n']}, 95% CI {ci_s}"

    def met(flag) -> str:
        return "not applicable (smoke run)" if flag is None else ("met" if flag else "missed")

    oracle_rows = []
    for kind in KINDS:
        for count in counts:
            s = stats[(kind, count)]
            oracle_rows.append(f"| {kind} | {count} | {s['indeterminate']} | {s['planted_bad']} | "
                               f"{s['planted_max']} | {s['picked_bad']} | {s['picked_max']} | "
                               f"{s['bands_mismatch']} | {s['edge_shift_median_hz']} | "
                               f"{s['edge_shift_max_hz']} | {'yes' if s['passes'] else 'no'} |")
    cp = measures["control"]["pair"]
    oracle_rows.append(f"| control, background off | {cp['count']} | {cp['indeterminate']} | "
                       f"{cp['planted_bad']} | {cp['planted_max']} | {cp['picked_bad']} | "
                       f"{cp['picked_max']} | {cp['bands_mismatch']} | {cp['edge_shift_median_hz']} | "
                       f"{cp['edge_shift_max_hz']} | {'yes' if cp['passes'] else 'no'} |")
    lines = [
        "# vFLIP2 recovery on planted probes (0.2.13, item 15-11)",
        "",
        "Written by `python scripts/vflip2_recovery.py --write`. Every number is computed by that script.",
        "",
        f"- Probes per run: {n}. Noiseless control: {min(n, N_Z0)} (one per depth).",
        f"- Frozen oracle trial counts: one-second {chosen['s1']}, two-second grid {chosen['s2']}"
        + (" (smoke run: not a passing count)" if smoke else "") + ".",
        "- Oracle disagreement between independent pairs A and B. Gated: defined windows where both find a "
        "planted crossover. Indeterminate: exactly one finds one (null, no localization measure). Picked "
        "bands, picked crossovers and edge shifts (Hz, windows where both have bands): uncertainty only.",
        "",
        "| oracle | trials | indeterminate | planted beyond 1 contact | planted max | "
        "picked beyond 1 contact | picked max | picked bands differ | edge shift median (Hz) | "
        "edge shift max (Hz) | planted gate |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ] + oracle_rows + [
        "",
        f"- Pool check (5 probes, serial vs ProcessPoolExecutor): {'identical' if pool_ok else 'DIFFERENT'}.",
        f"- Estimator agrees with the reimplemented window table on every probe: "
        f"{'yes' if measures['estimator_agrees_with_table'] else 'NO'}.",
        f"- Children: {jobs_info}",
        "",
        "## Measures",
        "",
        "| # | Measure | Count | Target |",
        "|---|---|---|---|",
        f"| 1 | Detection (accepted / n) | {fmt(p1)} | none |",
        f"| 2 | Conditional localization, picked bands, defined selected window (among those) | "
        f"{fmt(p2)} | none |",
        f"| 2b | Same, oracle's own bands | {fmt(p2['with_own_bands'])} | none |",
        f"| 2c | Band-edge shift vs oracle's own bands, selected window (median {be['median_hz']} Hz, "
        f"max {be['max_hz']} Hz; every edge within 1 Hz: {fmt(be['within_1hz'])}) | none |",
        f"| 2d | Accepted, no planted crossover (selected window undefined) | "
        f"{p2['accepted_undefined_window']} | none |",
        f"| 2e | Accepted, indeterminate oracle (selected window indeterminate) | "
        f"{p2['accepted_indeterminate_oracle']} | none |",
        f"| 3 | Unconditional recovery (accepted, scored, within 1 contact, / n) | {fmt(p3)}; "
        f"target 90 of 100: {met(p3.get('target_met'))} | at least 90 of 100 |",
        f"| 4 | Error against planted depth, accepted (contacts: count) | "
        + ", ".join(f"{k}: {v}" for k, v in p4.items()) + " | none |",
        f"| 5 | Window selection: window contains z0 | {p5['z0_inside']} of {p5['n_with_window']}; "
        f"{p5['distinct_windows']} distinct windows | none |",
        f"| 6 | Null acceptance (k / n) | {fmt(p6)}; target 5 of 100: {met(p6.get('target_met'))} "
        f"| at most 5 of 100 |",
        "",
        "## Other runs",
        "",
        f"- Noiseless control against the background-off oracle ({cp['count']} trials per record, A/B pair): "
        f"{bo['accepted']} accepted of {bo['n']}; undefined {bo['undefined']}; indeterminate "
        f"{bo['indeterminate']}; no crossover in either oracle {bo['no_crossover']}; scored {bo['scored']}; "
        f"within one contact {fmt(bo_block)}; misses beyond one contact (estimate minus oracle z*, contacts): "
        f"{miss_list}; by size: {miss_sizes}.",
        f"- Background-off pair gate: {'passes' if cp['passes'] else 'fails'} (planted beyond 1 contact where "
        f"both find one: {cp['planted_bad']}; indeterminate: {cp['indeterminate']}; plain mismatches: "
        f"{cp['plain_mismatches']}).",
        f"- model mismatch, background on vs off: {fmt(mm_block)} of the scored probes within one contact "
        f"of the background-on oracle's picked-band crossover.",
        f"- Geometry reversal: detection {fmt(rev['block']['1_detection'])}; mirror "
        f"{rev['mirror']['k']} of {rev['mirror']['n']}; orientation flipped "
        f"{rev['orientation_flipped']['k']} of {rev['orientation_flipped']['n']}; exact omega ties "
        f"{rev['ties_primary']['k']} of {rev['ties_primary']['n']} (primary), "
        f"{rev['ties_reversal']['k']} of {rev['ties_reversal']['n']} (reversed).",
        f"- Frequency grid (0.5 Hz, 299 bins, oracle {chosen['s2']} two-second trials): detection "
        f"{fmt(grd['1_detection'])}; recovery {fmt(grd['3_unconditional_recovery'])}; within one "
        f"contact (picked) {fmt(grd['2_conditional_localization'])}.",
        "",
    ]
    return "\n".join(lines) + "\n"


def oracle_document(stats: dict, tables: dict, chosen: dict, counts, kids,
                    ctrl_stats: dict, ctrl_tables: dict) -> dict:
    """The frozen record: seeds, the disagreement at every count, and what the measures are scored
    against. Scoring reads the A record's PSD at each frozen count and depth, and the indeterminate
    windows of its A/B pair (both frames), which the B record sets; the B PSD itself is not stored. The
    PSDs, their frequencies and the rules are stored at full precision. The window tables are rederived
    from the PSDs on load with window_table."""
    def psd_json(t):
        return {"psd_shape": list(t["psd"].shape), "psd": t["psd"].tolist()}

    def window_list(found):
        return [list(x) for x in sorted(found)]

    z0s = sorted({z0 for (_, _, _, z0) in tables})
    psd = {}
    for kind in KINDS:
        psd[kind] = {}
        for z0 in z0s:
            a = tables[(kind, chosen[kind], "A", z0)]
            b = tables[(kind, chosen[kind], "B", z0)]
            psd[kind][str(z0)] = dict(
                psd_json(a),
                indeterminate=window_list(indeterminate_windows(a["rows"], b["rows"])),
                indeterminate_reversed=window_list(indeterminate_windows(a["rows_reversed"],
                                                                         b["rows_reversed"])))
    freqs = {kind: tables[(kind, chosen[kind], "A", z0s[0])]["freqs"].tolist() for kind in KINDS}
    ctrl_z0s = sorted({z for (_, _, _, z) in ctrl_tables})
    ctrl_psd = {}
    for z0 in ctrl_z0s:
        a = ctrl_tables[("ctrl", CONTROL_ORACLE_COUNT, "A", z0)]
        b = ctrl_tables[("ctrl", CONTROL_ORACLE_COUNT, "B", z0)]
        ctrl_psd[str(z0)] = dict(psd_json(a),
                                 indeterminate=window_list(indeterminate_windows(a["rows"], b["rows"])))
    return {
        "contract": "artifacts/evidence/0.2.13/vflip2_generator_design.md",
        "entropy": ENTROPY,
        "children": {f"{kind}_{count}_{letter}": {
            "index": idx, "spawn_key": list(kids[idx].spawn_key)}
            for (kind, count, letter), idx in ORACLE_CHILD.items()},
        "counts_trials": list(counts),
        "frozen_count": {kind: chosen[kind] for kind in KINDS},
        "rule": ("the smallest count at which, at every depth, the planted-band crossovers of A and B "
                 f"agree within {TOLERANCE_CONTACTS} contact in every defined window where both find one; "
                 "a defined window where exactly one finds one is indeterminate (null, no localization "
                 "measure, counted at every count); picked-band crossovers, bands and edge shifts are "
                 "uncertainty only"),
        "disagreement": {kind: {str(count): {k: v for k, v in stats[(kind, count)].items()
                                             if k not in ("kind", "count")}
                                for count in counts} for kind in KINDS},
        "fs": FS, "n_contacts": N_CONTACTS, "pitch_um": PITCH_UM, "snr": SNR,
        "planted_bands_hz": {"low": list(VFLIP2_LOW_BAND_HZ), "high": list(VFLIP2_HIGH_BAND_HZ)},
        "planted_orientation": "upright",
        "z_units": "0-based contact index; null where undefined or absent",
        "defined_rule": "not every row of the window clipped at 0.05, nor every row at 0.95",
        "freqs": freqs,
        "psd": psd,
        "control_oracle": {
            "count": CONTROL_ORACLE_COUNT, "background": False,
            "rule": "the same gate as the background-on oracle, at this one count (no count search)",
            "stats": {k: v for k, v in ctrl_stats.items() if k not in ("kind", "count")},
            "children": {f"{letter}_{z0}": {"index": idx, "spawn_key": list(kids[idx].spawn_key)}
                         for (letter, z0), idx in CONTROL_ORACLE_CHILD.items()},
            "freqs": ctrl_tables[("ctrl", CONTROL_ORACLE_COUNT, "A", ctrl_z0s[0])]["freqs"].tolist(),
            "psd": ctrl_psd,
        },
    }


def plan_children_note() -> str:
    return (f"SeedSequence(0x{ENTROPY:04X}) spawned {N_CHILDREN} children; noiseless control "
            f"0-{N_Z0 - 1}, primary/null/reversal {CHILD_MEASURED}-{CHILD_MEASURED + N_PROBES - 1}, "
            f"grid {CHILD_GRID}-{CHILD_GRID + N_PROBES - 1}; oracle pairs "
            + ", ".join(f"{kind} {count} {letter} {idx}" for (kind, count, letter), idx
                        in ORACLE_CHILD.items())
            + f"; background-off control pairs {N_BACKGROUND_CHILDREN}-{N_CHILDREN - 1}")


def _extends(old, new) -> bool:
    """True when every value of `old` appears unchanged in `new`; `new` may add keys and items."""
    if isinstance(old, dict):
        return isinstance(new, dict) and all(k in new and _extends(v, new[k]) for k, v in old.items())
    if isinstance(old, list):
        return isinstance(new, list) and len(old) == len(new) and all(
            _extends(a, b) for a, b in zip(old, new))
    return old == new


def write_frozen(document: dict) -> str:
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    if ORACLE_PATH.exists():
        old_text = ORACLE_PATH.read_text(encoding="utf-8")
        if old_text == text:
            return "reproduced (frozen file unchanged)"
        if not _extends(json.loads(old_text), json.loads(text)):
            raise SystemExit(f"{ORACLE_PATH.relative_to(ROOT).as_posix()} exists and an existing value "
                             "differs from the recomputed oracle; a frozen oracle is never overwritten")
        ORACLE_PATH.write_text(text, encoding="utf-8", newline="\n")
        return "extended (every existing value unchanged; keys added)"
    ORACLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ORACLE_PATH.write_text(text, encoding="utf-8", newline="\n")
    return "written"


def rederive_job(job):
    """One depth of the background-on oracle, rederived from its stored A PSD with window_table: the
    forward and reversed tables. The indeterminate windows of the A/B pair are read back as stored."""
    kind, z0, psd, freqs, indet, indet_rev = job
    w = low_weight_for(z0)
    rows = window_table(psd, freqs, w)
    rows_rev = window_table(psd[::-1], freqs, w[::-1])
    return kind, z0, {"psd": psd, "freqs": freqs, "rows": rows, "rows_reversed": rows_rev,
                      "indeterminate": {tuple(x) for x in indet},
                      "indeterminate_reversed": {tuple(x) for x in indet_rev}}


def control_rederive_job(job):
    """One depth of the background-off control, rederived from its stored A PSD: the forward table.
    The indeterminate windows of the A/B pair are read back as stored."""
    z0, psd, freqs, indet = job
    rows = window_table(psd, freqs, low_weight_for(z0))
    return z0, {"rows": rows, "indeterminate": {tuple(x) for x in indet}}


def verify_job(job):
    """One stored PSD, checked: its window table (and the reversed one, when both_frames) rederived with
    window_table against the plain-numpy recomputation of the same PSD. Returns the table count and the
    number of tables that differ."""
    label, z0, psd, freqs, both_frames = job
    w = low_weight_for(z0)
    frames = [(psd, w), (psd[::-1], w[::-1])] if both_frames else [(psd, w)]
    differ = 0
    for p_arr, w_arr in frames:
        if compare_rows(window_table(p_arr, freqs, w_arr), plain_rows(p_arr, freqs, w_arr)):
            differ += 1
    return label, z0, len(frames), differ


def verify_frozen(path: pathlib.Path, pool) -> int:
    """--verify: rederive every frozen depth from its stored PSD and check each window table against the
    plain-numpy recomputation. No probes are run and nothing is written."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    jobs = []
    for kind in KINDS:
        freqs = np.array(doc["freqs"][kind], dtype=float)
        for z0, t in doc["psd"][kind].items():
            jobs.append((kind, int(z0), np.array(t["psd"], dtype=float), freqs, True))
    cdoc = doc["control_oracle"]
    cfreqs = np.array(cdoc["freqs"], dtype=float)
    for z0, t in cdoc["psd"].items():
        jobs.append(("control", int(z0), np.array(t["psd"], dtype=float), cfreqs, False))
    results = list(pool.map(verify_job, jobs))
    n_tables = sum(n for _, _, n, _ in results)
    n_differ = sum(bad for _, _, _, bad in results)
    for label, z0, _, bad in results:
        if bad:
            print(f"  differs: {label} z0 {z0}: {bad} table(s)")
    print(f"summary: verify: {n_tables} window tables rederived from the stored PSDs at "
          f"{len(doc['psd']['s1'])} depths (s1 and s2: forward and reversed; control: forward) and checked "
          f"against plain numpy; differing {n_differ}")
    return 0 if n_differ == 0 else 1


def load_frozen(path: pathlib.Path, z0s: Sequence[int], pool):
    """The frozen record as the measured runs read it: the disagreement stats by (kind, count), the
    background-on lookups by kind and depth, the control lookup by depth, the control stats, the
    counts and the frozen counts. The window tables are rederived from the stored A PSDs, at the
    depths in z0s, in the pool; the indeterminate windows are read back."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    counts = tuple(doc["counts_trials"])
    chosen = dict(doc["frozen_count"])
    stats = {(kind, int(c)): dict(v, kind=kind, count=int(c))
             for kind, by_count in doc["disagreement"].items() for c, v in by_count.items()}
    on_jobs = []
    for kind in KINDS:
        freqs = np.array(doc["freqs"][kind], dtype=float)
        for z0 in z0s:
            t = doc["psd"][kind][str(z0)]
            on_jobs.append((kind, z0, np.array(t["psd"], dtype=float), freqs,
                            t["indeterminate"], t["indeterminate_reversed"]))
    looks: Dict[str, Dict[int, dict]] = {kind: {} for kind in KINDS}
    for kind, z0, look in pool.map(rederive_job, on_jobs):
        looks[kind][z0] = look
    cdoc = doc["control_oracle"]
    cfreqs = np.array(cdoc["freqs"], dtype=float)
    ctrl_jobs = [(z0, np.array(cdoc["psd"][str(z0)]["psd"], dtype=float), cfreqs,
                  cdoc["psd"][str(z0)]["indeterminate"]) for z0 in z0s]
    ctrl = dict(pool.map(control_rederive_job, ctrl_jobs))
    ctrl_stats = dict(cdoc["stats"], kind="ctrl", count=cdoc["count"])
    return stats, looks, ctrl, ctrl_stats, counts, chosen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=N_PROBES, help="probes per run (default 100)")
    parser.add_argument("--oracle-only", action="store_true",
                        help="build and gate the oracle at every count, then stop")
    parser.add_argument("--write", action="store_true",
                        help="freeze the oracle and write vflip2_recovery.md and .json")
    parser.add_argument("--oracle-file", metavar="PATH",
                        help="load the frozen oracle from PATH instead of rebuilding it")
    parser.add_argument("--verify", action="store_true",
                        help="rederive every frozen depth from its stored PSD and check it against the "
                             "plain-numpy recomputation; runs alone, with no probes and no writes")
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("--n must be at least 1")
    if args.oracle_file and args.oracle_only:
        parser.error("--oracle-file loads an oracle; --oracle-only builds one")
    if args.verify and (args.write or args.oracle_only or args.oracle_file):
        parser.error("--verify checks the frozen oracle at ORACLE_PATH and runs alone")
    smoke = args.n < N_PROBES
    if args.write and smoke:
        parser.error("--write needs the full --n 100; a smoke run is printed only")
    counts = SMOKE_COUNTS if smoke else COUNTS
    z0s = needed_z0(args.n)
    kids = children()

    with futures.ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        if args.verify:
            return verify_frozen(ORACLE_PATH, pool)
        if args.oracle_file:
            path = pathlib.Path(args.oracle_file)
            stats, looks, ctrl, ctrl_stats, counts, chosen = load_frozen(path, z0s, pool)
            print(f"oracle loaded from {path.as_posix()}: frozen trial counts one-second "
                  f"{chosen['s1']}, two-second {chosen['s2']}; window tables rederived from the stored PSDs")
            frozen_state = "loaded (not rewritten)"
        else:
            stats, tables = build_oracle(z0s, counts, pool)
            ctrl_stats, ctrl_tables = build_control_oracle(pool)
            for kind in KINDS:
                for count in counts:
                    print("oracle: " + _stats_line(stats[(kind, count)]))
            print("control oracle (background off): " + _stats_line(ctrl_stats))
            plain_bad = [k for k, s in stats.items() if s["plain_mismatches"]]
            if ctrl_stats["plain_mismatches"]:
                plain_bad.append(("ctrl", CONTROL_ORACLE_COUNT))
            if plain_bad:
                for k in plain_bad:
                    print(f"GATE FAILED: plain recomputation differs for {k}")
                print("summary: plain recomputation failed; no measured run was made")
                return 1
            chosen: Dict[str, Optional[int]] = {}
            for kind in KINDS:
                chosen[kind] = choose_count({c: stats[(kind, c)]["passes"] for c in counts}, counts)
                if chosen[kind] is None:
                    if not smoke:
                        print(f"GATE FAILED: planted-band agreement fails at every count {tuple(counts)} "
                              f"for {kind}; stopped, nothing frozen")
                        print(f"summary: oracle gate failed at {counts[-1]} trials; stopped")
                        return 1
                    chosen[kind] = counts[0]
            if not ctrl_stats["passes"]:
                print("GATE FAILED: the background-off control pair fails the agreement gate at "
                      f"{CONTROL_ORACLE_COUNT} trials; stopped, nothing frozen")
                print("summary: control oracle gate failed; stopped")
                return 1
            print(f"frozen trial counts: one-second {chosen['s1']}, two-second {chosen['s2']}")
            frozen_state = "not written (no --write)"
            if args.write:
                frozen_state = write_frozen(oracle_document(stats, tables, chosen, counts, kids,
                                                            ctrl_stats, ctrl_tables))
            looks = {kind: {z0: look_for(tables, kind, chosen[kind], z0) for z0 in z0s} for kind in KINDS}
            ctrl = {z0: {"rows": ctrl_tables[("ctrl", CONTROL_ORACLE_COUNT, "A", z0)]["rows"],
                         "indeterminate": indeterminate_windows(
                             ctrl_tables[("ctrl", CONTROL_ORACLE_COUNT, "A", z0)]["rows"],
                             ctrl_tables[("ctrl", CONTROL_ORACLE_COUNT, "B", z0)]["rows"])}
                    for z0 in z0s}
        print(f"oracle frozen file: {frozen_state}")
        if args.oracle_only:
            return 0

        plan = plan_jobs(args.n)
        pool_jobs = [("primary", i, z0_for(i), CHILD_MEASURED + i, kids[CHILD_MEASURED + i])
                     for i in range(5)]
        serial = [probe_job(j) for j in pool_jobs]
        pooled = list(pool.map(probe_job, pool_jobs))
        pool_ok = serial == pooled
        print(f"pool check: 5 probes serial vs pool {'identical' if pool_ok else 'DIFFERENT'}")
        if not pool_ok:
            print("summary: pool check failed; no measured run was made")
            return 1
        outs = {}
        for key in ("control", "primary", "null", "reversal", "grid"):
            outs[key] = list(pool.map(probe_job, plan[key]))

    measures = run_measures(outs, looks, args.n, ctrl)
    measures["control"]["pair"] = ctrl_stats
    text = render(args.n, measures, stats, chosen, counts, smoke, pool_ok, plan_children_note())
    if args.write:
        payload = {"entropy": ENTROPY, "n": args.n, "frozen_count": chosen,
                   "measures": measures, "probes": outs}
        JSON_PATH.write_text(json.dumps(payload, indent=1, sort_keys=True, allow_nan=False) + "\n",
                             encoding="utf-8", newline="\n")
        MD_PATH.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {MD_PATH.relative_to(ROOT).as_posix()} and {JSON_PATH.relative_to(ROOT).as_posix()}")
    print(text, end="")
    p3 = measures["primary"]["3_unconditional_recovery"]
    p6 = measures["null"]["6_null_acceptance"]
    print(f"summary: detection {measures['primary']['1_detection']['k']} of {args.n}; "
          f"recovery {p3['k']} of {args.n}; null accepted {p6['k']} of {args.n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
