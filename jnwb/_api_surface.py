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
    "continuous": "public",
    "decoding": "public",
    "filtering": "public",
    "io": "public",
    "jrsa": "public",
    "laminar": "public",
    "metadata": "public",
    "nwb_inspect": "public",
    "nwb_events": "public",
    "onset_fitting": "public",
    "ontology": "public",
    "paths": "public",
    "permutation": "public",
    "rsa": "public",
    "spiking": "public",
    "spectral": "public",
    "statistics": "public",
    "tfr": "public",
    "tfr_accumulator": "public",
    "trajectory": "public",
    "unit_quality": "public",
    "viz": "public",
    "vis": "public",
    "vis.canvas": "public",
    "vis.hierarchy": "public",
    "vis.laminar": "public",
    "vis.sidecar": "public",
    "vis.spectral": "public",
    "vis.spiking": "public",
    "vis.state_space": "public",
    "vis.theme": "public",
    "visual_qc": "public",
    "_api_surface": "module-internal",
    "_backend": "module-internal",
    "_bins": "module-internal",
    "_dictlike": "module-internal",
    "_lazy_exports": "module-internal",
    "_layout": "module-internal",
    "_parallel": "module-internal",
    "_precision": "module-internal",
    "_rng": "module-internal",
    "_spread": "module-internal",
    "_units": "module-internal",
    "connectivity._common": "module-internal",
    "connectivity._granger": "module-internal",
    "connectivity._information": "module-internal",
    "connectivity._network": "module-internal",
    "connectivity._psi": "module-internal",
    "connectivity._transfer_entropy": "module-internal",
    "connectivity._trials": "module-internal",
    "jrsa._backends": "module-internal",
    "jrsa._inference": "module-internal",
    "jrsa._metrics": "module-internal",
    "jrsa._result": "module-internal",
    "jrsa._stages": "module-internal",
    "laminar._labels": "module-internal",
    "laminar._vflip": "module-internal",
    "laminar._xflip": "module-internal",
    "laminar._zflip": "module-internal",
    "spectral._common": "module-internal",
    "spectral._coupling": "module-internal",
    "spectral._decibels": "module-internal",
    "spectral._psd": "module-internal",
    "spectral._reference": "module-internal",
    "gpu_pca": "module-internal",
    "nwb_io": "module-internal",
    "testing": "module-internal",
    "testing.nwb_fixtures": "module-internal",
    "testing.synth": "module-internal",
    "bilinear": "optional-experimental",
    "nam": "optional-experimental",
    "mcp_server": "optional-experimental",
}

NON_PUBLIC_MODULES: Set[str] = {
    name for name, disp in MODULE_DISPOSITION.items() if disp != "public"
}
