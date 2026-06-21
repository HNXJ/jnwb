---
name: tfr-visualizaiton-traces
description: >
  Plotly interactive line traces plotting protocols for LFP band-power changes over time.
---

# Skill: tfr-visualizaiton-traces — TFR Traces & Power Changes

## Purpose
Guidelines for rendering interactive Plotly 1D band-power traces over time using the project's color palette.

---

## 1. Aesthetics & Colors
All plots must adhere to the **Madelane Golden Dark** paper aesthetic:
- **Primary / Target / Stimulus Present**: `#CFB87C` (Gold)
- **Secondary / Omission / Test**: `#9400D3` (Violet)
- **Plot Background**: `#FFFFFF` (White)

---

## 2. Band-Power Extraction
To extract time-varying power, average across frequency bins inside one of these bands:
- **Theta**: 4–8 Hz
- **Alpha**: 8–12 Hz
- **Beta**: 12–30 Hz
- **Gamma**: 30–80 Hz

---

## 3. Code Example
```python
import numpy as np
import plotly.graph_objects as go

def plot_tfr_trace(times, mean_power, sem_power, cond_label, color):
    fig = go.Figure()
    # Main trace
    fig.add_trace(go.Scatter(
        x=times, y=mean_power,
        mode='lines',
        line=dict(color=color, width=2),
        name=cond_label
    ))
    # SEM shading
    fig.add_trace(go.Scatter(
        x=np.concatenate([times, times[::-1]]),
        y=np.concatenate([mean_power + sem_power, (mean_power - sem_power)[::-1]]),
        fill='toself',
        fillcolor=color,
        opacity=0.15,
        line=dict(color='rgba(255,255,255,0)'),
        showlegend=False
    ))
    fig.update_layout(
        plot_bgcolor='#FFFFFF',
        paper_bgcolor='#FFFFFF',
        xaxis_title="Time from p1 onset (ms)",
        yaxis_title="Relative Power (dB)"
    )
    return fig
```
