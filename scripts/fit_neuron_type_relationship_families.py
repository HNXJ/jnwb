r"""
Pre-registered confirmatory families for the neuron-type x layer x firing-rate x LFP
supplemental analysis (goal-neuron-type-layer-lfp-relationships-20260815), Part 3 of the
approved plan. Each family gets its own Holm/BH correction (context/figures/figstats.py),
never pooled across families -- the fig05 convention (context/figures/fig05_v1_area_hierarchy_
glmm/README.md: "its own family ... never conflated").

FAMILY 1 -- layer enrichment (sup vs deep), per functional class, WITHIN animal x WITHIN area
    Never a pooled laminar coefficient -- outputs/layers/unit_layers.csv's own documented
    coverage imbalance (Kruskal-Wallis H=12.80, P=0.0017 across animals) means a pooled
    proportion would carry the animal/area difference inside it (scripts/export_putative_
    layers.py header). Proportion of a class's layer-informative units that are 'sup' vs the
    same stratum's overall sup-rate, Clopper-Pearson exact interval (jnwb.statistics.
    clopper_pearson, the promoted canonical implementation -- CLAUDE.md tripwire #5: denominator
    is layer-informative units in that (animal, area) stratum, not raw class counts).

FAMILY 2 -- firing rate x functional class, WITHIN area
    Mann-Whitney U, class vs non-class units in the same area (nonparametric per
    omission-statistics skill's test table: firing rate is not assumed normal).

Waveform family dropped entirely (bug-nwb-waveform-metrics-uninterpretable-20260815.json).
PPC-hit-rate family lands separately once scripts/aggregate_spike_lfp_coupling_v2_corrected.py
exists (its own Clopper-Pearson output is already the family; no p-value layer needed on top).

Output: outputs/relationship_search/family1_layer_enrichment.csv,
        outputs/relationship_search/family2_firing_rate_by_class.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))

from jnwb.statistics import clopper_pearson  # noqa: E402
from figstats import holm, bh  # noqa: E402

UNIT_FEATURES = REPO / "outputs/classification/unit_master_features.csv"
OUT_DIR = REPO / "outputs/relationship_search"

CLASSES = ["is_Splus", "is_Splus_double", "is_Sminus", "is_Sminus_double",
          "is_Oplus", "is_Oplus_double", "is_Ominus", "is_Ominus_double"]
MIN_N_CLASS = 5          # minimum labelled units in a class within a stratum to test
ALPHA = 0.05


def family1_layer_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    informative = df[df.layer_informative]
    rows = []
    for (animal, area), g in informative.groupby(["animal", "area10"]):
        n_total = len(g)
        n_sup_total = int((g.layer3 == "sup").sum())
        if n_total < MIN_N_CLASS:
            continue
        for cls in CLASSES:
            gc = g[g[cls]]
            n_cls = len(gc)
            if n_cls < MIN_N_CLASS:
                continue
            k_sup = int((gc.layer3 == "sup").sum())
            lo, hi = clopper_pearson(k_sup, n_cls, alpha=ALPHA)
            baseline_rate = n_sup_total / n_total
            # Two-sided binomial test of k_sup/n_cls against the stratum's own baseline sup-rate
            # (not against 0.5 -- the relevant null is "this class's layer distribution matches
            # its area x animal's overall layer distribution", per CLAUDE.md tripwire #6: a
            # selection criterion (class membership) must not smuggle in the conclusion by
            # comparing against an ungrounded reference rate).
            p = float(stats.binomtest(k_sup, n_cls, baseline_rate, alternative="two-sided").pvalue)
            rows.append({
                "animal": animal, "area": area, "class": cls,
                "n_class_layer_informative": n_cls, "n_class_sup": k_sup,
                "class_sup_rate": k_sup / n_cls, "ci95_lo": lo, "ci95_hi": hi,
                "stratum_baseline_sup_rate": baseline_rate,
                "stratum_n_layer_informative": n_total,
                "p": p, "family": "family1_layer_enrichment", "tail": "two-sided",
            })
    out = pd.DataFrame(rows)
    if len(out):
        out["p_holm"] = holm(out.p.to_numpy())
        out["q_bh"] = bh(out.p.to_numpy())
    return out


def family2_firing_rate_by_class(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for area, g in df.groupby("area10"):
        for cls in CLASSES:
            in_cls = g.loc[g[cls], "firing_rate"].dropna()
            out_cls = g.loc[~g[cls], "firing_rate"].dropna()
            if len(in_cls) < MIN_N_CLASS or len(out_cls) < MIN_N_CLASS:
                continue
            stat, p = stats.mannwhitneyu(in_cls, out_cls, alternative="two-sided")
            # Rank-biserial effect size (Mann-Whitney U's own natural effect size).
            eff = 1.0 - (2.0 * stat) / (len(in_cls) * len(out_cls))
            rows.append({
                "area": area, "class": cls,
                "n_class": len(in_cls), "n_other": len(out_cls),
                "median_class_hz": float(in_cls.median()), "median_other_hz": float(out_cls.median()),
                "rank_biserial_effect": float(eff), "u_stat": float(stat), "p": float(p),
                "family": "family2_firing_rate_by_class", "tail": "two-sided",
            })
    out = pd.DataFrame(rows)
    if len(out):
        out["p_holm"] = holm(out.p.to_numpy())
        out["q_bh"] = bh(out.p.to_numpy())
    return out


def main():
    df = pd.read_csv(UNIT_FEATURES)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    f1 = family1_layer_enrichment(df)
    f1.to_csv(OUT_DIR / "family1_layer_enrichment.csv", index=False)
    n1_holm = int((f1.p_holm < ALPHA).sum()) if len(f1) else 0
    n1_bh = int((f1.q_bh < ALPHA).sum()) if len(f1) else 0
    print(f"Family 1 (layer enrichment): {len(f1)} tests, {n1_holm} Holm-significant, "
          f"{n1_bh} BH-significant")

    f2 = family2_firing_rate_by_class(df)
    f2.to_csv(OUT_DIR / "family2_firing_rate_by_class.csv", index=False)
    n2_holm = int((f2.p_holm < ALPHA).sum()) if len(f2) else 0
    n2_bh = int((f2.q_bh < ALPHA).sum()) if len(f2) else 0
    print(f"Family 2 (firing rate by class): {len(f2)} tests, {n2_holm} Holm-significant, "
          f"{n2_bh} BH-significant")


if __name__ == "__main__":
    main()
