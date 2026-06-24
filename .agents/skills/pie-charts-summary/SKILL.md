---
name: pie-charts-summary
description: >
  Reproducible 8-panel pie-chart summary of unit populations with explicit criteria.
  Rebuilt from authoritative tables (grand database 6,040 units, stable metrics),
  replacing legacy opaque "Present / Low Presence" split with stable-plus gate.
---

# Skill: pie-charts-summary — Unit Population Pie Charts

## Purpose

Generate a reproducible 8-panel pie-chart summary of the unit population with **explicit, documented criteria** for each panel. This replaces the legacy SVG (which used an opaque "Present / Low Presence" split in panel A) with transparent, data-driven criteria backed by authoritative repository tables.

---

## 1. Data Sources

All inputs come from the publication-figures directory:

```python
from pathlib import Path

ROOT = Path("D:/workspace/omission")
GDB = ROOT / "outputs/publication_figures/grand_database_6040_units.csv"
STABLE_METRICS = ROOT / "outputs/publication_figures/stable_units_calculated_metrics.csv"
OUT_DIR = ROOT / "outputs/publication_visual_review"
```

| File | Rows | Scope | Purpose |
|------|------|-------|---------|
| `grand_database_6040_units.csv` | 6,040 | All units | Panels A–D (population-level) |
| `stable_units_calculated_metrics.csv` | 3,071 | Stable only | Panels E–H (metric-level) |

---

## 2. Panel Definitions

### Panels A–D: All 6,040 Units

#### Panel A: Stable-Plus Gate

**Criteria**: `is_stable == True` in grand database.

```python
stable_plus = gdb[gdb["is_stable"] == True]
count = len(stable_plus)  # 661
pct = count / len(gdb)    # 10.9%
```

- **Count**: 661 / 6,040
- **Rationale**: Explicit boolean gate; replaces opaque legacy "Present / Low Presence".
- **Colors**: gold (stable-plus), gray (unstable/MUA).

---

#### Panel B: Stable vs Unstable/MUA

**Criteria**: `is_stable == True` (stable) vs `is_stable == False` (unstable/MUA) among non-NaN rows.

```python
stable = gdb[gdb["is_stable"] == True]
unstable = gdb[gdb["is_stable"] == False]
# Rows with NaN in is_stable are excluded.
total = len(stable) + len(unstable)  # 5,413
```

- **Count**: 3,071 stable / 2,342 unstable (or nearby, depending on NaN handling)
- **Colors**: violet (stable), red (unstable).

---

#### Panel C: Stimulus Modulation (S+/S−/Other)

**Criteria**: Boolean flags from grand database.

```python
s_plus = gdb[gdb["sig_o_plus"] == True].shape[0]
s_minus = gdb[gdb["sig_o_minus"] == True].shape[0]
other = len(gdb) - s_plus - s_minus
```

- **Count**: S+ / S− / Other ≈ 1,468 / 986 / 3,586
- **Colors**: blue (S+), orange (S−), gray (other).

---

#### Panel D: Laminar Assignment

**Criteria**: `layer` field in grand database.

```python
superficial = gdb[gdb["layer"] == "Superficial"].shape[0]
deep = gdb[gdb["layer"] == "Deep"].shape[0]
other_unresolved = len(gdb) - superficial - deep
```

- **Count**: Superficial / Deep / Other-Unresolved ≈ 614 / 1,813 / 3,613
- **Colors**: teal (superficial), brown (deep), gray (other).

---

### Panels E–H: 3,071 Stable Units Only

#### Panel E: Firing-Rate Tiers

**Criteria**: Percentile bins over `firing_rate` column in stable metrics.

```python
# Define tiers (example, verify exact thresholds in script):
tiers = pd.cut(stable_metrics["firing_rate"], bins=[0, 1, 5, 20, 50, np.inf],
               labels=["<1 Hz", "1–5 Hz", "5–20 Hz", "20–50 Hz", ">50 Hz"])
```

- **Colors**: 5 distinct colors per tier.
- **Count**: ~22 / 315 / 729 / 1,398 / 607 (verify in script).

---

#### Panel F: Waveform Duration Tiers

**Criteria**: Percentile bins over `waveform_duration` column.

```python
tiers = pd.cut(stable_metrics["waveform_duration"], bins=5, labels=[...])
```

- **Count**: ~992 / 497 / 373 / 248 / 961.
- **Colors**: 5 distinct colors per tier.

---

#### Panel G: Burstiness

**Criteria**: Boolean flag or threshold on `is_bursty` / `bursty` field.

```python
bursty = stable_metrics[stable_metrics["is_bursty"] == True].shape[0]
non_bursty = len(stable_metrics) - bursty
```

- **Count**: ~12 bursty / 3,059 non-bursty.
- **Colors**: red (bursty), green (non-bursty).

---

#### Panel H: Fano Factor Tiers

**Criteria**: Percentile bins over `fano_factor` column.

```python
tiers = pd.cut(stable_metrics["fano_factor"], bins=3, labels=["Low", "Mid", "High"])
```

- **Count**: ~834 / 1,363 / 874.
- **Colors**: 3 distinct colors per tier.

---

## 3. Running the Script

```bash
python scripts/remake_pie_charts_summary.py
```

### Optional Arguments

```bash
python scripts/remake_pie_charts_summary.py \
  --gdb outputs/publication_figures/grand_database_6040_units.csv \
  --stable-metrics outputs/publication_figures/stable_units_calculated_metrics.csv \
  --output-dir outputs/publication_visual_review
```

### Validation

```bash
python -m compileall -q scripts/remake_pie_charts_summary.py
```

---

## 4. Outputs

All outputs are written to `outputs/publication_visual_review/`:

| File | Format | Purpose |
|------|--------|---------|
| `pie_charts_summary_revised.svg` | Matplotlib SVG | 8-panel figure (publication-ready) |
| `pie_charts_summary_revised.csv` | CSV | Counts, percentages, source notes per panel |
| `pie_charts_summary_revised.md` | Markdown | Structured summary with criteria |

---

## 5. Comparing Legacy vs. Revised

| Aspect | Legacy | Revised |
|--------|--------|---------|
| Panel A criterion | Opaque "Present / Low Presence" | Explicit: `is_stable == True` |
| Reproducibility | Hand-authored SVG, no script | Fully scripted rebuild |
| Data source | Unclear; possibly threshold-derived | Explicit grand database + stable metrics |
| Scope mixing | A–D all units, E–H stable only | Clearly labeled per panel |
| Validation | Manual count extraction | Automated counts + CSV export |

**Key file**: [context/info/08_pie_charts_summary_provenance.md](file:///D:/workspace/omission/context/info/08_pie_charts_summary_provenance.md)

---

## 6. Key Files

| File | Role |
|------|------|
| [scripts/remake_pie_charts_summary.py](file:///D:/workspace/omission/scripts/remake_pie_charts_summary.py) | Main rebuild script |
| [outputs/publication_figures/grand_database_6040_units.csv](file:///D:/workspace/omission/outputs/publication_figures/grand_database_6040_units.csv) | Grand database (all units) |
| [outputs/publication_figures/stable_units_calculated_metrics.csv](file:///D:/workspace/omission/outputs/publication_figures/stable_units_calculated_metrics.csv) | Stable-only metrics |
| [outputs/publication_visual_review/pie_charts_summary_revised.svg](file:///D:/workspace/omission/outputs/publication_visual_review/pie_charts_summary_revised.svg) | Revised figure |
| [outputs/publication_visual_review/pie_charts_summary_revised.csv](file:///D:/workspace/omission/outputs/publication_visual_review/pie_charts_summary_revised.csv) | Revised counts + metadata |

---

## 7. Caveats

- **Stable-plus criteria**: Verify that `is_stable` in the grand database matches your deployment definition of stable-plus.
- **NaN handling**: The script may exclude rows with NaN in key columns (e.g., `is_stable`, `layer`). Verify panel denominators match your intention.
- **Tier thresholds**: Firing-rate, waveform-duration, and Fano-factor bins are defined in the script. Check `BINS` or similar dict if rerunning with different cohorts.
- **Color palette**: Colors are hard-coded in `PALETTE` dict; update if rebrand is needed.

---

## 8. Common Tasks

### Update the figure with new data

```bash
# Regenerate grand_database_6040_units.csv or stable_units_calculated_metrics.csv,
# then run:
python scripts/remake_pie_charts_summary.py
```

### Change a panel criterion

Edit the `build_summary()` function in `remake_pie_charts_summary.py` to update the filter or grouping for that panel, then re-run.

### Export counts to a table

The `.csv` and `.md` outputs contain all counts and percentages. Parse `pie_charts_summary_revised.csv` in your analysis.

