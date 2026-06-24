#!/usr/bin/env python3
"""
SPECTRAL-RELATIONS PIPELINE: NETWORK VISUALIZATION & GRAPH MODULE

Comprehensive visualization suite for spectral network analysis:
- Network graphs with connection strength visualization
- Comparison heatmaps and panels
- Lead time distributions and temporal hierarchies
- Cross-modal network overlays

Author: Claude Code
Date: 2025-06-23
"""

import logging
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
from matplotlib.collections import LineCollection
import networkx as nx
from itertools import combinations

log = logging.getLogger(__name__)

# Styling
COLORS = {
    'V1': '#1f77b4',
    'V3': '#ff7f0e',
    'V4': '#2ca02c',
    'MT': '#d62728',
    'MST': '#9467bd',
    'PFC': '#8c564b',
    'FEF': '#e377c2',
}

BAND_COLORS = {
    'theta': '#e74c3c',
    'alpha': '#3498db',
    'beta': '#2ecc71',
    'low_gamma': '#f39c12',
    'high_gamma': '#9b59b6',
}

CONDITION_ORDER = [
    'stimulus',
    'baseline_pre_stim',
    'baseline_pre_omission',
    'omission',
    'baseline_post_omission',
]

# ============================================================================
# NETWORK GRAPH VISUALIZATION
# ============================================================================

class NetworkGraphVisualizer:
    """Create and visualize network graphs."""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.figs_dir = results_dir / 'figures'
        self.figs_dir.mkdir(exist_ok=True)

    def create_spectral_network_graph(self, df: pd.DataFrame, band: str, condition: str):
        """Create network graph for spectral correlations."""
        subset = df[(df['band'] == band) & (df['condition'] == condition)]

        if len(subset) == 0:
            return None

        # Filter to significant correlations
        sig_subset = subset[subset['significant']]

        if len(sig_subset) == 0:
            return None

        # Create graph
        G = nx.Graph()

        # Add nodes (areas)
        areas = set(sig_subset['area1'].unique()) | set(sig_subset['area2'].unique())
        for area in areas:
            G.add_node(area)

        # Add edges (correlations as weights)
        for _, row in sig_subset.iterrows():
            weight = abs(row['correlation'])
            G.add_edge(row['area1'], row['area2'], weight=weight,
                      correlation=row['correlation'], z_score=row['z_score'])

        # Visualize
        fig, ax = plt.subplots(figsize=(10, 10))

        # Layout
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

        # Draw edges with width proportional to correlation strength
        edges = G.edges()
        weights = [G[u][v]['weight'] for u, v in edges]
        max_weight = max(weights) if weights else 1.0

        for (u, v), weight in zip(edges, weights):
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                   'gray', alpha=0.3 + 0.7*weight/max_weight,
                   linewidth=1 + 3*weight/max_weight, zorder=1)

        # Draw nodes
        for node in G.nodes():
            ax.scatter(pos[node][0], pos[node][1], s=2000,
                      c=COLORS.get(node, '#555555'),
                      edgecolors='black', linewidths=2, zorder=2)
            ax.text(pos[node][0], pos[node][1], node,
                   ha='center', va='center', fontsize=12, fontweight='bold', zorder=3)

        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.axis('off')
        ax.set_title(f'{band} band — {condition}\n({len(sig_subset)} significant pairs)',
                    fontsize=14, fontweight='bold')

        plt.tight_layout()
        return fig

    def create_network_grid(self, df: pd.DataFrame):
        """Create 5×5 grid of networks (bands × conditions)."""
        bands = ['theta', 'alpha', 'beta', 'low_gamma', 'high_gamma']

        fig = plt.figure(figsize=(20, 20))
        gs = gridspec.GridSpec(5, 5, figure=fig, hspace=0.3, wspace=0.3)

        for band_idx, band in enumerate(bands):
            for cond_idx, condition in enumerate(CONDITION_ORDER):
                ax = fig.add_subplot(gs[band_idx, cond_idx])

                subset = df[(df['band'] == band) & (df['condition'] == condition)]
                sig_subset = subset[subset['significant']]

                if len(sig_subset) == 0:
                    ax.text(0.5, 0.5, 'No significant\npairs',
                           ha='center', va='center', transform=ax.transAxes)
                    ax.set_xlim(-1, 1)
                    ax.set_ylim(-1, 1)
                else:
                    # Create graph
                    G = nx.Graph()
                    areas = set(sig_subset['area1'].unique()) | set(sig_subset['area2'].unique())
                    for area in areas:
                        G.add_node(area)

                    for _, row in sig_subset.iterrows():
                        G.add_edge(row['area1'], row['area2'],
                                 weight=abs(row['correlation']))

                    # Layout
                    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

                    # Draw edges
                    edges = list(G.edges())
                    weights = [G[u][v]['weight'] for u, v in edges]
                    max_weight = max(weights) if weights else 1.0

                    for (u, v), weight in zip(edges, weights):
                        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                               'gray', alpha=0.3 + 0.7*weight/max_weight,
                               linewidth=0.5 + 2*weight/max_weight, zorder=1)

                    # Draw nodes
                    for node in G.nodes():
                        ax.scatter(pos[node][0], pos[node][1], s=300,
                                  c=COLORS.get(node, '#555555'),
                                  edgecolors='black', linewidths=1, zorder=2)
                        ax.text(pos[node][0], pos[node][1], node,
                               ha='center', va='center', fontsize=8, zorder=3)

                ax.set_xlim(-1.5, 1.5)
                ax.set_ylim(-1.5, 1.5)
                ax.axis('off')
                ax.set_title(f'{band} | {condition}', fontsize=10)

        fig.savefig(self.figs_dir / 'spectral_networks_grid.png', dpi=150, bbox_inches='tight')
        log.info(f"✓ Saved network grid: spectral_networks_grid.png")
        plt.close(fig)

    def create_spike_network_graph(self, df: pd.DataFrame, session: int = None):
        """Create network graph for spike correlations."""
        if session:
            subset = df[df['session'] == session]
        else:
            subset = df

        sig_subset = subset[subset['significant']]

        if len(sig_subset) < 10:
            return None

        # Create graph
        G = nx.Graph()
        units = set(sig_subset['unit1'].unique()) | set(sig_subset['unit2'].unique())

        for unit in list(units)[:50]:  # Limit for visualization
            G.add_node(unit)

        # Add edges
        for _, row in sig_subset.iterrows():
            if row['unit1'] in G and row['unit2'] in G:
                G.add_edge(row['unit1'], row['unit2'], weight=abs(row['correlation']))

        # Visualize
        fig, ax = plt.subplots(figsize=(12, 12))

        pos = nx.spring_layout(G, k=1, iterations=50, seed=42)

        # Draw edges
        edges = G.edges()
        weights = [G[u][v]['weight'] for u, v in edges]
        max_weight = max(weights) if weights else 1.0

        for (u, v), weight in zip(edges, weights):
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                   'gray', alpha=0.2 + 0.8*weight/max_weight,
                   linewidth=0.5 + 2*weight/max_weight, zorder=1)

        # Draw nodes
        for node in G.nodes():
            ax.scatter(pos[node][0], pos[node][1], s=100,
                      c='#3498db', edgecolors='black', linewidths=0.5, zorder=2)

        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.axis('off')
        ax.set_title(f'Spike Network - {len(sig_subset)} significant unit pairs',
                    fontsize=14, fontweight='bold')

        plt.tight_layout()
        return fig


# ============================================================================
# COMPARISON VISUALIZATIONS
# ============================================================================

class ComparisonVisualizer:
    """Create comparison panels and heatmaps."""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.figs_dir = results_dir / 'figures'
        self.figs_dir.mkdir(exist_ok=True)

    def create_band_comparison_heatmap(self, df: pd.DataFrame):
        """Create heatmap: bands × conditions → significance strength."""
        bands = ['theta', 'alpha', 'beta', 'low_gamma', 'high_gamma']

        # Build matrix
        heatmap_data = np.zeros((len(bands), len(CONDITION_ORDER)))

        for band_idx, band in enumerate(bands):
            for cond_idx, condition in enumerate(CONDITION_ORDER):
                subset = df[(df['band'] == band) & (df['condition'] == condition)]
                if len(subset) > 0:
                    heatmap_data[band_idx, cond_idx] = (
                        subset['z_score'].abs().mean() if len(subset) > 0 else 0
                    )

        # Plot
        fig, ax = plt.subplots(figsize=(12, 6))

        im = ax.imshow(heatmap_data, cmap='hot', aspect='auto')

        ax.set_xticks(range(len(CONDITION_ORDER)))
        ax.set_xticklabels(CONDITION_ORDER, rotation=45, ha='right')
        ax.set_yticks(range(len(bands)))
        ax.set_yticklabels(bands)

        ax.set_xlabel('Condition', fontsize=12, fontweight='bold')
        ax.set_ylabel('Frequency Band', fontsize=12, fontweight='bold')
        ax.set_title('Spectral Network Strength (Mean |z-score|)', fontsize=14, fontweight='bold')

        plt.colorbar(im, ax=ax, label='Mean |z-score|')

        for band_idx in range(len(bands)):
            for cond_idx in range(len(CONDITION_ORDER)):
                ax.text(cond_idx, band_idx, f'{heatmap_data[band_idx, cond_idx]:.2f}',
                       ha='center', va='center', color='white', fontsize=10)

        plt.tight_layout()
        fig.savefig(self.figs_dir / 'band_comparison_heatmap.png', dpi=150, bbox_inches='tight')
        log.info(f"✓ Saved band comparison heatmap")
        plt.close(fig)

    def create_lead_time_timeline(self, df: pd.DataFrame):
        """Create temporal hierarchy visualization."""
        fig, axes = plt.subplots(2, 1, figsize=(14, 8))

        # By band
        bands = ['theta', 'alpha', 'beta', 'low_gamma', 'high_gamma']
        band_leads = []

        for band in bands:
            subset = df[df['band1'] == band]
            if len(subset) > 0:
                mean_lag = subset['lag_ms'].mean()
                band_leads.append((band, mean_lag))

        if band_leads:
            band_names, lags = zip(*sorted(band_leads, key=lambda x: x[1]))
            colors = [BAND_COLORS.get(b, '#999999') for b in band_names]

            axes[0].barh(band_names, lags, color=colors, edgecolor='black', linewidth=2)
            axes[0].axvline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)
            axes[0].set_xlabel('Lead Time (ms)', fontsize=12, fontweight='bold')
            axes[0].set_title('Temporal Hierarchy: Band-wise Lead Times', fontsize=13, fontweight='bold')
            axes[0].grid(axis='x', alpha=0.3)

        # Distribution
        valid_lags = df['lag_ms'].dropna()
        if len(valid_lags) > 0:
            axes[1].hist(valid_lags, bins=30, color='steelblue', edgecolor='black', alpha=0.7)
            axes[1].axvline(valid_lags.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {valid_lags.mean():.1f}ms')
            axes[1].axvline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)
            axes[1].set_xlabel('Lead Time (ms)', fontsize=12, fontweight='bold')
            axes[1].set_ylabel('Frequency', fontsize=12, fontweight='bold')
            axes[1].set_title('Lead Time Distribution', fontsize=13, fontweight='bold')
            axes[1].legend()
            axes[1].grid(axis='y', alpha=0.3)

        plt.tight_layout()
        fig.savefig(self.figs_dir / 'lead_time_timeline.png', dpi=150, bbox_inches='tight')
        log.info(f"✓ Saved lead time timeline")
        plt.close(fig)

    def create_cross_modal_comparison(self, q1_df: pd.DataFrame, q2_df: pd.DataFrame):
        """Create LFP vs spike network comparison."""
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Correlation distributions
        if len(q1_df) > 0:
            axes[0].hist(q1_df['correlation'].dropna(), bins=30, alpha=0.6,
                        label='Spectral (LFP)', color='blue', edgecolor='black')
        if len(q2_df) > 0:
            axes[0].hist(q2_df['correlation'].dropna(), bins=30, alpha=0.6,
                        label='Spike', color='red', edgecolor='black')

        axes[0].set_xlabel('Correlation Coefficient (Rho)', fontsize=12, fontweight='bold')
        axes[0].set_ylabel('Frequency', fontsize=12, fontweight='bold')
        axes[0].set_title('Spectral vs. Spike Network Correlations', fontsize=13, fontweight='bold')
        axes[0].legend(fontsize=11)
        axes[0].grid(axis='y', alpha=0.3)

        # Z-score distributions
        if len(q1_df) > 0:
            axes[1].hist(q1_df['z_score'].dropna(), bins=30, alpha=0.6,
                        label='Spectral (LFP)', color='blue', edgecolor='black')
        if len(q2_df) > 0:
            axes[1].hist(q2_df['z_score'].dropna(), bins=30, alpha=0.6,
                        label='Spike', color='red', edgecolor='black')

        axes[1].set_xlabel('Z-score', fontsize=12, fontweight='bold')
        axes[1].set_ylabel('Frequency', fontsize=12, fontweight='bold')
        axes[1].set_title('Statistical Effect Sizes', fontsize=13, fontweight='bold')
        axes[1].axvline(1.96, color='green', linestyle='--', linewidth=2, alpha=0.7, label='Threshold (z=1.96)')
        axes[1].legend(fontsize=11)
        axes[1].grid(axis='y', alpha=0.3)

        plt.tight_layout()
        fig.savefig(self.figs_dir / 'cross_modal_comparison.png', dpi=150, bbox_inches='tight')
        log.info(f"✓ Saved cross-modal comparison")
        plt.close(fig)


# ============================================================================
# MAIN
# ============================================================================

def generate_all_visualizations(results_dir: Path):
    """Generate complete visualization suite."""
    log.info("\n" + "=" * 80)
    log.info("GENERATING COMPREHENSIVE VISUALIZATIONS")
    log.info("=" * 80)

    # Load results
    q1_file = results_dir / 'q1_spectral_networks_full.csv'
    q2_file = results_dir / 'q2_spike_networks_full.csv'
    q3_file = results_dir / 'q3_lead_times_full.csv'

    q1_df = pd.read_csv(q1_file) if q1_file.exists() else pd.DataFrame()
    q2_df = pd.read_csv(q2_file) if q2_file.exists() else pd.DataFrame()
    q3_df = pd.read_csv(q3_file) if q3_file.exists() else pd.DataFrame()

    # Network graphs
    net_viz = NetworkGraphVisualizer(results_dir)
    if len(q1_df) > 0:
        net_viz.create_network_grid(q1_df)
    if len(q2_df) > 0:
        fig = net_viz.create_spike_network_graph(q2_df)
        if fig:
            fig.savefig(results_dir / 'figures' / 'spike_network_graph.png', dpi=150, bbox_inches='tight')
            plt.close(fig)

    # Comparison visualizations
    comp_viz = ComparisonVisualizer(results_dir)
    if len(q1_df) > 0:
        comp_viz.create_band_comparison_heatmap(q1_df)
    if len(q3_df) > 0:
        comp_viz.create_lead_time_timeline(q3_df)
    if len(q1_df) > 0 or len(q2_df) > 0:
        comp_viz.create_cross_modal_comparison(q1_df, q2_df)

    log.info("=" * 80)
    log.info("VISUALIZATIONS COMPLETE")
    log.info("=" * 80)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    results_dir = Path("D:/workspace/omission/outputs/spectral_relations_pipeline/results")
    generate_all_visualizations(results_dir)
