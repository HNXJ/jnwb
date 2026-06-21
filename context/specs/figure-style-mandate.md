# OMISSION REPO FIGURE STYLE MANDATE
Version: 2.0 (Publication-Grade)
Status: Canonical
Applies to: `codes/functions/visualization/*`, `codes/scripts/analysis/*`, poster/manuscript exports

## 1. Global Mandates

1. **Self-Containment**: Every figure must be interpretable without the main text. Use explicit axis labels, units, legends, panel labels, and short in-panel annotations.
2. **Typography**: Use Arial or Helvetica. Never outline text. Maintain legibility at final export size.
3. **Accessibility**: Use the color-blind-safe palette (see below). Never rely on color alone; pair with line style, marker shape, or direct labels.
4. **Minimalism**: No drop shadows, 3D embellishment, glossy effects, or unnecessary gridlines.
5. **Color/Text**: Use black or dark gray text. Legends must use black text with colored swatches.
6. **Uncertainty**: Explicitly report error representation (e.g., `mean ± SEM`, `95% CI`).
7. **Statistics**: Report in compact format: `test, statistic, df, p, N, correction`.
8. **Sample Size**: Clearly distinguish `N` (independent units/sessions) from `n` (observations/neurons/trials).
9. **Consistency**: Condition colors and area ordering must remain fixed across the entire project.
10. **Events**: Event-locked plots must show timing explicitly (lines or shaded windows).

## 2. Default Accessible Palette

Unless project-specific Omission colors (Section 4) are required, use:
- **Black**: `#000000`
- **Orange**: `#E69F00`
- **Sky Blue**: `#56B4E9`
- **Bluish Green**: `#009E73`
- **Yellow**: `#F0E442`
- **Blue**: `#0072B2`
- **Vermillion**: `#D55E00`
- **Reddish Purple**: `#CC79A7`

## 3. Plot-Specific Rules

### 2D Trace-Line Plots
- Summary band default: `mean ± 1.0 SEM` with low opacity.
- Line thickness: Thin (individual), Thicker (means), Thickest (focal condition).
- Show baseline/zero-line clearly if relevant.
- Use significance bars/strips instead of many p-values on curves.

### 2D Image Plots (Spectrograms/Heatmaps)
- Use perceptually uniform colormaps (avoid rainbow/jet).
- Center diverging colormaps on zero/reference value.
- Explicitly label color bar units (e.g., dB, z-score, normalized power).
- Draw event lines/epoch boundaries.

### 2D Bar/Violin Plots
- Barplots: Use only for aggregate summaries; show raw data points if sample size allows.
- Violin plots: Overlay raw points, box, or median line. Same kernel bandwidth across groups.

## 4. Omission Project Specifics (The "Golden Standard")

### Canonical Area Order (V1 -> PFC)
`V1, V2, V3d, V3a, V4, MT, MST, TEO, FST, FEF, PFC`

### Canonical Timing (p1 onset = 0ms)
| Epoch | Window (ms) | Note |
|:---|:---:|:---|
| **fx** (Fixation) | -500 to 0 | Pre-stimulus baseline |
| **p1** | 0 to 531 | Stimulus 1 |
| **d1** | 531 to 1031 | Delay 1 |
| **p2 / x** | 1031 to 1562 | Stimulus 2 or Omission |
| **d2** | 1562 to 2062 | Delay 2 |
| **p3 / x** | 2062 to 2593 | Stimulus 3 or Omission |
| **d3** | 2593 to 3093 | Delay 3 |
| **p4 / x** | 3093 to 3624 | Stimulus 4 or Omission |
| **d4** | 3624 to 4124 | Delay 4 |

### Omission Color System
- **Ordered palette** (index 0..12): GOLD, BLUE, VIOLET, RED, GREEN, BLACK, PINK, BROWN, TEAL, ORANGE, RED_BEIGE, GRAY, WHITE — see `lfp_constants.OMISSION_PALETTE_ORDER`.
- **Event Patches**: p1=GOLD, p2=VIOLET, p3=TEAL, p4=ORANGE, d*=GRAY, Omission=PINK.
- **Spectral Bands** (by palette index): Theta=GOLD, Alpha=BLUE, l-beta=VIOLET, h-beta=RED, Gamma_L=GREEN, Gamma_H=BLACK.
- **Conditions**: AAAB=BLUE, BBBA=ORANGE, RRRR=GOLD (extend by palette index for other families).

## 5. Implementation Notes
- **Source of Truth**: `codes/functions/lfp/lfp_constants.py`.
- **Export**: Vector (SVG/PDF) for publication; HTML for QC.
- **Normalization**: Standard is $10 \cdot \log_{10}(P / P_{base})$ (dB).
