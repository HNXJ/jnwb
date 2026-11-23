"""Three public names are deprecated in 0.2.17 and removed no earlier than 0.2.18.

Each must warn ``DeprecationWarning`` on use, name its replacement or say there is none, and
return what it returned before. The values below are copied from the definitions as they stood
before the deprecation, so an edit that changed a value while adding the warning fails here.

The over-warning half matters as much: ``repair_band_artifacts(band_ranges=None)`` reads the same
band table, and ``read_nwb`` calls ``nwb_read_io``; neither may warn a caller who never named a
deprecated thing.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import jnwb.artifact_repair as artifact_repair
from jnwb.analyzers import TFRAnalyzer
from jnwb.nwb_io import nwb_read_io, read_nwb

OLD_LEGACY_VIZ_BANDS = {
    'delta':      (1.0,   4.0),
    'theta':      (4.0,   8.0),
    'alpha':      (8.0,  15.0),
    'beta':       (15.0,  30.0),
    'low_gamma':  (30.0,  60.0),
    'high_gamma': (60.0, 120.0),
    'broadband':  (1.0,  150.0),
}

OLD_DEFAULT_BANDS = {"Theta(4-8Hz)": (4, 8), "Alpha(8-14Hz)": (8, 14), "Beta(14-30Hz)": (14, 30),
                     "Gamma(Low,30-50Hz)": (30, 50), "Gamma(High,50-80Hz)": (50, 80)}

REMOVAL = r"removed in 0\.2\.18"


def _only_deprecations(record):
    return [w for w in record if issubclass(w.category, DeprecationWarning)]


@pytest.fixture(scope="module")
def nwb_path(tmp_path_factory):
    from jnwb.testing.nwb_fixtures import write_synth_nwb

    path = tmp_path_factory.mktemp("deprecations") / "base.nwb"
    write_synth_nwb(str(path))
    return path


class TestLegacyVizBands:
    def test_class_access_warns_and_returns_the_old_table(self):
        with pytest.warns(DeprecationWarning, match="LEGACY_VIZ_BANDS") as record:
            value = TFRAnalyzer.LEGACY_VIZ_BANDS
        assert value == OLD_LEGACY_VIZ_BANDS
        message = str(_only_deprecations(record)[0].message)
        assert "no replacement" in message
        assert "0.2.18" in message
        assert _only_deprecations(record)[0].filename == __file__

    def test_instance_access_warns_and_returns_the_old_table(self):
        with pytest.warns(DeprecationWarning, match="LEGACY_VIZ_BANDS"):
            value = TFRAnalyzer().LEGACY_VIZ_BANDS
        assert value == OLD_LEGACY_VIZ_BANDS

    def test_the_returned_table_still_drives_extract_band(self):
        rng = np.random.default_rng(0)
        freqs = np.arange(1.0, 151.0)
        tfr = rng.random((3, freqs.size, 5))
        with pytest.warns(DeprecationWarning, match="LEGACY_VIZ_BANDS"):
            table = TFRAnalyzer.LEGACY_VIZ_BANDS
        got = TFRAnalyzer.extract_band(tfr, "alpha", freqs=freqs, band_defs=table)
        explicit = TFRAnalyzer.extract_band(tfr, "alpha", freqs=freqs,
                                            band_defs=OLD_LEGACY_VIZ_BANDS)
        np.testing.assert_array_equal(got, explicit)

    def test_the_canonical_table_does_not_warn(self):
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            TFRAnalyzer.BANDS
        assert not _only_deprecations(record)


class TestDefaultBands:
    def test_module_attribute_warns_and_returns_the_old_table(self):
        with pytest.warns(DeprecationWarning, match="DEFAULT_BANDS") as record:
            value = artifact_repair.DEFAULT_BANDS
        assert value == OLD_DEFAULT_BANDS
        message = str(_only_deprecations(record)[0].message)
        assert "no replacement" in message
        assert "0.2.18" in message
        assert _only_deprecations(record)[0].filename == __file__

    def test_from_import_warns(self):
        with pytest.warns(DeprecationWarning, match=REMOVAL):
            from jnwb.artifact_repair import DEFAULT_BANDS
        assert DEFAULT_BANDS == OLD_DEFAULT_BANDS

    def test_the_default_band_ranges_are_the_old_table_and_do_not_warn(self):
        rng = np.random.default_rng(1)
        freqs = np.arange(3.0, 101.0, 2.0)
        power = 5.0 + rng.normal(0.0, 0.3, size=(20, 2, freqs.size, 30))
        power[3, :, (freqs >= 8) & (freqs < 14), 15] += 30.0
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            by_default, frac_default = artifact_repair.repair_band_artifacts(power, freqs)
        assert not _only_deprecations(record)
        explicit, frac_explicit = artifact_repair.repair_band_artifacts(
            power, freqs, band_ranges=OLD_DEFAULT_BANDS)
        assert list(frac_default) == list(OLD_DEFAULT_BANDS)
        assert frac_default == frac_explicit
        assert frac_default["Alpha(8-14Hz)"] > 0, "fixture must flag the Alpha spike"
        np.testing.assert_array_equal(by_default, explicit)

    def test_an_unknown_attribute_still_raises(self):
        with pytest.raises(AttributeError, match="NO_SUCH_NAME"):
            artifact_repair.NO_SUCH_NAME


class TestNwbReadIoMode:
    def test_mode_r_warns_and_reads_the_same_file(self, nwb_path):
        with nwb_read_io(str(nwb_path)) as io:
            expected = io.read().identifier
        with pytest.warns(DeprecationWarning, match="mode") as record:
            with nwb_read_io(str(nwb_path), mode="r") as io:
                got = io.read().identifier
        assert got == expected
        message = str(_only_deprecations(record)[0].message)
        assert "no replacement" in message
        assert "0.2.18" in message
        assert _only_deprecations(record)[0].filename == __file__

    def test_positional_mode_r_warns(self, nwb_path):
        with pytest.warns(DeprecationWarning, match=REMOVAL):
            with nwb_read_io(str(nwb_path), "r") as io:
                io.read()

    @pytest.mark.parametrize("mode", ["w", "a", "r+"])
    def test_another_mode_warns_and_is_still_refused_before_the_file_opens(
        self, nwb_path, tmp_path, mode
    ):
        path = tmp_path / "target.nwb"
        path.write_bytes(nwb_path.read_bytes())
        before = path.read_bytes()
        with pytest.warns(DeprecationWarning, match=REMOVAL):
            with pytest.raises(ValueError, match=r"pynwb\.NWBHDF5IO"):
                with nwb_read_io(str(path), mode):
                    pass  # pragma: no cover - the raise happens before the body
        assert path.read_bytes() == before

    def test_omitting_mode_does_not_warn(self, nwb_path):
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            with nwb_read_io(str(nwb_path)) as io:
                io.read()
        assert not _only_deprecations(record)

    def test_read_nwb_does_not_warn(self, nwb_path):
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            read_nwb(str(nwb_path))
        assert not _only_deprecations(record)
