"""
Replicate Published Raster Suite Figure Using Only jNWB

Target: o_positive_real_omission_FEF_ses230823_unit53_aligned_suite.svg

Original structure from reproduce_all_visual_reviews.ipynb:
- 3 panels (one per family: A, B, R)
- Each panel stacks all trials from each condition, colored by condition
- Limited to 15 trials per condition (not min_trials)
- Aligned to p1 (stimulus_number=2)
- Window: -1000 to 3000 ms
"""

import logging
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from omission import read
from omission.jnwb_ext.functions import raster_plot

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Define families and their conditions/colors (from original)
FAMILIES = {
    "A": {
        "conds": ["AAAB", "AXAB", "AAXB", "AAAX"],
        "colors": {"AAAB": "#1565C0", "AXAB": "#4CAF50", "AAXB": "#FF9800", "AAAX": "#E53935"},
    },
    "B": {
        "conds": ["BBBA", "BXBA", "BBXA", "BBBX"],
        "colors": {"BBBA": "#00ACC1", "BXBA": "#8E24AA", "BBXA": "#FFB300", "BBBX": "#D81B60"},
    },
    "R": {
        "conds": ["RRRR", "RXRR", "RRXR", "RRRX"],
        "colors": {"RRRR": "#E5D429", "RXRR": "#0E9F58", "RRXR": "#3E9BE5", "RRRX": "#D9541F"},
    },
}


def replicate_raster_suite():
    """
    Replicate raster suite using ONLY jnwb.raster_plot

    Structure:
    - 3 subplots (one per family)
    - Each subplot shows all conditions stacked with color coding
    - Up to 15 trials per condition
    - Aligned to p1 (stimulus_number=2)
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
    # 2. GET RASTER DATA FOR EACH CONDITION
    # ─────────────────────────────────────────────────────────────────

    unit_id = 53
    phase = 2  # p1 - alignment anchor
    window_ms = (-1000, 3000)  # Original uses -1000 to 3000

    rasters = {}
    all_conditions = []

    for fam_name, fam_cfg in FAMILIES.items():
        for cond in fam_cfg["conds"]:
            all_conditions.append(cond)
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
    # 3. CREATE FIGURE: 3-Panel Layout (one per family)
    # ─────────────────────────────────────────────────────────────────

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), facecolor='white')

    for ax_idx, (fam_name, fam_cfg) in enumerate(FAMILIES.items()):
        ax = axes[ax_idx]
        y_offset = 0

        # For each condition in this family
        for cond in fam_cfg["conds"]:
            raster_data = rasters[cond]['raster_data']

            # Group spikes by trial
            spikes_by_trial = defaultdict(list)
            for spike_entry in raster_data:
                spikes_by_trial[spike_entry['trial_id']].append(spike_entry['spike_time_ms'])

            # Limit to 15 trials per condition (as in original)
            trial_ids = sorted(spikes_by_trial.keys())[:15]
            n_trials_in_cond = len(trial_ids)

            # Plot vlines for each trial (stacked vertically with y_offset)
            for idx, trial_id in enumerate(trial_ids):
                trial_spikes = spikes_by_trial[trial_id]
                ax.vlines(trial_spikes, y_offset + idx, y_offset + idx + 0.8,
                         color=fam_cfg["colors"][cond], linewidth=1.2)

            y_offset += n_trials_in_cond

        # Format subplot
        ax.set_title(f"{fam_name} Conditions Family", fontsize=10, fontweight='bold')
        ax.set_xlim(-1000, 3000)
        ax.set_ylabel('Trials', fontsize=9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()

    # ─────────────────────────────────────────────────────────────────
    # 4. SAVE FIGURE
    # ─────────────────────────────────────────────────────────────────

    output_dir = Path("D:/workspace/omission/outputs/jnwb_replications")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "o_positive_real_omission_FEF_ses230823_unit53_aligned_suite.svg"

    fig.savefig(output_path, format='svg', bbox_inches='tight')
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
        log.info("  - A/B/R Family conditions")
        log.info("  - Aligned to p1 onset (-1000 to 3000 ms)")
        log.info("  - 3-panel layout (one per family)")
        log.info("="*80)
        return 0
    else:
        log.error("FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
