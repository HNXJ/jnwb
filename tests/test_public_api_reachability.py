"""A caller who can catch a read's refusal by name can reach its remedy by name.

``MissingRequiredNWBFieldError`` is public and meant to be caught. The waiver that clears it --
``read_nwb`` for the object, ``nwb_read_io`` for the object with its file still open -- and the
warning a repaired read emits, ``SqueezedAttributeWarning``, must be reachable the same way: as
``jnwb.<name>`` after ``import jnwb`` and nothing else. Everything here goes through the top-level
namespace only, except that the import table compares each name with its defining submodule.
"""

from __future__ import annotations

import importlib

import h5py
import numpy as np
import pytest

import jnwb

REMEDY = ("MissingRequiredNWBFieldError", "read_nwb", "nwb_read_io", "SqueezedAttributeWarning")


@pytest.mark.parametrize("name", REMEDY)
def test_the_name_is_exported_and_listed(name):
    assert name in jnwb.__all__
    assert name in dir(jnwb)
    assert getattr(jnwb, name).__module__ == "jnwb.nwb_io"


@pytest.fixture
def incomplete(tmp_path):
    from jnwb.testing.nwb_fixtures import write_synth_nwb

    path = tmp_path / "incomplete.nwb"
    write_synth_nwb(str(path))
    with h5py.File(path, "a") as handle:
        del handle["session_description"]
    return path


def test_a_caller_catching_the_refusal_reaches_the_waiver(incomplete):
    path = incomplete
    try:
        jnwb.read_nwb(str(path))
    except jnwb.MissingRequiredNWBFieldError as exc:
        nwbfile = jnwb.read_nwb(str(path), allow_missing=(exc.field_name,))
    else:  # pragma: no cover - the refusal is the premise
        pytest.fail("a file without session_description was not refused")

    assert nwbfile.session_description == ""
    assert nwbfile.jnwb_waived_requirements == ("session_description",)


def test_the_open_file_route_records_the_waiver_and_reads_data(incomplete):
    """The object ``read_nwb`` returns has a closed file; this route is how a waived file's data
    is read, so it must carry the same record of the waiver."""
    with pytest.raises(jnwb.MissingRequiredNWBFieldError):
        with jnwb.nwb_read_io(str(incomplete)) as io:
            io.read()

    with jnwb.nwb_read_io(str(incomplete), allow_missing=("session_description",)) as io:
        nwbfile = io.read()
        spikes = np.asarray(nwbfile.units["spike_times"][0])

    assert nwbfile.session_description == ""
    assert nwbfile.jnwb_waived_requirements == ("session_description",)
    assert spikes.size > 0


def test_the_squeeze_warning_is_catchable_by_its_public_name(tmp_path):
    from jnwb.testing.nwb_fixtures import write_synth_nwb

    path = tmp_path / "squeezed.nwb"
    write_synth_nwb(str(path))
    with h5py.File(path, "a") as handle:
        handle["/general/devices/synth_device_0"].attrs["description"] = np.array(
            ["probe desc"], dtype=object)

    with pytest.warns(jnwb.SqueezedAttributeWarning):
        jnwb.read_nwb(str(path))


# The export and import checks that the per-module test files repeated. A name in LISTED_IN_ALL is
# checked with `name in jnwb.__all__`. A name in IMPORTED_FROM is checked with `jnwb.<name> is` the
# same name in the module that defines it, as the removed test imported it from that module.
LISTED_IN_ALL = (
    # artifact_repair
    "repair_lfp_trials", "repair_band_artifacts",
    # connectivity
    "spike_mutual_information", "binary_occupancy_mutual_information",
    "spike_count_mutual_information", "granger_causality", "network_topology",
    "DirectedResult", "as_trials", "bin_spikes", "granger", "granger_spectral",
    "phase_slope_index", "transfer_entropy", "directed_connectivity", "directed_network",
    # decoding
    "majority_baseline", "fold_majority_baseline", "nested_cv_linear_svm",
    "assign_outer_folds", "build_inner_validation_partitions", "build_representation_ladder",
    # filtering
    "bandpass_filter", "notch_filter",
    # io
    "stream_npz_array", "io",
    # metadata
    "get_all_units_metadata", "classify_unit_quality", "unit_census_report",
    "get_snr_analysis", "electrode_inventory", "filter_by_criteria", "audit_units",
    "audit_electrodes", "assign_quality_tier",
    # onset_fitting
    "causal_exp_smooth", "fit_exponential_onset", "onset_model",
    # spiking
    "compute_response_metrics", "classify_response_significance", "phase_locking_index",
    "pairwise_phase_consistency", "gaussian_smooth_rate",
    # statistics
    "fires_in_window", "fire_indicator", "paired_fire_prob_test", "rate_in_window",
    "shuffle_pvalue_paired", "shuffle_pvalue_unpaired", "detect_trial_cycles",
    "assign_subblock_quartiles", "shuffle_r2_ci", "cross_modal_comparison",
    "clopper_pearson", "exact_sign_flip", "mann_whitney_p_floor", "fdr_correct",
    # viz
    "setup_vector_graphics", "apply_tight_auto_axis", "save_figure_suite",
    "resample_onsets", "raster_psth",
)


@pytest.mark.parametrize("name", LISTED_IN_ALL)
def test_listed_in_jnwb_all(name):
    assert name in jnwb.__all__


IMPORTED_FROM = {
    "jnwb.artifact_repair": ("repair_lfp_trials", "repair_band_artifacts",
                             "detect_band_outliers", "DETECTION_TAILS"),
    "jnwb.connectivity": ("spike_mutual_information", "binary_occupancy_mutual_information",
                          "spike_count_mutual_information", "granger_causality",
                          "network_topology", "DirectedResult", "as_trials", "bin_spikes",
                          "granger", "granger_spectral", "phase_slope_index",
                          "transfer_entropy", "directed_connectivity", "directed_network"),
    "jnwb.decoding": ("majority_baseline", "fold_majority_baseline", "nested_cv_linear_svm",
                      "assign_outer_folds", "build_inner_validation_partitions",
                      "build_representation_ladder"),
    "jnwb.filtering": ("bandpass_filter", "notch_filter"),
    "jnwb.onset_fitting": ("causal_exp_smooth", "fit_exponential_onset", "onset_model"),
    "jnwb.spiking": ("compute_response_metrics", "classify_response_significance",
                     "phase_locking_index", "pairwise_phase_consistency",
                     "gaussian_smooth_rate"),
    "jnwb.statistics": ("fires_in_window", "fire_indicator", "paired_fire_prob_test",
                        "rate_in_window", "shuffle_pvalue_paired", "shuffle_pvalue_unpaired",
                        "detect_trial_cycles", "assign_subblock_quartiles", "shuffle_r2_ci",
                        "cross_modal_comparison", "clopper_pearson", "exact_sign_flip",
                        "mann_whitney_p_floor", "fdr_correct"),
    "jnwb.viz": ("setup_vector_graphics", "apply_tight_auto_axis", "save_figure_suite",
                 "resample_onsets", "raster_psth"),
}


@pytest.mark.parametrize("module,name", [
    (module, name) for module, names in IMPORTED_FROM.items() for name in names
])
def test_importable_from_top_level_jnwb(module, name):
    assert getattr(jnwb, name) is getattr(importlib.import_module(module), name)
