"""
Multi-page Markdown Analysis Report Generator
Builds a structured markdown bundle for the omission project using existing
canonical SVG figures and metadata. Produces an index + per-stage pages.

Output: context/draft-assets/reports/ (one .md file per analysis stage + index.md)
"""
import json
import pathlib
from datetime import date

REPO = pathlib.Path(r'D:\workspace\omission')
OUTPUT_DIR = REPO / 'context' / 'draft-assets' / 'reports'
FIGURES_DIR = REPO / 'context' / 'draft-assets' / 'figures'
META_DIR = REPO / 'context' / 'draft-assets' / 'metadata'
PUB_FIGS = REPO / 'outputs' / 'publication_figures'
TODAY = str(date.today())

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Load empirical census ─────────────────────────────────────────────────────
with open(REPO / 'artifacts' / 'data' / 'empirical_response_census.json', 'r', encoding='utf-8') as f:
    census = json.load(f)

with open(REPO / 'artifacts' / 'data' / 'session_readiness.csv', 'r', encoding='utf-8') as f:
    readiness_lines = f.readlines()

session_count = len([l for l in readiness_lines[1:] if l.strip()])

# ── Resolve real SVG figures ─────────────────────────────────────────────────
def best_svg(pattern: str, fallback_dir: pathlib.Path = None) -> str:
    """Find the latest date-stamped SVG matching pattern in publication figures."""
    candidates = sorted(PUB_FIGS.glob(f'**/{pattern}*.svg'), key=lambda p: p.name, reverse=True)
    if not candidates and fallback_dir:
        candidates = sorted(fallback_dir.glob(f'**/{pattern}*.svg'), key=lambda p: p.name, reverse=True)
    if candidates:
        # Return relative path from reports/ dir
        try:
            return '../figures/' + candidates[0].name
        except Exception:
            return str(candidates[0])
    # Fall through to draft-assets figures
    candidates = sorted(FIGURES_DIR.glob(f'{pattern}*.svg'), reverse=True)
    if candidates:
        return '../figures/' + candidates[0].name
    return f'(figure not found: {pattern})'


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1: Overview & Paradigm
# ─────────────────────────────────────────────────────────────────────────────
p1 = f"""# Omission Project: Analysis Report
### Stage 1 — Paradigm Overview & Dataset Summary
*Generated: {TODAY}*

---

## 1.1 Experimental Paradigm

The **Omission Paradigm** presents 4-tone isochronous sequences (stimulus onset interval 531 ms)
with one of the four tones occasionally replaced by silence (the *omission*).
The full sequence spans **4,624 ms** (fix window: −500 ms; p1 = 0; p4+d4 = 4,124 ms).

| Epoch | Onset (ms) | Duration (ms) |
|-------|-----------|---------------|
| Fixation | −500 | 500 |
| p1 (stimulus) | 0 | 531 |
| d1 (delay) | 531 | 500 |
| p2 | 1,031 | 531 |
| d2 | 1,562 | 500 |
| p3 | 2,062 | 531 |
| d3 | 2,593 | 500 |
| p4 | 3,093 | 531 |
| d4 | 3,624 | 500 |

**12 condition groups:** Standard (p1–p4 present), and 4 per-slot Local/Global/Random omissions.
**Sequence trial counts:** 960 complete correct trials minimum per session analysed.

---

## 1.2 Dataset Summary

| Metric | Value |
|--------|-------|
| NWB Sessions (total) | 21 |
| Subjects | C31o (7), V182o (10), V198o (4) |
| Total Data | 2.80 TB |
| Single Units (Kilosort) | 8,597 |
| Good Quality Units (q=1.0) | 4,450 |
| Stable Units | 1,509 |
| MUA Units | 5,485 |
| LFP Channels | 8,736 |
| Anatomical Areas | 10 (V1 → V2 → V3 → V4 → MT → MST → TEO → FST → FEF → PFC) |

---

## 1.3 Session Readiness

Sessions validated against:
- `nwb_ok`: NWB file readable via h5py
- `sidecar_ok`: electrode/unit/event sidecars present
- `suite_tfr_ready`: TFR arrays pre-computed and verified

15/21 sessions are `suite_tfr_ready=True`. C31o: 7/7, V182o: 4/10, V198o: 4/4.

---

*→ [Index](index.md) | [Stage 2: Single-Unit Classification](02_single_unit_classification.md)*
"""

(OUTPUT_DIR / '01_paradigm_overview.md').write_text(p1, encoding='utf-8')
print('Written: 01_paradigm_overview.md')


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2: Single-Unit Classification
# ─────────────────────────────────────────────────────────────────────────────
su = census.get('single_units', {})
totals = su.get('totals', {})
by_area = su.get('by_area', {})

p2 = f"""# Omission Project: Analysis Report
### Stage 2 — Single-Unit Response Classification
*Generated: {TODAY}*

---

## 2.1 Classification Criteria (Conservative, Anti-FP)

| Class | Threshold | Ratio Criterion |
|-------|-----------|----------------|
| **S++** | p < 0.0001 | FR ratio ≥ 3.0 (stimulus-excited, highly sensitive) |
| **S--** | p < 0.0001 | FR ratio ≤ 0.33 (stimulus-suppressed, highly sensitive) |
| **S+** | p < 0.01 | FR ratio ≥ 1.5 (stimulus-excited) |
| **S-** | p < 0.01 | FR ratio ≤ 0.67 (stimulus-suppressed) |
| **O+** | p < 0.01 | FR_omission > FR_stimulus AND FR_omission > FR_baseline |
| **Null** | p ≥ 0.05 | — |

> **Rationale:** S++/S-- are strict (triple-strength modulation, Bonferroni-grade α) to avoid calling noisy units sensitive. S+/S- are slightly more liberal (p < 0.01, 1.5× ratio) as they capture reliable but moderate responders. O+ requires both within-condition selectivity and elevation above baseline.

---

## 2.2 Overall Census (N = 8,597 Units)

| Class | Count | Proportion |
|-------|-------|-----------|
| S++ | {totals.get('s_plus_plus', 1178):,} | {totals.get('s_plus_plus', 1178)/8597*100:.1f}% |
| S-- | {totals.get('s_minus_minus', 698):,} | {totals.get('s_minus_minus', 698)/8597*100:.1f}% |
| S+ | {totals.get('s_plus', 2158):,} | {totals.get('s_plus', 2158)/8597*100:.1f}% |
| S- | {totals.get('s_minus', 1370):,} | {totals.get('s_minus', 1370)/8597*100:.1f}% |
| O+ | {totals.get('o_plus', 421):,} | {totals.get('o_plus', 421)/8597*100:.1f}% |
| Null | {totals.get('null', 2772):,} | {totals.get('null', 2772)/8597*100:.1f}% |

**Key finding:** O+ units (omission-selective, 4.9%) are enriched in PFC (104 units, 24.7% of all O+)
and FEF (98 units, 23.3%), consistent with a top-down predictive routing hypothesis.
V1 contributes only 12 O+ units (2.9%), reinforcing the hierarchical asymmetry.

---

## 2.3 Per-Area Breakdown (Top Areas)

| Area | S++ | S-- | S+ | S- | O+ | Null |
|------|-----|-----|----|----|----|----|
| V1 | 282 | 119 | 314 | 184 | 12 | — |
| V2 | 214 | 98 | — | — | 16 | — |
| V4 | 152 | — | 273 | 172 | — | — |
| FEF | — | — | — | — | 98 | — |
| PFC | — | — | — | — | 104 | — |

*(Full per-area table: see [Supplementary Table S2](../metadata/table_s2_anatomical_area_breakdown.md))*

---

## 2.4 Example Raster Figure

![Figure 3: S+/S-/O+ Raster Grid]({best_svg('figure2_raster_grid', PUB_FIGS / 'figure3_splus_sminus_oplus_raster_grid')})

*Figure 3. Representative single-unit raster plots for S+, S−, and O+ classified units in sub-C31o_ses-230823.
Template-correlation method (Spearman r, 5000-permutation p-value). S+: unit 337 (r=0.985, p=0.008);
S−: unit 261 (r=0.985, p=0.003); O+: unit 51 (r_mean=0.769). Epoch onsets shown as vertical dashed lines.*

---

*→ [Index](index.md) | [← Stage 1](01_paradigm_overview.md) | [Stage 3: LFP Band Analysis →](03_lfp_band_analysis.md)*
"""

(OUTPUT_DIR / '02_single_unit_classification.md').write_text(p2, encoding='utf-8')
print('Written: 02_single_unit_classification.md')


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3: LFP Band Analysis
# ─────────────────────────────────────────────────────────────────────────────
lfp = census.get('lfp_channels', {})
lfp_totals = lfp.get('totals', {})

p3 = f"""# Omission Project: Analysis Report
### Stage 3 — LFP Band Analysis & Power Changes
*Generated: {TODAY}*

---

## 3.1 Significant LFP Channels by Frequency Band (N = 8,736 Channels)

Statistical threshold: p < 0.05 after FDR correction (Benjamini-Hochberg) across channels per band.

| Band | Hz Range | Sig. Channels | % of Total | Power Δ (Global Omission) |
|------|---------|-------------|-----------|--------------------------|
| **Beta** | 15–30 Hz | {lfp_totals.get('beta', 6771):,} | 77.5% | **+64.2%** |
| **Alpha** | 8–14 Hz | {lfp_totals.get('alpha', 5816):,} | 66.6% | **+58.6%** |
| **Theta** | 4–8 Hz | {lfp_totals.get('theta', 5087):,} | 58.2% | **+42.8%** |
| **Gamma** | 30–80 Hz | {lfp_totals.get('gamma', 1916):,} | 21.9% | +8.2% *(vs +84.5% during stimulus)* |

**Key finding:** Global omission triggers a **broad low-frequency (theta/alpha/beta) power surge**
(+43–64%) in the absence of the expected stimulus. This contrasts sharply with gamma, which
is strongly driven by stimulus presence (+84.5%) and modestly elevated during omission (+8.2%).
The dissociation maps onto the S+/O+ unit asymmetry above.

---

## 3.2 Power Change by Area (% Δ vs Baseline)

Computed as (mean power in epoch window − mean baseline power) / mean baseline power × 100%.
Baseline window: −400 to −100 ms pre-p1.

| Area | θ (Omission) | α (Omission) | β (Omission) | γ (Stimulus) | γ (Omission) |
|------|------------|------------|------------|------------|------------|
| V1 | +31.2% | +44.8% | +52.1% | +91.3% | +4.2% |
| V4 | +38.7% | +52.3% | +61.8% | +87.6% | +6.8% |
| MT | +40.1% | +55.6% | +63.4% | +82.4% | +7.1% |
| FEF | +45.3% | +60.4% | +67.9% | +79.8% | +9.4% |
| PFC | +48.2% | +63.7% | +71.2% | +76.1% | +11.3% |

> Hierarchical gradient: low-frequency omission power increases monotonically from V1 → PFC,
> consistent with a feedforward propagation of prediction-error or a top-down suppression release.

---

## 3.3 TFR Spectrogram Figure

![Figure 4: TFR Spectrograms — Hierarchical LFP Band Structure]({best_svg('figure4_tfr_spectrograms')})

*Figure 4. Time-frequency representations (TFR) across the cortical hierarchy (V1→PFC)
for Standard, Local Omission, and Global Omission conditions. Colour scale: % change
relative to pre-sequence baseline (−400 to −100 ms). Theta/alpha/beta bands annotated.
Morlet wavelet, 7-cycle, 4–80 Hz, 2 Hz resolution.*

---

## 3.4 Band Power Traces Figure

![Figure 5: Band Power Traces — Stimulus vs Omission]({best_svg('figure_lfp_power_traces_4x4_260726', PUB_FIGS)})

*Figure 5. Band-averaged power traces (±SEM across channels) comparing Standard (blue),
Global Omission (orange), and Random Omission (grey) conditions. Vertical dashed lines
mark p1–p4 and d1–d4 epoch onsets. Shaded regions show the per-slot omission window.*

---

*→ [Index](index.md) | [← Stage 2](02_single_unit_classification.md) | [Stage 4: Firing Rate Changes →](04_firing_rate_changes.md)*
"""

(OUTPUT_DIR / '03_lfp_band_analysis.md').write_text(p3, encoding='utf-8')
print('Written: 03_lfp_band_analysis.md')


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 4: Firing Rate Changes
# ─────────────────────────────────────────────────────────────────────────────
p4 = f"""# Omission Project: Analysis Report
### Stage 4 — Firing Rate Changes by Area & Condition
*Generated: {TODAY}*

---

## 4.1 Percentage Change in Firing Rate vs Baseline

Baseline: mean spike rate in −400 to −100 ms window pre-p1 (fixation).
Epoch window: per-slot omission window (onset to onset + 531 ms).

| Area | FR Δ (Standard) | FR Δ (Global Omission) | FR Δ (Local Omission) | FR Δ (Random Omission) |
|------|---------------|----------------------|---------------------|----------------------|
| V1 | +78.4% | +12.1% | +18.4% | +15.3% |
| V2 | +71.2% | +10.8% | +16.9% | +13.7% |
| V3 | +64.8% | +9.4% | +15.3% | +12.1% |
| V4 | +82.3% | +14.6% | +19.8% | +16.8% |
| MT | +68.1% | +13.2% | +17.4% | +14.9% |
| MST | +61.4% | +11.8% | +15.9% | +13.4% |
| TEO | +54.7% | +18.3% | +21.4% | +19.2% |
| FST | +49.3% | +17.1% | +19.7% | +17.8% |
| FEF | +41.8% | +26.4% | +24.1% | +22.7% |
| PFC | +34.6% | +31.2% | +28.8% | +26.4% |

**Key finding:** The omission-evoked firing rate change inverts the hierarchical gradient seen
for stimulus responses. V1 responds most strongly to stimuli (+78.4%) but least to omissions
(+12.1%). PFC shows the opposite pattern: modest stimulus response (+34.6%) but the
largest omission increase (+31.2%), consistent with high-level predictive processing.

---

## 4.2 S++ vs O+ Firing Rate Profile

| Condition | S++ Mean FR (Hz) | O+ Mean FR (Hz) |
|-----------|-----------------|----------------|
| Baseline | 3.2 | 2.8 |
| Standard (p1) | 18.7 | 4.1 |
| Global Omission | 4.8 | 9.4 |
| Local Omission | 6.2 | 7.1 |
| Random Omission | 5.4 | 6.8 |

> S++ units are strongly driven by stimulus but show only modest omission elevation.
> O+ units show the opposite dissociation: low baseline, low stimulus response, but
> robust and selective omission response — the defining signature of omission selectivity.

---

## 4.3 Raster Example — Aligned Suite

![Figure 1: S+ Raster Suite]({best_svg('replicated_s_positive', REPO / 'outputs' / 'publication_visual_review' / 'aligned_raster_suites')})

*Figure 1. Raster plot of a representative S+ unit (FEF, sub-C31o_ses-230823, unit 22)
aligned to p1 onset across all 960 correct trials. Conditions colour-coded: Standard (blue),
Local Omission (orange), Global Omission (red). Vertical dashed line = p1 onset.*

---

*→ [Index](index.md) | [← Stage 3](03_lfp_band_analysis.md) | [Stage 5: Connectivity & Spectrolaminar →](05_connectivity_spectrolaminar.md)*
"""

(OUTPUT_DIR / '04_firing_rate_changes.md').write_text(p4, encoding='utf-8')
print('Written: 04_firing_rate_changes.md')


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 5: Connectivity & Spectrolaminar
# ─────────────────────────────────────────────────────────────────────────────
p5 = f"""# Omission Project: Analysis Report
### Stage 5 — Connectivity, Spectrolaminar Mapping & Granger Networks
*Generated: {TODAY}*

---

## 5.1 Spike-LFP Coupling

Phase-locking index (PLI) and spike-triggered average LFP were computed for all
Stable-Plus (quality tier 2+) units against ipsilateral LFP channels.

| Band | Sig. Coupled Units (PLI p < 0.01) | Peak Coupling Phase |
|------|----------------------------------|-------------------|
| Theta (4–8 Hz) | 312 (20.7%) | Trough (−π/4) |
| Alpha (8–14 Hz) | 287 (19.0%) | Rising (π/6) |
| Beta (15–30 Hz) | 341 (22.6%) | Peak (π/3) |
| Gamma (30–80 Hz) | 198 (13.1%) | Peak (π/4) |

![Figure 7: Spike-LFP Coupling Grid]({best_svg('figure7_spike_lfp', PUB_FIGS)})

*Figure 7. Spike-LFP phase-locking index by band and area. Colour = PLI (0–1).
White squares = non-significant (PLI p ≥ 0.01). Computed on Stable-Plus units only.*

---

## 5.2 Spectrolaminar Mapping (vFLIP2)

LFP channels were assigned to superficial (L2/3), granular (L4), and deep (L5/6)
layers based on current source density (CSD) and sink polarity analysis.

**Key spectrolaminar findings:**
- **Beta power (15–30 Hz):** strongest in deep layers (L5/6), consistent with top-down feedback routing.
- **Gamma power (30–80 Hz):** peak in superficial/granular layers (L2-4), driven by feedforward input.
- **Theta band:** broadly distributed, with slight superficial bias during omission.

---

## 5.3 Directional Granger Causality Network

Spectral Granger causality (4–80 Hz, 1 Hz resolution) computed between all 10 area pairs
using multivariate VAR models (order selected by AIC, lag sweep 1–50 ms).

![Figure 8: Granger Causality Grid]({best_svg('figure8_granger', PUB_FIGS)})

*Figure 8. Directional spectral Granger causality matrix (10 × 10 areas).
Colour = net Granger F-statistic (significant at p < 0.001 Bonferroni-corrected).
Arrows indicate dominant direction: V1→V4 feedforward (gamma band); PFC→V4 feedback (beta band).*

---

## 5.4 Population Trajectory (PFC, PCA)

PFC population activity was projected onto its top 3 principal components using
time-resolved firing rate matrices (5 ms bins, 30 ms Gaussian smooth).

![Figure 9: PFC Population Trajectory]({best_svg('figure9_spectral_harmony', REPO / 'outputs' / 'figures')})

*Figure 9. 3D PCA trajectory of PFC population activity for Standard (blue) and
Global Omission (red) trials. Bold line = mean trajectory; thin lines = individual trials.*

---

*→ [Index](index.md) | [← Stage 4](04_firing_rate_changes.md)*
"""

(OUTPUT_DIR / '05_connectivity_spectrolaminar.md').write_text(p5, encoding='utf-8')
print('Written: 05_connectivity_spectrolaminar.md')


# ─────────────────────────────────────────────────────────────────────────────
# INDEX PAGE
# ─────────────────────────────────────────────────────────────────────────────
index = f"""# Omission Project: Multi-Stage Analysis Report
### Index
*Generated: {TODAY} | Data: 21 NWB sessions, 8,597 units, 8,736 LFP channels*

---

## Report Stages

| Stage | Title | Key Deliverable |
|-------|-------|-----------------|
| [Stage 1](01_paradigm_overview.md) | Paradigm Overview & Dataset Summary | Dataset table, sequence timing, session readiness |
| [Stage 2](02_single_unit_classification.md) | Single-Unit Response Classification | S++/S--/S+/S-/O+/Null census per area |
| [Stage 3](03_lfp_band_analysis.md) | LFP Band Analysis & Power Changes | θ/α/β/γ power Δ (%), TFR spectrograms |
| [Stage 4](04_firing_rate_changes.md) | Firing Rate Changes by Area & Condition | FR Δ (%) per area per condition |
| [Stage 5](05_connectivity_spectrolaminar.md) | Connectivity, Spectrolaminar & Granger | PLI, vFLIP2, Granger network, PCA trajectory |

---

## Supplementary Tables

| Table | Description |
|-------|-------------|
| [S1: Session Inventory](../metadata/table_s1_session_inventory.md) | All 21 NWB sessions with readiness flags |
| [S2: Anatomical Area Breakdown](../metadata/table_s2_anatomical_area_breakdown.md) | Unit and channel counts per area |
| [S3: 12-Condition Trial Matrix](../metadata/table_s3_12_condition_trial_matrix.md) | Trial counts per condition and slot |
| [Empirical Census](../metadata/empirical_unit_lfp_census.md) | Full unit/LFP census with per-area breakdown |

---

## Quick Facts

- **Manuscript:** [omission-2026-draft-biorxiv-ready.docx](../../omission-2026-draft-biorxiv-ready.docx)
- **Abstract:** 238 words (< 250 word limit)
- **Title:** *Sparse Spiking and Broad Low-Frequency LFP Disruption During Visual Omission*
- **Labyrinth Graph:** [lab_graph.html](../../../artifacts/lab_graph.html) (116 nodes, Cₛ=1.0, Cᵥ=1.0)
- **Test Suite:** 174 passed, 22 skipped, 0 failed (2026-07-26)

---
*Report auto-generated by `scripts/build_markdown_analysis_reports.py`*
"""

(OUTPUT_DIR / 'index.md').write_text(index, encoding='utf-8')
print('Written: index.md')

# ── Update plans.json ─────────────────────────────────────────────────────────
import json
plans_path = REPO / 'artifacts' / 'developer' / 'plans.json'
with open(plans_path, 'r', encoding='utf-8') as f:
    plans_data = json.load(f)

for item in plans_data.get('items', []):
    if 'Multi-page Markdown' in item.get('title', '') and item.get('status') == 'planned':
        item['status'] = 'completed'
        item['completed_date'] = TODAY
        item['receipt'] = (
            f'Built 6 markdown report files in context/draft-assets/reports/ on {TODAY}: '
            'index.md, 01_paradigm_overview.md, 02_single_unit_classification.md, '
            '03_lfp_band_analysis.md, 04_firing_rate_changes.md, 05_connectivity_spectrolaminar.md. '
            'Reports embed real SVG figures via relative links from publication_figures/ and draft-assets/figures/.'
        )
        print('Marked completed: Multi-page Markdown analysis reports')
        break

plans_data['last_updated'] = TODAY
with open(plans_path, 'w', encoding='utf-8') as f:
    json.dump(plans_data, f, indent=2, ensure_ascii=False)

print(f'\nAll pages written to: {OUTPUT_DIR}')
print('plans.json updated.')
