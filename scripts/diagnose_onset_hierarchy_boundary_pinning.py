r"""
Diagnostic for outputs/classification/onset_hierarchy/cell_fits.csv (built by
scripts/fit_class_onset_latency.py, 2026-08-15): quantify how much of that pipeline's onset
estimate is driven by a boundary-pinning failure mode of jnwb.onset_fitting.fit_exponential_onset,
distinct from the "low r2 / did not converge" gate that bootstrap_area_class already applies.

WHY THIS IS A SEPARATE DIAGNOSTIC, NOT A FIX TO THE PIPELINE FILES
    fit_class_onset_latency.py's own bootstrap_area_class docstring already excludes fits with
    r2 < MIN_R2 (0.3) or converged=False, on the reasoning that a degenerate (near-zero-amplitude)
    fit parks t0 near a bound with a flat residual -- not a real onset. That gate is working as
    designed and is untouched here.

    This script flags any REMAINING gate-passing cell (r2 >= 0.3, converged) whose t0 is still
    pinned near 0ms -- the earliest value the causality bound (t0 in [0, window_end]) permits --
    on the reasoning that the model cannot represent a rise that began before the window opens,
    so it is architecturally forced to place the entire visible rise at the earliest legal point
    regardless of how gradual that rise actually looks.

    2026-08-15 REVISION: the first version of this script only counted a cell as pinned when
    t0<1ms AND tau was ALSO pinned near its own lower bound (1.0ms, jnwb.onset_fitting's
    tau_bounds default) -- reasoning that a fast, small-tau, near-instant step was the only
    tell-tale shape. Manually inspecting a flagged cell (S+ V3a/d, area_class_summary.csv's
    11.9ms group mean) found a second, distinct shape the original version missed entirely: 4 of
    6 sessions had t0 pinned at ~0ms but with tau spread across the FULL range up to its upper
    bound (150ms) rather than pinned low -- i.e. the model is not fitting a fast step, it is
    fitting a SLOW, gradual, already-in-progress ramp and compressing it against the t0=0 wall,
    using a large tau to approximate whatever curvature is visible inside the window. Both shapes
    share the same root cause (t0 forced to its earliest legal value by a pre-window rise the
    causality bound can't let the model see) and both make the reported onset untrustworthy, so
    both are now counted as "pinned" -- distinguished by a hard/soft sub-classification for
    interpretability, but pooled in the headline number since neither is a real onset estimate.

OUTPUT
    outputs/classification/onset_hierarchy/boundary_pinning_diagnostic.csv -- per area x class:
        n_cells, n_r2_gated_out, n_gate_pass, n_pinned_hard (t0~0, tau~tau_lo -- fast/degenerate
        shape), n_pinned_soft (t0~0, tau NOT at its lower bound -- slow ramp compressed against
        the wall), n_pinned_total, n_clean, pinned_fraction_of_gate_pass.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CELL_CSV = REPO_ROOT / "outputs" / "classification" / "onset_hierarchy" / "cell_fits.csv"
OUT_CSV = REPO_ROOT / "outputs" / "classification" / "onset_hierarchy" / "boundary_pinning_diagnostic.csv"

MIN_R2 = 0.3
TAU_LO = 1.0
T0_PIN_THRESH_MS = 1.0
TAU_PIN_THRESH = 1.01


def classify(row) -> str:
    if row["t0"] >= T0_PIN_THRESH_MS:
        return "clean"
    return "pinned_hard" if row["tau"] <= TAU_PIN_THRESH else "pinned_soft"


def main():
    df = pd.read_csv(CELL_CSV)
    df["gate_pass"] = (df["r2"] >= MIN_R2) & (df["converged"].astype(bool))
    df["category"] = df.apply(classify, axis=1)
    df.loc[~df["gate_pass"], "category"] = "r2_gated_out"

    rows = []
    for (area, cls), g in df.groupby(["area", "class"]):
        gp = g[g["gate_pass"]]
        counts = gp["category"].value_counts()
        n_hard = int(counts.get("pinned_hard", 0))
        n_soft = int(counts.get("pinned_soft", 0))
        n_pinned = n_hard + n_soft
        rows.append({
            "area": area, "class": cls,
            "n_cells_total": int(len(g)),
            "n_r2_gated_out": int(len(g) - len(gp)),
            "n_gate_pass": int(len(gp)),
            "n_pinned_hard": n_hard,
            "n_pinned_soft": n_soft,
            "n_pinned_total": n_pinned,
            "n_clean": int(len(gp) - n_pinned),
            "pinned_fraction_of_gate_pass": float(n_pinned / len(gp)) if len(gp) else float("nan"),
        })
    out = pd.DataFrame(rows).sort_values(["class", "area"])
    out.to_csv(OUT_CSV, index=False)
    print(f"WROTE {OUT_CSV}")
    print(out.to_string(index=False))

    gated = df[df["gate_pass"]]
    total_gate_pass = int(gated.shape[0])
    total_hard = int((gated["category"] == "pinned_hard").sum())
    total_soft = int((gated["category"] == "pinned_soft").sum())
    total_pinned = total_hard + total_soft
    print(f"\nOverall: {total_pinned}/{total_gate_pass} gate-passing cells "
          f"({100.0*total_pinned/total_gate_pass:.1f}%) have t0<{T0_PIN_THRESH_MS}ms "
          f"(boundary-pinned) -- {total_hard} hard (tau also <= {TAU_PIN_THRESH}ms) + "
          f"{total_soft} soft (tau not at its lower bound, i.e. a slow ramp compressed "
          f"against the t0=0 wall).")


if __name__ == "__main__":
    main()
