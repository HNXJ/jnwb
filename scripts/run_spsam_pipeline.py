"""
run_spsam_pipeline.py — SpSAM NWB Pipeline Orchestrator.

Iterates over all NWB files, maps units to channels/areas/layers, classifies
units into 4 groups (stimulus_positive, stimulus_negative, omission, null),
computes Spike-LFP coupling (PLV across 7 bands + lag-0 cross-correlation)
in 4 contexts (standard, omission, flash, baseline), and aggregates
grand tables across sessions.

Outputs written to outputs/spsam/:
  <session>_probe_map.csv
  <session>_channel_area_vectors.csv
  <session>_unit_metadata.csv
  <session>_unit_lfp_coupling.csv
  <session>_manifest.json
  grand_probe_map.csv
  grand_channel_area_vectors.csv
  grand_unit_metadata.csv
  grand_unit_lfp_coupling.csv
"""
import os
import json
from pathlib import Path
import numpy as np
import pandas as pd
import scipy.signal as signal
from scipy.stats import ttest_rel
from scipy.ndimage import gaussian_filter1d
from pynwb import NWBHDF5IO
import matplotlib.pyplot as plt

from src.analysis.io.logger import log
from src.analysis.spsam.spsam_pipeline import (
    map_group_to_lfp_key,
    build_channel_area_map,
    extract_lfp_phase,
    compute_plv,
    compute_cross_correlation,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NWB_DIR = "D:/analysis/nwb"
OUTPUT_DIR = "outputs/spsam"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FREQUENCY_BANDS = {
    "theta":  (4,   8),
    "alpha":  (8,  12),
    "beta1":  (12, 20),
    "beta2":  (20, 30),
    "gamma1": (35, 50),
    "gamma2": (55, 90),
    "gamma3": (90, 150),
}

CONDITION_NUMBER_MAP = {
    "AAAB": [1, 2],
    "AXAB": [3],
    "AAXB": [4],
    "AAAX": [5],
    "BBBA": [6, 7],
    "BXBA": [8],
    "BBXA": [9],
    "BBBX": [10],
    "RRRR": list(range(11, 27)),
    "RXRR": list(range(27, 35)),
    "RRXR": [35, 37, 39, 41],
    "RRRX": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
}

# ---------------------------------------------------------------------------
# Spectrolaminar crossover
# ---------------------------------------------------------------------------

def compute_spectrolaminar_crossover(lfp_series):
    """Compute L4 crossover dynamically from 20 s of LFP using Welch PSD."""
    try:
        lfp_snippet = lfp_series.data[:20000, :]   # (20000, n_ch)
        n_ch = lfp_snippet.shape[1]
        fs = 1000.0

        ab_power = np.zeros(n_ch)
        ga_power = np.zeros(n_ch)
        for ch in range(n_ch):
            f, pxx = signal.welch(lfp_snippet[:, ch], fs=fs, nperseg=512)
            ab_power[ch] = np.mean(pxx[(f >= 8)  & (f <= 30)])
            ga_power[ch] = np.mean(pxx[(f >= 35) & (f <= 80)])

        ab_smooth = gaussian_filter1d(ab_power, sigma=2.0)
        ga_smooth = gaussian_filter1d(ga_power, sigma=2.0)

        ab_norm = ab_smooth / np.max(ab_smooth)
        ga_norm = ga_smooth / np.max(ga_smooth)
        diff = ga_norm - ab_norm

        crossover_idx = np.nan
        for i in range(len(diff) - 1):
            if diff[i] > 0 and diff[i + 1] < 0:
                crossover_idx = i + (0 - diff[i]) / (diff[i + 1] - diff[i])
                break

        if not np.isnan(crossover_idx):
            co_int = int(round(crossover_idx))
            if 10 < co_int < n_ch - 10:
                ab_above = np.mean(ab_norm[:co_int])
                ab_below = np.mean(ab_norm[co_int:])
                if ab_below > ab_above:
                    return crossover_idx, "normal"
                else:
                    return crossover_idx, "flipped"

        return crossover_idx, "invalid_orientation"

    except Exception as e:
        log.warning(f"Crossover computation failed: {e}")
        return np.nan, "error"


def get_laminar_position(local_ch_idx: int, crossover_idx, orientation: str) -> str:
    """Map local channel index to putative cortical layer."""
    if crossover_idx is None or (isinstance(crossover_idx, float) and np.isnan(crossover_idx)):
        return "unresolved"
    if orientation == "flipped":
        if local_ch_idx > crossover_idx + 1:
            return "Superficial (L2/3)"
        elif local_ch_idx < crossover_idx - 1:
            return "Deep (L5/L6)"
        else:
            return "Middle (L4)"
    else:
        if local_ch_idx < crossover_idx - 1:
            return "Superficial (L2/3)"
        elif local_ch_idx > crossover_idx + 1:
            return "Deep (L5/L6)"
        else:
            return "Middle (L4)"


# ---------------------------------------------------------------------------
# Per-session processing
# ---------------------------------------------------------------------------

def process_nwb_session(nwb_path: Path):
    session_id = nwb_path.stem.split("_")[1].replace("ses-", "")
    log.action(f"[Session {session_id}] Processing {nwb_path.name}")

    with NWBHDF5IO(str(nwb_path), "r", load_namespaces=True) as io:
        nwb = io.read()

        # ------------------------------------------------------------------
        # 1. Electrode / probe structure
        # ------------------------------------------------------------------
        if nwb.electrodes is None:
            log.warning(f"[{session_id}] No electrodes table. Skipping.")
            return None

        elec_df = nwb.electrodes.to_dataframe()
        n_elec = len(elec_df)

        # Build global-channel → {probe_id, local_idx, area} map
        channel_area_map = build_channel_area_map(elec_df)

        # Compute spectrolaminar crossover per probe
        probe_crossovers = {}   # probe_id → (crossover_idx, orientation)
        probe_names = elec_df["group_name"].unique() if "group_name" in elec_df.columns else elec_df["probe"].unique()

        probe_mapping_rows = []
        for p_name in probe_names:
            lfp_key, probe_idx = map_group_to_lfp_key(p_name)
            p_elec = elec_df[
                (elec_df["group_name"] == p_name) if "group_name" in elec_df.columns
                else (elec_df["probe"] == p_name)
            ]
            n_ch = len(p_elec)
            loc_str = p_elec["location"].iloc[0] if len(p_elec) else "unresolved"

            co_idx, orient = np.nan, "unresolved"
            if lfp_key in nwb.acquisition:
                co_idx, orient = compute_spectrolaminar_crossover(nwb.acquisition[lfp_key])
                log.action(
                    f"[{session_id}] Probe {p_name} ({lfp_key}): "
                    f"crossover={co_idx:.2f} ({orient})"
                )
            else:
                log.warning(f"[{session_id}] LFP key '{lfp_key}' not found in acquisition.")

            probe_crossovers[probe_idx] = (co_idx, orient)

            if n_ch != 128:
                log.warning(
                    f"[{session_id}] NONSTANDARD_PROBE_CHANNEL_COUNT: "
                    f"Probe {p_name} has {n_ch} channels (expected 128)."
                )

            probe_mapping_rows.append({
                "session_id":        session_id,
                "probe_name":        p_name,
                "probe_id":          probe_idx,
                "location":          loc_str,
                "channel_count":     n_ch,
                "crossover_channel": float(co_idx) if not np.isnan(co_idx) else None,
                "orientation":       orient,
            })

        # Augment channel_area_map with layer information
        for global_idx, info in channel_area_map.items():
            p_id = info["probe_id"]
            co_idx, orient = probe_crossovers.get(p_id, (np.nan, "unresolved"))
            info["layer"] = get_laminar_position(info["local_idx"], co_idx, orient)

        # Save probe map
        pd.DataFrame(probe_mapping_rows).to_csv(
            f"{OUTPUT_DIR}/{session_id}_probe_map.csv", index=False
        )

        # Save channel-area vector
        ch_rows = [
            {
                "session_id":    session_id,
                "channel_global": g_idx,
                "probe_id":      info["probe_id"],
                "probe_name":    info["probe_name"],
                "local_idx":     info["local_idx"],
                "area":          info["area"],
                "layer":         info["layer"],
            }
            for g_idx, info in channel_area_map.items()
        ]
        pd.DataFrame(ch_rows).to_csv(
            f"{OUTPUT_DIR}/{session_id}_channel_area_vectors.csv", index=False
        )

        # ------------------------------------------------------------------
        # 2. Event timings
        # ------------------------------------------------------------------
        if "omission_glo_passive" not in nwb.intervals:
            log.warning(f"[{session_id}] No 'omission_glo_passive' intervals. Skipping.")
            return None

        int_df = nwb.intervals["omission_glo_passive"].to_dataframe()
        for col in ("correct", "is_omission", "stimulus_number", "task_condition_number"):
            int_df[col] = pd.to_numeric(int_df[col], errors="coerce")

        correct_mask = int_df["correct"] == 1.0

        std_onsets = int_df[
            correct_mask &
            int_df["stimulus_number"].isin([2.0, 3.0, 4.0, 5.0]) &
            (int_df["is_omission"] != 1.0)
        ]["start_time"].values

        om_events = int_df[
            correct_mask &
            int_df["stimulus_number"].isin([3.0, 4.0, 5.0]) &
            (int_df["is_omission"] == 1.0)
        ]

        flash_onsets = np.array([])
        if nwb.intervals and "flash" in nwb.intervals:
            flash_onsets = nwb.intervals["flash"].to_dataframe()["start_time"].values

        p1_onsets = int_df[correct_mask & (int_df["stimulus_number"] == 2.0)]["start_time"].values
        baseline_onsets = p1_onsets - 0.5

        log.action(
            f"[{session_id}] Events — Std:{len(std_onsets)} "
            f"Om:{len(om_events)} Flash:{len(flash_onsets)} Baseline:{len(baseline_onsets)}"
        )

        # ------------------------------------------------------------------
        # 3. Unit metadata & classification
        # ------------------------------------------------------------------
        units_df = nwb.units.to_dataframe()
        units_metadata = []
        unit_spikes_cache = {}

        # Define condition lists for each slot omission and control
        s2_om_conds = [3, 8] + list(range(27, 35))
        s3_om_conds = [4, 9] + [35, 37, 39, 41]
        s4_om_conds = [5, 10] + [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50]
        ctrl_conds = list(range(11, 27)) + [1, 2, 6, 7]

        control_p1 = int_df[
            correct_mask &
            (int_df["stimulus_number"] == 2.0) &
            int_df["task_condition_number"].isin(ctrl_conds)
        ]["start_time"].values

        s2_om_onsets = int_df[
            correct_mask &
            (int_df["stimulus_number"] == 2.0) &
            int_df["task_condition_number"].isin(s2_om_conds)
        ]["start_time"].values

        s3_om_onsets = int_df[
            correct_mask &
            (int_df["stimulus_number"] == 2.0) &
            int_df["task_condition_number"].isin(s3_om_conds)
        ]["start_time"].values

        s4_om_onsets = int_df[
            correct_mask &
            (int_df["stimulus_number"] == 2.0) &
            int_df["task_condition_number"].isin(s4_om_conds)
        ]["start_time"].values

        for u_idx, row in units_df.iterrows():
            spikes = np.array(row["spike_times"], dtype=float)
            unit_spikes_cache[u_idx] = spikes

            # Map global channel → area/layer
            try:
                ch_global = int(float(row["peak_channel_id"]))
            except (TypeError, ValueError):
                ch_global = -1

            ch_info = channel_area_map.get(
                ch_global,
                {"probe_id": -1, "probe_name": "unresolved",
                 "local_idx": -1, "area": "unresolved", "layer": "unresolved"}
            )

            # Waveform class
            wf_dur = row.get("waveform_duration", np.nan)
            try:
                wf_dur = float(wf_dur)
                if np.isnan(wf_dur):
                    raise ValueError
                wf_class = "narrow" if wf_dur < 0.4 else "wide"
            except (TypeError, ValueError):
                wf_dur = np.nan
                wf_class = "unresolved"

            # Firing rates
            base_counts = [np.sum((spikes >= t) & (spikes < t + 0.5)) for t in baseline_onsets[:50]]
            base_fr = np.mean(base_counts) / 0.5 if base_counts else 0.0

            stim_counts_full = [np.sum((spikes >= t) & (spikes < t + 0.25)) for t in std_onsets[:50]]
            stim_fr = np.mean(stim_counts_full) / 0.25 if stim_counts_full else 0.0

            # Omission classification
            is_omission_unit = False
            diffs = []
            _window = 0.5
            
            if len(control_p1) > 0:
                if len(s2_om_onsets) > 0:
                    om_fr = np.mean([np.sum((spikes >= t + 1.1) & (spikes < t + 1.6)) for t in s2_om_onsets]) / _window
                    ctrl_fr = np.mean([np.sum((spikes >= t + 1.1) & (spikes < t + 1.6)) for t in control_p1]) / _window
                    diffs.append(om_fr - ctrl_fr)
                if len(s3_om_onsets) > 0:
                    om_fr = np.mean([np.sum((spikes >= t + 2.1) & (spikes < t + 2.6)) for t in s3_om_onsets]) / _window
                    ctrl_fr = np.mean([np.sum((spikes >= t + 2.1) & (spikes < t + 2.6)) for t in control_p1]) / _window
                    diffs.append(om_fr - ctrl_fr)
                if len(s4_om_onsets) > 0:
                    om_fr = np.mean([np.sum((spikes >= t + 3.1) & (spikes < t + 3.6)) for t in s4_om_onsets]) / _window
                    ctrl_fr = np.mean([np.sum((spikes >= t + 3.1) & (spikes < t + 3.6)) for t in control_p1]) / _window
                    diffs.append(om_fr - ctrl_fr)

            if diffs and max(diffs) > 2.0:
                is_omission_unit = True


            # Stimulus positive/negative via paired t-test
            n_subset = 30
            stim_sub = [np.sum((spikes >= t) & (spikes < t + 0.25)) for t in std_onsets[:n_subset]]
            base_sub = [np.sum((spikes >= t) & (spikes < t + 0.25)) for t in baseline_onsets[:n_subset]]

            group = "null"
            p_val = 1.0
            if is_omission_unit:
                group = "omission"
            elif len(stim_sub) > 5 and len(base_sub) > 5:
                n_min = min(len(stim_sub), len(base_sub))
                _, p_val = ttest_rel(stim_sub[:n_min], base_sub[:n_min])
                if p_val < 0.05:
                    group = "stimulus_positive" if stim_fr > base_fr else "stimulus_negative"

            units_metadata.append({
                "session_id":           session_id,
                "unit_id":              u_idx,
                "peak_channel_global":  ch_global,
                "probe_local_channel":  ch_info["local_idx"],
                "probe_id":             ch_info["probe_id"],
                "probe_name":           ch_info["probe_name"],
                "area":                 ch_info["area"],
                "layer":                ch_info["layer"],
                "quality":              row.get("quality", None),
                "snr":                  row.get("snr", np.nan),
                "presence_ratio":       row.get("presence_ratio", np.nan),
                "firing_rate":          row.get("firing_rate", np.nan),
                "waveform_duration":    wf_dur,
                "waveform_class":       wf_class,
                "baseline_fr":          base_fr,
                "stim_fr":              stim_fr,
                "group":                group,
                "stat_p_val":           p_val,
            })

        df_units = pd.DataFrame(units_metadata)

        # Cap groups: top-100 by p-val for stim groups, all omission, 100 null
        cap_map = {
            "stimulus_positive": 100,
            "stimulus_negative": 100,
            "omission":          None,
            "null":              100,
        }
        selected = []
        for g_name, cap in cap_map.items():
            g_df = df_units[df_units["group"] == g_name].copy()
            if cap is not None:
                if g_name in ("stimulus_positive", "stimulus_negative"):
                    g_df = g_df.sort_values("stat_p_val").head(cap)
                else:
                    g_df = g_df.head(cap)
            selected.append(g_df)

        df_selected = pd.concat(selected, ignore_index=True)
        df_selected.to_csv(f"{OUTPUT_DIR}/{session_id}_unit_metadata.csv", index=False)

        log.action(
            f"[{session_id}] Units selected: {len(df_selected)} "
            f"(+:{(df_selected['group']=='stimulus_positive').sum()} "
            f"-:{(df_selected['group']=='stimulus_negative').sum()} "
            f"om:{(df_selected['group']=='omission').sum()} "
            f"null:{(df_selected['group']=='null').sum()})"
        )

        # ------------------------------------------------------------------
        # 4. Spike-LFP coupling
        # ------------------------------------------------------------------
        coupling_results = []

        # Pre-load one LFP channel per probe into memory
        lfp_caches: dict = {}   # probe_id → full LFP array (time, n_ch)
        for p_name in probe_names:
            lfp_key, probe_idx = map_group_to_lfp_key(p_name)
            if lfp_key in nwb.acquisition:
                try:
                    lfp_caches[probe_idx] = nwb.acquisition[lfp_key].data[:]  # load full array
                    log.action(f"[{session_id}] LFP loaded for probe {p_name}: shape={lfp_caches[probe_idx].shape}")
                except Exception as e:
                    log.warning(f"[{session_id}] Failed to load LFP for probe {p_name}: {e}")

        contexts = {
            "standard":  std_onsets,
            "omission":  om_events["start_time"].values if not om_events.empty else np.array([]),
            "flash":     flash_onsets,
            "baseline":  baseline_onsets,
        }

        for u_row in df_selected.itertuples():
            u_id      = u_row.unit_id
            probe_id  = u_row.probe_id
            local_ch  = u_row.probe_local_channel
            spikes    = unit_spikes_cache[u_id]

            if probe_id not in lfp_caches or local_ch < 0:
                continue

            lfp_full = lfp_caches[probe_id]   # (total_time, n_ch)
            if local_ch >= lfp_full.shape[1]:
                log.warning(f"[{session_id}] Unit {u_id}: local_ch={local_ch} out of range ({lfp_full.shape[1]}). Skipping.")
                continue

            lfp_channel = lfp_full[:, local_ch].astype(float)
            fs = 1000.0

            for ctx_name, onsets in contexts.items():
                if len(onsets) == 0:
                    continue

                lfp_trials, spk_trials = [], []
                for t in onsets[:60]:
                    start_idx = int(round(t * fs))
                    end_idx   = start_idx + 500
                    if end_idx > len(lfp_channel):
                        continue
                    lfp_seg = lfp_channel[start_idx:end_idx]
                    spk_seg = np.histogram(spikes, bins=np.linspace(t, t + 0.5, 501))[0].astype(float)
                    if len(lfp_seg) == 500:
                        lfp_trials.append(lfp_seg)
                        spk_trials.append(spk_seg)

                if not lfp_trials:
                    continue

                lfp_arr = np.array(lfp_trials)   # (n_trials, 500)
                spk_arr = np.array(spk_trials)   # (n_trials, 500)

                time_corr = compute_cross_correlation(lfp_arr, spk_arr)

                plv_vals = {}
                for band_name, band_range in FREQUENCY_BANDS.items():
                    try:
                        phase_arr = extract_lfp_phase(lfp_arr, band_range, fs=fs)
                        plv_vals[band_name] = compute_plv(phase_arr, spk_arr)
                    except Exception:
                        plv_vals[band_name] = np.nan

                coupling_results.append({
                    "session_id":  session_id,
                    "unit_id":     u_id,
                    "area":        u_row.area,
                    "layer":       u_row.layer,
                    "group":       u_row.group,
                    "wf_class":    u_row.waveform_class,
                    "context":     ctx_name,
                    "time_corr":   time_corr,
                    **{f"{b}_plv": plv_vals.get(b, np.nan) for b in FREQUENCY_BANDS},
                })

        df_coupling = pd.DataFrame(coupling_results)
        df_coupling.to_csv(f"{OUTPUT_DIR}/{session_id}_unit_lfp_coupling.csv", index=False)

        # ------------------------------------------------------------------
        # 5. Manifest
        # ------------------------------------------------------------------
        manifest = {
            "session_id":      session_id,
            "nwb_file":        nwb_path.name,
            "probe_count":     len(probe_names),
            "total_units":     len(df_units),
            "selected_units":  len(df_selected),
            "crossovers": {
                str(pid): float(co) if co is not None and not np.isnan(co) else None
                for pid, (co, _) in probe_crossovers.items()
            },
            "orientations": {
                str(pid): orient for pid, (_, orient) in probe_crossovers.items()
            },
        }
        with open(f"{OUTPUT_DIR}/{session_id}_manifest.json", "w") as f:
            json.dump(manifest, f, indent=4)

        log.action(f"[{session_id}] Done. Coupling rows: {len(coupling_results)}")
        return session_id


# ---------------------------------------------------------------------------
# Grand table aggregation
# ---------------------------------------------------------------------------

def aggregate_grand_tables():
    log.action("Aggregating grand tables across all processed sessions...")
    probe_maps, ch_vecs, unit_metas, couplings = [], [], [], []

    for fname in os.listdir(OUTPUT_DIR):
        if fname.startswith("grand_"):
            continue
        fpath = f"{OUTPUT_DIR}/{fname}"
        if fname.endswith("_probe_map.csv"):
            probe_maps.append(pd.read_csv(fpath))
        elif fname.endswith("_channel_area_vectors.csv"):
            ch_vecs.append(pd.read_csv(fpath))
        elif fname.endswith("_unit_metadata.csv"):
            unit_metas.append(pd.read_csv(fpath))
        elif fname.endswith("_unit_lfp_coupling.csv"):
            couplings.append(pd.read_csv(fpath))

    def _save(frames, name):
        if frames:
            df = pd.concat(frames, ignore_index=True)
            df.to_csv(f"{OUTPUT_DIR}/{name}", index=False)
            log.action(f"Saved {name}: {len(df)} rows")

    _save(probe_maps,  "grand_probe_map.csv")
    _save(ch_vecs,     "grand_channel_area_vectors.csv")
    _save(unit_metas,  "grand_unit_metadata.csv")
    _save(couplings,   "grand_unit_lfp_coupling.csv")

    log.action("Grand tables complete -> outputs/spsam/")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    nwb_files = sorted(Path(NWB_DIR).glob("*.nwb"))
    print(f"Found {len(nwb_files)} NWB files to process.")

    processed = []
    for nwb_path in nwb_files:
        try:
            sid = process_nwb_session(nwb_path)
            if sid:
                processed.append(sid)
        except Exception as e:
            log.warning(f"Failed to process {nwb_path.name}: {e}")
            import traceback; traceback.print_exc()

    print(f"\nSuccessfully processed {len(processed)}/{len(nwb_files)} sessions: {processed}")
    aggregate_grand_tables()
