"""Module disposition registry for the jnwb package surface.

``jnwb.__all__`` is the authoritative list of public symbols. This module records
which active modules are public, module-internal, or optional/experimental so
mechanical tests can detect unclassified or leaked modules.
"""

from __future__ import annotations

from typing import Dict, Literal, Set

Disposition = Literal[
    "public",
    "module-internal",
    "optional-experimental",
    "dead-parked",
]

# Every active ``jnwb`` module (``mcp_server`` is one package entry, not per-file).
MODULE_DISPOSITION: Dict[str, Disposition] = {
    "__init__": "public",
    "addressing": "public",
    "analyzers": "public",
    "artifact_detection": "public",
    "artifact_repair": "public",
    "compression": "public",
    "connectivity": "public",
    "decoding": "public",
    "filtering": "public",
    "jrsa": "public",
    "metadata": "public",
    "nwb_inspect": "public",
    "nwb_events": "public",
    "onset_fitting": "public",
    "ontology": "public",
    "paths": "public",
    "permutation": "public",
    "spiking": "public",
    "spectral": "public",
    "statistics": "public",
    "tfr": "public",
    "tfr_accumulator": "public",
    "trajectory": "public",
    "viz": "public",
    "visual_qc": "public",
    "_api_surface": "module-internal",
    "_backend": "module-internal",
    "_lazy_exports": "module-internal",
    "_parallel": "module-internal",
    "gpu_pca": "module-internal",
    "nwb_io": "module-internal",
    "testing": "module-internal",
    "testing.nwb_fixtures": "module-internal",
    "bilinear": "optional-experimental",
    "nam": "optional-experimental",
    "mcp_server": "optional-experimental",
}

NON_PUBLIC_MODULES: Set[str] = {
    name for name, disp in MODULE_DISPOSITION.items() if disp != "public"
}
