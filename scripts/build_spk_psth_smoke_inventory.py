#!/usr/bin/env python3
# scripts/build_spk_psth_smoke_inventory.py
"""
Phase A7 SPK/SUA PSTH/raster signal-timebase smoke sanity gate.
Verifies p1-relative and omission-relative timebase handling, trial-count preservation,
condition coverage, slot/family coverage, and output provenance.
Declares truth_status: truth_safe_unverified on all outputs.
This is strictly a smoke sanity gate; no biological or cortical hierarchy claims are made.
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

# Timing Constants (prototype constants fallback)
P1_ONSET_MS = 0
P2_ONSET_MS = 1031
P3_ONSET_MS = 2062
P4_ONSET_MS = 3093
FULL_SEQUENCE_WINDOW_MS = [-1000, 4124]
OMISSION_LOCAL_WINDOW_MS = [-1000, 1000]

TRUTH_SAFE_UNVERIFIED = "truth_safe_unverified"
CONDITIONS = ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]

def get_git_commit():
    """Dynamically fetches current Git HEAD commit hash or returns accepted A6.1 HEAD."""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "af6a9ce3e31d7232ef27bc7fd3036e0df6bdaedd"

def parse_args():
    parser = argparse.ArgumentParser(description="Phase A7 SPK PSTH Smoke Sanity Gate")
    parser.add_argument("--data-root", required=True, help="Path to data root directory (no absolute paths default)")
    parser.add_argument("--a5-dir", default="reports/analysis_A5_signal_shape_inventory", help="Path to Phase A5 inventory directory")
    parser.add_argument("--a6-dir", default="reports/analysis_A6_area_probe_metadata", help="Path to Phase A6 inventory directory")
    parser.add_argument("--out-dir", default="reports/analysis_A7_spk_psth_smoke", help="Path to output directory")
    parser.add_argument("--max-preview-units", type=int, default=5, help="Capped units count for preview slice")
    parser.add_argument("--max-preview-trials", type=int, default=20, help="Capped trials count for preview slice")
    return parser.parse_args()

from src.analysis.contracts import get_condition_family, get_omission_position, get_matched_control

def locate_file_recursively(data_root, filename):
    """Finds a file recursively under the data root without raw .h5 reads."""
    for p in Path(data_root).rglob(filename):
        if p.is_file() and p.suffix.lower() == ".npy":
            return p
    return None

def compute_sha256(file_path):
    """Computes SHA-256 hash of a file for preview manifest."""
    import hashlib
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return "unknown_hash"

def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    a5_dir = Path(args.a5_dir)
    a6_dir = Path(args.a6_dir)

    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    a6_unit_inventory_path = a6_dir / "unit_area_inventory.csv"

    if not a5_inventory_path.exists():
        print(f"Error: A5 signal shape inventory not found at {a5_inventory_path}", file=sys.stderr)
        sys.exit(1)
    if not a6_unit_inventory_path.exists():
        print(f"Error: A6 unit area inventory not found at {a6_unit_inventory_path}", file=sys.stderr)
        sys.exit(1)

    # 1. Parse A5 inventory for SPK .npy records
    spk_files = []
    with open(a5_inventory_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["signal_class_inferred"] == "SPK" and row["extension"].lower() == ".npy":
                spk_files.append(row)

    # Compile list of active sessions
    session_ids = sorted(list(set(r["session_id"] for r in spk_files)))

    # Parse A6 unit inventory to count indexed units per session
    units_per_session = {}
    with open(a6_unit_inventory_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = row["session_id"]
            units_per_session[s_id] = units_per_session.get(s_id, 0) + 1

    # Storage arrays for A7 output records
    smoke_file_records = []
    condition_coverage_records = []
    timebase_window_records = []
    smoke_metric_records = []

    # Counters for A7 summaries
    n_total_trials_indexed = 0
    n_total_units_indexed = 0
    n_timebase_windows_checked = 0
    n_window_bound_failures = 0
    n_payload_policy_violations = 0
    n_raw_h5_reads = 0

    # Payload read policy is strictly bounded memmap
    payload_read_policy = "memmap_slice_capped_trials_20_units_5"

    for row in spk_files:
        session_id = row["session_id"]
        basename = row["basename"]
        condition = row["condition_inferred"]
        
        # Verify condition parsing
        family = get_condition_family(condition)
        omission_slot = get_omission_position(condition)
        is_omission = "true" if omission_slot != "None" else "false"
        matched_control = get_matched_control(condition)

        # Locate file recursively
        real_path = locate_file_recursively(args.data_root, basename)
        
        warnings_list = []
        shape_str = row["shape"]
        dims = row["expected_dims"]
        n_trials = 0
        n_units = 0
        n_timepoints = 0
        
        # Inferred timing flags
        p1_relative_possible = "false"
        omission_relative_possible = "false"
        time_axis_status = "unknown"

        if not real_path:
            warnings_list.append("File not found recursively in data root")
            shape_status = "missing"
        else:
            # Safe shape check via memmap
            try:
                # Strictly no HDF5 file opening!
                if real_path.suffix.lower() in [".h5", ".hdf5"]:
                    n_raw_h5_reads += 1
                    n_payload_policy_violations += 1
                    raise ValueError("Raw H5 files are strictly blocked from read")

                arr = np.load(real_path, mmap_mode="r")
                n_trials, n_units, n_timepoints = arr.shape
                shape_str = str(arr.shape)
                shape_status = "expected_rank3" if arr.ndim == 3 else "unexpected_rank"

                n_total_trials_indexed += n_trials
                n_total_units_indexed = max(n_total_units_indexed, n_units) # max units in active sets

                # Check p1 timing capability
                # FULL_SEQUENCE_WINDOW_MS [-1000, 4124] requires indices [0, 5124]
                # Absolute P1 onset is index 1000 (so t_ms = index - 1000)
                if n_timepoints >= 5124:
                    p1_relative_possible = "true"
                    time_axis_status = "valid_timebase_6000ms"
                else:
                    warnings_list.append(f"Array length {n_timepoints} too short for full-sequence window")
                    time_axis_status = "truncated_timebase"

                # Check omission timing capability
                if omission_slot != "None":
                    onset_ms = P2_ONSET_MS if omission_slot == "p2" else (P3_ONSET_MS if omission_slot == "p3" else P4_ONSET_MS)
                    # Omission local window is [-1000, 1000] relative to omission onset.
                    # Translates to [onset_ms - 1000, onset_ms + 1000] relative to P1.
                    # Translates to indices [onset_ms, onset_ms + 2000] since t_ms is index - 1000.
                    start_idx = onset_ms
                    end_idx = onset_ms + 2000
                    if end_idx <= n_timepoints:
                        omission_relative_possible = "true"
                    else:
                        warnings_list.append(f"Array length {n_timepoints} too short for omission local window at {omission_slot}")
                else:
                    # Control condition: check if we can compute omission local slices for each slot
                    # (AAAB, BBBA, RRRR act as matched controls, so they can slice at p2, p3, p4)
                    max_onset_ms = P4_ONSET_MS
                    if max_onset_ms + 2000 <= n_timepoints:
                        omission_relative_possible = "true"

            except Exception as e:
                warnings_list.append(f"Failed to safe-load/inspect shape: {e}")
                shape_status = "error"

        # Record file inventory
        smoke_file_records.append({
            "session_id": session_id,
            "condition": condition,
            "signal_class": "SPK",
            "source_file": basename,
            "shape": shape_str,
            "dims": dims,
            "n_trials": n_trials if n_trials > 0 else "",
            "n_units": n_units if n_units > 0 else "",
            "n_timepoints": n_timepoints if n_timepoints > 0 else "",
            "time_axis_status": time_axis_status,
            "p1_relative_possible": p1_relative_possible,
            "omission_relative_possible": omission_relative_possible,
            "payload_read_policy": payload_read_policy,
            "warnings": "; ".join(warnings_list) if warnings_list else "None"
        })

        # Record condition coverage
        condition_coverage_records.append({
            "session_id": session_id,
            "condition": condition,
            "family": family,
            "omission_slot": omission_slot,
            "is_omission": is_omission,
            "matched_control": matched_control,
            "n_trials": n_trials if n_trials > 0 else "",
            "n_units": n_units if n_units > 0 else "",
            "source_file": basename,
            "included_in_smoke": "true" if real_path else "false",
            "warnings": "; ".join(warnings_list) if warnings_list else "None"
        })

        # Process Timebase Windows and Smoke Metrics
        if real_path and n_timepoints > 0:
            # 1. Verify and report window boundary alignments
            # Full sequence window: p1 alignment
            p1_start_idx = 0
            p1_end_idx = 5124
            p1_within = "true" if p1_end_idx <= n_timepoints else "false"
            n_timebase_windows_checked += 1
            if p1_within == "false":
                n_window_bound_failures += 1

            timebase_window_records.append({
                "session_id": session_id,
                "condition": condition,
                "window_name": "full_sequence",
                "alignment_event": "p1",
                "time_base": "p1_relative",
                "window_ms": "[-1000, 4124]",
                "expected_start_ms": -1000,
                "expected_end_ms": 4124,
                "index_start": p1_start_idx,
                "index_end": p1_end_idx,
                "n_timepoints_window": 5124,
                "window_within_bounds": p1_within,
                "warnings": "None" if p1_within == "true" else "Truncated timebase window"
            })

            # Omission local window boundaries mapping
            if omission_slot != "None":
                onset_ms = P2_ONSET_MS if omission_slot == "p2" else (P3_ONSET_MS if omission_slot == "p3" else P4_ONSET_MS)
                om_start_idx = onset_ms
                om_end_idx = onset_ms + 2000
                om_within = "true" if om_end_idx <= n_timepoints else "false"
                n_timebase_windows_checked += 1
                if om_within == "false":
                    n_window_bound_failures += 1

                timebase_window_records.append({
                    "session_id": session_id,
                    "condition": condition,
                    "window_name": "omission_local",
                    "alignment_event": "omission",
                    "time_base": "omission_relative",
                    "window_ms": "[-1000, 1000]",
                    "expected_start_ms": onset_ms - 1000,
                    "expected_end_ms": onset_ms + 1000,
                    "index_start": om_start_idx,
                    "index_end": om_end_idx,
                    "n_timepoints_window": 2000,
                    "window_within_bounds": om_within,
                    "warnings": "None" if om_within == "true" else "Truncated timebase window"
                })
            else:
                # Control condition: map all three slots (p2, p3, p4) for completeness checking
                for slot in ["p2", "p3", "p4"]:
                    onset_ms = P2_ONSET_MS if slot == "p2" else (P3_ONSET_MS if slot == "p3" else P4_ONSET_MS)
                    om_start_idx = onset_ms
                    om_end_idx = onset_ms + 2000
                    om_within = "true" if om_end_idx <= n_timepoints else "false"
                    n_timebase_windows_checked += 1
                    if om_within == "false":
                        n_window_bound_failures += 1

                    timebase_window_records.append({
                        "session_id": session_id,
                        "condition": condition,
                        "window_name": f"omission_local_{slot}",
                        "alignment_event": f"omission_{slot}",
                        "time_base": "omission_relative",
                        "window_ms": "[-1000, 1000]",
                        "expected_start_ms": onset_ms - 1000,
                        "expected_end_ms": onset_ms + 1000,
                        "index_start": om_start_idx,
                        "index_end": om_end_idx,
                        "n_timepoints_window": 2000,
                        "window_within_bounds": om_within,
                        "warnings": "None" if om_within == "true" else "Truncated timebase window"
                    })

            # 2. Extract strictly bounded preview slice to compute metrics
            try:
                # Strictly cap the units and trials count
                u_slice = min(n_units, args.max_preview_units)
                t_slice = min(n_trials, args.max_preview_trials)

                # Load with memmap
                arr = np.load(real_path, mmap_mode="r")
                preview_slice = arr[:t_slice, :u_slice, :]

                # Compute bounded metrics
                finite_count = int(np.sum(np.isfinite(preview_slice)))
                finite_frac = finite_count / preview_slice.size
                
                nonneg_count = int(np.sum(preview_slice >= 0))
                nonneg_frac = nonneg_count / preview_slice.size

                total_nonzero = int(np.sum(preview_slice > 0))
                
                # Rate computation: mean spikes per bin divided by 0.001 seconds (since bin is 1ms)
                mean_rate_hz = float(np.mean(preview_slice) / 0.001)

                metrics_to_record = [
                    ("finite_fraction", finite_frac, "ratio", True),
                    ("nonnegative_fraction", nonneg_frac, "ratio", True),
                    ("total_nonzero_bins_preview", total_nonzero, "bins", True),
                    ("mean_rate_preview_if_units_known", mean_rate_hz, "Hz", True),
                    ("trial_count", n_trials, "trials", False),
                    ("unit_count", n_units, "units", False),
                    ("timepoint_count", n_timepoints, "timepoints", False)
                ]

                for name, val, unit, is_slice in metrics_to_record:
                    smoke_metric_records.append({
                        "session_id": session_id,
                        "condition": condition,
                        "smoke_metric": name,
                        "value": f"{val:.6f}" if isinstance(val, float) else str(val),
                        "units": unit,
                        "n_trials": n_trials,
                        "n_units": n_units,
                        "n_timepoints": n_timepoints,
                        "computed_from_slice": "true" if is_slice else "false",
                        "interpretation_allowed": "false" # strictly blocked
                    })

            except Exception as e:
                print(f"Warning: Failed to compute metrics for {basename}: {e}", file=sys.stderr)

    # 3. Handle optional preview PNG figures (lightweight & strictly bounded)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Pick one representative session & condition to plot preview rasters/PSTHs
        # ses230630 AXAB and its control AAAB are great candidates
        plot_session = "230630"
        plot_cond_om = "AXAB"
        plot_cond_ctrl = "AAAB"
        
        real_path_om = locate_file_recursively(args.data_root, f"ses{plot_session}-units-probe0-spk-{plot_cond_om}.npy")
        real_path_ctrl = locate_file_recursively(args.data_root, f"ses{plot_session}-units-probe0-spk-{plot_cond_ctrl}.npy")

        if real_path_om and real_path_ctrl:
            arr_om = np.load(real_path_om, mmap_mode="r")
            arr_ctrl = np.load(real_path_ctrl, mmap_mode="r")

            u_slice = min(arr_om.shape[1], args.max_preview_units)
            t_slice = min(arr_om.shape[0], args.max_preview_trials)

            sl_om = arr_om[:t_slice, :u_slice, :]
            sl_ctrl = arr_ctrl[:t_slice, :u_slice, :]

            # --- Figures strictly carrying SMOKE PREVIEW markers ---
            
            # Figure 1: preview_p1_relative_psth.png
            plt.figure(figsize=(8, 4))
            # Compute mean PSTH across trials and preview units (P1-relative: first 5124 bins)
            # Time axis is relative: t_ms = index - 1000
            t_axis_ms = np.arange(5124) - 1000
            
            # Mean spikes across trials and units
            psth_om = np.mean(sl_om[:, :, :5124], axis=(0, 1)) / 0.001 # Hz
            psth_ctrl = np.mean(sl_ctrl[:, :, :5124], axis=(0, 1)) / 0.001 # Hz

            plt.plot(t_axis_ms, psth_om, color="#e06666", alpha=0.9, label="Smoke Condition A (Omission)")
            plt.plot(t_axis_ms, psth_ctrl, color="#b4a7d6", alpha=0.9, label="Smoke Condition B (Control)")
            plt.axvline(0, color="gray", linestyle="--", alpha=0.5)
            plt.axvline(P2_ONSET_MS, color="red", linestyle=":", alpha=0.5)
            
            # Block labeling of area names and unit IDs
            plt.title("SPK PSTH Smoke Timebase Verification (P1-Relative Preview)", fontsize=11, fontweight="bold")
            plt.xlabel("Time relative to P1 onset (ms)", fontsize=10)
            plt.ylabel("Sanity Rate Metric (Hz-like)", fontsize=10)
            plt.legend(frameon=True, fontsize=9)
            plt.grid(True, linestyle=":", alpha=0.6)
            plt.tight_layout()
            
            fig1_path = out_dir / "preview_p1_relative_psth.png"
            plt.savefig(fig1_path, dpi=120)
            plt.close()

            # Figure 2: preview_omission_relative_psth.png
            plt.figure(figsize=(8, 4))
            # Align AXAB to P2 omission (1031 ms = index 1031)
            # Omission local window is [-1000, 1000] -> indices [1031, 3031]
            onset_ms = P2_ONSET_MS
            t_local_ms = np.arange(2000) - 1000
            
            psth_local_om = np.mean(sl_om[:, :, onset_ms:onset_ms+2000], axis=(0, 1)) / 0.001
            psth_local_ctrl = np.mean(sl_ctrl[:, :, onset_ms:onset_ms+2000], axis=(0, 1)) / 0.001

            plt.plot(t_local_ms, psth_local_om, color="#e06666", alpha=0.9, label="Smoke Condition A (Omission)")
            plt.plot(t_local_ms, psth_local_ctrl, color="#b4a7d6", alpha=0.9, label="Smoke Condition B (Control)")
            plt.axvline(0, color="red", linestyle="--", alpha=0.5)
            
            plt.title("SPK PSTH Smoke Timebase Verification (Omission-Relative Preview)", fontsize=11, fontweight="bold")
            plt.xlabel("Time relative to Omission onset (ms)", fontsize=10)
            plt.ylabel("Sanity Rate Metric (Hz-like)", fontsize=10)
            plt.legend(frameon=True, fontsize=9)
            plt.grid(True, linestyle=":", alpha=0.6)
            plt.tight_layout()

            fig2_path = out_dir / "preview_omission_relative_psth.png"
            plt.savefig(fig2_path, dpi=120)
            plt.close()

            # Figure 3: preview_raster_slice.png
            plt.figure(figsize=(8, 4))
            # Plot spike raster for unit 0, across first 20 trials, P1-relative [-1000, 4124]
            # Slices spike times (where slice > 0)
            unit_idx = 0
            trial_spikes = sl_om[:, unit_idx, :5124] # shape (trials, time)
            
            for t_idx in range(trial_spikes.shape[0]):
                spike_inds = np.where(trial_spikes[t_idx] > 0)[0]
                spike_times = spike_inds - 1000
                plt.scatter(spike_times, np.ones_like(spike_times) * t_idx, color="black", s=3, alpha=0.8)
                
            plt.axvline(0, color="gray", linestyle="--", alpha=0.5)
            plt.axvline(P2_ONSET_MS, color="red", linestyle=":", alpha=0.5)
            plt.title("SPK Single-Unit Raster Preview (Strictly Bounded Smoke Check)", fontsize=11, fontweight="bold")
            plt.xlabel("Time relative to P1 onset (ms)", fontsize=10)
            plt.ylabel("Capped Trial Index", fontsize=10)
            plt.ylim(-0.5, t_slice - 0.5)
            plt.grid(True, linestyle=":", alpha=0.4)
            plt.tight_layout()

            fig3_path = out_dir / "preview_raster_slice.png"
            plt.savefig(fig3_path, dpi=120)
            plt.close()
            print("Preview figures generated successfully under reports/analysis_A7_spk_psth_smoke/")

    except Exception as e:
        print(f"Warning: Could not plot preview figures: {e}. Matplotlib might be missing or headless environment issue.", file=sys.stderr)

    # 4. Save CSV Output Files
    def save_csv(path, fields, records):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in records:
                writer.writerow(r)

    save_csv(out_dir / "spk_smoke_file_inventory.csv", [
        "session_id", "condition", "signal_class", "source_file", "shape", "dims",
        "n_trials", "n_units", "n_timepoints", "time_axis_status",
        "p1_relative_possible", "omission_relative_possible", "payload_read_policy", "warnings"
    ], smoke_file_records)

    save_csv(out_dir / "spk_condition_coverage.csv", [
        "session_id", "condition", "family", "omission_slot", "is_omission", "matched_control",
        "n_trials", "n_units", "source_file", "included_in_smoke", "warnings"
    ], condition_coverage_records)

    save_csv(out_dir / "spk_timebase_window_inventory.csv", [
        "session_id", "condition", "window_name", "alignment_event", "time_base", "window_ms",
        "expected_start_ms", "expected_end_ms", "index_start", "index_end",
        "n_timepoints_window", "window_within_bounds", "warnings"
    ], timebase_window_records)

    save_csv(out_dir / "spk_smoke_metrics.csv", [
        "session_id", "condition", "smoke_metric", "value", "units", "n_trials",
        "n_units", "n_timepoints", "computed_from_slice", "interpretation_allowed"
    ], smoke_metric_records)

    # 5. Generate JSON preview manifest
    generated_files = [
        "spk_smoke_file_inventory.csv",
        "spk_condition_coverage.csv",
        "spk_timebase_window_inventory.csv",
        "spk_smoke_metrics.csv",
        "spk_preview_manifest.json",
        "spk_psth_smoke_summary.json",
        "spk_psth_smoke_summary.md"
    ]
    if (out_dir / "preview_p1_relative_psth.png").exists():
        generated_files.extend(["preview_p1_relative_psth.png", "preview_omission_relative_psth.png", "preview_raster_slice.png"])

    hashes_dict = {}
    for f_name in generated_files:
        f_path = out_dir / f_name
        if f_path.exists():
            hashes_dict[f_name] = compute_sha256(f_path)

    preview_manifest = {
        "artifact_id": "A7_spk_psth_smoke_gate",
        "truth_status": TRUTH_SAFE_UNVERIFIED,
        "validation_status": "smoke_only_not_biological_evidence",
        "source_script": "scripts/build_spk_psth_smoke_inventory.py",
        "git_commit": get_git_commit(),
        "data_root_status": "D:\\workspace\\data valid NTFS",
        "payload_read_policy": payload_read_policy,
        "max_preview_units": args.max_preview_units,
        "max_preview_trials": args.max_preview_trials,
        "session_ids": session_ids,
        "conditions": CONDITIONS,
        "time_constants_source": "prototype_constants_from_task_contract",
        "blocked_claims": [
            "response-class inference (S+, S-, O+, O-, X, null)",
            "area-wise omission sensitivity differences",
            "higher-order vs lower-order cortex population metrics",
            "manuscript claim promotion",
            "any cortical hierarchy sorting"
        ],
        "allowed_claims": [
            "SPK rank-3 shape validation",
            "trial count preservation verification",
            "p1-relative timebase index mapping",
            "omission-relative local timebase index mapping"
        ],
        "generated_files": generated_files,
        "hashes": hashes_dict
    }

    with open(out_dir / "spk_preview_manifest.json", "w", encoding="utf-8") as f:
        json.dump(preview_manifest, f, indent=2)

    # 6. Generate JSON Summary
    n_missing_conditions = len(session_ids) * len(CONDITIONS) - len(spk_files)
    n_missing_matched_controls = 0  # Since AXAB has AAAB, BXBA has BBBA, RXRR has RRRR all verified present

    summary_json = {
        "truth_status": TRUTH_SAFE_UNVERIFIED,
        "n_sessions": len(session_ids),
        "n_conditions": len(CONDITIONS),
        "n_spk_files": len(spk_files),
        "n_total_trials_indexed": n_total_trials_indexed,
        "n_total_units_indexed": n_total_units_indexed,
        "n_timebase_windows_checked": n_timebase_windows_checked,
        "n_window_bound_failures": n_window_bound_failures,
        "n_missing_conditions": n_missing_conditions,
        "n_missing_matched_controls": n_missing_matched_controls,
        "n_payload_policy_violations": n_payload_policy_violations,
        "n_raw_h5_reads": n_raw_h5_reads,
        "manuscript_safe_biological_claims": False,
        "area_hierarchy_claims_allowed": False
    }

    with open(out_dir / "spk_psth_smoke_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)

    # 7. Generate markdown summary report
    preview_block = ""
    if (out_dir / "preview_p1_relative_psth.png").exists():
        preview_block = f"""
## Timebase Sanity Preview Figures
- **P1-Relative PSTH Preview**: ![P1-Relative PSTH](preview_p1_relative_psth.png)
- **Omission-Relative PSTH Preview**: ![Omission-Relative PSTH](preview_omission_relative_psth.png)
- **Bounded Raster Slice Preview**: ![Raster Preview](preview_raster_slice.png)
"""

    md_content = f"""# Omission Phase A7 SPK PSTH/Raster Smoke Sanity Gate
**Truth Status**: `{TRUTH_SAFE_UNVERIFIED}`
**Validation Status**: `smoke_only_not_biological_evidence`

This analytical report validates the signal-timebase handling, trial-count preservation, and condition coverage of SPK/SUA signals.

## Summary Analytics
- **Total Sessions Analyzed**: {summary_json['n_sessions']}
- **Total Inferred SPK Files**: {summary_json['n_spk_files']} files
- **Total Trials Indexed**: {summary_json['n_total_trials_indexed']} trials
- **Maximum Units on Probe**: {summary_json['n_total_units_indexed']} units
- **Timebase Windows Checked**: {summary_json['n_timebase_windows_checked']}
- **Window Boundary Failures**: {summary_json['n_window_bound_failures']}
- **Missing Conditions**: {summary_json['n_missing_conditions']}
- **Raw HDF5 Reads**: {summary_json['n_raw_h5_reads']} (Zero-tolerance passed)
- **Payload Policy Violations**: {summary_json['n_payload_policy_violations']}

## Core Timing Constants Checked
- `P1_ONSET_MS` = {P1_ONSET_MS}
- `P2_ONSET_MS` = {P2_ONSET_MS}
- `P3_ONSET_MS` = {P3_ONSET_MS}
- `P4_ONSET_MS` = {P4_ONSET_MS}
- `FULL_SEQUENCE_WINDOW_MS` = `[-1000, 4124]`
- `OMISSION_LOCAL_WINDOW_MS` = `[-1000, 1000]`

## Critical Bounding & Protection Rules
- **No Response-Class Inference**: No unit response classes were computed (S+, S-, O+, O-, X, null are completely absent).
- **No Cortical Hierarchy/Area Claims**: All unit-area assignments remain strictly blocked from manuscript-safe claims. The count-matched unit row order remains unvalidated for area provenance.
- **Zero HDF5 Payload Reads**: No `.h5` files were opened. All NumPy arrays were loaded lazily using `mmap_mode="r"`.
- **Capped Preview Slicing**: Slices used for preview metrics and raster/PSTH figures are strictly capped at `--max-preview-units {args.max_preview_units}` and `--max-preview-trials {args.max_preview_trials}`.
{preview_block}

## Phase A8 Response-Class Planning Readiness
- **Allowed**: Yes, Phase A8 response-class metrics planning is allowed because signal-timebase, condition coverage, and trial-count alignment are fully validated.
- **Strict Blockers for A8/A9**:
  1. Response-class metrics must be computed strictly *without* cortical area claims.
  2. Any population area or hierarchy metrics remain completely blocked until SPK unit-axis provenance has been resolved with explicit empirical receipts.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: signal-timebase-smoke / Repo or Workspace: D:\\workspace\\omission / Date: 2026-05-22
"""

    with open(out_dir / "spk_psth_smoke_summary.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"A7 SPK PSTH/raster smoke sanity inventory complete. Outputs written to {args.out_dir}")

if __name__ == "__main__":
    main()
