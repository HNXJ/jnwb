"""
jnwb.vis.canvas -- Publication-grade Plotly canvas with exact relative domain math and triple export.

Enforces:
1. Exact physical dimensions:
   - "1col": 89 mm (~336 px at 96 DPI)
   - "1.5col": 136 mm (~514 px at 96 DPI)
   - "2col": 183 mm (~692 px at 96 DPI)
   - Custom mm or pixel dimensions with height <= 235 mm (~888 px)
2. Collision-free relative domain coordinate geometry:
   - Normalized domains [x0, x1] x [y0, y1] calculated from explicit margins and gutters.
   - Panel tags ('A', 'B', 'C') anchored in paper coordinates: (x0 - delta_x, y1 + delta_y).
   - Colorbars anchored with explicit independent coordinates: x = x1 + delta_cb.
3. Triple-format default export:
   - Vector SVG (with pure <text> tags via kaleido)
   - High-resolution PNG (300/600 DPI)
   - Interactive HTML (WebGL enabled, CDN plotly.js)
   - Epistemic argument object sidecar (*_argument.json)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import plotly.graph_objects as go

from .sidecar import EpistemicArgumentObject, serialize_argument_sidecar
from .theme import (
    COLORS,
    FONT_FAMILY,
    FONT_SIZES,
    configure_axis,
    get_publication_layout_template,
)

log = logging.getLogger(__name__)

# Conversion factor: 1 mm = 3.779527559 pixels at standard 96 CSS DPI
MM_TO_PX = 3.779527559055118

STANDARD_LAYOUT_WIDTHS_MM = {
    "1col": 89.0,    # 336.38 px
    "1.5col": 136.0,  # 514.02 px
    "2col": 183.0,   # 691.65 px
}
MAX_HEIGHT_MM = 235.0  # 888.19 px


class PlotlyPublicationCanvas:
    """Publication-grade multi-panel canvas built on pure Plotly with relative domain math."""

    def __init__(
        self,
        layout: str = "2col",
        width_mm: Optional[float] = None,
        height_mm: float = 140.0,
        rows: int = 1,
        cols: int = 1,
        row_height_ratios: Optional[Sequence[float]] = None,
        col_width_ratios: Optional[Sequence[float]] = None,
        tags: Optional[Sequence[Sequence[Optional[str]]]] = None,
        left_margin_px: float = 55.0,
        right_margin_px: float = 40.0,
        top_margin_px: float = 35.0,
        bottom_margin_px: float = 45.0,
        h_gutter_px: float = 45.0,
        v_gutter_px: float = 45.0,
    ):
        """
        Initialize publication canvas.

        Args:
            layout: Preset width ('1col': 89 mm, '1.5col': 136 mm, '2col': 183 mm).
            width_mm: Explicit width in mm (overrides layout preset).
            height_mm: Explicit height in mm (maximum 235 mm).
            rows: Number of panel rows.
            cols: Number of panel columns.
            row_height_ratios: Relative height weights for rows.
            col_width_ratios: Relative width weights for columns.
            tags: Panel letter tags grid (e.g. [['A', 'B'], ['C', 'D']]).
            left_margin_px: Canvas left margin in pixels.
            right_margin_px: Canvas right margin in pixels.
            top_margin_px: Canvas top margin in pixels.
            bottom_margin_px: Canvas bottom margin in pixels.
            h_gutter_px: Horizontal spacing between columns in pixels.
            v_gutter_px: Vertical spacing between rows in pixels.
        """
        if width_mm is None:
            if layout not in STANDARD_LAYOUT_WIDTHS_MM:
                raise ValueError(
                    f"Unknown layout preset '{layout}'. Choose from {list(STANDARD_LAYOUT_WIDTHS_MM.keys())} or specify width_mm."
                )
            width_mm = STANDARD_LAYOUT_WIDTHS_MM[layout]

        if height_mm > MAX_HEIGHT_MM:
            log.warning(f"height_mm={height_mm} exceeds Nature maximum print height of {MAX_HEIGHT_MM} mm.")

        self.width_mm = width_mm
        self.height_mm = height_mm
        self.width_px = int(round(width_mm * MM_TO_PX))
        self.height_px = int(round(height_mm * MM_TO_PX))
        self.rows = rows
        self.cols = cols

        # Normalize height and width ratios
        if row_height_ratios is None:
            self.row_ratios = [1.0 / rows] * rows
        else:
            if len(row_height_ratios) != rows:
                raise ValueError(f"Length of row_height_ratios ({len(row_height_ratios)}) must match rows ({rows})")
            tot = sum(row_height_ratios)
            self.row_ratios = [r / tot for r in row_height_ratios]

        if col_width_ratios is None:
            self.col_ratios = [1.0 / cols] * cols
        else:
            if len(col_width_ratios) != cols:
                raise ValueError(f"Length of col_width_ratios ({len(col_width_ratios)}) must match cols ({cols})")
            tot = sum(col_width_ratios)
            self.col_ratios = [c / tot for c in col_width_ratios]

        # Margins and gutters
        self.left_margin_px = left_margin_px
        self.right_margin_px = right_margin_px
        self.top_margin_px = top_margin_px
        self.bottom_margin_px = bottom_margin_px
        self.h_gutter_px = h_gutter_px
        self.v_gutter_px = v_gutter_px

        # Compute relative domain coordinates for each (row, col)
        self.domains: Dict[Tuple[int, int], Tuple[Tuple[float, float], Tuple[float, float]]] = {}
        self._compute_domains()

        # Initialize Plotly Figure
        self.fig = go.Figure()
        self.fig.layout.template = get_publication_layout_template()
        self.fig.layout.width = self.width_px
        self.fig.layout.height = self.height_px
        self.fig.layout.margin = dict(l=0, r=0, t=0, b=0, pad=0)

        # Setup axes mappings
        self._setup_axes()

        # Apply panel tags if provided
        if tags is not None:
            self.add_panel_tags(tags)

    def _compute_domains(self) -> None:
        """Compute exact non-overlapping normalized domains [x0, x1] and [y0, y1] for all panels."""
        W = float(self.width_px)
        H = float(self.height_px)

        available_w = W - self.left_margin_px - self.right_margin_px - (self.cols - 1) * self.h_gutter_px
        available_h = H - self.top_margin_px - self.bottom_margin_px - (self.rows - 1) * self.v_gutter_px

        if available_w <= 0 or available_h <= 0:
            raise ValueError(
                f"Canvas dimensions ({W}x{H} px) are too small for requested margins and gutters."
            )

        # Column x positions in pixels
        col_widths_px = [self.col_ratios[c] * available_w for c in range(self.cols)]
        col_x0_px: List[float] = []
        curr_x = self.left_margin_px
        for c in range(self.cols):
            col_x0_px.append(curr_x)
            curr_x += col_widths_px[c] + self.h_gutter_px

        # Row y positions in pixels (top to bottom)
        row_heights_px = [self.row_ratios[r] * available_h for r in range(self.rows)]
        row_y_top_px: List[float] = []
        curr_y = self.top_margin_px
        for r in range(self.rows):
            row_y_top_px.append(curr_y)
            curr_y += row_heights_px[r] + self.v_gutter_px

        # Convert to Plotly normalized paper coordinates ([0, 1], where (0,0) is bottom-left)
        for r in range(self.rows):
            for c in range(self.cols):
                x0 = col_x0_px[c] / W
                x1 = (col_x0_px[c] + col_widths_px[c]) / W

                # In Plotly, y=0 is bottom and y=1 is top
                y_top = 1.0 - (row_y_top_px[r] / H)
                y_bottom = 1.0 - ((row_y_top_px[r] + row_heights_px[r]) / H)

                self.domains[(r, c)] = ((x0, x1), (y_bottom, y_top))

    def _setup_axes(self) -> None:
        """Register axes on layout for each grid panel."""
        for r in range(self.rows):
            for c in range(self.cols):
                axis_idx = r * self.cols + c + 1
                xaxis_name = "xaxis" if axis_idx == 1 else f"xaxis{axis_idx}"
                yaxis_name = "yaxis" if axis_idx == 1 else f"yaxis{axis_idx}"

                (x0, x1), (y0, y1) = self.domains[(r, c)]

                xaxis_dict = dict(domain=[x0, x1])
                configure_axis(xaxis_dict)
                setattr(self.fig.layout, xaxis_name, xaxis_dict)

                yaxis_dict = dict(domain=[y0, y1])
                configure_axis(yaxis_dict)
                setattr(self.fig.layout, yaxis_name, yaxis_dict)

    def get_axis_names(self, row: int, col: int) -> Tuple[str, str]:
        """Return (xaxis_name, yaxis_name) identifiers for a given panel."""
        if (row, col) not in self.domains:
            raise IndexError(f"Panel ({row}, {col}) does not exist on {self.rows}x{self.cols} grid.")
        idx = row * self.cols + col + 1
        x_name = "x" if idx == 1 else f"x{idx}"
        y_name = "y" if idx == 1 else f"y{idx}"
        return x_name, y_name

    def get_domain(self, row: int, col: int) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Return ((x0, x1), (y0, y1)) paper domain for a given panel."""
        return self.domains[(row, col)]

    def add_panel_tags(
        self,
        tags: Sequence[Sequence[Optional[str]]],
        offset_x_px: float = 25.0,
        offset_y_px: float = 12.0,
    ) -> None:
        """
        Add 10 pt bold panel letters ('A', 'B', 'C', ...) anchored in paper coordinates.

        Never collides with panel titles or y-axis labels.
        """
        W = float(self.width_px)
        H = float(self.height_px)
        delta_x = offset_x_px / W
        delta_y = offset_y_px / H

        for r, row_tags in enumerate(tags):
            for c, tag in enumerate(row_tags):
                if tag is None or not str(tag).strip():
                    continue
                (x0, _), (_, y1) = self.domains[(r, c)]

                # Anchor tag to top-left of the panel domain with precise offset
                self.fig.add_annotation(
                    text=f"<b>{str(tag).strip()}</b>",
                    xref="paper",
                    yref="paper",
                    x=max(0.005, x0 - delta_x),
                    y=min(0.995, y1 + delta_y),
                    xanchor="right",
                    yanchor="bottom",
                    showarrow=False,
                    font=dict(
                        family=FONT_FAMILY,
                        size=FONT_SIZES["panel_tag"],
                        color=COLORS["text"],
                    ),
                )

    def get_colorbar_config(
        self,
        row: int,
        col: int,
        title: Optional[str] = None,
        offset_x_px: float = 12.0,
        thickness_px: float = 12.0,
        height_fraction: float = 0.85,
    ) -> Dict[str, Any]:
        """
        Construct a collision-free colorbar configuration locked to a panel's domain.

        Args:
            row: Panel row.
            col: Panel column.
            title: Colorbar title text.
            offset_x_px: Horizontal gap between panel right edge and colorbar.
            thickness_px: Colorbar thickness in pixels.
            height_fraction: Fraction of panel height occupied by colorbar.
        """
        (_, x1), (y0, y1) = self.domains[(row, col)]
        W = float(self.width_px)
        delta_x = offset_x_px / W
        panel_h = y1 - y0
        cb_len = panel_h * height_fraction
        cb_y = (y0 + y1) / 2.0

        cb_dict: Dict[str, Any] = dict(
            xref="paper",
            yref="paper",
            x=x1 + delta_x,
            y=cb_y,
            len=cb_len,
            thickness=thickness_px,
            xanchor="left",
            yanchor="middle",
            tickfont=dict(family=FONT_FAMILY, size=FONT_SIZES["tick"], color=COLORS["text"]),
            ticks="outside",
            ticklen=3,
            tickcolor=COLORS["spine"],
            outlinecolor=COLORS["spine"],
            outlinewidth=0.75,
        )
        if title is not None:
            cb_dict["title"] = dict(
                text=title,
                side="right",
                font=dict(family=FONT_FAMILY, size=FONT_SIZES["axis_label"], color=COLORS["text"]),
            )
        return cb_dict

    def save_and_seal(
        self,
        output_dir: Union[str, Path],
        basename: str,
        argument_object: Union[Dict[str, Any], EpistemicArgumentObject],
        png_dpi: int = 300,
    ) -> Dict[str, Path]:
        """
        Execute the triple-format default export and epistemic sidecar seal.

        Outputs:
        1. <basename>.svg  (pure vector text)
        2. <basename>.png  (high-resolution raster preview at png_dpi)
        3. <basename>.html (self-contained interactive WebGL widget)
        4. <basename>_argument.json (canonical 8-field epistemic argument sidecar)

        Returns:
            Dictionary mapping format key ('svg', 'png', 'html', 'argument') to output Path.
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        results: Dict[str, Path] = {}

        # 1. Epistemic Sidecar JSON
        sidecar_path = out_dir / f"{basename}_argument.json"
        serialize_argument_sidecar(sidecar_path, argument_object)
        results["argument"] = sidecar_path
        log.info(f"Sealed Epistemic Sidecar: {sidecar_path}")

        # 2. Interactive HTML (CDN plotly.js)
        html_path = out_dir / f"{basename}.html"
        self.fig.write_html(
            str(html_path),
            include_plotlyjs="cdn",
            full_html=True,
            config=dict(responsive=True, displayModeBar=True),
        )
        results["html"] = html_path
        log.info(f"Exported Interactive HTML: {html_path}")

        # 3. Pure Vector SVG via Kaleido
        svg_path = out_dir / f"{basename}.svg"
        self.fig.write_image(
            str(svg_path),
            format="svg",
            width=self.width_px,
            height=self.height_px,
        )
        results["svg"] = svg_path
        log.info(f"Exported Vector SVG: {svg_path}")

        # 4. High-Resolution PNG via Kaleido
        scale_factor = float(png_dpi) / 96.0
        png_path = out_dir / f"{basename}.png"
        self.fig.write_image(
            str(png_path),
            format="png",
            width=self.width_px,
            height=self.height_px,
            scale=scale_factor,
        )
        results["png"] = png_path
        log.info(f"Exported High-Res PNG ({png_dpi} DPI): {png_path}")

        # Verify all files exist and have non-zero size
        for fmt, p in results.items():
            if not p.exists() or p.stat().st_size == 0:
                raise RuntimeError(f"Export verification failed: {fmt} file {p} was not written properly.")

        return results
