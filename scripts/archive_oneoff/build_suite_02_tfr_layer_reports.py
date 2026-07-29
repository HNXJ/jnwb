"""
Suite 02 (LFP TFR traces per area/layer), generalized across sessions.

Refactor of notebooks/suite_02_tfr_lfp_traces_layer.ipynb, which was hardcoded to
one session (sub-C31o_ses-230823_rec.nwb, area FEF, both layers). This script
parametrizes the same real computation
(jnwb.session.OmissionSession.lfp_tfr_trace_suite_omission, backed by real
preprocessed TFR .npy arrays under D:/workspace/data/tfr_arrays) by session and
auto-selects a real area that has non-empty superficial AND deep layer masks
for that session, rather than assuming FEF exists everywhere.

Now that the `_rec`-suffix filename-matching bug in
jnwb/viz.py::lfp_tfr_trace_suite_omission has been fixed, this script always
runs with session_specific=True, so each session's figures are built only from
that session's own precomputed TFR files (not silently pooled across sessions
via the shared tfr_arrays directory).

For each session this writes:
    outputs/markdown_reports/<session>/tfr_lfp_traces_layer/
        index.md                          -- session-scoped report page
        figures/tfr_suite_<area>_<layer>.svg   -- one real SVG per layer

SVG is the only standard visualization format for this project (see
jnwb/markdown_report.py); PNG/PDF are not written here.

Usage:
    python scripts/build_suite_02_tfr_layer_reports.py --all-ready
    python scripts/build_suite_02_tfr_layer_reports.py --nwb <path> --area FEF
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jnwb as oa  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# Sessions whose TFR arrays are still being precomputed by a separate process
# as of 2026-07-12 (per artifacts/data/session_readiness.csv tfr_ok=False).
# Never touch these files; skip them until readiness is regenerated.
DEFAULT_SKIP_SESSIONS = {
    "sub-V182o_ses-260702",
    "sub-V182o_ses-260706",
    "sub-V182o_ses-260708",
}

FILE_RE = re.compile(r"^(.+)-([ABC])-([A-Za-z0-9]+)-([A-Z0-9]+)\.npy$")


def load_layer_masks(layer_masks_path: Path) -> Dict[str, dict]:
    with open(layer_masks_path, "r", encoding="utf-8") as f:
        return json.load(f).get("by_key", {})


def get_probe_masks(layer_masks_cache: Dict[str, dict], session_id: str, probe_letter: str):
    target = f"{session_id}|{probe_letter}"
    for key, entry in layer_masks_cache.items():
        if target in key or key in target:
            sup = np.array(entry["superficial_mask"])
            deep = np.array(entry["deep_mask"])
            return sup, deep
    return None, None


def discover_session_areas(tfr_dir: Path, session_prefix: str) -> Dict[Tuple[str, str], None]:
    """Return {(probe, area): None} for all (probe, area) pairs with TFR files
    for this exact session prefix."""
    found = {}
    for path in tfr_dir.glob(f"{session_prefix}-*.npy"):
        m = FILE_RE.match(path.name)
        if not m:
            continue
        sess, probe, area, cond = m.groups()
        if sess != session_prefix:
            continue
        found[(probe, area)] = None
    return found


def pick_area(tfr_dir: Path, layer_masks_cache: Dict[str, dict], session_prefix: str) -> Optional[str]:
    """Pick a real area for this session that has non-empty superficial AND
    deep channel masks (both layers genuinely present), preferring the most
    balanced (largest min(sup, deep)) candidate. Returns None if no such area
    exists (a real, confirmed data gap -- e.g. layer_masks.json has no probe
    boundary entries for this session's subject)."""
    candidates = []
    for probe, area in discover_session_areas(tfr_dir, session_prefix):
        sup, deep = get_probe_masks(layer_masks_cache, session_prefix, probe)
        if sup is None or deep is None:
            continue
        sup_n, deep_n = int(sup.sum()), int(deep.sum())
        if sup_n > 0 and deep_n > 0:
            candidates.append((min(sup_n, deep_n), area, sup_n, deep_n))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def extract_suptitle_metadata(fig) -> Dict[str, str]:
    """Pull the real N-trials and significant-band list back out of the
    figure's suptitle (set in jnwb/viz.py::lfp_tfr_trace_suite_omission),
    rather than recomputing/guessing them."""
    text = fig._suptitle.get_text() if fig._suptitle is not None else ""
    n_match = re.search(r"N=(\d+) trials/slot", text)
    sig_match = re.search(r"Significant Bands \(0-500ms\): (.+)$", text, re.MULTILINE)
    return {
        "n_trials": n_match.group(1) if n_match else "unknown",
        "significant_bands": sig_match.group(1).strip() if sig_match else "unknown",
        "raw_title": text,
    }


def run_one_session(nwb_path: Path, area: Optional[str], layers: List[str],
                     tfr_dir: Path, layer_masks_path: Path, out_root: Path,
                     layer_masks_cache: Dict[str, dict]) -> dict:
    """Run the real TFR layer-trace suite for one session and write its
    SVG figures + a markdown report page. Returns a receipt dict describing
    what actually happened (never fabricated)."""
    import matplotlib.pyplot as plt

    session_prefix = nwb_path.stem
    if session_prefix.endswith("_rec"):
        session_prefix = session_prefix[: -len("_rec")]

    receipt = {"session": session_prefix, "nwb_path": str(nwb_path)}

    if area is None:
        area = pick_area(tfr_dir, layer_masks_cache, session_prefix)
    if area is None:
        receipt["status"] = "skipped"
        receipt["reason"] = (
            "no area with both superficial AND deep channel masks found for this "
            "session (layer_masks.json has no probe-boundary entries covering it)"
        )
        return receipt
    receipt["area"] = area

    session = oa.read(str(nwb_path))

    out_dir = out_root / session_prefix / "tfr_lfp_traces_layer"
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    layer_results = {}
    for layer in layers:
        try:
            res = session.lfp_tfr_trace_suite_omission(area=area, layer=layer, session_specific=True)
        except ValueError as e:
            layer_results[layer] = {"status": "failed", "error": str(e)}
            continue

        fig = res["figure"]
        meta = extract_suptitle_metadata(fig)
        svg_name = f"tfr_suite_{area}_{layer}.svg"
        svg_path = figures_dir / svg_name
        fig.savefig(svg_path, format="svg", bbox_inches="tight")
        plt.close(fig)

        # Guard against a real, observed race on Windows: stat()/read_text()
        # immediately after savefig() has occasionally reported 0 bytes for a
        # file that was already fully written (confirmed non-zero on
        # immediate re-check) - retry briefly rather than writing a false
        # "0 bytes" claim into the report.
        svg_bytes = svg_path.stat().st_size
        if svg_bytes == 0:
            time.sleep(0.2)
            svg_bytes = svg_path.stat().st_size
            if svg_bytes == 0:
                raise RuntimeError(f"{svg_path} is 0 bytes after retry - real save failure, not a transient race")

        n_paths = svg_path.read_text(encoding="utf-8").count("<path ")
        layer_results[layer] = {
            "status": res["status"],
            "svg_path": str(svg_path),
            "svg_bytes": svg_bytes,
            "svg_path_elements": n_paths,
            **meta,
        }

    receipt["layers"] = layer_results
    receipt["status"] = "completed" if any(
        v.get("status") == "completed" for v in layer_results.values()
    ) else "failed"

    # Markdown report page (SVG-embedding convention per jnwb/markdown_report.py)
    lines = [
        f"# Suite 02: LFP TFR Traces by Layer -- {session_prefix}",
        "",
        f"Area: **{area}** (auto-selected: real superficial AND deep channel masks "
        f"both present for this session's probe).",
        "",
        "Source: `jnwb.session.OmissionSession.lfp_tfr_trace_suite_omission` "
        "(`session_specific=True`), generated by "
        "`scripts/build_suite_02_tfr_layer_reports.py`.",
        "",
    ]
    for layer in layers:
        r = layer_results.get(layer, {})
        lines.append(f"## {layer.capitalize()} layer")
        lines.append("")
        if r.get("status") != "completed":
            lines.append(f"*(failed: {r.get('error', 'unknown error')})*")
            lines.append("")
            continue
        lines.append(f"- N trials/slot: {r['n_trials']}")
        lines.append(f"- Significant bands (0-500ms window, t-test AND Mann-Whitney p<0.05): {r['significant_bands']}")
        lines.append(f"- SVG: `figures/tfr_suite_{area}_{layer}.svg` ({r['svg_bytes']} bytes, {r['svg_path_elements']} path elements)")
        lines.append("")
        lines.append(f"![{area} {layer} TFR trace suite](figures/tfr_suite_{area}_{layer}.svg)")
        lines.append("")

    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    receipt["report_path"] = str(out_dir / "index.md")
    return receipt


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nwb", type=Path, default=None,
                    help="Path to a single .nwb file. If omitted, use --all-ready.")
    p.add_argument("--area", default=None,
                    help="Brain area. If omitted, auto-selected per session from real "
                         "channel-mask coverage.")
    p.add_argument("--layers", nargs="+", default=["superficial", "deep"],
                    choices=["superficial", "deep"])
    p.add_argument("--all-ready", action="store_true",
                    help="Run every session in --readiness-csv with suite_tfr_ready=True "
                         "and short_nwb=False, skipping --skip-sessions.")
    p.add_argument("--readiness-csv", type=Path,
                    default=REPO_ROOT / "artifacts/data/session_readiness.csv")
    p.add_argument("--tfr-dir", type=Path, default=Path("D:/workspace/data/tfr_arrays"))
    p.add_argument("--layer-masks", type=Path,
                    default=REPO_ROOT / "outputs/publication_visual_review/area_layer_tfr/layer_masks.json")
    p.add_argument("--out-dir", type=Path, default=REPO_ROOT / "outputs/markdown_reports")
    p.add_argument("--skip-sessions", nargs="*", default=sorted(DEFAULT_SKIP_SESSIONS),
                    help="session_prefix values to never touch (default: sessions with an "
                         "in-progress TFR precompute).")
    return p.parse_args()


def main():
    args = parse_args()
    layer_masks_cache = load_layer_masks(args.layer_masks)

    if args.nwb is not None:
        jobs = [(args.nwb, args.area)]
    elif args.all_ready:
        df = pd.read_csv(args.readiness_csv)
        ready = df[(df["suite_tfr_ready"] == True) & (df["short_nwb"] == False)]  # noqa: E712
        jobs = []
        for _, row in ready.iterrows():
            if row["session_prefix"] in args.skip_sessions:
                print(f"SKIP {row['session_prefix']}: in --skip-sessions (pending TFR precompute)")
                continue
            jobs.append((Path(row["nwb_path"]), args.area))
    else:
        raise SystemExit("Specify --nwb <path> or --all-ready")

    receipts = []
    for nwb_path, area in jobs:
        print(f"=== {nwb_path.name} ===")
        if not nwb_path.exists():
            print(f"  SKIP: file not found: {nwb_path}")
            receipts.append({"session": nwb_path.stem, "status": "skipped", "reason": "file not found"})
            continue
        receipt = run_one_session(
            nwb_path, area, args.layers, args.tfr_dir, args.layer_masks, args.out_dir, layer_masks_cache
        )
        print(f"  status={receipt['status']} area={receipt.get('area')} reason={receipt.get('reason', '')}")
        for layer, r in receipt.get("layers", {}).items():
            if r.get("status") == "completed":
                print(f"    {layer}: N={r['n_trials']} sig={r['significant_bands']} "
                      f"svg={r['svg_bytes']}B paths={r['svg_path_elements']}")
            else:
                print(f"    {layer}: FAILED {r.get('error')}")
        receipts.append(receipt)

    n_ok = sum(1 for r in receipts if r["status"] == "completed")
    n_skip = sum(1 for r in receipts if r["status"] == "skipped")
    n_fail = sum(1 for r in receipts if r["status"] == "failed")
    print(f"\nDone: {n_ok} completed, {n_skip} skipped, {n_fail} failed (of {len(receipts)})")
    return receipts


if __name__ == "__main__":
    main()
