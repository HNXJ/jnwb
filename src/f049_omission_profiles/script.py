import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
import hashlib
import json
import subprocess
from datetime import datetime
from scipy.ndimage import gaussian_filter1d
from src.analysis.io.loader import DataLoader
from src.analysis.profile_search import ProfileSearcher

class OmissionPlotter:
    """Implements the visual grammar for Omission project figures."""
    
    STYLE = {
        'stim_color': "rgba(0, 100, 250, 0.1)",
        'om_color': "rgba(100, 100, 100, 0.1)",
        'baseline_color': "#FFA500", # Orange
        'response_color': "#FF0000", # Red
        'psth_color': "black",
        'raster_color': "gray"
    }

    def __init__(self, loader=None):
        self.loader = loader or DataLoader()
        self.time = np.linspace(-1000, 4999, 6000)

    def create_raster_psth_panel(self, unit_id, condition, family_cfg, show_control=False, ctrl_cond=None):
        """Creates a single Plotly figure with Raster and PSTH."""
        spk = self.loader.load_unit_spikes(unit_id, condition=condition)
        if spk is None: return None
        
        # Smoothed PSTH
        psth = np.mean(spk, axis=0) * 1000
        smoothed = gaussian_filter1d(psth, sigma=20) # 20ms smoothing
        
        fig = make_subplots(rows=2, cols=1, row_heights=[0.3, 0.7], vertical_spacing=0.05, shared_xaxes=True)
        
        # 1. Raster Panel (Top)
        n_trials = spk.shape[0]
        trial_indices, spike_times = np.where(spk > 0)
        # Shift spike times to ms
        spike_times_ms = self.time[spike_times]
        
        fig.add_trace(go.Scatter(
            x=spike_times_ms, y=trial_indices,
            mode='markers', marker=dict(size=2, color=self.STYLE['raster_color'], opacity=0.4),
            showlegend=False
        ), row=1, col=1)
        
        # 2. PSTH Panel (Bottom)
        fig.add_trace(go.Scatter(
            x=self.time, y=smoothed,
            mode='lines', line=dict(color=self.STYLE['psth_color'], width=2),
            name=f"{condition} PSTH"
        ), row=2, col=1)
        
        if show_control and ctrl_cond:
            ctrl_spk = self.loader.load_unit_spikes(unit_id, condition=ctrl_cond)
            if ctrl_spk is not None:
                ctrl_psth = gaussian_filter1d(np.mean(ctrl_spk, axis=0) * 1000, sigma=20)
                fig.add_trace(go.Scatter(
                    x=self.time, y=ctrl_psth,
                    mode='lines', line=dict(color='gray', dash='dash'),
                    name='Control'
                ), row=2, col=1)

        # 3. Task Shading
        self._add_task_shading(fig, family_cfg)
        
        # 4. Colored Segments for Omission (if applicable)
        if "X" in condition:
            onset = family_cfg['onset']
            # Baseline segment (-250 to 0 relative to om)
            base_mask = (self.time >= onset - 250) & (self.time < onset)
            fig.add_trace(go.Scatter(
                x=self.time[base_mask], y=smoothed[base_mask],
                mode='lines', line=dict(color=self.STYLE['baseline_color'], width=3),
                showlegend=False
            ), row=2, col=1)
            # Response segment (0 to 515 relative to om)
            resp_mask = (self.time >= onset) & (self.time <= onset + 515)
            fig.add_trace(go.Scatter(
                x=self.time[resp_mask], y=smoothed[resp_mask],
                mode='lines', line=dict(color=self.STYLE['response_color'], width=3),
                showlegend=False
            ), row=2, col=1)

        fig.update_layout(
            template="plotly_white",
            height=500,
            margin=dict(l=50, r=20, t=50, b=50),
            showlegend=True
        )
        fig.update_yaxes(title_text="Trial Index", row=1, col=1)
        fig.update_yaxes(title_text="Rate (Hz)", row=2, col=1)
        fig.update_xaxes(title_text="Time (ms)", row=2, col=1)
        
        return fig

    def _add_task_shading(self, fig, cfg):
        onsets = [0, 1031, 2062, 3093]
        om_onset = cfg['onset']
        for onset in onsets:
            color = self.STYLE['om_color'] if onset == om_onset else self.STYLE['stim_color']
            label = "Om" if onset == om_onset else "Stim"
            fig.add_vrect(x0=onset, x1=onset+515, fillcolor=color, layer="below", line_width=0, annotation_text=label)

    def _add_task_shading_to_subplot(self, fig, cfg, row, col):
        onsets = [0, 1031, 2062, 3093]
        om_onset = cfg['onset']
        for onset in onsets:
            color = "rgba(100, 100, 100, 0.1)" if onset == om_onset else "rgba(0, 100, 250, 0.1)"
            fig.add_vrect(x0=onset, x1=onset+515, fillcolor=color, layer="below", line_width=0, row=row, col=col)

def audit_mapping(df, loader):
    """Verifies anatomical mapping for all units in a dataframe."""
    results = []
    unique_ids = df['id'].unique()
    print(f"[action] Auditing mapping for {len(unique_ids)} unique units...")
    for unit_id in unique_ids:
        parts = unit_id.split('-')
        session = parts[0]
        probe = int(parts[1].replace('probe', ''))
        unit_idx = int(parts[2].replace('unit', ''))
        
        area, status, warn = loader.resolve_unit_area(session, probe, unit_idx, allow_heuristic=True)
        results.append({
            'id': unit_id,
            'session': session,
            'probe': probe,
            'unit_idx': unit_idx,
            'resolved_area': area,
            'mapping_status': status,
            'is_figure_grade': "metadata_resolved" in status,
            'warning': warn
        })
    return pd.DataFrame(results)

def run_f049():
    print(f"""[action] Starting Figure 49: Omission Profile production...""")
    plotter = OmissionPlotter()
    loader = plotter.loader
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = loader.get_output_dir("f049_omission_profiles") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load Audited Manifests from f048
    rep_df = pd.read_csv("outputs/oglo-8figs/f048-profile-analysis/repetition_profiles_spk.csv")
    om_df = pd.read_csv("outputs/oglo-8figs/f048-profile-analysis/omission_profiles_spk.csv")
    audit_df = pd.read_csv("outputs/oglo-8figs/f048-profile-analysis/repetition_audit_table.csv")

    # Use the hardened mapping status from f048 directly
    print(f"[action] Leveraging metadata audit from f048...")
    mapping_audit = pd.concat([
        rep_df[['id', 'session', 'probe', 'unit', 'resolved_area', 'mapping_status', 'is_figure_grade']],
        om_df[['id', 'session', 'probe', 'unit', 'resolved_area', 'mapping_status', 'is_figure_grade']]
    ]).drop_duplicates('id').rename(columns={'unit': 'unit_idx'})
    
    mapping_audit.to_csv(output_dir / "mapping_status_by_unit.csv", index=False)
    
    # Summary CSVs
    mapping_audit.groupby(['session', 'probe', 'mapping_status']).size().reset_index(name='count').to_csv(output_dir / "mapping_status_by_session_probe.csv", index=False)
    mapping_audit.groupby(['resolved_area', 'mapping_status']).size().reset_index(name='count').to_csv(output_dir / "mapping_status_by_area.csv", index=False)

    # 1. REPETITION EXEMPLARS
    print(f"""[action] Generating Repetition Exemplars (Metadata-Resolved only)...""")
    rep_families = ["AXAB", "BXBA", "RXRR"]
    fig_rep = make_subplots(
        rows=6, cols=2, 
        vertical_spacing=0.03, horizontal_spacing=0.05,
        row_heights=[0.1, 0.2, 0.1, 0.2, 0.1, 0.2],
        subplot_titles=["Facilitator", "Suppressor"] + [""]*10
    )

    for i, fam in enumerate(rep_families):
        fam_df = rep_df[rep_df['family'] == fam]
        
        # Priority: Metadata-resolved facilitators/suppressors
        figure_grade_df = fam_df[fam_df['is_figure_grade']]
        if figure_grade_df.empty:
            print(f"[warning] No figure-grade units found for family {fam}. Using best available.")
            figure_grade_df = fam_df
            
        fac = figure_grade_df.sort_values('p3_over_p1', ascending=False).iloc[0]
        sup = figure_grade_df.sort_values('p3_over_p1', ascending=True).iloc[0]
        
        for j, unit in enumerate([fac, sup]):
            col = j + 1
            row_raster = i * 2 + 1
            row_psth = i * 2 + 2
            
            spk = loader.load_unit_spikes(unit['id'], condition=fam)
            if spk is None: continue
            
            # Raster
            indices, times = np.where(spk > 0)
            fig_rep.add_trace(go.Scatter(
                x=plotter.time[times], y=indices,
                mode='markers', marker=dict(size=1, color='gray', opacity=0.3),
                showlegend=False
            ), row=row_raster, col=col)
            
            # PSTH
            rate = gaussian_filter1d(np.mean(spk, axis=0) * 1000, sigma=20)
            fig_rep.add_trace(go.Scatter(
                x=plotter.time, y=rate,
                mode='lines', line=dict(color='black', width=1.5),
                showlegend=False
            ), row=row_psth, col=col)
            
            plotter._add_task_shading_to_subplot(fig_rep, ProfileSearcher.OMISSION_FAMILIES['p2'], row_psth, col)
            
            # Label includes Mapping Status
            fig_rep.add_annotation(
                x=0.05, y=0.9, xref=f"x{row_psth if (row_psth*2 + col - 2) > 0 else ''} domain", 
                yref=f"y{row_psth if (row_psth*2 + col - 2) > 0 else ''} domain",
                text=f"{unit['id']}<br>{unit['resolved_area']}<br>({unit['mapping_status']})", 
                showarrow=False, align="left", font=dict(size=10)
            )

    fig_rep.update_layout(height=1200, width=1000, title_text=f"Repetition Scaling Profiles (Truth: {timestamp})", template="plotly_white")
    fig_rep.write_html(str(output_dir / "repetition_exemplars.html"))

    # 2. OMISSION EXEMPLARS
    print(f"""[action] Generating Omission Exemplars...""")
    fig_om = make_subplots(rows=6, cols=1, row_heights=[0.1, 0.2, 0.1, 0.2, 0.1, 0.2], vertical_spacing=0.05)
    
    for i, fam in enumerate(['p2', 'p3', 'p4']):
        f_df = om_df[om_df['family'] == fam]
        
        
        figure_grade_df = f_df[f_df['is_figure_grade']]
        if figure_grade_df.empty: figure_grade_df = f_df
        
        top = figure_grade_df.sort_values('effect_size', ascending=False).iloc[0]
        cfg = ProfileSearcher.OMISSION_FAMILIES[fam]
        
        row_raster = i * 2 + 1
        row_psth = i * 2 + 2
        
        om_spk = loader.load_unit_spikes(top['id'], condition=cfg['omission'][0])
        ctrl_spk = loader.load_unit_spikes(top['id'], condition=cfg['control'][0])
        
        if om_spk is not None:
            indices, times = np.where(om_spk > 0)
            fig_om.add_trace(go.Scatter(x=plotter.time[times], y=indices, mode='markers', marker=dict(size=1, color='gray', opacity=0.3), showlegend=False), row=row_raster, col=1)
            om_rate = gaussian_filter1d(np.mean(om_spk, axis=0) * 1000, sigma=20)
            fig_om.add_trace(go.Scatter(x=plotter.time, y=om_rate, mode='lines', line=dict(color='red', width=2), name='Omission'), row=row_psth, col=1)
            onset = cfg['onset']
            base_mask = (plotter.time >= onset - 250) & (plotter.time < onset)
            fig_om.add_trace(go.Scatter(x=plotter.time[base_mask], y=om_rate[base_mask], mode='lines', line=dict(color='orange', width=3), showlegend=False), row=row_psth, col=1)

        if ctrl_spk is not None:
            ctrl_rate = gaussian_filter1d(np.mean(ctrl_spk, axis=0) * 1000, sigma=20)
            fig_om.add_trace(go.Scatter(x=plotter.time, y=ctrl_rate, mode='lines', line=dict(color='black', dash='dash', width=1.5), name='Control'), row=row_psth, col=1)

        plotter._add_task_shading_to_subplot(fig_om, cfg, row_psth, 1)
        fig_om.add_annotation(x=0.05, y=0.9, xref=f"x{row_psth} domain", yref=f"y{row_psth} domain", text=f"{top['id']} {top['resolved_area']} ({top['mapping_status']})", showarrow=False)

    fig_om.update_layout(height=1000, width=800, title_text="Omission Selectivity Profiles", template="plotly_white")
    fig_om.write_html(str(output_dir / "omission_exemplars.html"))

    # 3. POPULATION SUMMARY (Metadata-Resolved only)
    print(f"""[action] Generating Population Summary (Metadata-Resolved only)...""")
    # Re-aggregate from audited rep_df
    figure_grade_rep = rep_df[rep_df['is_figure_grade']].copy()
    
    # Calculate counts (simple gt_1 / lt_1)
    figure_grade_rep['gt_1'] = figure_grade_rep['p3_over_p1'] > 1.0
    figure_grade_rep['lt_1'] = figure_grade_rep['p3_over_p1'] < 1.0
    
    fig_sum = go.Figure()
    areas = loader.CANONICAL_AREAS + ["V3"] # Include V3
    for area in areas:
        a_data = figure_grade_rep[figure_grade_rep['resolved_area'] == area]
        if a_data.empty: continue
        fig_sum.add_trace(go.Bar(x=[area], y=[a_data['gt_1'].sum()], name='Facilitation', marker_color='royalblue', showlegend=(area==areas[0])))
        fig_sum.add_trace(go.Bar(x=[area], y=[a_data['lt_1'].sum()], name='Suppression', marker_color='indianred', showlegend=(area==areas[0])))
    
    fig_sum.update_layout(barmode='group', title="Repetition Scaling by Area (Metadata Resolved)", template="plotly_white", xaxis_title="Area", yaxis_title="Unit Count")
    fig_sum.write_html(str(output_dir / "profile_population_summary.html"))

    # 4. MANIFEST
    try:
        git_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], encoding='utf8').strip()
    except Exception:
        git_head = "unknown"

    outputs = [f for f in output_dir.glob("*") if f.is_file() and f.name != "f049_manifest.json"]
    output_hashes = {}
    for out_file in outputs:
        with open(out_file, "rb") as f:
            output_hashes[out_file.name] = hashlib.sha256(f.read()).hexdigest()

    manifest = {
        'timestamp': timestamp,
        'script': "src/f049_omission_profiles/script.py",
        'repo_head': git_head,
        'truth_status': "truth_safe_unverified",
        'mapping_caveat': "local channel -> area is currently metadata_resolved_equal_segment (equal-segment inferred), not fully anatomical explicit-range",
        'inference_caveat': "higher-order omission claims are NOT manuscript-ready; they are analysis-hardened but still need session-aware hierarchy inference and anatomical confirmation",
        'figure_grade_inclusion_criteria': "metadata_resolved_*",
        'inclusion_statuses': ["metadata_resolved_equal_segment"],
        'excluded_statuses': ["heuristic_fallback", "unresolved_metadata", "unknown_area"],
        'inputs': {
            'repetition_profiles_spk': {"path": "outputs/oglo-8figs/f048-profile-analysis/repetition_profiles_spk.csv", "rows": len(rep_df)},
            'omission_profiles_spk': {"path": "outputs/oglo-8figs/f048-profile-analysis/omission_profiles_spk.csv", "rows": len(om_df)},
            'repetition_audit_table': {"path": "outputs/oglo-8figs/f048-profile-analysis/repetition_audit_table.csv", "rows": len(audit_df)}
        },
        'unit_counts': {
            'total_unique': len(mapping_audit),
            'figure_grade': int(mapping_audit['is_figure_grade'].sum()),
            'heuristic_fallback': int((mapping_audit['mapping_status'] == 'heuristic_fallback').sum()),
            'unresolved_metadata': int((mapping_audit['mapping_status'] == 'unresolved_metadata').sum()),
            'unknown_area': int((mapping_audit['mapping_status'] == 'unknown_area').sum())
        },
        'output_hashes': output_hashes
    }
    with open(output_dir / "f049_manifest.json", 'w') as f:
        json.dump(manifest, f, indent=4)

    print(f"""[action] Figure 49 generation complete. Manifest: {output_dir / 'f049_manifest.json'}""")

if __name__ == "__main__":
    run_f049()
