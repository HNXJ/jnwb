r"""
Group-level statistics for the LFP-LFP transfer-entropy network -- aggregates
outputs/lfp_lfp_te_network/edges.csv (written by scripts/compute_lfp_lfp_te_network.py) using
the SAME session-level aggregation and three-family design as
supp_lfp_lfp_granger.py's Granger network, so the two methods' results are directly
comparable. Not folded into supp_lfp_lfp_granger.py itself because the TE edge computation is
a separate, much longer-running job (see that script's docstring) -- this is the fast
aggregation-and-stats step, run once the edges are already on disk.

NOTE 2026-08-05: this folder was renamed from fig05_lfp_lfp_coupling/ to
lfp_lfp_connectivity_supplement/ when fig05's actual headline pivoted to the area x band GLMM
(all three LFP-LFP connectivity methods -- coherency, Granger, TE -- came back null; see
context/figures/fig05_v1_area_hierarchy_glmm/README.md for the current figure 5).

OUTPUT
    outputs/lfp_lfp_te_network/net_directionality.csv
    context/figures/lfp_lfp_connectivity_supplement/svg/supp_te_stats.md / .csv
"""
from __future__ import annotations

import os
import sys

import pandas as pd

REPO = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(REPO)
FIG05_DIR = os.path.join(REPO, "context", "figures", "lfp_lfp_connectivity_supplement")
sys.path.insert(0, os.path.join(REPO, "context", "figures"))
sys.path.insert(0, FIG05_DIR)
import supp_lfp_lfp_granger as f5  # noqa: E402
from figstyle import AREA_ORDER  # noqa: E402
from figstats import correct, write  # noqa: E402

EDGES_CSV = os.path.join(REPO, "outputs", "lfp_lfp_te_network", "edges.csv")
NET_OUT = os.path.join(REPO, "outputs", "lfp_lfp_te_network", "net_directionality.csv")
SVG_DIR = os.path.join(FIG05_DIR, "svg")


def main():
    edges_df = pd.read_csv(EDGES_CSV)
    net_df = f5.net_directionality(edges_df)
    net_df.to_csv(NET_OUT, index=False)
    areas = [a for a in AREA_ORDER if a in set(net_df.areaA) | set(net_df.areaB)]
    print(f"areas present: {areas}")
    print(f"sessions present: {edges_df.session.nunique()}")

    within = f5.within_condition_stats(net_df, areas)
    delta = f5.delta_stats(net_df, areas)
    all_stats = within["RXRR"] + within["RRRR"] + delta
    for r in all_stats:
        r.figure = "fig05_supp"
        r.family = "fig05_supp_te_" + r.family.replace("fig05_", "")

    corrected = correct(list(all_stats))
    os.makedirs(SVG_DIR, exist_ok=True)
    write(all_stats, SVG_DIR, "supp_te",
         title="Figure 5 supplement -- TE robustness check, directed LFP-LFP connectivity "
               "(transfer entropy)",
         preamble="Transfer entropy (n_surrogates=15, bias-corrected -- see "
                  "scripts/compute_lfp_lfp_te_network.py's docstring for the runtime/validity "
                  "tradeoff this required). Same three-family design, same session-as-unit-of-"
                  "inference convention as the Granger network in fig05_lfp_lfp_coupling.py.")

    n_sig = {fam: sum(1 for r in corrected if r.family == f"fig05_te_{fam}"
                      and r.p_holm is not None and r.p_holm < 0.05)
            for fam in ("RXRR", "RRRR")}
    n_sig["delta"] = sum(1 for r in corrected if r.family == "fig05_te_delta"
                         and r.p_holm is not None and r.p_holm < 0.05)
    print(f"significant (p_holm<0.05): {n_sig}")
    print(f"WROTE {NET_OUT}, {SVG_DIR}/supp_te_stats.md/.csv")


if __name__ == "__main__":
    main()
