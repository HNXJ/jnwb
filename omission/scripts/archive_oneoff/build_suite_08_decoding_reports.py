"""
Suite 08 (sliding-window omission decoding), generalized across sessions.

Refactor of notebooks/suite_08_omission_decoding.ipynb, which tried sub-C31o_ses-230823_rec.nwb
then fell back to sub-V182o_ses-260629.nwb, both hardcoded to area='FEF'. This script picks a
real, available area per session (the highest-unit-count area with >= MIN_UNITS real units,
verified per session rather than assuming FEF exists everywhere) and runs the same real
sliding-window omission.jnwb_ext.decoding.decode_omission_presence pipeline (nested-CV SVM, 5-fold).

Each window is a full nested-CV SVM fit (~1-2 minutes per window per the original notebook's
own estimate), so this is deliberately kept to a modest window count, matching the original.

Usage:
    python scripts/build_suite_08_decoding_reports.py --all-ready
    python scripts/build_suite_08_decoding_reports.py --nwb <path>
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import omission as oa
from omission.jnwb_ext.decoding import decode_omission_presence

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "outputs/markdown_reports"
WINDOW_STARTS_MS = [-450.0, -300.0, -150.0, 0.0, 150.0, 300.0, 450.0]
WINDOW_WIDTH_MS = 150.0
MIN_UNITS = 5


def pick_area(session) -> Optional[str]:
    units = session.get_units()
    if "area" not in units.columns:
        return None
    counts = units["area"].value_counts()
    counts = counts[counts >= MIN_UNITS]
    if len(counts) == 0:
        return None
    return str(counts.index[0])


def run_one_session(nwb_path: str, session_prefix: str) -> dict:
    try:
        session = oa.read(nwb_path)
    except Exception as e:
        return {"status": "failed", "reason": f"Failed to load NWB session: {e}"}

    area = pick_area(session)
    if area is None:
        return {"status": "skipped", "reason": f"No area with >= {MIN_UNITS} real units for this session"}

    rows = []
    for start_ms in WINDOW_STARTS_MS:
        window = (start_ms, start_ms + WINDOW_WIDTH_MS)
        try:
            res = decode_omission_presence(session, area=area, time_window_ms=window, n_splits=5)
        except Exception as e:
            return {"status": "failed", "reason": f"decode_omission_presence failed for window {window}: {e}"}
        rows.append({
            "window_start_ms": start_ms, "window_center_ms": start_ms + WINDOW_WIDTH_MS / 2.0,
            "accuracy": res["accuracy"], "f1": res["f1"], "auc": res["auc"],
            "majority_baseline_accuracy": res["majority_baseline_accuracy"],
        })

    results_df = pd.DataFrame(rows)
    return {"status": "completed", "area": area, "results_df": results_df}


def write_report(session_prefix: str, result: dict, out_root: Path = OUT_ROOT) -> Path:
    out_dir = out_root / session_prefix / "omission_decoding"
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = result["results_df"]
    area = result["area"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), sharex=True)
    ax1.plot(df["window_center_ms"], df["accuracy"], color="#0000FF", marker="o", linewidth=2.0,
              label="SVM accuracy (real, nested CV)")
    ax1.plot(df["window_center_ms"], df["majority_baseline_accuracy"], color="#888888", marker="s",
              linestyle="--", linewidth=1.5, label="Majority-class baseline (per-fold)")
    ax1.axvline(0, color="purple", linestyle="--", label="Omission window onset")
    ax1.set_ylabel("Accuracy")
    ax1.set_title(f"Suite 08: Standard (AAAB) vs. Omission (AAXB) decoding, area={area} -- {session_prefix}")
    ax1.legend(loc="lower right", fontsize=8)
    ax1.grid(True, linestyle=":", alpha=0.5)

    ax2.plot(df["window_center_ms"], df["f1"], color="#D55E00", marker="o", linewidth=2.0, label="F1")
    ax2.plot(df["window_center_ms"], df["auc"], color="#009E73", marker="^", linewidth=2.0, label="AUC")
    ax2.axhline(0.5, color="gray", linestyle=":", label="Chance (AUC=0.5)")
    ax2.set_xlabel("Time relative to omission onset (ms)")
    ax2.set_ylabel("F1 / AUC")
    ax2.legend(loc="lower right", fontsize=8)
    ax2.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()

    svg_path = fig_dir / "decoding_timecourse.svg"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)

    svg_bytes = svg_path.stat().st_size
    if svg_bytes == 0:
        time.sleep(0.2)
        svg_bytes = svg_path.stat().st_size
        if svg_bytes == 0:
            raise RuntimeError(f"{svg_path} is 0 bytes after retry")
    n_paths = svg_path.read_text(encoding="utf-8").count("<path ")

    gap = df["accuracy"] - df["majority_baseline_accuracy"]
    max_gap = gap.max()
    mean_auc = df["auc"].mean()
    n_above_chance = int((df["auc"] > 0.6).sum())

    index_md = f"""# Suite 08: Real Omission Decoding -- {session_prefix}

Area: **{area}** (real, highest-unit-count area with >= {MIN_UNITS} units for this session).

Real sliding-window SVM decoding (`omission.jnwb_ext.decoding.decode_omission_presence`, nested 5-fold CV),
standard (AAAB) vs. omission (AAXB) trials, {len(WINDOW_STARTS_MS)} windows of
{WINDOW_WIDTH_MS:.0f} ms each.

- Max accuracy gap over majority-class baseline: {max_gap:.4f}
- Mean AUC across windows: {mean_auc:.4f}
- Windows with AUC > 0.6 (weak-to-moderate above-chance separability): {n_above_chance} / {len(df)}
- SVG: `figures/decoding_timecourse.svg` ({svg_bytes} bytes, {n_paths} path elements)

![Decoding timecourse](figures/decoding_timecourse.svg)

## Per-window results

{df.to_markdown(index=False)}
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
        t0 = time.time()
        result = run_one_session(nwb_path, session_prefix)
        elapsed = time.time() - t0
        if result["status"] != "completed":
            print(f"  SKIPPED/FAILED: {result.get('reason')}")
            n_skipped += 1
            summary_rows.append({"session_prefix": session_prefix, "status": f"{result['status']}: {result.get('reason')}"})
            continue
        out_dir = write_report(session_prefix, result)
        df = result["results_df"]
        gap = (df["accuracy"] - df["majority_baseline_accuracy"]).max()
        print(f"  wrote report to {out_dir} (area={result['area']}, max_gap={gap:.4f}, {elapsed:.1f}s)")
        n_completed += 1
        summary_rows.append({
            "session_prefix": session_prefix, "status": "ok", "area": result["area"],
            "max_accuracy_gap": gap, "mean_auc": df["auc"].mean(),
        })

    print(f"\nDone: {n_completed} completed, {n_skipped} skipped (of {len(sessions)})")
    summary_path = OUT_ROOT.parent / "publication_visual_review" / "suite_08_omission_decoding" / "all_sessions_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
