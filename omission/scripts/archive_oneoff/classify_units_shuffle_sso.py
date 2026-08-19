"""
Classify one NWB with shuffle-controlled S+/S-/O+ rules and write updated tables.

Default pilot: sub-C31o_ses-230816_rec.nwb

Writes:
  outputs/classification/{stem}_shuffle_class.csv
  outputs/classification/{stem}_prevalence.json
  D:/analysis/nwb/f005_{ses}/f005_{ses}_classification_shuffle.csv  (if f005 dir exists)

Also refreshes the Suite-01 pilot rasters for one unit per class when --rasters.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import omission as oa
from omission.jnwb_ext.unit_classification import (
    ClassificationConfig,
    classify_session_units,
    prevalence_summary,
)
from omission.jnwb_ext.viz import raster_suite_omission

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("classify_shuffle")


def _stem_session(nwb_path: Path) -> str:
    # sub-C31o_ses-230816_rec.nwb → 230816
    name = nwb_path.stem
    if "ses-" in name:
        return name.split("ses-")[1].split("_")[0]
    return name


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--nwb",
        default=r"D:/analysis/nwb/sub-C31o_ses-230816_rec.nwb",
        help="Path to NWB file",
    )
    ap.add_argument("--n-shuffles", type=int, default=1000)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--no-fdr", action="store_true")
    ap.add_argument("--max-units", type=int, default=None, help="Debug: limit unit count")
    ap.add_argument("--rasters", action="store_true", help="Write one raster per class")
    args = ap.parse_args()

    nwb_path = Path(args.nwb)
    if not nwb_path.is_file():
        raise FileNotFoundError(nwb_path)

    cfg = ClassificationConfig(
        n_shuffles=args.n_shuffles,
        alpha=args.alpha,
        apply_fdr=not args.no_fdr,
    )

    log.info("Loading %s", nwb_path)
    session = oa.read(str(nwb_path), context="omission_glo_passive")
    unit_ids = list(session._units_df.index)
    if args.max_units is not None:
        unit_ids = unit_ids[: args.max_units]
        log.info("Limiting to first %d units", len(unit_ids))

    log.info("Classifying %d units (n_shuffles=%d, fdr=%s)", len(unit_ids), cfg.n_shuffles, cfg.apply_fdr)
    df = classify_session_units(session, cfg=cfg, unit_ids=unit_ids)
    # Prefer Other over legacy Null in exports
    if "display_class" in df.columns:
        df["display_class"] = df["display_class"].replace({"Null": "Other"})
    prev = prevalence_summary(df)
    log.info("Prevalence: %s", prev)
    log.info("Counts:\n%s", df["display_class"].value_counts().to_string())

    out_dir = Path("outputs/classification")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = nwb_path.stem
    csv_path = out_dir / f"{stem}_shuffle_class.csv"
    json_path = out_dir / f"{stem}_prevalence.json"
    df.to_csv(csv_path)
    json_path.write_text(json.dumps(prev, indent=2), encoding="utf-8")
    log.info("Wrote %s", csv_path)
    log.info("Wrote %s", json_path)

    # Update sidecar table next to legacy f005 lock when present
    ses = _stem_session(nwb_path)
    f005_dir = Path(r"D:/analysis/nwb") / f"f005_{ses}"
    if f005_dir.is_dir():
        side = f005_dir / f"f005_{ses}_classification_shuffle.csv"
        export = df.reset_index()[["unit_id", "display_class", "area", "layer", "firing_rate",
                                   "is_s_plus", "is_s_minus", "is_o_plus",
                                   "stim_effect_hz", "q_stim_shuffle",
                                   "om_vs_base_effect_hz", "q_om_vs_base_shuffle",
                                   "om_vs_ctrl_effect_hz", "q_om_vs_ctrl_shuffle"]]
        export.insert(0, "session", stem)
        export.to_csv(side, index=False)
        log.info("Wrote sidecar %s", side)

    if args.rasters and not df.empty:
        raster_root = Path("outputs/rasters") / stem / "shuffle_class"
        raster_root.mkdir(parents=True, exist_ok=True)
        for cls in ("S+", "S-", "O+"):
            subset = df[df["display_class"] == cls]
            if subset.empty:
                log.warning("No units for class %s — skip raster", cls)
                continue
            # Prefer FEF/PFC for O+; else first unit
            if cls == "O+":
                pref = subset[subset["area"].astype(str).isin(["FEF", "PFC"])]
                pick = pref.index[0] if len(pref) else subset.index[0]
            else:
                pick = subset.index[0]
            # Stamp flags for metadata box
            for col, val in (
                ("sig_s_plus", cls == "S+"),
                ("sig_s_minus", cls == "S-"),
                ("sig_o_plus", cls == "O+"),
            ):
                if col not in session._units_df.columns:
                    session._units_df[col] = False
                session._units_df.loc[pick, col] = val
            fig = raster_suite_omission(session, unit_id=int(pick))
            out_png = raster_root / cls.replace("+", "plus") / f"unit_{pick}.png"
            out_png.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(out_png, dpi=200, bbox_inches="tight")
            plt.close(fig)
            log.info("Raster %s unit %s -> %s", cls, pick, out_png)


if __name__ == "__main__":
    main()
