import os
import re
import json
import numpy as np
import plotly.graph_objects as go
from pathlib import Path
from scipy import stats
from src.analysis.lfp.lfp_layer_masks import get_probe_layer_masks


# Constants
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
OUTPUT_DIR = Path("D:/workspace/omission/outputs/omission_aligned_tfr")
LAYER_MASKS_PATH = Path("D:/workspace/omission/outputs/publication_visual_review/area_layer_tfr/layer_masks.json")

CANONICAL_AREAS = ['V1', 'V2', 'V3d', 'V3a', 'V4', 'MT', 'MST', 'TEO', 'FST', 'FEF', 'PFC']

# Frequencies and Times in original TFR files
FREQS_HZ = np.arange(3, 201, 2)  # 99 bins
N_TIME_BINS = 500
TIMES_MS = -1000.0 + np.arange(N_TIME_BINS) * 10.0  # -1000 to 3990 ms

# The 7 bands defined in the project specs (PUBLICATION_BANDS excluding delta)
BANDS = {
    "Theta": (3.0, 7.0),
    "Alpha": (8.0, 12.0),
    "Beta-1": (12.0, 20.0),
    "Beta-2": (20.0, 30.0),
    "Gamma-1": (32.0, 50.0),
    "Gamma-2": (50.0, 90.0),
    "Gamma-3": (90.0, 200.0)
}

# Standard styling colors for the 7 bands (Madelane Golden Dark ordering/complementary)
BAND_COLORS = {
    "Theta": "#9400D3",    # Violet
    "Alpha": "#4B0082",    # Indigo
    "Beta-1": "#0000FF",   # Blue
    "Beta-2": "#008B8B",   # Dark Cyan
    "Gamma-1": "#CFB87C",  # Gold
    "Gamma-2": "#D55E00",  # Vermillion / Orange
    "Gamma-3": "#FF1493"   # Deep Pink
}

# Slot mappings to omission conditions
SLOT_CONDITIONS = {
    2: ["AXAB", "BXBA", "RXRR"],
    3: ["AAXB", "BBXA", "RRXR"],
    4: ["AAAX", "BBBX", "RRRX"]
}

# Slice indices relative to omission onset (0 ms is at onset_idx)
# Common relative time scale: -1560 ms to +1030 ms (length 260, 10 ms steps)
RELATIVE_TIME_MS = np.arange(-156, 104) * 10.0

def area_search_tokens(canonical_area: str) -> list[str]:
    tokens = [canonical_area]
    if canonical_area == "V4":
        tokens.append("DP")
    return tokens

def discover_tfr_files(area: str) -> list[dict]:
    tokens = area_search_tokens(area)
    files = []
    file_pattern = re.compile(rf"^(.+)-([ABC])-([A-Za-z0-9]+)-([A-Z0-9]+)\.npy$")
    
    for path in TFR_DIR.glob("*.npy"):
        m = file_pattern.match(path.name)
        if not m:
            continue
        session, probe, file_area, cond = m.groups()
        if file_area not in tokens:
            continue
        
        # Identify which slot this omission belongs to
        slot = None
        for s_idx, conds in SLOT_CONDITIONS.items():
            if cond in conds:
                slot = s_idx
                break
        if slot is None:
            continue
            
        files.append({
            "path": path,
            "session": session,
            "probe": probe,
            "area": file_area,
            "condition": cond,
            "slot": slot
        })
    return files

def get_onset_idx_and_slices(slot: int) -> tuple[int, int, int]:
    # Omission onset times: Slot 2 = 1031 ms, Slot 3 = 2062 ms, Slot 4 = 3093 ms
    if slot == 2:
        onset_ms = 1031.0
    elif slot == 3:
        onset_ms = 2062.0
    else:
        onset_ms = 3093.0
        
    onset_idx = int(round((onset_ms - (-1000.0)) / 10.0))
    start_idx = onset_idx - 156
    end_idx = onset_idx + 104
    return onset_idx, start_idx, end_idx

def load_and_align_trials(file_info: dict, mask: np.ndarray) -> np.ndarray:
    """Load a TFR file, apply layer mask, baseline normalize, and align to omission onset.
    
    Returns array of shape (n_trials, n_freqs, 260) with aligned relative power in dB.
    """
    power = np.load(file_info["path"], mmap_mode="r")  # (trials, channels, freqs, times)
    n_trials = power.shape[0]
    
    # 1. Average across selected channels
    layer_power = np.mean(power[:, mask, :, :], axis=1)  # (trials, freqs, times)
    
    # 2. Baseline normalize to pre-stimulus baseline [-500, 0] ms relative to P1 onset
    baseline_mask = (TIMES_MS >= -500.0) & (TIMES_MS <= 0.0)
    baseline = np.mean(layer_power[..., baseline_mask], axis=-1, keepdims=True)
    
    safe_power = np.maximum(layer_power, 1e-12)
    safe_baseline = np.maximum(baseline, 1e-12)
    layer_power_db = 10.0 * np.log10(safe_power / safe_baseline)
    layer_power_db = np.nan_to_num(layer_power_db, nan=0.0, posinf=0.0, neginf=0.0)
    
    # 3. Align and slice relative to omission onset
    onset_idx, start_idx, end_idx = get_onset_idx_and_slices(file_info["slot"])
    
    aligned = np.full((n_trials, len(FREQS_HZ), len(RELATIVE_TIME_MS)), np.nan, dtype=np.float32)
    
    # Calculate overlap
    src_start = max(0, start_idx)
    src_end = min(N_TIME_BINS, end_idx)
    
    dest_start = src_start - start_idx
    dest_end = dest_start + (src_end - src_start)
    
    aligned[:, :, dest_start:dest_end] = layer_power_db[:, :, src_start:src_end]
    return aligned

def run_pipeline():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load layer masks
    with open(LAYER_MASKS_PATH, "r") as f:
        layer_masks_cache = json.load(f)
    by_key_masks = layer_masks_cache.get("by_key", {})
    
    stats_records = []
    
    for area in CANONICAL_AREAS:
        print(f"Processing Area: {area}")
        files = discover_tfr_files(area)
        if not files:
            print(f"  No TFR files discovered for {area}. Skipping.")
            continue
            
        for layer_name in ["superficial_putative", "deep_putative"]:
            layer_key = "superficial" if "superficial" in layer_name else "deep"
            mask_field = "superficial_mask" if "superficial" in layer_name else "deep_mask"
            
            # Gather aligned trials grouped by slot
            slot_trials = {2: [], 3: [], 4: []}
            
            for file_info in files:
                try:
                    masks, meta = get_probe_layer_masks(
                        file_info["session"],
                        file_info["probe"],
                        cache=by_key_masks
                    )
                    
                    # Update cache so we don't recompute next time
                    mask_key = f"{file_info['session']}|{file_info['probe']}"
                    if mask_key not in by_key_masks:
                        by_key_masks[mask_key] = {
                            "session_id": meta.session_id,
                            "probe_letter": meta.probe_letter,
                            "crossover_idx": meta.crossover_idx,
                            "orientation": meta.orientation,
                            "n_channels": meta.n_channels,
                            "n_superficial": meta.n_superficial,
                            "n_deep": meta.n_deep,
                            "classification_condition": meta.classification_condition,
                            "method": meta.method,
                            "superficial_mask": masks["superficial_putative"].tolist(),
                            "deep_mask": masks["deep_putative"].tolist()
                        }
                    
                    if meta.orientation in ["unresolved", "invalid_range", "error"]:
                        continue
                    
                    mask = masks[layer_name]
                    if not np.any(mask):
                        continue
                        
                    aligned = load_and_align_trials(file_info, mask)
                    slot_trials[file_info["slot"]].append(aligned)
                except Exception as e:
                    # Silence file not found if the raw arrays are missing, but print others
                    if not isinstance(e, FileNotFoundError):
                        print(f"  Error processing {file_info['path'].name}: {e}")


            
            # Concatenate trials for each slot
            slot_data = {}
            for slot in [2, 3, 4]:
                if slot_trials[slot]:
                    slot_data[slot] = np.concatenate(slot_trials[slot], axis=0)
                else:
                    slot_data[slot] = np.empty((0, len(FREQS_HZ), len(RELATIVE_TIME_MS)))
                    
            # Determine maximum possible equal N
            n_trials_per_slot = {s: d.shape[0] for s, d in slot_data.items()}
            print(f"  {layer_name} trial counts: {n_trials_per_slot}")
            
            if min(n_trials_per_slot.values()) == 0:
                print(f"  One of the slots has 0 trials for {area} {layer_name}. Skipping.")
                continue
                
            N = min(n_trials_per_slot.values())
            
            # Subsample trials randomly without replacement for balance
            rng = np.random.default_rng(42)  # Seed for reproducibility
            subsampled_data = {}
            for slot, data in slot_data.items():
                idx = rng.choice(data.shape[0], size=N, replace=False)
                subsampled_data[slot] = data[idx]
                
            # Pool trials (shape: (3 * N, n_freqs, n_times))
            pooled_trials = np.concatenate([subsampled_data[s] for s in [2, 3, 4]], axis=0)
            
            # Calculate band power traces
            band_traces = {}
            for band_name, (fmin, fmax) in BANDS.items():
                freq_mask = (FREQS_HZ >= fmin) & (FREQS_HZ <= fmax)
                # Average across frequencies for each trial
                # shape: (3 * N, n_times)
                trial_band_power = np.nanmean(pooled_trials[:, freq_mask, :], axis=1)
                
                mean_trace = np.nanmean(trial_band_power, axis=0)
                sem_trace = np.nanstd(trial_band_power, axis=0) / np.sqrt(N * 3)
                
                band_traces[band_name] = {
                    "mean": mean_trace,
                    "sem": sem_trace,
                    "trial_power": trial_band_power
                }
                
                # Perform statistics
                # Epochs: Pre-omission [-500, 0] ms, Omission [0, 500] ms, Post-omission [500, 1000] ms
                t_mask_pre = (RELATIVE_TIME_MS >= -500.0) & (RELATIVE_TIME_MS <= 0.0)
                t_mask_om = (RELATIVE_TIME_MS >= 0.0) & (RELATIVE_TIME_MS <= 500.0)
                t_mask_post = (RELATIVE_TIME_MS >= 500.0) & (RELATIVE_TIME_MS <= 1000.0)
                
                val_pre = np.nanmean(trial_band_power[:, t_mask_pre], axis=1)
                val_om = np.nanmean(trial_band_power[:, t_mask_om], axis=1)
                val_post = np.nanmean(trial_band_power[:, t_mask_post], axis=1)
                
                # Kruskal-Wallis H-test
                h_stat, kw_p = stats.kruskal(val_pre, val_om, val_post)
                
                # Wilcoxon signed-rank test (paired: Omission vs Pre-omission)
                wilc_stat, wilc_p = stats.wilcoxon(val_om, val_pre)
                
                stats_records.append({
                    "area": area,
                    "layer": layer_key,
                    "band": band_name,
                    "N_per_slot": int(N),
                    "total_N": int(N * 3),
                    "kw_h": float(h_stat),
                    "kw_p": float(kw_p),
                    "kw_df": 2,
                    "wilcoxon_stat": float(wilc_stat),
                    "wilcoxon_p": float(wilc_p)
                })
                
            # Create Plotly interactive line traces plot
            fig = go.Figure()
            
            for band_name, traces in band_traces.items():
                color = BAND_COLORS[band_name]
                mean_val = traces["mean"]
                sem_val = traces["sem"]
                
                # Shaded SEM area
                fig.add_trace(go.Scatter(
                    x=np.concatenate([RELATIVE_TIME_MS, RELATIVE_TIME_MS[::-1]]),
                    y=np.concatenate([mean_val + sem_val, (mean_val - sem_val)[::-1]]),
                    fill='toself',
                    fillcolor=color,
                    opacity=0.15,
                    line=dict(color='rgba(255,255,255,0)'),
                    showlegend=False,
                    name=f"{band_name} SEM"
                ))
                
                # Mean Line trace
                fig.add_trace(go.Scatter(
                    x=RELATIVE_TIME_MS,
                    y=mean_val,
                    mode='lines',
                    line=dict(color=color, width=2.5),
                    name=band_name
                ))
                
            # Standard formatting
            fig.update_layout(
                title=f"Unified Omission-Aligned TFR Traces: {area} {layer_key.capitalize()} (N={N} per slot, Total N={N*3})",
                xaxis_title="Time relative to omission onset (ms)",
                yaxis_title="Relative Power (dB)",
                plot_bgcolor='#FFFFFF',
                paper_bgcolor='#FFFFFF',
                xaxis=dict(
                    gridcolor='#F0F0F0',
                    zeroline=True,
                    zerolinecolor='#D0D0D0'
                ),
                yaxis=dict(
                    gridcolor='#F0F0F0',
                    zeroline=True,
                    zerolinecolor='#D0D0D0'
                ),
                legend=dict(
                    title="Frequency Bands",
                    bordercolor='#E0E0E0',
                    borderwidth=1
                )
            )
            
            # Add vertical lines for event markers
            fig.add_vline(x=0.0, line_dash="dash", line_color="black", annotation_text="Omission Onset")
            fig.add_vline(x=-531.0, line_dash="dot", line_color="gray", annotation_text="Pre-stim ISI")
            fig.add_vline(x=-1031.0, line_dash="dot", line_color="gray", annotation_text="Stim Onset")
            fig.add_vline(x=500.0, line_dash="dot", line_color="gray", annotation_text="Omission End")
            
            # Save interactive HTML figure
            out_filename = f"{area}_{layer_key}_omission_tfr_traces.html"
            fig.write_html(str(OUTPUT_DIR / out_filename))
            print(f"  Saved plot: {out_filename}")
            
    # Save back updated layer masks cache
    layer_masks_cache["by_key"] = by_key_masks
    with open(LAYER_MASKS_PATH, "w") as f:
        json.dump(layer_masks_cache, f, indent=2)
    print("Saved updated layer masks cache to disk.")

    # Export statistics to JSON
    with open(OUTPUT_DIR / "omission_aligned_tfr_stats.json", "w") as f:
        json.dump(stats_records, f, indent=2)
    print("Exported statistics report to JSON.")

    
    # Print summary Markdown table
    print("\n| Area | Layer | Band | N (slot) | KW H-stat | KW p-val | Wilcoxon p-val |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for r in stats_records:
        print(f"| {r['area']} | {r['layer']} | {r['band']} | {r['N_per_slot']} | {r['kw_h']:.2f} | {r['kw_p']:.2e} | {r['wilcoxon_p']:.2e} |")

if __name__ == "__main__":
    run_pipeline()
