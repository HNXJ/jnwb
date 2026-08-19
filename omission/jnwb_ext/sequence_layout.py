"""
Omission sequence presentation layout as Plotly vector objects (not a raster image).

Timing contract (ms relative to p1 onset):
  fx=-500; p1=0; d1=p1+531; p2=d1+500; d2=p2+531; p3=d2+500;
  d3=p3+531; p4=d3+500; d4=p4+531; end=d4+500 → full span 4624 ms (-500..4124).

Epochs: fx, p1, d1, p2, d2, p3, d3, p4, d4
Event-patch colors follow the Omission canonical palette indices.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

# Canonical palette (indices) — inlined; src/analysis/lfp/lfp_constants.py absent here.
OMISSION_PALETTE = (
    "#CFB87C",  # 0 GOLD  — p1 / Theta
    "#2563EB",  # 1 BLUE  — Alpha
    "#8F00FF",  # 2 VIOLET — p2 / l-beta
    "#DC2626",  # 3 RED   — h-beta
    "#16A34A",  # 4 GREEN — Gamma_L
    "#000000",  # 5 BLACK — Gamma_H
    "#FF1493",  # 6 PINK  — omission markers
    "#8B4513",  # 7 BROWN — fx
    "#00FFCC",  # 8 TEAL  — p3
    "#FF5E00",  # 9 ORANGE — p4
    "#C9A88A",  # 10 RED_BEIGE
    "#D3D3D3",  # 11 GRAY — delays
    "#FFFFFF",  # 12 WHITE
)

# Full-sequence epoch onsets (ms). Presentations are 531 ms; delays/fx are 500 ms.
EPOCH_ONSETS_MS: Dict[str, float] = {
    "fx": -500.0,
    "p1": 0.0,
    "d1": 531.0,
    "p2": 1031.0,
    "d2": 1562.0,
    "p3": 2062.0,
    "d3": 2593.0,
    "p4": 3093.0,
    "d4": 3624.0,
}
FULL_SEQUENCE_END_MS = 4124.0  # d4 + 500; span from fx = 4624 ms
FULL_SEQUENCE_START_MS = EPOCH_ONSETS_MS["fx"]
FULL_SEQUENCE_DURATION_MS = FULL_SEQUENCE_END_MS - FULL_SEQUENCE_START_MS  # 4624

EPOCH_ORDER: Tuple[str, ...] = (
    "fx", "p1", "d1", "p2", "d2", "p3", "d3", "p4", "d4"
)

# Presentation epochs (checkered / hatched markers in the template)
PRESENTATION_EPOCHS = frozenset({"p1", "p2", "p3", "p4"})

EPOCH_COLORS: Dict[str, str] = {
    "fx": OMISSION_PALETTE[7],   # BROWN
    "p1": OMISSION_PALETTE[0],   # GOLD
    "d1": OMISSION_PALETTE[11],  # GRAY
    "p2": OMISSION_PALETTE[2],   # VIOLET
    "d2": OMISSION_PALETTE[11],
    "p3": OMISSION_PALETTE[8],   # TEAL
    "d3": OMISSION_PALETTE[11],
    "p4": OMISSION_PALETTE[9],   # ORANGE
    "d4": OMISSION_PALETTE[11],
}

# R-family conditions for the publication suite
R_FAMILY_CONDITIONS: Tuple[str, ...] = ("RRRR", "RXRR", "RRXR", "RRRX")

# Omission slot for R-family: letter position of X (1-indexed among R's)
OMISSION_SLOT: Dict[str, Optional[int]] = {
    "RRRR": None,
    "RXRR": 2,  # p2 omitted
    "RRXR": 3,  # p3 omitted
    "RRRX": 4,  # p4 omitted
}

# Canonical 11-area order (publication). V3d and V3a are separate slots.
# When a probe is labeled V3 / V3d,V3a / V3d/V3a: ch 1–64 → V3d, ch 65–128 → V3a.
CANONICAL_AREAS_11: Tuple[str, ...] = (
    "V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"
)

# Probe-local channel count and dual-area half-split (1-based ch 1–64 / 65–128).
PROBE_N_CHANNELS = 128
DUAL_AREA_FIRST_SLICE = slice(0, 64)   # channels 1–64
DUAL_AREA_SECOND_SLICE = slice(64, 128)  # channels 65–128

# Bare "V3" on a probe means the dual pair V3d then V3a.
V3_DUAL_PAIR: Tuple[str, str] = ("V3d", "V3a")

# Single-token aliases that are not dual splits
AREA_ALIASES: Dict[str, str] = {
    "DP": "V4",
    "V3A": "V3a",
    "V3D": "V3d",
}


def normalize_area_name(area: str) -> str:
    """Canonicalize a single area token (no dual split)."""
    key = str(area).strip()
    if not key:
        return key
    if key in AREA_ALIASES:
        return AREA_ALIASES[key]
    # preserve known casing for V3a/V3d
    low = key.lower()
    if low == "v3a":
        return "V3a"
    if low == "v3d":
        return "V3d"
    if low == "v3":
        # bare V3 is a dual label, not a single area — callers should use parse_probe_areas
        return "V3"
    return key


def parse_probe_areas(label: str) -> Tuple[str, ...]:
    """
    Parse a probe area label into ordered canonical area names.

    Dual forms (comma or slash): \"Y, Z\" / \"Y/Z\" → (Y, Z).
    Bare \"V3\" → (V3d, V3a).
    Single area → one-element tuple.
    """
    raw = str(label).strip()
    if not raw:
        return ()
    # Dual separators: comma or slash (not used inside canonical names)
    if "," in raw or "/" in raw:
        parts = re.split(r"[,/]", raw)
        # Dual/multi labels: keep bare "V3" as V3 (half of probe). Only a
        # sole-label "V3" expands to V3d|V3a below.
        areas = tuple(
            normalize_area_name(p) for p in parts if p.strip()
        )
        return areas
    single = normalize_area_name(raw)
    if single == "V3":
        return V3_DUAL_PAIR
    return (single,)


def channel_slice_for_area(
    probe_areas: Sequence[str],
    target_area: str,
    *,
    n_channels: int = PROBE_N_CHANNELS,
) -> Optional[slice]:
    """
    Return the channel slice for target_area on a probe with probe_areas.

    Dual (len==2): first area → ch 1–64, second → ch 65–128.
    Single: all channels.
    More than two: equal linspace partitions (legacy fallback).
    """
    # Do not expand bare "V3" here — parse_probe_areas already expands sole-label
    # V3 → (V3d, V3a). Dual labels like ("V3", "V1") keep V3 as a half-slot.
    flat = [normalize_area_name(a) for a in probe_areas]
    target = normalize_area_name(target_area)
    if target not in flat:
        return None
    if len(flat) == 1:
        return slice(0, n_channels)
    if len(flat) == 2:
        if flat[0] == target:
            return DUAL_AREA_FIRST_SLICE if n_channels >= 128 else slice(0, n_channels // 2)
        if flat[1] == target:
            return DUAL_AREA_SECOND_SLICE if n_channels >= 128 else slice(n_channels // 2, n_channels)
        return None
    # n>2: equal partitions
    edges = np.linspace(0, n_channels, len(flat) + 1, dtype=int)
    idx = flat.index(target)
    return slice(int(edges[idx]), int(edges[idx + 1]))


# 7 labeled bands for traces (canonical names + palette indices 0..5, spare BROWN for 7th)
BANDS_7: Dict[str, Tuple[float, float]] = {
    "Theta": (3.0, 7.0),
    "Alpha": (8.0, 12.0),
    "l-beta": (12.0, 20.0),
    "h-beta": (20.0, 30.0),
    "Gamma_L": (32.0, 50.0),
    "Gamma_H": (50.0, 90.0),
    "Gamma_HH": (90.0, 200.0),  # extended high-gamma (palette BROWN)
}
BAND_COLORS_7: Dict[str, str] = {
    "Theta": OMISSION_PALETTE[0],
    "Alpha": OMISSION_PALETTE[1],
    "l-beta": OMISSION_PALETTE[2],
    "h-beta": OMISSION_PALETTE[3],
    "Gamma_L": OMISSION_PALETTE[4],
    "Gamma_H": OMISSION_PALETTE[5],
    "Gamma_HH": OMISSION_PALETTE[7],
}


@dataclass(frozen=True)
class EpochInterval:
    name: str
    start_ms: float
    end_ms: float
    color: str
    is_presentation: bool

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms


def epoch_intervals(
    end_ms: float = FULL_SEQUENCE_END_MS,
) -> List[EpochInterval]:
    """Return ordered epoch intervals covering [fx, end_ms]."""
    onsets = [EPOCH_ONSETS_MS[n] for n in EPOCH_ORDER]
    ends = onsets[1:] + [end_ms]
    out: List[EpochInterval] = []
    for name, start, end in zip(EPOCH_ORDER, onsets, ends):
        out.append(
            EpochInterval(
                name=name,
                start_ms=float(start),
                end_ms=float(end),
                color=EPOCH_COLORS[name],
                is_presentation=name in PRESENTATION_EPOCHS,
            )
        )
    return out


def omission_window_ms(condition: str) -> Optional[Tuple[float, float]]:
    """
    Return (start_ms, end_ms) for the d-p-d triplet around the omitted presentation.

    Example: RXRR → p2 omitted → window d1–p2–d2 = [531, 2062).
    """
    slot = OMISSION_SLOT.get(condition)
    if slot is None:
        return None
    # slot 2 → d1,p2,d2 ; slot 3 → d2,p3,d3 ; slot 4 → d3,p4,d4
    d_before = f"d{slot - 1}"
    d_after = f"d{slot}"
    start = EPOCH_ONSETS_MS[d_before]
    # end at start of next epoch after d_after, or full end
    after_idx = EPOCH_ORDER.index(d_after)
    if after_idx + 1 < len(EPOCH_ORDER):
        end = EPOCH_ONSETS_MS[EPOCH_ORDER[after_idx + 1]]
    else:
        end = FULL_SEQUENCE_END_MS
    return (start, end)


def sequence_shapes(
    y0: float = 0.0,
    y1: float = 1.0,
    *,
    opacity: float = 0.28,
    xref: str = "x",
    yref: str = "y",
    layer: str = "below",
    highlight_omission: Optional[str] = None,
    show_boundary_lines: bool = True,
) -> List[dict]:
    """
    Build Plotly layout.shapes for the full-sequence presentation background.

    These are vector rect/line objects — not an embedded PNG/SVG image.
    """
    shapes: List[dict] = []
    intervals = epoch_intervals()
    omit_win = omission_window_ms(highlight_omission) if highlight_omission else None

    for ep in intervals:
        fill = ep.color
        op = opacity
        if omit_win is not None and ep.name.startswith("p"):
            # Emphasize omitted presentation with PINK edge later
            slot = OMISSION_SLOT.get(highlight_omission or "")
            if slot is not None and ep.name == f"p{slot}":
                fill = OMISSION_PALETTE[6]  # PINK omission
                op = min(0.45, opacity + 0.12)

        shapes.append(
            {
                "type": "rect",
                "xref": xref,
                "yref": yref,
                "x0": ep.start_ms,
                "x1": ep.end_ms,
                "y0": y0,
                "y1": y1,
                "fillcolor": fill,
                "opacity": op,
                "line": {"width": 0},
                "layer": layer,
                "name": ep.name,
            }
        )

    if show_boundary_lines:
        for ep in intervals:
            shapes.append(
                {
                    "type": "line",
                    "xref": xref,
                    "yref": yref,
                    "x0": ep.start_ms,
                    "x1": ep.start_ms,
                    "y0": y0,
                    "y1": y1,
                    "line": {
                        "color": OMISSION_PALETTE[9],  # ORANGE dotted separators
                        "width": 1.0,
                        "dash": "dot",
                    },
                    "layer": layer,
                }
            )
        shapes.append(
            {
                "type": "line",
                "xref": xref,
                "yref": yref,
                "x0": FULL_SEQUENCE_END_MS,
                "x1": FULL_SEQUENCE_END_MS,
                "y0": y0,
                "y1": y1,
                "line": {
                    "color": OMISSION_PALETTE[9],
                    "width": 1.0,
                    "dash": "dot",
                },
                "layer": layer,
            }
        )

    if omit_win is not None:
        shapes.append(
            {
                "type": "rect",
                "xref": xref,
                "yref": yref,
                "x0": omit_win[0],
                "x1": omit_win[1],
                "y0": y0,
                "y1": y1,
                "fillcolor": OMISSION_PALETTE[6],
                "opacity": 0.08,
                "line": {"color": OMISSION_PALETTE[6], "width": 1.5, "dash": "dash"},
                "layer": layer,
                "name": "omission_window",
            }
        )

    return shapes


def sequence_annotations(
    y: float = 1.05,
    *,
    xref: str = "x",
    yref: str = "y",
    font_size: int = 10,
) -> List[dict]:
    """Epoch labels centered in each interval (Plotly annotations)."""
    anns: List[dict] = []
    for ep in epoch_intervals():
        mid = 0.5 * (ep.start_ms + ep.end_ms)
        anns.append(
            {
                "x": mid,
                "y": y,
                "xref": xref,
                "yref": yref,
                "text": ep.name,
                "showarrow": False,
                "font": {
                    "size": font_size,
                    "color": OMISSION_PALETTE[5] if ep.is_presentation else "#666666",
                    "family": "Arial",
                },
                "yshift": 0,
            }
        )
    return anns


def presentation_marker_traces(
    y: float = 1.08,
    *,
    marker_size: float = 10.0,
) -> List["object"]:
    """
    Top-of-panel solid vs checkered markers as Plotly scatter traces.

    Presentations → open square (checkered stand-in); fx/delays → filled square.
    """
    import plotly.graph_objects as go

    x_pres, x_delay = [], []
    for ep in epoch_intervals():
        mid = 0.5 * (ep.start_ms + ep.end_ms)
        if ep.is_presentation:
            x_pres.append(mid)
        else:
            x_delay.append(mid)

    traces = []
    if x_delay:
        traces.append(
            go.Scatter(
                x=x_delay,
                y=[y] * len(x_delay),
                mode="markers",
                marker=dict(
                    symbol="square",
                    size=marker_size,
                    color=OMISSION_PALETTE[11],
                    line=dict(width=0),
                ),
                name="delay/fx marker",
                hoverinfo="skip",
                showlegend=False,
            )
        )
    if x_pres:
        traces.append(
            go.Scatter(
                x=x_pres,
                y=[y] * len(x_pres),
                mode="markers",
                marker=dict(
                    symbol="square-open",
                    size=marker_size,
                    color=OMISSION_PALETTE[5],
                    line=dict(width=1.5, color=OMISSION_PALETTE[5]),
                ),
                name="presentation marker",
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return traces


def make_sequence_figure(
    *,
    title: str = "Omission sequence presentation layout",
    highlight_omission: Optional[str] = None,
    width: int = 1100,
    height: int = 220,
    dark: bool = False,
) -> "object":
    """Build a standalone Plotly figure of the sequence layout (vector shapes)."""
    import plotly.graph_objects as go

    bg = OMISSION_PALETTE[5] if dark else OMISSION_PALETTE[12]
    paper = bg
    fig = go.Figure()
    for tr in presentation_marker_traces(y=1.12):
        fig.add_trace(tr)

    fig.update_layout(
        title=dict(text=title, x=0.01, xanchor="left", font=dict(size=14)),
        width=width,
        height=height,
        plot_bgcolor=bg,
        paper_bgcolor=paper,
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(
            title="Time from p1 onset (ms)",
            range=[FULL_SEQUENCE_START_MS - 50, FULL_SEQUENCE_END_MS + 50],
            zeroline=False,
            showgrid=False,
            color="#333333" if not dark else "#DDDDDD",
        ),
        yaxis=dict(
            range=[-0.05, 1.25],
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            fixedrange=True,
        ),
        shapes=sequence_shapes(
            y0=0.0,
            y1=1.0,
            opacity=0.35 if dark else 0.28,
            highlight_omission=highlight_omission,
        ),
        annotations=sequence_annotations(y=1.05),
    )
    return fig


def apply_sequence_layout(
    fig: "object",
    *,
    y0: float,
    y1: float,
    highlight_omission: Optional[str] = None,
    opacity: float = 0.22,
    add_labels: bool = False,
    row: Optional[int] = None,
    col: Optional[int] = None,
) -> "object":
    """
    Overlay sequence shapes onto an existing Plotly figure / subplot.

    For plotly.subplots, pass row/col so xref/yref become xN/yN automatically
    via fig.add_shape(..., row=row, col=col).
    """
    shapes = sequence_shapes(
        y0=y0,
        y1=y1,
        opacity=opacity,
        highlight_omission=highlight_omission,
        show_boundary_lines=True,
    )
    for sh in shapes:
        kwargs = dict(sh)
        # When using add_shape with row/col, drop explicit xref/yref
        if row is not None and col is not None:
            kwargs.pop("xref", None)
            kwargs.pop("yref", None)
            fig.add_shape(kwargs, row=row, col=col)
        else:
            fig.add_shape(kwargs)

    if add_labels:
        for ann in sequence_annotations(y=y1 + 0.02 * (y1 - y0)):
            if row is not None and col is not None:
                ann = dict(ann)
                ann.pop("xref", None)
                ann.pop("yref", None)
                fig.add_annotation(ann, row=row, col=col)
            else:
                fig.add_annotation(ann)
    return fig


def export_figure_svg(fig: "object", path: Union[str, Path]) -> Path:
    """Write Plotly figure to SVG (vector). Requires kaleido."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(path), format="svg")
    return path


def export_figure_html(fig: "object", path: Union[str, Path]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(path), include_plotlyjs="cdn")
    return path


def layout_template_svgs(
    out_dir: Union[str, Path],
    conditions: Sequence[str] = R_FAMILY_CONDITIONS,
) -> Dict[str, Path]:
    """
    SVG round-trip demo: build Plotly object layout → write SVG for each condition.

    Output is editable vector SVG (rects/lines), not a flattened bitmap of the
    reference PNG template.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}

    # Base full-sequence template (no omission highlight)
    fig0 = make_sequence_figure(
        title="Full sequence fx→d4 (4624 ms)",
        highlight_omission=None,
        dark=False,
    )
    written["full_sequence"] = export_figure_svg(
        fig0, out_dir / "sequence_layout_full.svg"
    )
    export_figure_html(fig0, out_dir / "sequence_layout_full.html")

    for cond in conditions:
        fig = make_sequence_figure(
            title=f"Sequence layout · {cond}"
            + (
                f" · omission window {omission_window_ms(cond)}"
                if omission_window_ms(cond)
                else " · control (no omission)"
            ),
            highlight_omission=cond if OMISSION_SLOT.get(cond) else None,
            dark=False,
        )
        written[cond] = export_figure_svg(
            fig, out_dir / f"sequence_layout_{cond}.svg"
        )
    return written
