import pytest
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import jnwb


class TestDocsSmokeFixtures:
    @pytest.fixture
    def rng(self):
        return np.random.default_rng(42)

    def test_doc02_addressing_metadata_ontology(self, rng):
        # 1. Addressing
        elec_df = pd.DataFrame(
            {"location": ["V1", "PFC", "V1, V2"], "group_name": ["probeA", "probeB", "probeC"], "z": [500.0, 1500.0, 800.0]},
            index=[0, 1, 2]
        )
        assert jnwb.map_peak_channel_to_area(0, elec_df) == "V1"
        assert jnwb.classify_layer_from_depth(0, elec_df) == "Superficial"
        assert jnwb.classify_layer_from_depth(1, elec_df) == "Deep"

        enriched = jnwb.enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [0, 1]}), elec_df)
        assert "area" in enriched.columns and "layer" in enriched.columns

        # 2. Metadata & QC
        units_df = pd.DataFrame({
            "unit_id": [1, 2, 3],
            "area": ["V1", "V1", "PFC"],
            "quality": ["good", "good", "mua"],
            "firing_rate": [12.0, 0.2, 5.5],
            "waveform_duration": [0.8, 1.1, 0.6],
            "snr": [4.2, 1.1, 2.5],
            "trial_presence_fraction": [0.95, 0.4, 0.85],
        })
        classified = jnwb.classify_unit_quality(units_df)
        assert "quality_class" in classified.columns
        assert "is_valid" in classified.columns

        census = jnwb.unit_census_report(classified, group_by=["area"])
        assert len(census) >= 1
        snr = jnwb.get_snr_analysis(classified, snr_threshold=1.0)
        assert "pass_rate" in snr

        filtered = jnwb.filter_by_criteria(classified, criteria={"area": "V1", "firing_rate": (1.0, 50.0), "snr": (2.0, 10.0)})
        assert len(filtered) == 1
        audit = jnwb.audit_units(classified)
        assert "total_units" in audit

        # 3. Ontology
        q = jnwb.Query(sessions=["ses-01"], areas=["V1"])
        assert q.sessions == ["ses-01"]

    def test_doc03_jrsa_smoke(self, rng):
        X = rng.normal(size=(8, 20, 30))  # 8 conditions, 20 units, 30 timepoints
        res = jnwb.jrsa(X, X, metric="rsa", stats=False)
        assert isinstance(res, jnwb.JRSAResult)
        assert res.value is not None

    def test_doc04_spectral_and_analyzers(self, rng):
        sig = rng.normal(size=1000)
        freqs, psd = jnwb.compute_psd(sig, fs=1000.0)
        assert len(freqs) == len(psd)

        bp = jnwb.band_power(sig, sampling_rate=1000.0, freq_range=(14.0, 30.0))
        assert isinstance(bp, float) and bp >= 0.0

        tilt = jnwb.spectral_tilt(sig, sampling_rate=1000.0)
        assert "exponent" in tilt or "slope" in tilt or "spectral_tilt" in tilt

        coh = jnwb.cross_area_coherence(sig, sig, sampling_rate=1000.0)
        assert "band_coherence" in coh

        db_val = jnwb.to_db(2.0)
        assert np.isclose(db_val, 10.0 * np.log10(2.0))

        # TFRAnalyzer
        tfr_tensor = rng.normal(size=(4, 10, 50))  # 4 channels, 10 freqs, 50 times
        freq_coords = np.linspace(5.0, 50.0, 10)
        band_power = jnwb.TFRAnalyzer.extract_band(tfr_tensor, band="beta", freqs=freq_coords, freq_axis=1)
        assert band_power.shape == (4, 50)

        # complex_tfr primitive
        raw_lfp = rng.normal(size=(4, 200))
        tfr_res = jnwb.complex_tfr(raw_lfp, fs=1000.0, freqs=freq_coords, n_cycles=5.0)
        assert isinstance(tfr_res, jnwb.ComplexTFR)
        assert tfr_res.shape == (4, 10, 200)
        assert tfr_res.power.shape == (4, 10, 200)

    def test_doc05_artifact_detection_and_repair(self, rng):
        data = rng.normal(size=(8, 500))
        corr = jnwb.channel_correlation_matrix(data)
        assert corr.shape == (8, 8)
        bad_mask, _, _ = jnwb.bad_channels_from_correlation(corr, z_thresh=2.5)
        assert len(bad_mask) == 8

        lfp_trials = rng.normal(size=(10, 8, 200))
        repaired, frac, diag = jnwb.repair_lfp_trials(lfp_trials)
        assert repaired.shape == lfp_trials.shape

    def test_doc06_spiking_onset_dynamics(self, rng):
        spk_times = np.sort(rng.uniform(0, 10, 50))
        onsets = np.array([1.0, 3.0, 5.0, 7.0])
        tb, rate, sem = jnwb.raster_psth(spk_times, onsets, win_ms=(-100.0, 300.0), bin_ms=10.0)
        assert len(tb) == len(rate) == len(sem)

        smoothed = jnwb.causal_exp_smooth(rate, bin_ms=10.0, tau_ms=30.0)
        assert len(smoothed) == len(rate)

        fit = jnwb.fit_exponential_onset(tb, rate, t0_bounds=(0.0, 200.0))
        assert "t0" in fit and "bound_status" in fit

    def test_doc07_statistics_and_permutations(self, rng):
        data = rng.normal(size=50)
        boot = jnwb.StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=100, rng=rng)
        assert "bootstrap_ci" in boot

        labels = np.array(["A", "B", "A", "B", "A", "B"])
        groups = np.array([1, 1, 2, 2, 3, 3])
        shuf = jnwb.permute_labels(labels, groups=groups, scheme="within_group", rng=rng)
        assert len(shuf) == len(labels)

        fires_a = np.array([True, False, True, True, False])
        fires_b = np.array([False, False, True, False, False])
        f_test = jnwb.paired_fire_prob_test(fires_a, fires_b, n_shuffles=100, n_bootstrap=100, rng=rng)
        assert "p_value_fire_shuffle" in f_test

    def test_doc08_directed_connectivity(self, rng):
        X = rng.normal(size=500)
        Y = rng.normal(size=500)
        g_res = jnwb.granger(X, Y, order=2, n_surrogates=10, seed=0)
        assert isinstance(g_res, jnwb.DirectedResult)

        psi_res = jnwb.phase_slope_index(X, Y, fs=1000.0, n_surrogates=10, seed=0)
        assert isinstance(psi_res, jnwb.DirectedResult)

        te_res = jnwb.transfer_entropy(X, Y, n_surrogates=10, seed=0)
        assert isinstance(te_res, jnwb.DirectedResult)

    def test_doc09_decoding_and_viz(self, rng, tmp_path):
        X = rng.normal(size=(20, 5))
        y = np.repeat([0, 1], 10)
        dec_res = jnwb.nested_cv_linear_svm(X, y, n_splits=2)
        assert "accuracy" in dec_res

        jnwb.setup_vector_graphics()
        fig, ax = plt.subplots()
        ax.plot([0, 1, 2], [10, 20, 15])
        jnwb.apply_tight_auto_axis(ax, x_span=(0, 2), y_margin=0.1)

        out_suite = tmp_path / "fig_suite"
        jnwb.save_figure_suite([fig], output_dir=out_suite, basename="test_fig", formats=["png"])
        assert (out_suite / "test_fig_page1.png").exists()
        plt.close(fig)
