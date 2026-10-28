"""Central path resolution for jnwb.

Two kinds of root, resolved differently:

* **Working-directory outputs/artifacts** (:func:`outputs_dir`, :func:`artifacts_dir`):
  Precedence: explicit ``override`` argument > ``$JNWB_OUTPUTS_DIR`` >
  ``Path.cwd() / 'outputs'`` or ``'artifacts'``
  (process working-directory default, independent of package installation location).
* **External data roots** (:func:`nwb_dir`, :func:`analysis_dir`, and the
  :func:`tfr_dir` / :func:`meta_dir` / :func:`conndb_dir` subtrees under it):
  Precedence: explicit ``override`` > primary ``$JNWB_*`` environment variable >
  ``None`` (raises FileNotFoundError explaining how to configure the path).

:func:`describe` reports every root and whether it currently resolves -- run it
first after any drive remap or environment configuration.

Nothing here validates existence at import time. Callers that need a path to be
present should use :func:`require`, which fails with the env var name to set
rather than with a bare ``FileNotFoundError``.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "PACKAGE_ROOT",
    "ENV_NWB_DIR",
    "ENV_TFR_DIR",
    "ENV_META_DIR",
    "ENV_CONNDB_DIR",
    "ENV_ANALYSIS_DIR",
    "ENV_OUTPUTS_DIR",
    "ENV_ARTIFACTS_DIR",
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
    "resolve_nwb_path",
    "sha256_file",
    "sha256_groups",
    "require",
    "describe",
]

# jnwb/paths.py -> jnwb/ -> the root of THIS package's own source tree.
#
# Named PACKAGE_ROOT, not REPO_ROOT, because it is jnwb's root and never the caller's.
# Under the old name every consumer read it as "my repository root": it resolves from
# this file's location, so in a consuming project it points at the jnwb checkout. The
# path is well-formed, it is the wrong tree, so the failure is silent. One
# project had 41 live files building inputs and outputs from it; they resolved under
# the jnwb checkout, and the script producing its stable-unit presence table had
# therefore never run. A consumer wanting its own root should anchor explicitly, e.g.
# Path(__file__).resolve().parent.parent -- not ask a library where it lives.
PACKAGE_ROOT: Path = Path(__file__).resolve().parent.parent

# Primary generic environment variable names
ENV_NWB_DIR = "JNWB_NWB_DIR"
ENV_TFR_DIR = "JNWB_TFR_DIR"
ENV_META_DIR = "JNWB_META_DIR"
ENV_CONNDB_DIR = "JNWB_CONNDB_DIR"
ENV_ANALYSIS_DIR = "JNWB_ANALYSIS_DIR"
ENV_OUTPUTS_DIR = "JNWB_OUTPUTS_DIR"
ENV_ARTIFACTS_DIR = "JNWB_ARTIFACTS_DIR"

#: No default data-volume layout. External data lives on a separate volume with a layout
#: specific to each machine and project. ``None`` means :func:`nwb_dir` / :func:`analysis_dir`
#: raise a clear, actionable error naming the env var to set, instead of silently resolving
#: to a path that is wrong (or doesn't exist) on any other machine or project.
DEFAULT_NWB_DIR = None
DEFAULT_ANALYSIS_DIR = None

#: Derived-data subtrees. Resolved under :func:`analysis_dir` so that repointing the
#: analysis volume moves all of them together.
TFR_SUBDIR = "tfr_arrays"
META_SUBDIR = "metadata"
CONNDB_SUBDIR = "connectivity_databases"


def _resolve_env(primary_var: str) -> str | None:
    """The value of ``primary_var``, or ``None`` when it is unset or empty."""
    val = os.environ.get(primary_var)
    if val:
        return val
    return None


def nwb_dir(override: str | os.PathLike | None = None) -> Path:
    """Directory holding the session NWB files.

    Precedence: explicit ``override`` > ``$JNWB_NWB_DIR`` >
    :data:`DEFAULT_NWB_DIR` (``None`` by design -- there is no machine- or project-generic default).
    Raises ``FileNotFoundError`` naming the env var when none of those resolve to a path.
    """
    if override is not None:
        return Path(override)
    resolved = _resolve_env(ENV_NWB_DIR) or DEFAULT_NWB_DIR
    if resolved is None:
        raise FileNotFoundError(
            f"No NWB directory configured. Pass override=, or set ${ENV_NWB_DIR}."
        )
    return Path(resolved)


def analysis_dir(*parts: str, override: str | os.PathLike | None = None) -> Path:
    """Root of the derived-data volume: arrays, matrices, supplements, post-process output.

    Precedence: explicit ``override`` > ``$JNWB_ANALYSIS_DIR`` >
    :data:`DEFAULT_ANALYSIS_DIR` (``None`` by design).
    Raises ``FileNotFoundError`` naming the env var when none of those resolve to a path.
    """
    if override is not None:
        root = Path(override)
    else:
        resolved = _resolve_env(ENV_ANALYSIS_DIR) or DEFAULT_ANALYSIS_DIR
        if resolved is None:
            raise FileNotFoundError(
                f"No analysis directory configured. Pass override=, or set ${ENV_ANALYSIS_DIR}."
            )
        root = Path(resolved)
    return root.joinpath(*parts)


def _configured_dir(
    override: str | os.PathLike | None,
    env: str,
    subdir: str,
) -> Path:
    """The body behind `tfr_dir`, `meta_dir` and `conndb_dir`.

    Precedence: explicit ``override`` > ``$env`` > ``<analysis_dir>/subdir``. Each caller
    supplies its own two names and documents them concretely; only this resolution order
    is shared.
    """
    if override is not None:
        return Path(override)
    env_path = _resolve_env(env)
    if env_path:
        return Path(env_path)
    return Path(analysis_dir(subdir))


def tfr_dir(override: str | os.PathLike | None = None) -> Path:
    """Directory holding precomputed TFR arrays.

    Precedence: explicit ``override`` > ``$JNWB_TFR_DIR`` > ``<analysis_dir>/tfr_arrays``.
    """
    return _configured_dir(override, ENV_TFR_DIR, TFR_SUBDIR)


def meta_dir(override: str | os.PathLike | None = None) -> Path:
    """Directory holding session metadata sidecars (channel maps, layer exports).

    Precedence: explicit ``override`` > ``$JNWB_META_DIR`` > ``<analysis_dir>/metadata``.
    """
    return _configured_dir(override, ENV_META_DIR, META_SUBDIR)


def conndb_dir(override: str | os.PathLike | None = None) -> Path:
    """Directory holding connectivity databases, incl. layer assignments.

    Precedence: explicit ``override`` > ``$JNWB_CONNDB_DIR`` > ``<analysis_dir>/connectivity_databases``.
    """
    return _configured_dir(override, ENV_CONNDB_DIR, CONNDB_SUBDIR)


def outputs_dir(*parts: str, override: str | os.PathLike | None = None) -> Path:
    """Path under the designated outputs directory.

    Precedence: explicit ``override`` > ``$JNWB_OUTPUTS_DIR`` > ``Path.cwd() / 'outputs'``
    (process working-directory default, independent of package installation location).
    """
    if override is not None:
        root = Path(override)
    else:
        resolved = _resolve_env(ENV_OUTPUTS_DIR)
        root = Path(resolved) if resolved else Path.cwd() / "outputs"
    return root.joinpath(*parts)


def artifacts_dir(*parts: str, override: str | os.PathLike | None = None) -> Path:
    """Path under the designated artifacts directory.

    Precedence: explicit ``override`` > ``$JNWB_ARTIFACTS_DIR`` > ``Path.cwd() / 'artifacts'``
    (process working-directory default, independent of package installation location).
    """
    if override is not None:
        root = Path(override)
    else:
        resolved = _resolve_env(ENV_ARTIFACTS_DIR)
        root = Path(resolved) if resolved else Path.cwd() / "artifacts"
    return root.joinpath(*parts)


def layer_masks_path(subdir: str | os.PathLike = "publication_visual_review/area_layer_tfr") -> Path:
    """``layer_masks.json`` in ``subdir`` of the outputs directory (:func:`outputs_dir`).

    Args:
        subdir: The folder under the outputs directory, relative to it. The default is one
            corpus's convention, kept so existing callers resolve the same file; a project
            with another layout passes its own.

    Raises:
        ValueError: If ``subdir`` is empty, absolute or rooted (``'/x'``, and on Windows ``'C:x'``), or has
            a ``'..'`` component; each resolves to the outputs directory itself or outside it.
    """
    parts = Path(subdir)
    if not parts.parts:
        raise ValueError(f"layer_masks_path: subdir {subdir!r} is empty; name a folder "
                         f"under the outputs directory.")
    if parts.anchor:
        raise ValueError(f"layer_masks_path: subdir {subdir!r} is absolute; it is relative "
                         f"to the outputs directory.")
    if ".." in parts.parts:
        raise ValueError(f"layer_masks_path: subdir {subdir!r} has a '..' component, which "
                         f"leaves the outputs directory.")
    return outputs_dir(subdir, "layer_masks.json")


def resolve_nwb_path(
    prefix: str,
    nwb_dir_override: str | os.PathLike | None = None,
    *,
    suffixes: tuple[str, ...] = ("_rec", ""),
) -> Path:
    """Resolve a session prefix to its NWB file: the first existing file among
    ``{prefix}{suffix}.nwb``, probed in the order of ``suffixes``.

    Raises ``FileNotFoundError`` naming every probed path when none is a file. A name that
    only starts with a probe (``{prefix}_rec-old.nwb``) never matches. Pass ``suffixes`` for
    another naming scheme.
    """
    base = nwb_dir(nwb_dir_override)
    probes = [base / (prefix + suffix + ".nwb") for suffix in suffixes]
    for probe in probes:
        if probe.is_file():
            return probe
    raise FileNotFoundError(
        f"No NWB file for session prefix {prefix!r} in {base}. "
        f"Probed: {', '.join(str(p) for p in probes)}."
    )


def sha256_file(path: str | os.PathLike, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 hex digest of a file, read in chunks (no full read into memory)."""
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _frame(data: bytes) -> bytes:
    """``data`` with its length prefixed, so adjacent fields cannot run together."""
    return len(data).to_bytes(8, "little") + data


def sha256_groups(path: str | os.PathLike, groups: Iterable[str]) -> str:
    """SHA-256 hex digest of every dataset under the named HDF5 groups of ``path``.

    Each dataset contributes its path in the file, its shape, its dtype and its bytes.
    Datasets are hashed in sorted path order, so the order of ``groups`` changes nothing.
    Datasets outside the named groups, file attributes and timestamps do not contribute.

    Raises:
        KeyError: If the file holds no group of a given name; the message names it.
        ValueError: If ``groups`` is empty; there is nothing to hash.
    """
    import h5py
    import numpy as np

    groups = list(groups)
    if not groups:
        raise ValueError("sha256_groups: groups is empty; name at least one group to hash")

    found: dict[str, h5py.Dataset] = {}
    with h5py.File(path, "r") as f:
        for group in groups:
            if group not in f:
                raise KeyError(f"sha256_groups: no group {group!r} in {path}")
            node = f[group]
            if isinstance(node, h5py.Dataset):
                found[node.name] = node
            else:
                def collect(_name, obj):
                    if isinstance(obj, h5py.Dataset):
                        found[obj.name] = obj
                node.visititems(collect)
        h = hashlib.sha256()
        for name in sorted(found):
            ds = found[name]
            values = np.asarray(ds[()])
            if values.dtype.kind == "O":
                payload = [repr(v).encode("utf-8") for v in values.ravel()]
            else:
                payload = [np.ascontiguousarray(values).tobytes()]
            h.update(_frame(repr((name, tuple(ds.shape), ds.dtype.str)).encode("utf-8")))
            for part in payload:
                h.update(_frame(part))
    return h.hexdigest()


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

    Diagnostic helper -- reports whether external-data roots (``nwb_dir``, ``tfr_dir``,
    ``meta_dir``, ``analysis_dir``, ``conndb_dir``) and outputs/artifacts are configured.
    """
    result = {
        "PACKAGE_ROOT": {"path": str(PACKAGE_ROOT), "exists": PACKAGE_ROOT.exists()},
        f"outputs (${ENV_OUTPUTS_DIR})": {"path": str(outputs_dir()), "exists": outputs_dir().exists()},
        f"artifacts (${ENV_ARTIFACTS_DIR})": {"path": str(artifacts_dir()), "exists": artifacts_dir().exists()},
        "layer_masks": {"path": str(layer_masks_path()), "exists": layer_masks_path().exists()},
    }
    external_roots = {
        f"nwb_dir (${ENV_NWB_DIR})": nwb_dir,
        f"tfr_dir (${ENV_TFR_DIR})": tfr_dir,
        f"meta_dir (${ENV_META_DIR})": meta_dir,
        f"analysis_dir (${ENV_ANALYSIS_DIR})": analysis_dir,
        f"conndb_dir (${ENV_CONNDB_DIR})": conndb_dir,
    }
    for label, resolver in external_roots.items():
        try:
            p = resolver()
            result[label] = {"path": str(p), "exists": p.exists(), "configured": True}
        except FileNotFoundError as exc:
            result[label] = {"path": None, "exists": False, "configured": False, "error": str(exc)}
    return result

