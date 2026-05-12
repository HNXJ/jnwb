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

def plot_conjunction_exemplar(loader, unit_id, area, stats_row, output_path):
    """Plots 3-panel trace figure: AXAB, BXBA, RXRR."""
    print(f"""[action] Plotting Conjunction Exemplar for {unit_id}...""")
    conditions = ["AXAB", "BXBA", "RXRR"]
    time = np.linspace(-1000, 4999, 6000)
    
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.02,
                        subplot_titles=conditions)
    
    for i, cond in enumerate(conditions):
        spk = loader.load_unit_spikes(unit_id, condition=cond)
        if spk is None: continue
        
        # Scale to Hz (cast to float to avoid uint8 overflow)
        spk_hz = spk.astype(float) * 1000
        mean_trace = np.mean(spk_hz, axis=0)
        sem_trace = np.std(spk_hz, axis=0) / np.sqrt(spk_hz.shape[0])
        
        # Smooth
        smooth_mean = gaussian_filter1d(mean_trace, sigma=20)
        smooth_upper = gaussian_filter1d(mean_trace + sem_trace, sigma=20)
        smooth_lower = gaussian_filter1d(mean_trace - sem_trace, sigma=20)
        
        # 1. SEM Band
        fig.add_trace(go.Scatter(
            x=np.concatenate([time, time[::-1]]),
            y=np.concatenate([smooth_upper, smooth_lower[::-1]]),
            fill='toself', fillcolor='rgba(0,0,0,0.1)', line=dict(color='rgba(255,255,255,0)'),
            showlegend=False
        ), row=1, col=i+1)
        
        # 2. Mean Trace
        fig.add_trace(go.Scatter(
            x=time, y=smooth_mean, mode='lines', line=dict(color='black', width=2),
            showlegend=False
        ), row=1, col=i+1)
        
        # 3. Task Windows
        onsets = [0, 1031, 2062, 3093]
        for onset in onsets:
            # Color Stim blue, Om (p2) gray
            color = "rgba(100,100,100,0.05)" if onset == 1031 else "rgba(0,100,250,0.05)"
            fig.add_vrect(x0=onset, x1=onset+515, fillcolor=color, layer="below", line_width=0, row=1, col=i+1)
        
        # Shaded p1/p3 markers
        fig.add_vrect(x0=0, x1=515, line=dict(color='green', width=1, dash='dot'), row=1, col=i+1)
        fig.add_vrect(x0=2062, x1=2577, line=dict(color='red', width=1, dash='dot'), row=1, col=i+1)
        
        # Annotation
        p1 = stats_row[f"{cond.lower()}_p1"]
        p3 = stats_row[f"{cond.lower()}_p3"]
        ratio = stats_row[f"{cond.lower()}_ratio"]
        # Plotly uses 'x domain' for the first axis, not 'x1 domain'
        xr = f"x{i+1 if i > 0 else ''} domain"
        fig.add_annotation(x=0.05, y=0.95, xref=xr, yref=f"y{i+1 if i > 0 else ''} domain",
                           text=f"p1={p1:.1f}Hz<br>p3={p3:.1f}Hz<br>Ratio={ratio:.2f}",
                           showarrow=False, align="left", font=dict(size=10))

    fig.update_layout(
        title=f"Conjunction Profile: {unit_id} ({area}) | Facilitates in AXAB+BXBA, Not in RXRR",
        template="plotly_white", height=400, width=1200,
        margin=dict(l=50, r=20, t=50, b=50)
    )
    fig.update_yaxes(title_text="Firing Rate (Hz)", row=1, col=1)
    fig.write_html(str(output_path))

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

from scipy.stats import wilcoxon, binomtest

def run_f050():
    print(f"""[action] Starting Figure 50: Conjunction Hardening Cycle...""")
    loader = DataLoader()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = loader.get_output_dir("f050_conjunction_profiles") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. LOAD DATA
    rep_path = "outputs/oglo-8figs/f048-profile-analysis/repetition_profiles_spk.csv"
    om_path = "outputs/oglo-8figs/f048-profile-analysis/omission_profiles_spk.csv"
    rep_df = pd.read_csv(rep_path)
    om_df = pd.read_csv(om_path)
    
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

    # Filter for Figure-Grade
    figure_grade_ids = mapping_audit[mapping_audit['is_figure_grade']]['id'].unique()
    print(f"[action] Restricted analysis to {len(figure_grade_ids)} figure-grade units.")
    
    # Identify Omission-Positive Units (Audit mapping)
    om_positive_ids = set(om_df[om_df['is_omission_positive'] & om_df['is_figure_grade']]['id'].unique())
    # 2. PIVOT & SCORE (Restricted to figure-grade)
    figure_grade_rep = rep_df[rep_df['id'].isin(figure_grade_ids)].copy()
    pivoted = figure_grade_rep.pivot(index=['id'], columns='family', values=['p1_value', 'p3_value', 'p3_over_p1'])
    pivoted.columns = [f"{col[1].lower()}_{col[0].replace('_value', '')}" for col in pivoted.columns]
    pivoted = pivoted.reset_index().rename(columns={
        'axab_p3_over_p1': 'axab_ratio',
        'bxba_p3_over_p1': 'bxba_ratio',
        'rxrr_p3_over_p1': 'rxrr_ratio'
    })
    # Add back area and status
    pivoted = pivoted.merge(mapping_audit[['id', 'resolved_area', 'mapping_status']], on='id')
    pivoted = pivoted.rename(columns={'resolved_area': 'area'})
    
    # Selectivity Score
    axab_diff = pivoted['axab_p3'] - pivoted['axab_p1']
    bxba_diff = pivoted['bxba_p3'] - pivoted['bxba_p1']
    rxrr_diff = pivoted['rxrr_p3'] - pivoted['rxrr_p1']
    pivoted['conjunction_score'] = np.minimum(axab_diff, bxba_diff) - np.maximum(0, rxrr_diff)
    
    # 3. TRIAL-LEVEL STATISTICAL HARDENING
    print(f"""[action] Running trial-level statistical hardening...""")
    target_units = pivoted[pivoted['axab_ratio'] > 1.0].id.unique()
    
    hardened_results = []
    for i, uid in enumerate(target_units):
        unit_stats = {'id': uid, 'p_axab': 1.0, 'p_bxba': 1.0, 'p_rxrr': 1.0}
        for cond in ['AXAB', 'BXBA', 'RXRR']:
            spk = loader.load_unit_spikes(uid, condition=cond)
            if spk is None or spk.shape[0] < 3: continue
            p1_trials = np.mean(spk[:, 1000:1515], axis=1)
            p3_trials = np.mean(spk[:, 3062:3577], axis=1)
            
            if np.all(p1_trials == p3_trials): 
                p = 1.0
            else:
                try:
                    res = wilcoxon(p3_trials, p1_trials, alternative='greater' if cond != 'RXRR' else 'two-sided')
                    p = res.pvalue
                except: p = 1.0
            unit_stats[f'p_{cond.lower()}'] = p
        hardened_results.append(unit_stats)
    if hardened_results:
        hardened_df = pd.DataFrame(hardened_results)
        pivoted = pivoted.merge(hardened_df, on='id', how='left')
    
    # 4. FINAL LOGICAL CLASSES
    pivoted['is_hardened'] = (pivoted['p_axab'] < 0.1) & (pivoted['p_bxba'] < 0.1) & (pivoted['p_rxrr'] > 0.05)
    pivoted['is_omission_overlap'] = pivoted['id'].isin(om_positive_ids)
    
    # 5. AREA ENRICHMENT & OVERLAP
    print(f"""[action] Computing Area Enrichment & Overlap (Figure-Grade only)...""")
    enrich_rows = []
    global_rate = pivoted['is_hardened'].sum() / len(pivoted) if not pivoted.empty else 0
    
    areas = loader.CANONICAL_AREAS + ["V3"]
    for area in areas:
        a_df = pivoted[pivoted['area'] == area]
        n_area = len(a_df)
        n_hard = a_df['is_hardened'].sum()
        n_overlap = a_df[a_df['is_hardened']]['is_omission_overlap'].sum()
        
        if n_area > 0 and global_rate > 0:
            res = binomtest(n_hard, n_area, global_rate, alternative='greater')
            p_enrich = res.pvalue
        else:
            p_enrich = 1.0
        
        enrich_rows.append({
            'area': area, 'n_total': n_area, 'n_hardened': n_hard,
            'enrichment_ratio': (n_hard/n_area) / global_rate if global_rate > 0 and n_area > 0 else 0,
            'p_enrich': p_enrich,
            'n_om_overlap': n_overlap,
            'overlap_prop': n_overlap / n_hard if n_hard > 0 else 0
        })
    enrich_df = pd.DataFrame(enrich_rows)
    enrich_df.to_csv(output_dir / "area_enrichment_hardened.csv", index=False)
    
    # 6. SUMMARY OUTPUTS
    pivoted.to_csv(output_dir / "conjunction_hardened_manifest.csv", index=False)
    
    # 7. SUMMARY FIGURE
    print(f"""[action] Generating Summary Figure...""")
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Area Enrichment", "Omission Overlap"])
    fig.add_trace(go.Bar(x=enrich_df['area'], y=enrich_df['enrichment_ratio'], marker_color='royalblue', name='Enrichment Ratio'), row=1, col=1)
    fig.add_trace(go.Bar(x=enrich_df['area'], y=enrich_df['overlap_prop'], marker_color='indianred', name='Omission Overlap %'), row=1, col=2)
    fig.update_layout(template="plotly_white", title=f"Conjunction Summary (Truth: {timestamp})", height=500)
    fig.write_html(str(output_dir / "conjunction_summary_hardened.html"))

    # 8. TOP 3 EXEMPLARS (Hardened + Scored)
    top_3 = pivoted[pivoted['is_hardened']].sort_values('conjunction_score', ascending=False).head(3)
    for i, (_, row) in enumerate(top_3.iterrows()):
        plot_conjunction_exemplar(loader, row['id'], row['area'], row, output_dir / f"hardened_exemplar_{i}_{row['id']}.html")

    # 9. MANIFEST
    try:
        git_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], encoding='utf8').strip()
    except Exception:
        git_head = "unknown"

    outputs = [f for f in output_dir.glob("*") if f.is_file() and f.name != "f050_manifest.json"]
    output_hashes = {f.name: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in outputs}

    manifest = {
        'timestamp': timestamp,
        'script': "src/f050_conjunction_profiles/script.py",
        'repo_head': git_head,
        'truth_status': "truth_safe_unverified",
        'mapping_caveat': "local channel -> area is currently metadata_resolved_equal_segment (equal-segment inferred), not fully anatomical explicit-range",
        'inference_caveat': "higher-order omission claims are NOT manuscript-ready; they are analysis-hardened but still need session-aware hierarchy inference and anatomical confirmation",
        'omission_position_pooling': "p2/p3/p4 positions are pooled for omission overlap metrics",
        'figure_grade_inclusion_criteria': "metadata_resolved_*",
        'inclusion_statuses': ["metadata_resolved_equal_segment"],
        'excluded_statuses': ["heuristic_fallback", "unresolved_metadata", "unknown_area"],
        'inputs': {
            'repetition_profiles_spk': {"path": rep_path, "rows": len(rep_df)},
            'omission_profiles_spk': {"path": om_path, "rows": len(om_df)}
        },
        'unit_counts': {
            'total_unique': len(mapping_audit),
            'figure_grade': int(mapping_audit['is_figure_grade'].sum()),
            'heuristic_fallback': int((mapping_audit['mapping_status'] == 'heuristic_fallback').sum()),
            'unresolved_metadata': int((mapping_audit['mapping_status'] == 'unresolved_metadata').sum()),
            'unknown_area': int((mapping_audit['mapping_status'] == 'unknown_area').sum()),
            'hardened_conjunctions': int(pivoted['is_hardened'].sum())
        },
        'output_hashes': output_hashes
    }
    with open(output_dir / "f050_manifest.json", 'w') as f:
        json.dump(manifest, f, indent=4)

    print(f"""[action] Figure 50 Hardening Complete. Manifest: {output_dir / 'f050_manifest.json'}""")

if __name__ == "__main__":
    run_f050()
