"""Deterministic synthetic NWB fixtures and signal generators for tests and tutorials."""

from .nwb_fixtures import (
    SynthNWBBuildOptions,
    SynthNWBReceipt,
    build_synth_nwb,
    canonical_co_resident_options,
    lfp_wrapped_options,
    numeric_codes_options,
    task_only_options,
    write_synth_nwb,
)
from .synth import (
    SynthLaminarReceipt,
    build_canonical_tutorial_nwb,
    synth_ar_noise,
    synth_correlation_blocks,
    synth_laminar_motif,
    synth_periodic_response,
    synth_phase_gradient,
    synth_unequal_groups,
    synth_white_noise,
)

__all__ = [
    "SynthLaminarReceipt",
    "SynthNWBBuildOptions",
    "SynthNWBReceipt",
    "build_canonical_tutorial_nwb",
    "build_synth_nwb",
    "canonical_co_resident_options",
    "lfp_wrapped_options",
    "numeric_codes_options",
    "synth_ar_noise",
    "synth_correlation_blocks",
    "synth_laminar_motif",
    "synth_periodic_response",
    "synth_phase_gradient",
    "synth_unequal_groups",
    "synth_white_noise",
    "task_only_options",
    "write_synth_nwb",
]

