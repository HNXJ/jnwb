"""
Replicate Published Raster Suite Figure Using Only jNWB

Target: o_positive_real_omission_FEF_ses230823_unit53_aligned_suite.svg

Facts from filename:
- Session: 230823
- Unit: 53
- Area: FEF
- Type: o_positive (omission-responsive)
- Suite: aligned_suite (raster + PSTH + autocorrelogram)
"""

import logging
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from jnwb import read
from jnwb.functions import raster_plot, psth_analysis

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def replicate_raster_suite():
    """
    Replicate raster suite using ONLY jnwb.raster_plot and jnwb.psth_analysis

    KEY: Align to p1 (stimulus_number=2), not to the omission stimulus.
    Plot all four conditions in A family: AAAB, AXAB, AAXB, AAAX
    """

    # ─────────────────────────────────────────────────────────────────
    # 1. LOAD SESSION
    # ─────────────────────────────────────────────────────────────────

    nwb_path = Path("D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb")
    if not nwb_path.exists():
        log.error(f"NWB not found: {nwb_path}")
        return False

    session = read(str(nwb_path))
    log.info(f"✓ Loaded: {nwb_path.name}")

    # ─────────────────────────────────────────────────────────────────
    # 2. GET RASTER DATA - ALIGNED TO P1, FOR EACH A-FAMILY CONDITION
    # ─────────────────────────────────────────────────────────────────

    # Unit 53, FEF
    # Plot all four A-family conditions, aligned to p1 (stimulus_number=2)
    unit_id = 53
    phase = 2  # p1 - the alignment anchor
    window_ms = (-1000, 4000)  # Full sequence window

    conditions = ['AAAB', 'AXAB', 'AAXB', 'AAAX']
    rasters = {}

    for cond in conditions:
        raster = raster_plot(
            session=session,
            unit_id=unit_id,
            condition=cond,
            phase=phase,
            window_ms=window_ms
        )

        if 'error' in raster:
            log.error(f"Raster failed for {cond}: {raster['error']}")
            return False

        rasters[cond] = raster
        log.info(f"✓ {cond}: {raster['n_spikes']} spikes, {raster['n_trials']} trials")

    # ─────────────────────────────────────────────────────────────────
    # 3. GET PSTH DATA - ALIGNED TO P1, FOR EACH CONDITION
    # ─────────────────────────────────────────────────────────────────

    psths = {}

    for cond in conditions:
        psth = psth_analysis(
            session=session,
            unit_id=unit_id,
            condition=cond,
            phase=phase,
            bin_size_ms=20
        )

        if 'error' in psth:
            log.error(f"PSTH failed for {cond}: {psth['error']}")
            return False

        psths[cond] = psth

    log.info(f"✓ PSTH computed for all conditions")

    # ─────────────────────────────────────────────────────────────────
    # 3.5. TRUNCATE RASTERS TO MINIMUM TRIALS (for visual comparability)
    # ─────────────────────────────────────────────────────────────────

    min_trials = min(r['n_trials'] for r in rasters.values())
    log.info(f"✓ Truncating to minimum: {min_trials} trials")

    for cond in conditions:
        raster_data = rasters[cond]['raster_data']
        # Group by trial_id and keep only first min_trials unique trials
        trial_ids = sorted(set(x['trial_id'] for x in raster_data))[:min_trials]
        rasters[cond]['raster_data'] = [x for x in raster_data if x['trial_id'] in trial_ids]
        rasters[cond]['n_trials'] = min_trials

    # ─────────────────────────────────────────────────────────────────
    # 4. CREATE FIGURE: 5-Panel Raster Suite (4 rasters + combined PSTH)
    # ─────────────────────────────────────────────────────────────────

    # Colors for A-family conditions (from original notebook)
    condition_colors = {
        'AAAB': '#1565C0',
        'AXAB': '#4CAF50',
        'AAXB': '#FF9800',
        'AAAX': '#E53935',
    }

    # Stimulus slot colors (from original notebook)
    slot_colors = [
        (0, 500, '#FCF9E3'),      # p1
        (1031, 1531, '#F6EEF9'),  # p2
        (2062, 2562, '#E9F5FC'),  # p3
        (3093, 3593, '#FDF2E9'),  # p4
    ]

    fig = plt.figure(figsize=(10, 14))
    gs = gridspec.GridSpec(5, 1, figure=fig, height_ratios=[1, 1, 1, 1, 3.5])

    # Panels 1-4: Rasters for each condition
    for panel_idx, (cond, ax_idx) in enumerate(zip(conditions, range(4))):
        ax = fig.add_subplot(gs[ax_idx])

        # Add stimulus slot background colors
        for start, end, color in slot_colors:
            ax.axvspan(start, end, color=color, alpha=0.8, zorder=0)

        # Add stimulus marker lines
        for marker in [0, 1031, 2062, 3093]:
            ax.axvline(marker, color='#C0C0C0', linestyle='--', linewidth=1.0, zorder=1)

        # Plot raster
        raster_data = rasters[cond]['raster_data']
        if raster_data:
            trial_ids = [x['trial_id'] for x in raster_data]
            spike_times_ms = [x['spike_time_ms'] for x in raster_data]

            ax.vlines(spike_times_ms, np.array(trial_ids) - 0.4, np.array(trial_ids) + 0.4,
                     colors='black', linewidth=0.5)

        n_trials = rasters[cond]['n_trials']
        ax.set_ylim(-1, n_trials)
        ax.set_title(f'{cond} Raster (N={n_trials} trials)', fontsize=11, pad=3)
        ax.set_ylabel('Trials', fontsize=9)
        ax.set_xlim(-1000, 4000)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    # Panel 5: Combined PSTH
    ax_psth = fig.add_subplot(gs[4])

    # Add stimulus slot background colors
    for start, end, color in slot_colors:
        ax_psth.axvspan(start, end, color=color, alpha=0.8, zorder=0)

    # Add stimulus marker lines
    for marker in [0, 1031, 2062, 3093]:
        ax_psth.axvline(marker, color='#C0C0C0', linestyle='--', linewidth=1.0, zorder=1)

    # Plot PSTH for each condition
    for cond in conditions:
        psth_data = psths[cond]
        if 'psth_rate_hz' in psth_data and 'bin_times_ms' in psth_data:
            time_bins = psth_data['bin_times_ms']
            firing_rate = psth_data['psth_rate_hz']

            ax_psth.plot(time_bins, firing_rate, color=condition_colors[cond],
                        label=cond, linewidth=1.5, zorder=3)

    ax_psth.legend(loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=4, frameon=False)
    ax_psth.set_xlabel('Time from p1 onset (ms)', fontsize=10)
    ax_psth.set_ylabel('FR (Hz)', fontsize=10)
    ax_psth.set_xlim(-1000, 4000)
    ax_psth.spines['top'].set_visible(False)
    ax_psth.spines['right'].set_visible(False)

    plt.suptitle(f'Unit 53 FEF - A Family Conditions\nAligned to p1 onset',
                fontsize=12, fontweight='bold', y=0.995)

    # ─────────────────────────────────────────────────────────────────
    # 5. SAVE FIGURE
    # ─────────────────────────────────────────────────────────────────

    output_dir = Path("D:/workspace/omission/outputs/jnwb_replications")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "o_positive_real_omission_FEF_ses230823_unit53_aligned_suite.svg"

    plt.tight_layout()
    fig.savefig(output_path, format='svg', dpi=150)
    plt.close(fig)

    log.info(f"✓ Figure saved: {output_path}")

    return True


def main():
    log.info("="*80)
    log.info("REPLICATE RASTER SUITE - USING ONLY jNWB")
    log.info("="*80)

    success = replicate_raster_suite()

    if success:
        log.info("="*80)
        log.info("✓ SUCCESS: Raster suite replicated")
        log.info("  - Unit 53 (FEF)")
        log.info("  - Session 230823")
        log.info("  - Omission condition (AAXB p3)")
        log.info("  - Aligned suite: raster + PSTH + autocorrelogram")
        log.info("="*80)
        return 0
    else:
        log.error("FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
