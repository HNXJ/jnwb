"""
Build / refresh the grand S+/S-/O+/Other unit table across all NWBs.

Same engine as Suite 01 notebook:

  python scripts/build_grand_unit_table_shuffle_sso.py
  python scripts/build_grand_unit_table_shuffle_sso.py --max-files 1   # smoke
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from jnwb.unit_classification import (
    ClassificationConfig,
    classify_all_nwbs,
    config_to_dict,
    prevalence_summary,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("grand_table")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nwb-root", default=r"D:/analysis/nwb")
    ap.add_argument(
        "--grand",
        default="outputs/classification/grand_unit_table_shuffle_sso.csv",
    )
    ap.add_argument(
        "--per-session-dir",
        default="outputs/classification/per_session",
    )
    ap.add_argument("--n-shuffles", type=int, default=1000)
    ap.add_argument("--max-files", type=int, default=None)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cfg = ClassificationConfig(n_shuffles=args.n_shuffles, seed=args.seed)
    log.info("Config: %s", json.dumps(config_to_dict(cfg)))

    grand = classify_all_nwbs(
        nwb_root=args.nwb_root,
        grand_path=args.grand,
        cfg=cfg,
        per_session_dir=args.per_session_dir,
        max_files=args.max_files,
    )
    if grand is None or len(grand) == 0:
        log.error("No rows written")
        return
    prev = prevalence_summary(grand)
    log.info("Overall prevalence: %s", prev)
    log.info("Wrote %s (%d rows, %d sessions)", args.grand, len(grand), grand["nwb_stem"].nunique())


if __name__ == "__main__":
    main()
