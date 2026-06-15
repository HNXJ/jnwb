"""Tests for vFLIP2 mask-aware, area-aware, segment-aware laminar estimation."""

from __future__ import annotations

import numpy as np
import pytest

from codes.functions.vflip2_mapping import FlipResults, vFLIP2


class TestMaskCoercion:
    """Test mask and label coercion helpers."""

    def test_coerce_bool_mask_default_true(self):
        """Default mask should be all True."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            valid_channel_mask=None,
            auto_bad_channels=False,
        )
        assert np.all(flip.valid_channel_mask_input)
        assert len(flip.valid_channel_mask_input) == 32

    def test_coerce_bool_mask_provided(self):
        """Provided mask should be used correctly."""
        mask = np.array([True] * 16 + [False] * 16)
        flip = vFLIP2(
            np.random.rand(32, 100),
            valid_channel_mask=mask,
            auto_bad_channels=False,
        )
        assert np.array_equal(flip.valid_channel_mask_input, mask)

    def test_coerce_bool_mask_too_short_raises(self):
        """Short mask should raise ValueError."""
        with pytest.raises(ValueError, match="Mask length"):
            vFLIP2(
                np.random.rand(32, 100),
                valid_channel_mask=np.array([True] * 10),
            )

    def test_coerce_area_labels_default(self):
        """Default area labels should be 'unknown'."""
        flip = vFLIP2(np.random.rand(32, 100), area_labels=None)
        assert np.all(flip.area_labels == "unknown")

    def test_coerce_area_labels_provided(self):
        """Provided area labels should be used."""
        labels = np.array(["V1"] * 16 + ["V2"] * 16)
        flip = vFLIP2(
            np.random.rand(32, 100),
            area_labels=labels,
            auto_bad_channels=False,
        )
        assert np.array_equal(flip.area_labels, labels)

    def test_coerce_area_labels_too_short_raises(self):
        """Short area labels should raise ValueError."""
        with pytest.raises(ValueError, match="area_labels length"):
            vFLIP2(
                np.random.rand(32, 100),
                area_labels=np.array(["V1"] * 10),
            )


class TestAutoBadChannelDetection:
    """Test automatic zig-zag bad channel detection."""

    def test_auto_bad_channels_detects_spike(self):
        """Should detect channel with anomalous PSD as bad."""
        np.random.seed(42)
        n_chan, n_freq = 32, 100
        psd = np.random.lognormal(0, 0.5, (n_chan, n_freq))

        # Inject an outlier channel
        psd[15, :] *= 100

        flip = vFLIP2(
            psd,
            auto_bad_channels=True,
            bad_zscore_cut=5.0,
            omega_cut=-np.inf,  # Allow fit to proceed
        )

        assert flip.auto_bad_channel_mask[15]
        assert not flip.valid_channel_mask[15]

    def test_auto_bad_channels_false_skips_detection(self):
        """When disabled, should not run detection."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        assert np.all(~flip.auto_bad_channel_mask)

    def test_robust_z_scores_stored(self):
        """Robust Z-scores should be accessible after fitting."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            auto_bad_channels=True,
            omega_cut=-np.inf,
        )
        assert hasattr(flip, "zigzag_robust_z")
        assert len(flip.zigzag_robust_z) == 32


class TestAreaAwareSegmentation:
    """Test area-aware segment candidate generation."""

    def test_single_area_creates_one_segment(self):
        """Single valid area should create one segment."""
        labels = np.array(["na"] * 4 + ["V1"] * 24 + ["na"] * 4)
        flip = vFLIP2(
            np.random.rand(32, 100),
            area_labels=labels,
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        # Should have one clean segment in V1
        assert len(flip.candidate_segments) >= 1
        # First segment should be in V1
        seg_start, seg_end, seg_area = flip.candidate_segments[0]
        assert seg_area == "V1"

    def test_two_areas_create_two_segments(self):
        """Two distinct areas should create separate segments."""
        labels = np.array(
            ["na"] * 4 + ["V1"] * 12 + ["na"] * 4 + ["V2"] * 12 + ["na"] * 4
        )
        flip = vFLIP2(
            np.random.rand(36, 100),
            area_labels=labels,
            allow_cross_area=False,
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        # Should have segments for V1 and V2
        areas = {seg[2] for seg in flip.candidate_segments}
        assert areas == {"V1", "V2"}

    def test_allow_cross_area_creates_multi_segment(self):
        """With allow_cross_area=True, should create multi-area segment."""
        labels = np.array(["V1"] * 16 + ["V2"] * 16)
        flip = vFLIP2(
            np.random.rand(32, 100),
            area_labels=labels,
            allow_cross_area=True,
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        areas = {seg[2] for seg in flip.candidate_segments}
        assert "multi" in areas

    def test_na_areas_filtered(self):
        """NA/bad/out areas should be filtered from valid channels."""
        labels = np.array(["bad"] * 10 + ["V1"] * 20 + ["wm"] * 10)
        flip = vFLIP2(
            np.random.rand(40, 100),
            area_labels=labels,
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        # Valid channels should only be in V1 region
        assert np.all(flip.area_labels[flip.valid_channel_mask] == "V1")

    def test_custom_na_labels(self):
        """Custom NA labels should be respected."""
        labels = np.array(["exclude"] * 10 + ["V1"] * 20 + ["skip"] * 10)
        flip = vFLIP2(
            np.random.rand(40, 100),
            area_labels=labels,
            na_area_labels=("exclude", "skip"),
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        assert np.all(flip.area_labels[flip.valid_channel_mask] == "V1")


class TestNoValidChannels:
    """Test behavior when no valid channels remain after filtering."""

    def test_all_bad_channels_raises(self):
        """All channels marked bad should raise ValueError."""
        with pytest.raises(ValueError, match="No valid channels"):
            vFLIP2(
                np.random.rand(32, 100),
                bad_channel_mask=np.ones(32, dtype=bool),
            )

    def test_all_na_areas_raises(self):
        """All channels in NA areas should raise ValueError."""
        with pytest.raises(ValueError, match="No valid channels"):
            vFLIP2(
                np.random.rand(32, 100),
                area_labels=np.array(["na"] * 32),
            )

    def test_no_clean_segments_raises(self):
        """No segments long enough should raise ValueError."""
        # Very sparse valid channels
        valid = np.zeros(32, dtype=bool)
        valid[5] = True
        valid[20] = True
        with pytest.raises(ValueError, match="No clean contiguous segment"):
            vFLIP2(
                np.random.rand(32, 100),
                valid_channel_mask=valid,
                min_segment_channels=10,
            )


class TestSegmentFitting:
    """Test that fitting respects segment boundaries."""

    def test_segment_info_reported(self):
        """Segment info should report fitted segment."""
        labels = np.array(["V1"] * 32)
        flip = vFLIP2(
            np.random.rand(32, 100),
            area_labels=labels,
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        info = flip.get_segment_info()
        assert info["fitted"]
        assert info["area"] == "V1"
        assert info["start"] < info["end"]
        assert info["n_valid_channels"] == 32

    def test_results_contains_segment_fields(self):
        """Results should contain segment start/end/area."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        assert flip.Results is not None
        assert flip.Results.segment_startchannel is not None
        assert flip.Results.segment_endchannel is not None
        assert flip.Results.segment_area is not None


class TestLaminarLabels:
    """Test laminar label vector generation."""

    def test_label_vector_shape(self):
        """Label vector should have requested shape."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        labels = flip.get_laminar_labels128()
        assert labels.shape == (128,)

    def test_label_vector_values(self):
        """Labels should only contain valid values."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        labels = flip.get_laminar_labels128()
        valid_values = {"sup", "mid", "deep", "na"}
        assert set(np.unique(labels)).issubset(valid_values)

    def test_label_vector_outside_segment_is_na(self):
        """Channels outside fitted segment should be 'na'."""
        labels_input = np.array(["na"] * 4 + ["V1"] * 24 + ["na"] * 4)
        flip = vFLIP2(
            np.random.rand(32, 100),
            area_labels=labels_input,
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        labels = flip.get_laminar_labels128()
        # Edge channels should be na
        assert np.all(labels[:4] == "na")
        assert np.all(labels[28:] == "na")

    def test_crossover_within_segment(self):
        """Crossover should be within segment boundaries."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        if flip.Results is not None:
            start = flip.Results.segment_startchannel
            end = flip.Results.segment_endchannel
            cross = flip.Results.crossoverchannel
            assert start <= cross <= end

    def test_mid_zone_width(self):
        """Mid zone width should respect layer4 thickness."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            layer4Thickness=0.4,
            intdist=0.05,
            auto_bad_channels=False,
            omega_cut=-np.inf,
        )
        labels = flip.get_laminar_labels128()
        n_mid = np.sum(labels == "mid")
        # With 0.4mm layer4 and 0.05mm intdist, mid zone ~8 channels
        assert 4 <= n_mid <= 16


class TestAdaptiveCrossover:
    """Test adaptive crossover refinement."""

    def test_adaptive_crossover_enabled(self):
        """With adaptive_crossover=True, should refine crossover."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            adaptive_crossover=True,
            crossover_search_radius=4,
            omega_cut=-np.inf,
        )
        # Should complete without error
        assert flip.Results is not None

    def test_adaptive_crossover_disabled(self):
        """With adaptive_crossover=False, should use base crossover."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            adaptive_crossover=False,
            omega_cut=-np.inf,
        )
        assert flip.Results is not None


class TestBackwardCompatibility:
    """Test that old API still works."""

    def test_legacy_flip_functions_alias(self):
        """FlipFunctions should be alias for vFLIP2."""
        from codes.functions.vflip2_mapping import FlipFunctions

        assert FlipFunctions is vFLIP2

    def test_legacy_init_signature(self):
        """Old-style init should work."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            intdist=0.05,
            freqbinsize=1.0,
            DataType="psd",
        )
        assert flip.intdist == 0.05

    def test_results_dataclass_access(self):
        """Results should be accessible as dataclass attributes."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            omega_cut=-np.inf,
        )
        assert flip.Results is not None
        # Should be able to access as attributes
        _ = flip.Results.crossoverchannel
        _ = flip.Results.omega
        _ = flip.Results.segment_area


class TestOmegaCut:
    """Test omega threshold behavior."""

    def test_low_omega_cut_returns_none(self):
        """Very high omega_cut should result in no fit."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            omega_cut=100.0,  # Impossibly high
        )
        assert flip.Results is None

    def test_negative_omega_cut_allows_fit(self):
        """Negative omega_cut should allow any fit."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            omega_cut=-np.inf,
        )
        # May or may not fit depending on data quality
        # but should not error


class TestAcceptanceChecks:
    """Test recommended acceptance checks."""

    def test_acceptance_check_pattern(self):
        """Demonstrate recommended acceptance pattern."""
        flip = vFLIP2(
            np.random.rand(32, 100),
            area_labels=np.array(["V1"] * 32),
            omega_cut=-np.inf,
        )

        # Check 1: Results exists
        assert flip.Results is not None, "Fit failed"

        # Check 2: Omega is finite
        assert np.isfinite(flip.Results.omega), "Omega not finite"

        # Check 3: Crossover within segment
        assert (
            flip.Results.segment_startchannel
            <= flip.Results.crossoverchannel
            <= flip.Results.segment_endchannel
        ), "Crossover outside segment"

        # Check 4: Segment area is valid
        assert flip.Results.segment_area not in {
            "na",
            "bad",
            "out",
            "white_matter",
            "wm",
        }, "Invalid area"

        # Check 5: Labels have correct shape
        labels = flip.get_laminar_labels128()
        assert labels.shape == (128,), "Wrong label shape"

        # Check 6: Labels have valid values
        assert set(np.unique(labels)).issubset(
            {"sup", "mid", "deep", "na"}
        ), "Invalid label values"


class TestRealisticPSD:
    """Test with more realistic PSD structure."""

    def create_realistic_psd(
        self, n_chan: int = 32, n_freq: int = 100
    ) -> np.ndarray:
        """Create PSD with superficial/deep frequency gradient."""
        np.random.seed(42)
        freqs = np.linspace(0, 100, n_freq)

        psd = np.zeros((n_chan, n_freq))
        for ch in range(n_chan):
            # Deeper channels (higher index) have more low-freq power
            depth_factor = ch / n_chan

            # Low frequency component (alpha/beta)
            low_freq_pow = 10 * (1 - depth_factor) * np.exp(-((freqs - 10) ** 2) / 50)

            # High frequency component (gamma)
            high_freq_pow = 5 * depth_factor * np.exp(-((freqs - 50) ** 2) / 200)

            psd[ch, :] = low_freq_pow + high_freq_pow + np.random.exponential(0.5, n_freq)

        return psd

    def test_fits_realistic_psd(self):
        """Should fit to PSD with realistic laminar structure."""
        psd = self.create_realistic_psd(32, 100)
        flip = vFLIP2(
            psd,
            orientation="both",
            omega_cut=0.0,  # Low threshold for test
        )
        # Should either fit or not, but not error
        if flip.Results is not None:
            assert flip.Results.orientation in {-1, 1}

    def test_multi_segment_fitting(self):
        """Test fitting with multiple area segments."""
        psd = self.create_realistic_psd(64, 100)
        labels = np.array(["V1"] * 32 + ["V2"] * 32)

        flip = vFLIP2(
            psd,
            area_labels=labels,
            allow_cross_area=False,
            omega_cut=0.0,
        )

        # Should fit one of the segments
        if flip.Results is not None:
            assert flip.Results.segment_area in {"V1", "V2"}
