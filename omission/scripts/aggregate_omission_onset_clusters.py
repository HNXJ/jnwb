"""
Second-stage aggregation for decode_omission_onset_sliding_window.py: combines session-level
per-bin decode-accuracy curves and their nulls into a per-area cluster-based permutation test,
and a bootstrap (over sessions) confidence interval on each area's onset latency.

Group-level statistic at each bin = mean across session-level cells of (observed_accuracy - 0.5).
Group-level null draw i at each bin = mean across cells of (that cell's null draw i - 0.5) --
cells share a common draw index (all cells were run with N_PERMUTATIONS=500, same seed
convention), so this reuses each cell's own within-block permutation null rather than
re-permuting at the group level, and preserves whatever bin-to-bin correlation a single
permutation draw produced within each session.

Cluster test: threshold both the observed and every null draw's curve at the null's own per-bin
95th percentile (one-sided, since the hypothesis is decodability ABOVE chance), form contiguous
significant-bin clusters, cluster mass = sum of (statistic - threshold) over the cluster's bins.
An observed cluster is significant if its mass exceeds the 95th percentile of the null draws' own
max-cluster-mass distribution. Onset latency = left edge of the earliest significant cluster.

Bootstrap CI: resample sessions (the independent replication unit) within an area with
replacement, recompute the group curve and its onset, repeat -- CI is the 2.5/97.5 percentile of
the resulting onset distribution. Areas with too few sessions to bootstrap meaningfully (n<3) are
flagged, not silently given a point estimate dressed as a CI.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

IN_DIR = REPO_ROOT / "outputs/classification/omission_onset_sliding_window"
MANIFEST_CSV = IN_DIR / "cell_manifest.csv"
OUT_JSON = REPO_ROOT / "artifacts/data/omission_onset_latency_by_area.json"
OUT_CSV = REPO_ROOT / "outputs/classification/omission_onset_latency_by_area.csv"

AREA_MERGE = {"MST": "MST+FST", "FST": "MST+FST", "V3a": "V3a/d", "V3d": "V3a/d"}
MIN_SESSIONS_FOR_CLUSTER_TEST = 2
N_BOOT = 2000
BOOT_SEED = 42


def load_cells(manifest: pd.DataFrame):
    cells = {}
    for _, row in manifest.iterrows():
        d = np.load(row["npz"])
        cells.setdefault(row["area"], []).append({
            "session": row["session"], "observed": d["observed"], "null": d["null"],
            "bin_centers_ms": d["bin_centers_ms"],
        })
    return cells


def group_curve_and_null(cell_list):
    """Returns (ctr, observed_group[n_bins], null_group[N_PERM, n_bins]) using only bins/perm
    counts common to every cell in the group (cells share the same WIN_MS/BIN_MS/N_PERMUTATIONS
    by construction, so this is just a stack, not an alignment problem)."""
    ctr = cell_list[0]["bin_centers_ms"]
    obs_stack = np.stack([c["observed"] - 0.5 for c in cell_list], axis=0)  # (n_cells, n_bins)
    null_stack = np.stack([c["null"] - 0.5 for c in cell_list], axis=0)     # (n_cells, N_PERM, n_bins)
    observed_group = np.nanmean(obs_stack, axis=0)
    null_group = np.nanmean(null_stack, axis=0)  # (N_PERM, n_bins)
    return ctr, observed_group, null_group


def _clusters_above(curve: np.ndarray, threshold: np.ndarray):
    """Contiguous bins where curve > threshold (per-bin). Returns list of (start_idx, end_idx, mass)."""
    above = curve > threshold
    clusters = []
    i = 0
    n = len(curve)
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            mass = float(np.sum(curve[i:j] - threshold[i:j]))
            clusters.append((i, j, mass))
            i = j
        else:
            i += 1
    return clusters


def cluster_test(ctr, observed_group, null_group):
    """One-sided cluster-based permutation test. Returns dict with onset_ms, cluster spans, p.

    Search is restricted to bins at ctr >= 0 (at or after the omitted slot's own onset).
    A bin centered before slot onset cannot causally carry information about whether that
    slot's stimulus failed to appear -- the label the decoder predicts is not yet determined
    at that time. An above-chance cluster entirely before t=0 is therefore not a candidate
    "reporting the omission" signal by construction, not merely a low-confidence one; dropping
    those bins from the search prevents a null-distribution fluke there from ever being reported
    as an onset (see FEF's spurious -12.5ms single-bin cluster, 2026-08-13).
    """
    n_perm, n_bins = null_group.shape
    valid = ctr >= 0
    ctr, observed_group, null_group = ctr[valid], observed_group[valid], null_group[:, valid]
    n_perm, n_bins = null_group.shape
    per_bin_threshold = np.percentile(null_group, 95, axis=0)  # (n_bins,)

    obs_clusters = _clusters_above(observed_group, per_bin_threshold)

    null_max_mass = np.zeros(n_perm)
    for p in range(n_perm):
        clusters = _clusters_above(null_group[p], per_bin_threshold)
        null_max_mass[p] = max((c[2] for c in clusters), default=0.0)

    sig_clusters = []
    for (i, j, mass) in obs_clusters:
        p_val = float(np.mean(null_max_mass >= mass))
        sig_clusters.append({
            "start_ms": float(ctr[i]), "end_ms": float(ctr[j - 1]), "mass": mass, "p_cluster": p_val,
            "significant": bool(p_val < 0.05),
        })

    onset_ms = None
    for c in sig_clusters:
        if c["significant"]:
            onset_ms = c["start_ms"]
            break

    return {
        "onset_ms": onset_ms, "clusters": sig_clusters,
        "null_max_mass_mean": float(null_max_mass.mean()), "null_max_mass_95pct": float(np.percentile(null_max_mass, 95)),
    }


def bootstrap_onset_ci(cell_list, n_boot=N_BOOT, seed=BOOT_SEED):
    n_sessions = len(cell_list)
    if n_sessions < MIN_SESSIONS_FOR_CLUSTER_TEST:
        return None
    rng = np.random.default_rng(seed)
    onsets = []
    for _ in range(n_boot):
        idx = rng.integers(0, n_sessions, size=n_sessions)
        resampled = [cell_list[i] for i in idx]
        ctr, obs_g, null_g = group_curve_and_null(resampled)
        result = cluster_test(ctr, obs_g, null_g)
        if result["onset_ms"] is not None:
            onsets.append(result["onset_ms"])
    if not onsets:
        return {"n_boot_with_onset": 0, "n_boot": n_boot, "ci_lo_ms": None, "ci_hi_ms": None, "median_ms": None}
    onsets = np.array(onsets)
    return {
        "n_boot_with_onset": int(len(onsets)), "n_boot": n_boot,
        "ci_lo_ms": float(np.percentile(onsets, 2.5)), "ci_hi_ms": float(np.percentile(onsets, 97.5)),
        "median_ms": float(np.median(onsets)),
    }


def main():
    manifest = pd.read_csv(MANIFEST_CSV)
    manifest["area_m"] = manifest["area"].replace(AREA_MERGE)
    cells = load_cells(manifest.assign(area=manifest["area"]))  # keyed by raw area (npz filenames)

    # merge cell lists by area_m
    merged = {}
    for raw_area, cell_list in cells.items():
        area_m = AREA_MERGE.get(raw_area, raw_area)
        merged.setdefault(area_m, []).extend(cell_list)

    rows = []
    detail = {}
    for area_m, cell_list in sorted(merged.items()):
        n_sessions = len(cell_list)
        if n_sessions < MIN_SESSIONS_FOR_CLUSTER_TEST:
            rows.append({"area": area_m, "n_sessions": n_sessions, "onset_ms": None,
                        "ci_lo_ms": None, "ci_hi_ms": None, "note": "too few sessions for cluster test"})
            continue
        ctr, obs_g, null_g = group_curve_and_null(cell_list)
        result = cluster_test(ctr, obs_g, null_g)
        boot = bootstrap_onset_ci(cell_list)
        rows.append({
            "area": area_m, "n_sessions": n_sessions, "onset_ms": result["onset_ms"],
            "ci_lo_ms": boot["ci_lo_ms"] if boot else None, "ci_hi_ms": boot["ci_hi_ms"] if boot else None,
            "boot_median_ms": boot["median_ms"] if boot else None,
            "n_boot_with_onset": boot["n_boot_with_onset"] if boot else 0,
            "n_significant_clusters": sum(c["significant"] for c in result["clusters"]),
            "peak_observed_minus_chance": float(np.nanmax(obs_g)),
            "note": "",
        })
        detail[area_m] = {
            "bin_centers_ms": ctr.tolist(), "observed_minus_chance": obs_g.tolist(),
            "clusters": result["clusters"], "bootstrap": boot,
        }
        print(f"{area_m}: n_sessions={n_sessions} onset_ms={result['onset_ms']} "
              f"boot_CI=({boot['ci_lo_ms'] if boot else None},{boot['ci_hi_ms'] if boot else None}) "
              f"n_sig_clusters={sum(c['significant'] for c in result['clusters'])}")

    out_df = pd.DataFrame(rows).sort_values("onset_ms", na_position="last")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False)
    print("\nwrote", OUT_CSV)
    print(out_df.to_string(index=False))

    import json
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "method": "cluster-based permutation, one-sided (accuracy > chance), group=area, "
                 "unit=session; per-bin threshold = null 95th percentile; cluster mass vs null "
                 "max-cluster-mass distribution; bootstrap CI over sessions with replacement",
        "n_permutations_per_cell": 500, "bin_ms": 25.0, "win_ms": [-100.0, 600.0],
        "n_boot": N_BOOT,
        "summary": rows, "detail": detail,
    }, indent=2), encoding="utf-8")
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
