"""Mechanical checks for jnwb module disposition vs public exports."""
from __future__ import annotations

from pathlib import Path

import jnwb
from jnwb._api_surface import MODULE_DISPOSITION, NON_PUBLIC_MODULES
from jnwb._lazy_exports import EXPORT_MODULES, SUBMODULES

REPO_ROOT = Path(__file__).resolve().parents[1]
JNWB_DIR = REPO_ROOT / "jnwb"


def _discovered_module_keys() -> set[str]:
    keys: set[str] = set()
    for path in sorted(JNWB_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(JNWB_DIR)
        if rel.parts[0] == "mcp_server":
            if rel.name == "__init__.py":
                keys.add("mcp_server")
            continue
        stem = rel.with_suffix("").as_posix().replace("/", ".")
        if stem.endswith("__init__"):
            stem = stem[: -len("__init__")].rstrip(".") or "__init__"
        keys.add(stem)
    return keys


def test_every_active_module_is_classified():
    discovered = _discovered_module_keys()
    registered = set(MODULE_DISPOSITION)
    assert discovered == registered, (
        f"unclassified or stale registry entries: "
        f"discovered-only={sorted(discovered - registered)!r}, "
        f"registry-only={sorted(registered - discovered)!r}"
    )


def test_non_public_modules_are_not_exported():
    assert NON_PUBLIC_MODULES.isdisjoint(set(EXPORT_MODULES.values()))
    assert NON_PUBLIC_MODULES.isdisjoint(SUBMODULES)
    for name in ("gpu_pca", "nwb_io", "bilinear", "nam", "mcp_server"):
        assert name not in jnwb.__all__
        assert name not in EXPORT_MODULES


def test_public_exports_resolve():
    missing = [name for name in jnwb.__all__ if not hasattr(jnwb, name)]
    assert not missing, f"__all__ names not bound: {missing}"


def test_lazy_export_modules_are_public():
    for module_name in set(EXPORT_MODULES.values()):
        assert MODULE_DISPOSITION.get(module_name) == "public", module_name
