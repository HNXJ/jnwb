"""
Suite 03 (2D TFR spectrogram heatmaps), generalized across sessions.

Refactor of notebooks/suite_03_tfr_lfp_heatmap2d.ipynb, which was hardcoded to
one session (sub-C31o_ses-230823_rec.nwb) and three explicit calls
(V1/AAAB, V1/AAXB, FEF/AAAB). This script parametrizes the same real
computation (jnwb.session.OmissionSession.plot_tfr, backed by
tfr_from_preprocessed reading real preprocessed .npy TFR arrays under
D:/workspace/data/tfr_arrays) by session, auto-discovering the real areas
that session actually has TFR files for (rather than assuming V1/FEF exist
everywhere), and running the same two condition/phase pairs the original
notebook established for every discovered area:

    - AAAB @ phase=2 (p1, control response)
    - AAXB @ phase=3 (p2, omission-slot response)

(stimulus_number crosswalk: p1=2, p2=3 -- see
legacy/context/07_authoritative_data_topology_single_units.md.)

plot_tfr never fabricates a spectrogram: if a file is missing it returns
status='missing_tfr' and no figure (no silent synthetic science). This
script records that as a real per-(area, condition) skip in the report
rather than papering over it.

For each session this writes:
    outputs/markdown_reports/<session>/tfr_lfp_heatmap2d/
        index.md                                    -- session-scoped report page
        figures/tfr_heatmap_<area>_<condition>.svg   -- one real SVG per (area, condition)

SVG is the only standard visualization format for this project (see
jnwb/markdown_report.py); PNG/PDF are not written here.

Usage:
    python scripts/build_suite_03_tfr_heatmap_reports.py --all-ready
    python scripts/build_suite_03_tfr_heatmap_reports.py --nwb <path> --areas V1 FEF
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jnwb as oa  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# Sessions whose TFR arrays are still being precomputed by a separate process
# as of 2026-07-12 (per artifacts/data/session_readiness.csv tfr_ok=False).
# Never touch these files; skip them until readiness is regenerated.
IN_PROGRESS_SKIP_SESSIONS = {
    "sub-V182o_ses-260702",
    "sub-V182o_ses-260706",
    "sub-V182o_ses-260708",
}

# Sessions with a confirmed-stale precomputed TFR array (real trial-count
# mismatch vs current intervals data, confirmed 2026-07-12) that a separate
# task is fixing right now. Skip until that fix lands and readiness is
# regenerated -- do not attempt to recompute or paper over this here.
STALE_TFR_SKIP_SESSIONS = {
    "sub-C31o_ses-230816",
    "sub-C31o_ses-230901",
}

DEFAULT_SKIP_SESSIONS = IN_PROGRESS_SKIP_SESSIONS | STALE_TFR_SKIP_SESSIONS

# Probe letter can be any single uppercase letter (A/B/C for most subjects,
# D observed for V182o's TEO probe) -- do not assume only A|B|C.
FILE_RE = re.compile(r"^(.+)-([A-Z])-([A-Za-z0-9]+)-([A-Z0-9]+)\.npy$")

# Fixed condition/phase pairs this suite compares, per the original notebook:
# AAAB @ phase=2 (p1, control) and AAXB @ phase=3 (p2, omission slot).
CONDITION_PHASES: List[Tuple[str, int]] = [("AAAB", 2), ("AAXB", 3)]


def discover_session_areas(tfr_dir: Path, session_prefix: str) -> Set[str]:
    """Return the set of real area tokens with at least one TFR file for this
    exact session prefix (across any probe letter)."""
    areas: Set[str] = set()
    for path in tfr_dir.glob(f"{session_prefix}-*.npy"):
        m = FILE_RE.match(path.name)
        if not m:
            continue
        sess, probe, area, cond = m.groups()
        if sess != session_prefix:
            continue
        areas.add(area)
    return areas


def run_one_session(nwb_path: Path, areas: Optional[List[str]], tfr_dir: Path,
                     out_root: Path) -> dict:
    """Run the real 2D TFR heatmap suite for one session and write its SVG
    figures + a markdown report page. Returns a receipt dict describing what
    actually happened (never fabricated)."""
    import matplotlib.pyplot as plt

    session_prefix = nwb_path.stem
    if session_prefix.endswith("_rec"):
        session_prefix = session_prefix[: -len("_rec")]

    receipt = {"session": session_prefix, "nwb_path": str(nwb_path)}

    if areas is None:
        areas = sorted(discover_session_areas(tfr_dir, session_prefix))
    if not areas:
        receipt["status"] = "skipped"
        receipt["reason"] = f"no TFR files found for {session_prefix} under {tfr_dir}"
        return receipt
    receipt["areas"] = areas

    session = oa.read(str(nwb_path))

    out_dir = out_root / session_prefix / "tfr_lfp_heatmap2d"
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    area_results: Dict[str, Dict[str, dict]] = {}
    for area in areas:
        cond_results: Dict[str, dict] = {}
        for condition, phase in CONDITION_PHASES:
            res = session.plot_tfr(area=area, condition=condition, phase=phase)
            if res["status"] != "completed":
                cond_results[condition] = {"status": res["status"], "error": res.get("error")}
                continue

            fig = res["figure"]
            svg_name = f"tfr_heatmap_{area}_{condition}.svg"
            svg_path = figures_dir / svg_name
            fig.savefig(svg_path, format="svg", bbox_inches="tight")
            plt.close(fig)

            # Guard against a real, observed race on Windows: stat()/read_text()
            # immediately after savefig() has occasionally reported 0 bytes for a
            # file that was already fully written (confirmed non-zero on
            # immediate re-check) -- retry briefly rather than writing a false
            # "0 bytes" claim into the report. Same pattern as
            # scripts/build_suite_02_tfr_layer_reports.py.
            svg_bytes = svg_path.stat().st_size
            if svg_bytes == 0:
                time.sleep(0.2)
                svg_bytes = svg_path.stat().st_size
                if svg_bytes == 0:
                    raise RuntimeError(f"{svg_path} is 0 bytes after retry - real save failure, not a transient race")

            n_paths = svg_path.read_text(encoding="utf-8").count("<path ")
            cond_results[condition] = {
                "status": "completed",
                "phase": phase,
                "svg_path": str(svg_path),
                "svg_bytes": svg_bytes,
                "svg_path_elements": n_paths,
            }
        area_results[area] = cond_results

    receipt["area_results"] = area_results
    any_completed = any(
        c.get("status") == "completed"
        for conds in area_results.values()
        for c in conds.values()
    )
    receipt["status"] = "completed" if any_completed else "failed"

    # Markdown report page (SVG-embedding convention per jnwb/markdown_report.py)
    lines = [
        f"# Suite 03: 2D TFR Spectrogram Heatmaps -- {session_prefix}",
        "",
        f"Areas (auto-discovered: real TFR files present under `{tfr_dir}`): "
        f"**{', '.join(areas)}**.",
        "",
        "Source: `jnwb.session.OmissionSession.plot_tfr` (backed by "
        "`tfr_from_preprocessed`), generated by "
        "`scripts/build_suite_03_tfr_heatmap_reports.py`.",
        "",
        "Condition/phase pairs (fixed, per original notebook design): "
        "`AAAB` @ phase=2 (p1, control) and `AAXB` @ phase=3 (p2, omission slot).",
        "",
    ]
    for area in areas:
        lines.append(f"## Area: {area}")
        lines.append("")
        for condition, phase in CONDITION_PHASES:
            r = area_results[area].get(condition, {})
            lines.append(f"### {condition} (phase={phase})")
            lines.append("")
            if r.get("status") != "completed":
                lines.append(f"*(missing/failed: {r.get('error', 'unknown error')})*")
                lines.append("")
                continue
            svg_name = f"tfr_heatmap_{area}_{condition}.svg"
            lines.append(f"- SVG: `figures/{svg_name}` ({r['svg_bytes']} bytes, {r['svg_path_elements']} path elements)")
            lines.append("")
            lines.append(f"![{area} {condition} TFR heatmap](figures/{svg_name})")
            lines.append("")

    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    receipt["report_path"] = str(out_dir / "index.md")
    return receipt


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nwb", type=Path, default=None,
                    help="Path to a single .nwb file. If omitted, use --all-ready.")
    p.add_argument("--areas", nargs="+", default=None,
                    help="Brain area(s). If omitted, auto-discovered per session from real "
                         "TFR files under --tfr-dir.")
    p.add_argument("--all-ready", action="store_true",
                    help="Run every session in --readiness-csv with suite_tfr_ready=True "
                         "and short_nwb=False, skipping --skip-sessions.")
    p.add_argument("--readiness-csv", type=Path,
                    default=REPO_ROOT / "artifacts/data/session_readiness.csv")
    p.add_argument("--tfr-dir", type=Path, default=Path("D:/workspace/data/tfr_arrays"))
    p.add_argument("--out-dir", type=Path, default=REPO_ROOT / "outputs/markdown_reports")
    p.add_argument("--skip-sessions", nargs="*", default=sorted(DEFAULT_SKIP_SESSIONS),
                    help="session_prefix values to never touch (default: sessions with an "
                         "in-progress TFR precompute, or a confirmed-stale TFR array).")
    return p.parse_args()


def main():
    args = parse_args()

    if args.nwb is not None:
        jobs = [(args.nwb, args.areas)]
    elif args.all_ready:
        df = pd.read_csv(args.readiness_csv)
        ready = df[(df["suite_tfr_ready"] == True) & (df["short_nwb"] == False)]  # noqa: E712
        jobs = []
        for _, row in ready.iterrows():
            if row["session_prefix"] in args.skip_sessions:
                print(f"SKIP {row['session_prefix']}: in --skip-sessions (precompute in progress or stale TFR)")
                continue
            jobs.append((Path(row["nwb_path"]), args.areas))
    else:
        raise SystemExit("Specify --nwb <path> or --all-ready")

    receipts = []
    for nwb_path, areas in jobs:
        print(f"=== {nwb_path.name} ===")
        if not nwb_path.exists():
            print(f"  SKIP: file not found: {nwb_path}")
            receipts.append({"session": nwb_path.stem, "status": "skipped", "reason": "file not found"})
            continue
        receipt = run_one_session(nwb_path, areas, args.tfr_dir, args.out_dir)
        print(f"  status={receipt['status']} areas={receipt.get('areas')} reason={receipt.get('reason', '')}")
        for area, conds in receipt.get("area_results", {}).items():
            for condition, r in conds.items():
                if r.get("status") == "completed":
                    print(f"    {area}/{condition}: svg={r['svg_bytes']}B paths={r['svg_path_elements']}")
                else:
                    print(f"    {area}/{condition}: {r.get('status')} {r.get('error')}")
        receipts.append(receipt)

    n_ok = sum(1 for r in receipts if r["status"] == "completed")
    n_skip = sum(1 for r in receipts if r["status"] == "skipped")
    n_fail = sum(1 for r in receipts if r["status"] == "failed")
    print(f"\nDone: {n_ok} completed, {n_skip} skipped, {n_fail} failed (of {len(receipts)})")
    return receipts


if __name__ == "__main__":
    main()
