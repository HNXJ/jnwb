"""Import-time behavior: public symbols resolve without eager heavy submodules."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_analyzer_exports_are_not_imported_with_package():
    code = """
import sys
before = set(sys.modules)
import jnwb
added = set(sys.modules) - before
assert "jnwb.analyzers" not in added
for name in ("TFRAnalyzer", "UnitAnalyzer", "PopulationAnalyzer"):
    assert name in jnwb.__all__
    cls = getattr(jnwb, name)
    assert cls.__name__ == name
assert "jnwb.analyzers" in sys.modules
print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert "OK" in result.stdout, result.stdout + result.stderr
