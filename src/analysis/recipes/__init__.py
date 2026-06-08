"""Analysis recipe API for omission project.

Standardizes the workflow:
    Data + Specs -> Analysis Function -> Saved Output -> Figure -> Notebook

This is an orchestration layer over existing analysis engines.
"""

from __future__ import annotations

from src.analysis.recipes.specs import (
    EventSpec,
    WindowSpec,
    SignalSpec,
    AnalysisSpec,
    OutputSpec,
    RecipeResult,
    SignalClass,
    TimeBase,
    LayerStatus,
    AnalysisKind,
    CANONICAL_AREAS,
    PUBLICATION_BANDS,
)

from src.analysis.recipes.events import (
    get_event_timing_vectors,
    save_event_timing_vectors_npz,
    load_event_timing_vectors_npz,
    save_event_timing_vectors_json,
    export_event_timing_vectors_csv,
)

from src.analysis.recipes.signals import (
    get_spike_epochs,
    get_lfp_epochs,
    get_muae_epochs,
    smooth_spike_epochs,
    BLOCKED_SIGNAL_SERIES_MISSING,
    BLOCKED_SIGNAL_RATE_MISSING,
    BLOCKED_SIGNAL_WINDOW_OUT_OF_BOUNDS,
    BLOCKED_UNSUPPORTED_SIGNAL_SHAPE,
)

from src.analysis.recipes.analyses import (
    run_spike_rate,
    run_smoothed_spike_rate,
    run_tfr,
    run_band_power,
    run_spectral_coherence,
    run_spike_lfp_mi,
    run_spike_phase_locking,
    run_pac,
    build_Y_tensor,
    build_H_harmony,
)

from src.analysis.recipes.io import (
    make_recipe_output_root,
    save_array_npz,
    save_table_csv,
    save_manifest_json,
    write_recipe_manifest,
)

from src.analysis.recipes.figures import (
    plot_spike_rate_preview,
    plot_tfr_preview,
    plot_band_power_preview,
    plot_Y_tensor_heatmap,
    plot_H_harmony_heatmap,
)

from src.analysis.recipes.notebooks import (
    write_analysis_recipe_notebook,
)

__all__ = [
    # Specs
    "EventSpec",
    "WindowSpec",
    "SignalSpec",
    "AnalysisSpec",
    "OutputSpec",
    "RecipeResult",
    "SignalClass",
    "TimeBase",
    "LayerStatus",
    "AnalysisKind",
    "CANONICAL_AREAS",
    "PUBLICATION_BANDS",
    # Events
    "get_event_timing_vectors",
    "save_event_timing_vectors_npz",
    "load_event_timing_vectors_npz",
    "save_event_timing_vectors_json",
    "export_event_timing_vectors_csv",
    # Signals
    "get_spike_epochs",
    "get_lfp_epochs",
    "get_muae_epochs",
    "smooth_spike_epochs",
    "BLOCKED_SIGNAL_SERIES_MISSING",
    "BLOCKED_SIGNAL_RATE_MISSING",
    "BLOCKED_SIGNAL_WINDOW_OUT_OF_BOUNDS",
    "BLOCKED_UNSUPPORTED_SIGNAL_SHAPE",
    # Analyses
    "run_spike_rate",
    "run_smoothed_spike_rate",
    "run_tfr",
    "run_band_power",
    "run_spectral_coherence",
    "run_spike_lfp_mi",
    "run_spike_phase_locking",
    "run_pac",
    "build_Y_tensor",
    "build_H_harmony",
    # IO
    "make_recipe_output_root",
    "save_array_npz",
    "save_table_csv",
    "save_manifest_json",
    "write_recipe_manifest",
    # Figures
    "plot_spike_rate_preview",
    "plot_tfr_preview",
    "plot_band_power_preview",
    "plot_Y_tensor_heatmap",
    "plot_H_harmony_heatmap",
    # Notebooks
    "write_analysis_recipe_notebook",
]
