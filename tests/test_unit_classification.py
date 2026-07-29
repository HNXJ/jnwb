"""Unit tests for shuffle-controlled S+/S-/O+ classification."""

from __future__ import annotations

import numpy as np
import pandas as pd

from jnwb.unit_classification import (
    ClassificationConfig,
    GLO_CONDITIONS,
    omission_events,
    prevalence_summary,
    slot_is_omission,
    slot_is_stimulus,
    stimulus_present_events,
    _assign_labels,
    _shuffle_pvalue_paired,
)


def test_stimulus_and_omission_slot_maps_cover_12_conditions():
    stim = stimulus_present_events()
    omit = omission_events()
    # 12 conditions × 4 slots = 48; omissions are exactly one X per omission condition
    # 9 omission conditions (3 families × 3) → 9 omission events
    assert len(omit) == 9
    assert len(stim) + len(omit) == 48
    assert all(slot_is_stimulus(c, s) for c, s in stim)
    assert all(slot_is_omission(c, s) for c, s in omit)
    # Examples from the user prompt
    assert ("RXRR", 2) in omit
    assert ("RRXR", 3) in omit
    assert ("RRRX", 4) in omit
    assert ("RRRR", 2) in stim
    assert ("RRXR", 2) in stim
    assert ("RXRR", 1) in stim
    assert all(c in GLO_CONDITIONS for c, _ in stim + omit)


def test_shuffle_pvalue_detects_strong_paired_effect():
    rng = np.random.default_rng(0)
    base = rng.normal(5.0, 1.0, size=80)
    stim = base + 4.0 + rng.normal(0, 0.2, size=80)
    eff, p = _shuffle_pvalue_paired(stim, base, n_shuffles=500, rng=rng, alternative="two-sided")
    assert eff > 3.0
    assert p < 0.01


def test_assign_labels_priority_o_plus_over_s_plus():
    df = pd.DataFrame(
        [
            {
                "p_stim_shuffle": 0.001,
                "p_s_plus_shuffle": 0.001,
                "p_s_minus_shuffle": 0.9,
                "p_om_vs_base_shuffle": 0.001,
                "p_om_vs_ctrl_shuffle": 0.001,
                "p_om_vs_delay_shuffle": 0.001,
                "stim_effect_hz": 5.0,
                "om_vs_base_effect_hz": 3.0,
                "om_vs_ctrl_effect_hz": 3.0,
                "om_vs_delay_effect_hz": 3.0,
                "mean_stim_hz": 8.0,
                "mean_baseline_hz": 3.0,
                "n_stim_events": 50,
                "n_omission_events": 20,
            }
        ]
    )
    cfg = ClassificationConfig(apply_fdr=False, alpha=0.05, alpha_omission=0.05)
    out = _assign_labels(df, cfg)
    assert bool(out.loc[0, "is_o_plus"])
    assert bool(out.loc[0, "is_s_plus"])
    assert not bool(out.loc[0, "is_o_plusplus"])
    assert out.loc[0, "display_class"] == "O+"
    assert out.loc[0, "o_plus_tier"] == "O+"


def test_assign_labels_o_plusplus_requires_r_family_robustness():
    row = {
        "p_stim_shuffle": 0.5,
        "p_s_plus_shuffle": 0.5,
        "p_s_minus_shuffle": 0.5,
        "p_om_vs_base_shuffle": 0.001,
        "p_om_vs_ctrl_shuffle": 0.001,
        "p_om_vs_delay_shuffle": 0.001,
        "p_r_family_om_vs_ctrl_shuffle": 0.001,
        "stim_effect_hz": 0.0,
        "om_vs_base_effect_hz": 5.0,
        "om_vs_ctrl_effect_hz": 5.0,
        "om_vs_delay_effect_hz": 5.0,
        "r_family_om_vs_ctrl_effect_hz": 5.0,
        "n_r_family_slots_sig": 2,
        "n_r_family_omission_events": 20,
        "mean_stim_hz": 2.0,
        "mean_baseline_hz": 2.0,
        "n_stim_events": 50,
        "n_omission_events": 20,
    }
    cfg = ClassificationConfig(apply_fdr=False, alpha_omission=0.01)
    out = _assign_labels(pd.DataFrame([row]), cfg)
    assert bool(out.loc[0, "is_o_plus"])
    assert bool(out.loc[0, "is_o_plusplus"])
    assert out.loc[0, "display_class"] == "O++"
    assert out.loc[0, "o_plus_tier"] == "O++"

    weak = dict(row)
    weak["n_r_family_slots_sig"] = 1
    out2 = _assign_labels(pd.DataFrame([weak]), cfg)
    assert bool(out2.loc[0, "is_o_plus"])
    assert not bool(out2.loc[0, "is_o_plusplus"])
    assert out2.loc[0, "display_class"] == "O+"


def test_assign_o_plusplus_from_template_table_fef_pfc_corr():
    from jnwb.unit_classification import assign_o_plusplus_from_template_table, oplusplus_census_summary

    df = pd.DataFrame(
        [
            {"area": "PFC", "mean_correlation": 0.72, "permutation_pval": 0.01},
            {"area": "FEF", "mean_correlation": 0.61, "permutation_pval": 0.02},
            {"area": "V1", "mean_correlation": 0.90, "permutation_pval": 0.001},
            {"area": "PFC", "mean_correlation": 0.40, "permutation_pval": 0.01},
        ]
    )
    out = assign_o_plusplus_from_template_table(df)
    assert list(out["is_o_plusplus"]) == [True, True, False, False]
    summary = oplusplus_census_summary(out)
    assert summary["n_o_plusplus"] == 2
    assert summary["fef_pfc_n"] == 2
    assert abs(summary["fef_pfc_frac"] - 1.0) < 1e-9


def test_o_plus_rejects_delay_nonspecific():
    """Fatigue-like elevation that is not selective vs delays is not O+."""
    df = pd.DataFrame(
        [
            {
                "p_stim_shuffle": 0.5,
                "p_s_plus_shuffle": 0.5,
                "p_s_minus_shuffle": 0.5,
                "p_om_vs_base_shuffle": 0.001,
                "p_om_vs_ctrl_shuffle": 0.001,
                "p_om_vs_delay_shuffle": 0.5,
                "stim_effect_hz": 0.0,
                "om_vs_base_effect_hz": 3.0,
                "om_vs_ctrl_effect_hz": 3.0,
                "om_vs_delay_effect_hz": 0.1,
                "mean_stim_hz": 2.0,
                "mean_baseline_hz": 2.0,
                "n_stim_events": 50,
                "n_omission_events": 20,
            }
        ]
    )
    cfg = ClassificationConfig(apply_fdr=False, alpha_omission=0.01)
    out = _assign_labels(df, cfg)
    assert not bool(out.loc[0, "is_o_plus"])
    assert out.loc[0, "display_class"] == "Other"


def test_prevalence_summary_keys():
    df = pd.DataFrame({"display_class": ["S+", "S+", "S-", "Other", "O+"]})
    prev = prevalence_summary(df)
    assert abs(prev["S+"] - 0.4) < 1e-9
    assert abs(prev["S-"] - 0.2) < 1e-9
    assert abs(prev["O+"] - 0.2) < 1e-9
    assert abs(prev["Other"] - 0.2) < 1e-9
    assert prev["n_units"] == 5


def test_append_session_to_grand_table_idempotent(tmp_path):
    from jnwb.unit_classification import (
        ClassificationConfig,
        append_session_to_grand_table,
        config_to_dict,
    )

    cfg = ClassificationConfig(n_shuffles=10)
    grand = tmp_path / "grand.csv"
    df1 = pd.DataFrame(
        {
            "nwb_stem": ["sesA", "sesA"],
            "unit_id": [1, 2],
            "display_class": ["S+", "Other"],
            "area": ["PFC", "V1"],
        }
    )
    g1 = append_session_to_grand_table(df1, grand, cfg, repo_root=tmp_path)
    assert len(g1) == 2
    df2 = pd.DataFrame(
        {
            "nwb_stem": ["sesA", "sesA", "sesA"],
            "unit_id": [1, 2, 3],
            "display_class": ["S+", "S-", "O+"],
            "area": ["PFC", "V1", "FEF"],
        }
    )
    g2 = append_session_to_grand_table(df2, grand, cfg, repo_root=tmp_path)
    assert len(g2) == 3
    assert set(g2["unit_id"]) == {1, 2, 3}
    assert (tmp_path / "grand.meta.json").is_file()
    assert "method" in config_to_dict(cfg)
