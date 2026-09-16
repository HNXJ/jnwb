"""The vFLIP calibration receipt must describe the estimator that ships.

The 0.2.2 receipt was generated before the support score was density-normalized and the
crossover polarity rule changed, and no generator was kept, so its numbers described a
different estimator and could not be reproduced. The receipt now records a hash of the
``vflip`` source; changing the estimator without rerunning
``scripts/calibrate_vflip.py`` fails here.
"""

import inspect
import json
import pathlib

from jnwb.laminar import vflip

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "artifacts" / "benchmarks" / "vflip_calibration_0.2.4_raw.json"
REPORT = ROOT / "artifacts" / "benchmarks" / "vflip_calibration_0.2.4.md"


def _raw():
    return json.loads(RAW.read_text(encoding="utf-8"))


def test_receipt_and_generator_exist():
    assert (ROOT / "scripts" / "calibrate_vflip.py").is_file()
    assert RAW.is_file() and REPORT.is_file()


def test_receipt_was_generated_from_the_current_estimator():
    import importlib.util

    spec = importlib.util.spec_from_file_location("calibrate_vflip", ROOT / "scripts" / "calibrate_vflip.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _raw()["estimator_sha256"] == module.estimator_sha256(), (
        "vflip changed since the calibration receipt was generated; "
        "rerun `python scripts/calibrate_vflip.py`"
    )


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
