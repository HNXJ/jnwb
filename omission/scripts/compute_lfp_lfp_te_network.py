r"""
Directed LFP-LFP connectivity via transfer entropy (TE) -- third method attempted for fig05's
main-figure slot, after undirected imaginary coherency (0/240 significant) and directed Granger
causality (0/150 significant) both came back null at the group level on this corpus.

WHY A SEPARATE SCRIPT, NOT A --method FLAG ON fig05_lfp_lfp_coupling.py
    TE at a defensible surrogate count is computationally incompatible with an interactive
    session (see runtime note below) -- this runs as a long, separately-launched background
    job, checkpointing after every session exactly like fig05_lfp_lfp_coupling.py's
    compute_edges() does, so it can be safely left running across turns / restarted from a
    partial edges.csv without recomputing finished sessions.

RUNTIME / SURROGATE COUNT TRADEOFF (stated plainly, not discovered after the fact)
    omission.jnwb_ext.connectivity.transfer_entropy()'s default n_surrogates=200 makes a single (session,
    band, condition) 10-area call impractically slow (>2 min for a 5-area subset alone).
    n_surrogates=15 here is a deliberate compromise: fast enough to finish the full grid in
    single-digit hours, not so low that the bias correction (raw TE minus surrogate mean) is
    pure noise. This is a real statistical cost -- fewer surrogates means a noisier per-session
    point estimate feeding the group-level test -- disclosed here, not silently chosen.

INPUT / METHOD / STATISTICS -- identical design to fig05_lfp_lfp_coupling.py's Granger network,
    swapping method='granger' for method='te'. See that script's own docstring for the full
    rationale (per-trial band power, full trial window, session as unit of inference, three
    families fig05_te_RXRR/fig05_te_RRRR/fig05_te_delta).

OUTPUT
    outputs/lfp_lfp_te_network/edges.csv       checkpointed after every session
    outputs/lfp_lfp_te_network/receipt.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(REPO)
sys.path.insert(0, os.path.join(REPO, "context", "figures"))
sys.path.insert(0, REPO)
from figstyle import AREA_ORDER  # noqa: E402
from omission.jnwb_ext.connectivity import directed_network  # noqa: E402

TRIALS_NPZ = os.path.join(REPO, "outputs", "condition_band_power_trials", "trials.npz")
OUT_DIR = os.path.join(REPO, "outputs", "lfp_lfp_te_network")
CONDS = ["RXRR", "RRRR"]
BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
N_SURROGATES = 15
MIN_AREAS_PER_CALL = 3


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    edges_path = os.path.join(OUT_DIR, "edges.csv")
    done = set()
    rows = []
    if os.path.exists(edges_path):
        prev = pd.read_csv(edges_path)
        rows = prev.to_dict("records")
        done = set(zip(prev.session, prev.cond, prev.band))
        print(f"resuming: {len(done)} (session,cond,band) combos already done", flush=True)

    d = np.load(TRIALS_NPZ)
    keys = set(k for k in d.files if k != "times")
    sessions = sorted({k.split("|")[0] for k in keys})
    t0 = time.time()

    for si, session in enumerate(sessions, 1):
        for cond in CONDS:
            for band in BANDS:
                if (session, cond, band) in done:
                    continue
                areas = [a for a in AREA_ORDER
                        if f"{session}|{a}|{cond}|{band}" in keys]
                if len(areas) < MIN_AREAS_PER_CALL:
                    continue
                signals = {a: d[f"{session}|{a}|{cond}|{band}"] for a in areas}
                n_tr = {a: v.shape[0] for a, v in signals.items()}
                try:
                    res = directed_network(signals, method="te", fdr=False,
                                          n_surrogates=N_SURROGATES)
                except Exception as e:
                    rows.append({"session": session, "cond": cond, "band": band,
                                "areaA": None, "areaB": None, "error": str(e)})
                    continue
                mat, pmat, labels = res["matrix"], res["p_matrix"], res["labels"]
                for i, a in enumerate(labels):
                    for j, b in enumerate(labels):
                        if i == j:
                            continue
                        rows.append({
                            "session": session, "cond": cond, "band": band,
                            "areaA": a, "areaB": b,
                            "x_to_y": float(mat[i, j]), "p_x_to_y": float(pmat[i, j]),
                            "n_trials_A": n_tr[a], "n_trials_B": n_tr[b],
                            "n_warnings": len(res.get("warnings", [])),
                            "error": None,
                        })
        pd.DataFrame(rows).to_csv(edges_path, index=False)
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{len(rows)} edge rows so far, {time.time()-t0:.0f}s", flush=True)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "source": TRIALS_NPZ,
        "conditions": CONDS, "bands": BANDS, "n_surrogates": N_SURROGATES,
        "n_sessions": len(sessions), "runtime_s": round(time.time() - t0, 1),
        "note": "n_surrogates=15 is a deliberate runtime/validity compromise -- see module "
               "docstring. Do not report a single edge's raw p-value; the group-level test in "
               "fig05_lfp_lfp_coupling.py (or its TE variant) is what matters.",
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {edges_path} ({len(rows)} rows), receipt.json")


if __name__ == "__main__":
    main()
