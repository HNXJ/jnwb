"""
tag_stable_units.py
====================
Tags each unit in grand_unit_metadata.csv with is_stable based on 3 criteria:

  1. Per-trial spike count: unit must fire >= 5 spikes in EVERY correct trial,
     where a trial window is [-1000ms, +4000ms] around p1 onset
     (p1 = stimulus_number == 2.0, correct == 1.0 in omission_glo_passive intervals).
  2. Overall average firing rate >= 1.0 Hz.
  3. presence_ratio >= 0.98 OR snr > 0.75.

A unit is Stable if it satisfies ALL THREE criteria.

Outputs:
  outputs/spsam/grand_unit_metadata.csv  -- adds column: is_stable, min_trial_spikes, n_trials_checked
  outputs/spsam/grand_unit_lfp_coupling.csv -- adds column: is_stable
  outputs/spsam/stability_report.md     -- human-readable summary
"""

import glob
import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pynwb import NWBHDF5IO

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUTPUT_DIR = "outputs/spsam"
NWB_GLOB   = "D:/analysis/nwb/*.nwb"

# Stability thresholds
MIN_SPIKES_PER_TRIAL = 5          # criterion 1: every trial must have >= this many spikes
PRE_WINDOW_S         = 1.0        # 1000ms before p1
POST_WINDOW_S        = 4.0        # 4000ms after p1
MIN_FIRING_RATE      = 1.0        # criterion 2
MIN_PRESENCE_RATIO   = 0.98       # criterion 3a
MIN_SNR              = 0.75       # criterion 3b

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def get_session_p1_onsets(nwb_path: str) -> np.ndarray:
    """Return start_time of correct p1 events (stimulus_number==2, correct==1)."""
    with NWBHDF5IO(nwb_path, "r") as io:
        nwb = io.read()
        if "omission_glo_passive" not in nwb.intervals:
            return np.array([])
        idf = nwb.intervals["omission_glo_passive"].to_dataframe()
    for col in ("correct", "stimulus_number"):
        idf[col] = pd.to_numeric(idf[col], errors="coerce")
    p1 = idf[(idf["correct"] == 1.0) & (idf["stimulus_number"] == 2.0)]
    return p1["start_time"].values


def compute_unit_trial_spike_counts(
    spike_times: np.ndarray, p1_onsets: np.ndarray
) -> np.ndarray:
    """Count spikes per trial in [p1 - PRE_WINDOW_S, p1 + POST_WINDOW_S]."""
    counts = np.empty(len(p1_onsets), dtype=np.int32)
    for i, t0 in enumerate(p1_onsets):
        t_start = t0 - PRE_WINDOW_S
        t_end   = t0 + POST_WINDOW_S
        counts[i] = int(np.sum((spike_times >= t_start) & (spike_times < t_end)))
    return counts


def tag_session(nwb_path: str, session_id: str, units_df: pd.DataFrame) -> pd.DataFrame:
    """
    For one session: load spikes, compute per-trial counts, apply criteria 1.
    Criteria 2 and 3 are applied from the metadata CSV (already computed).
    Returns a DataFrame with columns: unit_id, min_trial_spikes, n_trials_checked, stable_c1
    """
    log.info(f"  [{session_id}] Loading NWB ...")
    p1_onsets = get_session_p1_onsets(nwb_path)
    n_trials = len(p1_onsets)
    log.info(f"  [{session_id}] Correct p1 events: {n_trials}")

    if n_trials == 0:
        log.warning(f"  [{session_id}] No correct p1 events — criterion 1 CANNOT be evaluated. Marking all unstable.")
        rows = []
        for _, row in units_df.iterrows():
            rows.append({
                "unit_id": row["unit_id"],
                "session_id": session_id,
                "min_trial_spikes": np.nan,
                "n_trials_checked": 0,
                "stable_c1": False,
            })
        return pd.DataFrame(rows)

    with NWBHDF5IO(nwb_path, "r") as io:
        nwb = io.read()
        nwb_units = nwb.units.to_dataframe()

    # NWB cluster_id is stored as string float ('105.0'); normalise to int
    nwb_units["_cluster_id_int"] = pd.to_numeric(
        nwb_units["cluster_id"], errors="coerce"
    ).astype("Int64")

    rows = []
    for _, row in units_df.iterrows():
        uid = row["unit_id"]
        # unit_id is the raw cluster_id integer
        try:
            cluster_id = int(uid)
        except (ValueError, TypeError):
            rows.append({
                "unit_id": uid,
                "session_id": session_id,
                "min_trial_spikes": np.nan,
                "n_trials_checked": n_trials,
                "stable_c1": False,
            })
            continue

        # Locate unit in NWB units table using normalised int cluster_id
        unit_rows = nwb_units[nwb_units["_cluster_id_int"] == cluster_id]
        if unit_rows.empty:
            rows.append({
                "unit_id": uid,
                "session_id": session_id,
                "min_trial_spikes": np.nan,
                "n_trials_checked": n_trials,
                "stable_c1": False,
            })
            continue

        spike_times = np.asarray(unit_rows.iloc[0]["spike_times"])
        counts = compute_unit_trial_spike_counts(spike_times, p1_onsets)
        min_spikes = int(counts.min())

        rows.append({
            "unit_id": uid,
            "session_id": session_id,
            "min_trial_spikes": min_spikes,
            "n_trials_checked": n_trials,
            "stable_c1": bool(min_spikes >= MIN_SPIKES_PER_TRIAL),
        })

    log.info(
        f"  [{session_id}] Done — {sum(r['stable_c1'] for r in rows)}/{len(rows)} "
        f"pass criterion 1 (>={MIN_SPIKES_PER_TRIAL} spikes/trial)"
    )
    return pd.DataFrame(rows)


def main():
    log.info("=" * 60)
    log.info("SpSAM Stability Tagger")
    log.info(f"Run: {datetime.now(timezone.utc).isoformat()}")
    log.info("=" * 60)

    # Load grand metadata
    meta_path = f"{OUTPUT_DIR}/grand_unit_metadata.csv"
    coupling_path = f"{OUTPUT_DIR}/grand_unit_lfp_coupling.csv"

    if not os.path.exists(meta_path):
        log.error(f"Grand metadata not found: {meta_path}")
        sys.exit(1)

    meta = pd.read_csv(meta_path)
    coupling = pd.read_csv(coupling_path)

    # Drop stale stability columns from any previous run to avoid merge _x/_y collisions
    stale_cols = ["stable_c1", "is_stable", "min_trial_spikes", "n_trials_checked"]
    meta.drop(columns=[c for c in stale_cols if c in meta.columns], inplace=True)
    coupling.drop(columns=[c for c in ["is_stable"] if c in coupling.columns], inplace=True)

    log.info(f"Loaded metadata: {len(meta)} units, {meta['session_id'].nunique()} sessions")

    # Build NWB path map  (filenames may have subject prefix, key on session date)
    nwb_files = sorted(glob.glob(NWB_GLOB))
    nwb_map = {}
    for f in nwb_files:
        basename = os.path.basename(f)
        if "ses-" in basename:
            sid = basename.split("ses-")[1].split("_")[0]
        else:
            sid = basename.split("_")[0]
        nwb_map[sid] = f
    log.info(f"NWB files found: {len(nwb_map)} sessions")

    # --- Apply criteria 2 and 3 from metadata (no NWB needed) ---------------
    c2_mask = (meta["firing_rate"] >= MIN_FIRING_RATE).values
    c3_mask = ((meta["presence_ratio"] >= MIN_PRESENCE_RATIO) | (meta["snr"] > MIN_SNR)).values
    log.info(f"\nCriterion 2 (FR >= {MIN_FIRING_RATE} Hz): {c2_mask.sum()}/{len(meta)}")
    log.info(f"Criterion 3 (PR >= {MIN_PRESENCE_RATIO} OR SNR > {MIN_SNR}): {c3_mask.sum()}/{len(meta)}")

    # --- Apply criterion 1 per session (NWB read) ----------------------------
    all_c1_rows = []
    for session_id in sorted(meta["session_id"].astype(str).unique()):
        if session_id not in nwb_map:
            log.warning(f"  [{session_id}] NWB not found — marking all unstable")
            sess_units = meta[meta["session_id"].astype(str) == session_id]
            for _, row in sess_units.iterrows():
                all_c1_rows.append({
                    "unit_id": row["unit_id"],
                    "session_id": session_id,
                    "min_trial_spikes": np.nan,
                    "n_trials_checked": 0,
                    "stable_c1": False,
                })
            continue

        sess_units = meta[meta["session_id"].astype(str) == session_id].copy()
        c1_df = tag_session(nwb_map[session_id], session_id, sess_units)
        all_c1_rows.extend(c1_df.to_dict("records"))

    c1_df_all = pd.DataFrame(all_c1_rows)
    # Align session_id dtype with meta (int64)
    c1_df_all["session_id"] = c1_df_all["session_id"].astype(int)
    # Merge on both unit_id AND session_id to avoid ambiguity if cluster_ids repeat across sessions
    meta = meta.merge(
        c1_df_all[["unit_id", "session_id", "min_trial_spikes", "n_trials_checked", "stable_c1"]]
            .rename(columns={"session_id": "_sid_merge"}),
        left_on=["unit_id", "session_id"],
        right_on=["unit_id", "_sid_merge"],
        how="left",
    ).drop(columns=["_sid_merge"], errors="ignore")

    # --- Combine all three criteria -------------------------------------------
    meta["stable_c1"] = meta["stable_c1"].fillna(False).astype(bool)
    c2_mask = (meta["firing_rate"] >= MIN_FIRING_RATE).values
    c3_mask = ((meta["presence_ratio"] >= MIN_PRESENCE_RATIO) | (meta["snr"] > MIN_SNR)).values
    meta["is_stable"] = (
        meta["stable_c1"] &
        c2_mask &
        c3_mask
    )

    log.info(f"Criterion 1 (>={MIN_SPIKES_PER_TRIAL} spikes/trial in every trial): {meta['stable_c1'].sum()}/{len(meta)}")
    log.info(f"STABLE (C1 AND C2 AND C3): {meta['is_stable'].sum()}/{len(meta)}")

    # --- Save updated metadata ------------------------------------------------
    meta.to_csv(meta_path, index=False)
    log.info(f"\nSaved tagged metadata -> {meta_path}")

    # --- Tag coupling table ---------------------------------------------------
    uid_stable = meta.set_index("unit_id")["is_stable"].to_dict()
    coupling["is_stable"] = coupling["unit_id"].map(uid_stable).fillna(False).astype(bool)
    coupling.to_csv(coupling_path, index=False)
    log.info(f"Tagged coupling table -> {coupling_path}")

    # --- Write stability report -----------------------------------------------
    _write_report(meta)


def _write_report(meta: pd.DataFrame):
    """Write a markdown stability report."""
    total = len(meta)
    n_stable = meta["is_stable"].sum()
    n_unstable = total - n_stable

    # Breakdown by group
    grp = (
        meta.groupby("group")["is_stable"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "stable", "count": "total"})
    )
    grp["unstable"] = grp["total"] - grp["stable"]
    grp["pct_stable"] = (grp["stable"] / grp["total"] * 100).round(1)

    # Breakdown by area
    area = (
        meta.groupby("area")["is_stable"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "stable", "count": "total"})
    )
    area["pct_stable"] = (area["stable"] / area["total"] * 100).round(1)
    area = area.sort_values("stable", ascending=False)

    # Criterion breakdown
    c1_pass = meta["stable_c1"].sum()
    c2_pass = (meta["firing_rate"] >= MIN_FIRING_RATE).sum()
    c3_pass = ((meta["presence_ratio"] >= MIN_PRESENCE_RATIO) | (meta["snr"] > MIN_SNR)).sum()

    # Omission neurons that are stable
    stable_omission = meta[(meta["is_stable"]) & (meta["group"] == "omission")]

    lines = [
        "# SpSAM Stability Report",
        f"\n**Generated**: {datetime.now(timezone.utc).isoformat()}",
        f"\n**Total units**: {total}",
        f"**Stable**: {n_stable} ({n_stable/total*100:.1f}%)",
        f"**Unstable**: {n_unstable} ({n_unstable/total*100:.1f}%)",
        "\n---\n",
        "## Criterion Breakdown\n",
        "| Criterion | Threshold | Units Passing |",
        "|-----------|-----------|---------------|",
        f"| C1: min spikes/trial | >= {MIN_SPIKES_PER_TRIAL} spikes in every trial (window: -{PRE_WINDOW_S*1000:.0f}ms to +{POST_WINDOW_S*1000:.0f}ms) | {c1_pass}/{total} ({c1_pass/total*100:.1f}%) |",
        f"| C2: firing rate | >= {MIN_FIRING_RATE} Hz | {c2_pass}/{total} ({c2_pass/total*100:.1f}%) |",
        f"| C3: presence OR SNR | PR >= {MIN_PRESENCE_RATIO} OR SNR > {MIN_SNR} | {c3_pass}/{total} ({c3_pass/total*100:.1f}%) |",
        f"| **ALL (is_stable)** | C1 AND C2 AND C3 | **{n_stable}/{total} ({n_stable/total*100:.1f}%)** |",
        "\n---\n",
        "## Stable Units by Group\n",
        grp.reset_index().to_markdown(index=False),
        "\n---\n",
        "## Stable Units by Area\n",
        area.reset_index().to_markdown(index=False),
        "\n---\n",
        "## Stable Omission Neurons\n",
        f"**{len(stable_omission)}** omission-classified units pass all 3 stability criteria.\n",
    ]

    if len(stable_omission) > 0:
        area_counts = stable_omission.groupby("area")["unit_id"].count().sort_values(ascending=False)
        lines.append("**By area:**\n")
        for area_name, cnt in area_counts.items():
            lines.append(f"- {area_name}: {cnt}")

    report_path = f"{OUTPUT_DIR}/stability_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"Stability report -> {report_path}")


if __name__ == "__main__":
    main()
