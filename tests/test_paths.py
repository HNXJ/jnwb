"""Tests for jnwb.paths' external-data root resolution.

DEFAULT_NWB_DIR / DEFAULT_ANALYSIS_DIR are intentionally None (no machine- or project-generic
default data location -- see jnwb/paths.py's module docstring for why a prior D:/nwb/omission
literal default was removed). nwb_dir()/analysis_dir() must raise a clear, actionable
FileNotFoundError naming the relevant env var when neither an override nor the env var is set.
"""
from __future__ import annotations

import pytest

import jnwb.paths as paths


@pytest.fixture(autouse=True)
def _clear_path_env_vars(monkeypatch):
    for var in (
        paths.ENV_NWB_DIR, paths.ENV_TFR_DIR, paths.ENV_META_DIR,
        paths.ENV_CONNDB_DIR, paths.ENV_ANALYSIS_DIR,
    ):
        monkeypatch.delenv(var, raising=False)


class TestNoDefaultDataLocation:
    def test_defaults_are_none(self):
        assert paths.DEFAULT_NWB_DIR is None
        assert paths.DEFAULT_ANALYSIS_DIR is None

    def test_nwb_dir_raises_when_unconfigured(self):
        with pytest.raises(FileNotFoundError, match=paths.ENV_NWB_DIR):
            paths.nwb_dir()

    def test_analysis_dir_raises_when_unconfigured(self):
        with pytest.raises(FileNotFoundError, match=paths.ENV_ANALYSIS_DIR):
            paths.analysis_dir()

    def test_tfr_meta_conndb_dir_raise_when_unconfigured(self):
        for fn in (paths.tfr_dir, paths.meta_dir, paths.conndb_dir):
            with pytest.raises(FileNotFoundError, match=paths.ENV_ANALYSIS_DIR):
                fn()


class TestOverrideAndEnvVarPrecedence:
    def test_explicit_override_wins_even_with_no_env_var(self):
        assert paths.nwb_dir(override="X:/custom") == paths.Path("X:/custom")

    def test_env_var_used_when_no_override(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_NWB_DIR, "Y:/from_env")
        assert paths.nwb_dir() == paths.Path("Y:/from_env")

    def test_override_wins_over_env_var(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_NWB_DIR, "Y:/from_env")
        assert paths.nwb_dir(override="X:/custom") == paths.Path("X:/custom")

    def test_analysis_dir_subtrees_follow_env_var(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_ANALYSIS_DIR, "Z:/data")
        assert paths.tfr_dir() == paths.Path("Z:/data") / paths.TFR_SUBDIR
        assert paths.meta_dir() == paths.Path("Z:/data") / paths.META_SUBDIR
        assert paths.conndb_dir() == paths.Path("Z:/data") / paths.CONNDB_SUBDIR


class TestRepoInternalRootsAlwaysResolve:
    def test_repo_root_and_outputs_never_raise(self):
        assert paths.REPO_ROOT.exists()
        paths.outputs_dir()
        paths.artifacts_dir()
        paths.layer_masks_path()


class TestDescribeNeverRaises:
    def test_describe_reports_unconfigured_without_raising(self):
        result = paths.describe()
        assert result["REPO_ROOT"]["exists"] is True
        nwb_key = f"nwb_dir (${paths.ENV_NWB_DIR})"
        assert result[nwb_key]["configured"] is False
        assert result[nwb_key]["path"] is None

    def test_describe_reports_configured_when_env_var_set(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_NWB_DIR, "Y:/from_env")
        result = paths.describe()
        nwb_key = f"nwb_dir (${paths.ENV_NWB_DIR})"
        assert result[nwb_key]["configured"] is True
        assert result[nwb_key]["path"] == str(paths.Path("Y:/from_env"))
