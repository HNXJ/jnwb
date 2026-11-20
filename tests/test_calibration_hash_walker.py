"""The calibration receipts' code walker resolves a package's relative imports against the package."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # needed: the installed-wheel run clears pythonpath

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


def _load_calibration_script(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _receipt_raw_name(path: pathlib.Path, module) -> str:
    if hasattr(module, "STEM"):
        return f"{module.STEM}_raw.json"
    matches = sorted(set(re.findall(r"\b\w[\w.]*_raw\.json\b", path.read_text(encoding="utf-8"))))
    assert len(matches) == 1, f"{path.name} must name one *_raw.json receipt, found {matches}"
    return matches[0]


def test_every_calibrate_script_receipt_is_current_and_checked_by_a_test():
    scripts = sorted((ROOT / "scripts").glob("calibrate_*.py"))
    assert len(scripts) >= 4, "expected at least the four laminar calibration scripts"
    calibration_dir = ROOT / "artifacts" / "benchmarks" / "calibration"
    test_sources = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "tests").glob("test_*.py"))
        if p.name != "test_calibration_hash_walker.py"
    }
    for script_path in scripts:
        module = _load_calibration_script(script_path)
        raw_name = _receipt_raw_name(script_path, module)
        raw_path = calibration_dir / raw_name
        assert raw_path.is_file(), f"{script_path.name} receipt {raw_path} is missing"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        live_sha = (
            module.estimator_shas()
            if hasattr(module, "estimator_shas")
            else module.estimator_sha256()
        )
        assert raw["estimator_sha256"] == live_sha, (
            f"{raw_name} estimator_sha256 is stale for {script_path.name}"
        )
        stem_token = getattr(module, "STEM", raw_name)
        referencing_tests = [
            name for name, src in test_sources.items()
            if (raw_name in src or stem_token in src)
            and ("estimator_sha256" in src or "estimator_shas" in src)
        ]
        assert referencing_tests, (
            f"no dedicated test file checks estimator_sha256/estimator_shas for {raw_name}"
        )
