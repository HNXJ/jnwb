#!/usr/bin/env python3
"""F06 matched SPK-LFP substrate v1.

Builds ONE deterministic, session-resolved matched table for the F06 (SPK-LFP dissociation)
manuscript figure, per the 2026-08-24 Stage-A/B authorization. This is new analysis work: LFP
is recomputed at session resolution directly from raw NWB LFP via the *already-validated* L2
per-session extractor (``_l_lfp_common.batched_spectrogram`` + ``L2_band_power_traces.
session_band_traces``) -- reused, not reimplemented, per L0's canonical pooling method and
L2's log-last-order discipline. SPK effects are read from the existing, receipt-backed
``unit_inclusion_v1.csv`` (2026-08-17), aggregated to session x area (never per-unit rows, to
avoid pseudoreplicating units against one shared LFP value).

Matching audit finding this script exists to resolve: the previously-saved L2_stats.json only
retains POOLED group-level traces, not per-session values, so no LFP number could be joined to
a specific (session, area) SPK row without recomputing session-level LFP directly -- done here.

Two contrasts, matched to SPK's own already-computed comparisons:
  OB (omission vs local pre-omission baseline) -- SPK: `om_vs_base_effect_hz` (baseline
      [omit_onset-250, omit_onset-50] ms). LFP: harmonized to the same local-baseline geometry
      by differencing two already-log'd points on the SAME fixation-baselined dB(t) trace
      (mathematically exact: db(t1)-db(t2) = 10*log10(P(t1)/P(t2)), independent of which
      baseline the trace itself was referenced to -- this is NOT re-averaging in dB space, it
      is a difference of two already-formed, single log-ratios). LFP's NATIVE (fixation-
      baselined) value is kept as a reference-only column, never used in matched inference.
  OS (omission vs matched real stimulus, same slot position) -- SPK: `om_vs_ctrl_effect_hz`
      ("same slot window on the family control condition"). LFP: RXRR omission-window dB minus
      RRRR trace at the identical absolute time window (times align natively across conditions
      per L2's own design) -- baseline-invariant by construction (the shared fixation-baseline
      term cancels in the subtraction), so NATIVE and HARMONIZED coincide for this contrast.

Position (p2/p3/p4): NOT resolved in v1, by explicit instruction -- RXRR (p2 omission) only,
matching L1-L5's own canonical single-position convention. Deferred as F06-v2.
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("OMISSION_NWB_DIR", "D:/nwb/omission")

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
REPO_ROOT = OA_ROOT.parent
sys.path.insert(0, str(OA_ROOT / "context" / "figures" / "L2_band_power_traces"))
sys.path.insert(0, str(OA_ROOT / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(OA_ROOT / "context" / "figures"))
sys.path.insert(0, str(REPO_ROOT))

from L2_band_power_traces import (  # noqa: E402
    sessions_for_area, session_band_traces, EPOCH_WIN_S, BASELINE_WIN_S, COMMON_TIME_GRID_MS,
    AREAS, BANDS, require_l0_canonical_method,
)

ATLAS_DIR = OA_ROOT / "outputs" / "panel_atlas"
F06_DIR = ATLAS_DIR / "F06"
SUBSTRATE_DIR = OA_ROOT / "outputs" / "f06_substrate"

OMISSION_WIN_MS = (1031.0, 1562.0)   # p2 omission slot, matches L3_stats.json response_windows_ms
LOCAL_BASE_GAP_LO_MS = 250.0          # matches unit_classification.py's local_baseline definition
LOCAL_BASE_GAP_HI_MS = 50.0
LOCAL_BASE_WIN_MS = (OMISSION_WIN_MS[0] - LOCAL_BASE_GAP_LO_MS, OMISSION_WIN_MS[0] - LOCAL_BASE_GAP_HI_MS)
BAND_NAMES = list(BANDS.keys())


def window_mean(trace_db: np.ndarray, win_ms: tuple[float, float]) -> float:
    mask = (COMMON_TIME_GRID_MS >= win_ms[0]) & (COMMON_TIME_GRID_MS <= win_ms[1])
    if not np.any(mask):
        return float("nan")
    return float(np.mean(trace_db[mask]))


def extract_lfp_cell(session_prefix: str, probe: str, area: str) -> dict | None:
    """One (session, area) LFP cell: both conditions, all 5 bands, both contrasts."""
    try:
        omit_traces, n_trials_omit, frac_omit = session_band_traces(
            session_prefix, probe, area, "RXRR")
        stim_traces, n_trials_stim, frac_stim = session_band_traces(
            session_prefix, probe, area, "RRRR")
    except Exception as e:
        return {"exclusion_reason": f"lfp_extraction_failed: {type(e).__name__}: {e}"}

    row = {
        "lfp_n_trials_omission": n_trials_omit, "lfp_n_trials_stim": n_trials_stim,
        "lfp_fraction_repaired_omission": frac_omit, "lfp_fraction_repaired_stim": frac_stim,
    }
    for band in BAND_NAMES:
        om = omit_traces[band]
        st = stim_traces[band]
        omit_win = window_mean(om, OMISSION_WIN_MS)
        local_base_win = window_mean(om, LOCAL_BASE_WIN_MS)
        stim_win = window_mean(st, OMISSION_WIN_MS)  # same absolute window, RRRR condition
        row[f"{band}_ob_native_db"] = omit_win  # already fixation-baselined (F05's own estimator)
        row[f"{band}_ob_harmonized_db"] = omit_win - local_base_win  # local-baseline referenced
        row[f"{band}_os_db"] = omit_win - stim_win  # baseline-invariant, matched real-stimulus
    return row


def aggregate_spk_cell(units: pd.DataFrame) -> dict:
    ob = units["om_vs_base_effect_hz"].dropna()
    os_ = units["om_vs_ctrl_effect_hz"].dropna()
    n_trials = units["n_omission_trials"].dropna()
    return {
        "spk_n_units_total": int(len(units)),
        "spk_n_units_ob": int(len(ob)), "spk_ob_effect_hz_mean": float(ob.mean()) if len(ob) else np.nan,
        "spk_ob_effect_hz_sd": float(ob.std()) if len(ob) > 1 else np.nan,
        "spk_ob_effect_hz_sem": float(ob.std() / np.sqrt(len(ob))) if len(ob) > 1 else np.nan,
        "spk_n_units_os": int(len(os_)), "spk_os_effect_hz_mean": float(os_.mean()) if len(os_) else np.nan,
        "spk_os_effect_hz_sd": float(os_.std()) if len(os_) > 1 else np.nan,
        "spk_os_effect_hz_sem": float(os_.std() / np.sqrt(len(os_))) if len(os_) > 1 else np.nan,
        "spk_n_trials_median": float(n_trials.median()) if len(n_trials) else np.nan,
    }


def main() -> None:
    SUBSTRATE_DIR.mkdir(parents=True, exist_ok=True)
    l0_method = require_l0_canonical_method()
    print(f"L0 gate: canonical_pooling_method={l0_method!r} (confirmed)")
    spk_all = pd.read_csv(OA_ROOT / "outputs" / "classification" / "unit_inclusion_v1.csv")
    print(f"SPK source: {len(spk_all)} units, {spk_all['session'].nunique()} sessions, "
          f"{spk_all['area'].nunique()} areas")

    rows = []
    exclusions = []
    c_s_cells = set(spk_all.groupby(["session", "area"]).groups.keys())
    c_l_attempted = set()

    for area in AREAS:
        sess_list = sessions_for_area(area)
        print(f"=== {area}: {len(sess_list)} candidate sessions ===")
        for session_prefix, subject, probe in sess_list:
            c_l_attempted.add((session_prefix, area))
            spk_units = spk_all[(spk_all["session"] == session_prefix) & (spk_all["area"] == area)]
            if len(spk_units) == 0:
                exclusions.append({"session": session_prefix, "area": area,
                                    "reason": "missing_spk_units_for_session_area"})
                continue

            lfp = extract_lfp_cell(session_prefix, probe, area)
            if lfp is None or "exclusion_reason" in lfp:
                exclusions.append({"session": session_prefix, "area": area,
                                    "reason": lfp.get("exclusion_reason", "unknown") if lfp else "lfp_none"})
                continue

            spk_agg = aggregate_spk_cell(spk_units)
            if spk_agg["spk_n_units_ob"] == 0 and spk_agg["spk_n_units_os"] == 0:
                exclusions.append({"session": session_prefix, "area": area,
                                    "reason": "insufficient_units_both_contrasts"})
                continue

            base_row = {
                "subject": subject, "session": session_prefix, "area": area, "probe": probe,
                "omission_window_ms": str(OMISSION_WIN_MS),
                "local_baseline_window_ms": str(LOCAL_BASE_WIN_MS),
                **lfp, **spk_agg,
                "source_spk": "outputs/classification/unit_inclusion_v1.csv",
                "source_lfp_code": "context/figures/L2_band_power_traces/L2_band_power_traces.py::session_band_traces",
            }
            rows.append(base_row)
            print(f"  {session_prefix} / {area}: OK (n_units={len(spk_units)}, "
                  f"n_trials_omit={lfp['lfp_n_trials_omission']})")

    table = pd.DataFrame(rows)
    excl_df = pd.DataFrame(exclusions)

    c_s = len(c_s_cells)
    c_l = len(c_l_attempted)
    c_matched = len(table)
    print(f"\n|C_S| (session,area cells with >=1 SPK unit) = {c_s}")
    print(f"|C_L| (session,area cells attempted for LFP)  = {c_l}")
    print(f"|C_S intersect C_L| (matched, both present)   = {c_matched}")

    table.to_csv(SUBSTRATE_DIR / "f06_matched_substrate_v1.csv", index=False)
    excl_df.to_csv(SUBSTRATE_DIR / "f06_matched_substrate_v1_exclusions.csv", index=False)

    coverage_by_area = table.groupby("area").size().to_dict() if len(table) else {}
    coverage_by_subject = table.groupby("subject").size().to_dict() if len(table) else {}
    excl_by_reason = excl_df["reason"].value_counts().to_dict() if len(excl_df) else {}

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(),
        "git_sha_note": "uncommitted working tree -- see git status at generation time",
        "n_C_S": c_s, "n_C_L": c_l, "n_matched": c_matched,
        "exclusions_by_reason": excl_by_reason,
        "matched_coverage_by_area": coverage_by_area,
        "matched_coverage_by_subject": coverage_by_subject,
        "omission_window_ms": OMISSION_WIN_MS, "local_baseline_window_ms": LOCAL_BASE_WIN_MS,
        "epoch_window_s": EPOCH_WIN_S, "lfp_native_baseline_window_s": BASELINE_WIN_S,
        "bands_hz": BANDS,
        "position": "RXRR (p2 omission) only -- position resolution deferred to F06-v2",
        "contrasts": {
            "OB_NATIVE": "LFP omission-window dB re fixed fixation baseline (F05's own estimator) -- reference only, NOT used for SPK-LFP matched inference (no valid SPK analogue)",
            "OB_HARMONIZED": "LFP omission-window dB minus local pre-omission-window dB (both on the fixation-baselined trace; algebraically equals a local-baseline-referenced contrast) -- matched to SPK's om_vs_base_effect_hz",
            "OS": "LFP omission-window dB minus RRRR trace at the same absolute window (baseline-invariant by construction) -- matched to SPK's om_vs_ctrl_effect_hz",
        },
        "spk_aggregation": "session x area, mean/SD/SEM of unit-level effects -- units are NOT independent replicates for cross-modal inference; session-area is the matched biological cell",
        "source_spk_file": "outputs/classification/unit_inclusion_v1.csv",
        "source_spk_generated": "2026-08-17 (unit_inclusion_v1_manifest.json)",
        "source_lfp_extraction": "context/figures/L2_band_power_traces/L2_band_power_traces.py (session_band_traces, batched_spectrogram) -- L0's validated canonical_pooling_method='a_per_channel_then_pool', log-last order preserved exactly, reused not reimplemented",
        "l0_gate": f"require_l0_canonical_method() called and passed at run start: {l0_method!r}",
    }
    (SUBSTRATE_DIR / "f06_matched_substrate_v1_receipt.json").write_text(
        json.dumps(receipt, indent=2, default=str))

    print(f"\nWrote {SUBSTRATE_DIR / 'f06_matched_substrate_v1.csv'} ({len(table)} rows)")
    print(f"Wrote {SUBSTRATE_DIR / 'f06_matched_substrate_v1_receipt.json'}")


if __name__ == "__main__":
    main()
