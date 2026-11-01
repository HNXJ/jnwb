"""Tests for jnwb.paths external-data root resolution and working-tree path resolution.

Tests explicit overrides, primary JNWB_* variables, precedence resolution, and path
composition.
"""
from __future__ import annotations

import sys
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

    def test_legacy_omission_env_var_is_ignored(self, monkeypatch):
        """The OMISSION_* names were removed in 0.2.13: only JNWB_* is read, and silently."""
        with pytest.raises(FileNotFoundError) as unset:
            paths.nwb_dir()
        monkeypatch.setenv("OMISSION_NWB_DIR", "Z:/legacy")
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            with pytest.raises(FileNotFoundError) as legacy:
                paths.nwb_dir()
        assert str(legacy.value) == str(unset.value)
        assert record == []

    def test_primary_analysis_dir_subtrees_follow_env_var(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_ANALYSIS_DIR, "Z:/synthetic_data")
        assert paths.tfr_dir() == Path("Z:/synthetic_data") / paths.TFR_SUBDIR
        assert paths.meta_dir() == Path("Z:/synthetic_data") / paths.META_SUBDIR
        assert paths.conndb_dir() == Path("Z:/synthetic_data") / paths.CONNDB_SUBDIR

    @pytest.mark.parametrize("fn, primary", [
        ("tfr_dir", "ENV_TFR_DIR"),
        ("meta_dir", "ENV_META_DIR"),
        ("conndb_dir", "ENV_CONNDB_DIR"),
    ])
    def test_subtree_override_wins_over_its_env_var(self, monkeypatch, fn, primary):
        monkeypatch.setenv(getattr(paths, primary), "Y:/from_env")
        assert getattr(paths, fn)(override="X:/custom") == Path("X:/custom")

    @pytest.mark.parametrize("fn, primary", [
        ("tfr_dir", "ENV_TFR_DIR"),
        ("meta_dir", "ENV_META_DIR"),
        ("conndb_dir", "ENV_CONNDB_DIR"),
    ])
    def test_subtree_env_var_wins_over_analysis_dir(self, monkeypatch, fn, primary):
        monkeypatch.setenv(paths.ENV_ANALYSIS_DIR, "Z:/synthetic_data")
        monkeypatch.setenv(getattr(paths, primary), "Y:/primary")
        assert getattr(paths, fn)() == Path("Y:/primary")


class TestOutputsAndArtifacts:
    def test_default_fallback_to_process_cwd(self):
        assert paths.PACKAGE_ROOT.exists()
        assert paths.outputs_dir() == Path.cwd() / "outputs"
        assert paths.artifacts_dir() == Path.cwd() / "artifacts"
        assert paths.layer_masks_path() == Path.cwd() / "outputs" / "publication_visual_review" / "area_layer_tfr" / "layer_masks.json"

    def test_layer_masks_path_takes_a_subdir_of_the_outputs_directory(self, monkeypatch, tmp_path):
        """The folder was hardcoded to one corpus's layout; that layout stays the default."""
        monkeypatch.setenv(paths.ENV_OUTPUTS_DIR, str(tmp_path))
        assert paths.layer_masks_path("masks") == tmp_path / "masks" / "layer_masks.json"
        assert paths.layer_masks_path(subdir=Path("a", "b")) == tmp_path / "a" / "b" / "layer_masks.json"
        assert (paths.layer_masks_path()
                == tmp_path / "publication_visual_review" / "area_layer_tfr" / "layer_masks.json")

    @pytest.mark.parametrize("subdir, named", [
        ("", "empty"),
        (".", "empty"),
        pytest.param("C:x", "absolute", marks=pytest.mark.skipif(
            sys.platform != "win32", reason="a drive-relative path roots only on Windows")),
        (str(Path.cwd()), "absolute"),
        ("/masks", "absolute"),
        ("../masks", "'..'"),
        (Path("a", "..", "..", "b"), "'..'"),
    ])
    def test_layer_masks_path_refuses_a_subdir_outside_the_outputs_directory(
            self, monkeypatch, tmp_path, subdir, named):
        monkeypatch.setenv(paths.ENV_OUTPUTS_DIR, str(tmp_path))
        with pytest.raises(ValueError, match=named) as info:
            paths.layer_masks_path(subdir)
        assert "subdir" in str(info.value)

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


class TestResolveNwbPath:
    """17-69: a session prefix names an existing file, or refuses naming every probe."""

    def test_default_probes_rec_then_plain(self, tmp_path):
        (tmp_path / "s1_rec.nwb").write_bytes(b"r")
        (tmp_path / "s1.nwb").write_bytes(b"p")
        assert paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path) == tmp_path / "s1_rec.nwb"

    def test_suffixes_are_probed_in_the_order_given(self, tmp_path):
        (tmp_path / "s1_rec.nwb").write_bytes(b"r")
        (tmp_path / "s1.nwb").write_bytes(b"p")
        found = paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path, suffixes=("", "_rec"))
        assert found == tmp_path / "s1.nwb"

    def test_a_custom_suffix_is_probed(self, tmp_path):
        (tmp_path / "s1_v2.nwb").write_bytes(b"v")
        found = paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path, suffixes=("_v2",))
        assert found == tmp_path / "s1_v2.nwb"

    def test_no_file_raises_naming_every_probe(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc:
            paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path)
        msg = str(exc.value)
        assert str(tmp_path / "s1_rec.nwb") in msg
        assert str(tmp_path / "s1.nwb") in msg

    def test_a_name_that_only_starts_with_a_probe_never_matches(self, tmp_path):
        (tmp_path / "s1_rec-old.nwb").write_bytes(b"x")
        (tmp_path / "s1.nwb.bak").write_bytes(b"x")
        assert (tmp_path / "s1_rec-old.nwb").exists() and (tmp_path / "s1.nwb.bak").exists()
        with pytest.raises(FileNotFoundError):
            paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path)

    def test_a_directory_named_as_a_probe_is_not_a_file(self, tmp_path):
        (tmp_path / "s1_rec.nwb").mkdir()
        (tmp_path / "s1.nwb").write_bytes(b"p")
        assert (tmp_path / "s1_rec.nwb").is_dir()
        assert paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path) == tmp_path / "s1.nwb"


class TestSha256Groups:
    """17-67: a receipt fingerprints the groups a reader used, not the whole file."""

    @staticmethod
    def _nwb(path, spikes=(1.0, 2.0), labels=("a", "bb"), acquisition=(0, 1, 2)):
        import h5py
        with h5py.File(path, "w") as f:
            f.create_dataset("units/spike_times", data=list(spikes))
            f.create_dataset("units/labels", data=list(labels), dtype=h5py.string_dtype())
            f.create_dataset("acquisition/ts", data=list(acquisition))
        return path

    def test_identical_content_gives_the_same_digest(self, tmp_path):
        a = self._nwb(tmp_path / "a.nwb")
        b = self._nwb(tmp_path / "b.nwb")
        assert paths.sha256_groups(a, ["units"]) == paths.sha256_groups(b, ["units"])

    def test_a_dataset_inside_a_named_group_changes_the_digest(self, tmp_path):
        a = self._nwb(tmp_path / "a.nwb")
        b = self._nwb(tmp_path / "b.nwb", spikes=(1.0, 2.5))
        assert paths.sha256_file(a) != paths.sha256_file(b)
        assert paths.sha256_groups(a, ["units"]) != paths.sha256_groups(b, ["units"])

    def test_a_string_inside_a_named_group_changes_the_digest(self, tmp_path):
        a = self._nwb(tmp_path / "a.nwb")
        b = self._nwb(tmp_path / "b.nwb", labels=("a", "bc"))
        assert paths.sha256_groups(a, ["units"]) != paths.sha256_groups(b, ["units"])

    def test_a_dataset_outside_the_named_groups_does_not_change_the_digest(self, tmp_path):
        a = self._nwb(tmp_path / "a.nwb")
        b = self._nwb(tmp_path / "b.nwb", acquisition=(0, 1, 9))
        assert paths.sha256_file(a) != paths.sha256_file(b)
        assert paths.sha256_groups(a, ["units"]) == paths.sha256_groups(b, ["units"])

    def test_group_order_does_not_change_the_digest(self, tmp_path):
        a = self._nwb(tmp_path / "a.nwb")
        assert (paths.sha256_groups(a, ["units", "acquisition"])
                == paths.sha256_groups(a, ["acquisition", "units"]))

    def test_a_missing_group_raises_naming_it(self, tmp_path):
        a = self._nwb(tmp_path / "a.nwb")
        with pytest.raises(KeyError, match="stimulus"):
            paths.sha256_groups(a, ["units", "stimulus"])

