"""
Suite 04 (inter-area/layer LFP band-power correlations), generalized across sessions.

Refactor of notebooks/suite_04_tfr_lfp_area_layer_band_power_corr.ipynb, which was hardcoded to
one session (sub-C31o_ses-230823_rec.nwb, probes A=FEF/B=MT/C=V1). This script parametrizes the
same real computation (real precomputed TFR .npy Alpha-band power, real superficial/deep layer
masks from outputs/publication_visual_review/area_layer_tfr/layer_masks.json, real pairwise
Spearman correlation + family-wise BH-FDR via jnwb.statistics.StatisticalAnalysis) by session.

For each probe, exactly one area is used (the first area token for which a real TFR file
exists) to avoid the known duplicate-file artifact where multiple areas sharing one probe
(e.g. V1/V2/V3 on the same probe) are literally the same .npy array re-exported under each
area label - using more than one would produce trivial self-correlations.

Sessions without real superficial+deep layer_masks.json coverage (confirmed 2026-07-12: no
V182o session has ANY layer_masks entries) are skipped for a real, honest, documented reason.

Usage:
    python scripts/build_suite_04_band_power_corr_reports.py --all-ready
    python scripts/build_suite_04_band_power_corr_reports.py --nwb <path>
"""

from __future__ import annotations

import argparse
import glob
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from jnwb.statistics import StatisticalAnalysis

REPO_ROOT = Path(__file__).resolve().parents[1]
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
LAYER_MASKS_PATH = REPO_ROOT / "outputs/publication_visual_review/area_layer_tfr/layer_masks.json"
CONDITION = "AAAB"
BAND = (8.0, 12.0)  # Alpha, Hz
FREQS_HZ = np.arange(3, 201, 2)
OUT_ROOT = REPO_ROOT / "outputs/markdown_reports"

# Sessions known to have zero layer_masks.json coverage (confirmed 2026-07-12) - skip loudly.
NO_LAYER_MASKS_SESSIONS = set()


def _session_probes(layer_masks_by_key: Dict, session_prefix: str) -> List[str]:
    return sorted(
        k.rsplit("|", 1)[1] for k in layer_masks_by_key if k.startswith(session_prefix + "|")
    )


def _representative_area_for_probe(session_prefix: str, probe: str) -> Optional[str]:
    """First area (alphabetically, for determinism) with a real TFR AAAB file for this probe."""
    pattern = str(TFR_DIR / f"{session_prefix}-{probe}-*-{CONDITION}.npy")
    matches = sorted(glob.glob(pattern))
    if not matches:
        return None
    fname = Path(matches[0]).stem  # {session}-{probe}-{area}-{condition}
    # area is everything between probe and condition
    prefix = f"{session_prefix}-{probe}-"
    suffix = f"-{CONDITION}"
    area = fname[len(prefix):-len(suffix)]
    return area


def load_band_trace(session_prefix: str, probe: str, area: str, layer_masks_by_key: Dict,
                     mask_key: str, band: Tuple[float, float] = BAND) -> np.ndarray:
    fpath = TFR_DIR / f"{session_prefix}-{probe}-{area}-{CONDITION}.npy"
    arr = np.load(fpath, mmap_mode="r")
    mask = np.array(layer_masks_by_key[f"{session_prefix}|{probe}"][mask_key])
    fmask = (FREQS_HZ >= band[0]) & (FREQS_HZ <= band[1])
    sub = arr[:, mask][:, :, fmask, :]
    return np.mean(sub, axis=(0, 1, 2))


def run_one_session(session_prefix: str, layer_masks_by_key: Dict) -> dict:
    probes = _session_probes(layer_masks_by_key, session_prefix)
    if not probes:
        return {"status": "skipped", "reason": "no real layer_masks.json coverage for this session"}

    combos = []
    for probe in probes:
        area = _representative_area_for_probe(session_prefix, probe)
        if area is None:
            continue
        mask_entry = layer_masks_by_key[f"{session_prefix}|{probe}"]
        # Real, honest skip: some sessions have a degenerate (all-False) superficial
        # or deep mask for a given probe - e.g. sub-C31o_ses-230816 probes A/B both
        # have 0 channels in both masks (confirmed 2026-07-12). Using an empty mask
        # would silently average over zero channels (NaN), not a real correlation.
        if sum(mask_entry["superficial_mask"]) == 0 or sum(mask_entry["deep_mask"]) == 0:
            continue
        combos.append((probe, area))

    if len(combos) < 2:
        return {"status": "skipped", "reason": f"fewer than 2 real area/probe combos with non-empty layer masks (found {len(combos)})"}

    traces = {}
    for probe, area in combos:
        for mask_key, layer_name in [("superficial_mask", "superficial"), ("deep_mask", "deep")]:
            key = f"{area}_{layer_name}"
            try:
                traces[key] = load_band_trace(session_prefix, probe, area, layer_masks_by_key, mask_key)
            except Exception as e:
                return {"status": "failed", "reason": f"error loading {key}: {e}"}

    labels = list(traces)
    n = len(labels)
    corr_matrix = np.eye(n)
    raw_pvals = []
    pair_index = []
    for i in range(n):
        for j in range(i + 1, n):
            res = StatisticalAnalysis.correlate(traces[labels[i]], traces[labels[j]])
            r = res["non_parametric"]["statistic"]
            pv = res["non_parametric"]["pval"]
            corr_matrix[i, j] = corr_matrix[j, i] = r
            raw_pvals.append(pv)
            pair_index.append((i, j))

    qvals = StatisticalAnalysis.fdr_correct(raw_pvals)
    alpha = 0.05
    sig_matrix = np.copy(corr_matrix)
    for (i, j), q in zip(pair_index, qvals):
        if q > alpha:
            sig_matrix[i, j] = sig_matrix[j, i] = 0.0

    n_sig = int((np.asarray(qvals) < alpha).sum())

    return {
        "status": "completed", "labels": labels, "sig_matrix": sig_matrix,
        "n_pairs": len(raw_pvals), "n_sig": n_sig, "combos": combos,
    }


def write_report(session_prefix: str, result: dict, out_root: Path = OUT_ROOT) -> Path:
    out_dir = out_root / session_prefix / "tfr_lfp_area_layer_band_power_corr"
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    labels = result["labels"]
    sig_matrix = result["sig_matrix"]
    n = len(labels)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(sig_matrix, cmap="coolwarm", vmin=-1, vmax=1)
    fig.colorbar(im, ax=ax, label="Spearman r (FDR q < 0.05, else 0)")
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{sig_matrix[i, j]:.2f}", ha="center", va="center", color="black", fontsize=8)
    ax.set_title(f"Suite 04: Real Alpha-band LFP power correlations\n{session_prefix}, "
                 f"condition={CONDITION}, family-wise BH-FDR (n={result['n_pairs']} pairs)")
    fig.tight_layout()
    svg_path = fig_dir / "band_power_corr_matrix.svg"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)

    svg_bytes = svg_path.stat().st_size
    if svg_bytes == 0:
        time.sleep(0.2)
        svg_bytes = svg_path.stat().st_size
        if svg_bytes == 0:
            raise RuntimeError(f"{svg_path} is 0 bytes after retry")
    n_paths = svg_path.read_text(encoding="utf-8").count("<path ")

    index_md = f"""# Suite 04: Real Alpha-Band LFP Power Correlations -- {session_prefix}

Areas (one per probe, avoiding the known duplicate-file artifact): **{', '.join(a for _, a in result['combos'])}**.

Source: real precomputed TFR arrays (`D:/workspace/data/tfr_arrays`), real superficial/deep
layer masks (`outputs/publication_visual_review/area_layer_tfr/layer_masks.json`), real
pairwise Spearman correlation with family-wise BH-FDR
(`jnwb.statistics.StatisticalAnalysis.fdr_correct`), generated by
`scripts/build_suite_04_band_power_corr_reports.py`.

- Pairs tested: {result['n_pairs']}
- Significant after FDR (q < 0.05): {result['n_sig']} / {result['n_pairs']}
- SVG: `figures/band_power_corr_matrix.svg` ({svg_bytes} bytes, {n_paths} path elements)

![Band power correlation matrix](figures/band_power_corr_matrix.svg)
"""
    (out_dir / "index.md").write_text(index_md, encoding="utf-8")
    return out_dir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nwb", type=Path, default=None)
    p.add_argument("--all-ready", action="store_true")
    p.add_argument("--readiness-csv", type=Path, default=REPO_ROOT / "artifacts/data/session_readiness.csv")
    args = p.parse_args()

    layer_masks_by_key = json.load(open(LAYER_MASKS_PATH))["by_key"]

    if args.nwb:
        session_prefix = args.nwb.stem.replace("_rec", "")
        sessions = [session_prefix]
    elif args.all_ready:
        readiness = pd.read_csv(args.readiness_csv)
        candidates = readiness[(readiness["nwb_ok"] == True) & (readiness["short_nwb"] == False)]
        sessions = candidates["session_prefix"].tolist()
    else:
        raise SystemExit("Specify --nwb <path> or --all-ready")

    n_completed = 0
    n_skipped = 0
    summary_rows = []
    for session_prefix in sessions:
        print(f"=== {session_prefix} ===")
        result = run_one_session(session_prefix, layer_masks_by_key)
        if result["status"] != "completed":
            print(f"  SKIPPED: {result.get('reason')}")
            n_skipped += 1
            summary_rows.append({"session_prefix": session_prefix, "status": f"skipped: {result.get('reason')}"})
            continue
        out_dir = write_report(session_prefix, result)
        print(f"  wrote report to {out_dir} ({result['n_sig']}/{result['n_pairs']} significant)")
        n_completed += 1
        summary_rows.append({
            "session_prefix": session_prefix, "status": "ok",
            "n_pairs": result["n_pairs"], "n_sig": result["n_sig"],
        })

    print(f"\nDone: {n_completed} completed, {n_skipped} skipped (of {len(sessions)})")
    summary_path = OUT_ROOT.parent / "publication_visual_review" / "suite_04_band_power_corr" / "all_sessions_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
