"""Regression gates for the failed 0.1.7 release recovery (CI blockers)."""
from __future__ import annotations

import inspect
import re
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_POS = inspect.Parameter.POSITIONAL_OR_KEYWORD


class TestGrangercausalitytestsCompatibility:
    def test_compat_omits_verbose_when_statsmodels_drops_it(self):
        from jnwb.jrsa import _grangercausalitytests_compat

        data = np.zeros((50, 2))
        captured: dict = {}

        def fake_gc(arr, **kwargs):
            captured.update(kwargs)
            mock_model = MagicMock(aic=0.0)
            return {1: (None, [None, mock_model])}

        sig_without_verbose = inspect.Signature(
            [
                inspect.Parameter("data", _POS),
                inspect.Parameter("maxlag", _POS),
            ]
        )
        with patch("statsmodels.tsa.stattools.grangercausalitytests", side_effect=fake_gc):
            with patch.object(inspect, "signature", return_value=sig_without_verbose):
                _grangercausalitytests_compat(data, maxlag=3)
        assert captured == {"maxlag": 3}

    def test_compat_passes_verbose_when_supported(self):
        from jnwb.jrsa import _grangercausalitytests_compat

        data = np.zeros((50, 2))
        captured: dict = {}

        def fake_gc(arr, **kwargs):
            captured.update(kwargs)
            mock_model = MagicMock(aic=0.0)
            return {1: (None, [None, mock_model])}

        sig_with_verbose = inspect.Signature(
            [
                inspect.Parameter("data", _POS),
                inspect.Parameter("maxlag", _POS),
                inspect.Parameter("verbose", _POS),
            ]
        )
        with patch("statsmodels.tsa.stattools.grangercausalitytests", side_effect=fake_gc):
            with patch.object(inspect, "signature", return_value=sig_with_verbose):
                _grangercausalitytests_compat(data, maxlag=2)
        assert captured == {"maxlag": 2, "verbose": False}

    def test_granger_ssr_ftest_works_when_statsmodels_drops_verbose(self):
        from statsmodels.tsa.stattools import grangercausalitytests

        if "verbose" in inspect.signature(grangercausalitytests).parameters:
            pytest.skip("statsmodels still exposes verbose; signature-mock tests cover compat")

        rng = np.random.default_rng(0)
        x = rng.normal(size=(80,))
        y = np.roll(x, 2) + 0.1 * rng.normal(size=(80,))
        res = __import__("jnwb").jrsa(x, y, metric="granger_ssr_ftest", stats=False)
        assert res.value > 0


class TestApiMdDeterminism:
    def test_generator_passes_on_current_interpreter(self):
        res = subprocess.run(
            [sys.executable, "scripts/generate_api_md.py", "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stdout + res.stderr

    def test_generator_passes_on_python_floor_when_available(self):
        if sys.version_info[:2] == (3, 12):
            pytest.skip("current interpreter is already the Python floor")
        py_launcher = shutil.which("py")
        if py_launcher is None:
            pytest.skip("no Python launcher available for floor cross-check")
        probe = subprocess.run(
            [py_launcher, "-3.12", "-c", "import numpy, jnwb"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            pytest.skip("Python 3.12 launcher is not a dependency-equipped environment")
        res = subprocess.run(
            [py_launcher, "-3.12", "scripts/generate_api_md.py", "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stdout + res.stderr

    def test_optional_annotation_renders_as_pep604_union(self):
        from scripts.generate_api_md import _format_annotation
        import typing

        rendered = _format_annotation(typing.Optional[typing.List[str]])
        assert rendered == "List[str] | None"

    def test_pandas_types_use_public_names(self):
        import pandas as pd
        from scripts.generate_api_md import _format_annotation

        assert _format_annotation(pd.DataFrame) == "pandas.DataFrame"
        assert _format_annotation(pd.Series) == "pandas.Series"


class TestReleaseGateCoverage:
    def test_release_gate_checks_api_md_generator(self):
        text = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
        assert "generate_api_md.py" in text
        assert "--check" in text

    def test_ci_matrix_installs_docs_dependencies(self):
        """Mechanically enforce invariant:
        environment runs full tests => environment contains dependencies of full tests.
        Since test_docs_nwb_workflow.py runs test_mkdocs_strict_build in the full test suite,
        the CI test matrix must install the [test,docs] extras, and [vis] for tests/test_vis.py.
        """
        import yaml

        wf_path = REPO_ROOT / ".github" / "workflows" / "workflow.yml"
        wf_data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        test_job = wf_data["jobs"]["test"]
        install_steps = [
            s for s in test_job["steps"] if s.get("name") == "Install dependencies"
        ]
        assert len(install_steps) == 1
        install_run = install_steps[0].get("run", "")
        # The extras are a set, so they are compared as one rather than as a substring whose
        # order and neighbours happen to match. `vis` because tests/test_vis.py skips without it.
        specs = re.findall(r'pip install "\.\[([A-Za-z0-9_,-]+)\]"', install_run)
        assert len(specs) == 1, install_run
        assert {"test", "docs", "vis"} <= set(specs[0].split(",")), specs[0]

    def test_the_documented_install_and_the_release_gate_require_the_ci_extras(self):
        """A contributor following the setup instructions can collect the suite.

        The instructions installed `[test,docs]`, and the suite's collection imports `jnwb.vis`,
        which raises without Plotly. The extras CI installs for the suite are the ones the
        documented install and the release gate's tooling check must both name.
        """
        import yaml

        if str(REPO_ROOT) not in sys.path:
            sys.path.append(str(REPO_ROOT))
        from scripts.release_gate import REQUIRED_EXTRAS

        wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "workflow.yml")
                            .read_text(encoding="utf-8"))
        step = next(s for s in wf["jobs"]["test"]["steps"] if s.get("name") == "Install dependencies")
        ci = set(re.findall(r'pip install "\.\[([A-Za-z0-9_,-]+)\]"', step["run"])[0].split(","))

        contributing = (REPO_ROOT / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")
        documented = re.findall(r'pip install -e "\.\[([A-Za-z0-9_,-]+)\]"', contributing)
        assert documented, "CONTRIBUTING.md no longer shows the development install"
        for spec in documented:
            assert ci <= set(spec.split(",")), (spec, sorted(ci))
        assert ci <= set(REQUIRED_EXTRAS), (REQUIRED_EXTRAS, sorted(ci))


class TestReleaseGateOrder:
    """The gate stopped at its first failure only after a twelve to thirty minute suite."""

    @staticmethod
    def _main_source() -> str:
        import ast

        source = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
        main = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        return ast.get_source_segment(source, main) or ""

    def test_the_state_file_is_checked_before_anything_else(self):
        main = self._main_source()
        assert "check_state_is_current()" in main
        first_check = min(main.index(name) for name in (
            "check_release_readiness(", "verify_declared_environment(", "published_versions(",
            "check_live_release_body(", "check_ci_conclusion("))
        assert main.index("check_state_is_current()") < first_check

    def test_the_suite_runs_after_the_smoke_script_and_the_tutorials(self):
        main = self._main_source()
        suite = main.index('"pytest"')
        for cheaper in ("harness_gate.py", '"build"', "INSTALLED_SMOKE", "=== STEP 8"):
            assert main.index(cheaper) < suite, f"{cheaper} runs after the suite"

    @staticmethod
    def _repository(root: Path) -> str:
        import os

        env = {k: v for k, v in os.environ.items()
               if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")}
        git = ["git", "-C", str(root), "-c", "user.name=jnwb-test",
               "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]
        subprocess.run(git + ["init", "-q"], check=True, capture_output=True, env=env)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "base"],
                       check=True, capture_output=True, env=env)
        return subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                              text=True, env=env).stdout.strip()

    @pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
    def test_a_stale_state_file_is_refused(self, tmp_path):
        if str(REPO_ROOT) not in sys.path:
            sys.path.append(str(REPO_ROOT))
        from scripts.release_gate import check_state_is_current

        head = self._repository(tmp_path)
        assert check_state_is_current(tmp_path) == [], "an absent state file passes"
        state = tmp_path / "artifacts" / "state.md"
        state.parent.mkdir()
        state.write_bytes(f"# State\n\n| HEAD | `{head}` |\n".encode("utf-8"))
        assert check_state_is_current(tmp_path) == []
        state.write_bytes(f"# State\n\n| HEAD | `{'0' * 40}` |\n".encode("utf-8"))
        violations = check_state_is_current(tmp_path)
        assert len(violations) == 1 and "generated at " + "0" * 40 in violations[0], violations
