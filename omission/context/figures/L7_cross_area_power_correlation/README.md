# L7 — cross-area power correlation (Fig 6)

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json), same gate
as L1-L6. Reuses L3's precomputed-TFR + `channel_layers_all.csv` node infrastructure rather than
rebuilding it.

**Method**: trial-by-trial Pearson correlation of band power across area×layer nodes (sup/deep
only — this corpus's layer labels don't resolve granular, same restriction L3 already states).
Each node gets one dB value **per trial** (channels-in-node pooled linear → band pooled linear →
divided by that trial's own baseline-window power → log10 once, per omission-signal §1), so the
correlation is genuinely trial-paired, not built from already-averaged traces. Computed
**separately per session** (never pooled or trial-concatenated across sessions — per
omission-statistics "test within session first") and **separately per condition** (stim/omission
never pooled, per spec). Benjamini-Hochberg FDR applied once across the full node-pair×band
family within a session/condition (`jnwb.StatisticalAnalysis.fdr_correct`), α=0.05.

**Node coverage** is corpus-limited: only sessions with ≥2 area×layer nodes (a labelled sup/deep
channel set AND a precomputed TFR file for both conditions) qualify. The top-3 sessions by node
count all happened to be **V182o** (FEF/MST/PFC or FEF/MT/PFC probes) — a single-subject result,
stated here since it wasn't planned. Node inventory and any excluded pairs (trial-count mismatch)
are in `L7_stats.json` per the spec's own acceptance criterion.

## Bugs found and fixed (visual-inspection gate)

1. **Node-key collision caused silent data loss, not just a cosmetic label clash.** The original
   node key was a bare `f"{area}{layer}"`. `sub-V182o_ses-260702` genuinely records FEF on two
   different probes (A and B); the first run's `node_trial_traces` dict assignment
   (`out[node_key] = band_traces`) silently let the second probe's FEF data overwrite the first's,
   so that session's matrix reported only **4 nodes** (`FEFdeep, FEFsup, MTdeep, MTsup`) instead
   of the true **6** — one whole probe's FEF data was dropped from the analysis without any error
   or warning. Fixed by making every node key probe-qualified (`f"{area}{layer}_{probe}"`),
   always, not conditionally. Rerun after the fix; `sub-V182o_ses-260702` now correctly shows 6
   nodes (`FEFdeep_A, FEFdeep_B, FEFsup_A, FEFsup_B, MTdeep_C, MTsup_C`) and its correlation
   matrix and significant-pair counts changed materially (see Result below) — this was a real
   correctness fix, not a relabeling. The same latent bug was independently found and fixed in
   [L8](../L8_cross_area_coherence/README.md).
2. **Figure layout**: first render mis-placed the "Pearson r (stim)" colorbar (overlapped session
   row 2's node labels) and clipped the suptitle at the canvas top. Fixed with explicit `GridSpec`
   columns for both colorbars and `fig.subplots_adjust(top=0.90)`.

## Result (descriptive — no claim asserted in code; reflects the POST-FIX run)

- **FEFdeep–FEFsup within one probe** (same-probe, adjacent depth) shows a consistently near-1
  correlation in every session and band, both conditions — the same same-probe-adjacent-depth
  pattern [L6](../L6_volume_conduction_control/README.md) and
  [L8](../L8_cross_area_coherence/README.md) already flag as often reference/volume-conduction-
  driven, visible again here via trial-level power correlation.
- **New since the node-key fix**: on `sub-V182o_ses-260702`, FEF recorded on probe A is *also*
  strongly trial-power-correlated with FEF recorded on probe B (the 4×4 FEFdeep_A/FEFsup_A/
  FEFdeep_B/FEFsup_B block is uniformly dark red across every band) — a genuinely different
  finding than the pre-fix 4-node run could show, since one probe's FEF data was silently absent
  before. **This is worth reading against L8**: for this same session/pair, L8's cross-area
  coherence found FEF-A↔FEF-B standard coherence LOW (0.08–0.13) with low imaginary coherency
  too — i.e. two different statistics disagree on how "coupled" FEF-A and FEF-B are. Trial-level
  power correlation and phase coherence measure different things (a shared slow arousal/state
  signal can drive correlated power without phase-locked activity), so this is not a
  contradiction to resolve here — it is flagged as a cross-metric discrepancy for the manuscript
  text to address, not smoothed over.
- **`sub-V182o_ses-260715` is an outlier**: 13–15 of 15 node pairs are FDR-significant in
  *every* band and *both* conditions — completely non-selective across frequency and area, which
  looks more consistent with a session-wide shared artifact (movement, broadband gain drift) than
  genuine area-specific coupling. [L8](../L8_cross_area_coherence/README.md) independently flags
  elevated (though not saturated) cross-probe PFC↔FEF coherence for this same session, a
  cross-validating signal. `sub-V182o_ses-260702` (post-fix) is now ALSO fairly dense
  (7–9 of 15 significant across bands, up from the pre-fix run which couldn't even see half its
  nodes) — the sparsest session is `sub-V182o_ses-260629` (3–9 of 15). Flagged here, not silently
  averaged away.
- Difference matrices (omission − stim, high_gamma shown) are small in magnitude for
  `sub-V182o_ses-260629` and `sub-V182o_ses-260702` and are **not independently FDR-corrected**
  (stated in the stats JSON — no resampling null was built for the difference itself, only for
  each condition's own matrix).

## Self-test

`python L7_cross_area_power_correlation.py --test`: 4 synthetic nodes with known trial-level
structure — n1-n2 strongly correlated in both conditions (recovered r=0.73/0.75, FDR-significant
q<0.05), n3-n4 independent in both (r≈-0.06, correctly NOT significant), n1-n3 correlated *only*
in the synthetic omission condition (recovered difference +0.68, matching the injected
condition-specific coupling). Plus a mismatched-trial-count pair-exclusion guard and a
determinism check.

Outputs: `L7.svg` / `L7.png` / `L7.pdf`, `L7_stats.json`, `L7_manifest.json`.
