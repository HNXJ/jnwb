---
name: visualization
description: >
  Canonical Plotly and Matplotlib visualization conventions for the Omission
  project. Covers the Madelane Golden Dark palette, OmissionPlotter usage,
  raster/PSTH layouts, TFR heatmaps, and SVG/HTML export.
---

# Skill: visualization — Omission Project Visualization

## Purpose
Ensure any agent producing figures follows the **Madelane Golden Dark** aesthetic
protocol and uses the canonical plotting infrastructure correctly. All figures
must use pure-white backgrounds and the Gold/Violet palette.

---

## 1. Mandatory Aesthetic Protocol

| Token | Color | Use |
|-------|-------|-----|
| `GOLD = "#CFB87C"` | Gold | Sink / Stimulus signals, p1 markers |
| `VIOLET = "#9400D3"` | Dark violet | Source / Omission signals, p2–p4 markers |
| `WHITE = "#FFFFFF"` | White | **ALWAYS** paper/plot background |
| `GRAY = "#D3D3D3"` | Light gray | Grid lines, delay epochs |
| `TEAL = "#00FFCC"` | Teal | p3 slot markers |
| `ORANGE = "#FF5E00"` | Bright orange | p4 slot markers |

```python
from src.analysis.lfp.lfp_constants import GOLD, VIOLET, WHITE, GRAY, TEAL, ORANGE
```

> **Hard Rule**: Paper background = `#FFFFFF`. Never `"plotly_dark"` or `"seaborn"`.

---

## 2. OmissionPlotter (Plotly Canonical Wrapper)

```python
from src.analysis.visualization.plotting import OmissionPlotter

plotter = OmissionPlotter(
    title    = "Omission PSTH — FEF",
    x_label  = "Time",
    y_label   = "Firing Rate",
    subtitle  = "AXAB (p2 omission), n=36 units",
    x_unit   = "ms",
    y_unit   = "Hz",
    p_value  = 0.003,   # auto-injects significance stars into title
)

# Add a trace
plotter.fig.add_scatter(
    x=t_ms, y=rate_hz,
    mode='lines',
    line=dict(color=GOLD, width=2),
    name="AAAB (control)",
)

# Add event lines
for label, t_ms_event, color in [
    ("p1", 0, GOLD), ("p2", 1031, VIOLET), ("p3", 2062, TEAL), ("p4", 3093, ORANGE)
]:
    plotter.fig.add_vline(
        x=t_ms_event, line_dash="dash", line_color=color,
        annotation_text=f"<b>{label}</b>",
        annotation_position="top right",
    )

# Export
plotter.fig.write_html("outputs/fig.html")
```

---

## 3. Raster + PSTH Layout (Matplotlib)

Standard 2-column layout for raster figures (see `generate_all_rasters_expanded.py`):

```python
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

fig = plt.figure(figsize=(13, 14), facecolor="white")
# Left column: 4 raster rows + 1 PSTH row; right column: metadata + waveform
gs = gridspec.GridSpec(5, 2, figure=fig,
                       width_ratios=[3, 1],
                       height_ratios=[1, 1, 1, 1, 3.5],
                       hspace=0.35, wspace=0.3)

axes_raster = [fig.add_subplot(gs[i, 0]) for i in range(4)]
ax_psth     = fig.add_subplot(gs[4, 0])
ax_info     = fig.add_subplot(gs[0:2, 1])
ax_waveform = fig.add_subplot(gs[2:4, 1])
```

Raster row colors per family:
- **A-family**: `#1565C0` (AAAB), `#4CAF50` (AXAB), `#FF9800` (AAXB), `#E53935` (AAAX)
- **B-family**: `#00ACC1` (BBBA), `#8E24AA` (BXBA), `#FFB300` (BBXA), `#D81B60` (BBBX)
- **R-family**: `#E5D429` (RRRR), `#0E9F58` (RXRR), `#3E9BE5` (RRXR), `#D9541F` (RRRX)

---

## 4. Raster Plot Drawing

```python
def draw_raster(ax, rasters, colors_per_cond, time_range_ms, cond_labels):
    """
    rasters: dict[cond_name → list[np.ndarray of spike times in ms]]
    """
    y_offset = 0
    ytick_locs = []
    ytick_labels = []

    for cond_name in cond_labels:
        spikes = rasters.get(cond_name, [])
        color  = colors_per_cond[cond_name]
        for k, trial_spikes in enumerate(spikes):
            ax.vlines(trial_spikes, y_offset + k - 0.4, y_offset + k + 0.4,
                      colors=color, linewidth=0.6, alpha=0.85)
        ytick_locs.append(y_offset + len(spikes) / 2)
        ytick_labels.append(cond_name)
        y_offset += len(spikes) + 2  # spacing between conditions

    ax.set_yticks(ytick_locs)
    ax.set_yticklabels(ytick_labels, fontsize=7)
    ax.set_xlim(time_range_ms)
    ax.axvline(0, color="black", linewidth=1.0, linestyle="--", alpha=0.5)
    ax.set_facecolor("white")
    ax.spines[['top', 'right']].set_visible(False)
```

---

## 5. Waveform Subplot

```python
def draw_waveform(ax, waveform_mean, unit_id, area, layer, snr, fr):
    """
    waveform_mean: 1-D array (82 samples @ 30 kHz → 2.73 ms)
    """
    t_us = np.arange(len(waveform_mean)) / 30.0 * 1000.0   # µs
    wf_norm = waveform_mean / np.abs(waveform_mean).max()
    ax.plot(t_us, wf_norm, color=GOLD, linewidth=1.5)
    ax.axhline(0, color=GRAY, linewidth=0.7, linestyle=":")
    ax.set_xlabel("µs", fontsize=7)
    ax.set_ylabel("Norm. V", fontsize=7)
    ax.set_title("Waveform", fontsize=8)
    ax.set_facecolor("white")
    ax.spines[['top', 'right']].set_visible(False)

    # Metadata text
    meta_txt = (
        f"Unit: {unit_id}  Area: {area}\n"
        f"Layer: {layer}\n"
        f"SNR: {snr:.2f}  FR: {fr:.1f} Hz"
    )
    ax.text(0.05, 0.95, meta_txt, transform=ax.transAxes,
            fontsize=7, va='top', family='monospace',
            bbox=dict(boxstyle='round', fc='white', alpha=0.8))
```

---

## 6. SVG Export

All rasters and publication figures must be saved as **SVG**:

```python
fig.savefig(save_path, format='svg', dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close(fig)
```

Naming convention: `{area}_ses{session_id}_unit{unit_id}_{family}_family.svg`

Example: `PFC_ses230830_unit134_A_family.svg`

---

## 7. Statistical Annotations

Always attach statistical evidence to figures:

```python
plotter.add_stats_metadata(
    test_name  = "Mann-Whitney U",
    p_value    = 0.003,
    n_sessions = 11,
    n_units    = 36,
)
```

Significance tiers (from `src.analysis.stats.tiers`):
| Tier | p-value | Stars |
|------|---------|-------|
| S4 | p < 0.0001 | ★★★★ |
| S3 | p < 0.001 | ★★★ |
| S2 | p < 0.01 | ★★ |
| S1 | p < 0.05 | ★ |

---

## 8. Key Files

| File | Role |
|------|------|
| [visualization/plotting.py](file:///D:/workspace/omission/src/analysis/visualization/plotting.py) | OmissionPlotter class |
| [visualization/lfp_plotting.py](file:///D:/workspace/omission/src/analysis/visualization/lfp_plotting.py) | LFP-specific plots |
| [lfp_constants.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_constants.py) | Color tokens & timing |
| [stats/tiers.py](file:///D:/workspace/omission/src/analysis/stats/tiers.py) | Significance tier labels |
| [scripts/generate_strict_rasters.py](file:///D:/workspace/omission/scripts/generate_strict_rasters.py) | Reference raster script |
