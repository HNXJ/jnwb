"""Non-finite inputs fail loudly on every public numeric function.

Each plain function in `jnwb.__all__` is called once with valid inputs and twice
more with one leaf poisoned, first NaN then inf. The poisoned call must raise
`ValueError` naming the poisoned argument. Three functions document NaN
propagation instead of refusal and are checked for that; functions taking no
numeric argument are exempt with a reason. A function that stays silent, or
whose refusal does not name the argument, is listed in `AWAITING_REPAIR` as a
strict xfail, so wiring the refusal turns the row green.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import jnwb

EXEMPT = {
    "acquisition_channel": "takes a path or open NWB, not a numeric array",
    "apply_tight_auto_axis": "takes a Matplotlib axes, not a numeric array",
    "assert_mergeable": "takes metadata dicts, not a numeric array",
    "cache_clear": "takes a directory path only",
    "cache_key": "hashes its inputs; NaN changes the key, it is not computed on",
    "cache_load": "takes a directory path and a key only",
    "cache_store": "storage writes bytes; nothing numeric is computed",
    "check_ragged_indices": "takes a path, not a numeric array",
    "check_waveform_blocks": "takes a path, not a numeric array",
    "compress_fp32": "takes paths, not a numeric array",
    "edges_near_events": "takes a path plus an event array, but never runs without a file",
    "electrode_inventory": "takes paths, not a numeric array",
    "event_onsets": "takes a path or open NWB, not a numeric array",
    "events": "takes a path or open NWB, not a numeric array",
    "fuse_laminar_anchors": "takes scalars only; no numeric array argument",
    "get_all_units_metadata": "takes paths, not a numeric array",
    "inspect": "takes a path or open NWB, not a numeric array",
    "label_layers": "takes result objects, not a numeric array",
    "map_peak_channel_to_layer": "takes a LaminarCurationResult object, not a numeric array",
    "nwb_read_io": "takes a path only; the NaN-path row below tracks its refusal",
    "preflight": "takes a Question object, not a numeric array",
    "read_nwb": "takes a path, not a numeric array",
    "repair_nwb": "takes paths, not a numeric array",
    "repair_ragged_index": "takes a path, not a numeric array",
    "resolve_acquisition": "takes a path or open NWB, not a numeric array",
    "resolve_interval_table": "takes a path or open NWB, not a numeric array",
    "save_figure_suite": "takes Figure objects, not a numeric array",
    "screen_units_against_labels": "takes a fitted classifier object, not a numeric array",
    "setup_vector_graphics": "takes no arguments at all",
    "stream_npz_array": "reads an array from disk; nothing numeric is computed",
    "transform_nwb": "takes paths, not a numeric array",
    "unit_spike_times": "takes a path or open NWB, not a numeric array",
    "units_table": "takes an open NWBFile, not a numeric array",
    "validate_nwb": "takes a path, not a numeric array",
    "verify_nwb": "takes a path, not a numeric array",
    "write_nwb": "takes an open NWBFile, not a numeric array",
}

#: Functions whose docstring states NaN propagation instead of refusal.
NAN_PROPAGATES = {
    "aggregate_to_db": "a NaN ratio stays NaN through the log",
    "causal_gaussian_smooth": "a NaN bin spreads through the kernel sum",
    "jrsa": "a NaN sample stays NaN through the alignment",
}

#: The poisoned leaf per function: `key`, `key[column]`, `key[sub]` or `key[sub][column]`.
LEAF = {
    'align_waveforms': 'fs',
    'amplitude_cutoff': 'amplitudes',
    'aperiodic_fit': 'freqs',
    'as_trials': 'X',
    'assign_outer_folds': 'trials[start_time]',
    'assign_quality_tier': 'snr',
    'assign_subblock_quartiles': 'epochs_df[start_time]',
    'audit_electrodes': 'elec_df[x]',
    'audit_units': 'units_df[firing_rate]',
    'bad_channels_from_correlation': 'corr',
    'bad_trials_single_channel': 'trial_waveforms',
    'band_power': 'baseline',
    'bandpass_filter': 'data',
    'bin_spikes': 'window_s',
    'binary_occupancy_mutual_information': 'time_window',
    'bipolar_reference': 'channel_data',
    'build_inner_validation_partitions': 'outer_trials[outer_fold]',
    'build_permutation_plan': 'rng',
    'build_representation_ladder': 'raster',
    'build_time_resolved_matrix': 'time_window_ms',
    'causal_exp_smooth': 'bin_ms',
    'channel_correlation_matrix': 'data_ch_by_time',
    'classify_layer_from_depth': 'electrodes_df[x]',
    'classify_response_significance': 'metrics[z]',
    'classify_unit_quality': 'units_df[firing_rate]',
    'clopper_pearson': 'k',
    'cluster_permutation_test': 'X',
    'coherence_bias_floor': 'signals',
    'complex_tfr': 'data',
    'compute_multitaper_psd': 'data',
    'compute_population_trajectory': 'time_window_ms',
    'compute_psd': 'lfp_data',
    'compute_response_metrics': 'epoch_onsets',
    'consensus_bad_trials': 'per_channel_flags',
    'cross_area_coherence': 'fs',
    'cross_modal_comparison': 'spike_data',
    'curate_and_label': 'lfp',
    'current_source_density_1d': 'conductivity_s_per_m',
    'derive_tick_clock': 'spike_times',
    'detect_bad_channels': 'data',
    'detect_band_outliers': 'band_trace',
    'detect_trial_cycles': 'epochs_df[start_time]',
    'directed_connectivity': 'X',
    'directed_network': 'signals',
    'effective_rate': 'data',
    'effective_sample_size': 'x',
    'enrich_units_dataframe': 'electrodes_df[x]',
    'epoch_continuous': 'data',
    'evoked_csd_sink': 'erp',
    'exact_sign_flip': 'diffs',
    'fano_factor': 'window_s',
    'fdr_correct': 'p_values',
    'filter_by_criteria': 'df[firing_rate]',
    'fire_indicator': 'spike_times',
    'fires_in_window': 'spike_times',
    'fit_exponential_onset': 'rate',
    'fleiss_kappa': 'counts',
    'fold_majority_baseline': 'y_test',
    'gaussian_smooth_rate': 'bin_ms',
    'gaze_departure_onsets': 'trial_starts',
    'get_snr_analysis': 'units_df[firing_rate]',
    'granger': 'X',
    'granger_causality': 'signal1',
    'granger_nonparametric': 'X',
    'granger_spectral': 'X',
    'granger_time_reversed': 'X',
    'harmonic_analysis': 'lfp_trace',
    'imaginary_coherency': 'x',
    'interpolate_channel_runs': 'data',
    'isi_cv': 'spike_times',
    'laplacian_reference': 'channel_data',
    'majority_baseline': 'labels',
    'mann_whitney_p_floor': 'n1',
    'map_peak_channel_to_area': 'electrodes_df[x]',
    'morlet_wavelet': 'f0',
    'nested_cv_linear_svm': 'X',
    'network_burst_index': 'window_s',
    'network_topology': 'adjacency_matrix',
    'noise_correlation': 'min_trials',
    'normalize_waveforms': 'waveforms',
    'notch_filter': 'data',
    'onset_model': 't',
    'paired_fire_prob_test': 'fires_null',
    'pairwise_phase_consistency': 'phases',
    'partial_coherence': 'fs',
    'permute_labels': 'y',
    'phase_locking_index': 'lfp_phase',
    'phase_slope_index': 'X',
    'presence_ratio': 'spike_times',
    'probe_geometry': 'electrodes_table[x]',
    'raster_psth': 'onsets',
    'rate_in_window': 'spike_times',
    'rdm': 'X',
    'rdm_similarity': 'rdm1',
    'refractory_contamination': 'spike_times',
    'relative_power': 'baseline',
    'repair_band_artifacts': 'freqs',
    'repair_lfp_trials': 'segments',
    'repolarization_slope': 'waveform',
    'resample_onsets': 'onsets',
    'shuffle_pvalue_paired': 'a',
    'shuffle_pvalue_unpaired': 'a',
    'shuffle_r2_ci': 'y_score',
    'spatial_derivative_sharpness': 'channel_positions',
    'spectral_tilt': 'lfp_trace',
    'spike_count_correlation': 'window_s',
    'spike_count_mutual_information': 'time_window',
    'spike_mutual_information': 'time_window',
    'to_db': 'ratio',
    'transfer_entropy': 'X',
    'trial_correlation_matrix': 'trial_waveforms',
    'unit_census_report': 'units_df[firing_rate]',
    'vflip': 'freqs',
    'vflip2': 'freqs',
    'vflip2_from_lfp': 'contact_spacing',
    'vflip_from_lfp': 'fs',
    'voltage_curvature_1d': 'pitch_um',
    'waveform_features': 'waveform',
    'waveform_flatness': 'waveform',
    'waveform_halfwidth': 'waveform',
    'waveform_snr': 'spike_waveforms',
    'waveform_spread': 'waveform',
    'wavemap': 'waveforms',
    'wavemap_resolution_sweep': 'waveforms',
    'wpli': 'x',
    'xflip': 'data',
    'zflip': 'freq_range',
}

#: Rows silent on the poisoned leaf, or refusing without naming the argument.
#: Strict xfail: wiring the refusal removes the row.
AWAITING_REPAIR = {
    'assign_outer_folds': 'silent: NaN/inf in trials[start_time] returns a value',
    'assign_quality_tier': 'silent: NaN/inf in snr returns a value',
    'assign_subblock_quartiles': 'no refusal naming the argument: epochs_df[start_time] nan->VE(names=False) inf->VE(names=False)',
    'audit_electrodes': 'silent: NaN/inf in elec_df[x] returns a value',
    'audit_units': 'silent: NaN/inf in units_df[firing_rate] returns a value',
    'bad_channels_from_correlation': 'silent: NaN/inf in corr returns a value',
    'bad_trials_single_channel': 'silent: NaN/inf in trial_waveforms returns a value',
    'build_inner_validation_partitions': 'no refusal naming the argument: outer_trials[outer_fold] nan->VE(names=False) inf->OverflowError',
    'classify_layer_from_depth': 'silent: NaN/inf in electrodes_df[x] returns a value',
    'classify_response_significance': 'silent: NaN/inf in metrics[z] returns a value',
    'classify_unit_quality': 'silent: NaN/inf in units_df[firing_rate] returns a value',
    'clopper_pearson': 'no refusal naming the argument: k nan->VE(names=True) inf->OverflowError',
    'cluster_permutation_test': 'no refusal naming the argument: X nan->VE(names=False) inf->VE(names=False)',
    'detect_trial_cycles': 'no refusal naming the argument: epochs_df[start_time] nan->VE(names=False) inf->VE(names=False)',
    'directed_network': 'no refusal naming the argument: signals nan->VE(names=False) inf->VE(names=False)',
    'enrich_units_dataframe': 'silent: NaN/inf in electrodes_df[x] returns a value',
    'epoch_continuous': 'silent: NaN/inf in data returns a value',
    'fdr_correct': 'no refusal naming the argument: p_values nan->VE(names=False) inf->VE(names=False)',
    'filter_by_criteria': 'silent: NaN/inf in df[firing_rate] returns a value',
    'fit_exponential_onset': 'no refusal naming the argument: rate nan->VE(names=False) inf->VE(names=False)',
    'get_snr_analysis': 'silent: NaN/inf in units_df[firing_rate] returns a value',
    'granger_causality': 'no refusal naming the argument: signal1 nan->VE(names=False) inf->VE(names=False)',
    'interpolate_channel_runs': 'silent: NaN/inf in data returns a value',
    'mann_whitney_p_floor': 'no refusal naming the argument: n1 nan->VE(names=True) inf->OverflowError',
    'map_peak_channel_to_area': 'silent: NaN/inf in electrodes_df[x] returns a value',
    'morlet_wavelet': 'no refusal naming the argument: f0 nan->VE(names=False) inf->VE(names=True)',
    'network_topology': 'silent: NaN/inf in adjacency_matrix returns a value',
    'normalize_waveforms': 'silent: NaN/inf in waveforms returns a value',
    'pairwise_phase_consistency': 'silent: NaN/inf in phases returns a value',
    'phase_locking_index': 'silent: NaN/inf in lfp_phase returns a value',
    'probe_geometry': 'silent: NaN/inf in electrodes_table[x] returns a value',
    'rdm': 'no refusal naming the argument: X nan->VE(names=False) inf->VE(names=False)',
    'rdm_similarity': 'no refusal naming the argument: rdm1 nan->VE(names=False) inf->VE(names=False)',
    'shuffle_r2_ci': 'no refusal naming the argument: y_score nan->VE(names=False) inf->VE(names=False)',
    'to_db': 'silent: NaN/inf in ratio returns a value',
    'trial_correlation_matrix': 'silent: NaN/inf in trial_waveforms returns a value',
    'unit_census_report': 'silent: NaN/inf in units_df[firing_rate] returns a value',
}

UNITS_DF = pd.DataFrame({
    "unit_id": [0, 1, 2, 3],
    "area": ["V1"] * 4,
    "peak_channel_id": [0, 1, 2, 3],
    "quality": ["good"] * 4,
    "snr": [2.0] * 4,
    "stable": ["good"] * 4,
    "presence_ratio": [0.99] * 4,
    "electrode_group": ["g0"] * 4,
    "firing_rate": [5.0, 6.0, 4.0, 7.0],
    "waveform_duration": [0.4, 0.5, 0.4, 0.6],
})
ELEC_DF = pd.DataFrame({
    "channel_id": [0, 1, 2, 3],
    "x": [0.0] * 4,
    "y": [0.0] * 4,
    "z": [100.0, 200.0, 300.0, 400.0],
    "location": ["V1"] * 4,
    "group": ["g0"] * 4,
})
EPOCHS_DF = pd.DataFrame({"start_time": [0.0, 1.0, 2.0, 3.0],
                          "stop_time": [0.5, 1.5, 2.5, 3.5]})

FORCE_DEFAULTS = {"fs", "sampling_rate", "freq_range", "window_s",
                  "time_window_s", "time_window"}

NAME_TABLE = {
    "win_ms": (-100.0, 100.0),
    "window_ms": (-100.0, 100.0),
    "window_s": (0.0, 0.5),
    "window": (0.0, 0.5),
    "time_window_s": (0.0, 1.0),
    "time_window": (0.0, 1.0),
    "win_s": (-0.1, 0.5),
    "freq_bands": "canonical",
    "bands": "alpha",
    "onset_s": 1.0,
    "time_window_ms": (0.0, 100.0),
    "baseline_window_s": (0.0, 0.5),
    "reference_trials": [0, 1, 2, 3],
    "summary": "mean",
    "freq_range": (5.0, 40.0),
    "how": "mean_of_ratios",
    "scheme": "global",
    "low_cut": 4.0,
    "high_cut": 40.0,
    "refractory_ms": 2.0,
    "censored_ms": 1.0,
    "duration_s": 5.0,
    "orientation": "superficial_to_deep",
    "contact_spacing": 100.0,
    "blocks": np.array([[0.0, 1.0], [2.0, 3.0]]),
    "counts": None,
    "criteria": {"area": "V1"},
    "metrics": {"z": 2.5, "n": 10},
    "y_train": None,
}


class _Session:
    """One area with two units, each firing at the same times."""

    def __init__(self, spike_times):
        self._spike_times = spike_times

    def get_units(self, quality=None, area=None):
        return pd.DataFrame({"unit_id": [0, 1], "area": ["V1", "V1"]})

    def get_spike_times(self, unit_id):
        return self._spike_times


def _arr1d(rng, n=200):
    return rng.standard_normal(n) + 5.0


def _spikes(rng, n=40, lo=0.0, hi=5.0):
    return np.sort(rng.uniform(lo, hi, n))


def _onsets():
    return np.linspace(0.2, 4.0, 8)


def _by_name(rng, tmp_path, pname, param):
    n = (pname or "").lower()
    if n in NAME_TABLE and NAME_TABLE[n] is not None:
        v = NAME_TABLE[n]
        return list(v) if isinstance(v, (list, tuple)) else v
    ann = str(param.annotation) if param.annotation is not inspect._empty else ""
    if "rng" in n or "random_state" in n or "seed" in n:
        return 0
    if "path" in n or n in ("src", "dst", "file_path", "cache_dir", "output_dir"):
        return str(tmp_path / "f.nwb")
    if "df" in n or "frame" in n or "table" in n or n in ("epochs", "trials"):
        if "elec" in n:
            return ELEC_DF
        if "epoch" in n or n == "trials":
            if "outer" in n or "trial" in n:
                return pd.DataFrame({
                    "analysis": ["a"] * 4, "cycle": [0, 0, 1, 1],
                    "session": ["s"] * 4, "slot_key": ["k"] * 4,
                    "trial_id": [0, 1, 2, 3],
                    "start_time": [0.0, 1.0, 2.0, 3.0],
                    "outer_fold": [0, 1, 0, 1]})
            return EPOCHS_DF
        return UNITS_DF
    if "spike" in n:
        return _spikes(rng)
    if "tfr" in n:
        return rng.standard_normal((2, 5, 50))
    if "raster" in n:
        return rng.standard_normal((6, 4, 50)) + 5.0
    if "freqs" in n:
        return np.linspace(1.0, 200.0, 65)
    if "psd" in n or n == "power":
        return np.abs(rng.standard_normal((8, 65))) + 0.5
    if n == "baseline" or ("baseline" in n and "window" not in n and "model" not in n):
        return np.abs(rng.standard_normal((8, 65))) + 0.5
    if "spike_times" in n or n in ("st",):
        return _spikes(rng)
    if "onset" in n or "starts" in n or "times_ms" in n or "timestamps" in n:
        return _onsets()
    if "waveform" in n and "blocks" not in n and "trial" not in n:
        return rng.standard_normal((10, 48)) + 5.0
    if n in ("data", "trial_waveforms"):
        return rng.standard_normal((8, 200)) + 5.0
    if "corr" in n and ("matrix" in n or n == "corr"):
        return np.corrcoef(rng.standard_normal((4, 200)))
    if n in ("electrodes_table", "elec_df", "electrodes_df", "electrodes"):
        return ELEC_DF
    if n in ("units_df",):
        return UNITS_DF
    if n in ("epochs_df", "epochs", "outer_trials", "trials", "trials_df"):
        if "outer" in n or "trial" in n:
            return pd.DataFrame({
                "analysis": ["a"] * 4, "cycle": [0, 0, 1, 1],
                "session": ["s"] * 4, "slot_key": ["k"] * 4,
                "trial_id": [0, 1, 2, 3],
                "start_time": [0.0, 1.0, 2.0, 3.0],
                "outer_fold": [0, 1, 0, 1]})
        return EPOCHS_DF
    if n in ("y_train", "y_test", "labels", "condition_id", "groups"):
        return np.array([0] * 10 + [1] * 10)
    if "counts" in n:
        return rng.integers(0, 5, size=(6, 3))
    if "phase" in n:
        return rng.uniform(-np.pi, np.pi, 200)
    if "lfp" in n or n in ("trace", "channel_data", "signals", "segments",
                           "band_trace", "data_ch_by_time", "raster"):
        return rng.standard_normal((4, 200)) + 5.0
    if n in ("x", "y", "z", "a", "b", "diffs", "rate", "amplitudes",
             "phases", "t", "t_ms", "y_true", "y_score", "signal1", "signal2"):
        return _arr1d(rng)
    if "p_values" in n or n == "ps":
        return rng.uniform(0.01, 0.99, 20)
    if n in ("freq", "q", "order", "k", "n", "alpha", "rtol", "atol", "fs",
              "pitch_um", "sigma_bins", "bin_ms", "threshold", "site_spacing_um",
              "n_shuffles", "n1", "n2", "seed", "axis", "key", "name", "how",
              "metric", "scheme"):
        scalars = {"fs": 1000.0, "pitch_um": 100.0, "sigma_bins": 2.0,
                   "bin_ms": 10.0, "threshold": 0.5, "site_spacing_um": 20.0,
                   "freq": 60.0, "q": 30.0, "rtol": 1e-5, "atol": 1e-8,
                   "alpha": 0.05, "axis": -1, "order": 5, "k": 3, "n": 10,
                   "n1": 10, "n2": 10, "n_shuffles": 50, "seed": 0,
                   "key": "k", "name": "op", "how": "mean", "metric": "rsa",
                   "scheme": "permutation"}
        return scalars.get(n, 1.0)
    if "adjacency" in n:
        m = rng.random((4, 4))
        return (m + m.T) / 2
    if "units" in n and "df" not in n:
        return UNITS_DF
    if "electrodes" in n:
        return ELEC_DF
    if "geometry" in n or "curation" in n or "question" in n or n in (
            "nwb", "session", "probe_starts", "ax", "figures", "nwbfile",
            "probe_column", "units"):
        return None
    d = param.default
    if d is not inspect._empty:
        return d
    if "float" in ann:
        return 1.0
    if "int" in ann:
        return 4
    if "str" in ann:
        return "x"
    if "bool" in ann:
        return True
    if "tuple" in ann.lower() or "sequence" in ann.lower() or "list" in ann.lower():
        return None
    if not ann:
        return _arr1d(rng)
    return None


def _is_required_default(d):
    return "requir" in repr(d).lower()


def _overrides(rng):
    st = _spikes(rng)
    return {
        "assign_quality_tier": {
            "quality": pd.Series(["good", "sua"] * 5),
            "trial_presence_fraction": pd.Series(rng.uniform(0.9, 1.0, 10)),
            "snr": pd.Series(rng.uniform(0.0, 3.0, 10))},
        "build_time_resolved_matrix": {
            "session": _Session(st), "area": "V1", "epochs_df": EPOCHS_DF,
            "time_window_ms": (0.0, 100.0)},
        "build_representation_ladder": {
            "raster": rng.standard_normal((6, 4, 50)) + 5.0},
        "build_inner_validation_partitions": {
            "outer_trials": pd.DataFrame({
                "analysis": ["a"] * 6, "session": ["s"] * 6,
                "slot_key": ["k"] * 6, "trial_id": [0, 1, 2, 3, 4, 5],
                "outer_fold": [0, 0, 0, 1, 1, 1],
                "outer_group": ["g0", "g0", "g1", "g0", "g0", "g1"]})},
        "build_permutation_plan": {
            "groups": np.array([0, 1] * 10)},
        "coherence_bias_floor": {
            "signals": rng.standard_normal((3, 4, 128)) + 5.0},
        "compute_population_trajectory": {
            "session": _Session(st), "area": "V1", "epochs_df": EPOCHS_DF,
            "time_window_ms": (0.0, 100.0)},
        "consensus_bad_trials": {
            "per_channel_flags": np.zeros((4, 8), dtype=bool)},
        "band_power": {"lfp_trace": _arr1d(rng, 4000),
                       "baseline": _arr1d(rng, 4000)},
        "cross_area_coherence": {
            "lfp_area1": _arr1d(rng, 2000), "lfp_area2": _arr1d(rng, 2000),
            "freq_bands": "canonical"},
        "cross_modal_comparison": {
            "tfr_data": rng.standard_normal((5, 50, 6)),
            "spike_data": rng.standard_normal((50, 6)) + 5.0},
        "curate_and_label": {
            "lfp": rng.standard_normal((16, 4, 2048)) + 5.0,
            "compute_xflip": False, "n_windows": 2},
        "derive_tick_clock": {
            "tick_segments": [np.arange(0, 500), np.arange(1000, 1500)],
            "spike_times": np.linspace(0.0, 5.0, 60)},
        "effective_rate": {"data": _arr1d(rng), "rate": 1000.0},
        "evoked_csd_sink": {
            "erp": rng.standard_normal((8, 200)) + 5.0,
            "times_ms": np.linspace(-100.0, 300.0, 200)},
        "fano_factor": {"spike_times": [st, st + 0.05]},
        "fleiss_kappa": {"counts": np.tile([[3, 2, 1]], (5, 1))},
        "gaze_departure_onsets": {
            "gaze": _arr1d(rng, 6000), "trial_starts": np.linspace(0.5, 4.5, 5),
            "rate": 1000.0},
        "granger_nonparametric": {"n_freqs": 16, "bands": "canonical"},
        "harmonic_analysis": {"lfp_trace": _arr1d(rng, 1000)},
        "interpolate_channel_runs": {
            "data": rng.standard_normal((4, 200)) + 5.0,
            "bad_mask": np.zeros(4, dtype=bool)},
        "jrsa": {"x1": rng.standard_normal((20, 6)) + 5.0, "null": "iid"},
        "nested_cv_linear_svm": {"X": rng.standard_normal((20, 5)) + 5.0},
        "network_burst_index": {"spike_times": [st, st + 0.05]},
        "noise_correlation": {
            "counts": rng.standard_normal((6, 20)) + 5.0,
            "condition_id": np.array([0] * 10 + [1] * 10)},
        "onset_model": {
            "t": np.linspace(0.0, 200.0, 200), "t0": 50.0, "tau": 10.0,
            "amplitude": 5.0, "baseline": 1.0},
        "paired_fire_prob_test": {
            "fires_target": np.array([True] * 14 + [False] * 6),
            "fires_null": np.array([True] * 10 + [False] * 10)},
        "phase_locking_index": {
            "lfp_timestamps": np.linspace(0.2, 4.0, 200)},
        "rdm": {"X": rng.standard_normal((10, 5)) + 5.0},
        "rdm_similarity": {
            "rdm1": np.arange(45, dtype=float),
            "rdm2": np.arange(45, dtype=float)[::-1]},
        "repair_band_artifacts": {
            "power": np.abs(rng.standard_normal((6, 4, 8, 50))) + 0.5,
            "freqs": np.linspace(1.0, 100.0, 8)},
        "waveform_snr": {
            "spike_waveforms": rng.standard_normal((10, 48)) + 5.0},
        "repair_lfp_trials": {
            "segments": rng.standard_normal((6, 4, 200)) + 5.0},
        "spatial_derivative_sharpness": {
            "channel_positions": rng.standard_normal((10, 3)) * 100.0},
        "spectral_tilt": {"lfp_trace": _arr1d(rng, 2000)},
        "spike_count_correlation": {"spike_times": [st, st + 0.05]},
        "vflip2_from_lfp": {"lfp": rng.standard_normal((4, 2000)) + 5.0},
        "wavemap": {"waveforms": rng.standard_normal((30, 48)) + 5.0},
        "wavemap_resolution_sweep": {
            "waveforms": rng.standard_normal((30, 48)) + 5.0,
            "resolutions": [0.5, 1.0]},
    }


def build(name, tmp_path):
    """Valid inputs for one public function, rebuilt identically each call."""
    rng = np.random.default_rng(0)
    fn = getattr(jnwb, name)
    kwargs = {}
    missing = None
    for pname, p in inspect.signature(fn).parameters.items():
        if p.kind in (inspect.Parameter.VAR_POSITIONAL,
                      inspect.Parameter.VAR_KEYWORD):
            continue
        if p.default is not inspect._empty and not _is_required_default(p.default):
            if pname not in FORCE_DEFAULTS:
                continue
        v = _by_name(rng, tmp_path, pname, p)
        if v is None:
            if p.default is inspect._empty and missing is None:
                missing = pname
            continue
        kwargs[pname] = v
    over = _overrides(rng)
    if name in over:
        kwargs.update(over[name])
    if missing is not None and missing not in kwargs:
        raise AssertionError(f"{name}: no valid input for {missing}")
    return kwargs


def _poison(kwargs, spec, value):
    """Copy-on-write NaN/inf injection into one leaf of built inputs."""
    kw = dict(kwargs)
    parts = spec[:-1].split("[") if spec.endswith("]") else [spec]
    top = parts[0]
    v = kwargs[top]
    if len(parts) == 1:
        if isinstance(v, np.ndarray):
            a = np.array(v, dtype=float)
            a.flat[0] = value
            kw[top] = a
        elif isinstance(v, pd.Series):
            s = v.astype(float).copy()
            s.iloc[0] = value
            kw[top] = s
        elif isinstance(v, (list, tuple)):
            items = list(v)
            items[0] = value
            kw[top] = type(v)(items)
        else:
            kw[top] = value
        return kw
    if isinstance(v, pd.DataFrame):
        d = v.copy()
        col = parts[1]
        d[col] = d[col].astype(float)
        d.iloc[0, d.columns.get_loc(col)] = value
        kw[top] = d
        return kw
    if isinstance(v, dict):
        d = dict(v)
        sub = parts[1]
        if len(parts) == 3:
            dd = v[sub].copy()
            col = parts[2]
            dd[col] = dd[col].astype(float)
            dd.iloc[0, dd.columns.get_loc(col)] = value
            d[sub] = dd
        elif isinstance(d[sub], np.ndarray):
            a = np.array(d[sub], dtype=float)
            a.flat[0] = value
            d[sub] = a
        else:
            d[sub] = value
        kw[top] = d
        return kw
    raise AssertionError(f"cannot poison {spec}")


def _plain_functions():
    return sorted(
        n for n in jnwb.__all__
        if inspect.isfunction(getattr(jnwb, n, None)) and not inspect.isclass(getattr(jnwb, n)))


def test_examined_set_covers_every_plain_function():
    names = _plain_functions()
    assert len(names) == 166, f"expected 166 plain functions, saw {len(names)}"
    assert set(EXEMPT) | set(LEAF) | set(NAN_PROPAGATES) == set(names)
    assert set(LEAF) & set(EXEMPT) == set()
    assert set(LEAF) & set(NAN_PROPAGATES) == set()
    assert set(AWAITING_REPAIR) <= set(LEAF)


def _poison_params():
    out = []
    for name in sorted(LEAF):
        if name in AWAITING_REPAIR:
            out.append(pytest.param(
                name, marks=pytest.mark.xfail(strict=True, reason=AWAITING_REPAIR[name])))
        else:
            out.append(pytest.param(name))
    return out


@pytest.mark.parametrize("name", _poison_params())
def test_nan_and_inf_in_poisoned_leaf_are_refused_by_name(name, tmp_path):
    fn = getattr(jnwb, name)
    spec = LEAF[name]
    arg = spec.split("[")[0]
    for value in (np.nan, np.inf):
        with pytest.raises(ValueError) as err:
            fn(**_poison(build(name, tmp_path), spec, value))
        assert arg in str(err.value), (
            f"{name}: refusal does not name {arg}: {str(err.value)[:120]}")


@pytest.mark.parametrize("name", sorted(set(LEAF) | set(NAN_PROPAGATES)))
def test_valid_inputs_run(name, tmp_path):
    assert getattr(jnwb, name)(**build(name, tmp_path)) is not None


def _holds_nonfinite(out):
    if isinstance(out, np.ndarray):
        return bool((~np.isfinite(out)).any()) if out.dtype.kind == "f" else False
    if isinstance(out, float):
        return not np.isfinite(out)
    if isinstance(out, (tuple, list)):
        return any(_holds_nonfinite(e) for e in out)
    if isinstance(out, dict):
        return any(_holds_nonfinite(e) for e in out.values())
    if isinstance(out, (pd.DataFrame, pd.Series)):
        return bool(out.isna().any().any() if isinstance(out, pd.DataFrame)
                    else out.isna().any())
    return False


@pytest.mark.parametrize("name", sorted(NAN_PROPAGATES))
def test_nan_propagates_where_documented(name, tmp_path):
    fn = getattr(jnwb, name)
    leaf = {"aggregate_to_db": "power",
            "causal_gaussian_smooth": "rate", "jrsa": "x1"}[name]
    out = fn(**_poison(build(name, tmp_path), leaf, np.nan))
    if name != "jrsa":
        assert _holds_nonfinite(out), f"{name}: NaN in gives no NaN out"


def test_inf_propagates_or_refuses_where_documented(tmp_path):
    for name in ("aggregate_to_db", "causal_gaussian_smooth"):
        fn = getattr(jnwb, name)
        leaf = {"aggregate_to_db": "power", "causal_gaussian_smooth": "rate"}[name]
        assert _holds_nonfinite(fn(**_poison(build(name, tmp_path), leaf, np.inf)))
    with pytest.raises(ValueError):
        getattr(jnwb, "jrsa")(**_poison(build("jrsa", tmp_path), "x1", np.inf))


@pytest.mark.xfail(strict=True, reason="path-only entry: NaN path raises TypeError, not ValueError")
def test_nan_path_is_refused_by_name():
    with pytest.raises(ValueError) as err:
        jnwb.nwb_read_io(np.nan)
    assert "path" in str(err.value)

