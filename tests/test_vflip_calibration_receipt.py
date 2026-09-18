"""The vFLIP calibration receipt must describe the estimator that ships.

The 0.2.2 receipt was generated before the support score was density-normalized and the
crossover polarity rule changed, and no generator was kept, so its numbers described a
different estimator and could not be reproduced. The receipt records a hash of the
estimator; changing it without rerunning ``scripts/calibrate_vflip.py`` fails here.

That hash covered ``inspect.getsource(vflip)`` alone, while ``vflip`` delegates the band
normalization to ``_unit_range``. A line-count-preserving defect in that helper left the
receipt reading "current" and this file passing 4 of 4, so the hash now covers every
module-level function in ``jnwb.laminar`` that ``vflip`` can reach.
"""

import ast
import importlib.util
import inspect
import json
import pathlib

from jnwb import laminar
from jnwb.laminar import vflip

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "artifacts" / "benchmarks" / "vflip_calibration_0.2.4_raw.json"
REPORT = ROOT / "artifacts" / "benchmarks" / "vflip_calibration_0.2.4.md"


def _raw():
    return json.loads(RAW.read_text(encoding="utf-8"))


def test_receipt_and_generator_exist():
    assert (ROOT / "scripts" / "calibrate_vflip.py").is_file()
    assert RAW.is_file() and REPORT.is_file()


def _generator():
    spec = importlib.util.spec_from_file_location(
        "calibrate_vflip", ROOT / "scripts" / "calibrate_vflip.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reachable_from_vflip():
    """The closure, recomputed here rather than taken from the generator."""
    tree = ast.parse(inspect.getsource(laminar))
    defs = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    reached, stack = set(), ["vflip"]
    while stack:
        name = stack.pop()
        if name in reached or name not in defs:
            continue
        reached.add(name)
        for call in ast.walk(defs[name]):
            if isinstance(call, ast.Call):
                callee = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
                if callee:
                    stack.append(callee)
    return reached


def test_receipt_was_generated_from_the_current_estimator():
    assert _raw()["estimator_sha256"] == _generator().estimator_sha256(), (
        "the estimator changed since the calibration receipt was generated; "
        "rerun `python scripts/calibrate_vflip.py`"
    )


def test_the_receipt_covers_every_helper_vflip_reaches():
    """The receipt has to certify the estimator, not one function of it.

    Hashing `vflip` alone was not a narrower receipt, it was a receipt that could be
    read as current while the estimator had changed: recentring `_unit_range` on its own
    mean moved the median signed bias and left this file passing 4 of 4. Widening the
    hash once would not keep it wide, so the reachable set is recomputed here and
    compared against the set the generator hashes.
    """
    covered = {name for name, _ in _generator().estimator_sources()}
    expected = _reachable_from_vflip()

    assert "vflip" in covered
    assert "_unit_range" in covered, (
        "`vflip` delegates its band normalization to `_unit_range`; a receipt that does "
        "not hash it cannot detect a defect reintroduced there"
    )
    assert covered == expected, (
        "the generator hashes a different set of functions than `vflip` reaches: "
        f"missing {sorted(expected - covered)}, extra {sorted(covered - expected)}"
    )
    for name, source in _generator().estimator_sources():
        assert source.strip(), f"{name} hashed as empty source"


def test_receipt_threshold_is_the_shipped_default():
    default = inspect.signature(vflip).parameters["min_support_score"].default
    assert _raw()["default_min_support_score"] == default


def test_report_is_rendered_from_the_raw_receipt():
    raw = _raw()
    report = REPORT.read_text(encoding="utf-8")
    assert raw["estimator_sha256"][:16] in report
    for name in ("white_noise", "ar_background", "amplitude_ramp", "parallel_bands"):
        tau = str(raw["operating"]["selected_threshold"])
        rate = raw["families"][name]["None"]["rate_curve"][tau]
        assert f"| `{name}` |" in report
        assert f"{rate:.3f}" in report
