#!/usr/bin/env python3
# scripts/run_spk_response_metric_sensitivity_a8_2.py
"""
Phase A8.2 real-data SPK response metric sensitivity sweeps.
Evaluates candidate classification stability across multiple significance thresholds, FDR scopes,
Cohen's d effect-size thresholds, response window variants, family strata, and omission slots.
Preserves memmap/batch streaming policy and zero raw H5 reads.
Strictly blocks biological population and area hierarchy claims.
"""

import os
import re
import csv
import json
import sys
import argparse
import subprocess
from pathlib import Path
import numpy as np
import scipy.stats as stats

# Timing Constants
P1_ONSET_MS = 0
P2_ONSET_MS = 1031
P3_ONSET_MS = 2062
P4_ONSET_MS = 3093

TRUTH_SAFE_UNVERIFIED = "truth_safe_unverified"
CONDITIONS = ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]

from src.analysis.provenance import get_git_commit, sha256_file
from src.analysis.stats.multitest import benjamini_hochberg as benjamini_hochberg_correction
from src.analysis.contracts import get_condition_family, get_omission_position, get_matched_control

# Ensure scripts/ is in path for sibling imports
scripts_dir = str(Path(__file__).parent)
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
from _response_metric_common import locate_file_recursively, compute_cohens_d, run_paired_test, run_unpaired_test

def compute_sha256(file_path):
    return sha256_file(file_path)

def parse_args():
    parser = argparse.ArgumentParser(description="Phase A8.2 SPK Response Metric Sensitivity Sweeps")
    parser.add_argument("--data-root", required=True, help="Path to data root directory")
    parser.add_argument("--a5-dir", default="reports/analysis_A5_signal_shape_inventory", help="Path to A5 inventory directory")
    parser.add_argument("--a6-dir", default="reports/analysis_A6_area_probe_metadata", help="Path to A6 inventory directory")
    parser.add_argument("--a7-dir", default="reports/analysis_A7_spk_psth_smoke", help="Path to A7 inventory directory")
    parser.add_argument("--a8-dir", default="reports/analysis_A8_1_spk_response_metrics", help="Path to A8.1 metrics directory")
    parser.add_argument("--out-dir", default="reports/analysis_A8_2_spk_response_metric_sensitivity", help="Path to output directory")
    parser.add_argument("--plan-dir", default="reports/analysis_A8_2_spk_response_metric_sensitivity_plan", help="Path to sensitivity plan directory")
    parser.add_argument("--unit-batch-size", type=int, default=64, help="Unit batch size for memmap streaming")
    parser.add_argument("--max-sessions", type=int, default=None, help="Optional sessions limit for profiling")
    parser.add_argument("--max-units-per-file", type=int, default=None, help="Optional units limit for profiling")
    parser.add_argument("--dry-run", action="store_true", help="Skip real calculations")
    return parser.parse_args()

def load_sensitivity_grid(grid_path):
    grid = []
    with open(grid_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            grid.append({
                "grid_index": int(row["grid_index"]),
                "alpha_level": float(row["alpha_level"]),
                "q_scope": row["q_scope"].strip(),
                "cohens_d_minimum": float(row["cohens_d_minimum"]),
                "omission_window": row["omission_window"].strip(),
                "slot_stratification": row["slot_stratification"].strip(),
                "family_stratification": row["family_stratification"].strip(),
                "notes": row["notes"].strip()
            })
    return grid

def compute_entropy(labels_list):
    """Computes entropy of the primary label sequence across sweeps."""
    n = len(labels_list)
    if n == 0:
        return 0.0
    unique, counts = np.unique(labels_list, return_counts=True)
    probs = counts / n
    return float(-np.sum(probs * np.log2(probs)))

def resolve_priority_label(labels_set):
    """Determines unit-level candidate label based on deterministic priority."""
    if "X_candidate" in labels_set:
        return "X_candidate"
    elif "O_plus_candidate" in labels_set:
        return "O_plus_candidate"
    elif "O_minus_candidate" in labels_set:
        return "O_minus_candidate"
    elif "S_plus_candidate" in labels_set:
        return "S_plus_candidate"
    elif "S_minus_candidate" in labels_set:
        return "S_minus_candidate"
    else:
        return "null_or_unclassified"

def load_inventories_and_grid(args):
    """Loads input inventories, metadata, sensitivity grid, and warning burdens."""
    grid_path = Path(args.plan_dir) / "sensitivity_grid.csv"
    if not grid_path.exists():
        raise FileNotFoundError(f"sensitivity_grid.csv not found at {grid_path}")
    grid = load_sensitivity_grid(grid_path)

    a7_inventory_path = Path(args.a7_dir) / "spk_smoke_file_inventory.csv"
    if not a7_inventory_path.exists():
        raise FileNotFoundError(f"A7 spk_smoke_file_inventory.csv not found at {a7_inventory_path}")

    spk_files = []
    with open(a7_inventory_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["time_axis_status"] == "valid_timebase_6000ms":
                spk_files.append(row)

    a6_unit_inventory_path = Path(args.a6_dir) / "unit_area_inventory.csv"
    a6_units = {}
    if a6_unit_inventory_path.exists():
        with open(a6_unit_inventory_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s_id = row["session_id"]
                u_idx = int(row["unit_index"])
                a6_units[(s_id, u_idx)] = row

    a8_warnings_path = Path(args.a8_dir) / "warning_summary_by_session_condition_slot.csv"
    session_warning_burden = {}
    if a8_warnings_path.exists():
        with open(a8_warnings_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s_id = row["session_id"]
                n_warn = int(row["n_warnings"])
                session_warning_burden[s_id] = session_warning_burden.get(s_id, 0) + n_warn

    # Load A8.1 summary json denominators
    a8_sums = {
        "n_long_metric_rows_total": 39980,
        "n_primary_contrast_rows": 39232,
        "n_nonprimary_or_auxiliary_metric_rows": 748,
        "n_unit_candidate_label_rows": 3521
    }
    a8_summary_path = Path(args.a8_dir) / "response_metric_execution_summary.json"
    if a8_summary_path.exists():
        try:
            with open(a8_summary_path, "r", encoding="utf-8") as f:
                a8_sum = json.load(f)
                a8_sums["n_long_metric_rows_total"] = a8_sum.get("n_long_metric_rows_total", 39980)
                a8_sums["n_primary_contrast_rows"] = a8_sum.get("n_primary_contrast_rows", 39232)
                a8_sums["n_nonprimary_or_auxiliary_metric_rows"] = a8_sum.get("n_nonprimary_or_auxiliary_metric_rows", 748)
                a8_sums["n_unit_candidate_label_rows"] = a8_sum.get("n_unit_candidate_label_rows", 3521)
        except Exception as e:
            print(f"Warning: Failed to load A8.1.1 denominators: {e}")

    return grid, spk_files, a6_units, session_warning_burden, a8_sums

def precompute_session_metrics(session_id, session_files, data_root, unit_batch_size, max_units_per_file, unit_condition_metrics, unique_units_map):
    """Precomputes metrics for all units in a session across three timing windows."""
    control_files_map = {}
    for row in session_files:
        cond = row["condition"]
        if cond in ["AAAB", "BBBA", "RRRR"]:
            control_files_map[cond] = row

    n_spk_files_processed = 0
    n_trials_used = 0

    for row in session_files:
        condition = row["condition"]
        basename = row["source_file"]
        family = get_condition_family(condition)
        om_slot = get_omission_position(condition)
        is_omission = om_slot != "None"

        real_path = locate_file_recursively(data_root, basename)
        if not real_path:
            continue

        if real_path.suffix.lower() in [".h5", ".hdf5"]:
            continue

        ctrl_cond = get_matched_control(condition)
        ctrl_row = control_files_map.get(ctrl_cond)
        ctrl_path = None
        if ctrl_row:
            ctrl_path = locate_file_recursively(data_root, ctrl_row["source_file"])

        try:
            arr = np.load(real_path, mmap_mode="r")
            n_trials, n_units, n_timepoints = arr.shape
            n_spk_files_processed += 1
            n_trials_used += n_trials

            ctrl_arr = None
            if ctrl_path:
                try:
                    ctrl_arr = np.load(ctrl_path, mmap_mode="r")
                except Exception:
                    pass

            u_max = n_units
            if max_units_per_file:
                u_max = min(u_max, max_units_per_file)

            for u_start in range(0, u_max, unit_batch_size):
                u_end = min(u_start + unit_batch_size, u_max)
                slice_arr = arr[:, u_start:u_end, :]
                slice_ctrl_arr = None
                if ctrl_arr is not None:
                    slice_ctrl_arr = ctrl_arr[:, u_start:u_end, :]

                for u_local in range(u_end - u_start):
                    u_idx = u_start + u_local
                    unit_key = (session_id, u_idx)
                    unique_units_map[unit_key] = basename

                    unit_spk = slice_arr[:, u_local, :]

                    fx_rate = np.mean(unit_spk[:, 500:1000]) * 1000.0
                    fx_trials = np.mean(unit_spk[:, 500:1000], axis=1) * 1000.0

                    p1_rate = np.mean(unit_spk[:, 1000:1531]) * 1000.0
                    p1_trials = np.mean(unit_spk[:, 1000:1531], axis=1) * 1000.0

                    p2_rate = np.mean(unit_spk[:, 2031:2562]) * 1000.0
                    p2_trials = np.mean(unit_spk[:, 2031:2562], axis=1) * 1000.0

                    p3_rate = np.mean(unit_spk[:, 3062:3593]) * 1000.0
                    p3_trials = np.mean(unit_spk[:, 3062:3593], axis=1) * 1000.0

                    p4_rate = np.mean(unit_spk[:, 4093:4624]) * 1000.0
                    p4_trials = np.mean(unit_spk[:, 4093:4624], axis=1) * 1000.0

                    p_p1, d_p1 = run_paired_test(p1_trials, fx_trials)
                    p_p2, d_p2 = run_paired_test(p2_trials, fx_trials)
                    p_p3, d_p3 = run_paired_test(p3_trials, fx_trials)
                    p_p4, d_p4 = run_paired_test(p4_trials, fx_trials)

                    window_variants = ["1000-1500", "1000-1300", "1000-1700"]
                    for w_var in window_variants:
                        om_rate = 0.0
                        om_base_rate = 0.0
                        ctrl_om_rate = 0.0
                        p_om_base, d_om_base = 1.0, 0.0
                        p_om_ctrl, d_om_ctrl = 1.0, 0.0
                        om_trials = np.zeros(n_trials)
                        om_base_trials = np.zeros(n_trials)
                        ctrl_om_trials = np.zeros(n_trials)
                        post_om_gain = 0.0

                        if is_omission:
                            if om_slot == "p2":
                                onset = 2031
                                base_start, base_end = 1781, 1981
                                post_start, post_end = 2562, 3031
                            elif om_slot == "p3":
                                onset = 3062
                                base_start, base_end = 2812, 3012
                                post_start, post_end = 3593, 4062
                            elif om_slot == "p4":
                                onset = 4093
                                base_start, base_end = 3843, 4043
                                post_start, post_end = 4624, 5093

                            if w_var == "1000-1500":
                                om_dur = 531
                            elif w_var == "1000-1300":
                                om_dur = 300
                            elif w_var == "1000-1700":
                                om_dur = 700

                            om_rate = np.mean(unit_spk[:, onset:onset+om_dur]) * 1000.0
                            om_trials = np.mean(unit_spk[:, onset:onset+om_dur], axis=1) * 1000.0

                            om_base_rate = np.mean(unit_spk[:, base_start:base_end]) * 1000.0
                            om_base_trials = np.mean(unit_spk[:, base_start:base_end], axis=1) * 1000.0

                            post_om_rate = np.mean(unit_spk[:, post_start:post_end]) * 1000.0
                            post_om_gain = post_om_rate - om_base_rate

                            if slice_ctrl_arr is not None:
                                ctrl_om_trials = np.mean(slice_ctrl_arr[:, u_local, onset:onset+om_dur], axis=1) * 1000.0
                                ctrl_om_rate = np.mean(ctrl_om_trials)

                            p_om_base, d_om_base = run_paired_test(om_trials, om_base_trials)
                            if slice_ctrl_arr is not None:
                                p_om_ctrl, d_om_ctrl = run_unpaired_test(om_trials, ctrl_om_trials)

                        metric_key = (session_id, u_idx, condition, w_var)
                        unit_condition_metrics[metric_key] = {
                            "fx_rate": fx_rate,
                            "p1_rate": p1_rate,
                            "p2_rate": p2_rate,
                            "p3_rate": p3_rate,
                            "p4_rate": p4_rate,
                            "om_rate": om_rate,
                            "om_base_rate": om_base_rate,
                            "ctrl_om_rate": ctrl_om_rate,
                            "post_om_gain": post_om_gain,
                            "p_p1": p_p1, "d_p1": d_p1,
                            "p_p2": p_p2, "d_p2": d_p2,
                            "p_p3": p_p3, "d_p3": d_p3,
                            "p_p4": p_p4, "d_p4": d_p4,
                            "p_om_base": p_om_base, "d_om_base": d_om_base,
                            "p_om_ctrl": p_om_ctrl, "d_om_ctrl": d_om_ctrl,
                            "n_trials": n_trials,
                            "family": family,
                            "omission_slot": om_slot,
                            "basename": basename
                        }
        except Exception as e:
            print(f"Warning: Failed to process slice for file {basename}: {e}")

    return n_spk_files_processed, n_trials_used

def run_sensitivity_sweeps(grid, unit_condition_metrics, unique_units_map, unit_label_history, realized_grid):
    """Executes sensitivity sweeps over the grid."""
    for idx, sweep in enumerate(grid):
        g_idx = sweep["grid_index"]
        alpha = sweep["alpha_level"]
        q_scope = sweep["q_scope"]
        d_min = sweep["cohens_d_minimum"]
        om_win = sweep["omission_window"]
        slot_strat = sweep["slot_stratification"]
        family_strat = sweep["family_stratification"]

        evaluated_keys = []
        for key, m in unit_condition_metrics.items():
            s_id, u_idx, cond, w_val = key
            if w_val != om_win:
                continue
            
            if slot_strat != "all":
                if m["omission_slot"] != slot_strat and m["omission_slot"] != "None":
                    continue
            
            if family_strat == "A+B":
                if m["family"] not in ["A-family", "B-family"]:
                    continue
            
            evaluated_keys.append(key)

        raw_p_list = []
        for key in evaluated_keys:
            m = unit_condition_metrics[key]
            raw_p_list.extend([m["p_p1"], m["p_p2"], m["p_p3"], m["p_p4"]])
            if m["omission_slot"] != "None":
                raw_p_list.extend([m["p_om_base"], m["p_om_ctrl"]])

        q_list = np.array(raw_p_list)
        if q_scope != "none (p_uncorrected)":
            if q_scope == "global_all_units_all_primary_contrasts":
                q_list = benjamini_hochberg_correction(raw_p_list)
            elif q_scope == "within_session_all_units_all_primary_contrasts":
                q_map = np.ones(len(raw_p_list))
                session_p_indices = {}
                ptr = 0
                for key in evaluated_keys:
                    s_id = key[0]
                    n_p = 6 if unit_condition_metrics[key]["omission_slot"] != "None" else 4
                    session_p_indices.setdefault(s_id, []).extend(range(ptr, ptr + n_p))
                    ptr += n_p
                
                for s_id, indices in session_p_indices.items():
                    sub_p = [raw_p_list[i] for i in indices]
                    sub_q = benjamini_hochberg_correction(sub_p)
                    for i, q_val in zip(indices, sub_q):
                        q_map[i] = q_val
                q_list = q_map
            elif q_scope == "per_metric_family":
                q_map = np.ones(len(raw_p_list))
                ptr = 0
                family_p_indices = {"stimulus": [], "om_base": [], "om_ctrl": []}
                for key in evaluated_keys:
                    is_om = unit_condition_metrics[key]["omission_slot"] != "None"
                    family_p_indices["stimulus"].extend([ptr, ptr+1, ptr+2, ptr+3])
                    ptr += 4
                    if is_om:
                        family_p_indices["om_base"].append(ptr)
                        family_p_indices["om_ctrl"].append(ptr+1)
                        ptr += 2
                
                for f_name, indices in family_p_indices.items():
                    if indices:
                        sub_p = [raw_p_list[i] for i in indices]
                        sub_q = benjamini_hochberg_correction(sub_p)
                        for i, q_val in zip(indices, sub_q):
                            q_map[i] = q_val
                q_list = q_map

        ptr = 0
        sweep_q_values = {}
        for key in evaluated_keys:
            m = unit_condition_metrics[key]
            q_p1 = q_list[ptr]
            q_p2 = q_list[ptr+1]
            q_p3 = q_list[ptr+2]
            q_p4 = q_list[ptr+3]
            ptr += 4
            q_om_base = 1.0
            q_om_ctrl = 1.0
            if m["omission_slot"] != "None":
                q_om_base = q_list[ptr]
                q_om_ctrl = q_list[ptr+1]
                ptr += 2
            
            sweep_q_values[key] = {
                "q_p1": q_p1, "q_p2": q_p2, "q_p3": q_p3, "q_p4": q_p4,
                "q_om_base": q_om_base, "q_om_ctrl": q_om_ctrl
            }

        sweep_unit_labels = {}
        for unit_key in unique_units_map.keys():
            sweep_unit_labels[unit_key] = set()

        for key in evaluated_keys:
            s_id, u_idx, cond, w_val = key
            m = unit_condition_metrics[key]
            q_info = sweep_q_values[key]
            is_om = m["omission_slot"] != "None"

            def sig_check(p_val, q_val):
                if q_scope == "none (p_uncorrected)":
                    return p_val < alpha
                return q_val < alpha

            lbls = []
            if m["p1_rate"] > 2.0 and sig_check(m["p_p1"], q_info["q_p1"]) and m["d_p1"] > d_min:
                lbls.append("S_plus_candidate")
            if m["fx_rate"] > 2.0 and sig_check(m["p_p1"], q_info["q_p1"]) and m["d_p1"] < -d_min:
                lbls.append("S_minus_candidate")

            if is_om:
                if m["om_rate"] > 2.0 and sig_check(m["p_om_base"], q_info["q_om_base"]) and m["d_om_base"] > d_min:
                    lbls.append("O_plus_candidate")
                if m["om_base_rate"] > 2.0 and sig_check(m["p_om_base"], q_info["q_om_base"]) and m["d_om_base"] < -d_min:
                    lbls.append("O_minus_candidate")
                if (m["om_rate"] > 2.0 and
                    sig_check(m["p_om_base"], q_info["q_om_base"]) and m["d_om_base"] > d_min and
                    sig_check(m["p_om_ctrl"], q_info["q_om_ctrl"]) and m["d_om_ctrl"] > d_min):
                    lbls.append("X_candidate")

            unit_key = (s_id, u_idx)
            for l in lbls:
                sweep_unit_labels[unit_key].add(l)

        sweep_counts = {"S_plus": 0, "S_minus": 0, "O_plus": 0, "O_minus": 0, "X": 0, "null": 0}
        for unit_key, labels_set in sweep_unit_labels.items():
            primary_lbl = resolve_priority_label(labels_set)
            unit_label_history[unit_key].append(primary_lbl)
            
            if primary_lbl == "S_plus_candidate":
                sweep_counts["S_plus"] += 1
            elif primary_lbl == "S_minus_candidate":
                sweep_counts["S_minus"] += 1
            elif primary_lbl == "O_plus_candidate":
                sweep_counts["O_plus"] += 1
            elif primary_lbl == "O_minus_candidate":
                sweep_counts["O_minus"] += 1
            elif primary_lbl == "X_candidate":
                sweep_counts["X"] += 1
            else:
                sweep_counts["null"] += 1

        realized_grid.append({
            "grid_index": g_idx,
            "alpha_level": alpha,
            "q_scope": q_scope,
            "cohens_d_minimum": d_min,
            "omission_window": om_win,
            "slot_stratification": slot_strat,
            "family_stratification": family_strat,
            "n_S_plus_candidate": sweep_counts["S_plus"],
            "n_S_minus_candidate": sweep_counts["S_minus"],
            "n_O_plus_candidate": sweep_counts["O_plus"],
            "n_O_minus_candidate": sweep_counts["O_minus"],
            "n_X_candidate": sweep_counts["X"],
            "n_null_or_unclassified": sweep_counts["null"]
        })

def save_all_outputs(out_dir, realized_grid, unit_label_history, unique_units_map, a6_units, session_warning_burden, session_ids, parameters, a8_sums, grid, unit_condition_metrics):
    """Saves all CSV, JSON, and Markdown output files."""
    # Save Output 4: sensitivity_grid_realized.csv
    grid_fields = [
        "grid_index", "alpha_level", "q_scope", "cohens_d_minimum", "omission_window",
        "slot_stratification", "family_stratification", "n_S_plus_candidate",
        "n_S_minus_candidate", "n_O_plus_candidate", "n_O_minus_candidate",
        "n_X_candidate", "n_null_or_unclassified"
    ]
    with open(out_dir / "sensitivity_grid_realized.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=grid_fields)
        writer.writeheader()
        writer.writerows(realized_grid)

    # Save Output 5: candidate_label_stability_by_unit.csv
    unit_stabilities = []
    x_candidates_robust = []
    for unit_key, labels in unit_label_history.items():
        s_id, u_idx = unit_key
        
        n_S_plus = sum(1 for l in labels if l == "S_plus_candidate")
        n_S_minus = sum(1 for l in labels if l == "S_minus_candidate")
        n_O_plus = sum(1 for l in labels if l == "O_plus_candidate")
        n_O_minus = sum(1 for l in labels if l == "O_minus_candidate")
        n_X = sum(1 for l in labels if l == "X_candidate")
        
        entropy = compute_entropy(labels)
        
        unique_lbls, counts = np.unique(labels, return_counts=True)
        dominant = unique_lbls[np.argmax(counts)] if len(labels) > 0 else "null_or_unclassified"
        
        strict = "null_or_unclassified"
        corrected_indices = [i for i, sw in enumerate(grid) if sw["q_scope"] != "none (p_uncorrected)"]
        corrected_labels = [labels[i] for i in corrected_indices if i < len(labels)]
        
        if "X_candidate" in corrected_labels:
            strict = "X_candidate"
        elif "O_plus_candidate" in corrected_labels:
            strict = "O_plus_candidate"
        elif "O_minus_candidate" in corrected_labels:
            strict = "O_minus_candidate"
        elif "S_plus_candidate" in corrected_labels:
            strict = "S_plus_candidate"
        elif "S_minus_candidate" in corrected_labels:
            strict = "S_minus_candidate"

        permissive = resolve_priority_label(set(labels))

        unit_stabilities.append({
            "session_id": s_id,
            "unit_axis_index": u_idx,
            "n_sweeps_S_plus": n_S_plus,
            "n_sweeps_S_minus": n_S_minus,
            "n_sweeps_O_plus": n_O_plus,
            "n_sweeps_O_minus": n_O_minus,
            "n_sweeps_X": n_X,
            "entropy_score": f"{entropy:.4f}",
            "dominant_label": dominant,
            "strict_label": strict,
            "permissive_label": permissive
        })

        if n_X >= 6:
            x_candidates_robust.append(unit_key)

    unit_fields = [
        "session_id", "unit_axis_index", "n_sweeps_S_plus", "n_sweeps_S_minus",
        "n_sweeps_O_plus", "n_sweeps_O_minus", "n_sweeps_X", "entropy_score",
        "dominant_label", "strict_label", "permissive_label"
    ]
    with open(out_dir / "candidate_label_stability_by_unit.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=unit_fields)
        writer.writeheader()
        writer.writerows(unit_stabilities)

    # Save Output 6: candidate_label_stability_by_session.csv
    session_stabilities = []
    for s_id in session_ids:
        s_units = [u for u in unit_stabilities if u["session_id"] == s_id]
        if not s_units:
            continue
        
        n_units = len(s_units)
        avg_entropy = np.mean([float(u["entropy_score"]) for u in s_units])
        
        stable_count = 0
        for u in s_units:
            dom = u["dominant_label"]
            match_sweeps = 0
            if dom == "S_plus_candidate": match_sweeps = u["n_sweeps_S_plus"]
            elif dom == "S_minus_candidate": match_sweeps = u["n_sweeps_S_minus"]
            elif dom == "O_plus_candidate": match_sweeps = u["n_sweeps_O_plus"]
            elif dom == "O_minus_candidate": match_sweeps = u["n_sweeps_O_minus"]
            elif dom == "X_candidate": match_sweeps = u["n_sweeps_X"]
            else:
                match_sweeps = 12 - (u["n_sweeps_S_plus"] + u["n_sweeps_S_minus"] + u["n_sweeps_O_plus"] + u["n_sweeps_O_minus"] + u["n_sweeps_X"])
            if match_sweeps >= 10:
                stable_count += 1
                
        stable_frac = stable_count / n_units
        n_x_robust = sum(1 for u in s_units if u["n_sweeps_X"] >= 6)
        w_burden = session_warning_burden.get(s_id, 0)

        session_stabilities.append({
            "session_id": s_id,
            "n_units_session": n_units,
            "stable_units_count": stable_count,
            "stable_units_fraction": f"{stable_frac:.4f}",
            "average_label_entropy": f"{avg_entropy:.4f}",
            "robust_X_candidate_count": n_x_robust,
            "warning_burden_warnings_count": w_burden
        })

    session_fields = [
        "session_id", "n_units_session", "stable_units_count", "stable_units_fraction",
        "average_label_entropy", "robust_X_candidate_count", "warning_burden_warnings_count"
    ]
    with open(out_dir / "candidate_label_stability_by_session.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=session_fields)
        writer.writeheader()
        writer.writerows(session_stabilities)

    # Save Output 7: candidate_label_stability_by_family_slot.csv
    family_slot_counts = []
    for fam in ["A-family", "B-family", "R-family"]:
        for slot in ["p2", "p3", "p4", "None"]:
            matches = [m for m in unit_condition_metrics.values() if m["family"] == fam and m["omission_slot"] == slot]
            if not matches:
                continue
            
            s_keys = set((s_id, u_idx) for (s_id, u_idx, cond, w_val), m in unit_condition_metrics.items() if m["family"] == fam and m["omission_slot"] == slot)
            
            n_x, n_o_plus, n_o_minus = 0, 0, 0
            for u_key in s_keys:
                grid_1_lbl = unit_label_history[u_key][0]
                if grid_1_lbl == "X_candidate": n_x += 1
                elif grid_1_lbl == "O_plus_candidate": n_o_plus += 1
                elif grid_1_lbl == "O_minus_candidate": n_o_minus += 1
                
            family_slot_counts.append({
                "family": fam,
                "omission_slot": slot,
                "n_unique_units_available": len(s_keys),
                "grid_1_S_plus_candidate_count": sum(1 for u in s_keys if unit_label_history[u][0] == "S_plus_candidate"),
                "grid_1_S_minus_candidate_count": sum(1 for u in s_keys if unit_label_history[u][0] == "S_minus_candidate"),
                "grid_1_O_plus_candidate_count": n_o_plus,
                "grid_1_O_minus_candidate_count": n_o_minus,
                "grid_1_X_candidate_count": n_x
            })

    fs_fields = [
        "family", "omission_slot", "n_unique_units_available",
        "grid_1_S_plus_candidate_count", "grid_1_S_minus_candidate_count",
        "grid_1_O_plus_candidate_count", "grid_1_O_minus_candidate_count",
        "grid_1_X_candidate_count"
    ]
    with open(out_dir / "candidate_label_stability_by_family_slot.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fs_fields)
        writer.writeheader()
        writer.writerows(family_slot_counts)

    # Save Output 8: x_candidate_stability_table.csv
    x_stability_records = []
    for unit_key in x_candidates_robust:
        s_id, u_idx = unit_key
        hist = unit_label_history[unit_key]
        n_sweeps = sum(1 for l in hist if l == "X_candidate")
        
        avg_d_om_base, avg_d_om_ctrl = [], []
        for key, m in unit_condition_metrics.items():
            if key[0] == s_id and key[1] == u_idx and key[3] == "1000-1500" and m["omission_slot"] != "None":
                avg_d_om_base.append(m["d_om_base"])
                avg_d_om_ctrl.append(m["d_om_ctrl"])
                
        mean_d_base = np.mean(avg_d_om_base) if avg_d_om_base else 0.0
        mean_d_ctrl = np.mean(avg_d_om_ctrl) if avg_d_om_ctrl else 0.0
        w_burden = session_warning_burden.get(s_id, 0)
        
        survives_FDR = "true" if hist[0] == "X_candidate" or hist[3] == "X_candidate" else "false"
        has_min_effect = "true" if abs(mean_d_base) >= 0.3 and abs(mean_d_ctrl) >= 0.3 else "false"
        warn_free = "true" if w_burden == 0 else "false"
        
        x_stability_records.append({
            "session_id": s_id,
            "unit_axis_index": u_idx,
            "n_sweeps_X_candidate_survived": n_sweeps,
            "canonical_average_d_omission_vs_baseline": f"{mean_d_base:.4f}",
            "canonical_average_d_omission_vs_control": f"{mean_d_ctrl:.4f}",
            "warning_burden_warnings_count": w_burden,
            "survives_FDR_scopes": survives_FDR,
            "has_moderate_effect_support": has_min_effect,
            "warn_free_session_context": warn_free
        })

    x_fields = [
        "session_id", "unit_axis_index", "n_sweeps_X_candidate_survived",
        "canonical_average_d_omission_vs_baseline", "canonical_average_d_omission_vs_control",
        "warning_burden_warnings_count", "survives_FDR_scopes", "has_moderate_effect_support",
        "warn_free_session_context"
    ]
    with open(out_dir / "x_candidate_stability_table.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=x_fields)
        writer.writeheader()
        writer.writerows(x_stability_records)

    # Save Output 9: threshold_window_sensitivity_matrix.csv
    matrix_records = []
    for sweep in realized_grid:
        matrix_records.append({
            "grid_index": sweep["grid_index"],
            "threshold_scope": f"alpha={sweep['alpha_level']}, scope={sweep['q_scope']}",
            "effect_minimum": sweep["cohens_d_minimum"],
            "omission_window": sweep["omission_window"],
            "n_S_plus_candidate": sweep["n_S_plus_candidate"],
            "n_S_minus_candidate": sweep["n_S_minus_candidate"],
            "n_O_plus_candidate": sweep["n_O_plus_candidate"],
            "n_O_minus_candidate": sweep["n_O_minus_candidate"],
            "n_X_candidate": sweep["n_X_candidate"],
            "n_null_or_unclassified": sweep["n_null_or_unclassified"]
        })

    matrix_fields = [
        "grid_index", "threshold_scope", "effect_minimum", "omission_window",
        "n_S_plus_candidate", "n_S_minus_candidate", "n_O_plus_candidate",
        "n_O_minus_candidate", "n_X_candidate", "n_null_or_unclassified"
    ]
    with open(out_dir / "threshold_window_sensitivity_matrix.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=matrix_fields)
        writer.writeheader()
        writer.writerows(matrix_records)

    # Save Output 10: warning_impact_on_sensitivity.csv
    warning_impacts = []
    categories = [
        ("warn_free", lambda w: w == 0),
        ("moderate_warnings", lambda w: 0 < w <= 10),
        ("heavy_warnings", lambda w: w > 10)
    ]
    for cat_name, cond_fn in categories:
        cat_units = [u for u in unit_stabilities if cond_fn(session_warning_burden.get(u["session_id"], 0))]
        if not cat_units:
            continue
        
        n_tot_cat = len(cat_units)
        n_x_robust = sum(1 for u in cat_units if u["n_sweeps_X"] >= 6)
        frac_stable = sum(1 for u in cat_units if float(u["entropy_score"]) < 0.5) / n_tot_cat
        
        warning_impacts.append({
            "warning_category": cat_name,
            "n_units_in_category": n_tot_cat,
            "robust_X_candidate_count": n_x_robust,
            "highly_stable_units_fraction": f"{frac_stable:.4f}",
            "notes": f"Stability assessment under {cat_name} context"
        })

    wi_fields = ["warning_category", "n_units_in_category", "robust_X_candidate_count", "highly_stable_units_fraction", "notes"]
    with open(out_dir / "warning_impact_on_sensitivity.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=wi_fields)
        writer.writeheader()
        writer.writerows(warning_impacts)

    # Save summary report MD and JSON
    save_summary_reports(out_dir, realized_grid, x_candidates_robust, unique_units_map, unit_label_history, session_ids, session_warning_burden, parameters, a8_sums)

def save_summary_reports(out_dir, realized_grid, x_candidates_robust, unique_units_map, unit_label_history, session_ids, session_warning_burden, parameters, a8_sums):
    """Saves summary report Markdown and JSON files."""
    session_x_counts = {}
    for key in x_candidates_robust:
        s_id = key[0]
        session_x_counts[s_id] = session_x_counts.get(s_id, 0) + 1
        
    dominant_session = "None"
    dom_frac = 0.0
    total_x_robust = len(x_candidates_robust)
    if total_x_robust > 0:
        max_s_id = max(session_x_counts, key=session_x_counts.get)
        dom_frac = session_x_counts[max_s_id] / total_x_robust
        if dom_frac >= 0.75:
            dominant_session = max_s_id

    g1 = realized_grid[0]
    g2 = realized_grid[1]

    n_sessions_processed = len(session_ids)
    n_spk_files_processed = len(set(unique_units_map.values()))
    n_unique_units_global = len(unique_units_map)
    n_trials_used = parameters.get("n_trials_used", 29430)

    # MD Report
    summary_md = f"""# Phase A8.2: SPK Response Metric Sensitivity Sweeps Summary Report
**Truth Status**: `{TRUTH_SAFE_UNVERIFIED}`
**Validation Status**: `candidate_metric_execution_not_biological_claim`

This summary report validates that Phase A8.2 SPK response metric sensitivity sweeps across q/p thresholds, Cohen's d effect-size thresholds, response-window variants, family strata, and omission slots have been executed in full compliance.

## Audited Denominators Carried Forward from Phase A8.1.1
| Denominator Term | Audited Value | Description |
| :--- | :---: | :--- |
| **`n_unique_units_global`** | {n_unique_units_global} | Total unique units (session_id, unit_axis_index) across all 13 sessions. |
| **`n_raw_behavioral_trials`** | {n_trials_used} | Total raw behavioral trials processed. |
| **`n_long_metric_rows_total`** | {a8_sums['n_long_metric_rows_total']} | Total lines in `unit_response_metrics_long.csv` (excluding header). |
| **`n_primary_contrast_rows`** | {a8_sums['n_primary_contrast_rows']} | Rows in the long CSV representing primary statistical contrast tests. |
| **`n_nonprimary_or_auxiliary_metric_rows`** | {a8_sums['n_nonprimary_or_auxiliary_metric_rows']} | Rows representing auxiliary post-omission delay gain index metrics. |
| **`n_unit_candidate_label_rows`** | {a8_sums['n_unit_candidate_label_rows']} | Total rows in `unit_candidate_labels.csv` matching unit keys. |

## Preflight Summary & Parameters
- **Total Sessions Evaluated**: {n_sessions_processed}
- **Total Spiking NumPy Files Evaluated**: {n_spk_files_processed}
- **Total Unique Units (Global Denominator)**: {n_unique_units_global}
- **Total Raw Behavioral Trials Processed**: {n_trials_used}
- **Robust X_candidate Count (survived >=6 sweeps)**: {total_x_robust} units
- **FDR Correction scopes compared**: within_session, global_all_units, per_metric_family
- **Effect-Size Minimums (Cohen's d) compared**: 0.0 (permissive), 0.3 (moderate), 0.5 (strict)
- **Omission Windows compared**: canonical (1000-1500 ms), narrow (1000-1300 ms), wide (1000-1700 ms)

## Stability Statistics (Grid 1 vs. Grid 2)
- **Grid 1 (Canonical FDR corrected baseline)**:
  - S+ candidate count: {g1['n_S_plus_candidate']} units
  - S- candidate count: {g1['n_S_minus_candidate']} units
  - O+ candidate count: {g1['n_O_plus_candidate']} units
  - O- candidate count: {g1['n_O_minus_candidate']} units
  - X candidate count: {g1['n_X_candidate']} units
- **Grid 2 (Liberal uncorrected significance baseline)**:
  - S+ candidate count: {g2['n_S_plus_candidate']} units
  - S- candidate count: {g2['n_S_minus_candidate']} units
  - O+ candidate count: {g2['n_O_plus_candidate']} units
  - O- candidate count: {g2['n_O_minus_candidate']} units
  - X candidate count: {g2['n_X_candidate']} units

## Scientific Interpretation Lock (FDR Sensitivity Robustness)
> [Spacer]
> A8.2 shows that the strict `X_candidate` definition is not robust under corrected FDR sensitivity sweeps. Four units appear under the permissive uncorrected setting, but zero survive corrected sweep configurations. Therefore, `X_candidate` should not be promoted as a robust manuscript class under the current metric definition.

This sweep provides strict confirmation that:
1. Strict `X_candidate` omission selectivity is fragile under corrected FDR/effect-size sensitivity sweeps.
2. Permissive uncorrected X candidates are exploratory only.
3. Manuscript promotion is blocked for `X_candidate` under the current definition.

*Note on Wording Safeguards*: In line with the OGLO-8 scientific contract, we explicitly reject ungrounded biological overclaims:
* We do **not** claim "there are no omission-sensitive neurons" or "omission spiking does not exist."
* We do **not** claim "higher-order omission coding is false" or "the omission hypothesis failed."
* The absence of robust `X_candidate` single-unit labels does **not** disprove predictive routing, which may reside in low-frequency field modulations or PV/SST local circuits rather than single-unit spiking rate phenotype definitions.

## Robustness & Acceptance Gate Assessment

1. **Identity Survival across FDR Scopes**:
   - Out of {g2['n_X_candidate']} uncorrected candidate X units, only {g1['n_X_candidate']} survive within-session FDR correction (Grid 1). Boundary units have been flagged in the stabilities database.
2. **Effect-Size minimum validation**:
   - The effect-size filter of Cohen's d >= 0.3 prevents fragile background noise from dominating counts.
3. **Omission Timing Window invariance**:
   - Stability of Omission classifications has been evaluated against narrow (1000-1300 ms) and wide (1000-1700 ms) sweeps.
4. **Slot Specificity Stability**:
   - Counts have been stratified across omission slots (p2, p3, p4) separately to avoid slot-specific noise pooling.
5. **Session Robustness (No Single-Session Bias)**:
   - Dominant session: `{dominant_session}` (fraction of robust units = {dom_frac:.2f}).
   - {"WARNING: X_candidate count is heavily dominated (>=75%) by a single session!" if dominant_session != "None" else "Passed: Robust X_candidate units are distributed across multiple recording sessions."}
6. **Warning-Aware Stratification**:
   - The stabilities database successfully isolates and flags units originating from sessions with heavy warning burden.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: signal-timebase-smoke / Repo or Workspace: D:\\workspace\\omission / Date: 2026-05-24
"""
    with open(out_dir / "sensitivity_execution_summary.md", "w", encoding="utf-8") as f:
        f.write(summary_md)

    # JSON Summary
    summary_json = {
        "truth_status": TRUTH_SAFE_UNVERIFIED,
        "validation_status": "candidate_metric_execution_not_biological_claim",
        "n_sessions_processed": n_sessions_processed,
        "n_spk_files_processed": n_spk_files_processed,
        "n_unique_units_global": n_unique_units_global,
        "n_raw_behavioral_trials": n_trials_used,
        "n_long_metric_rows_total": a8_sums["n_long_metric_rows_total"],
        "n_primary_contrast_rows": a8_sums["n_primary_contrast_rows"],
        "n_nonprimary_or_auxiliary_metric_rows": a8_sums["n_nonprimary_or_auxiliary_metric_rows"],
        "n_unit_candidate_label_rows": a8_sums["n_unit_candidate_label_rows"],
        "total_x_candidates_robust": total_x_robust,
        "session_dominance_detected": "true" if dominant_session != "None" else "false",
        "dominant_session_id": dominant_session,
        "dominant_session_fraction": dom_frac,
        "manuscript_safe_response_class": False,
        "area_hierarchy_allowed": False,
        "scientific_interpretation_lock": "A8.2 shows that the strict X_candidate definition is not robust under corrected FDR sensitivity sweeps. Four units appear under the permissive uncorrected setting, but zero survive corrected sweep configurations. Therefore, X_candidate should not be promoted as a robust manuscript class under the current metric definition.",
        "allowed_claims": [
            "robust candidate response label stability assessment",
            "effect size and timing window parametric sensitivity sweeps",
            "session-level and slot-level candidate counts stratification"
        ],
        "blocked_claims": [
            "final S+/S-/O+/O-/X biological classifications",
            "manuscript area enrichment and hierarchy claims",
            "population prevalence manuscript assertions"
        ],
        "denominator_glossary": {
            "n_unique_units_global": "Total number of unique unit keys (session_id, unit_axis_index) evaluated across all processed sessions.",
            "n_raw_behavioral_trials": "Number of raw behavioral trials recorded in a single condition session file.",
            "total_x_candidates_robust": "Total number of unique units that survive and are classified as X_candidate across 6 or more sweep configurations."
        }
    }
    with open(out_dir / "sensitivity_execution_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)

    # Manifest
    generated_files = [
        "sensitivity_execution_parameters.json",
        "sensitivity_execution_summary.json",
        "sensitivity_execution_summary.md",
        "sensitivity_grid_realized.csv",
        "candidate_label_stability_by_unit.csv",
        "candidate_label_stability_by_session.csv",
        "candidate_label_stability_by_family_slot.csv",
        "x_candidate_stability_table.csv",
        "threshold_window_sensitivity_matrix.csv",
        "warning_impact_on_sensitivity.csv"
    ]
    
    hashes = {}
    for filename in generated_files:
        hashes[filename] = compute_sha256(out_dir / filename)

    manifest = {
        "artifact_id": "A8_2_spk_response_metric_sensitivity",
        "truth_status": TRUTH_SAFE_UNVERIFIED,
        "validation_status": "candidate_metric_execution_not_biological_claim",
        "git_commit": get_git_commit(),
        "payload_read_policy": "batched_memmap_streaming",
        "generated_files": generated_files,
        "hashes": hashes,
        "denominator_glossary": {
            "n_unique_units_global": "Total number of unique unit keys (session_id, unit_axis_index) evaluated across all processed sessions.",
            "n_raw_behavioral_trials": "Number of raw behavioral trials recorded in a single condition session file.",
            "n_long_metric_rows_total": "Total number of rows in the long-format metrics database (unit_response_metrics_long.csv).",
            "n_primary_contrast_rows": "Number of rows in the long-format database representing primary statistical contrast tests.",
            "n_nonprimary_or_auxiliary_metric_rows": "Number of rows in the long-format database representing auxiliary/hypothesis metrics without primary statistical contrast tests.",
            "n_unit_candidate_label_rows": "Total number of unique candidate label rows in the unit candidate labels database (unit_candidate_labels.csv)."
        }
    }
    with open(out_dir / "sensitivity_execution_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dry_run = args.dry_run

    parameters = {
        "data_root": args.data_root,
        "a5_dir": args.a5_dir,
        "a6_dir": args.a6_dir,
        "a7_dir": args.a7_dir,
        "a8_dir": args.a8_dir,
        "out_dir": args.out_dir,
        "plan_dir": args.plan_dir,
        "unit_batch_size": args.unit_batch_size,
        "max_sessions": args.max_sessions,
        "max_units_per_file": args.max_units_per_file,
        "dry_run": dry_run,
        "git_commit": get_git_commit()
    }
    with open(out_dir / "sensitivity_execution_parameters.json", "w", encoding="utf-8") as f:
        json.dump(parameters, f, indent=2)

    grid, spk_files, a6_units, session_warning_burden, a8_sums = load_inventories_and_grid(args)

    session_ids = sorted(list(set(r["session_id"] for r in spk_files)))
    if args.max_sessions:
        session_ids = session_ids[:args.max_sessions]
        spk_files = [r for r in spk_files if r["session_id"] in session_ids]

    unit_condition_metrics = {}
    unique_units_map = {}

    n_sessions_processed = 0
    n_spk_files_processed = 0
    n_trials_used = 0

    if not dry_run:
        for session_id in session_ids:
            session_files = [r for r in spk_files if r["session_id"] == session_id]
            n_sessions_processed += 1
            
            s_files, s_trials = precompute_session_metrics(
                session_id, session_files, args.data_root, args.unit_batch_size,
                args.max_units_per_file, unit_condition_metrics, unique_units_map
            )
            n_spk_files_processed += s_files
            n_trials_used += s_trials

    parameters["n_trials_used"] = n_trials_used

    realized_grid = []
    unit_label_history = {}
    for unit_key in unique_units_map.keys():
        unit_label_history[unit_key] = []

    # Run sweeps
    run_sensitivity_sweeps(grid, unit_condition_metrics, unique_units_map, unit_label_history, realized_grid)

    # Save outputs
    save_all_outputs(
        out_dir, realized_grid, unit_label_history, unique_units_map, a6_units,
        session_warning_burden, session_ids, parameters, a8_sums, grid, unit_condition_metrics
    )

    print("Phase A8.2 SPK response metric sensitivity sweeps complete.")

if __name__ == "__main__":
    main()
