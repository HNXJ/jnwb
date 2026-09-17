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


class TestWhatImportingJnwbActuallyCosts:
    """05-48 reported `import jnwb` at about 2 s with "80% of it two eager submodules",
    and prescribed moving `rsa` into `EXPORT_MODULES`. The cost reproduces; the
    mechanism does not.

    Measured on a repaired tree against a `HEAD` worktree, five interleaved repetitions:
    deferring `rsa` changed the import time by nothing. The item's discriminator --
    `scipy.spatial` absent from `sys.modules` -- cannot be reached that way either,
    because `laminar`, `spectral`, `connectivity` and `spiking` all import `scipy.stats`
    at module scope and are all imported eagerly, and `scipy.stats` pulls
    `scipy.spatial` itself through `scipy.spatial._kdtree`.

    `rsa` looked responsible only because it is the *first* eager module to touch scipy,
    so `-X importtime` charges it the whole shared cost. Three measurements of the same
    package have now blamed three different modules: `artifacts/benchmarks/` blamed
    `jnwb.tfr` and `jnwb.addressing` at 0.1.5, the audit blamed `rsa` and `nwb_inspect`,
    and a run at 0.2.4 blames `rsa` and `nwb_io`. The order changed; the cost did not.

    What the cost actually is, timed inside fresh interpreters, median of five:
    numpy 0.12 s, the first scipy submodule +1.09 s, every further scipy submodule about
    0.00 s, pandas +0.31 s, pynwb +0.30 s -- 1.82 s for everything the eager surface
    needs, against 1.87 s for `import jnwb`. jnwb's own module bodies are the remaining
    0.05 s. Whichever scipy submodule is imported first pays: `scipy.signal` first costs
    1.22 s and makes `scipy.stats` free, while `scipy.stats` first costs 1.13 s and
    leaves `scipy.signal` at 0.09 s.

    So no single-module deferral can help. Removing scipy from the eager graph means
    deferring seven modules, pandas six more, pynwb three; that is most of the package
    and a different change from the one the item describes. These tests pin what is
    true now, so that a regression is caught and a deliberate improvement is noticed.
    """

    @staticmethod
    def _eager_top_level():
        import subprocess
        import sys

        code = (
            "import sys\n"
            "before = set(sys.modules)\n"
            "import jnwb\n"
            "std = set(sys.stdlib_module_names)\n"
            "added = {m.split('.')[0] for m in sys.modules if m not in before}\n"
            "print(' '.join(sorted(m for m in added if m not in std "
            "and not m.startswith('_'))))\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                text=True, cwd=REPO_ROOT, env=env, check=False)
        assert result.returncode == 0, result.stderr
        return set(result.stdout.split())

    def test_no_heavy_optional_dependency_is_imported_eagerly(self):
        """The deferrals that do pay for themselves. `sklearn`, `statsmodels`,
        `matplotlib` and `joblib` are reached only through `EXPORT_MODULES`, and nothing
        guarded that until now -- `TestOptionalExtras` checks only the packages declared
        as extras, which these are not."""
        eager = self._eager_top_level()

        heavy = {"sklearn", "scikit_learn", "statsmodels", "matplotlib", "joblib",
                 "numba", "seaborn", "plotly", "networkx", "sympy", "torch", "cupy",
                 "jax"}
        found = sorted(eager & heavy)

        assert not found, (
            f"importing jnwb now eagerly loads {found}; defer the module that pulls it "
            f"through jnwb/_lazy_exports.py")

    def test_the_eager_surface_is_the_one_the_docs_describe(self):
        """`docs/install.md` says which surface loads eagerly. If a future change defers
        scipy, pandas or pynwb, this fails -- update the doc, do not undo the work."""
        eager = self._eager_top_level()

        assert {"numpy", "scipy", "pandas", "pynwb"} <= eager, (
            f"the eager surface shrank to {sorted(eager)}; docs/install.md still "
            f"describes scipy, pandas and pynwb as eagerly loaded")

    def test_deferring_one_module_cannot_remove_a_shared_dependency(self):
        """The mechanism behind the item's failure, stated as an executable fact: more
        than one eagerly imported module imports scipy at module scope, so no single
        deferral removes it."""
        import re

        importers = []
        for path in sorted((REPO_ROOT / "jnwb").glob("*.py")):
            head = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^(from scipy|import scipy)", head, re.MULTILINE):
                importers.append(path.stem)

        init = (REPO_ROOT / "jnwb" / "__init__.py").read_text(encoding="utf-8")
        eager_importers = [m for m in importers
                           if re.search(rf"^from \.{m} import", init, re.MULTILINE)]

        assert len(eager_importers) > 1, (
            f"only {eager_importers} imports scipy eagerly; a single deferral would now "
            f"remove it, so 05-48's prescription may be worth revisiting")
