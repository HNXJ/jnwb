"""
Build nested O++ census from R-family template-correlation table.

Inclusive O+ headline (421/8597 = 4.90%) is unchanged.
O++ = FEF/PFC units with mean_correlation >= 0.60 and permutation_pval <= 0.05
on random-control templates (RXRR/RRXR/RRRX) from grand_oplus_units.csv.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from jnwb.unit_classification import (
    OPLUSPLUS_METHOD_ID,
    OPlusPlusTemplateConfig,
    assign_o_plusplus_from_template_table,
    oplusplus_census_summary,
)
from jnwb import paths as _P

REPO = Path(_P.REPO_ROOT)
SRC = REPO / "outputs" / "classification" / "grand_oplus_units.csv"
OUT_CSV = REPO / "outputs" / "classification" / "grand_oplusplus_units.csv"
OUT_JSON = REPO / "artifacts" / "data" / "oplusplus_census.json"


def bootstrap_ci(n: int, total: int, n_boot: int = 10000, seed: int = 42):
    rng = np.random.default_rng(seed)
    if total <= 0:
        return 0.0, 0.0, 0.0
    p = n / total
    draws = rng.binomial(total, p, size=n_boot) / total
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(p * 100), float(lo * 100), float(hi * 100)


def main():
    cfg = OPlusPlusTemplateConfig()
    df = pd.read_csv(SRC)
    labeled = assign_o_plusplus_from_template_table(df, cfg)
    summary = oplusplus_census_summary(labeled)
    n = summary["n_o_plusplus"]
    # Bootstrap CI relative to inclusive primary census denominator (8597)
    pct, lo, hi = bootstrap_ci(n, 8597)
    # Also vs inclusive O+ candidates in this table
    pct_of_cand, lo_c, hi_c = bootstrap_ci(n, len(labeled))

    out_units = labeled[labeled["is_o_plusplus"]].copy()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_units.to_csv(OUT_CSV, index=False)

    receipt = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": OPLUSPLUS_METHOD_ID,
        "source_table": str(SRC),
        "criteria": {
            "templates": ["RXRR", "RRXR", "RRRX"],
            "min_mean_correlation": cfg.min_mean_correlation,
            "max_permutation_pval": cfg.max_permutation_pval,
            "require_higher_order_areas": list(cfg.higher_order_areas),
        },
        "inclusive_o_plus_headline": {
            "n": 421,
            "total": 8597,
            "pct": 4.90,
            "note": "Unchanged primary census; O++ is nested subset.",
        },
        "o_plusplus": {
            **summary,
            "pct_of_primary_census": pct,
            "bootstrap_95ci_primary_pct": [lo, hi],
            "pct_of_template_candidates": pct_of_cand,
            "bootstrap_95ci_candidate_pct": [lo_c, hi_c],
            "in_target_band_25_60": bool(25 <= n <= 60),
        },
        "outputs": {"csv": str(OUT_CSV), "json": str(OUT_JSON)},
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt["o_plusplus"], indent=2))
    print("Wrote", OUT_CSV, "n=", n)
    print("Wrote", OUT_JSON)


if __name__ == "__main__":
    main()
