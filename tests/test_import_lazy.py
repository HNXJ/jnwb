"""Import-time behavior: public symbols resolve without eager heavy submodules."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_PROBE = """
import sys
before = set(sys.modules)
import jnwb
added = {{m for m in sys.modules if m not in before}}
loaded = [m for m in added if m.startswith({mod!r})]
assert not loaded, f"eager imports for {{mod!r}}: {{loaded}}"
value = getattr(jnwb, {symbol!r})
if {symbol!r} == "visual_qc":
    assert value.__name__.endswith("visual_qc")
else:
    assert getattr(value, "__name__", {symbol!r}) == {symbol!r}
print("OK")
"""


def _run(deferred: str, symbol: str) -> None:
    code = _PROBE.format(mod=deferred, symbol=symbol)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )
    assert "OK" in result.stdout, result.stdout + result.stderr


class TestDeferredImports:
    def test_statistics_not_eager(self):
        _run("jnwb.statistics", "StatisticalAnalysis")

    def test_ontology_not_eager(self):
        _run("jnwb.ontology", "Query")

    def test_metadata_not_eager(self):
        _run("jnwb.metadata", "filter_by_criteria")

    def test_decoding_not_eager(self):
        _run("jnwb.decoding", "nested_cv_linear_svm")

    def test_analyzers_not_eager(self):
        _run("jnwb.analyzers", "TFRAnalyzer")

    def test_visual_qc_submodule_not_eager(self):
        _run("jnwb.visual_qc", "visual_qc")

    def test_viz_not_eager(self):
        _run("jnwb.viz", "setup_vector_graphics")
