"""Tests for jnwb.paths external-data root resolution and working-tree path resolution.

Tests explicit overrides, primary JNWB_* variables, deprecated legacy OMISSION_* variables
with warnings, precedence resolution, and path composition.
"""
from __future__ import annotations

import warnings
import pytest
from pathlib import Path

import jnwb.paths as paths


@pytest.fixture(autouse=True)
def _clear_path_env_vars(monkeypatch):
    for var in (
        paths.ENV_NWB_DIR, paths.ENV_TFR_DIR, paths.ENV_META_DIR,
        paths.ENV_CONNDB_DIR, paths.ENV_ANALYSIS_DIR,
        paths.ENV_OUTPUTS_DIR, paths.ENV_ARTIFACTS_DIR,
        paths.LEGACY_ENV_NWB_DIR, paths.LEGACY_ENV_TFR_DIR, paths.LEGACY_ENV_META_DIR,
        paths.LEGACY_ENV_CONNDB_DIR, paths.LEGACY_ENV_ANALYSIS_DIR,
        paths.LEGACY_ENV_OUTPUTS_DIR, paths.LEGACY_ENV_ARTIFACTS_DIR,
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
        with pytest.raises(FileNotFoundError):
            paths.tfr_dir()
        with pytest.raises(FileNotFoundError):
            paths.meta_dir()
        with pytest.raises(FileNotFoundError):
            paths.conndb_dir()


class TestOverrideAndEnvVarPrecedence:
    def test_explicit_override_wins_even_with_no_env_var(self):
        assert paths.nwb_dir(override="X:/custom") == Path("X:/custom")

    def test_primary_env_var_used_when_no_override(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_NWB_DIR, "Y:/from_env")
        assert paths.nwb_dir() == Path("Y:/from_env")

    def test_override_wins_over_primary_env_var(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_NWB_DIR, "Y:/from_env")
        assert paths.nwb_dir(override="X:/custom") == Path("X:/custom")

    def test_primary_env_var_wins_over_legacy_env_var(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_NWB_DIR, "Y:/primary")
        monkeypatch.setenv(paths.LEGACY_ENV_NWB_DIR, "Z:/legacy")
        # Should use primary without warning
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            assert paths.nwb_dir() == Path("Y:/primary")
            assert not any(issubclass(w.category, DeprecationWarning) for w in record)

    def test_legacy_env_var_fallback_emits_deprecation_warning(self, monkeypatch):
        monkeypatch.setenv(paths.LEGACY_ENV_NWB_DIR, "Z:/legacy")
        with pytest.deprecated_call(match="OMISSION_NWB_DIR is deprecated"):
            assert paths.nwb_dir() == Path("Z:/legacy")

    def test_legacy_analysis_dir_subtrees_fallback_with_warning(self, monkeypatch):
        monkeypatch.setenv(paths.LEGACY_ENV_ANALYSIS_DIR, "Z:/legacy_data")
        with pytest.deprecated_call(match="OMISSION_ANALYSIS_DIR is deprecated"):
            assert paths.tfr_dir() == Path("Z:/legacy_data") / paths.TFR_SUBDIR
            assert paths.meta_dir() == Path("Z:/legacy_data") / paths.META_SUBDIR
            assert paths.conndb_dir() == Path("Z:/legacy_data") / paths.CONNDB_SUBDIR

    def test_primary_analysis_dir_subtrees_follow_env_var(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_ANALYSIS_DIR, "Z:/data")
        assert paths.tfr_dir() == Path("Z:/data") / paths.TFR_SUBDIR
        assert paths.meta_dir() == Path("Z:/data") / paths.META_SUBDIR
        assert paths.conndb_dir() == Path("Z:/data") / paths.CONNDB_SUBDIR


class TestOutputsAndArtifacts:
    def test_default_fallback_to_process_cwd(self):
        assert paths.PACKAGE_ROOT.exists()
        assert paths.outputs_dir() == Path.cwd() / "outputs"
        assert paths.artifacts_dir() == Path.cwd() / "artifacts"
        assert paths.layer_masks_path() == Path.cwd() / "outputs" / "publication_visual_review" / "area_layer_tfr" / "layer_masks.json"

    def test_outputs_and_artifacts_independent_of_package_install_location(self, monkeypatch, tmp_path):
        """Simulate jnwb installed under site-packages and verify outputs/artifacts resolve to consumer cwd."""
        simulated_site_packages = tmp_path / "site-packages" / "jnwb"
        simulated_site_packages.mkdir(parents=True)
        monkeypatch.setattr(paths, "PACKAGE_ROOT", simulated_site_packages.parent)
        monkeypatch.setattr(paths, "__file__", str(simulated_site_packages / "paths.py"))

        consumer_project_dir = tmp_path / "consumer_project"
        consumer_project_dir.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: consumer_project_dir)

        out = paths.outputs_dir("experiment_a", "summary.csv")
        art = paths.artifacts_dir("evidence.json")

        assert out == consumer_project_dir / "outputs" / "experiment_a" / "summary.csv"
        assert art == consumer_project_dir / "artifacts" / "evidence.json"
        assert "site-packages" not in str(out)
        assert "site-packages" not in str(art)

    def test_outputs_dir_override_parameter(self):
        assert paths.outputs_dir("subfolder", "table.csv", override="C:/custom_outputs") == Path("C:/custom_outputs/subfolder/table.csv")

    def test_artifacts_dir_override_parameter(self):
        assert paths.artifacts_dir("evidence.json", override="C:/custom_artifacts") == Path("C:/custom_artifacts/evidence.json")

    def test_outputs_and_artifacts_primary_env_vars(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_OUTPUTS_DIR, "D:/my_project/outputs")
        monkeypatch.setenv(paths.ENV_ARTIFACTS_DIR, "D:/my_project/artifacts")
        assert paths.outputs_dir("run1") == Path("D:/my_project/outputs/run1")
        assert paths.artifacts_dir("log.txt") == Path("D:/my_project/artifacts/log.txt")
        # Explicit override still takes precedence over env var
        assert paths.outputs_dir("run1", override="E:/override") == Path("E:/override/run1")
        assert paths.artifacts_dir("log.txt", override="E:/override") == Path("E:/override/log.txt")

    def test_outputs_and_artifacts_legacy_env_vars_fallback_with_warning(self, monkeypatch):
        monkeypatch.setenv(paths.LEGACY_ENV_OUTPUTS_DIR, "D:/legacy_project/outputs")
        monkeypatch.setenv(paths.LEGACY_ENV_ARTIFACTS_DIR, "D:/legacy_project/artifacts")
        with pytest.deprecated_call(match="OMISSION_OUTPUTS_DIR is deprecated"):
            assert paths.outputs_dir("run1") == Path("D:/legacy_project/outputs/run1")
        with pytest.deprecated_call(match="OMISSION_ARTIFACTS_DIR is deprecated"):
            assert paths.artifacts_dir("log.txt") == Path("D:/legacy_project/artifacts/log.txt")

    def test_outputs_and_artifacts_primary_wins_over_legacy(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_OUTPUTS_DIR, "D:/primary/outputs")
        monkeypatch.setenv(paths.LEGACY_ENV_OUTPUTS_DIR, "D:/legacy/outputs")
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            assert paths.outputs_dir("run1") == Path("D:/primary/outputs/run1")
            assert not any(issubclass(w.category, DeprecationWarning) for w in record)


class TestDescribeNeverRaises:
    def test_describe_reports_unconfigured_without_raising(self):
        result = paths.describe()
        assert result["PACKAGE_ROOT"]["exists"] is True
        nwb_key = f"nwb_dir (${paths.ENV_NWB_DIR})"
        assert result[nwb_key]["configured"] is False
        assert result[nwb_key]["path"] is None

    def test_describe_reports_configured_when_env_var_set(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_NWB_DIR, "Y:/from_env")
        result = paths.describe()
        nwb_key = f"nwb_dir (${paths.ENV_NWB_DIR})"
        assert result[nwb_key]["configured"] is True
        assert result[nwb_key]["path"] == str(Path("Y:/from_env"))


class TestPackageRootRename:
    """JNWB-007: REPO_ROOT was jnwb's own checkout under a name consumers read as theirs.

    It resolved from paths.py's own location, so in a consuming project it pointed at
    the jnwb checkout. The path was well-formed and simply named the wrong tree.
    In 0.2.0, the deprecated REPO_ROOT alias is removed completely in favor of PACKAGE_ROOT.
    """

    def test_package_root_is_the_jnwb_package_parent(self):
        assert paths.PACKAGE_ROOT == Path(paths.__file__).resolve().parent.parent
        assert (paths.PACKAGE_ROOT / "jnwb" / "paths.py").exists()

    def test_repo_root_is_absent_and_raises_attribute_error(self):
        """0.2.0 removal commitment: paths.REPO_ROOT must not exist."""
        assert not hasattr(paths, "REPO_ROOT")
        with pytest.raises(AttributeError):
            _ = paths.REPO_ROOT

    def test_package_root_does_not_warn(self):
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            _ = paths.PACKAGE_ROOT
        assert [w for w in record if issubclass(w.category, DeprecationWarning)] == []

    def test_public_surface_advertises_package_root_only(self):
        assert "PACKAGE_ROOT" in paths.__all__
        assert "REPO_ROOT" not in paths.__all__

    def test_unknown_attribute_still_raises_attribute_error(self):
        """The module must raise AttributeError for non-existent attributes."""
        with pytest.raises(AttributeError):
            _ = paths.definitely_not_a_real_attribute

    def test_describe_reports_package_root_and_omits_repo_root(self):
        """describe() reports PACKAGE_ROOT and no longer contains the deprecated REPO_ROOT key."""
        result = paths.describe()
        assert "PACKAGE_ROOT" in result
        assert result["PACKAGE_ROOT"]["path"] == str(paths.PACKAGE_ROOT)
        assert "REPO_ROOT" not in result

