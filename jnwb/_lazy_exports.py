"""Deferred ``import jnwb`` exports resolved through ``jnwb.__getattr__``."""

from __future__ import annotations

SUBMODULES = frozenset({"visual_qc"})

EXPORT_MODULES: dict[str, str] = {
    # ontology
    "Query": "ontology",
    "Dataset": "ontology",
    "AlignedDataset": "ontology",
    "Alignment": "ontology",
    "EpochCollection": "ontology",
    "Question": "ontology",
    "Result": "ontology",
    "Interpretation": "ontology",
    "Figure": "ontology",
    "Provenance": "ontology",
    "Lineage": "ontology",
    # statistics
    "StatisticalAnalysis": "statistics",
    "fires_in_window": "statistics",
    "fire_indicator": "statistics",
    "paired_fire_prob_test": "statistics",
    "rate_in_window": "statistics",
    "shuffle_pvalue_paired": "statistics",
    "shuffle_pvalue_unpaired": "statistics",
    "cluster_permutation_test": "statistics",
    "detect_trial_cycles": "statistics",
    "assign_subblock_quartiles": "statistics",
    "shuffle_r2_ci": "statistics",
    "cross_modal_comparison": "statistics",
    # metadata
    "get_all_units_metadata": "metadata",
    "classify_unit_quality": "metadata",
    "unit_census_report": "metadata",
    "get_snr_analysis": "metadata",
    "electrode_inventory": "metadata",
    "filter_by_criteria": "metadata",
    "audit_units": "metadata",
    "audit_electrodes": "metadata",
    "assign_quality_tier": "metadata",
    # decoding
    "majority_baseline": "decoding",
    "fold_majority_baseline": "decoding",
    "nested_cv_linear_svm": "decoding",
    "assign_outer_folds": "decoding",
    "build_inner_validation_partitions": "decoding",
    "build_representation_ladder": "decoding",
    # onset fitting
    "causal_exp_smooth": "onset_fitting",
    "fit_exponential_onset": "onset_fitting",
    "onset_model": "onset_fitting",
    # analyzers
    "TFRAnalyzer": "analyzers",
    "UnitAnalyzer": "analyzers",
    "PopulationAnalyzer": "analyzers",
    # viz (matplotlib)
    "setup_vector_graphics": "viz",
    "apply_tight_auto_axis": "viz",
    "save_figure_suite": "viz",
    "resample_onsets": "viz",
    "raster_psth": "viz",
}
