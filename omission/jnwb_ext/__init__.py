"""omission.jnwb_ext: omission-task-specific extensions to the generic ``jnwb`` library.

Moved out of ``jnwb/`` on 2026-08-19 to keep that package dataset-agnostic. These
modules hardcode this experiment's condition codes (AXAB/BXBA/RXRR/...), p1-p4 slot
timing, and the S+/S-/O+ unit-classification scheme -- they only make sense for this
project. Import from ``omission`` (the package facade) rather than these submodules
directly where possible, to match the pre-restructure ``import jnwb as oa`` surface.
"""
