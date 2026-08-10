"""Central path resolution for jnwb.

Added 2026-08-08. Before this module, roots were hardcoded as absolute ``D:/...``
literals in ``session.py``, ``viz.py``, ``report.py`` and ~27 scripts. A drive
remap broke all of them at once, and the four literals that pointed at the repo's
own ``outputs/`` through a drive letter (``D:/workspace/omission/outputs/...``)
became permanently wrong once the repo moved to ``C:\\workspace\\omission`` --
silently, because they were default arguments that resolve to a nonexistent path
rather than raise.

Two kinds of root, resolved differently:

* **Repo-internal** (``REPO_ROOT``, :func:`outputs_dir`, :func:`artifacts_dir`) --
  derived from this file's own location. Always correct, never configurable;
  the repo cannot be anywhere other than where its own source is.
* **External data** (:func:`nwb_dir`, :func:`analysis_dir`, and the
  :func:`tfr_dir` / :func:`meta_dir` / :func:`conndb_dir` subtrees under it) -- lives on a separate volume that moves. Resolved from an
  environment variable with a documented fallback. ``OMISSION_TFR_DIR`` and
  ``OMISSION_META_DIR`` predate this module (``session.py`` and
  ``build_session_readiness.py`` respectively) and are kept verbatim so existing
  shells keep working.

:func:`describe` reports every root and whether it currently resolves -- run it
first after any drive remap.

Nothing here validates existence at import time. Callers that need a path to be
present should use :func:`require`, which fails with the env var name to set
rather than with a bare ``FileNotFoundError``.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "REPO_ROOT",
    "ENV_NWB_DIR",
    "ENV_TFR_DIR",
    "ENV_META_DIR",
    "ENV_CONNDB_DIR",
    "ENV_ANALYSIS_DIR",
    "DEFAULT_NWB_DIR",
    "DEFAULT_ANALYSIS_DIR",
    "TFR_SUBDIR",
    "META_SUBDIR",
    "CONNDB_SUBDIR",
    "nwb_dir",
    "tfr_dir",
    "meta_dir",
    "conndb_dir",
    "analysis_dir",
    "outputs_dir",
    "artifacts_dir",
    "layer_masks_path",
    "require",
    "describe",
]

# jnwb/paths.py -> jnwb/ -> repo root
REPO_ROOT: Path = Path(__file__).resolve().parent.parent

ENV_NWB_DIR = "OMISSION_NWB_DIR"
ENV_TFR_DIR = "OMISSION_TFR_DIR"
ENV_META_DIR = "OMISSION_META_DIR"
ENV_CONNDB_DIR = "OMISSION_CONNDB_DIR"
ENV_ANALYSIS_DIR = "OMISSION_ANALYSIS_DIR"

#: Data-volume layout, corrected 2026-08-08 (second revision, same day).
#:
#: The first version of this module inherited the pre-remap literals -- NWBs at
#: ``D:/analysis/nwb`` and derived data under ``D:/workspace/data/*``. Both were
#: wrong: those were the OLD layout, and D: was empty at the time so nothing
#: contradicted them. The live layout is:
#:
#:   D:/nwb/omission/   -- omission NWB sessions  (D:/nwb/mglo/ is a DIFFERENT experiment)
#:   D:/analysis/       -- every derived artifact: arrays, matrices, supplements, post-process
#:
#: These remain *defaults*, not guarantees. Override with the env vars above.
DEFAULT_NWB_DIR = "D:/nwb/omission"
DEFAULT_ANALYSIS_DIR = "D:/analysis"
#: Derived-data subtrees. Resolved under :func:`analysis_dir` so that repointing the
#: analysis volume moves all of them together.
TFR_SUBDIR = "tfr_arrays"
META_SUBDIR = "metadata"
CONNDB_SUBDIR = "connectivity_databases"


def nwb_dir(override: str | os.PathLike | None = None) -> Path:
    """Directory holding the ``sub-*_ses-*_rec.nwb`` session files.

    Precedence: explicit ``override`` > ``$OMISSION_NWB_DIR`` > :data:`DEFAULT_NWB_DIR`.
    """
    if override is not None:
        return Path(override)
    return Path(os.environ.get(ENV_NWB_DIR) or DEFAULT_NWB_DIR)


def analysis_dir(*parts: str, override: str | os.PathLike | None = None) -> Path:
    """Root of the derived-data volume: arrays, matrices, supplements, post-process output.

    Everything the pipeline produces from NWBs lives under here, NOT in the repo.
    Precedence: explicit ``override`` > ``$OMISSION_ANALYSIS_DIR`` > :data:`DEFAULT_ANALYSIS_DIR`.
    """
    root = Path(override) if override is not None else Path(
        os.environ.get(ENV_ANALYSIS_DIR) or DEFAULT_ANALYSIS_DIR
    )
    return root.joinpath(*parts)


def tfr_dir(override: str | os.PathLike | None = None) -> Path:
    """Directory holding precomputed TFR arrays.

    Precedence: explicit ``override`` > ``$OMISSION_TFR_DIR`` > ``<analysis_dir>/tfr_arrays``.
    """
    if override is not None:
        return Path(override)
    return Path(os.environ.get(ENV_TFR_DIR) or analysis_dir(TFR_SUBDIR))


def meta_dir(override: str | os.PathLike | None = None) -> Path:
    """Directory holding session metadata sidecars (channel maps, layer exports).

    Precedence: explicit ``override`` > ``$OMISSION_META_DIR`` > ``<analysis_dir>/metadata``.
    """
    if override is not None:
        return Path(override)
    return Path(os.environ.get(ENV_META_DIR) or analysis_dir(META_SUBDIR))


def conndb_dir(override: str | os.PathLike | None = None) -> Path:
    """Directory holding connectivity databases, incl. vFLIP2 ``*_channel_layers.csv``.

    Precedence: explicit ``override`` > ``$OMISSION_CONNDB_DIR`` > ``<analysis_dir>/connectivity_databases``.
    """
    if override is not None:
        return Path(override)
    return Path(os.environ.get(ENV_CONNDB_DIR) or analysis_dir(CONNDB_SUBDIR))


def outputs_dir(*parts: str) -> Path:
    """A path under the repo's ``outputs/`` tree. Always repo-relative."""
    return REPO_ROOT.joinpath("outputs", *parts)


def artifacts_dir(*parts: str) -> Path:
    """A path under the repo's ``artifacts/`` tree. Always repo-relative."""
    return REPO_ROOT.joinpath("artifacts", *parts)


def layer_masks_path() -> Path:
    """Canonical vFLIP layer-mask JSON. Repo-internal, so never configurable."""
    return outputs_dir("publication_visual_review", "area_layer_tfr", "layer_masks.json")


def require(path: str | os.PathLike, what: str, env_var: str | None = None) -> Path:
    """Return ``path`` if it exists, else raise with the fix in the message.

    Args:
        path: The resolved path to check.
        what: Human-readable description, e.g. ``"NWB session directory"``.
        env_var: Environment variable that would override it, if any.
    """
    p = Path(path)
    if p.exists():
        return p
    hint = f" Set ${env_var} to point at it." if env_var else ""
    raise FileNotFoundError(f"{what} not found: {p}.{hint}")


def describe() -> dict:
    """Every root this module resolves, with whether it currently exists.

    Diagnostic helper -- call after a drive remap to see what is reachable.
    """
    roots = {
        "REPO_ROOT": REPO_ROOT,
        "outputs": outputs_dir(),
        "artifacts": artifacts_dir(),
        "layer_masks": layer_masks_path(),
        f"nwb_dir (${ENV_NWB_DIR})": nwb_dir(),
        f"tfr_dir (${ENV_TFR_DIR})": tfr_dir(),
        f"meta_dir (${ENV_META_DIR})": meta_dir(),
        f"analysis_dir (${ENV_ANALYSIS_DIR})": analysis_dir(),
        f"conndb_dir (${ENV_CONNDB_DIR})": conndb_dir(),
    }
    return {k: {"path": str(v), "exists": v.exists()} for k, v in roots.items()}
