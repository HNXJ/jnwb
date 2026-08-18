r"""
Part 4 of the neuron-type x layer x LFP supplemental analysis (goal-neuron-type-layer-lfp-
relationships-20260815): the broad combinatorial relationship sweep Hamm asked for ("any
interesting relation between any two features ... list them all"), run EXPLICITLY as
hypothesis-generating output, never as a corrected/confirmatory finding -- per the 2026-08-15
multiplicity decision ("pre-register a few families, rest is hypothesis-generating").

Bounded to physically-motivated pairwise relationships (not an unbounded all-pairs blowup):
  1. firing rate x LFP band power, per (class, band), across (session, area, layer) rows
  2. PPC hit-rate x LFP band-onset latency, per (class, band), across area rows -- does an
     earlier band-power divergence onset predict stronger phase locking for that class/band?
  3. layer sup-rate (Part 3 family 1) x firing rate (Part 3 family 2), per class, across
     (animal, area) rows

Every correlation here is Spearman on a small number of non-independent aggregate rows --
per omission-statistics skill ("correlations on few, non-independent aggregate units are
descriptive, not inferential") these are DESCRIPTIVE, reported with r/p/n as information, not
as corrected significance claims. No Holm/BH applied -- that would misrepresent an exploratory
scan as a confirmatory family.

LAYER JOIN NOTE: outputs/lfp_band_census_v2/channel_band_power.csv.gz's own putative_layer
column is 100% null, and outputs/channel_area_vector/channel_area_vector.csv's is too --
neither carries real layer data despite the column existing. The real per-channel layer source
is outputs/layers/channel_layers_all.csv (channel_idx/probe/putative_layer, real sup/mid/deep/na
values), joined here on (session_prefix, probe, channel<->channel_idx).

PHYSICAL PLAUSIBILITY: LFP band-power onset (outputs/classification/lfp_band_onset_latency)
already gates on the >=10ms general floor (0 violations found) -- carried through here, not
re-derived.

Output: outputs/relationship_search/exploratory_sweep_all_pairs.csv,
        outputs/relationship_search/README.md (the non-confirmatory label, in the output itself)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

UNIT_FEATURES = REPO / "outputs/classification/unit_master_features.csv"
BAND_POWER = REPO / "outputs/lfp_band_census_v2/channel_band_power.csv.gz"
CHANNEL_LAYERS = REPO / "outputs/layers/channel_layers_all.csv"
LFP_ONSET_SUMMARY = REPO / "outputs/classification/lfp_band_onset_latency/area_band_summary.csv"
PPC_HIT_RATES = REPO / "outputs/spike_lfp_coupling/class_hit_rates_v2.csv"
FAMILY1 = REPO / "outputs/relationship_search/family1_layer_enrichment.csv"
FAMILY2 = REPO / "outputs/relationship_search/family2_firing_rate_by_class.csv"
OUT_DIR = REPO / "outputs/relationship_search"

CLASSES = ["is_Splus", "is_Splus_double", "is_Sminus", "is_Sminus_double",
          "is_Oplus", "is_Oplus_double", "is_Ominus", "is_Ominus_double"]
BAND_NAME_MAP = {  # channel_band_power.csv.gz's band names -> figstyle-style display names
    "theta": "Theta (4-8 Hz)", "alpha": "Alpha (8-14 Hz)", "beta": "Beta (14-30 Hz)",
    "low_gamma": "Low gamma (30-50 Hz)", "high_gamma": "High gamma (50-80 Hz)",
}
MIN_N_PAIR = 5   # minimum paired (x, y) points to report a descriptive correlation at all


def build_band_power_by_layer():
    """session x area x layer3 x band -> mean db_mid_omirel, joined against the REAL layer
    source (channel_layers_all.csv), not channel_band_power.csv.gz's own null column."""
    bp = pd.read_csv(BAND_POWER).drop(columns=["putative_layer"])
    cl = pd.read_csv(CHANNEL_LAYERS)[["session_prefix", "probe", "channel_idx", "putative_layer"]]
    m = bp.merge(cl, left_on=["session_prefix", "probe", "channel"],
                right_on=["session_prefix", "probe", "channel_idx"], how="inner")
    m["layer3"] = np.where(m.putative_layer == "sup", "sup",
                    np.where(m.putative_layer == "deep", "deep", "Null"))
    m["band"] = m["band"].map(BAND_NAME_MAP)
    g = (m.groupby(["session_prefix", "area", "layer3", "band"])["db_mid_omirel"]
         .mean().reset_index().rename(columns={"session_prefix": "session"}))
    return g


def build_firing_rate_by_layer(feat: pd.DataFrame):
    """session x area10 x layer3 x class -> mean firing_rate, class units only."""
    rows = []
    for cls in CLASSES:
        sub = feat[feat[cls]]
        g = (sub.groupby(["session", "area10", "layer3"])["firing_rate"].mean()
             .reset_index().rename(columns={"area10": "area", "firing_rate": "mean_firing_rate"}))
        g["class"] = cls
        rows.append(g)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def spearman_row(x, y, label, n_family="exploratory_sweep", **meta):
    if len(x) < MIN_N_PAIR:
        return None
    rho, p = stats.spearmanr(x, y)
    return {"relation": label, "n": len(x), "spearman_rho": float(rho), "p": float(p),
           "family": n_family, "confirmatory": False, **meta}


def relation1_firing_rate_vs_band_power(fr_by_layer, bp_by_layer):
    rows = []
    for cls in CLASSES:
        fr = fr_by_layer[fr_by_layer["class"] == cls]
        for band in BAND_NAME_MAP.values():
            bp = bp_by_layer[bp_by_layer.band == band]
            m = fr.merge(bp, on=["session", "area", "layer3"], how="inner")
            r = spearman_row(m.mean_firing_rate, m.db_mid_omirel,
                             f"firing_rate x LFP_band_power ({cls}, {band})",
                             band=band, unit_class=cls)
            if r:
                rows.append(r)
    return rows


def relation2_ppc_vs_onset():
    if not (PPC_HIT_RATES.exists() and LFP_ONSET_SUMMARY.exists()):
        return []
    ppc = pd.read_csv(PPC_HIT_RATES)
    onset = pd.read_csv(LFP_ONSET_SUMMARY)
    ppc_band_map = {"theta": "Theta (4-8 Hz)", "alpha": "Alpha (8-14 Hz)", "beta": "Beta (14-30 Hz)",
                    "low_gamma": "Low gamma (30-50 Hz)", "high_gamma": "High gamma (50-80 Hz)"}
    ppc = ppc.copy()
    ppc["band_display"] = ppc["band"].map(ppc_band_map)
    rows = []
    for cls in CLASSES:
        sub = ppc[(ppc["class"] == cls) & (ppc.context == "omission")]
        m = sub.merge(onset, left_on=["area", "band_display"], right_on=["area", "band"],
                      how="inner", suffixes=("_ppc", "_onset"))
        r = spearman_row(m.hit_rate, m.onset_ms,
                         f"PPC_hit_rate x LFP_band_onset_ms ({cls})", unit_class=cls,
                         note="does an earlier LFP context-divergence onset predict stronger "
                             "class-specific beta/gamma phase locking, during omission")
        if r:
            rows.append(r)
    return rows


def relation3_layer_enrichment_vs_firing_rate():
    if not (FAMILY1.exists() and FAMILY2.exists()):
        return []
    f1 = pd.read_csv(FAMILY1)
    f2 = pd.read_csv(FAMILY2)
    rows = []
    for cls in CLASSES:
        a = f1[f1["class"] == cls][["area", "class_sup_rate"]]
        b = f2[f2["class"] == cls][["area", "median_class_hz"]]
        m = a.merge(b, on="area", how="inner")
        r = spearman_row(m.class_sup_rate, m.median_class_hz,
                         f"layer_sup_rate x median_firing_rate ({cls})", unit_class=cls)
        if r:
            rows.append(r)
    return rows


def main():
    feat = pd.read_csv(UNIT_FEATURES)
    fr_by_layer = build_firing_rate_by_layer(feat)
    bp_by_layer = build_band_power_by_layer()

    rows = []
    rows += relation1_firing_rate_vs_band_power(fr_by_layer, bp_by_layer)
    rows += relation2_ppc_vs_onset()
    rows += relation3_layer_enrichment_vs_firing_rate()

    out = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_DIR / "exploratory_sweep_all_pairs.csv", index=False)

    readme = """# Exploratory relationship sweep -- NOT CORRECTED, NOT CONFIRMATORY

Every row in exploratory_sweep_all_pairs.csv is a descriptive Spearman correlation on a small
number of non-independent aggregate (session x area x layer) or (area) points -- per the
omission-statistics skill, "correlations on few, non-independent aggregate units are
descriptive, not inferential." No Holm/BH multiplicity correction is applied across these rows;
doing so would misrepresent an exploratory scan as a pre-registered confirmatory family.

These are hypothesis-generating candidates for follow-up, cross-referenced against
family1_layer_enrichment.csv / family2_firing_rate_by_class.csv / class_hit_rates_v2.csv (the
actual pre-registered, Holm/BH-corrected confirmatory results) -- nothing here should be quoted
as "significant" on its own.

Physical-plausibility note: the LFP band-power onset values feeding relation 2 already passed
the >=10ms general neural-delay floor check (0/38 area x band cells violated it) before being
used here.
"""
    (OUT_DIR / "README.md").write_text(readme, encoding="utf-8")

    print(f"WROTE {OUT_DIR / 'exploratory_sweep_all_pairs.csv'} ({len(out)} descriptive "
          f"correlations, all labeled non-confirmatory)")
    if len(out):
        top = out.reindex(out.spearman_rho.abs().sort_values(ascending=False).index).head(15)
        print(top[["relation", "n", "spearman_rho", "p"]].to_string(index=False))


if __name__ == "__main__":
    main()
