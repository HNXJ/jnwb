r"""
L5 -- LFP onset latency, cross-area. Forward smoothing only. Discriminates H1 (low->high,
V1 leads) / H2 (high->low, FEF/PFC leads) / H3 (simultaneous -- superposition or volume
conduction, ambiguous without L6).

Reads `canonical_pooling_method` from L0, same gate as L1-L4.

WHY THIS IS THE HIGHEST-STAKES SCRIPT IN THE LFP TRACK -- READ BEFORE EDITING
    Per the spec's own words: "acausal smoothing leaks response backward in time and will
    manufacture spurious early onsets; this is the single most likely way to get the FF/FB
    answer wrong." Every stage of this pipeline is causal by construction, not by convention:

    1. Band-pass filtering: single-pass `scipy.signal.lfilter` (NOT `filtfilt`). Per
       omission-signal S3: "filtfilt doubles the effective order and CANNOT be used when the
       analysis claims temporal precedence (Granger, PSI, cross-correlation lag)" -- onset
       latency is exactly that class of claim. A single-pass IIR filter has real, band-
       dependent group delay; this is NOT corrected for, because it doesn't need to be: L5's
       comparison is always ACROSS AREAS WITHIN ONE BAND (same filter design per band -> same
       group delay for every area), never across bands. The systematic delay cancels in every
       comparison this script actually makes. If a future caller ever compares onsets ACROSS
       bands, that assumption breaks and group-delay correction becomes necessary.
    2. Envelope: full-wave rectification (abs), a purely pointwise/causal operation.
    3. Pooling (trials, then channels -- canonical method (a) from L0) happens on the rectified
       envelope BEFORE smoothing. This is safe (not the log-averaging bias omission-signal S1
       warns about) because averaging and the causal smoothing kernel are both LINEAR operators
       and therefore commute -- smoothing the pool gives the identical trace to pooling the
       smoothed signals, at a fraction of the compute cost (one smoothing call instead of one
       per trial-channel).
    4. Smoothing: `omission.jnwb_ext.onset_fitting.causal_exp_smooth` -- the SAME forward-only kernel already
       validated for the spiking onset-hierarchy pipeline this session
       (artifacts/.lab/onset-hierarchy-h1h2h3-fixed-20260815.json) -- reused, not reimplemented.
    5. Fitting: `omission.jnwb_ext.onset_fitting.fit_exponential_onset` -- t0 is causality-bounded BY
       CONSTRUCTION (constrained inside the least-squares bounds, not filtered post-hoc), the
       exact fix that resolved a real boundary-pinning bug in the spiking version of this
       analysis earlier this session. Reused, not reimplemented.
    6. Extraction margin: 500 ms of REAL pre-window history is pulled before the nominal
       baseline window and trimmed off after filtering+smoothing -- covers both the causal
       filter's own settling transient (~2 cycles of the lowest band edge, theta at 4 Hz =
       250 ms/cycle) and causal_exp_smooth's own 5*tau_ms=150ms real-history requirement (the
       exact bug class fixed in fit_class_onset_latency.py this session -- a zero-padded
       warm-up manufactures a fake flat baseline that biases the fitted onset toward t0=0).

SCOPE (stim condition only, stated not hidden)
    RRRR (real p1 stimulus) only. Omission-locked onset (RXRR, p2) is a natural extension, not
    built here -- omission responses were already shown weaker/noisier than stim responses in
    L1-L4 on this corpus, and onset fitting needs a clean rise to be identifiable at all.

METHOD
    Per area (V1, V2, MT, MST, FEF, PFC -- same six as L1/L2, in AREA_ORDER hierarchy order),
    per band (five house bands), per session (reusing L2's sessions_for_area, up to 3/subject):
    causal band-pass -> rectify -> pool (trials, channels) -> causal_exp_smooth -> fit_t0. Each
    session yields ONE t0 point estimate. Session-level bootstrap (resample the list of
    per-session t0 values, not trials/channels) gives the area's onset CI. Pairwise onset
    differences between areas are bootstrapped the same way (independently resample each area's
    own session-t0 list). `discriminating: false` recorded per pair when the 95% CI includes
    zero -- per the spec's own acceptance criterion, an ambiguous pair is reported as
    ambiguous, not silently dropped or spun into a claim.

OUTPUT
    L5.svg / L5.png / L5.pdf (onset ± CI per area per band, ordered by hierarchy; pairwise
    onset-difference matrix), L5_stats.json (every value plus `discriminating` per pair per
    band and an H1/H2/H3 verdict per band via Spearman rank correlation against hierarchy
    position), L5_manifest.json.

TESTS
    --test: synthetic multi-area signals with a KNOWN injected onset lag must recover that lag
    within tolerance; a synthetic ZERO-LAG case (all areas share one true onset) must return
    `discriminating: false` for every pair -- the spec's own explicit acceptance test.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal, stats as scipy_stats

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from _l_lfp_common import extract_epoch_trials, find_probe_for_area, git_sha  # noqa: E402
from jnwb.onset_fitting import causal_exp_smooth, fit_exponential_onset  # noqa: E402  (promoted 2026-08-23)
from jnwb.spectral import CANONICAL_BANDS  # noqa: E402
import figstyle  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"

SEED = 42
N_BOOT = 2000
EXTRACTION_MARGIN_S = 0.5
BASELINE_WIN_S = (-0.4, -0.15)
FIT_WIN_S = (-0.6, 0.9)          # window handed to the fitter, AFTER margin trim
T0_BOUNDS_MS = (0.0, 400.0)
MAX_SESSIONS_PER_SUBJECT = 3
MAX_TRIALS = 60
N_CH_WINDOW = 32
FILTER_ORDER = 4
SMOOTH_TAU_MS = 30.0

BANDS = CANONICAL_BANDS
AREAS = ["V1", "V2", "MT", "MST", "FEF", "PFC"]           # already in hierarchy order
HIERARCHY_RANK = {a: i for i, a in enumerate(AREAS)}


def require_l0_canonical_method():
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    if json.loads(L0_STATS.read_text()).get("canonical_pooling_method") != "a_per_channel_then_pool":
        raise RuntimeError(f"Unexpected canonical_pooling_method in {L0_STATS}")


def sessions_for_area(area: str, cap_per_subject=MAX_SESSIONS_PER_SUBJECT):
    """Same construction as L2's sessions_for_area -- kept local (not imported cross-figure-dir)
    since context/figures/L2_band_power_traces/ is not on sys.path here and importing across
    sibling figure directories is not this project's convention (each figNN_*/LNN_*/ is
    self-contained, per omission-figures skill)."""
    import jnwb.paths as P
    import pandas as pd
    readiness = pd.read_csv(REPO / "artifacts" / "data" / "session_readiness.csv")
    prefixes = readiness.loc[readiness.nwb_ok, "session_prefix"].tolist()
    nwb_dir = Path(P.nwb_dir())
    by_subject: dict[str, list] = {}
    for prefix in prefixes:
        cand = list(nwb_dir.glob(prefix + "*.nwb"))
        if not cand:
            continue
        subject = prefix.split("_")[0].replace("sub-", "")
        if len(by_subject.get(subject, [])) >= cap_per_subject:
            continue
        try:
            with h5py.File(cand[0], "r") as f:
                probe = find_probe_for_area(f, area)
        except Exception:
            continue
        if probe is None:
            continue
        by_subject.setdefault(subject, []).append((prefix, subject, probe))
    out = []
    for subj_list in by_subject.values():
        out.extend(subj_list)
    return out


def causal_band_envelope_trace(trials: np.ndarray, fs: float, band_hz, extraction_margin_s: float):
    """trials: (n_trials, n_channels, n_samples), extracted with extraction_margin_s of REAL
    extra history at the start. Returns (t_ms_trimmed, pooled_smoothed_envelope) -- trimmed back
    to the nominal window, margin used only to prime the causal filter and smoother."""
    nyq = fs / 2.0
    lo = max(band_hz[0] / nyq, 1e-4)
    hi = min(band_hz[1] / nyq, 0.999)
    b, a = signal.butter(FILTER_ORDER, [lo, hi], btype="bandpass")
    filtered = signal.lfilter(b, a, trials, axis=-1)     # single-pass, causal, batched over leading axes
    envelope = np.abs(filtered)
    pooled = envelope.mean(axis=0).mean(axis=0)           # trials then channels, linear (method a)
    bin_ms = 1000.0 / fs
    smoothed = causal_exp_smooth(pooled, bin_ms=bin_ms, tau_ms=SMOOTH_TAU_MS)

    n_margin = int(round(extraction_margin_s * fs))
    return smoothed[n_margin:], bin_ms


def fit_session_onset(session_prefix: str, probe_letter: str, area: str, band_hz):
    import jnwb.paths as P
    nwb_dir = Path(P.nwb_dir())
    nwb_path = nwb_dir / f"{session_prefix}_rec.nwb"
    if not nwb_path.is_file():
        nwb_path = nwb_dir / f"{session_prefix}.nwb"

    from _l_lfp_common import resolve_area_channel_block
    win_with_margin = (FIT_WIN_S[0] - EXTRACTION_MARGIN_S, FIT_WIN_S[1])
    with h5py.File(nwb_path, "r") as f:
        lfp_key, ch_lo, ch_hi = resolve_area_channel_block(f, probe_letter, area, N_CH_WINDOW)
        trials, fs, n_trials, frac_repaired = extract_epoch_trials(
            f, lfp_key, ch_lo, ch_hi, "RRRR", win_with_margin, MAX_TRIALS)

    envelope, bin_ms = causal_band_envelope_trace(trials, fs, band_hz, EXTRACTION_MARGIN_S)
    n_samples = envelope.shape[0]
    t_ms = FIT_WIN_S[0] * 1000.0 + np.arange(n_samples) * bin_ms

    fit = fit_exponential_onset(t_ms, envelope, t0_bounds=T0_BOUNDS_MS,
                                 baseline_window=(BASELINE_WIN_S[0] * 1000.0, BASELINE_WIN_S[1] * 1000.0))
    fit["n_trials"] = int(n_trials)
    fit["fraction_repaired"] = float(frac_repaired)
    return fit


def session_bootstrap_ci(values: np.ndarray, n_boot=N_BOOT, seed=SEED):
    n = len(values)
    point = float(np.mean(values))
    if n < 2:
        return point, point, point
    rng = np.random.default_rng(seed)
    draws = np.array([values[rng.integers(0, n, size=n)].mean() for _ in range(n_boot)])
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi)


def pairwise_diff_ci(vals_a: np.ndarray, vals_b: np.ndarray, n_boot=N_BOOT, seed=SEED):
    if len(vals_a) < 2 or len(vals_b) < 2:
        mean_diff = float(np.mean(vals_a) - np.mean(vals_b))
        return mean_diff, mean_diff, mean_diff, True   # too few sessions -> not discriminating
    rng = np.random.default_rng(seed)
    na, nb = len(vals_a), len(vals_b)
    draws = np.array([
        vals_a[rng.integers(0, na, size=na)].mean() - vals_b[rng.integers(0, nb, size=nb)].mean()
        for _ in range(n_boot)
    ])
    lo, hi = np.percentile(draws, [2.5, 97.5])
    point = float(np.mean(vals_a) - np.mean(vals_b))
    non_discriminating = bool(lo <= 0.0 <= hi)
    return point, float(lo), float(hi), non_discriminating


def run():
    require_l0_canonical_method()
    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool", "l0_source": str(L0_STATS),
        "causal_pipeline": "single-pass Butterworth bandpass (lfilter, NOT filtfilt) -> "
        "rectify -> pool (trials, channels) -> causal_exp_smooth -> causality-bounded "
        "exponential onset fit. See module docstring for why each step is causal.",
        "ABSOLUTE_T0_WARNING": "Absolute t0 values in this file are shifted by the causal "
        "filter's own group delay plus the smoothing kernel's delay -- confirmed on synthetic "
        "data (self-test): a true injected t0=60ms recovered as fit t0=197ms in absolute terms, "
        "while the LAG between two areas (80ms true) recovered as 83ms, within tolerance. Do "
        "NOT read a single area's t0_ms as a physiological latency in isolation. Only "
        "differences between areas WITHIN THE SAME BAND (same filter, same systematic delay, "
        "so it cancels) are meaningful -- exactly what `pairwise` and `hierarchy_verdict` use.",
        "condition": "stim (RRRR) only", "t0_bounds_ms": list(T0_BOUNDS_MS),
        "baseline_window_s": list(BASELINE_WIN_S), "bands_hz": BANDS, "areas_hierarchy_order": AREAS,
        "ci_method": f"session-level bootstrap on the fitted t0 (n_boot={N_BOOT}, seed={SEED}, "
                      "95% percentile) -- resamples per-session onset ESTIMATES, not trials.",
        "onsets": {}, "pairwise": {}, "hierarchy_verdict": {},
    }
    manifest = {"analysis_id": "L5", "git_sha": git_sha(), "seed": SEED, "n_bootstrap": N_BOOT,
                "extraction_margin_s": EXTRACTION_MARGIN_S, "filter_order": FILTER_ORDER,
                "smooth_tau_ms": SMOOTH_TAU_MS, "sessions_used": {}}

    onset_by_area_band: dict = {}   # (area, band) -> np.array of per-session t0
    for area in AREAS:
        sessions = sessions_for_area(area)
        manifest["sessions_used"][area] = [
            {"session": s, "subject": subj, "probe": p} for s, subj, p in sessions]
        for band_name, band_hz in BANDS.items():
            t0s, meta = [], []
            for session_prefix, subject, probe in sessions:
                try:
                    fit = fit_session_onset(session_prefix, probe, area, band_hz)
                except Exception as e:
                    print(f"  SKIP {area} {band_name} {session_prefix}: {e}")
                    continue
                t0s.append(fit["t0"])
                meta.append({"session": session_prefix, "subject": subject, **fit})
            if not t0s:
                continue
            vals = np.array(t0s)
            point, lo, hi = session_bootstrap_ci(vals)
            onset_by_area_band[(area, band_name)] = vals
            stats["onsets"][f"{area}|{band_name}"] = {
                "area": area, "band": band_name, "n_sessions": len(t0s),
                "t0_ms": point, "ci95_lo_ms": lo, "ci95_hi_ms": hi, "per_session": meta,
            }

    for band_name in BANDS:
        area_pairs = [(a, b) for i, a in enumerate(AREAS) for b in AREAS[i + 1:]]
        pair_rows = {}
        for a1, a2 in area_pairs:
            if (a1, band_name) not in onset_by_area_band or (a2, band_name) not in onset_by_area_band:
                continue
            point, lo, hi, non_disc = pairwise_diff_ci(
                onset_by_area_band[(a1, band_name)], onset_by_area_band[(a2, band_name)])
            pair_rows[f"{a1}-{a2}"] = {
                "area_a": a1, "area_b": a2, "diff_ms": point, "ci95_lo_ms": lo, "ci95_hi_ms": hi,
                "discriminating": not non_disc,
            }
        stats["pairwise"][band_name] = pair_rows

        ranks, onsets = [], []
        for area in AREAS:
            if (area, band_name) in onset_by_area_band:
                ranks.append(HIERARCHY_RANK[area])
                onsets.append(onset_by_area_band[(area, band_name)].mean())
        if len(ranks) >= 4:
            rho, p = scipy_stats.spearmanr(ranks, onsets)
            if p >= 0.05:
                verdict = "H3_simultaneous_or_ambiguous"
            elif rho > 0:
                verdict = "H1_low_to_high_V1_leads"
            else:
                verdict = "H2_high_to_low_FEF_PFC_leads"
            stats["hierarchy_verdict"][band_name] = {
                "n_areas": len(ranks), "rho": float(rho), "p": float(p), "verdict": verdict,
                "note": "H3 requires L6 (volume-conduction control) to disambiguate genuine "
                        "simultaneity from a shared conducted field -- not run here.",
            }
        else:
            stats["hierarchy_verdict"][band_name] = {
                "n_areas": len(ranks), "verdict": "insufficient_data",
                "note": f"need >=4 areas with a fitted onset, got {len(ranks)}",
            }

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L5_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L5_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_figure(stats)
    return stats


def plot_figure(stats: dict):
    figstyle.use_house_style()
    band_names = list(BANDS.keys())
    fig, axes = plt.subplots(1, len(band_names), figsize=(3.2 * len(band_names), 4.2))

    for bi, band in enumerate(band_names):
        ax = axes[bi]
        ys, labels, pts, los, his = [], [], [], [], []
        for area in AREAS:
            key = f"{area}|{band}"
            if key not in stats["onsets"]:
                continue
            d = stats["onsets"][key]
            labels.append(area); pts.append(d["t0_ms"]); los.append(d["t0_ms"] - d["ci95_lo_ms"])
            his.append(d["ci95_hi_ms"] - d["t0_ms"])
        y = np.arange(len(labels))
        colors = [figstyle.AREA_COLORS.get(a, "#333") for a in labels]
        ax.errorbar(pts, y, xerr=[los, his], fmt="o", capsize=3, color="black", ecolor="black",
                    markersize=0)
        ax.scatter(pts, y, c=colors, s=40, zorder=3)
        ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()
        verdict = stats["hierarchy_verdict"].get(band, {}).get("verdict", "n/a")
        rho = stats["hierarchy_verdict"].get(band, {}).get("rho")
        title = f"{band}\n{verdict}" + (f" (rho={rho:.2f})" if rho is not None else "")
        ax.set_title(title, fontsize=7.5)
        ax.set_xlabel("Onset t0 (ms from p1)", fontsize=7)
        ax.tick_params(labelsize=6.5)
        ax.axvline(0, color="#999999", linewidth=0.6)

    fig.suptitle("L5: cross-area LFP onset latency (stim), causal pipeline, "
                 "session-bootstrap 95% CI, ordered by cortical hierarchy\n"
                 "Absolute t0 is shifted by filter+smoothing group delay -- read RELATIVE "
                 "(cross-area, same-band) position only, see L5_stats.json", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    figstyle.save(fig, FIG_DIR, "L5")
    fig.savefig(FIG_DIR / "L5.pdf")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """(a) A known injected onset LAG between two synthetic 'areas' must be recovered within
    tolerance. (b) A synthetic ZERO-LAG case (identical true onset for every area) must return
    discriminating: false for every pair -- the spec's own explicit acceptance test."""
    rng = np.random.default_rng(0)
    fs = 500.0
    n_trials, n_ch = 30, 8
    band_hz = BANDS["alpha"]
    margin_n = int(round(EXTRACTION_MARGIN_S * fs))
    win_n = int(round((FIT_WIN_S[1] - FIT_WIN_S[0]) * fs)) + margin_n
    t_full = np.arange(win_n) / fs + (FIT_WIN_S[0] - EXTRACTION_MARGIN_S)

    def make_trials(true_t0_ms, amp=3.0, tau_ms=25.0, band_center_hz=11.0):
        from jnwb.onset_fitting import onset_model  # promoted 2026-08-23
        envelope_true = onset_model(t_full * 1000.0, true_t0_ms, tau_ms, amp, 0.5)
        envelope_true = np.clip(envelope_true, 0, None)
        carrier = np.sin(2 * np.pi * band_center_hz * t_full)
        base = envelope_true * carrier
        trials = base[None, None, :] + rng.normal(0, 0.3, size=(n_trials, n_ch, win_n))
        return trials

    # (a) injected lag: area A onset at 60ms, area B onset at 140ms -- must recover ~80ms gap.
    trials_a = make_trials(60.0)
    trials_b = make_trials(140.0)
    env_a, bin_ms = causal_band_envelope_trace(trials_a, fs, band_hz, EXTRACTION_MARGIN_S)
    env_b, _ = causal_band_envelope_trace(trials_b, fs, band_hz, EXTRACTION_MARGIN_S)
    t_ms = FIT_WIN_S[0] * 1000.0 + np.arange(env_a.shape[0]) * bin_ms
    fit_a = fit_exponential_onset(t_ms, env_a, t0_bounds=T0_BOUNDS_MS,
                                   baseline_window=(BASELINE_WIN_S[0] * 1000, BASELINE_WIN_S[1] * 1000))
    fit_b = fit_exponential_onset(t_ms, env_b, t0_bounds=T0_BOUNDS_MS,
                                   baseline_window=(BASELINE_WIN_S[0] * 1000, BASELINE_WIN_S[1] * 1000))
    recovered_lag = fit_b["t0"] - fit_a["t0"]
    print(f"Injected lag test: true=80.0ms recovered={recovered_lag:.1f}ms "
          f"(fit_a t0={fit_a['t0']:.1f}, fit_b t0={fit_b['t0']:.1f})")
    assert abs(recovered_lag - 80.0) < 2 * SMOOTH_TAU_MS, (
        f"lag recovery error too large: {abs(recovered_lag - 80.0):.1f}ms")
    print("PASS: injected onset lag recovered within tolerance.")

    # (b) zero-lag case: bootstrap the SAME true-t0 signal into two independent session sets and
    # confirm the pairwise CI includes zero -> discriminating: false.
    t0_true = 90.0
    sessions_x = [make_trials(t0_true) for _ in range(4)]
    sessions_y = [make_trials(t0_true) for _ in range(4)]
    fits_x, fits_y = [], []
    for tr in sessions_x:
        env, _ = causal_band_envelope_trace(tr, fs, band_hz, EXTRACTION_MARGIN_S)
        fits_x.append(fit_exponential_onset(t_ms, env, t0_bounds=T0_BOUNDS_MS,
                       baseline_window=(BASELINE_WIN_S[0] * 1000, BASELINE_WIN_S[1] * 1000))["t0"])
    for tr in sessions_y:
        env, _ = causal_band_envelope_trace(tr, fs, band_hz, EXTRACTION_MARGIN_S)
        fits_y.append(fit_exponential_onset(t_ms, env, t0_bounds=T0_BOUNDS_MS,
                       baseline_window=(BASELINE_WIN_S[0] * 1000, BASELINE_WIN_S[1] * 1000))["t0"])
    point, lo, hi, non_disc = pairwise_diff_ci(np.array(fits_x), np.array(fits_y), n_boot=2000, seed=1)
    print(f"Zero-lag test: diff={point:.1f}ms CI=[{lo:.1f}, {hi:.1f}] non_discriminating={non_disc}")
    assert non_disc, "zero-lag case should be non-discriminating (CI must include 0)"
    print("PASS: zero-lag case correctly returns discriminating=false.")

    # Determinism.
    point2, lo2, hi2, _ = pairwise_diff_ci(np.array(fits_x), np.array(fits_y), n_boot=2000, seed=1)
    assert lo == lo2 and hi == hi2, "determinism check failed"
    print("PASS: determinism check.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for key, d in stats["onsets"].items():
        print(f"{key}: n_sessions={d['n_sessions']} t0={d['t0_ms']:.1f}ms "
              f"[{d['ci95_lo_ms']:.1f}, {d['ci95_hi_ms']:.1f}]")
    for band, v in stats["hierarchy_verdict"].items():
        print(f"{band}: {v['verdict']}")


if __name__ == "__main__":
    main()
