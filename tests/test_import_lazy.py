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


class TestOptionalExtras:
    """0.2.4-10: the declared extras must be well formed and must aggregate.

    Installing every combination is not attempted: with five extras that is 32 clean
    environments per run, and `gpu` cannot resolve on a CI runner without CUDA. What is
    checked here is the failure that actually happens -- a requirement string that no
    resolver can parse, or an `all` that silently stops covering one of the others -- plus
    the property the base install depends on, which is that no extra is needed to import
    the package. Base-wheel install and `pip check` in a clean venv are covered by CI and
    by the release gate.
    """

    @staticmethod
    def _extras():
        import tomllib
        with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
            return tomllib.load(handle)["project"]["optional-dependencies"]

    def test_every_requirement_string_is_parseable(self):
        from packaging.requirements import Requirement
        for extra, requirements in self._extras().items():
            for raw in requirements:
                try:
                    Requirement(raw)
                except Exception as exc:  # pragma: no cover - the assertion is the report
                    raise AssertionError(f"{extra!r} has an unparseable requirement {raw!r}: {exc}")

    def test_all_aggregates_every_other_extra(self):
        from packaging.requirements import Requirement
        extras = self._extras()
        others = {name for name in extras if name != "all"}
        covered = set()
        for raw in extras["all"]:
            requirement = Requirement(raw)
            assert requirement.name == "jnwb", (
                f"'all' should aggregate jnwb's own extras, got {raw!r}"
            )
            covered |= set(requirement.extras)
        assert covered == others, (
            f"'all' covers {sorted(covered)} but the declared extras are {sorted(others)}"
        )

    def test_no_extra_is_required_to_import_jnwb(self):
        """The base wheel must import with nothing optional present."""
        import subprocess
        import sys

        from packaging.requirements import Requirement
        requirements = {
            Requirement(raw).name.lower()
            for extra, reqs in self._extras().items()
            if extra != "all"
            for raw in reqs
        }
        result = subprocess.run(
            [sys.executable, "-c", "import jnwb; print(jnwb.__version__)"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        # None of the optional distributions may appear as an eager import of the package.
        eager = subprocess.run(
            [sys.executable, "-c",
             "import sys, jnwb; print(' '.join(sorted(m.split('.')[0] for m in sys.modules)))"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        loaded = set(eager.stdout.split())
        for optional in ("torch", "cupy", "jax", "mcp", "mkdocs"):
            if optional in requirements:
                assert optional not in loaded, f"importing jnwb eagerly loaded {optional}"
