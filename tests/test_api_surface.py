"""Mechanical checks for jnwb module disposition vs public exports."""
from __future__ import annotations

import ast
import importlib
import re
import types
from pathlib import Path

import jnwb
from jnwb._api_surface import MODULE_DISPOSITION, NON_PUBLIC_MODULES
from jnwb._lazy_exports import EXPORT_MODULES, SUBMODULES

REPO_ROOT = Path(__file__).resolve().parents[1]
JNWB_DIR = REPO_ROOT / "jnwb"
MODULE_MAP_PAGE = REPO_ROOT / "docs" / "01_architecture_and_philosophy.md"


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



def test_lazy_export_modules_are_public():
    for module_name in set(EXPORT_MODULES.values()):
        assert MODULE_DISPOSITION.get(module_name) == "public", module_name


# --------------------------------------------------------------------------- module map


def _owner(name: str) -> str | None:
    """The jnwb module an exported name belongs to, or None for a plain constant.

    Resolved from the registries first, so a name behind an optional extra is never imported.
    """
    if name in SUBMODULES:
        return name
    if name in EXPORT_MODULES:
        return EXPORT_MODULES[name]
    obj = getattr(jnwb, name)
    if isinstance(obj, types.ModuleType):
        return obj.__name__.split(".", 1)[1]
    if isinstance(obj, type) or callable(obj):
        module = getattr(obj, "__module__", "") or ""
        if module.startswith("jnwb."):
            return module.split(".")[1]
    return None


def _module_map_rows() -> dict[str, list[str]]:
    text = MODULE_MAP_PAGE.read_text(encoding="utf-8")
    heading = re.search(r"^## [^\n]*Module Map[^\n]*$", text, re.M)
    assert heading, f"{MODULE_MAP_PAGE.name} has no Module Map section"
    section = text[heading.end():]
    following = re.search(r"^## ", section, re.M)
    section = section[: following.start()] if following else section
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows[cells[0].strip("`")] = re.findall(r"`([A-Za-z_]\w*)`", cells[-1])
    return rows


def test_the_module_map_has_a_row_for_every_module_that_owns_an_export():
    """The map on the philosophy page is the only per-module summary a reader gets.

    It once omitted the modules a reader calls first -- file discovery, event onsets, the
    NWB read -- together with the time-frequency, laminar and RDM operations, and nothing
    compared it with the package. A row whose symbols another module owns, or that are no
    longer exported, misroutes the reader the same way.
    """
    rows = _module_map_rows()
    owners = {name: _owner(name) for name in jnwb.__all__}
    owning = {module for module in owners.values() if module is not None}
    # Bypasses: a table that stops parsing, or an owner lookup that resolves nothing, would
    # leave both comparisons below vacuous.
    assert "spectral" in rows and len(rows) >= 10, sorted(rows)
    assert {"spectral", "nwb_inspect", "laminar"} <= owning, sorted(owning)

    missing = sorted(owning - set(rows))
    assert not missing, f"modules owning exports with no module-map row: {missing}"

    wrong = []
    for module, symbols in rows.items():
        assert symbols, f"module-map row {module!r} names no symbol"
        for symbol in symbols:
            if symbol not in jnwb.__all__:
                wrong.append(f"{module}: {symbol} is not exported")
            elif owners[symbol] is None:
                if not hasattr(importlib.import_module(f"jnwb.{module}"), symbol):
                    wrong.append(f"{module}: constant {symbol} is not defined there")
            elif owners[symbol] != module:
                wrong.append(f"{module}: {symbol} belongs to {owners[symbol]}")
    assert not wrong, "module-map rows name symbols they do not own:\n" + "\n".join(wrong)


# --------------------------------------------------------------------------- synthetic data


def _imported_modules(tree: ast.Module, package: list[str]) -> set[str]:
    """Every absolute module name `tree` imports, relative imports resolved against `package`."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - (node.level - 1)] if node.level else []
            stem = base + (node.module.split(".") if node.module else [])
            found.add(".".join(stem))
            # `from . import testing` names the module in the alias, not in `module`.
            found.update(".".join(stem + [alias.name]) for alias in node.names)
    return found


def _is_testing(module: str) -> bool:
    return module == "jnwb.testing" or module.startswith("jnwb.testing.")


def test_no_analysis_module_imports_the_synthetic_generators():
    """`docs/01_architecture_and_philosophy.md` says synthetic signals live in `jnwb.testing`
    and are never presented as measurements. That holds only while no module outside
    `jnwb/testing/` can reach the generators: an analysis path that imports one can fill a
    gap in real data with a plausible synthetic value, and nothing downstream can tell.
    """
    # The detector on each import form, so a resolver that finds nothing cannot pass.
    def detected(source: str, package: list[str]) -> set[str]:
        return {m for m in _imported_modules(ast.parse(source), package) if _is_testing(m)}

    assert detected("import jnwb.testing.synth", ["jnwb"]) == {"jnwb.testing.synth"}
    assert "jnwb.testing" in detected("from jnwb.testing import nwb_fixtures", ["jnwb"])
    assert "jnwb.testing" in detected("from . import testing", ["jnwb"])
    assert "jnwb.testing.synth" in detected("from .testing import synth", ["jnwb"])
    assert detected("def f():\n    from ..testing.synth import x\n", ["jnwb", "vis"])
    assert not detected("from .testing import x\nfrom . import spectral", ["jnwb", "vis"])

    assert "testing" not in jnwb.__all__
    violations = []
    for path in sorted(JNWB_DIR.rglob("*.py")):
        rel = path.relative_to(JNWB_DIR)
        if "__pycache__" in rel.parts or rel.parts[0] == "testing":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found = sorted(m for m in _imported_modules(tree, ["jnwb", *rel.parts[:-1]])
                       if _is_testing(m))
        if found:
            violations.append(f"jnwb/{rel.as_posix()} imports {found}")
    assert not violations, "\n".join(violations)
