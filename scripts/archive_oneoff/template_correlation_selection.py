"""
Template-correlation neuron selection for Figure 3 (S+/S-/O+ exemplars).

Alternative to the pooled shuffle-test classifier (jnwb.unit_classification.is_o_plus etc.):
for each real unit, compute its real per-epoch mean firing rate (spikes/s, duration-normalized
so the p531ms stim epochs and the differently-sized delay epochs are weighted fairly) averaged
across real trials, then Pearson-correlate that 9-element vector against an idealized 0/1
"pulse" template over the real epoch sequence (fx, p1, d1, p2, d2, p3, d3, p4, d4):

  S+ template (RRRR): 0-1-0-1-0-1-0-1-0   (fires WITH each real stimulus presentation)
  S- template (RRRR): 1-0-1-0-1-0-1-0-1   (fires BETWEEN real stimulus presentations)
  O+ template (per omission condition): all-zero except a 1 at the real omitted slot's
    position (e.g. RXRR -> 1 at p2; RRXR -> 1 at p3; RRRX -> 1 at p4) - fires specifically
    during the real missing-stimulus window.

Significance: a real permutation test per unit (5000 draws) - shuffle which epoch each
observed per-epoch rate is assigned to, recompute r, and take p = fraction of |r_perm| >=
|r_obs|. This does not assume Gaussian asymptotics on a 9-sample vector.

Usage:
    python scripts/template_correlation_selection.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import jnwb as oa
from jnwb.sequence_layout import EPOCH_ONSETS_MS

NWB_PATH = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"
SESSION_PREFIX = "sub-C31o_ses-230823_rec"
CONDITIONS = ["RRRR", "RXRR", "RRXR", "RRRX"]
MIN_TRIALS = 40
MIN_MEAN_RATE_HZ = 1.0
N_PERM = 5000
RNG_SEED = 42

EPOCH_NAMES = list(EPOCH_ONSETS_MS.keys())  # fx, p1, d1, p2, d2, p3, d3, p4, d4
EPOCH_ENDS_MS = list(EPOCH_ONSETS_MS.values())[1:] + [4124.0]  # each epoch's stop = next onset

S_PLUS_TEMPLATE = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0], dtype=float)
S_MINUS_TEMPLATE = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1], dtype=float)
OMIT_SLOT_TO_EPOCH = {"RXRR": "p2", "RRXR": "p3", "RRRX": "p4"}


def omission_template(cond: str) -> np.ndarray:
    t = np.zeros(len(EPOCH_NAMES))
    t[EPOCH_NAMES.index(OMIT_SLOT_TO_EPOCH[cond])] = 1.0
    return t


def per_epoch_rate_vector(spike_times: np.ndarray, onsets: np.ndarray) -> np.ndarray:
    """Real duration-normalized mean firing rate (Hz) per epoch, averaged across trials."""
    rates = np.zeros((len(onsets), len(EPOCH_NAMES)))
    for ti, onset in enumerate(onsets):
        for ei, (name, t0) in enumerate(EPOCH_ONSETS_MS.items()):
            t1 = EPOCH_ENDS_MS[ei]
            lo, hi = onset + t0 / 1000.0, onset + t1 / 1000.0
            n_spk = np.sum((spike_times >= lo) & (spike_times < hi))
            rates[ti, ei] = n_spk / ((t1 - t0) / 1000.0)
    return rates.mean(axis=0)


def perm_test_corr(vec: np.ndarray, template: np.ndarray, n_perm: int, rng: np.random.Generator):
    if vec.std() == 0 or template.std() == 0:
        return 0.0, 1.0
    r_obs = np.corrcoef(vec, template)[0, 1]
    n_ge = 0
    for _ in range(n_perm):
        perm = rng.permutation(vec)
        r_perm = np.corrcoef(perm, template)[0, 1]
        if abs(r_perm) >= abs(r_obs):
            n_ge += 1
    p = (n_ge + 1) / (n_perm + 1)
    return r_obs, p


def main():
    rng = np.random.default_rng(RNG_SEED)
    sess = oa.read(NWB_PATH)
    grand = pd.read_csv("outputs/classification/grand_unit_table_shuffle_sso.csv")
    sub = grand[grand["nwb_stem"] == SESSION_PREFIX]

    onsets_by_cond = {}
    for cond in CONDITIONS:
        epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
        onsets_by_cond[cond] = epochs["start_time"].values

    results = []
    for _, row in sub.iterrows():
        uid = int(row["unit_id"])
        spike_times = sess.get_spike_times(uid)
        if spike_times is None or len(spike_times) == 0:
            continue

        cond_ok = True
        cond_vecs = {}
        for cond in CONDITIONS:
            onsets = onsets_by_cond[cond]
            if len(onsets) < MIN_TRIALS:
                cond_ok = False
                break
            vec = per_epoch_rate_vector(spike_times, onsets[:MIN_TRIALS])
            if vec.mean() < MIN_MEAN_RATE_HZ:
                cond_ok = False
                break
            cond_vecs[cond] = vec
        if not cond_ok:
            continue

        r_splus, p_splus = perm_test_corr(cond_vecs["RRRR"], S_PLUS_TEMPLATE, N_PERM, rng)
        r_sminus, p_sminus = perm_test_corr(cond_vecs["RRRR"], S_MINUS_TEMPLATE, N_PERM, rng)

        o_r, o_p = {}, {}
        for cond in ("RXRR", "RRXR", "RRRX"):
            r, p = perm_test_corr(cond_vecs[cond], omission_template(cond), N_PERM, rng)
            o_r[cond], o_p[cond] = r, p

        results.append({
            "unit_id": uid, "prior_display_class": row["display_class"],
            "r_Splus": r_splus, "p_Splus": p_splus,
            "r_Sminus": r_sminus, "p_Sminus": p_sminus,
            "r_Oplus_RXRR": o_r["RXRR"], "p_Oplus_RXRR": o_p["RXRR"],
            "r_Oplus_RRXR": o_r["RRXR"], "p_Oplus_RRXR": o_p["RRXR"],
            "r_Oplus_RRRX": o_r["RRRX"], "p_Oplus_RRRX": o_p["RRRX"],
            "r_Oplus_mean": np.mean([o_r["RXRR"], o_r["RRXR"], o_r["RRRX"]]),
            "Oplus_all_sig": all(o_p[c] < 0.05 for c in ("RXRR", "RRXR", "RRRX")),
        })

    df = pd.DataFrame(results)
    df.to_csv("outputs/classification/figure3_template_correlation_scan.csv", index=False)
    print(f"Scanned {len(df)} real qualifying units (>= {MIN_TRIALS} trials/cond, "
          f">= {MIN_MEAN_RATE_HZ} Hz all conds) in {SESSION_PREFIX}\n")

    print("=== Top 5 by r_Splus (p<0.05 only) ===")
    print(df[df["p_Splus"] < 0.05].sort_values("r_Splus", ascending=False)
          [["unit_id", "prior_display_class", "r_Splus", "p_Splus"]].head(5).to_string(index=False))

    print("\n=== Top 5 by r_Sminus (p<0.05 only) ===")
    print(df[df["p_Sminus"] < 0.05].sort_values("r_Sminus", ascending=False)
          [["unit_id", "prior_display_class", "r_Sminus", "p_Sminus"]].head(5).to_string(index=False))

    print("\n=== Top 5 by r_Oplus_mean, significant (p<0.05) in ALL 3 omission conditions ===")
    print(df[df["Oplus_all_sig"]].sort_values("r_Oplus_mean", ascending=False)
          [["unit_id", "prior_display_class", "r_Oplus_RXRR", "r_Oplus_RRXR", "r_Oplus_RRRX", "r_Oplus_mean"]]
          .head(5).to_string(index=False))


if __name__ == "__main__":
    main()
