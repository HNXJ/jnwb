r"""
Onset-latency propagation-hierarchy test (H1 low->high / H2 high->low / H3 superposition),
spiking, per response class.

WHY / WHAT
    Hamm's request 2026-08-15: test whether visual response onset across the 10-area hierarchy
    (figstyle.AREA_ORDER, already stored bottom-up: V1,V2,V3a/d,V4,MT,MST,TEO,FST,FEF,PFC) is
    organized bottom-up (H1), top-down (H2), or near-simultaneous (H3, "superposition" -- e.g.
    volume conduction). Run once pooling all stable units per area ("omnibus"), and once each
    for S+/S++ (stimulus-excited, MUST show H1 as both a scientific claim and the validity check
    for this whole method -- if it doesn't, the method itself is suspect, per the user's own
    framing), S-/S-- (stimulus-suppressed, no prior), and O+/O++ and O-/O-- (omission-responsive,
    constrained: onset >=40ms and not earlier than the matched-area S+/S++ onset).

    No existing code in this repo computes a stimulus-aligned, per-response-class onset latency
    (the only prior onset-latency work, scripts/aggregate_omission_onset_clusters.py, answers a
    population-DECODER onset question, not a per-class firing-rate-rise question) and no
    exponential-onset-fitting method existed before jnwb/onset_fitting.py (built alongside this
    script, self-tested on synthetic data first).

UNIT-CLASS TABLE, JOINED EXACTLY AS fig03_unit_census.py DOES
    omission_grand_units.csv (session, unit_row, area10, omission_class in {O++,O+,ns,O-,O--})
    left-joined with grand_s_and_o_units.csv (session_prefix, unit_row_idx, is_Splus,
    is_Splus_double, is_Sminus, is_Sminus_double) on (session,unit_row)<->(session_prefix,
    unit_row_idx) -- same key-name mismatch fig03_unit_census.py::attach_legacy already
    resolves; reused here rather than re-derived. is_Splus_double (S++) is a STRICT SUBSET of
    is_Splus (S+) by construction (stricter p<0.01 vs p<0.05, same r>0.3), so "S+/S++" pools as
    plain is_Splus; likewise "S-/S--" pools as is_Sminus. omission_class's O+ already excludes
    O++ (mutually exclusive tiers), so "O+/O++" pools as omission_class in {"O+","O++"}, and
    "O-/O--" as {"O-","O--"}. Stability gate reused from fig03_unit_census.py::attach_stability
    (quality==1 SUA with trial_presence_fraction > 0.98 against unit_trial_presence.csv).

ALIGNMENT
    S classes and omnibus: p1 onset (t=0ms, jnwb.sequence_layout.EPOCH_ONSETS_MS["p1"]), i.e.
    sess.get_epochs(phase=2, correct_only=True)["start_time"] pooled across ALL 12 conditions
    (p1 is never omitted in this task, so condition doesn't matter for this alignment).
    O classes: the OMITTED SLOT's own onset, reusing decode_omission_onset_sliding_window.py's
    SLOT_TO_CONDITIONS table and slot-onset construction (trial start_time + EPOCH_ONSETS_MS
    offset for the omitted slot).

CAUSALITY
    fit_exponential_onset's t0 is bounded to [0, window_end] BY CONSTRUCTION (see
    jnwb/onset_fitting.py) -- mirrors the ctr>=0 restriction already applied to the
    cluster-permutation onset search. Any fitted onset <40ms (visual-system minimum latency,
    user-specified) is flagged, not silently accepted.

OUTPUT
    outputs/classification/onset_hierarchy/cell_fits.csv       -- one row per session x area10 x class
    outputs/classification/onset_hierarchy/area_class_summary.csv -- per area x class: n_sessions,
                                                                      onset_ms mean/CI
    outputs/classification/onset_hierarchy/hierarchy_test_results.csv -- per class: H1/H2/H3 verdict
    artifacts/.lab/onset-hierarchy-h1h2h3-<date>.json -- evidence record
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "context" / "figures"))

import jnwb as oa  # noqa: E402
from jnwb import paths as _P  # noqa: E402
from jnwb.sequence_layout import EPOCH_ONSETS_MS  # noqa: E402
from jnwb.onset_fitting import causal_exp_smooth, fit_exponential_onset  # noqa: E402
from figstyle import AREA_ORDER  # noqa: E402
from figstats import holm, bh  # noqa: E402

MIN_UNITS = 3
MIN_SESSIONS_PER_CELL = 3
MIN_R2 = 0.3
BIN_MS = 5.0
TAU_SMOOTH_MS = 30.0
MIN_VISUAL_LATENCY_MS = 40.0
T0_PIN_THRESH_MS = 1.0
N_BOOT = 1000
N_PERM = 5000
SEED = 9100

# 2026-08-15 revision (root-cause fix for the boundary-pinning artifact documented in
# artifacts/.lab/onset-hierarchy-h1h2h3-clean-only-20260815.json): two separate problems were
# conflated in the original (-100, +window_end) windows.
#
# (1) causal_exp_smooth needs 5*TAU_SMOOTH_MS=150ms of REAL preceding history to fully warm up
#     its kernel; it zero-pads whatever it doesn't have (jnwb/onset_fitting.py:
#     `padded = np.concatenate([np.zeros(len(h)-1), rate])`). With only 100ms of pre-window
#     lookback, EVERY bin in the old window was smoothed against a partially fabricated
#     zero-history, artificially suppressing early rate estimates relative to what real
#     preceding activity would have produced. EXTRACTION_MARGIN_MS below fixes this
#     unconditionally (extract further back than the window used for fitting/interpretation,
#     trim the margin off before the fit ever sees it) -- this part is a pure bug fix, not a
#     scientific judgment call.
# (2) Separately, S+/S-/omnibus (all p1-aligned -- see class_mask/run_extraction: "omnibus" is
#     NOT in the O-tuple, so it uses p1_onsets/S_WIN_MS same as S+/S- despite pooling all stable
#     units) had their baseline window (old: -100 to 0ms) sitting inside the very region a
#     pre-stimulus ramp (if present) would already have started elevating -- biasing the fitted
#     "baseline" upward and pushing the apparent onset toward t0=0 by construction, independent
#     of the smoothing bug. jnwb.sequence_layout.EPOCH_ONSETS_MS puts fixation acquisition
#     ("fx") at -500ms relative to p1 -- a full 500ms of genuine pre-trial period is available,
#     so S_BASELINE_MS is moved back into it, safely clear of any pre-onset ramp that starts
#     anywhere in [-150, 0]ms (an assumption, not a certainty -- if a ramp starts earlier than
#     -150ms this window can still be contaminated; not observed in this corpus's fits so far).
#
#     O+/O- (omission-slot-aligned) are NOT given the same baseline-window treatment: the period
#     immediately before an omitted slot is the preceding delay (d_{slot-1}, always exactly
#     500ms long per EPOCH_ONSETS_MS), and any anticipatory/omission-expectation ramp toward the
#     omitted slot is itself the phenomenon O+/O- exist to measure -- moving the O baseline
#     window back risks quietly assuming away the exact effect being tested, which is a
#     different and unresolved judgment call, not a bug. O_WIN_MS is widened ONLY enough to fix
#     the smoothing-warmup bug (1), staying safely inside the preceding delay period for all
#     three omitted slots (checked against EPOCH_ONSETS_MS: -250ms relative to any omitted slot
#     never crosses into the prior real-stimulus flash for slots 2, 3, or 4).
EXTRACTION_MARGIN_MS = 5.0 * TAU_SMOOTH_MS

S_WIN_MS = (-500.0, 400.0)
S_BASELINE_MS = (-400.0, -150.0)
O_WIN_MS = (-250.0, 600.0)
O_BASELINE_MS = (-250.0, -150.0)

ALL_SLOTS = (2, 3, 4)
SLOT_TO_CONDITIONS = {
    2: ["RXRR", "AXAB", "BXBA"],
    3: ["RRXR", "AAXB", "BBXA"],
    4: ["RRRX", "AAAX", "BBBX"],
}

OUT_DIR = REPO_ROOT / "outputs" / "classification" / "onset_hierarchy"
CELL_CSV = OUT_DIR / "cell_fits.csv"
SUMMARY_CSV = OUT_DIR / "area_class_summary.csv"
TEST_CSV = OUT_DIR / "hierarchy_test_results.csv"

CLASSES = ["omnibus", "S+", "S-", "O+", "O-"]


def load_unit_class_table() -> pd.DataFrame:
    grand = pd.read_csv(_P.outputs_dir("classification", "omission_grand_units.csv"))
    grand["area10"] = grand["area10"].fillna(grand["area"])

    legacy = pd.read_csv(_P.outputs_dir("classification", "grand_s_and_o_units.csv"))
    m = grand.merge(
        legacy[["session_prefix", "unit_row_idx", "is_Splus", "is_Splus_double",
                "is_Sminus", "is_Sminus_double"]],
        left_on=["session", "unit_row"], right_on=["session_prefix", "unit_row_idx"], how="left",
    )

    stab = pd.read_csv(_P.outputs_dir("classification", "unit_trial_presence.csv"))
    m = m.merge(stab[["session", "unit_row", "trial_presence_fraction"]],
                on=["session", "unit_row"], how="left")
    STABLE_KEEP_THRESHOLD = 0.98
    m["is_stable"] = (m.quality == 1) & (m.trial_presence_fraction > STABLE_KEEP_THRESHOLD)

    m["is_Splus"] = m["is_Splus"].fillna(False).astype(bool)
    m["is_Sminus"] = m["is_Sminus"].fillna(False).astype(bool)
    m["is_Oplus"] = m["omission_class"].isin(["O+", "O++"])
    m["is_Ominus"] = m["omission_class"].isin(["O-", "O--"])
    return m


def class_mask(df: pd.DataFrame, cls: str) -> pd.Series:
    if cls == "omnibus":
        return df["is_stable"]
    if cls == "S+":
        return df["is_stable"] & df["is_Splus"]
    if cls == "S-":
        return df["is_stable"] & df["is_Sminus"]
    if cls == "O+":
        return df["is_stable"] & df["is_Oplus"]
    if cls == "O-":
        return df["is_stable"] & df["is_Ominus"]
    raise ValueError(cls)


def load_session(prefix: str):
    return oa.read(str(_P.resolve_nwb_path(prefix)))


def p1_onsets_s(sess) -> np.ndarray:
    epochs = sess.get_epochs(phase=2, correct_only=True)
    if epochs is None or len(epochs) == 0:
        return np.array([])
    return np.asarray(epochs["start_time"].values, dtype=float)


def omitted_slot_onsets_s(sess) -> np.ndarray:
    onsets = []
    for omit_slot, conds in SLOT_TO_CONDITIONS.items():
        offset_s = EPOCH_ONSETS_MS[f"p{omit_slot}"] / 1000.0
        for cond in conds:
            epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
            if epochs is None or len(epochs) == 0:
                continue
            starts = np.asarray(epochs["start_time"].values, dtype=float)
            onsets.append(starts + offset_s)
    if not onsets:
        return np.array([])
    return np.concatenate(onsets)


def population_psth(sess, unit_rows: list, onsets_s: np.ndarray, win_ms: tuple, bin_ms: float):
    if len(unit_rows) < MIN_UNITS or len(onsets_s) == 0:
        return None, None, 0
    edges_ms = np.arange(win_ms[0], win_ms[1] + bin_ms, bin_ms)
    ctr_ms = (edges_ms[:-1] + edges_ms[1:]) / 2.0
    edges_s = edges_ms / 1000.0
    n_bins = len(ctr_ms)
    counts_total = np.zeros(n_bins, dtype=np.float64)
    n_unit_trial = 0
    for row in unit_rows:
        spikes = sess.get_spike_times(row)
        if spikes is None or len(spikes) == 0:
            continue
        spikes = np.sort(np.asarray(spikes, dtype=float))
        for onset in onsets_s:
            c, _ = np.histogram(
                spikes[(spikes >= onset + edges_s[0]) & (spikes < onset + edges_s[-1])] - onset,
                bins=edges_s,
            )
            counts_total += c
            n_unit_trial += 1
    if n_unit_trial == 0:
        return None, None, 0
    rate = counts_total / (n_unit_trial * (bin_ms / 1000.0))
    return ctr_ms, rate, n_unit_trial


def fit_one_cell(sess, unit_rows: list, onsets_s: np.ndarray, win_ms: tuple,
                  baseline_ms: tuple) -> dict | None:
    """Extract with an extra EXTRACTION_MARGIN_MS of real pre-window history so causal_exp_smooth
    is never zero-padded over the region actually used for baseline/onset fitting, then trim the
    margin off before fitting (see the 2026-08-15 module-level comment above win_ms's definition).
    """
    extract_win = (win_ms[0] - EXTRACTION_MARGIN_MS, win_ms[1])
    ctr_ms, rate, n_unit_trial = population_psth(sess, unit_rows, onsets_s, extract_win, BIN_MS)
    if ctr_ms is None:
        return None
    smoothed = causal_exp_smooth(rate, BIN_MS, tau_ms=TAU_SMOOTH_MS)
    keep = ctr_ms >= win_ms[0]
    ctr_fit, smoothed_fit = ctr_ms[keep], smoothed[keep]
    fit = fit_exponential_onset(
        ctr_fit, smoothed_fit, t0_bounds=(0.0, win_ms[1]), baseline_window=baseline_ms,
    )
    fit["n_units"] = len(unit_rows)
    fit["n_trials"] = len(onsets_s)
    fit["n_unit_trial"] = n_unit_trial
    return fit


def run_extraction(sessions: list[str], out_dir: Path = OUT_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    unit_table = load_unit_class_table()

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
            print(f"[{k}/{len(sessions)}] {prefix}: no rows in unit class table, skipping")
            continue

        p1_onsets = p1_onsets_s(sess)
        omit_onsets = omitted_slot_onsets_s(sess)

        for area in AREA_ORDER:
            area_sub = sub[sub["area10"] == area]
            if area_sub.empty:
                continue
            for cls in CLASSES:
                mask = class_mask(area_sub, cls)
                unit_rows = area_sub.loc[mask, "unit_row"].tolist()
                if len(unit_rows) < MIN_UNITS:
                    continue
                is_o = cls in ("O+", "O-")
                onsets_s = omit_onsets if is_o else p1_onsets
                win_ms = O_WIN_MS if is_o else S_WIN_MS
                baseline_ms = O_BASELINE_MS if is_o else S_BASELINE_MS
                try:
                    fit = fit_one_cell(sess, unit_rows, onsets_s, win_ms, baseline_ms)
                except Exception as e:
                    print(f"  {prefix} {area} {cls}: fit failed -- {e}")
                    traceback.print_exc()
                    continue
                if fit is None:
                    continue
                fit.update({"session": prefix, "area": area, "class": cls})
                rows.append(fit)

        if k % 5 == 0 or k == len(sessions):
            print(f"[{k}/{len(sessions)}] {prefix} done, {len(rows)} cells so far, "
                  f"{time.time()-t_start:.0f}s", flush=True)
            pd.DataFrame(rows).to_csv(CELL_CSV, index=False)

    df = pd.DataFrame(rows)
    df.to_csv(CELL_CSV, index=False)
    print(f"WROTE {CELL_CSV} ({len(df)} cells)")
    return df


def bootstrap_area_class(df_cell: pd.DataFrame, area: str, cls: str, rng: np.random.Generator):
    """Session-level bootstrap CI for an area x class onset estimate.

    A degenerate fit (amplitude ~0, i.e. the class showed no detectable rise in that
    session x area) leaves t0 numerically unidentified -- the optimizer parks it near a bound
    with an essentially flat residual, NOT a genuine "onset at t=0" finding. Gate on
    (r2 >= MIN_R2 AND converged) before a session's fit is allowed into the onset estimate;
    sessions failing this gate are excluded from the mean/CI, not silently averaged in as if
    they were real onsets (found during the 2-session smoke test: several S-/omnibus cells had
    r2 < 1e-3 with t0 pinned at 0, which would otherwise have corrupted the hierarchy test).
    """
    raw = df_cell[(df_cell.area == area) & (df_cell["class"] == cls)]
    sub = raw[(raw["r2"] >= MIN_R2) & (raw["converged"])]
    if sub.shape[0] < MIN_SESSIONS_PER_CELL:
        return None
    onsets = sub["t0"].to_numpy()
    n = onsets.size
    boot = np.array([rng.choice(onsets, size=n, replace=True).mean() for _ in range(N_BOOT)])
    return {
        "area": area, "class": cls, "n_sessions": int(n), "n_sessions_total": int(raw.shape[0]),
        "n_sessions_excluded_low_r2": int(raw.shape[0] - n),
        "onset_ms": float(onsets.mean()),
        "ci_lo_ms": float(np.percentile(boot, 2.5)), "ci_hi_ms": float(np.percentile(boot, 97.5)),
    }


def hierarchy_test(summary: pd.DataFrame, cls: str, rng: np.random.Generator) -> dict:
    """Spearman correlation of area-mean onset vs AREA_ORDER rank, permutation p-value.

    Permutation reshuffles the (small, n_areas-sized) pairing between area rank and area onset
    mean -- an exact permutation test on the areas themselves, distinct from and complementary to
    the session-level bootstrap CI already computed per area (that CI answers "how uncertain is
    THIS area's onset estimate"; this test answers "is there a monotonic relationship with
    hierarchy rank across areas").
    """
    sub = summary[summary["class"] == cls].copy()
    sub["rank"] = sub["area"].map({a: i for i, a in enumerate(AREA_ORDER)})
    sub = sub.dropna(subset=["rank"])
    n_areas = sub.shape[0]
    if n_areas < 4:
        return {"class": cls, "n_areas": n_areas, "rho": np.nan, "p": np.nan, "verdict": "insufficient_areas"}

    from scipy.stats import spearmanr
    rho_obs, _ = spearmanr(sub["rank"], sub["onset_ms"])

    ranks = sub["rank"].to_numpy()
    onsets = sub["onset_ms"].to_numpy()
    null_rho = np.empty(N_PERM)
    for i in range(N_PERM):
        perm = rng.permutation(onsets)
        null_rho[i], _ = spearmanr(ranks, perm)
    p = float((np.abs(null_rho) >= abs(rho_obs)).mean())

    return {
        "class": cls, "n_areas": n_areas, "rho": float(rho_obs), "p": p,
        "areas": sub["area"].tolist(), "onsets_ms": sub["onset_ms"].tolist(),
    }


def run_hierarchy_tests(df_cell: pd.DataFrame, out_dir: Path = OUT_DIR):
    rng = np.random.default_rng(SEED)
    summary_rows = []
    for area in AREA_ORDER:
        for cls in CLASSES:
            r = bootstrap_area_class(df_cell, area, cls, rng)
            if r is not None:
                summary_rows.append(r)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(f"WROTE {SUMMARY_CSV} ({len(summary)} area x class cells)")
    if summary.empty:
        print("No area x class cell reached MIN_SESSIONS_PER_CELL -- skipping hierarchy test "
              "(this is expected on a small --limit-sessions smoke test).")
        empty_test = pd.DataFrame(columns=["class", "n_areas", "rho", "p", "p_holm", "q_bh", "verdict"])
        empty_test.to_csv(TEST_CSV, index=False)
        return summary, empty_test, []

    test_rows = [hierarchy_test(summary, cls, rng) for cls in CLASSES]
    test_df = pd.DataFrame(test_rows)
    valid = test_df["p"].notna()
    test_df.loc[valid, "p_holm"] = holm(test_df.loc[valid, "p"].to_numpy())
    test_df.loc[valid, "q_bh"] = bh(test_df.loc[valid, "p"].to_numpy())

    def verdict(row):
        if not np.isfinite(row.get("p_holm", np.nan)):
            return "insufficient_data"
        if row["p_holm"] < 0.05:
            return "H1_low_then_high" if row["rho"] > 0 else "H2_high_then_low"
        return "H3_superposition_candidate"
    test_df["verdict"] = test_df.apply(verdict, axis=1)
    test_df.to_csv(TEST_CSV, index=False)
    print(f"WROTE {TEST_CSV}")
    print(test_df[["class", "n_areas", "rho", "p", "p_holm", "q_bh", "verdict"]].to_string())

    # Physical-plausibility / causality gate checks -- surfaced, not silently accepted.
    flags = []
    for _, r in summary.iterrows():
        if r["onset_ms"] < MIN_VISUAL_LATENCY_MS:
            flags.append(f"{r['class']} {r['area']}: onset {r['onset_ms']:.1f}ms < "
                         f"{MIN_VISUAL_LATENCY_MS}ms minimum visual latency")

    # Boundary-pinning flag (folded in from scripts/diagnose_onset_hierarchy_boundary_pinning.py,
    # 2026-08-15 -- see artifacts/.lab/onset-hierarchy-h1h2h3-clean-only-20260815.json). A
    # gate-passing cell (r2>=MIN_R2, converged) with t0<T0_PIN_THRESH_MS is not evidence of a
    # genuine sub-millisecond onset -- it is the causality bound (t0>=0) forcing a rise that was
    # already underway before the window opens to collapse onto the earliest legal point. Report
    # per area x class even after the EXTRACTION_MARGIN_MS / baseline-window fix above, since that
    # fix addresses the smoothing-warmup bug and (for S/omnibus) baseline contamination, not every
    # possible cause of a pre-existing ramp.
    gated = df_cell[(df_cell["r2"] >= MIN_R2) & (df_cell["converged"].astype(bool))]
    for (area, cls), g in gated.groupby(["area", "class"]):
        n_pinned = int((g["t0"] < T0_PIN_THRESH_MS).sum())
        if n_pinned > 0:
            flags.append(f"{cls} {area}: {n_pinned}/{len(g)} gate-passing sessions boundary-"
                         f"pinned (t0<{T0_PIN_THRESH_MS}ms) -- area-level onset_ms may be biased "
                         f"toward 0")

    s_plus = summary[summary["class"] == "S+"].set_index("area")["onset_ms"]
    for cls in ("O+", "O-"):
        o_sub = summary[summary["class"] == cls]
        for _, r in o_sub.iterrows():
            if r["area"] in s_plus.index and r["onset_ms"] < s_plus[r["area"]]:
                flags.append(f"{cls} {r['area']}: onset {r['onset_ms']:.1f}ms earlier than "
                             f"matched S+ onset {s_plus[r['area']]:.1f}ms")
    if flags:
        print("\nFLAGGED (physically implausible or causality-violating, NOT auto-excluded):")
        for f in flags:
            print(f"  - {f}")
    else:
        print("\nNo physical-plausibility flags.")

    return summary, test_df, flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-sessions", type=int, default=None)
    ap.add_argument("--skip-extraction", action="store_true")
    args = ap.parse_args()

    readiness = pd.read_csv(REPO_ROOT / "artifacts/data/session_readiness.csv")
    # session_prefix (not stem) matches omission_grand_units.csv's own "session" field and is
    # what jnwb.paths.resolve_nwb_path expects (see that function's docstring).
    sessions = readiness.loc[readiness.nwb_ok, "session_prefix"].tolist()
    if args.limit_sessions:
        sessions = sessions[: args.limit_sessions]

    if args.skip_extraction and CELL_CSV.exists():
        df_cell = pd.read_csv(CELL_CSV)
    else:
        df_cell = run_extraction(sessions)

    if df_cell.empty:
        print("No cells fit -- aborting before hierarchy test.")
        return

    summary, test_df, flags = run_hierarchy_tests(df_cell)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "n_sessions_attempted": len(sessions),
        "n_cells_fit": int(len(df_cell)),
        "min_units": MIN_UNITS, "min_sessions_per_cell": MIN_SESSIONS_PER_CELL,
        "s_win_ms": list(S_WIN_MS), "o_win_ms": list(O_WIN_MS),
        "s_baseline_ms": list(S_BASELINE_MS), "o_baseline_ms": list(O_BASELINE_MS),
        "extraction_margin_ms": EXTRACTION_MARGIN_MS, "bin_ms": BIN_MS,
        "tau_smooth_ms": TAU_SMOOTH_MS, "min_visual_latency_ms": MIN_VISUAL_LATENCY_MS,
        "t0_pin_thresh_ms": T0_PIN_THRESH_MS,
        "n_boot": N_BOOT, "n_perm": N_PERM, "seed": SEED,
        "flags": flags,
        "test_results": test_df.to_dict(orient="records"),
    }
    with open(OUT_DIR / "receipt.json", "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2, default=str)
    print(f"WROTE {OUT_DIR / 'receipt.json'}")


if __name__ == "__main__":
    main()
