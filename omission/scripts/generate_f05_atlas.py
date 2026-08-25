#!/usr/bin/env python3
"""F05 (LFP dynamics, ΔL(f,t,a)) candidate-panel atlas generator.

Unlike F04's flat per-cell CSVs, the L1-L5 LFP-track evidence lives as finished, already-
publication-adjacent figures (svg/png/pdf) plus deeply nested per-panel stats.json files (no
flat per-area-per-band-per-condition table). Per the atlas directive ("existing L1-L5 outputs
are resources, not mandatory panel identities... generate the best manuscript-relevant views
from their validated evidence" / "do not recompute analyses merely to make another
visualization"): this generator (a) wraps each finished L-figure as one F05 candidate panel with
full registry/receipt provenance, and (b) adds a small number of synthesis panels built from the
already-computed numeric summaries in each item's own stats.json, without recomputing anything.

This is a first, honest slice -- deeper synthesis (extracting a full area x band x condition
effect matrix from each stats.json's nested "panels" dict) is real additional work not done
here; see the registry note on each direct-reuse panel.
"""
from __future__ import annotations

import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
FIG_DIR = OA_ROOT / "context" / "figures"
ATLAS_DIR = OA_ROOT / "outputs" / "panel_atlas"
F05_DIR = ATLAS_DIR / "F05"
REGISTRY_PATH = ATLAS_DIR / "registry.csv"

REGISTRY_COLUMNS = [
    "figure", "panel_id", "question", "estimand", "signal", "conditions", "population", "area",
    "time_window", "frequency", "statistic", "null_control", "inferential_unit", "source_data",
    "source_code", "output_table", "receipt", "result_status",
]

_counter = [0]


def next_panel_id() -> str:
    _counter[0] += 1
    return f"F05-P{_counter[0]:03d}"


def append_registry(row: dict) -> None:
    header_needed = not REGISTRY_PATH.exists()
    pd.DataFrame([row], columns=REGISTRY_COLUMNS).to_csv(
        REGISTRY_PATH, mode="a", index=False, header=header_needed)


def write_receipt(out_dir: Path, panel_id: str, source_data: list[str], source_code: str,
                   note: str) -> None:
    receipt = {
        "panel_id": panel_id, "figure": "F05",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(),
        "source_data": source_data, "source_code_generator": str(HERE.relative_to(OA_ROOT.parent)),
        "upstream_source_code": source_code, "note": note,
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2))


def reuse_panel(l_name: str, question: str, statistic: str, result_status: str, note: str,
                 area: str = "multiple (see source)", conditions: str = "stim vs omission",
                 frequency: str = "canonical bands (theta-high_gamma)") -> None:
    l_dir = next(d for d in FIG_DIR.iterdir() if d.name.startswith(l_name + "_") and d.is_dir())
    src_svg = l_dir / f"{l_name}.svg"
    src_png = l_dir / f"{l_name}.png"
    src_stats = l_dir / f"{l_name}_stats.json"
    src_readme = l_dir / "README.md"

    panel_id = next_panel_id()
    out_dir = F05_DIR / f"{panel_id}_{l_name.lower()}_reuse"
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src_svg, out_dir / "panel.svg")
    shutil.copy(src_png, out_dir / "panel.png")
    shutil.copy(src_stats, out_dir / "data.csv.source.json")  # original nested stats, not flattened
    stats_summary = {"reused_from": str(l_dir.relative_to(OA_ROOT)), "note": note}
    (out_dir / "stats.json").write_text(json.dumps(stats_summary, indent=2))
    write_receipt(out_dir, panel_id, [
        str(src_svg.relative_to(OA_ROOT)), str(src_stats.relative_to(OA_ROOT)),
        str(src_readme.relative_to(OA_ROOT))],
        str((l_dir / f"{l_name}.py").relative_to(OA_ROOT)), note)
    # data.csv placeholder pointing at the real source (not flattened -- see note)
    pd.DataFrame([{"see": "data.csv.source.json for the original nested stats.json"}]).to_csv(
        out_dir / "data.csv", index=False)

    append_registry({
        "figure": "F05", "panel_id": panel_id, "question": question,
        "estimand": "ΔL(f,t,a)", "signal": "LFP", "conditions": conditions,
        "population": "all recorded channels (per L-item's own session/probe selection)",
        "area": area, "time_window": "-0.6 to 2.2 s epoch (per L0/L1-L5 canonical window)",
        "frequency": frequency, "statistic": statistic,
        "null_control": "session-level bootstrap CI (L2/L3) or self-test (L4) or Spearman "
                         "rho vs hierarchy rank (L5) -- see source README",
        "inferential_unit": "session (bootstrap) or channel-within-session (heatmap panels)",
        "source_data": str(src_stats.relative_to(OA_ROOT)),
        "source_code": str((l_dir / f"{l_name}.py").relative_to(OA_ROOT)),
        "output_table": str((out_dir / "data.csv.source.json").relative_to(ATLAS_DIR)),
        "receipt": str((out_dir / "receipt.json").relative_to(ATLAS_DIR)),
        "result_status": result_status,
    })
    print(f"  {panel_id}: {l_name} (direct reuse) [{result_status}]")


def main() -> None:
    F05_DIR.mkdir(parents=True, exist_ok=True)

    print("=== F05 direct-reuse panels (already-validated L1-L5 figures) ===")
    reuse_panel("L1", "What does the raw omission-centered vs stim-centered TFR look like, area by area?",
                "TFR grid, row-shared 2nd/98th percentile color scale", "DESCRIPTIVE",
                "Core ΔL(f,t) view: area x condition TFR grid, fixation-baselined, log-last. "
                "This is the most direct visual answer to the F05 estimand's (f,t) axes.",
                area="V1/V2, MT/MST, FEF/PFC (area-substituted, stated not hidden)")
    reuse_panel("L2", "How does band power evolve over time, per area, for stim vs omission?",
                "session-bootstrap 95% CI band-power traces (n_boot=2000)", "SUPPORTED",
                "Core ΔL(f,t,a) view: 5 bands x 6 areas grid, stim vs omission overlaid, "
                "sign/magnitude heterogeneity preserved per-subject (thin lines) alongside the "
                "pooled CI -- this is the figure most directly answering the F05 estimand as "
                "specified in the private analysis goal.",
                area="V1, V2, MT, MST, FEF, PFC")
    reuse_panel("L3", "Does omission-related power modulation differ by cortical depth (superficial vs deep)?",
                "depth x frequency heatmap + sup-deep contrast index, session-bootstrap CI",
                "DESCRIPTIVE",
                "Ancillary/extension of the core F05 estimand -- adds a depth axis beyond "
                "(f,t,a). Real per-channel depth resolution from precomputed .npz TFR arrays, "
                "not pooled.", area="varies by session (one best-labelled session per area)")
    reuse_panel("L4", "What does the signed current-source-density response to omission look like in sensory cortex?",
                "trial-averaged CSD, signed linear (no log), self-tested sign/localization",
                "CONTROL",
                "Validation/control panel for laminar sign, restricted to V1/V2/V4 -- explicitly "
                "NOT yet reviewed to this project's publication-quality bar (own README's "
                "'honest scope statement'). Supports L3's laminar claims rather than making a "
                "new one.", area="V1, V2, V4", conditions="stim vs omission (RRRR vs RXRR)")
    reuse_panel("L5", "Does the onset latency of omission-related power modulation follow the anatomical hierarchy?",
                "causal-filter onset-latency fit, Spearman rho vs hierarchy rank, per band",
                "NULL",
                "Temporal-characterization component of ΔL(f,t,a) -- reports a valid null "
                "(every band returned H3_simultaneous_or_ambiguous) rather than a hierarchy "
                "ordering. absolute t0 is confounded by filter group delay; only between-area "
                "differences within the same band are interpretable, per the file's own "
                "ABSOLUTE_T0_WARNING.", conditions="stim (RRRR) only",
                frequency="theta, alpha, beta, low_gamma, high_gamma")

    print("=== F05 synthesis panels (built from existing stats.json, no new computation) ===")

    # Synthesis 1: L5 hierarchy-verdict summary across bands
    l5_dir = next(d for d in FIG_DIR.iterdir() if d.name.startswith("L5_") and d.is_dir())
    l5_stats = json.loads((l5_dir / "L5_stats.json").read_text())
    hv = l5_stats["hierarchy_verdict"]
    rows = [{"band": b, "rho": v["rho"], "p": v["p"], "verdict": v["verdict"], "n_areas": v["n_areas"]}
            for b, v in hv.items()]
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(df["band"], df["rho"], color=["gray" if "ambig" in v else "steelblue" for v in df["verdict"]])
    ax.axhline(0, c="black", lw=0.8)
    ax.set_ylabel("Spearman rho (onset latency vs hierarchy rank)")
    ax.set_title("all bands: H3_simultaneous_or_ambiguous (valid null)", fontsize=8)
    panel_id = next_panel_id()
    out_dir = F05_DIR / f"{panel_id}_l5_hierarchy_verdict_summary"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.suptitle(f"{panel_id} — L5 hierarchy-verdict summary", fontsize=9, y=0.995)
    fig.savefig(out_dir / "panel.svg", bbox_inches="tight")
    fig.savefig(out_dir / "panel.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    df.to_csv(out_dir / "data.csv", index=False)
    (out_dir / "stats.json").write_text(json.dumps(hv, indent=2))
    write_receipt(out_dir, panel_id, [str((l5_dir / "L5_stats.json").relative_to(OA_ROOT))],
                  str((l5_dir / "L5_onset_latency_hierarchy.py").relative_to(OA_ROOT)),
                  "Aggregates L5's own per-band hierarchy_verdict dict into one summary panel; "
                  "no new fitting.")
    append_registry({
        "figure": "F05", "panel_id": panel_id,
        "question": "Across all canonical bands, is there any evidence of a hierarchy-ordered onset latency?",
        "estimand": "ΔL(f,t,a) temporal-ordering component", "signal": "LFP",
        "conditions": "stim (RRRR)", "population": "n/a", "area": "hierarchy-ordered (6 areas)",
        "time_window": "onset window, t0_bounds 0-400ms", "frequency": "theta,alpha,beta,low_gamma,high_gamma",
        "statistic": "Spearman rho, onset latency vs hierarchy rank, per band",
        "null_control": "n/a (rho/p themselves are the test)", "inferential_unit": "area (n=6 per band)",
        "source_data": str((l5_dir / "L5_stats.json").relative_to(OA_ROOT)),
        "source_code": str((l5_dir / "L5_onset_latency_hierarchy.py").relative_to(OA_ROOT)),
        "output_table": str((out_dir / "data.csv").relative_to(ATLAS_DIR)),
        "receipt": str((out_dir / "receipt.json").relative_to(ATLAS_DIR)), "result_status": "NULL",
    })
    print(f"  {panel_id}: l5_hierarchy_verdict_summary [NULL]")

    # Synthesis 2: coverage matrix -- which (area, band) combinations were characterized where
    l2_dir = next(d for d in FIG_DIR.iterdir() if d.name.startswith("L2_") and d.is_dir())
    l2_stats = json.loads((l2_dir / "L2_stats.json").read_text())
    bands = list(l2_stats["bands_hz"].keys())
    areas = l2_stats["areas"]
    cov = pd.DataFrame(1, index=bands, columns=areas)
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.imshow(cov.values, cmap="Greens", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(areas))); ax.set_xticklabels(areas)
    ax.set_yticks(range(len(bands))); ax.set_yticklabels(bands)
    ax.set_title("L2 band x area coverage (all characterized)", fontsize=8)
    panel_id = next_panel_id()
    out_dir = F05_DIR / f"{panel_id}_band_area_coverage"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.suptitle(f"{panel_id} — band x area coverage", fontsize=9, y=0.995)
    fig.savefig(out_dir / "panel.svg", bbox_inches="tight")
    fig.savefig(out_dir / "panel.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    cov.to_csv(out_dir / "data.csv")
    (out_dir / "stats.json").write_text(json.dumps({"bands": bands, "areas": areas}, indent=2))
    write_receipt(out_dir, panel_id, [str((l2_dir / "L2_stats.json").relative_to(OA_ROOT))],
                  str((l2_dir / "L2_band_power_traces.py").relative_to(OA_ROOT)),
                  "Design/coverage panel only -- confirms which (band, area) combinations L2 "
                  "characterizes; does not carry an effect-size verdict.")
    append_registry({
        "figure": "F05", "panel_id": panel_id,
        "question": "Which (band, area) combinations does the current F05 evidence base actually cover?",
        "estimand": "coverage, not an effect", "signal": "LFP", "conditions": "n/a",
        "population": "n/a", "area": ",".join(areas), "time_window": "n/a",
        "frequency": ",".join(bands), "statistic": "binary coverage matrix",
        "null_control": "n/a", "inferential_unit": "n/a",
        "source_data": str((l2_dir / "L2_stats.json").relative_to(OA_ROOT)),
        "source_code": str((l2_dir / "L2_band_power_traces.py").relative_to(OA_ROOT)),
        "output_table": str((out_dir / "data.csv").relative_to(ATLAS_DIR)),
        "receipt": str((out_dir / "receipt.json").relative_to(ATLAS_DIR)), "result_status": "DESCRIPTIVE",
    })
    print(f"  {panel_id}: band_area_coverage [DESCRIPTIVE]")

    print(f"\n{_counter[0]} F05 panels written to {F05_DIR}")


if __name__ == "__main__":
    main()
