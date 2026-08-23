"""
Suite 09 (real Granger-causality network across brain areas via VAR models on
LFP), generalized across sessions.

Refactor of notebooks/suite_09_granger_network.ipynb, which was hardcoded to
one session (sub-V182o_ses-260629.nwb). This script parametrizes the same
real computation:
    jnwb.connectivity.granger_causality(signal1, signal2, order=20, ...)
on real, continuous, decimated (1000 -> 200 Hz) LFP for a ~60 s task-engaged
window anchored at the first correct AAAB phase-1 (stimulus_number=2) onset,
plus the notebook's real circular-shift permutation test (n=200 shuffles) +
jnwb.statistics.StatisticalAnalysis.fdr_correct (BH-FDR) across all directed
area pairs.

order=20 (not AIC-auto) is kept deliberately: AIC-auto selects order 10 on
this decimated LFP, which fails Ljung-Box residual whiteness on every pair;
order=20 clears it. Do not revert to 'auto'.

Per-area LFP extraction uses each session's own canonical probe_areas.json
sidecar (D:/workspace/data/metadata/<stem>/probe_areas.json) for the
probe -> {area: channel_slice} mapping, rather than assuming one area per
probe. The V182o demo session happens to have exactly one area per probe
(PFC/FEF/MST/FST/TEO across 4 probes); most other real sessions have
dual- or triple-area probes (e.g. C31o probe C = "V1, V2, V3") that must be
split into per-area channel groups using that probe's own channel_slices,
not averaged together.

Data dependency: this notebook reads raw broadband LFP directly via h5py
(acquisition/probe_N_lfp) -- it does NOT use the precomputed TFR .npy
pipeline (D:/workspace/data/tfr_arrays) at all. Session selection is
therefore based on nwb_ok=True & short_nwb=False in session_readiness.csv,
independent of tfr_ok/suite_tfr_ready.

NOTE (discovered this pass, not fixed -- out of scope): the
h5_paths.json sidecar's "lfp_data_template": "acquisition/{key}/data" is
WRONG for the V182o session. That file's real per-probe LFP arrays are
nested one level deeper: acquisition/probe_N_lfp/probe_N_lfp_data/{data,
timestamps}, unlike every other real session checked here (flat
acquisition/probe_N_lfp/{data,timestamps}). This script detects the actual
on-disk layout per file at read time instead of trusting that template.

For each session this writes:
    outputs/publication_visual_review/suite_09_granger_network/<session_prefix>/
        index.md
        figures/causality_matrix.svg

Usage:
    python scripts/build_suite_09_granger_reports.py --all-ready
    python scripts/build_suite_09_granger_reports.py --nwb <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import h5py
import numpy as np
import pandas as pd
from scipy.signal import decimate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import omission as oa  # noqa: E402
from jnwb.connectivity import granger_causality  # noqa: E402
from jnwb.statistics import StatisticalAnalysis  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# V182o sessions whose TFR precompute is still running in the background as
# of 2026-07-12 (per another concurrent process). This notebook does not
# read TFR files at all, so nothing here technically requires skipping them;
# they are skipped anyway purely as an I/O-contention courtesy (avoid heavy
# concurrent NWB/h5py reads on files another process is actively writing
# derived artifacts for). Re-run explicitly via --nwb once that job is done.
DEFAULT_SKIP_SESSIONS = {
    "sub-V182o_ses-260702",
    "sub-V182o_ses-260706",
    "sub-V182o_ses-260708",
}


def load_probe_areas(metadata_dir: Path, stem: str) -> Dict[str, dict]:
    path = metadata_dir / stem / "probe_areas.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_lfp_dataset(h5file: h5py.File, lfp_key: str) -> Tuple[h5py.Dataset, h5py.Dataset]:
    """Return (data, timestamps) h5py datasets for a probe's LFP acquisition
    entry, handling both real on-disk layouts seen in this repo's NWB files:
    flat (acquisition/<key>/{data,timestamps}) or nested one level deeper
    (acquisition/<key>/<key>_data/{data,timestamps}, seen on V182o).
    """
    grp = h5file[f"acquisition/{lfp_key}"]
    if "data" in grp and "timestamps" in grp:
        return grp["data"], grp["timestamps"]
    nested_key = f"{lfp_key}_data"
    if nested_key in grp:
        nested = grp[nested_key]
        if "data" in nested and "timestamps" in nested:
            return nested["data"], nested["timestamps"]
    raise KeyError(f"Could not find data/timestamps under acquisition/{lfp_key} (flat or nested)")


def extract_area_signals(
    nwb_path: Path,
    probe_areas: Dict[str, dict],
    t_start: float,
    t_end: float,
    decim_factor: int,
) -> Tuple[Dict[str, np.ndarray], List[str], Dict[str, dict]]:
    """Real per-area regional LFP (channel-mean within that area's real
    channel_slice on its probe), decimated. Returns (area_signals,
    area_order, area_provenance)."""
    area_signals: Dict[str, np.ndarray] = {}
    area_order: List[str] = []
    area_provenance: Dict[str, dict] = {}

    with h5py.File(nwb_path, "r") as f:
        for probe, entry in probe_areas.items():
            lfp_key = entry["lfp_key"]
            try:
                data_dset, ts_dset = resolve_lfp_dataset(f, lfp_key)
            except KeyError:
                continue
            ts = ts_dset
            i0 = int(np.searchsorted(ts, t_start))
            i1 = int(np.searchsorted(ts, t_end))
            if i1 <= i0:
                continue
            raw = data_dset[i0:i1, :]  # real recorded voltage (n_samples, n_channels)
            for area, sl in entry["channel_slices"].items():
                ch0, ch1 = int(sl["start"]), int(sl["stop"])
                region_mean = raw[:, ch0:ch1].mean(axis=1)
                region_ds = decimate(region_mean, decim_factor, ftype="fir", zero_phase=True)
                area_signals[area] = region_ds
                area_order.append(area)
                area_provenance[area] = {
                    "probe": probe,
                    "lfp_key": lfp_key,
                    "location_raw": entry.get("location_raw"),
                    "channel_start": ch0,
                    "channel_stop": ch1,
                    "n_raw_samples": int(raw.shape[0]),
                    "n_decimated_samples": int(region_ds.shape[0]),
                }
    return area_signals, area_order, area_provenance


def compute_granger_matrix(
    area_signals: Dict[str, np.ndarray], area_order: List[str], order: int
) -> Tuple[np.ndarray, List[str]]:
    n = len(area_order)
    causality_matrix = np.zeros((n, n))
    warnings: List[str] = []
    for i, area_from in enumerate(area_order):
        for j, area_to in enumerate(area_order):
            if i == j:
                continue
            sig1 = area_signals[area_from]
            sig2 = area_signals[area_to]
            result = granger_causality(sig1, sig2, order=order, device="cpu", criterion="aic", ridge=0.0)
            causality_matrix[i, j] = result["F_1_to_2"]
            diag = result["diagnostics"]
            if not diag["ok_for_interpretation"]:
                warnings.append(f"{area_from} -> {area_to}: {diag['warnings']}")
    return causality_matrix, warnings


def permutation_test(
    area_signals: Dict[str, np.ndarray],
    area_order: List[str],
    causality_matrix: np.ndarray,
    order: int,
    n_shuffles: int,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Real circular-shift permutation test on the GC values themselves,
    with BH-FDR across all directed pairs. Same pattern as the original
    notebook (n=200 shuffles, seed=42) -- reused here, not re-derived."""
    n = len(area_order)
    rng = np.random.default_rng(seed)
    raw_pvals = np.full((n, n), np.nan)

    for i, area_from in enumerate(area_order):
        for j, area_to in enumerate(area_order):
            if i == j:
                continue
            sig1 = area_signals[area_from]
            sig2 = area_signals[area_to]
            observed = causality_matrix[i, j]

            surrogate_vals = np.empty(n_shuffles)
            for s in range(n_shuffles):
                shift = rng.integers(1, len(sig2) - 1)
                sig2_shifted = np.roll(sig2, shift)
                r_shuf = granger_causality(sig1, sig2_shifted, order=order, device="cpu", criterion="aic")
                surrogate_vals[s] = r_shuf["F_1_to_2"]

            p_val = (np.sum(surrogate_vals >= observed) + 1) / (n_shuffles + 1)
            raw_pvals[i, j] = p_val

    pairs_i, pairs_j = np.where(~np.isnan(raw_pvals))
    flat_p = raw_pvals[pairs_i, pairs_j]
    flat_q = StatisticalAnalysis.fdr_correct(flat_p)
    qval_matrix = np.full((n, n), np.nan)
    qval_matrix[pairs_i, pairs_j] = flat_q
    return raw_pvals, qval_matrix


def plot_causality_matrix(causality_matrix: np.ndarray, area_order: List[str],
                           qval_matrix: np.ndarray, session_prefix: str, svg_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(area_order)
    fig, ax = plt.subplots(figsize=(max(6, n * 1.3), max(5, n * 1.1)))
    vmax = max(causality_matrix.max(), 1e-6)
    im = ax.imshow(causality_matrix, cmap="Oranges", vmin=0, vmax=vmax)
    fig.colorbar(im, ax=ax, label="Granger Causality (log variance ratio)")

    ax.set_xticks(range(n))
    ax.set_xticklabels(area_order, rotation=45, ha="right")
    ax.set_yticks(range(n))
    ax.set_yticklabels(area_order)
    ax.set_xlabel("To Region")
    ax.set_ylabel("From Region")
    ax.set_title(f"Suite 09: Directed Granger Causality (real LFP, {session_prefix})")

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            sig = "*" if qval_matrix[i, j] < 0.05 else ""
            ax.text(j, i, f"{causality_matrix[i, j]:.2f}{sig}", ha="center", va="center",
                     color="black", fontweight="bold", fontsize=8)

    svg_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def run_one_session(
    nwb_path: Path,
    metadata_dir: Path,
    out_root: Path,
    window_s: float,
    decim_factor: int,
    order: int,
    n_shuffles: int,
    seed: int,
) -> dict:
    stem = nwb_path.stem
    session_prefix = stem[:-len("_rec")] if stem.endswith("_rec") else stem
    receipt = {"session": session_prefix, "stem": stem, "nwb_path": str(nwb_path)}

    probe_areas_path = metadata_dir / stem / "probe_areas.json"
    if not probe_areas_path.exists():
        receipt["status"] = "skipped"
        receipt["reason"] = f"no probe_areas.json sidecar at {probe_areas_path}"
        return receipt
    probe_areas = load_probe_areas(metadata_dir, stem)

    session = oa.read(str(nwb_path))
    p1_aaab = session.get_epochs(phase=2, condition="AAAB", correct_only=True)
    if len(p1_aaab) == 0:
        receipt["status"] = "skipped"
        receipt["reason"] = "no correct AAAB p1 epochs found -- cannot anchor a task-engaged window"
        return receipt
    t_start = float(p1_aaab["start_time"].values[0])
    t_end = t_start + window_s

    area_signals, area_order, area_provenance = extract_area_signals(
        nwb_path, probe_areas, t_start, t_end, decim_factor
    )
    if len(area_order) < 2:
        receipt["status"] = "skipped"
        receipt["reason"] = f"fewer than 2 real areas resolved from LFP ({area_order})"
        return receipt

    causality_matrix, diag_warnings = compute_granger_matrix(area_signals, area_order, order)
    raw_pvals, qval_matrix = permutation_test(
        area_signals, area_order, causality_matrix, order, n_shuffles, seed
    )

    n = len(area_order)
    sig_pairs = []
    for i, area_from in enumerate(area_order):
        for j, area_to in enumerate(area_order):
            if i != j and qval_matrix[i, j] < 0.05:
                sig_pairs.append({
                    "from": area_from, "to": area_to,
                    "gc": float(causality_matrix[i, j]),
                    "q": float(qval_matrix[i, j]),
                })

    out_dir = out_root / session_prefix
    figures_dir = out_dir / "figures"
    svg_path = figures_dir / "causality_matrix.svg"
    plot_causality_matrix(causality_matrix, area_order, qval_matrix, session_prefix, svg_path)

    n_directed_pairs = n * (n - 1)
    n_sig = len(sig_pairs)

    lines = [
        f"# Suite 09: Granger Causality Network -- {session_prefix}",
        "",
        f"Real broadband LFP (`acquisition/probe_*_lfp`), 1 kHz -> 200 Hz (decimate factor "
        f"{decim_factor}), {window_s:.0f}s continuous task-engaged window anchored at the "
        f"first correct AAAB p1 (stimulus_number=2) onset (t_start={t_start:.2f}s).",
        "",
        f"Real areas ({n}, from this session's own probe_areas.json channel_slices, "
        "NOT assumed to match any other session): " + ", ".join(area_order),
        "",
        "| probe | area | channels | location_raw |",
        "|---|---|---|---|",
    ]
    for area in area_order:
        prov = area_provenance[area]
        lines.append(
            f"| {prov['probe']} | {area} | {prov['channel_start']}-{prov['channel_stop']} | "
            f"{prov['location_raw']} |"
        )
    lines += [
        "",
        f"VAR order={order} (fixed, not AIC-auto -- order 10 fails Ljung-Box residual "
        "whiteness on this decimated LFP; order=20 clears it, per the notebook's established fix).",
        "",
    ]
    if diag_warnings:
        lines.append("Residual-diagnostic warnings (Ljung-Box / lightweight ADF) -- "
                      "interpret directionality cautiously for these pairs:")
        lines.append("")
        for w in diag_warnings:
            lines.append(f"- {w}")
        lines.append("")
    else:
        lines.append("All directed pairs passed residual diagnostics (Ljung-Box + lightweight ADF).")
        lines.append("")

    lines.append(
        f"Circular-shift permutation test (n={n_shuffles} shuffles, seed={seed}) + BH-FDR "
        f"across all {n_directed_pairs} directed pairs: **{n_sig}/{n_directed_pairs}** significant at q<0.05."
    )
    lines.append("")
    if sig_pairs:
        lines.append("| From | To | GC | q |")
        lines.append("|---|---|---|---|")
        for sp in sig_pairs:
            lines.append(f"| {sp['from']} | {sp['to']} | {sp['gc']:.4f} | {sp['q']:.4f} |")
        lines.append("")
    lines.append("![Directed Granger causality matrix](figures/causality_matrix.svg)")
    lines.append("")

    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")

    receipt.update({
        "status": "completed",
        "n_areas": n,
        "area_order": area_order,
        "t_start": t_start,
        "t_end": t_end,
        "n_directed_pairs": n_directed_pairs,
        "n_significant_q05": n_sig,
        "significant_pairs": sig_pairs,
        "diagnostic_warnings": diag_warnings,
        "causality_matrix": causality_matrix.tolist(),
        "qval_matrix": np.where(np.isnan(qval_matrix), None, qval_matrix).tolist(),
        "report_path": str(out_dir / "index.md"),
        "svg_path": str(svg_path),
        "svg_bytes": svg_path.stat().st_size,
    })
    return receipt


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nwb", type=Path, default=None, help="Path to a single .nwb file.")
    p.add_argument("--all-ready", action="store_true",
                    help="Run every session in --readiness-csv with nwb_ok=True and "
                         "short_nwb=False (independent of tfr_ok), skipping --skip-sessions.")
    p.add_argument("--readiness-csv", type=Path, default=REPO_ROOT / "artifacts/data/session_readiness.csv")
    p.add_argument("--metadata-dir", type=Path, default=Path("D:/workspace/data/metadata"))
    p.add_argument("--out-dir", type=Path,
                    default=REPO_ROOT / "outputs/publication_visual_review/suite_09_granger_network")
    p.add_argument("--window-s", type=float, default=60.0)
    p.add_argument("--decim-factor", type=int, default=5)
    p.add_argument("--order", type=int, default=20)
    p.add_argument("--n-shuffles", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--skip-sessions", nargs="*", default=sorted(DEFAULT_SKIP_SESSIONS),
                    help="session_prefix values to never touch (default: V182o sessions with "
                         "an in-progress TFR precompute by a concurrent process; skipped here "
                         "purely as an I/O courtesy, not a real data dependency).")
    return p.parse_args()


def main():
    args = parse_args()

    if args.nwb is not None:
        jobs = [args.nwb]
    elif args.all_ready:
        df = pd.read_csv(args.readiness_csv)
        ready = df[(df["nwb_ok"] == True) & (df["short_nwb"] == False)]  # noqa: E712
        jobs = []
        for _, row in ready.iterrows():
            if row["session_prefix"] in args.skip_sessions:
                print(f"SKIP {row['session_prefix']}: in --skip-sessions (concurrent TFR precompute courtesy)")
                continue
            jobs.append(Path(row["nwb_path"]))
    else:
        raise SystemExit("Specify --nwb <path> or --all-ready")

    receipts = []
    for nwb_path in jobs:
        print(f"=== {nwb_path.name} ===")
        if not nwb_path.exists():
            print("  SKIP: file not found")
            receipts.append({"session": nwb_path.stem, "status": "skipped", "reason": "file not found"})
            continue
        receipt = run_one_session(
            nwb_path, args.metadata_dir, args.out_dir,
            args.window_s, args.decim_factor, args.order, args.n_shuffles, args.seed,
        )
        print(f"  status={receipt['status']} n_areas={receipt.get('n_areas')} "
              f"n_sig={receipt.get('n_significant_q05')}/{receipt.get('n_directed_pairs')} "
              f"reason={receipt.get('reason', '')}")
        receipts.append(receipt)

    n_ok = sum(1 for r in receipts if r["status"] == "completed")
    n_skip = sum(1 for r in receipts if r["status"] == "skipped")
    print(f"\nDone: {n_ok} completed, {n_skip} skipped (of {len(receipts)})")

    summary_rows = []
    for r in receipts:
        summary_rows.append({
            "session_prefix": r.get("session"),
            "status": r["status"],
            "n_areas": r.get("n_areas"),
            "n_directed_pairs": r.get("n_directed_pairs"),
            "n_significant_q05": r.get("n_significant_q05"),
            "reason": r.get("reason", ""),
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_path = args.out_dir / "all_sessions_summary.csv"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_path, index=False)
    print(f"Summary written to {summary_path}")

    return receipts


if __name__ == "__main__":
    main()
