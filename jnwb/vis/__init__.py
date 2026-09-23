"""
jnwb.vis -- Publication-grade electrophysiology visualization engine in pure Plotly.

Enforces:
1. Pure Plotly engine (interactive HTML + camera-ready vector SVG and 300/600 DPI PNG).
2. Collision-free relative domain coordinate mathematics ([x0, x1] x [y0, y1]).
3. Triple-format default export (.svg, .png, .html) with epistemic sidecar (*_argument.json).
4. Intervals, nulls and markers are inputs: ribbons (fill='tonexty') and error bars draw the bounds
   the caller passes, and crossover markers sit at a depth the caller computed. Two panels compute
   from data: the PSTH panel draws mean +/- 1.96 SEM across trials, and the hierarchy panel draws a
   least-squares line.
"""

from __future__ import annotations

try:
    import plotly  # noqa: F401
except ImportError as exc:
    raise ImportError(
        "jnwb.vis requires Plotly, which jnwb installs only with the optional 'vis' extra: "
        "pip install jnwb[vis]"
    ) from exc

from .canvas import PlotlyPublicationCanvas
from .sidecar import EpistemicArgumentObject, serialize_argument_sidecar
from .theme import (
    COLOR_PALETTES,
    NATURE_ACCENTS,
    OKABE_ITO,
    TOL_MUTED,
    apply_publication_theme,
    configure_axis,
    get_publication_layout_template,
)

# Submodules
from . import canvas
from . import hierarchy
from . import laminar
from . import sidecar
from . import spectral
from . import spiking
from . import state_space
from . import theme

# High-level plotting function aliases
from .hierarchy import plot_hierarchy_regression
from .laminar import plot_csd, plot_opposing_gradients, plot_spectrolaminar_map
from .spectral import plot_granger_spectra, plot_spectral_modulation_matrix
from .spiking import plot_multi_condition_raster_psth, plot_sorted_heatmap
from .state_space import plot_decoding_timecourse, plot_rsm_heatmap

__all__ = [
    # Canvas & Layout
    "PlotlyPublicationCanvas",
    # Epistemic Sidecar
    "EpistemicArgumentObject",
    "serialize_argument_sidecar",
    # Theme & Palettes
    "get_publication_layout_template",
    "configure_axis",
    "COLOR_PALETTES",
    "TOL_MUTED",
    "OKABE_ITO",
    "NATURE_ACCENTS",
    # Submodules
    "canvas",
    "theme",
    "sidecar",
    "laminar",
    "spiking",
    "hierarchy",
    "spectral",
    "state_space",
    # High-level primitives
    "plot_spectrolaminar_map",
    "plot_opposing_gradients",
    "plot_csd",
    "plot_multi_condition_raster_psth",
    "plot_sorted_heatmap",
    "plot_hierarchy_regression",
    "plot_spectral_modulation_matrix",
    "plot_granger_spectra",
    "plot_decoding_timecourse",
    "plot_rsm_heatmap",
]
