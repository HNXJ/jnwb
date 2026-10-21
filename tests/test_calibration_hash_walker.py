"""The calibration receipts' code walker resolves a package's relative imports against the package."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.calibrate_xflip import _module_table  # noqa: E402


def test_a_package_init_resolves_its_relative_imports_against_itself():
    """`jnwb/laminar/__init__.py` holds `from ._vflip2 import ...`; read against `jnwb` it named
    `jnwb._vflip2`, which does not exist."""
    _, _, imported = _module_table("jnwb.laminar")
    assert imported["vflip2"] == ("jnwb.laminar._vflip2", "vflip2")


def test_a_module_still_resolves_against_its_parent():
    _, _, imported = _module_table("jnwb.laminar_curation")
    assert imported, "fixture must import from other jnwb modules"
    assert not any(origin.startswith("jnwb.laminar_curation.") for origin, _ in imported.values())
