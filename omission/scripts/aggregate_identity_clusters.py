"""
Second-stage aggregation for decode_identity_sliding_window.py: combines session-level signed
per-bin decodability curves (curve_A -> +1, curve_B -> -1, 0 = chance) into per-area, per-analysis
cluster-based permutation tests and bootstrap onset-latency CIs.

Group-level statistic at each bin = mean across session-level cells of obs_a (resp. obs_b).
Group-level null draw i at each bin = mean across cells of null_a[i] (resp. null_b[i]) -- cells
share a common draw index (N_PERMUTATIONS=500, same seed convention as
decode_identity_sliding_window.py), so this reuses each cell's own within-group permutation null
rather than re-permuting at the group level.

Cluster test (per curve, one-sided): threshold at the null's own per-bin 95th percentile (curve_A,
testing FOR positive/A-leaning decodability) or 5th percentile (curve_B, testing FOR
negative/B-leaning decodability -- implemented by negating both curve and null once and reusing
the same "above threshold" machinery). Cluster mass = sum of (statistic - threshold) over a
contiguous run of above-threshold bins; a cluster is significant if its mass exceeds the 95th
percentile of the null draws' own max-cluster-mass distribution.

Causal restriction: the search is restricted to bins at ctr >= 0 (at or after the decoded slot's
own onset), for the identical reason established in aggregate_omission_onset_clusters.py
(2026-08-13, the FEF -12.5ms false-positive fix) -- a bin centered before a slot's onset cannot
carry information about that slot's identity, since the identity is not yet knowable to the
system at that time. Baking this in from the start here, rather than patching after the fact.

Bootstrap CI: resample sessions (the independent replication unit) within an (area, analysis)
group with replacement, recompute the group curve and its onset, repeat -- CI is the 2.5/97.5
percentile of the resulting onset distribution.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

IN_DIR = REPO_ROOT / "outputs/classification/identity_sliding_window"
MANIFEST_CSV = IN_DIR / "cell_manifest.csv"
OUT_JSON = REPO_ROOT / "artifacts/data/identity_decoding_latency_by_area.json"
OUT_CSV = REPO_ROOT / "outputs/classification/identity_decoding_latency_by_area.csv"

AREA_MERGE = {"MST": "MST+FST", "FST": "MST+FST", "V3a": "V3a/d", "V3d": "V3a/d"}
MIN_SESSIONS_FOR_CLUSTER_TEST = 2
N_BOOT = 2000
BOOT_SEED = 43


def load_cells(manifest: pd.DataFrame):
    cells = {}
    for _, row in manifest.iterrows():
        d = np.load(row["npz"])
        key = (row["area"], row["analysis"])
        cells.setdefault(key, []).append({
            "session": row["session"], "obs_a": d["obs_a"], "obs_b": d["obs_b"],
            "null_a": d["null_a"], "null_b": d["null_b"], "bin_centers_ms": d["bin_centers_ms"],
        })
    return cells


def group_curve_and_null(cell_list, which: str):
    ctr = cell_list[0]["bin_centers_ms"]
    obs_key, null_key = f"obs_{which}", f"null_{which}"
    obs_stack = np.stack([c[obs_key] for c in cell_list], axis=0)   # (n_cells, n_bins)
    null_stack = np.stack([c[null_key] for c in cell_list], axis=0)  # (n_cells, N_PERM, n_bins)
    observed_group = np.nanmean(obs_stack, axis=0)
    null_group = np.nanmean(null_stack, axis=0)
    return ctr, observed_group, null_group


def _clusters_above(curve: np.ndarray, threshold: np.ndarray):
    above = curve > threshold
    clusters = []
    i, n = 0, len(curve)
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


def cluster_test(ctr, observed_group, null_group, *, sign: int):
    """sign=+1 tests for curve significantly ABOVE null (curve_A); sign=-1 tests for curve
    significantly BELOW null (curve_B, via negation so the same above-threshold logic applies).
    Search restricted to ctr >= 0 -- see module docstring."""
    valid = ctr >= 0
    ctr_v = ctr[valid]
    obs_v = sign * observed_group[valid]
    null_v = sign * null_group[:, valid]
    n_perm, n_bins = null_v.shape
    per_bin_threshold = np.percentile(null_v, 95, axis=0)

    obs_clusters = _clusters_above(obs_v, per_bin_threshold)
    null_max_mass = np.zeros(n_perm)
    for p in range(n_perm):
        clusters = _clusters_above(null_v[p], per_bin_threshold)
        null_max_mass[p] = max((c[2] for c in clusters), default=0.0)

    sig_clusters = []
    for (i, j, mass) in obs_clusters:
        p_val = float(np.mean(null_max_mass >= mass))
        sig_clusters.append({
            "start_ms": float(ctr_v[i]), "end_ms": float(ctr_v[j - 1]), "mass": mass,
            "p_cluster": p_val, "significant": bool(p_val < 0.05),
        })
    onset_ms = next((c["start_ms"] for c in sig_clusters if c["significant"]), None)
    return {"onset_ms": onset_ms, "clusters": sig_clusters}


def bootstrap_onset_ci(cell_list, which: str, sign: int, n_boot=N_BOOT, seed=BOOT_SEED):
    n_sessions = len(cell_list)
    if n_sessions < MIN_SESSIONS_FOR_CLUSTER_TEST:
        return None
    rng = np.random.default_rng(seed)
    onsets = []
    for _ in range(n_boot):
        idx = rng.integers(0, n_sessions, size=n_sessions)
        resampled = [cell_list[i] for i in idx]
        ctr, obs_g, null_g = group_curve_and_null(resampled, which)
        result = cluster_test(ctr, obs_g, null_g, sign=sign)
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
    import argparse
    global MANIFEST_CSV, OUT_CSV, OUT_JSON
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, default=None)
    parser.add_argument("--out-csv", type=str, default=None)
    parser.add_argument("--out-json", type=str, default=None)
    args = parser.parse_args()
    if args.manifest:
        MANIFEST_CSV = Path(args.manifest)
    if args.out_csv:
        OUT_CSV = Path(args.out_csv)
    if args.out_json:
        OUT_JSON = Path(args.out_json)

    manifest = pd.read_csv(MANIFEST_CSV)
    manifest["area_m"] = manifest["area"].replace(AREA_MERGE)
    cells = load_cells(manifest.assign(area=manifest["area"]))

    merged = {}
    for (raw_area, analysis), cell_list in cells.items():
        area_m = AREA_MERGE.get(raw_area, raw_area)
        merged.setdefault((area_m, analysis), []).extend(cell_list)

    rows = []
    detail = {}
    for (area_m, analysis), cell_list in sorted(merged.items()):
        n_sessions = len(cell_list)
        entry = {"area": area_m, "analysis": analysis, "n_sessions": n_sessions}
        if n_sessions < MIN_SESSIONS_FOR_CLUSTER_TEST:
            entry.update({"onset_A_ms": None, "onset_B_ms": None, "note": "too few sessions"})
            rows.append(entry)
            continue
        ctr, obs_a, null_a = group_curve_and_null(cell_list, "a")
        _, obs_b, null_b = group_curve_and_null(cell_list, "b")
        res_a = cluster_test(ctr, obs_a, null_a, sign=1)
        res_b = cluster_test(ctr, obs_b, null_b, sign=-1)
        boot_a = bootstrap_onset_ci(cell_list, "a", sign=1)
        boot_b = bootstrap_onset_ci(cell_list, "b", sign=-1)
        entry.update({
            "onset_A_ms": res_a["onset_ms"], "ci_lo_A_ms": boot_a["ci_lo_ms"] if boot_a else None,
            "ci_hi_A_ms": boot_a["ci_hi_ms"] if boot_a else None,
            "onset_B_ms": res_b["onset_ms"], "ci_lo_B_ms": boot_b["ci_lo_ms"] if boot_b else None,
            "ci_hi_B_ms": boot_b["ci_hi_ms"] if boot_b else None,
            "peak_A": float(np.nanmax(obs_a)), "trough_B": float(np.nanmin(obs_b)),
            "n_sig_clusters_A": sum(c["significant"] for c in res_a["clusters"]),
            "n_sig_clusters_B": sum(c["significant"] for c in res_b["clusters"]),
            "note": "",
        })
        rows.append(entry)
        detail[f"{area_m}|{analysis}"] = {
            "bin_centers_ms": ctr.tolist(), "curve_A": obs_a.tolist(), "curve_B": obs_b.tolist(),
            "clusters_A": res_a["clusters"], "clusters_B": res_b["clusters"],
            "bootstrap_A": boot_a, "bootstrap_B": boot_b,
        }
        print(f"{area_m}/{analysis}: n_sessions={n_sessions} onset_A={res_a['onset_ms']} onset_B={res_b['onset_ms']}")

    out_df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False)
    print("\nwrote", OUT_CSV)
    print(out_df.to_string(index=False))

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "method": "cluster-based permutation, one-sided, group=area x analysis, unit=session; "
                 "search restricted to bins >= 0 (causal); bootstrap CI over sessions",
        "n_permutations_per_cell": 500, "bin_ms": 25.0, "win_ms": [-100.0, 600.0], "n_boot": N_BOOT,
        "summary": rows, "detail": detail,
    }, indent=2), encoding="utf-8")
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
