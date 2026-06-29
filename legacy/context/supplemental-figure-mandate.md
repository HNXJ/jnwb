# OMISSION REPO: SUPPLEMENTAL FIGURE MANDATE
Version: 1.0 (Predictive Routing Translation)
Status: Canonical
Applies to: `codes/functions/visualization/*`, `codes/scripts/analysis/*`

## 1. Global Method Mandate

### Signals
- **MUAe**: Derive from 30 kHz data. Band-pass 500–5000 Hz, rectify (envelope), low-pass 250 Hz, resample to 1 kHz. Use repo’s analog MUA path.
- **SPK**: Use stable "Good" units only (Presence > 0.95, ISI < 0.5, FR > 1.0) for unit-based figures.
- **LFP**: Use **bipolar derivations** (400 µm spacing) for all coherence, Granger, or power-coupling analyses.

### Spectral Estimation
- **Method**: Multitaper spectral estimation.
- **Window**: 1 s sliding windows.
- **Smoothing**: 5 Hz frequency smoothing.

### Time & Area Base
- **Time Axis**: Always **p1-relative ms** (Code 101.0 = 0ms). Default window: `-1000 ms` to `+4000 ms`.
- **Area Order**: `V1, V2, V3d, V3a, V4, MT, MST, TEO, FST, FEF, PFC`.

### Statistics & Inference
- **Time/Freq Curves**: Cluster-based randomization with first-level thresholding and corrected cluster testing.
- **Laminar Summaries**: Superficial vs. Deep comparisons using rank-sum or non-parametric tests.
- **Inference Level**: `N` = independent sessions (primary). `n` = channels/units/trials (secondary/metadata).

---

## 2. Figure Logic Translations

| Style | Original Supplemental Role | Omission Translation |
|:---:|:---|:---|
| **SF1** | Average MUA traces per area | Compare `RRRR` vs. Omission family (`RXRR`, `RRXR`, `RRRX`). Use for population MUA shifts. |
| **SF2** | MUA x LFP power correlation | Correlate `(Omit - Control) MUA` with `(Omit - Control) LFP Power` per band. Pairs spikes with nearby bipolar LFP. |
| **SF3** | Area-wise info & power mod | Barplots of spike decoding (Omission identity/pos) vs. LFP band modulation per area. |
| **SF4** | Pre-sample power modulation | "Pre-omission expectancy interval" power. Compare Omission vs. Full-sequence control before the missing item. |
| **SF5** | History-controlled power | Balance confounds: trial count, omission position, and preceding sequence history. |
| **SF6** | First-violation adaptation | Lock to 1st omission trial after full-sequence run. Track power change over subsequent omission trials. |
| **SF7** | Predictive state build-up | Lock to start of stable full-sequence block. Show buildup of expected state before violations appear. |
| **SF8** | Behavior/Eye x Power | Correlate eye metrics (pupil, microsaccades, stability) with LFP power across area x frequency heatmaps. |
| **SF9** | Coherence Networks | Omission vs. Matched-control coherence structure on bipolar derivations. Fixed canonical area layout. |
| **SF10** | Pairwise Coherence Spectra | Small multiples of all area pairs. Show corrected significant frequency clusters. |
| **SF11** | Pre-omission Networks | Coherence structure during the interval *predicting* the upcoming omission. |
| **SF12** | Directed Granger Flow | Omission vs. Control GC difference z-scores. Show `A -> B` and `A <- B` flow changes. |
| **SF13** | Cross-area Power-Spike coupling | Regression: High-order LFP power (`FEF`, `PFC`) predicting Low-order activity (`V1`, `V2`, `V4`, `MT`). |

---

## 3. Manuscript Mapping
- **Figures 5–6**: Use logic from **SF4–5** (Expectancy) and **SF9–12** (Networks/Granger).
- **Figure 7**: Use logic from **SF2** (Spike-LFP corr) and **SF13** (Cross-area coupling).
- **Figure 8**: Use logic from **SF9** and **SF11** (State vs. Event coherence).
- **Spike Groups**: Use logic from **SF1** and **SF3** (MUA/Decoding) but locked to specific unit classes.

## 4. Implementation Requirement
Every figure implementation must define:
1. **Signal** | 2. **Window** | 3. **Comparison** | 4. **Inference Level** | 5. **Plot Type** | 6. **Stats** | 7. **Saved Sidecar Tables**
