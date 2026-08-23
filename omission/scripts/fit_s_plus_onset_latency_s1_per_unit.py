r"""
scripts/fit_s_plus_onset_latency_s1_per_unit.py

S+ onset-latency hierarchy, single-unit-level (Hamm, 2026-08-17: "lets do it single unit per
area; all units; all V1 single units, all V2 single units, ..., all PFC single units; so each
single unit will be a single data point in the onset analysis, grouped then per area").

RELATIONSHIP TO fit_s_plus_onset_latency_s1.py (session-level, kept unmodified, Conservation)
    That script pools every S+ unit WITHIN a (session, area) cell into one population trace and
    fits ONE onset per cell, then bootstraps across SESSIONS (session = inferential unit,
    consistent with omission-statistics skill: "session is the default inferential unit for
    population claims" and CLAUDE.md tripwire #4: "channels/units within a session are not
    independent"). This script instead fits ONE onset per INDIVIDUAL UNIT (population_psth
    called with a single-unit list) and pools those across BOTH sessions and units within an
    area. Units recorded in the same session share session-level state (behavioral engagement,
    drift, shared local noise) and are NOT independent replicates the way separate sessions are
    -- this view is reported as DESCRIPTIVE/SENSITIVITY, alongside the session-level result, not
    as a replacement primary test. n_sessions_contributing is reported per area specifically so
    the pseudoreplication risk (many units, few sessions) is visible, not hidden.

    Reuses jnwb.onset_fitting (via fit_class_onset_latency.py's already-imported
    causal_exp_smooth/fit_exponential_onset) and the same S_WIN_MS/S_BASELINE_MS/
    MIN_VISUAL_LATENCY_MS/T0_PIN_THRESH_MS -- only the pooling level changes.

OUTPUT
    outputs/classification/onset_hierarchy_s1_per_unit/unit_fits.csv   -- one row per unit
    outputs/classification/onset_hierarchy_s1_per_unit/area_summary.csv
    outputs/classification/onset_hierarchy_s1_per_unit/hierarchy_test_result.json
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

import omission as oa  # noqa: E402
from jnwb import paths as _P  # noqa: E402
from figstyle import AREA_ORDER  # noqa: E402
from figstats import holm, bh  # noqa: E402

import fit_class_onset_latency as _fcol  # noqa: E402 -- reused, not reimplemented

# fit_one_cell -> population_psth internally gates on module-level MIN_UNITS (=3, tuned for the
# pooled session-level cell fit). A single-unit call always has len(unit_rows)==1 < 3, so that
# gate would silently reject every fit here. population_psth resolves MIN_UNITS from its own
# module's namespace at call time (not captured at def time), so overriding it on the imported
# module object -- rather than editing fit_class_onset_latency.py, per Conservation -- correctly
# changes what population_psth sees for calls made through this script.
_fcol.MIN_UNITS = 1

S_WIN_MS, S_BASELINE_MS = _fcol.S_WIN_MS, _fcol.S_BASELINE_MS
MIN_R2 = _fcol.MIN_R2
MIN_VISUAL_LATENCY_MS = _fcol.MIN_VISUAL_LATENCY_MS
T0_PIN_THRESH_MS = _fcol.T0_PIN_THRESH_MS
N_BOOT, N_PERM, SEED = _fcol.N_BOOT, _fcol.N_PERM, _fcol.SEED
p1_onsets_s = _fcol.p1_onsets_s
fit_one_cell = _fcol.fit_one_cell

OUT_DIR = REPO_ROOT / "outputs" / "classification" / "onset_hierarchy_s1_per_unit"
UNIT_CSV = OUT_DIR / "unit_fits.csv"
SUMMARY_CSV = OUT_DIR / "area_summary.csv"

MIN_UNITS_PER_AREA_FOR_SUMMARY = 5


def load_s1_s_plus_table() -> pd.DataFrame:
    s1 = pd.read_csv(_P.outputs_dir("classification", "unit_inclusion_v1.csv"))
    nonmua = s1[(s1["quality_tier"] != "mua") & (s1["is_s_plus"] == True)].copy()  # noqa: E712
    return nonmua[["session", "unit_row", "area"]]


def bootstrap_unit_level(t0_values: np.ndarray, rng: np.random.Generator):
    n = t0_values.size
    boot = np.array([rng.choice(t0_values, size=n, replace=True).mean() for _ in range(N_BOOT)])
    return float(t0_values.mean()), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def hierarchy_test_area_level(summary: pd.DataFrame, rng: np.random.Generator) -> dict:
    sub = summary.copy()
    sub["rank"] = sub["area"].map({a: i for i, a in enumerate(AREA_ORDER)})
    sub = sub.dropna(subset=["rank"])
    n_areas = sub.shape[0]
    if n_areas < 4:
        return {"n_areas": n_areas, "rho": np.nan, "p": np.nan, "verdict": "insufficient_areas"}
    from scipy.stats import spearmanr
    rho_obs, _ = spearmanr(sub["rank"], sub["onset_ms"])
    ranks = sub["rank"].to_numpy()
    onsets = sub["onset_ms"].to_numpy()
    null_rho = np.empty(N_PERM)
    for i in range(N_PERM):
        perm = rng.permutation(onsets)
        null_rho[i], _ = spearmanr(ranks, perm)
    p = float((np.abs(null_rho) >= abs(rho_obs)).mean())
    return {"n_areas": n_areas, "rho": float(rho_obs), "p": p,
            "areas": sub["area"].tolist(), "onsets_ms": sub["onset_ms"].tolist()}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    unit_table = load_s1_s_plus_table()

    readiness = pd.read_csv(REPO_ROOT / "artifacts/data/session_readiness.csv")
    sessions = readiness.loc[readiness.nwb_ok, "session_prefix"].tolist()

    rows = []
    t_start = time.time()
    for k, prefix in enumerate(sessions, 1):
        sub = unit_table[unit_table["session"] == prefix]
        if sub.empty:
            continue
        try:
            sess = oa.read(str(_P.resolve_nwb_path(prefix)))
        except Exception as e:
            print(f"[{k}/{len(sessions)}] {prefix}: load failed -- {e}")
            continue
        p1_onsets = p1_onsets_s(sess)

        for _, urow in sub.iterrows():
            try:
                fit = fit_one_cell(sess, [int(urow["unit_row"])], p1_onsets, S_WIN_MS, S_BASELINE_MS)
            except Exception:
                continue
            if fit is None:
                continue
            fit.update({"session": prefix, "area": urow["area"], "unit_row": int(urow["unit_row"])})
            rows.append(fit)

        if k % 5 == 0 or k == len(sessions):
            print(f"[{k}/{len(sessions)}] {prefix} done, {len(rows)} units fit so far, "
                  f"{time.time()-t_start:.0f}s", flush=True)
            pd.DataFrame(rows).to_csv(UNIT_CSV, index=False)

    df_unit = pd.DataFrame(rows)
    df_unit.to_csv(UNIT_CSV, index=False)
    print(f"WROTE {UNIT_CSV} ({len(df_unit)} units)")
    if df_unit.empty:
        print("No units fit -- aborting.")
        return

    rng = np.random.default_rng(SEED)
    summary_rows = []
    for area in AREA_ORDER:
        raw = df_unit[df_unit.area == area]
        gated = raw[(raw["r2"] >= MIN_R2) & (raw["converged"].astype(bool))]
        if gated.shape[0] < MIN_UNITS_PER_AREA_FOR_SUMMARY:
            continue
        t0s = gated["t0"].to_numpy()
        point, lo, hi = bootstrap_unit_level(t0s, rng)
        n_sessions_contributing = gated["session"].nunique()
        summary_rows.append({
            "area": area, "n_units": int(gated.shape[0]), "n_units_total_fit": int(raw.shape[0]),
            "n_units_excluded_low_r2": int(raw.shape[0] - gated.shape[0]),
            "n_sessions_contributing": int(n_sessions_contributing),
            "onset_ms": point, "ci_lo_ms": lo, "ci_hi_ms": hi,
        })
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(f"WROTE {SUMMARY_CSV} ({len(summary)} areas)")
    print(summary.to_string(index=False))

    test_result = hierarchy_test_area_level(summary, rng)
    if np.isfinite(test_result.get("p", np.nan)):
        test_result["p_holm"] = float(holm(np.array([test_result["p"]]))[0])
        test_result["q_bh"] = float(bh(np.array([test_result["p"]]))[0])
    print("\nHierarchy test (S1-sourced S+, UNIT-level pooling):", test_result)

    flags = []
    for _, r in summary.iterrows():
        if r["onset_ms"] < MIN_VISUAL_LATENCY_MS:
            flags.append(f"S+ {r['area']}: onset {r['onset_ms']:.1f}ms < "
                         f"{MIN_VISUAL_LATENCY_MS}ms minimum visual latency")
        if r["n_sessions_contributing"] < 3:
            flags.append(f"S+ {r['area']}: only {r['n_sessions_contributing']} session(s) "
                         f"contribute {r['n_units']} units -- pseudoreplication risk, this "
                         f"area's narrow CI mostly reflects within-session unit count, not "
                         f"independent replicates")
    gated_all = df_unit[(df_unit["r2"] >= MIN_R2) & (df_unit["converged"].astype(bool))]
    for area, g in gated_all.groupby("area"):
        n_pinned = int((g["t0"] < T0_PIN_THRESH_MS).sum())
        if n_pinned > 0:
            flags.append(f"S+ {area}: {n_pinned}/{len(g)} gate-passing units boundary-pinned "
                         f"(t0<{T0_PIN_THRESH_MS}ms)")
    if flags:
        print("\nFLAGGED:")
        for f in flags:
            print(" -", f)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "pooling_level": "SINGLE UNIT -- one onset fit per unit, no within-session pooling. "
                         "Descriptive/sensitivity view; session remains the primary inferential "
                         "unit per omission-statistics skill and CLAUDE.md tripwire #4 -- see "
                         "fit_s_plus_onset_latency_s1.py for the session-level primary result.",
        "population_source": str(_P.outputs_dir("classification", "unit_inclusion_v1.csv")),
        "population_filter": "quality_tier != 'mua', is_s_plus == True",
        "n_sessions_attempted": len(sessions), "n_units_fit": int(len(df_unit)),
        "s_win_ms": list(S_WIN_MS), "s_baseline_ms": list(S_BASELINE_MS),
        "min_visual_latency_ms": MIN_VISUAL_LATENCY_MS,
        "n_boot": N_BOOT, "n_perm": N_PERM, "seed": SEED,
        "flags": flags, "hierarchy_test": test_result,
        "area_summary": summary.to_dict(orient="records"),
    }
    with open(OUT_DIR / "hierarchy_test_result.json", "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2, default=str)
    print(f"WROTE {OUT_DIR / 'hierarchy_test_result.json'}")


if __name__ == "__main__":
    main()
