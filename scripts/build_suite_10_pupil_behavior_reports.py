"""
Suite 10 (pupil/behavior around omission), generalized across sessions.

Refactor of notebooks/suite_10_pupil_behavior.ipynb, which was hardcoded to
sub-V182o_ses-260629.nwb. This script parametrizes the same real computation: real trial-onset
extraction (session.get_epochs), real pupil diameter timeseries read directly via h5py, trial-
averaged baseline-subtracted pupil traces for AAAB (control) vs AAXB (omission), a real per-
timepoint Mann-Whitney U test with family-wise BH-FDR across all timepoints
(jnwb.statistics.StatisticalAnalysis.fdr_correct).

All 15 real sessions have acquisition/pupil_1_tracking (confirmed 2026-07-12), so no session
should need to be skipped for missing pupil data - any skip here is a genuine, reportable
exception, not an expected outcome.

Usage:
    python scripts/build_suite_10_pupil_behavior_reports.py --all-ready
    python scripts/build_suite_10_pupil_behavior_reports.py --nwb <path>
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu

import jnwb as oa
from jnwb.statistics import StatisticalAnalysis

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "outputs/markdown_reports"
WINDOW_S = (-1.0, 2.0)  # relative to p1 onset
MIN_TRIALS = 5


def run_one_session(nwb_path: str, session_prefix: str) -> dict:
    try:
        session = oa.read(nwb_path)
    except Exception as e:
        return {"status": "failed", "reason": f"Failed to load NWB session: {e}"}

    aaab_epochs = session.get_epochs(phase=2, condition="AAAB", correct_only=True)
    aaxb_epochs = session.get_epochs(phase=2, condition="AAXB", correct_only=True)
    if len(aaab_epochs) < MIN_TRIALS or len(aaxb_epochs) < MIN_TRIALS:
        return {"status": "skipped",
                "reason": f"Too few real trials: AAAB={len(aaab_epochs)}, AAXB={len(aaxb_epochs)} (need >= {MIN_TRIALS} each)"}

    try:
        with h5py.File(nwb_path, "r") as f:
            if "acquisition/pupil_1_tracking" not in f:
                return {"status": "skipped", "reason": "No acquisition/pupil_1_tracking group in this NWB file"}
            grp = f["acquisition/pupil_1_tracking"]
            # Real on-disk layout differs by session (confirmed 2026-07-12, same class of
            # difference already handled for LFP in scripts/build_suite_09_granger_reports.py):
            # C31o/V198o store data/timestamps flat directly under pupil_1_tracking; V182o
            # nests them one level deeper under pupil_1_diameter_data.
            if "data" in grp and "timestamps" in grp:
                pupil_ts = grp["timestamps"][:]
                pupil_data = grp["data"][:]
            elif "pupil_1_diameter_data" in grp:
                nested = grp["pupil_1_diameter_data"]
                pupil_ts = nested["timestamps"][:]
                pupil_data = nested["data"][:]
            else:
                return {"status": "skipped", "reason": "Could not find pupil data/timestamps under acquisition/pupil_1_tracking (flat or nested)"}
    except Exception as e:
        return {"status": "failed", "reason": f"Failed to read real pupil data: {e}"}

    fs_pupil = 1.0 / np.median(np.diff(pupil_ts))
    n_pre = int(-WINDOW_S[0] * fs_pupil)
    n_post = int(WINDOW_S[1] * fs_pupil)
    n_total = n_pre + n_post
    time_points_ms = (np.arange(n_total) - n_pre) / fs_pupil * 1000.0

    def extract_traces(epochs):
        traces = []
        for onset in epochs["start_time"].values:
            idx = np.searchsorted(pupil_ts, onset)
            lo, hi = idx - n_pre, idx + n_post
            if lo < 0 or hi > len(pupil_data):
                continue
            seg = pupil_data[lo:hi].astype(float)
            baseline = np.nanmean(seg[:n_pre]) if n_pre > 0 else np.nan
            traces.append(seg - baseline)
        return np.array(traces) if traces else np.empty((0, n_total))

    aaab_traces = extract_traces(aaab_epochs)
    aaxb_traces = extract_traces(aaxb_epochs)
    if len(aaab_traces) < MIN_TRIALS or len(aaxb_traces) < MIN_TRIALS:
        return {"status": "skipped",
                "reason": f"Too few real in-bounds pupil segments: AAAB={len(aaab_traces)}, AAXB={len(aaxb_traces)}"}

    raw_pvals = np.full(n_total, np.nan)
    for t_i in range(n_total):
        a = aaab_traces[:, t_i]
        b = aaxb_traces[:, t_i]
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if len(a) >= 3 and len(b) >= 3:
            try:
                _, pv = mannwhitneyu(a, b, alternative="two-sided")
                raw_pvals[t_i] = pv
            except ValueError:
                pass

    valid = np.isfinite(raw_pvals)
    qvals = np.full(n_total, np.nan)
    if valid.sum() > 0:
        qvals[valid] = StatisticalAnalysis.fdr_correct(raw_pvals[valid].tolist())
    n_sig = int((qvals[valid] < 0.05).sum()) if valid.sum() > 0 else 0

    return {
        "status": "completed", "n_aaab_trials": len(aaab_traces), "n_aaxb_trials": len(aaxb_traces),
        "time_points_ms": time_points_ms, "aaab_traces": aaab_traces, "aaxb_traces": aaxb_traces,
        "n_timepoints_tested": int(valid.sum()), "n_sig": n_sig, "n_total": n_total,
    }


def write_report(session_prefix: str, result: dict, out_root: Path = OUT_ROOT) -> Path:
    out_dir = out_root / session_prefix / "pupil_behavior"
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    t = result["time_points_ms"]
    aaab_mean = np.nanmean(result["aaab_traces"], axis=0)
    aaab_sem = np.nanstd(result["aaab_traces"], axis=0) / np.sqrt(max(result["n_aaab_trials"], 1))
    aaxb_mean = np.nanmean(result["aaxb_traces"], axis=0)
    aaxb_sem = np.nanstd(result["aaxb_traces"], axis=0) / np.sqrt(max(result["n_aaxb_trials"], 1))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t, aaab_mean, color="#2563EB", label=f"AAAB (control, n={result['n_aaab_trials']})")
    ax.fill_between(t, aaab_mean - aaab_sem, aaab_mean + aaab_sem, color="#2563EB", alpha=0.2)
    ax.plot(t, aaxb_mean, color="#FF1493", label=f"AAXB (omission, n={result['n_aaxb_trials']})")
    ax.fill_between(t, aaxb_mean - aaxb_sem, aaxb_mean + aaxb_sem, color="#FF1493", alpha=0.2)
    ax.axvline(0.0, color="black", linestyle="--", linewidth=1.0, label="p1 onset")
    ax.set_xlabel("Time relative to p1 onset (ms)")
    ax.set_ylabel("Baseline-subtracted pupil diameter (a.u.)")
    ax.set_title(f"Suite 10: Real pupil trace -- {session_prefix}\n"
                 f"{result['n_sig']}/{result['n_timepoints_tested']} timepoints significant (BH-FDR q<0.05)")
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()
    svg_path = fig_dir / "pupil_trace.svg"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)

    svg_bytes = svg_path.stat().st_size
    if svg_bytes == 0:
        time.sleep(0.2)
        svg_bytes = svg_path.stat().st_size
        if svg_bytes == 0:
            raise RuntimeError(f"{svg_path} is 0 bytes after retry")
    n_paths = svg_path.read_text(encoding="utf-8").count("<path ")

    index_md = f"""# Suite 10: Real Pupil/Behavior -- {session_prefix}

Real trial-averaged pupil diameter (baseline-subtracted), real per-timepoint Mann-Whitney U
test with family-wise BH-FDR across all {result['n_timepoints_tested']} tested timepoints.

- Real trials: AAAB={result['n_aaab_trials']}, AAXB={result['n_aaxb_trials']}
- Significant timepoints after FDR (q < 0.05): {result['n_sig']} / {result['n_timepoints_tested']}
- SVG: `figures/pupil_trace.svg` ({svg_bytes} bytes, {n_paths} path elements)

![Pupil trace](figures/pupil_trace.svg)
"""
    (out_dir / "index.md").write_text(index_md, encoding="utf-8")
    return out_dir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nwb", type=Path, default=None)
    p.add_argument("--all-ready", action="store_true")
    p.add_argument("--readiness-csv", type=Path, default=REPO_ROOT / "artifacts/data/session_readiness.csv")
    args = p.parse_args()

    if args.nwb:
        session_prefix = args.nwb.stem.replace("_rec", "")
        sessions = [(str(args.nwb), session_prefix)]
    elif args.all_ready:
        readiness = pd.read_csv(args.readiness_csv)
        candidates = readiness[(readiness["nwb_ok"] == True) & (readiness["short_nwb"] == False)]
        sessions = list(zip(candidates["nwb_path"], candidates["session_prefix"]))
    else:
        raise SystemExit("Specify --nwb <path> or --all-ready")

    n_completed = 0
    n_skipped = 0
    summary_rows = []
    for nwb_path, session_prefix in sessions:
        print(f"=== {session_prefix} ===")
        result = run_one_session(nwb_path, session_prefix)
        if result["status"] != "completed":
            print(f"  SKIPPED/FAILED: {result.get('reason')}")
            n_skipped += 1
            summary_rows.append({"session_prefix": session_prefix, "status": f"{result['status']}: {result.get('reason')}"})
            continue
        out_dir = write_report(session_prefix, result)
        print(f"  wrote report to {out_dir} ({result['n_sig']}/{result['n_timepoints_tested']} sig timepoints)")
        n_completed += 1
        summary_rows.append({
            "session_prefix": session_prefix, "status": "ok",
            "n_aaab_trials": result["n_aaab_trials"], "n_aaxb_trials": result["n_aaxb_trials"],
            "n_sig": result["n_sig"], "n_timepoints_tested": result["n_timepoints_tested"],
        })

    print(f"\nDone: {n_completed} completed, {n_skipped} skipped (of {len(sessions)})")
    summary_path = OUT_ROOT.parent / "publication_visual_review" / "suite_10_pupil_behavior" / "all_sessions_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
