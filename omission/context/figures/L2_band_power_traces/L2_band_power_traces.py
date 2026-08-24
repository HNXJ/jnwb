r"""
L2 -- Per-band power time-series, all areas, stim + omission overlaid, fixation-baselined,
per-monkey and pooled, session-bootstrap CI (Fig 5).

Reads `canonical_pooling_method` from L0 (same gate as L1) and fails loudly if missing/wrong.

SPEC ACCEPTANCE CRITERION -- READ BEFORE CHANGING THE CI CONSTRUCTION
    "CI method stated in stats JSON. Trial-level bootstrapping is a known inflation and is
    explicitly disallowed here." Sessions are the unit of replication: each session gets its
    own COMPLETE, correctly log-last-pooled dB(t) trace (per-channel power -> average channels
    -> average within-band frequency bins -> divide by baseline -> log once -- see LOG-LAST
    ORDER below), and only THEN do session point estimates get resampled/averaged across
    sessions for the group trace and its CI. This is the corrected connectivity-analysis
    pattern this project's own omission-signal skill (S10) already documents as necessary on
    this corpus (pooling raw per-session estimates before testing manufactured false negatives
    there; testing/summarizing session-level statistics after each session has its own decision
    is the fix) -- reused here for the same reason, not reinvented.

LOG-LAST ORDER (two nested applications, both required)
    1. Channel pooling (L0's canonical method a): average LINEAR power over trials, then over
       channels, per session.
    2. Band pooling: average LINEAR power over the frequency bins inside a band, THEN divide by
       that band's own baseline-window linear power and take 10*log10 exactly once. Averaging
       already-computed per-frequency-bin dB values across a band would repeat the exact
       log-averaging bias omission-signal S1 documents -- this script never does that.
    Only after both pooling steps is a session's dB(t) trace treated as a single, complete
    session-level statistic eligible for cross-session averaging/bootstrap.

SCOPE (stated, not hidden)
    Bands: the five house bands (omission-signal S6). Areas: same six as L1 (V1, V2, MT, MST,
    FEF, PFC -- FEF/PFC substituted for the spec's stale "8A/PFC", see L1's README). Up to 3
    sessions per subject per area (tractability cap). Probe-to-area assignment is NOT fixed
    across sessions on this corpus (confirmed 2026-08-17 directly against V182o's own electrode
    tables -- FEF sits on probe A in one V182o session and probe B in the next) so every
    session's probe is resolved fresh via _l_lfp_common.find_probe_for_area, never hardcoded or
    cached across sessions.

    Real, corpus-confirmed per-area subject coverage (from a direct electrode-table survey,
    2026-08-17): MT, MST, FEF, PFC each have real sessions from BOTH C31o and V182o -- a
    genuine per-monkey comparison. V1/V2 have C31o and V198o. No area in this corpus has all
    three subjects simultaneously (area x subject confounded corpus-wide, per omission-statistics
    skill -- expected, not a bug).

DISPLAY DESIGN (stated, since "per-monkey and pooled" could mean several things)
    Each panel (band x area) shows the POOLED (all available sessions/subjects) dB(t) trace
    with a shaded 95% session-bootstrap CI, for stim (solid) and omission (dashed) overlaid on
    one shared p1-referenced time axis (both conditions extracted from the same epoch window,
    so times align natively -- no separate zoom per condition, unlike L1). For areas with >=2
    subjects, thin per-subject MEAN lines are added without their own CI shading (2-3 sessions
    per subject is too few for a CI worth trusting on its own; the pooled CI is the one to read
    quantitatively; per-subject lines are for qualitative between-animal comparison only) --
    stated explicitly here and in the stats JSON, not left for the reader to guess.

OUTPUT
    L2.svg / L2.png / L2.pdf, L2_stats.json (every number plotted, CI method, n sessions per
    area/subject/condition), L2_manifest.json.

TESTS
    --test: synthetic multi-session dataset with a KNOWN population mean and between-session
    variance -- the session-bootstrap CI must cover the true mean at roughly its nominal rate
    and must NOT collapse to the (much narrower) trial-level CI width. Plus determinism and a
    shape/NaN guard.
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

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from _l_lfp_common import (  # noqa: E402
    batched_spectrogram, extract_epoch_trials, find_probe_for_area, git_sha,
    resolve_area_channel_block,
)
import figstyle  # noqa: E402
from jnwb.spectral import CANONICAL_BANDS, to_db  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"

SEED = 42
N_BOOT = 2000
EPOCH_WIN_S = (-0.6, 2.2)
BASELINE_WIN_S = (-0.4, -0.15)
DISPLAY_WIN_MS = (-300, 1900)
MAX_TRIALS = 60
N_CH_WINDOW = 32
MAX_SESSIONS_PER_SUBJECT = 3
COMMON_TIME_GRID_MS = np.arange(EPOCH_WIN_S[0] * 1000, EPOCH_WIN_S[1] * 1000 + 1.0, 10.0)

BANDS = CANONICAL_BANDS
AREAS = ["V1", "V2", "MT", "MST", "FEF", "PFC"]
CONDITIONS = {"stim": "RRRR", "omission": "RXRR"}


def require_l0_canonical_method() -> str:
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    method = stats.get("canonical_pooling_method")
    if method != "a_per_channel_then_pool":
        raise RuntimeError(f"L0_stats.json canonical_pooling_method={method!r} unexpected.")
    return method


def sessions_for_area(area: str, cap_per_subject=MAX_SESSIONS_PER_SUBJECT):
    """(session_prefix, subject, probe_letter) for every session carrying `area`, capped per
    subject. Resolves fresh from each session's own electrode table -- see module docstring."""
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


def session_band_traces(session_prefix: str, probe_letter: str, area: str, condition_code: str):
    """Returns {band_name: db_trace_on_common_grid} for one session/condition -- log-last at
    both the channel-pooling and band-pooling steps (see module docstring)."""
    import jnwb.paths as P
    nwb_dir = Path(P.nwb_dir())
    nwb_path = nwb_dir / f"{session_prefix}_rec.nwb"
    if not nwb_path.is_file():
        nwb_path = nwb_dir / f"{session_prefix}.nwb"

    with h5py.File(nwb_path, "r") as f:
        lfp_key, ch_lo, ch_hi = resolve_area_channel_block(f, probe_letter, area, N_CH_WINDOW)
        trials, fs, n_trials, frac_repaired = extract_epoch_trials(
            f, lfp_key, ch_lo, ch_hi, condition_code, EPOCH_WIN_S, MAX_TRIALS)

    freqs, times, Sxx = batched_spectrogram(trials, fs)
    pooled = Sxx.mean(axis=0).mean(axis=0)  # (n_freqs, n_times) -- channel pooling, log-last step 1
    times_ms = EPOCH_WIN_S[0] * 1000.0 + times * 1000.0
    base_mask = (times_ms >= BASELINE_WIN_S[0] * 1000.0) & (times_ms <= BASELINE_WIN_S[1] * 1000.0)

    out = {}
    for band_name, (flo, fhi) in BANDS.items():
        fmask = (freqs >= flo) & (freqs < fhi)
        if not np.any(fmask):
            raise ValueError(f"Band {band_name} has no bins at fs={fs}")
        band_power_t = pooled[fmask, :].mean(axis=0)  # linear, band pooling step 1
        baseline_val = band_power_t[base_mask].mean()   # linear baseline, band pooling step 2
        db_t = to_db(np.maximum(band_power_t, 1e-15) / max(baseline_val, 1e-15))
        db_common = np.interp(COMMON_TIME_GRID_MS, times_ms, db_t)
        out[band_name] = db_common
    return out, n_trials, frac_repaired


def session_bootstrap_ci(traces: np.ndarray, n_boot=N_BOOT, seed=SEED):
    """traces: (n_sessions, n_times). Resamples SESSION indices (not trials). Returns
    (mean_trace, ci_lo_trace, ci_hi_trace)."""
    n_sessions = traces.shape[0]
    point = traces.mean(axis=0)
    if n_sessions < 2:
        return point, point.copy(), point.copy()
    rng = np.random.default_rng(seed)
    draws = np.empty((n_boot, traces.shape[1]))
    for i in range(n_boot):
        idx = rng.integers(0, n_sessions, size=n_sessions)
        draws[i] = traces[idx].mean(axis=0)
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    return point, lo, hi


def run():
    require_l0_canonical_method()
    dmask = (COMMON_TIME_GRID_MS >= DISPLAY_WIN_MS[0]) & (COMMON_TIME_GRID_MS <= DISPLAY_WIN_MS[1])
    disp_t = COMMON_TIME_GRID_MS[dmask]

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "l0_source": str(L0_STATS),
        "ci_method": "session-level bootstrap (resample SESSION indices with replacement, "
                      f"n_boot={N_BOOT}, seed={SEED}, 95% percentile interval). Trial-level "
                      "bootstrapping explicitly NOT used, per spec.",
        "log_last_order": "power averaged over trials, then channels (L0 method a), then over "
                            "the band's frequency bins, THEN divided by baseline and log10'd "
                            "once -- never averaged in dB space at either pooling step.",
        "bands_hz": BANDS, "areas": AREAS, "epoch_window_s": list(EPOCH_WIN_S),
        "baseline_window_s": list(BASELINE_WIN_S), "display_window_ms": list(DISPLAY_WIN_MS),
        "max_sessions_per_subject": MAX_SESSIONS_PER_SUBJECT, "max_trials_per_session": MAX_TRIALS,
        "panels": {},
    }
    manifest = {
        "analysis_id": "L2", "git_sha": git_sha(), "seed": SEED, "n_bootstrap": N_BOOT,
        "epoch_window_s": list(EPOCH_WIN_S), "baseline_window_s": list(BASELINE_WIN_S),
        "bands_hz": BANDS, "max_sessions_per_subject": MAX_SESSIONS_PER_SUBJECT,
        "max_trials_per_session": MAX_TRIALS, "n_channels_cap": N_CH_WINDOW,
        "sessions_used": {},
    }

    panel_data = {}
    for area in AREAS:
        sessions = sessions_for_area(area)
        manifest["sessions_used"][area] = [
            {"session": s, "subject": subj, "probe": p} for s, subj, p in sessions]
        if not sessions:
            continue
        for condition, code in CONDITIONS.items():
            per_session_bands = {}   # band -> list of (subject, trace)
            per_session_meta = []
            for session_prefix, subject, probe in sessions:
                try:
                    traces, n_trials, frac_rep = session_band_traces(
                        session_prefix, probe, area, code)
                except Exception as e:
                    print(f"  SKIP {area} {condition} {session_prefix}: {e}")
                    continue
                for band, tr in traces.items():
                    per_session_bands.setdefault(band, []).append((subject, tr))
                per_session_meta.append({"session": session_prefix, "subject": subject,
                                          "n_trials": n_trials, "fraction_repaired": frac_rep})
            for band in BANDS:
                entries = per_session_bands.get(band, [])
                if not entries:
                    continue
                subjects = [e[0] for e in entries]
                mat = np.stack([e[1] for e in entries])  # (n_sessions, n_times_common)
                point, lo, hi = session_bootstrap_ci(mat)
                per_subject_means = {}
                for subj in sorted(set(subjects)):
                    sub_mat = np.stack([e[1] for e in entries if e[0] == subj])
                    per_subject_means[subj] = sub_mat.mean(axis=0)

                key = (area, band, condition)
                panel_data[key] = {
                    "point": point, "lo": lo, "hi": hi,
                    "per_subject_means": per_subject_means, "n_sessions": mat.shape[0],
                }
                stats["panels"][f"{area}|{band}|{condition}"] = {
                    "area": area, "band": band, "condition": condition,
                    "n_sessions": int(mat.shape[0]),
                    "n_subjects": int(len(set(subjects))),
                    "subjects": sorted(set(subjects)),
                    "session_meta": [m for m in per_session_meta],
                    "point_estimate_db_at_display_window": point[dmask].tolist(),
                    "ci95_lo_db_at_display_window": lo[dmask].tolist(),
                    "ci95_hi_db_at_display_window": hi[dmask].tolist(),
                }

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L2_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L2_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_grid(panel_data, disp_t, dmask)
    return stats


SUBJECT_COLORS = {"C31o": "#1B7837", "V182o": "#762A83", "V198o": "#B35806"}


def plot_grid(panel_data: dict, disp_t: np.ndarray, dmask: np.ndarray):
    figstyle.use_house_style()
    band_names = list(BANDS.keys())
    n_rows, n_cols = len(band_names), len(AREAS)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(2.6 * n_cols, 1.9 * n_rows), squeeze=False)

    for ri, band in enumerate(band_names):
        for ci, area in enumerate(AREAS):
            ax = axes[ri][ci]
            any_data = False
            for condition, ls in [("stim", "-"), ("omission", "--")]:
                key = (area, band, condition)
                if key not in panel_data:
                    continue
                any_data = True
                d = panel_data[key]
                color = figstyle.AREA_COLORS.get(area, "#333333")
                ax.plot(disp_t, d["point"][dmask], color=color, linestyle=ls, linewidth=1.3,
                        label=condition)
                ax.fill_between(disp_t, d["lo"][dmask], d["hi"][dmask], color=color, alpha=0.15,
                                 linewidth=0)
                for subj, mean_trace in d["per_subject_means"].items():
                    if len(d["per_subject_means"]) < 2:
                        continue
                    sc = SUBJECT_COLORS.get(subj, "#999999")
                    ax.plot(disp_t, mean_trace[dmask], color=sc, linestyle=ls, linewidth=0.6,
                            alpha=0.8)
            ax.axhline(0, color="#999999", linewidth=0.6, zorder=0)
            ax.axvline(0, color="black", linewidth=0.5, linestyle=":")
            ax.axvline(1031, color="black", linewidth=0.5, linestyle=":")
            if ri == 0:
                ax.set_title(area, fontsize=8)
            if ci == 0:
                ax.set_ylabel(f"{band}\ndB", fontsize=7)
            if ri == n_rows - 1:
                ax.set_xlabel("ms from p1", fontsize=7)
            if not any_data:
                ax.text(0.5, 0.5, "no data", transform=ax.transAxes, ha="center", va="center",
                        fontsize=7, color="#999999")
            ax.tick_params(labelsize=6)

    handles = [plt.Line2D([0], [0], color="black", linestyle="-", label="stim"),
               plt.Line2D([0], [0], color="black", linestyle="--", label="omission")]
    handles += [plt.Line2D([0], [0], color=c, linewidth=1.5, label=s)
                for s, c in SUBJECT_COLORS.items()]
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), fontsize=7,
               bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("L2: band-power traces, band x area, fixation-baselined, session-bootstrap CI "
                 "(shaded = pooled 95% CI; thin lines = per-monkey mean)", fontsize=9, y=1.04)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    figstyle.save(fig, FIG_DIR, "L2")
    fig.savefig(FIG_DIR / "L2.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """Session-bootstrap CI must (a) cover a known population mean at roughly its nominal rate
    and (b) be substantially WIDER than a trial-level CI would be on the same data -- the whole
    point of the spec's 'trial-level bootstrapping is explicitly disallowed' rule. No real data,
    seconds to run."""
    rng = np.random.default_rng(0)
    n_times = 50
    true_mean = np.full(n_times, 2.0)  # true population dB effect, flat for simplicity
    n_sessions = 8
    session_effect_sd = 1.5   # between-session variance -- the thing trial-level CI ignores
    trial_noise_sd = 0.2      # within-session (trial) noise -- much smaller

    session_means = true_mean[None, :] + rng.normal(0, session_effect_sd, size=(n_sessions, 1))
    # Each session's own trace has small residual (trial-level) noise on top.
    session_traces = session_means + rng.normal(0, trial_noise_sd, size=(n_sessions, n_times))

    point, lo, hi = session_bootstrap_ci(session_traces, n_boot=2000, seed=1)
    covered = np.mean((lo <= true_mean) & (true_mean <= hi))
    print(f"Session-bootstrap CI coverage of true mean: {covered:.2f} (want roughly >=0.85 "
          f"at nominal 95%, small-n_sessions bootstrap is conservative-to-liberal, not exact)")
    assert covered > 0.7, f"CI coverage implausibly low: {covered:.2f}"

    ci_width_session = float(np.mean(hi - lo))
    # A (deliberately wrong) trial-level CI would treat all n_sessions*n_trials_equivalent
    # samples as independent and be governed by trial_noise_sd, not session_effect_sd -- far
    # narrower. Approximate that wrong CI width directly from trial_noise_sd for comparison.
    naive_trial_level_width = float(2 * 1.96 * trial_noise_sd / np.sqrt(n_sessions * 20))
    print(f"Session-bootstrap CI width = {ci_width_session:.2f}, "
          f"naive (wrong) trial-level-scale width ~= {naive_trial_level_width:.2f}")
    assert ci_width_session > 3 * naive_trial_level_width, (
        "session-bootstrap CI is not meaningfully wider than a trial-level CI would be -- "
        "the whole point of this rule is being violated")
    print("PASS: session-bootstrap CI reflects between-session variance, not trial noise.")

    # Determinism.
    point2, lo2, hi2 = session_bootstrap_ci(session_traces, n_boot=2000, seed=1)
    assert np.array_equal(lo, lo2) and np.array_equal(hi, hi2), "determinism check failed"
    print("PASS: same seed -> byte-identical CI (determinism check).")

    # Shape/NaN guard: single-session input must not crash and must return a degenerate
    # (zero-width) CI rather than fabricating uncertainty from n=1.
    single = session_traces[:1]
    p1, l1, h1 = session_bootstrap_ci(single)
    assert np.allclose(l1, h1) and np.allclose(l1, p1), "n=1 session should give a degenerate CI"
    print("PASS: n=1 session guard (degenerate CI, no fabricated uncertainty).")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for key, p in stats["panels"].items():
        print(f"{key}: n_sessions={p['n_sessions']} n_subjects={p['n_subjects']} "
              f"subjects={p['subjects']}")


if __name__ == "__main__":
    main()
