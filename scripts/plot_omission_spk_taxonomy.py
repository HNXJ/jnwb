#!/usr/bin/env python3
"""
scripts/plot_omission_spk_taxonomy.py
=====================================
Generates the publication-quality Spiking Response Taxonomy figure.
Plots:
  - Left column: Average PSTH traces (-500 to 4000 ms) for AXAB (Slot 2 Omission),
    AAXB (Slot 3 Omission), and AAAX (Slot 4 Omission) conditions for:
      1. Excited by stimulus (S+)
      2. Inhibited by stimulus (S-)
      3. Correlated to omission (O+; N=36)
  - Right column: Bar charts showing the % of total units per area for each group.
Uses the vetted 6,040 unit database and the large A-family spike epoch NPZ.
"""

import os
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.ndimage import gaussian_filter1d
from pathlib import Path

# Paths
OUTPUT_DIR = Path("D:/workspace/omission/outputs/publication_figures")
NPZ_PATH = Path("D:/workspace/omission/outputs/archive/time_frequency_representation/afamily_spk_p1_epochs.npz")
UNIT_META_CSV = Path("D:/workspace/omission/outputs/archive/time_frequency_representation/afamily_spk_p1_unit_metadata.csv")
TRIAL_META_CSV = Path("D:/workspace/omission/outputs/archive/time_frequency_representation/afamily_spk_p1_trial_metadata.csv")
GRAND_DB_CSV = Path("D:/workspace/omission/outputs/publication_figures/grand_database_6040_units.csv")

CANONICAL_AREAS = ['V1', 'V2', 'V3d', 'V3a', 'V4', 'MT', 'MST', 'TEO', 'FST', 'FEF', 'PFC']

# Group colors (matches poster/Madelane Golden Dark style)
COLORS = {
    "AXAB": "#9400D3",  # Violet (Slot 2)
    "AAXB": "#2E7D32",  # Green (Slot 3)
    "AAAX": "#1565C0",  # Blue (Slot 4)
}

BAR_COLORS = {
    "S+": "#1565C0",  # Blue for excited by stimulus
    "S-": "#EF6C00",  # Orange for inhibited by stimulus
    "O+": "#8E24AA",  # Purple for correlated to omission
}

def load_data():
    print("Loading data...")
    grand_db = pd.read_csv(GRAND_DB_CSV)
    epochs_data = np.load(NPZ_PATH, allow_pickle=True)
    
    unit_meta_list = json.loads(str(epochs_data["signal_metadata_json"]))
    unit_meta = pd.DataFrame(unit_meta_list)
    
    trial_meta_list = json.loads(str(epochs_data["trial_metadata_json"]))
    trial_meta = pd.DataFrame(trial_meta_list)
    
    return grand_db, unit_meta, trial_meta, epochs_data

def get_session_num(session_key):
    # E.g. sub_V198o_ses_230629 -> 230629
    import re
    m = re.search(r"(\d{6})", session_key)
    return int(m.group(1)) if m else None

def map_units(unit_meta, grand_db):
    print("Mapping NPZ units to Grand Database...")
    mapped_indices = []
    
    # Pre-build dictionary for fast lookup
    # key: (session_id, unit_id) -> row
    db_lookup = {}
    for idx, row in grand_db.iterrows():
        db_lookup[(int(row["session_id"]), int(row["unit_id"]))] = row
        
    for idx, row in unit_meta.iterrows():
        sess_num = get_session_num(row["session_id"])
        sig_id = int(row["signal_id"])
        
        db_row = db_lookup.get((sess_num, sig_id))
        if db_row is not None:
            mapped_indices.append({
                "npz_unit_idx": idx,
                "session_id": sess_num,
                "unit_id": sig_id,
                "area": db_row["area"],
                "stable_plus": bool(db_row["stable_plus"]),
                "sig_s_plus": bool(db_row["sig_s_plus"]),
                "sig_s_minus": bool(db_row["sig_s_minus"]),
                "sig_o_plus": bool(db_row["sig_o_plus"]),
                "is_stable": bool(db_row["is_stable"]),
            })
            
    return pd.DataFrame(mapped_indices)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grand_db, unit_meta, trial_meta, epochs_data = load_data()
    mapped_units = map_units(unit_meta, grand_db)
    
    # 1. Classify the NPZ units (which are the 2,875 stable units)
    # S+: sig_s_plus == True
    # S-: sig_s_minus == True
    # O+: sig_o_plus == True & stable_plus == True (the 36 omission units)
    
    s_plus_units = mapped_units[mapped_units["sig_s_plus"] == True]["npz_unit_idx"].values
    s_minus_units = mapped_units[mapped_units["sig_s_minus"] == True]["npz_unit_idx"].values
    o_plus_units = mapped_units[(mapped_units["sig_o_plus"] == True) & (mapped_units["stable_plus"] == True)]["npz_unit_idx"].values
    
    print(f"NPZ Unit Groups - S+: {len(s_plus_units)}, S-: {len(s_minus_units)}, O+: {len(o_plus_units)}")
    
    # 2. Compute PSTH traces for each group and condition
    # For each session, extract spike epochs and average
    time_axis = epochs_data["time_axis_ms"]
    n_bins = len(time_axis)
    
    conditions = ["AXAB", "AAXB", "AAAX"]
    
    # Initialize group traces: {group: {cond: list of unit traces}}
    group_unit_traces = {
        "S+": {c: [] for c in conditions},
        "S-": {c: [] for c in conditions},
        "O+": {c: [] for c in conditions}
    }
    
    # List of all session keys in NPZ
    session_keys = epochs_data["session_keys"]
    
    for sess_key in session_keys:
        epochs_key = f"spk_epochs__{sess_key}"
        if epochs_key not in epochs_data:
            continue
            
        print(f"Processing session: {sess_key}")
        # Shape: (trials, units, times)
        spk_epochs = epochs_data[epochs_key]
        n_trials, n_units_in_sess, _ = spk_epochs.shape
        
        # Filter trial metadata for this session
        sess_trial_meta = trial_meta[trial_meta["artifact_session_key"] == sess_key].reset_index(drop=True)
        # Filter unit metadata for this session
        sess_unit_meta = unit_meta[unit_meta["artifact_session_key"] == sess_key].reset_index(drop=True)
        
        for cond in conditions:
            cond_trial_indices = sess_trial_meta[sess_trial_meta["condition"] == cond].index.values
            if len(cond_trial_indices) == 0:
                continue
                
            # Average across trials (trials, units, times) -> (units, times)
            mean_spk = np.mean(spk_epochs[cond_trial_indices, :, :], axis=0) * 1000.0  # Spikes/s
            
            for u_idx in range(n_units_in_sess):
                global_unit_idx = sess_unit_meta.loc[u_idx, "global_unit_index"]
                
                # Check which group this unit belongs to
                mapped_row = mapped_units[mapped_units["npz_unit_idx"] == global_unit_idx]
                if mapped_row.empty:
                    continue
                    
                mapped_row = mapped_row.iloc[0]
                unit_trace = mean_spk[u_idx, :]
                smoothed_trace = gaussian_filter1d(unit_trace, sigma=40)
                
                if mapped_row["sig_s_plus"]:
                    group_unit_traces["S+"][cond].append(smoothed_trace)
                if mapped_row["sig_s_minus"]:
                    group_unit_traces["S-"][cond].append(smoothed_trace)
                if mapped_row["sig_o_plus"] and mapped_row["stable_plus"]:
                    group_unit_traces["O+"][cond].append(smoothed_trace)
                    
    # Compute mean and SEM across units for each group and condition
    group_averages = {}
    for group in ["S+", "S-", "O+"]:
        group_averages[group] = {}
        for cond in conditions:
            traces = np.array(group_unit_traces[group][cond])
            if len(traces) > 0:
                group_averages[group][cond] = {
                    "mean": np.mean(traces, axis=0),
                    "sem": np.std(traces, axis=0) / np.sqrt(len(traces)),
                    "n": len(traces)
                }
            else:
                group_averages[group][cond] = {
                    "mean": np.zeros(n_bins),
                    "sem": np.zeros(n_bins),
                    "n": 0
                }
                
    # 3. Calculate % of total per area from Grand Database (6,040 units)
    total_by_area = grand_db.groupby("area").size()
    
    pct_s_plus = (grand_db[grand_db["sig_s_plus"] == True].groupby("area").size() / total_by_area * 100).reindex(CANONICAL_AREAS, fill_value=0.0)
    pct_s_minus = (grand_db[grand_db["sig_s_minus"] == True].groupby("area").size() / total_by_area * 100).reindex(CANONICAL_AREAS, fill_value=0.0)
    pct_o_plus = (grand_db[(grand_db["sig_o_plus"] == True) & (grand_db["stable_plus"] == True)].groupby("area").size().reindex(CANONICAL_AREAS, fill_value=0) / total_by_area * 100).reindex(CANONICAL_AREAS, fill_value=0.0)
    
    counts_s_plus = grand_db[grand_db["sig_s_plus"] == True].groupby("area").size().reindex(CANONICAL_AREAS, fill_value=0)
    counts_s_minus = grand_db[grand_db["sig_s_minus"] == True].groupby("area").size().reindex(CANONICAL_AREAS, fill_value=0)
    counts_o_plus = grand_db[(grand_db["sig_o_plus"] == True) & (grand_db["stable_plus"] == True)].groupby("area").size().reindex(CANONICAL_AREAS, fill_value=0)
    
    # 4. Create Multi-Panel Subplots
    fig = make_subplots(
        rows=3, cols=2,
        column_widths=[0.65, 0.35],
        shared_xaxes=False,
        vertical_spacing=0.08,
        horizontal_spacing=0.08,
        subplot_titles=[
            "<b>Excited by Stimulus (S+) Traces</b>", "<b>% of Total Neurons Excited by Stimulus</b>",
            "<b>Inhibited by Stimulus (S-) Traces</b>", "<b>% of Total Neurons Inhibited by Stimulus</b>",
            "<b>Correlated to Omission (O+) Traces (N=36 Prime)</b>", "<b>% of Total Neurons Correlated to Omission</b>"
        ]
    )
    
    # Panel Traces Left Column
    groups = ["S+", "S-", "O+"]
    group_display_names = {
        "S+": f"Excited by Stimulus (N={sum(counts_s_plus)} / 6,040 total)",
        "S-": f"Inhibited by Stimulus (N={sum(counts_s_minus)} / 6,040 total)",
        "O+": f"Correlated to Omission (N=36 Prime / 6,040 total)"
    }
    
    for row_idx, group in enumerate(groups, start=1):
        for cond in conditions:
            mean = group_averages[group][cond]["mean"]
            sem = group_averages[group][cond]["sem"]
            n = group_averages[group][cond]["n"]
            
            color = COLORS[cond]
            rgba_color = f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15)"
            
            # Add SEM shading
            fig.add_trace(go.Scatter(
                x=np.concatenate([time_axis, time_axis[::-1]]),
                y=np.concatenate([mean + sem, (mean - sem)[::-1]]),
                fill='toself',
                fillcolor=rgba_color,
                line=dict(color='rgba(255,255,255,0)'),
                showlegend=False,
                name=f"{cond} SEM"
            ), row=row_idx, col=1)
            
            # Add Mean Line
            legend_name = f"{cond} (N={n} units)" if row_idx == 1 else None
            fig.add_trace(go.Scatter(
                x=time_axis,
                y=mean,
                mode='lines',
                line=dict(color=color, width=2.5),
                name=f"{cond} Omission Window" if row_idx == 1 else None,
                showlegend=(row_idx == 1)
            ), row=row_idx, col=1)
            
        # Draw background stimulation patches
        # Stim 1: 0 to 531 ms
        # Omission/Stim 2: 1031 to 1562 ms
        # Omission/Stim 3: 2062 to 2593 ms
        # Omission/Stim 4: 3093 to 3624 ms
        fig.add_vrect(x0=0, x1=531, fillcolor="#FFCDD2", opacity=0.2, line_width=0, row=row_idx, col=1)
        fig.add_vrect(x0=1031, x1=1562, fillcolor="#E1BEE7", opacity=0.3, line_width=0, row=row_idx, col=1)
        fig.add_vrect(x0=2062, x1=2593, fillcolor="#C8E6C9", opacity=0.3, line_width=0, row=row_idx, col=1)
        fig.add_vrect(x0=3093, x1=3624, fillcolor="#BBDEFB", opacity=0.3, line_width=0, row=row_idx, col=1)
        
        # Horizontal baseline line
        fig.add_hline(y=0.0, line_dash="dash", line_color="gray", row=row_idx, col=1)
        fig.update_yaxes(title_text="Firing Rate (spikes/s)", row=row_idx, col=1)
        fig.update_xaxes(title_text="Time relative to P1 onset (ms)", row=row_idx, col=1)
        
    # Right Column Bar Plots
    # S+
    fig.add_trace(go.Bar(
        x=CANONICAL_AREAS,
        y=pct_s_plus,
        marker_color=BAR_COLORS["S+"],
        marker_line_color="#000000",
        marker_line_width=1,
        text=[f"{v:.1f}%" for v in pct_s_plus],
        textposition="outside",
        name="S+ % per area"
    ), row=1, col=2)
    fig.update_yaxes(title_text="% of total neurons", row=1, col=2)
    
    # S-
    fig.add_trace(go.Bar(
        x=CANONICAL_AREAS,
        y=pct_s_minus,
        marker_color=BAR_COLORS["S-"],
        marker_line_color="#000000",
        marker_line_width=1,
        text=[f"{v:.1f}%" for v in pct_s_minus],
        textposition="outside",
        name="S- % per area"
    ), row=2, col=2)
    fig.update_yaxes(title_text="% of total neurons", row=2, col=2)
    
    # O+
    fig.add_trace(go.Bar(
        x=CANONICAL_AREAS,
        y=pct_o_plus,
        marker_color=BAR_COLORS["O+"],
        marker_line_color="#000000",
        marker_line_width=1,
        text=[f"{v:.1f}%" for v in pct_o_plus],
        textposition="outside",
        name="O+ % per area"
    ), row=3, col=2)
    fig.update_yaxes(title_text="% of total neurons", row=3, col=2)
    
    # Formatting layout
    fig.update_layout(
        title=dict(
            text="<b>Enhanced Spiking response taxonomy and Omission Motifs Across Cortical Hierarchy</b>"
                 "<br><sup>Calculated on the full 6,040 unit database. O+ represents the vetted N=36 prime omission units.</sup>",
            x=0.5,
            font=dict(size=16)
        ),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        legend=dict(
            bordercolor="#E0E0E0",
            borderwidth=1,
            x=0.02,
            y=0.98
        ),
        height=1000,
        width=1400
    )
    
    # Apply grid styling to all axes
    for row in range(1, 4):
        for col in range(1, 3):
            fig.update_xaxes(gridcolor="#F0F0F0", linecolor="#000000", row=row, col=col)
            fig.update_yaxes(gridcolor="#F0F0F0", linecolor="#000000", row=row, col=col)
            
    fig.write_html(str(OUTPUT_DIR / "spk_omission_taxonomy_dashboard.html"))
    try:
        fig.write_image(str(OUTPUT_DIR / "spk_omission_taxonomy_dashboard.svg"))
        fig.write_image(str(OUTPUT_DIR / "spk_omission_taxonomy_dashboard.png"))
    except Exception as e:
        print(f"Skipped image export due to: {e} (normal if kaleido is not installed)")
    print("Successfully generated Spiking response taxonomy dashboard!")
    
    # Print the table of results
    print("\n| Area | Total Units | S+ (Stim Excited) | S- (Stim Inhibited) | O+ (Omission Prime) |")
    print("| --- | --- | --- | --- | --- |")
    for area in CANONICAL_AREAS:
        t = total_by_area[area]
        s_p = f"{counts_s_plus[area]} ({pct_s_plus[area]:.1f}%)"
        s_m = f"{counts_s_minus[area]} ({pct_s_minus[area]:.1f}%)"
        o_p = f"{counts_o_plus[area]} ({pct_o_plus[area]:.1f}%)"
        print(f"| {area} | {t} | {s_p} | {s_m} | {o_p} |")

if __name__ == "__main__":
    main()
