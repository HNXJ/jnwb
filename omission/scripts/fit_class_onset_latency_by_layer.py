r"""
Layer-stratified extension of scripts/fit_class_onset_latency.py (Andre's ask, relayed via
Hamm 2026-08-15: "How about also looking into the layer where these cells are located").

WHY A SEPARATE FILE, NOT A FLAG ON THE ORIGINAL
    Reuses fit_class_onset_latency.py's functions directly (load_unit_class_table, class_mask,
    fit_one_cell, bootstrap_area_class, hierarchy_test, S/O windows and baselines -- all
    unmodified, imported not reimplemented) and only adds the extra layer dimension: joining
    outputs/layers/unit_layers.csv (session_prefix, unit_id, unit_layer in {sup, mid, deep, na})
    onto the unit-class table on (session, unit_id), and looping area x layer x class instead of
    area x class. A separate output tree (outputs/classification/onset_hierarchy_by_layer/) keeps
    this from overwriting the original run.

COVERAGE CAVEAT -- READ BEFORE INTERPRETING ANY OUTPUT HERE
    Per PROJECT_STATE.md section 5 and export_putative_layers.py's own docstring: layer coverage
    is ~31% of units (measured here: 2853/9056 = 31.5%) and is NOT balanced across animal or area
    (Kruskal-Wallis H=12.80, P=0.0017 on channel-level coverage). Splitting the already-thin
    per-area unit counts (fit_class_onset_latency.py's own area x class cells were frequently
    underpowered even unstratified -- see artifacts/.lab/onset-hierarchy-h1h2h3-fixed-20260815.json)
    three ways by layer is expected to leave most area x layer x class cells below MIN_UNITS/
    MIN_SESSIONS_PER_CELL. A cell reporting insufficient_data here is the correct, honest answer
    given current corpus size -- not a bug to work around.

OUTPUT
    outputs/classification/onset_hierarchy_by_layer/cell_fits_by_layer.csv
    outputs/classification/onset_hierarchy_by_layer/area_layer_class_summary.csv
    outputs/classification/onset_hierarchy_by_layer/coverage_report.csv -- how many area x class
        cells survive at each layer vs the unstratified (layer="all") baseline, so the power loss
        from stratifying is explicit rather than buried in a long insufficient_data list.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from fit_class_onset_latency import (  # noqa: E402
    AREA_ORDER, CLASSES, MIN_SESSIONS_PER_CELL, MIN_UNITS, N_BOOT, N_PERM, SEED,
    O_BASELINE_MS, O_WIN_MS, S_BASELINE_MS, S_WIN_MS,
    bootstrap_area_class, class_mask, fit_one_cell, hierarchy_test,
    load_session, load_unit_class_table, omitted_slot_onsets_s, p1_onsets_s,
)
from figstats import holm, bh  # noqa: E402

LAYERS = ["sup", "mid", "deep"]
OUT_DIR = REPO_ROOT / ".." / "outputs" / "classification" / "onset_hierarchy_by_layer"
CELL_CSV = OUT_DIR / "cell_fits_by_layer.csv"
SUMMARY_CSV = OUT_DIR / "area_layer_class_summary.csv"
COVERAGE_CSV = OUT_DIR / "coverage_report.csv"


def load_unit_class_table_with_layer() -> pd.DataFrame:
    m = load_unit_class_table()
    layers = pd.read_csv(REPO_ROOT / ".." / "outputs" / "layers" / "unit_layers.csv")
    m = m.merge(
        layers[["session_prefix", "unit_id", "unit_layer"]],
        left_on=["session", "unit_id"], right_on=["session_prefix", "unit_id"], how="left",
    )
    n_labelled = m["unit_layer"].isin(LAYERS).sum()
    print(f"Layer join: {n_labelled}/{len(m)} units ({100*n_labelled/len(m):.1f}%) carry a "
          f"real layer label (sup/mid/deep); the rest are 'na' or unmatched.")
    return m


def run_extraction(sessions: list[str]) -> pd.DataFrame:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    unit_table = load_unit_class_table_with_layer()

    rows = []
    t_start = time.time()
    for k, prefix in enumerate(sessions, 1):
        try:
            sess = load_session(prefix)
        except Exception as e:
            print(f"[{k}/{len(sessions)}] {prefix}: load failed -- {e}")
            continue
        sub = unit_table[unit_table["session"] == prefix]
        if sub.empty:
            continue

        p1_onsets = p1_onsets_s(sess)
        omit_onsets = omitted_slot_onsets_s(sess)

        for area in AREA_ORDER:
            area_sub = sub[sub["area10"] == area]
            if area_sub.empty:
                continue
            for layer in LAYERS:
                layer_sub = area_sub[area_sub["unit_layer"] == layer]
                if layer_sub.empty:
                    continue
                for cls in CLASSES:
                    mask = class_mask(layer_sub, cls)
                    unit_rows = layer_sub.loc[mask, "unit_row"].tolist()
                    if len(unit_rows) < MIN_UNITS:
                        continue
                    is_o = cls in ("O+", "O-")
                    onsets_s = omit_onsets if is_o else p1_onsets
                    win_ms = O_WIN_MS if is_o else S_WIN_MS
                    baseline_ms = O_BASELINE_MS if is_o else S_BASELINE_MS
                    try:
                        fit = fit_one_cell(sess, unit_rows, onsets_s, win_ms, baseline_ms)
                    except Exception as e:
                        print(f"  {prefix} {area} {layer} {cls}: fit failed -- {e}")
                        continue
                    if fit is None:
                        continue
                    fit.update({"session": prefix, "area": area, "layer": layer, "class": cls})
                    rows.append(fit)

        if k % 5 == 0 or k == len(sessions):
            print(f"[{k}/{len(sessions)}] {prefix} done, {len(rows)} cells so far, "
                  f"{time.time()-t_start:.0f}s", flush=True)
            pd.DataFrame(rows).to_csv(CELL_CSV, index=False)

    df = pd.DataFrame(rows)
    df.to_csv(CELL_CSV, index=False)
    print(f"WROTE {CELL_CSV} ({len(df)} cells)")
    return df


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-sessions", type=int, default=None)
    ap.add_argument("--skip-extraction", action="store_true")
    args = ap.parse_args()

    readiness = pd.read_csv(REPO_ROOT / ".." / "artifacts/data/session_readiness.csv")
    sessions = readiness.loc[readiness.nwb_ok, "session_prefix"].tolist()
    if args.limit_sessions:
        sessions = sessions[: args.limit_sessions]

    if args.skip_extraction and CELL_CSV.exists():
        df_cell = pd.read_csv(CELL_CSV)
    else:
        df_cell = run_extraction(sessions)

    if df_cell.empty:
        print("No cells fit at all -- aborting.")
        return

    rng = np.random.default_rng(SEED)
    summary_rows = []
    for area in AREA_ORDER:
        for layer in LAYERS:
            for cls in CLASSES:
                sub = df_cell[(df_cell.area == area) & (df_cell.layer == layer)]
                r = bootstrap_area_class(sub, area, cls, rng)
                if r is not None:
                    r["layer"] = layer
                    summary_rows.append(r)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(f"WROTE {SUMMARY_CSV} ({len(summary)} area x layer x class cells reach "
          f"MIN_SESSIONS_PER_CELL={MIN_SESSIONS_PER_CELL})")
    if not summary.empty:
        print(summary.to_string(index=False))

    # Coverage report: how much does stratifying by layer cost, relative to the unstratified
    # (all-layer) run -- explicit rather than a silent wall of insufficient_data.
    unstrat_path = REPO_ROOT / ".." / "outputs" / "classification" / "onset_hierarchy" / "area_class_summary.csv"
    n_unstrat_cells = 0
    if unstrat_path.exists():
        n_unstrat_cells = len(pd.read_csv(unstrat_path))
    cov = pd.DataFrame([{
        "n_area_class_cells_unstratified": n_unstrat_cells,
        "n_area_layer_class_cells_with_data": len(summary),
        "n_units_total": int(len(load_unit_class_table_with_layer())),
        "layer_coverage_note": "layer label present for ~31% of units, not balanced across "
                               "animal/area (PROJECT_STATE.md section 5) -- most area x layer x "
                               "class cells are expected to fall below MIN_SESSIONS_PER_CELL for "
                               "this reason, not a fitting error",
    }])
    cov.to_csv(COVERAGE_CSV, index=False)
    print(f"WROTE {COVERAGE_CSV}")
    print(cov.to_string(index=False))


if __name__ == "__main__":
    main()
