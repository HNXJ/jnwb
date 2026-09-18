"""The xFLIP calibration receipt must describe the estimator that ships.

`xflip_calibration_0.2.3.md` was produced under 0.2.3 with no generator, so it could not be
regenerated, and two changes had already invalidated it: 0.2.4 made `xflip` reject a
zero-variance channel rather than report its correlation as 0, and 05-07 found the
smooth-gradient drop gate was skipped on the `contiguous=False` path, so its null rates were
conditional on a setting it did not name. It is replaced by `xflip_calibration_0.2.5.md`
and a generator, and the receipt records a hash of the estimator; changing the estimator
without rerunning `scripts/calibrate_xflip.py` fails here.

The hash covers every module-level function in `jnwb.laminar` that `xflip` can reach, not
`xflip` alone. Hashing one function of an estimator is not a narrower receipt, it is one
that can be read as current while the estimator has changed -- `tests/test_vflip_calibration_receipt.py`
records where that happened.
"""

import ast
import importlib.util
import inspect
import json
import pathlib

from jnwb import laminar
from jnwb.laminar import xflip

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "artifacts" / "benchmarks" / "xflip_calibration_0.2.5_raw.json"
REPORT = ROOT / "artifacts" / "benchmarks" / "xflip_calibration_0.2.5.md"


def _raw():
    return json.loads(RAW.read_text(encoding="utf-8"))


def _generator():
    spec = importlib.util.spec_from_file_location(
        "calibrate_xflip", ROOT / "scripts" / "calibrate_xflip.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reachable_from_xflip():
    """The closure, recomputed here rather than taken from the generator.

    An oracle that imports the thing it checks certifies nothing, so this walk is written
    out a second time on purpose.
    """
    tree = ast.parse(inspect.getsource(laminar))
    defs = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    reached, stack = set(), ["xflip"]
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


def test_receipt_and_generator_exist():
    assert (ROOT / "scripts" / "calibrate_xflip.py").is_file()
    assert RAW.is_file() and REPORT.is_file()


def test_the_receipt_without_a_generator_is_gone():
    """The defect 05-60 repaired was a receipt nobody could reproduce, not its contents."""
    for stale in ("xflip_calibration_0.2.3.md", "xflip_calibration_raw.json"):
        assert not (ROOT / "artifacts" / "benchmarks" / stale).exists(), (
            f"{stale} is a calibration receipt with no generator; it was replaced by "
            "xflip_calibration_0.2.5.md and scripts/calibrate_xflip.py"
        )


def test_receipt_was_generated_from_the_current_estimator():
    assert _raw()["estimator_sha256"] == _generator().estimator_sha256(), (
        "the estimator changed since the calibration receipt was generated; "
        "rerun `python scripts/calibrate_xflip.py`"
    )


def test_the_receipt_covers_every_helper_xflip_reaches():
    covered = {name for name, _ in _generator().estimator_sources()}
    expected = _reachable_from_xflip()

    assert "xflip" in covered
    assert covered == expected, (
        "the generator hashes a different set of functions than `xflip` reaches: "
        f"missing {sorted(expected - covered)}, extra {sorted(covered - expected)}"
    )
    for name, source in _generator().estimator_sources():
        assert source.strip(), f"{name} hashed as empty source"


def test_the_operating_point_is_the_shipped_default_where_it_claims_to_be():
    """`alpha` is recorded from the signature, so a changed default cannot go unnoticed."""
    assert _raw()["alpha"] == inspect.signature(xflip).parameters["alpha"].default


def test_report_is_rendered_from_the_raw_receipt():
    raw = _raw()
    report = REPORT.read_text(encoding="utf-8")
    assert raw["estimator_sha256"][:16] in report
    for name, cell in raw["nulls"].items():
        assert f"| `{name}` |" in report
        assert f"{cell['false_positive_rate']:.3f}" in report


def test_the_report_reads_the_gradient_row_rather_than_only_reporting_it():
    """A 0.000 acceptance rate on the gradient null invites the opposite conclusion.

    Every gradient is maximally significant under the omnibus permutation test -- median,
    min and max p all sit at the 1/(surrogates+1) floor -- and the rate is produced entirely
    by the local boundary-drop gate. 05-07 found that gate skipped on the unrestricted path,
    where the same nulls were accepted 15/15. A receipt that prints 0.000 without that
    sentence reads as though the permutation test rejects gradients.
    """
    raw = _raw()
    grad = raw["nulls"]["smooth_spatial_gradient"]
    floor = 1.0 / (raw["n_surrogates"] + 1)

    assert grad["median_p"] == grad["min_p"] == grad["max_p"]
    assert abs(grad["median_p"] - floor) < 1e-12, (
        "the gradient null is no longer pinned at the permutation floor, so the explanation "
        "in the report no longer describes the measurement; rerun the generator"
    )
    assert "boundary-drop gate" in REPORT.read_text(encoding="utf-8")
