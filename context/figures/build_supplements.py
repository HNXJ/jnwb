r"""
Assemble the supplementary figures from panels the main-figure scripts already wrote.

WHY IT WORKS THIS WAY
    Supplements carry no analysis of their own. Every panel here was drawn by one of the
    figNN_*.py scripts, under that script's receipt, and is reused rather than redrawn. If a
    supplement needs a panel nothing emits, the panel is added to the owning figure's script
    -- never to this file. That keeps one generator and one receipt behind every panel in the
    repository.

    A supplement whose panels are absent is skipped and reported, not faked. Figures 6 and 7
    have no analysis yet, so the supplements that would draw on them are listed as pending.

USAGE
    python build_supplements.py            assemble everything whose panels exist
    python build_supplements.py --list     print the plan and what is missing, write nothing

OUTPUT
    supplements/figSNN_<description>.svg
    supplements/supplements_receipt.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import platform
from datetime import datetime, timezone

from svgassemble import PT_PER_IN, assemble

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "supplements")

F1 = "fig01_recording_topology_and_paradigm/svg"
F2 = "fig02_spiking_exemplar_rasters/svg"
F3 = "fig03_unit_census/svg"
F4 = "fig04_v1_pfc_condition_tfr/svg"
F5 = "fig05_band_power_hierarchy/svg"
F6 = "fig06_band_power_coupling/svg"
F7 = "fig07_lfp_spike_coupling/svg"

# (number, slug, panel patterns in reading order, columns, caption[, width_pt])
# Patterns are globs resolved against this directory; each pattern may match several panels.
#
# WIDTH. The default is the 468 pt portrait text column. The time-frequency panels are drawn
# 27 inches wide, so casting one to 468 pt leaves it 180 pt tall and unreadable. Those are
# given LANDSCAPE, the text column of a rotated page, and are meant to be placed on a rotated
# page in the submission. Rescaling them at the drawing stage instead would break the
# typography, which is tuned at the drawn width.
LANDSCAPE = 9.5 * PT_PER_IN     # 684 pt
PLAN = [
    (1, "recording_topology_full", [f"{F1}/fig01_full.svg"], 1,
     "The full-layout variant of figure 1, at the same page width."),
    (2, "paradigm_source_panels", [f"{F1}/02_paradigm.svg"], 1,
     "The paradigm panel at full size, with the trial timing legible."),
    (3, "census_area_by_question", [f"{F3}/supp_fig03_area_by_question.svg"], 1,
     "Prevalence of each of the four questions in each area."),
    (4, "census_panels_at_size", [f"{F3}/fig03_a_questions.svg", f"{F3}/fig03_b_classes.svg",
                                  f"{F3}/fig03_c_by_area.svg", f"{F3}/fig03_d_by_type.svg"], 1,
     "The four census panels at full width, with every count and interval readable."),
    (5, "tfr_V1_V2", [f"{F4}/pair_V1_V2.svg"], 1,
     "Time-frequency maps and five-band traces for V1 and V2.", LANDSCAPE),
    (6, "tfr_V3ad_V4", [f"{F4}/pair_V3ad_V4.svg"], 1,
     "Time-frequency maps and five-band traces for V3a/d and V4.", LANDSCAPE),
    (7, "tfr_MT_MST", [f"{F4}/pair_MT_MST.svg"], 1,
     "Time-frequency maps and five-band traces for MT and MST.", LANDSCAPE),
    (8, "tfr_TEO_FST", [f"{F4}/pair_TEO_FST.svg"], 1,
     "Time-frequency maps and five-band traces for TEO and FST.", LANDSCAPE),
    (9, "tfr_FEF_PFC", [f"{F4}/pair_FEF_PFC.svg"], 1,
     "Time-frequency maps and five-band traces for FEF and PFC.", LANDSCAPE),
    (10, "tfr_all_areas_grid", [f"{F4}/all_areas_grid.svg"], 1,
     "All ten areas on one common colour scale.", LANDSCAPE),
    (11, "tfr_layers_V1_V4", [f"{F4}/supp_V1_V4_layers.svg"], 1,
     "Superficial and deep compartments of V1 and V4.", LANDSCAPE),
    (12, "tfr_layers_MT_FEF", [f"{F4}/supp_MT_FEF_layers.svg"], 1,
     "Superficial and deep compartments of MT and FEF.", LANDSCAPE),
    (13, "tfr_layers_TEO_PFC", [f"{F4}/supp_TEO_PFC_layers.svg"], 1,
     "Superficial and deep compartments of TEO and PFC.", LANDSCAPE),
    (14, "tfr_early_visual", [f"{F4}/supp_early_visual_areas.svg"], 1,
     "V1, V2, V3a/d and V4 on one page.", LANDSCAPE),
    (15, "tfr_mid_level", [f"{F4}/supp_mid_level_areas.svg"], 1,
     "MT, MST, TEO and FST on one page.", LANDSCAPE),
    (16, "tfr_frontal", [f"{F4}/supp_frontal_areas.svg"], 1,
     "FEF and PFC on one page.", LANDSCAPE),
    (17, "band_hierarchy_superficial", [f"{F5}/fig05_band_hierarchy_sup.svg"], 1,
     "Band-power hierarchy restricted to superficial channels."),
    (18, "band_hierarchy_deep", [f"{F5}/fig05_band_hierarchy_deep.svg"], 1,
     "Band-power hierarchy restricted to deep channels."),
    (19, "band_hierarchy_by_layer", [f"{F5}/fig05_band_hierarchy_sup.svg",
                                     f"{F5}/fig05_band_hierarchy_mid.svg",
                                     f"{F5}/fig05_band_hierarchy_deep.svg"], 1,
     "The three laminar compartments stacked, so the layer difference is read down a column."),
    (20, "census_presence_layer_correlation_traces",
     [f"{F3}/fig03_p1_presence_by_area.svg", f"{F3}/fig03_f_layer_by_area.svg",
      f"{F3}/fig03_g_stim_omission_correlation.svg", f"{F3}/fig03_h_group_traces.svg"], 1,
     "Presence composition and layer composition by area, the firing-rate/omission-effect "
     "correlation with its shuffle null, and the five-class omission-aligned population PSTH, "
     "at full width. The main figure's own three panels (presence, functionality, RXRR "
     "template trace) are not repeated here."),
    (21, "census_rxrr_template_trace_full_width",
     [f"{F3}/fig03_p3_template_trace_rxrr.svg"], 1,
     "The seven-class RXRR full-trial template trace at full width, for reading the O++ "
     "trace (n = 3) against its SEM band."),
    (22, "coupling_stimulus_window", [f"{F6}/fig06_stimulus_matrices.svg"], 1,
     "LFP-LFP imaginary-coherency matrices during the stimulus window (p1, present in every "
     "condition) -- the main figure shows the omission window (RXRR, p2) only."),
    (23, "spike_field_coupling_stimulus_window", [f"{F7}/fig07_stimulus_ppc.svg"], 1,
     "Spike-LFP PPC during the stimulus window (p1, present in every condition) -- the main "
     "figure shows the omission window (RXRR, p2) only."),
]

# Supplements that cannot be built because their figure has no analysis yet.
PENDING = {
}


def resolve(patterns):
    out = []
    for p in patterns:
        out.extend(sorted(glob.glob(os.path.join(HERE, p))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print the plan, write nothing")
    args = ap.parse_args()

    # Numbering drifts when PLAN entries are reordered/renamed across edits, and unlike a
    # figNN.svg (one name, safely overwritten), a renumbered supplement leaves its old file
    # behind under the old number -- two different figures end up sharing an "S07", say, one
    # current and one orphaned. Confirmed on 2026-07-29: 19 of 40 files on disk were stale
    # duplicates from an earlier numbering pass. Clean anything not in the current PLAN first.
    if not args.list:
        current_names = {f"figS{num:02d}_{slug}.svg" for num, slug, *_ in PLAN}
        current_names |= {f"figS{num:02d}_{slug}.png" for num, slug, *_ in PLAN}
        for existing in glob.glob(os.path.join(OUT, "figS*")):
            if os.path.basename(existing) not in current_names:
                os.remove(existing)
                print(f"  removed stale  {os.path.basename(existing)}")

    built, skipped = [], []
    for num, slug, pats, ncol, caption, *rest in PLAN:
        width = rest[0] if rest else None
        panels = resolve(pats)
        name = f"figS{num:02d}_{slug}"
        if not panels:
            skipped.append({"figure": name, "reason": "no panel matched " + "; ".join(pats)})
            print(f"  skip  {name}  (no panel matched)")
            continue
        if args.list:
            print(f"  plan  {name}  <- {len(panels)} panel(s)")
            continue
        path, w, h = assemble(panels, os.path.join(OUT, name + ".svg"), ncol=ncol,
                              letters=len(panels) > 1,
                              **({"width": width} if width else {}))
        built.append({"figure": name, "caption": caption, "ncol": ncol,
                      "panels": [os.path.relpath(p, HERE).replace("\\", "/") for p in panels],
                      "width_pt": round(w, 2), "height_pt": round(h, 2),
                      "orientation": "landscape" if width else "portrait"})
        print(f"  built {name}  {len(panels)} panel(s)  {w:.0f} x {h:.0f} pt")

    for k, v in PENDING.items():
        print(f"  pending  {k}  -- {v}")

    if args.list:
        return
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "rule": "supplements carry no analysis; every panel is reused from a main figure's "
                "svg/ folder and inherits that figure's receipt",
        "built": built, "skipped": skipped, "pending": PENDING,
        "env": {"python": platform.python_version()},
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "supplements_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\n{len(built)} supplements built, {len(skipped)} skipped, "
          f"{len(PENDING)} pending on figures 6 and 7")


if __name__ == "__main__":
    main()
