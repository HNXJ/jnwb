r"""
scripts/fit_all_classes_onset_latency_per_unit.py

Per-neuron onset latency for all four functional families (Hamm, 2026-08-17):
"each of the groups; S++/S+; S--/S-; O++/O+; O--/O-; has an onset (that must be valid and more
than minimum causal onset); calculate each neuron's average onset; then per area; average onset;
will be calculated."

METHOD
    One onset fit per neuron per class it belongs to (a neuron can appear in more than one
    class). "Each neuron's average onset" = that neuron's own fitted t0 from its own
    trial-pooled rate trace (population_psth called with a single-unit list, one fit) -- this
    IS already the average across that neuron's own trials, by construction of the pooled PSTH
    it's fit against. No further per-neuron averaging step exists beyond that single fit.

    VALIDITY GATE (Hamm's explicit requirement this time, not just a flag as in the earlier S+
    sensitivity check): a neuron's onset only counts toward its area's average if
    r2>=MIN_R2 AND converged AND t0 >= MIN_VISUAL_LATENCY_MS (40ms). Units failing this are
    EXCLUDED from the area average, counted and reported, not silently averaged in. This
    directly removes the boundary-pinning artifact (t0 collapsing to ~0 on a noisy single-unit
    fit) found in the earlier S+-only per-unit run.

    Reuses jnwb.onset_fitting (causal_exp_smooth, fit_exponential_onset) and
    fit_class_onset_latency.py's fit_one_cell/population_psth/p1_onsets_s/omitted_slot_onsets_s
    UNMODIFIED (module-level MIN_UNITS overridden to 1 for single-unit calls, same pattern as
    fit_s_plus_onset_latency_s1_per_unit.py -- Conservation, no edit to the shared file).

POPULATIONS (four, three different source tables -- stated explicitly, not silently merged)
    S+  : unit_inclusion_v1.csv (S1), quality_tier!=mua, is_s_plus==True.  p1-aligned.
    S-  : unit_inclusion_v1.csv (S1), quality_tier!=mua, is_s_minus==True. p1-aligned.
    O+/O++ : grand_oplus_units.csv candidates, mean_correlation>=0.65 & permutation_pval<=0.05,
             deduplicated on (session_prefix,unit_row_idx). ALL areas (only O++ specifically was
             area-restricted for its own threshold-count purpose earlier; O+ itself was not).
             Omission-slot aligned (omitted_slot_onsets_s, pools RXRR/RRXR/RRRX conditions).
    O-/O-- : omission_grand_units.csv, omission_class in {O-,O--} (Q1 peak+ramp -- the only
             existing source; NOT the same causally-validated pipeline as O+/O++ above, this
             caveat carried through to the output).

OUTPUT
    outputs/classification/onset_hierarchy_all_classes_per_unit/unit_fits.csv
    outputs/classification/onset_hierarchy_all_classes_per_unit/area_summary.csv
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "context" / "figures"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import jnwb as oa  # noqa: E402
from jnwb import paths as _P  # noqa: E402
from figstyle import AREA_ORDER  # noqa: E402

import fit_class_onset_latency as _fcol  # noqa: E402 -- reused, not reimplemented
_fcol.MIN_UNITS = 1  # see module docstring: single-unit calls always have len(unit_rows)==1

S_WIN_MS, S_BASELINE_MS = _fcol.S_WIN_MS, _fcol.S_BASELINE_MS
O_WIN_MS, O_BASELINE_MS = _fcol.O_WIN_MS, _fcol.O_BASELINE_MS
MIN_R2 = _fcol.MIN_R2
MIN_VISUAL_LATENCY_MS = _fcol.MIN_VISUAL_LATENCY_MS
p1_onsets_s = _fcol.p1_onsets_s
omitted_slot_onsets_s = _fcol.omitted_slot_onsets_s
fit_one_cell = _fcol.fit_one_cell

N_BOOT = 1000
SEED = 9200
MIN_UNITS_PER_AREA_FOR_SUMMARY = 5

OUT_DIR = REPO_ROOT / "outputs" / "classification" / "onset_hierarchy_all_classes_per_unit"
UNIT_CSV = OUT_DIR / "unit_fits.csv"
SUMMARY_CSV = OUT_DIR / "area_summary.csv"


def load_populations() -> dict:
    """Returns {class_name: DataFrame[session, unit_row, area]}, four independent populations."""
    s1 = pd.read_csv(_P.outputs_dir("classification", "unit_inclusion_v1.csv"))
    nonmua = s1[s1["quality_tier"] != "mua"]
    s_plus = nonmua[nonmua["is_s_plus"] == True][["session", "unit_row", "area"]].copy()  # noqa: E712
    s_minus = nonmua[nonmua["is_s_minus"] == True][["session", "unit_row", "area"]].copy()  # noqa: E712

    cand = pd.read_csv(_P.outputs_dir("classification", "grand_oplus_units.csv"))
    mask = (cand["mean_correlation"] >= 0.65) & (cand["permutation_pval"] <= 0.05)
    o_plus = cand.loc[mask, ["session_prefix", "unit_row_idx", "area"]].drop_duplicates(
        ["session_prefix", "unit_row_idx"]
    ).rename(columns={"session_prefix": "session", "unit_row_idx": "unit_row"})

    om = pd.read_csv(_P.outputs_dir("classification", "omission_grand_units.csv"))
    o_minus = om[om["omission_class"].isin(["O-", "O--"])][["session", "unit_row", "area"]].copy()

    return {"S+": s_plus, "S-": s_minus, "O+": o_plus, "O-": o_minus}


ALIGN = {"S+": ("p1", S_WIN_MS, S_BASELINE_MS), "S-": ("p1", S_WIN_MS, S_BASELINE_MS),
         "O+": ("omit", O_WIN_MS, O_BASELINE_MS), "O-": ("omit", O_WIN_MS, O_BASELINE_MS)}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pops = load_populations()
    for name, df in pops.items():
        print(f"{name}: {len(df)} candidate units (pre-fit)")

    readiness = pd.read_csv(REPO_ROOT / "artifacts/data/session_readiness.csv")
    sessions = readiness.loc[readiness.nwb_ok, "session_prefix"].tolist()

    rows = []
    t_start = time.time()
    for k, prefix in enumerate(sessions, 1):
        try:
            sess = oa.read(str(_P.resolve_nwb_path(prefix)))
        except Exception as e:
            print(f"[{k}/{len(sessions)}] {prefix}: load failed -- {e}")
            continue
        p1_onsets = p1_onsets_s(sess)
        omit_onsets = omitted_slot_onsets_s(sess)

        for cls, df in pops.items():
            sub = df[df["session"] == prefix]
            if sub.empty:
                continue
            align_kind, win_ms, baseline_ms = ALIGN[cls]
            onsets_s = p1_onsets if align_kind == "p1" else omit_onsets
            for _, urow in sub.iterrows():
                try:
                    fit = fit_one_cell(sess, [int(urow["unit_row"])], onsets_s, win_ms, baseline_ms)
                except Exception:
                    continue
                if fit is None:
                    continue
                fit.update({"session": prefix, "area": urow["area"], "unit_row": int(urow["unit_row"]),
                            "class": cls})
                rows.append(fit)

        if k % 5 == 0 or k == len(sessions):
            print(f"[{k}/{len(sessions)}] {prefix} done, {len(rows)} fits so far, "
                  f"{time.time()-t_start:.0f}s", flush=True)
            pd.DataFrame(rows).to_csv(UNIT_CSV, index=False)

    df_unit = pd.DataFrame(rows)
    df_unit.to_csv(UNIT_CSV, index=False)
    print(f"WROTE {UNIT_CSV} ({len(df_unit)} unit x class fits)")
    if df_unit.empty:
        print("No fits -- aborting.")
        return

    rng = np.random.default_rng(SEED)
    summary_rows = []
    for cls in ALIGN:
        for area in AREA_ORDER:
            raw = df_unit[(df_unit.area == area) & (df_unit["class"] == cls)]
            if raw.empty:
                continue
            valid = raw[(raw["r2"] >= MIN_R2) & (raw["converged"].astype(bool))
                        & (raw["t0"] >= MIN_VISUAL_LATENCY_MS)]
            n_excluded_low_r2_or_unconverged = int(((raw["r2"] < MIN_R2) | (~raw["converged"].astype(bool))).sum())
            n_excluded_subfloor = int(((raw["r2"] >= MIN_R2) & (raw["converged"].astype(bool))
                                        & (raw["t0"] < MIN_VISUAL_LATENCY_MS)).sum())
            if valid.shape[0] < MIN_UNITS_PER_AREA_FOR_SUMMARY:
                summary_rows.append({
                    "class": cls, "area": area, "n_valid": int(valid.shape[0]),
                    "n_total_fit": int(raw.shape[0]),
                    "n_excluded_low_r2_or_unconverged": n_excluded_low_r2_or_unconverged,
                    "n_excluded_subfloor_t0": n_excluded_subfloor,
                    "n_sessions_contributing": int(valid["session"].nunique()),
                    "onset_ms": np.nan, "ci_lo_ms": np.nan, "ci_hi_ms": np.nan,
                    "excluded_insufficient_n": True,
                })
                continue
            t0s = valid["t0"].to_numpy()
            n = t0s.size
            boot = np.array([rng.choice(t0s, size=n, replace=True).mean() for _ in range(N_BOOT)])
            summary_rows.append({
                "class": cls, "area": area, "n_valid": int(n), "n_total_fit": int(raw.shape[0]),
                "n_excluded_low_r2_or_unconverged": n_excluded_low_r2_or_unconverged,
                "n_excluded_subfloor_t0": n_excluded_subfloor,
                "n_sessions_contributing": int(valid["session"].nunique()),
                "onset_ms": float(t0s.mean()),
                "ci_lo_ms": float(np.percentile(boot, 2.5)), "ci_hi_ms": float(np.percentile(boot, 97.5)),
                "excluded_insufficient_n": False,
            })
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(f"WROTE {SUMMARY_CSV}")
    print(summary.to_string(index=False))

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "method": "one onset fit per neuron per class (population_psth on a single-unit list); "
                  "a neuron's onset counts toward its area's average only if r2>=MIN_R2, "
                  "converged, AND t0>=MIN_VISUAL_LATENCY_MS (40ms) -- HARD gate, excluded "
                  "neurons are counted and reported, not averaged in.",
        "populations": {
            "S+": "unit_inclusion_v1.csv (S1), non-mua, is_s_plus -- p1-aligned",
            "S-": "unit_inclusion_v1.csv (S1), non-mua, is_s_minus -- p1-aligned",
            "O+": "grand_oplus_units.csv candidates, r>=0.65 & p<=0.05, deduplicated, ALL areas "
                  "-- omission-slot aligned",
            "O-": "omission_grand_units.csv, omission_class in {O-,O--} (Q1 peak+ramp, NOT the "
                  "same causally-validated pipeline as O+ above) -- omission-slot aligned",
        },
        "min_visual_latency_ms": MIN_VISUAL_LATENCY_MS, "min_r2": MIN_R2,
        "n_boot": N_BOOT, "seed": SEED,
        "n_sessions_attempted": len(sessions), "n_unit_class_fits": int(len(df_unit)),
    }
    with open(OUT_DIR / "receipt.json", "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2, default=str)
    print(f"WROTE {OUT_DIR / 'receipt.json'}")


if __name__ == "__main__":
    main()
