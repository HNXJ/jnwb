"""Regression gates for the failed 0.1.7 release recovery (CI blockers)."""
from __future__ import annotations

import inspect
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
