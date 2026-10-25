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

    def test_compat_takes_the_no_verbose_branch_on_real_statsmodels(self):
        """Runs the branch that omits verbose on any statsmodels, not only one that dropped it."""
        import statsmodels.tsa.stattools as stattools

        from jnwb.jrsa import _grangercausalitytests_compat

        real = stattools.grangercausalitytests
        seen: dict = {}

        def without_verbose(data, maxlag):
            seen.update(maxlag=maxlag)
            return real(data, maxlag=maxlag)

        data = np.random.default_rng(0).normal(size=(80, 2))
        with patch.object(stattools, "grangercausalitytests", new=without_verbose):
            res = _grangercausalitytests_compat(data, maxlag=2)
        assert seen == {"maxlag": 2}
        assert np.isfinite(res[2][1][1].aic)


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
        for cheaper in ("harness_gate.py", '"build"', "smoke_installed.py", "=== STEP 8"):
            assert main.index(cheaper) < suite, f"{cheaper} runs after the suite"

    def test_step_7_runs_the_installed_smoke_script_as_ci_does(self):
        """Hamm 2026-10-13: one installed smoke. STEP 7 runs scripts/smoke_installed.py with the
        arguments CI passes, from the staging directory, with PYTHONPATH stripped."""
        main = self._main_source()
        step_7 = main[main.index("=== STEP 7"):main.index("=== STEP 8")]
        assert "smoke_installed.py" in step_7, "STEP 7 does not run scripts/smoke_installed.py"
        assert "--expected-version" in step_7 and "--not-under" in step_7, step_7
        assert 'k != "PYTHONPATH"' in step_7 and "env=smoke_env" in step_7, step_7
        assert "INSTALLED_SMOKE" not in main, "STEP 7 still builds its own smoke script"

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


class TestCiRunSelection:
    """STEP 0e took the newest run for the commit, so a pull-request run still executing hid the
    push run for the same commit, which had concluded green."""

    SHA = "c" * 40
    JOBS = [{"name": "Test", "status": "completed", "conclusion": "success"}]

    @staticmethod
    def _run(run_id, status, conclusion=""):
        return {"databaseId": run_id, "headSha": TestCiRunSelection.SHA, "status": status,
                "conclusion": conclusion, "workflowName": "CI", "headBranch": "main"}

    @staticmethod
    def _gh(runs, jobs_payload):
        import json

        def run(args, **kwargs):
            stdout = json.dumps(runs) if args[:3] == ["gh", "run", "list"] else jobs_payload
            return subprocess.CompletedProcess(args, 0, stdout, "")
        return run

    def test_a_concluded_green_run_suffices_beside_one_still_executing(self):
        import json

        from scripts.release_gate import CI_VERIFIED, check_ci_conclusion, select_run_for_commit

        runs = [self._run(20, "in_progress"), self._run(10, "completed", "success")]
        run, reason = select_run_for_commit(self.SHA, json.dumps(runs))
        assert reason is None and run["databaseId"] == 10, (run, reason)
        green = json.dumps({"headSha": self.SHA, "conclusion": "success", "jobs": self.JOBS})
        outcome = check_ci_conclusion(self.SHA, required=["Test"],
                                      runner=self._gh(runs, green))
        assert outcome.status == CI_VERIFIED, outcome

    def test_a_newer_concluded_failure_beside_an_older_green_run_still_fails(self):
        import json

        from scripts.release_gate import CI_FAILED, check_ci_conclusion

        runs = [self._run(30, "completed", "failure"), self._run(10, "completed", "success")]
        failed = json.dumps({"headSha": self.SHA, "conclusion": "failure", "jobs": [
            {"name": "Test", "status": "completed", "conclusion": "failure"}]})
        outcome = check_ci_conclusion(self.SHA, required=["Test"],
                                      runner=self._gh(runs, failed))
        assert outcome.status == CI_FAILED, outcome

    def test_a_commit_with_no_concluded_run_is_held_by_its_newest(self):
        import json

        from scripts.release_gate import CI_UNRESOLVED, check_ci_conclusion

        runs = [self._run(20, "in_progress"), self._run(10, "queued")]
        outcome = check_ci_conclusion(self.SHA, required=["Test"],
                                      runner=self._gh(runs, json.dumps({})))
        assert outcome.status == CI_UNRESOLVED and "in_progress" in outcome.detail, outcome


class TestTheInstalledSmokeScriptRunsInTheSuite:
    """P-352: the installed-package smoke script ran only at STEP 7, so an exact key set that went
    stale in it passed a whole cycle of green suites. The suite runs the same script against the
    checkout. It must get through its checks before the installed-location check and refuse the
    checkout there, so a stale line fails the suite rather than the release."""

    SMOKE = REPO_ROOT / "scripts" / "smoke_installed.py"

    @classmethod
    def _run(cls, tmp_path: Path, script: Path, *args: str):
        import os

        shadow = tmp_path / "shadow"
        shadow.mkdir()
        # `omission` absent, as the script requires of the environment it is written for.
        (shadow / "omission.py").write_text(
            'raise ModuleNotFoundError("absent in this test")\n', encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(shadow), str(REPO_ROOT)]))
        return subprocess.run([sys.executable, str(script), *args], cwd=tmp_path, env=env,
                              capture_output=True, text=True, timeout=300)

    @staticmethod
    def _checkout_args() -> list:
        """What the suite passes: the source version, and the checkout as the place the package
        must not be imported from."""
        from scripts.release_gate import jnwb_source_version

        return ["--expected-version", jnwb_source_version(), "--not-under", str(REPO_ROOT)]

    def test_the_script_runs_its_checks_up_to_the_location_check(self, tmp_path):
        result = self._run(tmp_path, self.SMOKE, *self._checkout_args())
        assert "PASS: omission is strictly absent" in result.stdout, result.stderr
        assert "PASS: workflow checks completed" in result.stdout, result.stderr
        assert result.returncode != 0, result.stdout
        assert "FAIL: jnwb was imported from" in result.stderr, result.stderr
        assert f"inside {REPO_ROOT}" in result.stderr, result.stderr

    def test_a_stale_line_fails_before_the_location_check(self, tmp_path):
        """A mutant whose workflow check names a constant that no longer exists: the run must fail
        on that line, before the location check that would refuse the checkout."""
        source = self.SMOKE.read_text(encoding="utf-8")
        anchor = "assert spikes.size > 0 and lfp.size > 0 and fs_hz == receipt.fs_hz"
        assert source.count(anchor) == 1, "the mutant's anchor did not apply exactly once"
        mutant = tmp_path / "smoke_mutant.py"
        mutant.write_text(source.replace(anchor, anchor.replace("receipt.fs_hz", "FS_HZ_STALE")),
                          encoding="utf-8")
        result = self._run(tmp_path, mutant, *self._checkout_args())
        assert result.returncode != 0, result.stdout
        assert "NameError" in result.stderr, result.stderr
        assert "PASS: workflow checks completed" not in result.stdout, result.stdout
        assert "FAIL: jnwb was imported from" not in result.stderr, result.stderr


class TestTheBannerNamesEachSkip:
    """A release run with a skipped check must not print the VERIFIED banner unqualified."""

    def test_a_run_with_no_skip_keeps_the_verified_banner(self):
        from scripts.release_gate import verified_banner

        assert verified_banner([]) == "=== RELEASE GATE VERIFIED: DISTRIBUTABLE PACKAGE READY ==="

    def test_a_run_with_skips_counts_them_and_names_each(self):
        from scripts.release_gate import verified_banner

        banner = verified_banner(["release body (STEP 0d)", "CI conclusion (STEP 0e)"])
        assert "2 CHECK(S) SKIPPED" in banner, banner
        assert "release body (STEP 0d)" in banner and "CI conclusion (STEP 0e)" in banner, banner
        assert "VERIFIED: DISTRIBUTABLE" not in banner, banner

    def test_an_unreachable_index_skip_is_recorded_once(self, monkeypatch):
        import scripts.release_gate as release_gate

        monkeypatch.setattr(release_gate, "SKIPPED_CHECKS", [])
        monkeypatch.setenv(release_gate.SKIP_INDEX_ENV, "1")
        assert release_gate.check_version_is_not_already_published("0.2.14", None) == []
        assert release_gate.check_version_is_not_already_published("0.2.14", None) == []
        assert len(release_gate.SKIPPED_CHECKS) == 1, release_gate.SKIPPED_CHECKS
