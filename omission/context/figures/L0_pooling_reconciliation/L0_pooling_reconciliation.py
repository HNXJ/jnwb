r"""
L0 -- Reconcile per-channel vs pooled omission LFP response. BLOCKER for L1-L12.

WHY THIS EXISTS
    Per the LFP-primary analysis spec (pasted 2026-08-16, confirmed by Hamm to target this
    repo -- "naming is just old/different", subjects are C31o/V182o/V198o, task is "omission",
    not the spec's stale "Ivan"/"oGLO" labels): Andre reports no omission LFP response in any
    area/band; Hamed reports the effect is visible per-channel and vanishes when pooled. This
    script reconciles the two by computing the same omission response four different ways on
    one session/area/band and reporting which pooling choice explains the discrepancy.

METHOD (spec's own four variants)
    (a) per-channel band power, then average the (linear) power across channels, THEN take
        10*log10 once relative to a channel-pooled baseline -- the "log-last" pooling this
        project's omission-signal skill (S1) already prescribes as correct.
    (b) average the raw LFP trace across channels FIRST (in the time domain, per trial), THEN
        compute band power on the channel-averaged trace -- tests destructive interference /
        dipole cancellation across channels sharing a common reference.
    (c) per-channel band power, per-channel dB (10*log10 against that channel's OWN baseline),
        THEN average the dB values across channels -- averages in log space, which
        omission-signal S1 documents as biased (Jensen's inequality, E[log X] < log E[X]).
    (d) same as (a) but on Laplacian-(CSD-)referenced traces instead of raw-referenced traces.
        omission.jnwb_ext.spectral.laplacian_reference (interior channel i = x[i] - mean(x[i-1], x[i+1])) is
        the standard discrete second-spatial-derivative CSD estimator for a linearly-spaced,
        depth-ordered probe (CSD ~ -d2V/dz2); reused here rather than building new CSD infra,
        since it is already the house re-referencing utility used for exactly this purpose in
        extract_lfp_coupling_matrices.py.

DATA CONTRACT DECISIONS (stated, not hidden -- confirm before reusing for L1+)
    - One session (sub-C31o_ses-230823), one area (FEF -- a single-area 128-channel probe, so
      this first blocker run needs no area-boundary resolution), one band (alpha, 8-14 Hz).
    - A 32-channel contiguous depth block (local indices 48:80) from the middle of the probe is
      used as "the area's channels", not all 128 -- CSD/Laplacian referencing needs literal
      adjacent physical contacts, and this keeps per-channel FFT cost bounded. This is a
      tractability choice, stated here, not a claim that FEF is only 32 channels wide.
    - Condition RXRR only (the only condition carrying a genuine omission at a mid-sequence
      slot). Response window = the omission window used corpus-wide in
      extract_lfp_coupling_matrices.py's CONTEXTS["omission"]: 1.031-1.562 s post p1 (p2 is the
      omitted slot in RXRR). Baseline window = (-0.400, -0.150) s pre-p1 -- the same pre-trial
      reference window this session's onset_fitting.py fix established as clear of any
      pre-stimulus ramp contamination (artifacts/.lab/onset-hierarchy-h1h2h3-fixed-20260815.json).
    - Raw movement-artifact repair (jnwb.artifact_repair.repair_lfp_trials) runs before any
      re-referencing, exactly as in extract_lfp_coupling_matrices.py.
    - Per-method point estimate plus a trial-level bootstrap CI (resampling trial INDICES, not
      re-running the FFT -- the four per-trial-per-channel power arrays are computed once and
      reused for every bootstrap draw). Seed fixed and recorded so the run is byte-reproducible.

OUTPUT
    L0.svg / L0.png  -- 4-panel comparison figure, one panel per method, shared dB axis.
    L0_stats.json    -- every number in the figure, plus canonical_pooling_method.
    L0_manifest.json -- input file, git SHA, seed, band edges, n trials/channels, exclusions.

TESTS
    --test runs the synthetic ground-truth self-test (no real data, seconds to run): an
    equal-and-opposite superficial/deep dipole must show a real effect under method (a) and a
    null effect under method (b) -- the spec's own acceptance criterion for this analysis.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from precompute_tfr_arrays import (  # noqa: E402
    condition_numbers_for, p1_onsets_s, resolve_lfp_datasets,
)
from omission.jnwb_ext.spectral import laplacian_reference  # noqa: E402
from jnwb.artifact_repair import repair_lfp_trials  # noqa: E402  (promoted 2026-08-23 from omission.jnwb_ext.artifact_repair)
from jnwb.addressing import map_peak_channel_to_area  # noqa: E402
import figstyle  # noqa: E402

SEED = 42
RESPONSE_WIN_S = (1.031, 1.562)   # omission window (p2 slot in RXRR), matches CONTEXTS["omission"]
BASELINE_WIN_S = (-0.400, -0.150)  # pre-trial, matches the fixed onset_fitting.py convention
MAX_TRIALS = 60
N_BOOT = 2000
BAND_NAME = "alpha"
BAND_HZ = (8.0, 14.0)   # house band set, omission-signal skill S6
N_CH_WINDOW = 32
PROBE_LETTER_TO_KEY = {"A": "probe_0_lfp", "B": "probe_1_lfp", "C": "probe_2_lfp", "D": "probe_3_lfp"}

FIG_DIR = Path(__file__).resolve().parent


# --------------------------------------------------------------------- area/channel resolution --

def probe_channel_areas(f: h5py.File, group_name: str) -> np.ndarray:
    """Area label per LOCAL channel index (0-based within this probe), depth order = index order,
    resolved via jnwb.addressing.map_peak_channel_to_area (position-aware for multi-area probes,
    not a naive location.split(',')[0])."""
    et = f["general/extracellular_ephys/electrodes"]

    def dec(a):
        return np.array([x.decode() if isinstance(x, bytes) else x for x in a[:]])

    loc = dec(et["location"])
    grp = dec(et["group_name"])
    import pandas as pd
    edf = pd.DataFrame({"location": loc, "group_name": grp})
    probe_rows = edf.index[edf["group_name"] == group_name].to_numpy()
    probe_rows.sort()
    areas = np.array([map_peak_channel_to_area(float(idx), edf) for idx in probe_rows])
    return areas  # local index i -> areas[i]


def resolve_area_channel_block(f: h5py.File, probe_letter: str, area: str, n_ch: int):
    """Contiguous local-index channel block of width n_ch centered in the target area's
    contiguous run on this probe. Raises if the area isn't found or is narrower than n_ch."""
    key = PROBE_LETTER_TO_KEY[probe_letter]
    et = f["general/extracellular_ephys/electrodes"]

    def dec(a):
        return np.array([x.decode() if isinstance(x, bytes) else x for x in a[:]])

    grp = dec(et["group_name"])
    group_name = f"probe{probe_letter}"
    if group_name not in grp:
        raise ValueError(f"No electrode group {group_name!r} in this session")
    areas = probe_channel_areas(f, group_name)
    idx = np.where(areas == area)[0]
    if len(idx) == 0:
        raise ValueError(f"Area {area!r} not found on probe {probe_letter}; areas present: "
                          f"{sorted(set(areas))}")
    if len(idx) < n_ch:
        raise ValueError(f"Area {area!r} only has {len(idx)} channels on probe {probe_letter}, "
                          f"need {n_ch}")
    lo_area, hi_area = int(idx.min()), int(idx.max()) + 1
    mid = (lo_area + hi_area) // 2
    lo = max(lo_area, mid - n_ch // 2)
    hi = min(hi_area, lo + n_ch)
    lo = hi - n_ch
    return key, lo, hi


# --------------------------------------------------------------------------- trial extraction --

def extract_windows(f: h5py.File, lfp_key: str, ch_lo: int, ch_hi: int, condition: str,
                     max_trials: int):
    """Returns (resp_trials, base_trials): each (n_trials, n_channels, n_samples), raw-referenced,
    artifact-repaired. Both windows drawn from the same trial set (same onsets), so trial i in
    resp_trials and trial i in base_trials are the same trial."""
    data, ts, fs = resolve_lfp_datasets(f, lfp_key)
    onsets = p1_onsets_s(f, condition)[:max_trials]
    if len(onsets) == 0:
        raise ValueError(f"No {condition} trials found")

    def pull(win_s):
        need = int(round((win_s[1] - win_s[0]) * fs))
        out = []
        for onset in onsets:
            t0, t1 = onset + win_s[0], onset + win_s[1]
            if ts is not None:
                i0, i1 = int(np.searchsorted(ts, t0)), int(np.searchsorted(ts, t1))
            else:
                i0, i1 = int(round(t0 * fs)), int(round(t1 * fs))
            i0, i1 = max(0, i0), min(data.shape[0], i1)
            if i1 - i0 < need // 2:
                continue
            raw = np.asarray(data[i0:i1, ch_lo:ch_hi], dtype=np.float64)
            if raw.shape[0] < need:
                raw = np.pad(raw, ((0, need - raw.shape[0]), (0, 0)), mode="edge")
            elif raw.shape[0] > need:
                raw = raw[:need]
            out.append(raw.T)  # (n_channels, n_samples)
        return np.stack(out) if out else None, fs

    resp, fs = pull(RESPONSE_WIN_S)
    base, _ = pull(BASELINE_WIN_S)
    n = min(len(resp) if resp is not None else 0, len(base) if base is not None else 0)
    if n == 0:
        raise ValueError("No usable trials after window extraction")
    resp, base = resp[:n], base[:n]

    resp, frac_resp, _ = repair_lfp_trials(resp, times_ms=None, reward_window_ms=None)
    base, frac_base, _ = repair_lfp_trials(base, times_ms=None, reward_window_ms=None)
    return resp, base, fs, n, float(max(frac_resp, frac_base))


# ------------------------------------------------------------------------------- band power --

def trial_channel_band_power(x_trials: np.ndarray, fs: float, band) -> np.ndarray:
    """(n_trials, n_channels, n_samples) -> (n_trials, n_channels) linear band power,
    Hann-windowed periodogram, mean over band bins (Welch with a single segment == periodogram;
    trial windows here are short enough -- 250-531 samples -- that a single Hann segment per
    trial is the natural choice, matching trial_band_fft's convention in
    extract_lfp_coupling_matrices.py)."""
    n_trials, n_channels, n_samples = x_trials.shape
    window = np.hanning(n_samples)
    U = np.sum(window ** 2)
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / fs)
    fmask = (freqs >= band[0]) & (freqs < band[1])
    if not np.any(fmask):
        raise ValueError(f"Band {band} has no FFT bins at fs={fs}, n_samples={n_samples}")
    Xf = np.fft.rfft(x_trials * window[None, None, :], axis=2)
    psd = (np.abs(Xf) ** 2) * (2.0 / (fs * U))
    return psd[:, :, fmask].mean(axis=2)


def trial_avgtrace_band_power(x_trials: np.ndarray, fs: float, band) -> np.ndarray:
    """Average across channels FIRST (time domain, per trial), then band power on the
    resulting single trace per trial. Returns (n_trials,)."""
    avg_trace = x_trials.mean(axis=1)  # (n_trials, n_samples)
    return trial_channel_band_power(avg_trace[:, None, :], fs, band)[:, 0]


def csd_reference_trials(x_trials: np.ndarray) -> np.ndarray:
    """laplacian_reference per trial (same channel count/order out as in)."""
    return np.stack([laplacian_reference(x_trials[t]) for t in range(x_trials.shape[0])])


# --------------------------------------------------------------------------------- methods --

def method_a(resp_pc, base_pc, idx):
    """Per-channel power, average across channels (linear), log once -- correct log-last pooling."""
    r = resp_pc[idx].mean(axis=0)   # (n_channels,) -- mean over trials
    b = base_pc[idx].mean(axis=0)
    return 10.0 * np.log10(r.mean() / b.mean())


def method_b(resp_avg, base_avg, idx):
    """Channel-averaged trace, then power -- tests destructive interference."""
    r = resp_avg[idx].mean()
    b = base_avg[idx].mean()
    return 10.0 * np.log10(r / b)


def method_c(resp_pc, base_pc, idx):
    """Per-channel dB (each channel against its own baseline), THEN average the dB values."""
    r = resp_pc[idx].mean(axis=0)
    b = base_pc[idx].mean(axis=0)
    db_per_channel = 10.0 * np.log10(r / b)
    return float(db_per_channel.mean())


def method_d(resp_csd_pc, base_csd_pc, idx):
    """Same construction as method (a), on CSD/Laplacian-referenced channels."""
    return method_a(resp_csd_pc, base_csd_pc, idx)


def bootstrap_ci(fn, *arrays, n_trials, n_boot, rng):
    point = fn(*arrays, np.arange(n_trials))
    draws = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n_trials, size=n_trials)
        draws[i] = fn(*arrays, idx)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(point), float(lo), float(hi)


# ------------------------------------------------------------------------------------- main --

def run(session_prefix: str, probe_letter: str, area: str, nwb_dir: Path, seed=SEED,
        n_boot=N_BOOT, max_trials=MAX_TRIALS, n_ch=N_CH_WINDOW):
    nwb_path = nwb_dir / f"{session_prefix}_rec.nwb"
    if not nwb_path.is_file():
        nwb_path = nwb_dir / f"{session_prefix}.nwb"
    if not nwb_path.is_file():
        raise FileNotFoundError(f"No NWB for {session_prefix} under {nwb_dir}")

    rng = np.random.default_rng(seed)
    with h5py.File(nwb_path, "r") as f:
        lfp_key, ch_lo, ch_hi = resolve_area_channel_block(f, probe_letter, area, n_ch)
        resp, base, fs, n_trials, frac_repaired = extract_windows(
            f, lfp_key, ch_lo, ch_hi, "RXRR", max_trials)

    resp_pc = trial_channel_band_power(resp, fs, BAND_HZ)
    base_pc = trial_channel_band_power(base, fs, BAND_HZ)
    resp_avg = trial_avgtrace_band_power(resp, fs, BAND_HZ)
    base_avg = trial_avgtrace_band_power(base, fs, BAND_HZ)
    resp_csd = csd_reference_trials(resp)
    base_csd = csd_reference_trials(base)
    resp_csd_pc = trial_channel_band_power(resp_csd, fs, BAND_HZ)
    base_csd_pc = trial_channel_band_power(base_csd, fs, BAND_HZ)

    results = {}
    results["a_per_channel_then_pool"] = bootstrap_ci(
        method_a, resp_pc, base_pc, n_trials=n_trials, n_boot=n_boot, rng=rng)
    results["b_pool_then_power"] = bootstrap_ci(
        method_b, resp_avg, base_avg, n_trials=n_trials, n_boot=n_boot, rng=rng)
    results["c_per_channel_db_then_average"] = bootstrap_ci(
        method_c, resp_pc, base_pc, n_trials=n_trials, n_boot=n_boot, rng=rng)
    results["d_csd_referenced"] = bootstrap_ci(
        method_d, resp_csd_pc, base_csd_pc, n_trials=n_trials, n_boot=n_boot, rng=rng)

    # Canonical determination: (a) is the log-last, correct pooling per omission-signal S1.
    # This is a methodological determination, not data-driven -- record it plainly, and also
    # record whether (a) and (b) actually disagree on this session/area/band (the empirical
    # question L0 exists to answer), separately from which method is canonical.
    a_val = results["a_per_channel_then_pool"][0]
    b_val = results["b_pool_then_power"][0]
    disagreement_db = float(a_val - b_val)

    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:
        git_sha = "unknown"

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "canonical_pooling_method_rationale": (
            "Per omission-signal skill S1 (take the logarithm last): average power over "
            "channels in linear space, divide by baseline, take 10*log10 exactly once. "
            "Averaging in dB space (method c) biases toward whichever channels are noisier; "
            "averaging voltage before computing power (method b) is a different physical "
            "quantity (destructive interference across a dipole), not an alternative estimate "
            "of the same one."
        ),
        "session": session_prefix, "probe": probe_letter, "area": area,
        "band_name": BAND_NAME, "band_hz": list(BAND_HZ),
        "condition": "RXRR", "response_window_s": list(RESPONSE_WIN_S),
        "baseline_window_s": list(BASELINE_WIN_S),
        "n_trials": int(n_trials), "n_channels": int(ch_hi - ch_lo),
        "channel_index_range_local": [int(ch_lo), int(ch_hi)],
        "fraction_trials_repaired": frac_repaired,
        "methods": {
            k: {"db": v[0], "ci95_lo": v[1], "ci95_hi": v[2]} for k, v in results.items()
        },
        "a_minus_b_db": disagreement_db,
        "a_and_b_agree": bool(abs(disagreement_db) < 0.5),
    }

    manifest = {
        "analysis_id": "L0", "date": None, "git_sha": git_sha, "seed": seed,
        "n_bootstrap": n_boot, "input_nwb": str(nwb_path), "lfp_key": lfp_key,
        "band_hz": list(BAND_HZ), "n_trials": int(n_trials),
        "n_channels": int(ch_hi - ch_lo), "channel_index_range_local": [int(ch_lo), int(ch_hi)],
        "max_trials_cap": max_trials, "exclusions": {"fraction_trials_repaired": frac_repaired},
    }

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L0_stats.json").write_text(json.dumps(stats, indent=2))
    (FIG_DIR / "L0_manifest.json").write_text(json.dumps(manifest, indent=2))

    plot_comparison(results, session_prefix, area, disagreement_db)
    return stats


def plot_comparison(results: dict, session_prefix: str, area: str, disagreement_db: float):
    figstyle.use_house_style()
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.2), sharey=True)
    labels = {
        "a_per_channel_then_pool": "(a) per-channel\n→ pool (log-last)",
        "b_pool_then_power": "(b) pool voltage\n→ power",
        "c_per_channel_db_then_average": "(c) per-channel dB\n→ average",
        "d_csd_referenced": "(d) CSD-referenced\n(a)-style pooling",
    }
    all_vals = [v for r in results.values() for v in r]
    ymin, ymax = min(all_vals) - 0.5, max(all_vals) + 0.5
    for ax, (key, label) in zip(axes, labels.items()):
        point, lo, hi = results[key]
        color = figstyle.AREA_COLORS.get(area, "#333333")
        ax.bar([0], [point], width=0.6, color=color)
        ax.errorbar([0], [point], yerr=[[point - lo], [hi - point]], fmt="none",
                    ecolor="black", capsize=4, linewidth=1.2)
        ax.axhline(0, color="#999999", linewidth=0.8, zorder=0)
        ax.set_title(label, fontsize=8)
        ax.set_xticks([])
        ax.set_ylim(ymin, ymax)
    axes[0].set_ylabel("Omission response (dB re baseline)")
    fig.suptitle(
        f"L0: {session_prefix} {area} {BAND_NAME} ({BAND_HZ[0]}-{BAND_HZ[1]} Hz), condition RXRR "
        f"— (a) − (b) = {disagreement_db:+.2f} dB",
        fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    figstyle.save(fig, FIG_DIR, "L0")
    fig.savefig(FIG_DIR / "L0.pdf")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """Equal-and-opposite superficial/deep dipole: real effect under (a), null under (b).
    This is the spec's own acceptance test for L0 -- no real data, must run in seconds."""
    rng = np.random.default_rng(0)
    fs = 1000.0
    n_trials = 40
    n_ch = 16
    n_samples_resp = 531
    n_samples_base = 250
    f0 = 11.0  # alpha-band center

    def make(n_samples, with_signal: bool):
        t = np.arange(n_samples) / fs
        noise = rng.normal(0, 0.05, size=(n_trials, n_ch, n_samples))
        if not with_signal:
            return noise
        amp = 1.0
        sig = amp * np.sin(2 * np.pi * f0 * t)[None, None, :]
        sign = np.array([1.0] * (n_ch // 2) + [-1.0] * (n_ch // 2))[None, :, None]
        return noise + sig * sign

    resp = make(n_samples_resp, with_signal=True)
    base = make(n_samples_base, with_signal=False)

    resp_pc = trial_channel_band_power(resp, fs, BAND_HZ)
    base_pc = trial_channel_band_power(base, fs, BAND_HZ)
    resp_avg = trial_avgtrace_band_power(resp, fs, BAND_HZ)
    base_avg = trial_avgtrace_band_power(base, fs, BAND_HZ)

    idx = np.arange(n_trials)
    db_a = method_a(resp_pc, base_pc, idx)
    db_b = method_b(resp_avg, base_avg, idx)

    print(f"Synthetic dipole self-test: method (a) = {db_a:.2f} dB, method (b) = {db_b:.2f} dB")
    assert db_a > 3.0, f"method (a) should show a real effect (>3 dB), got {db_a:.2f}"
    assert abs(db_b) < 1.0, f"method (b) should be null (|dB|<1), got {db_b:.2f}"
    print("PASS: (a) shows the dipole, (b) cancels it -- matches the spec's acceptance criterion.")

    # Determinism check: same seed -> byte-identical dB values.
    rng2 = np.random.default_rng(0)
    resp2 = np.empty_like(resp)  # rebuild with the same seeded rng2 stream, same construction
    t = np.arange(n_samples_resp) / fs
    noise2 = rng2.normal(0, 0.05, size=(n_trials, n_ch, n_samples_resp))
    amp = 1.0
    sig = amp * np.sin(2 * np.pi * f0 * t)[None, None, :]
    sign = np.array([1.0] * (n_ch // 2) + [-1.0] * (n_ch // 2))[None, :, None]
    resp2 = noise2 + sig * sign
    noise2b = rng2.normal(0, 0.05, size=(n_trials, n_ch, n_samples_base))
    base2 = noise2b
    resp2_pc = trial_channel_band_power(resp2, fs, BAND_HZ)
    base2_pc = trial_channel_band_power(base2, fs, BAND_HZ)
    db_a2 = method_a(resp2_pc, base2_pc, idx)
    assert db_a == db_a2, f"determinism check failed: {db_a} != {db_a2}"
    print("PASS: same seed -> byte-identical dB value (determinism check).")

    # Shape/NaN guard: zero-variance channel must not silently propagate NaN into the mean.
    degenerate = np.zeros((5, 4, 100))
    p = trial_channel_band_power(degenerate, fs, BAND_HZ)
    assert np.all(np.isfinite(p)), "zero-signal input produced non-finite band power"
    print("PASS: degenerate zero-signal input stays finite (shape/NaN guard).")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true", help="Run the synthetic ground-truth self-test only")
    ap.add_argument("--session", default="sub-C31o_ses-230823")
    ap.add_argument("--probe", default="A")
    ap.add_argument("--area", default="FEF")
    args = ap.parse_args()

    if args.test:
        run_synthetic_selftest()
        return

    import jnwb.paths as P
    nwb_dir = P.nwb_dir()
    stats = run(args.session, args.probe, args.area, nwb_dir)
    print(json.dumps(stats["methods"], indent=2))
    print(f"\ncanonical_pooling_method = {stats['canonical_pooling_method']}")
    print(f"(a) - (b) = {stats['a_minus_b_db']:+.2f} dB "
          f"({'AGREE' if stats['a_and_b_agree'] else 'DISAGREE'})")


if __name__ == "__main__":
    main()
