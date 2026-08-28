#!/usr/bin/env python3
"""Matched context-vs-content contrast for F04.

Scientific question:
  Is omission *context* (predictable/structured stream vs random stream, X|Structured
  vs X|R) more decodable from population spiking than omission *content* (expected
  identity, X|A vs X|B) -- on the same session x area x slot cells, same feature
  extraction, same CV scheme, same permutation-null correction?

This is the direct test Hamm asked for: not "context significant + content
nonsignificant implies context > content" (an inference fallacy), but an explicit
paired difference test on D_c = P_context,c - P_content,c.

Content target (X|A vs X|B) is only defined within the structured/predictable subset
of omission trials -- an X|R (random) omission has no expected identity to decode.
Feature extraction, CV fold count, and permutation-null construction are copied
verbatim from compute_predictable_vs_random_omission_decoding.py so that P_context and
P_content are computed identically apart from the label they predict.

Outputs:
  - outputs/classification/context_vs_content_content_results.csv (new content-only decoding)
  - outputs/classification/context_vs_content_matched_contrast.csv (D_c per matched cell)
  - outputs/classification/context_vs_content_contrast_receipt.json (paired test, session-clustered)
  - outputs/classification/context_vs_content_scatter.png (P_content vs P_context, y=x line)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

os.environ.setdefault("OMISSION_NWB_DIR", "D:/nwb/omission")

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
REPO_ROOT = OA_ROOT.parent

sys.path.insert(0, str(OA_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from omission.jnwb_ext.trial_ontology import build_trial_ontology
from compute_predictable_vs_random_omission_decoding import (
    SLOT_ONSETS_MS,
    SLOT_DUR_MS,
    extract_spk_features,
)

OUT_DIR = OA_ROOT / "outputs" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_PERM = 999


def evaluate_cv_direct(X: np.ndarray, y: np.ndarray, cv_splits, seed: int = 42):
    oof_preds = np.zeros(len(y), dtype=float)
    for fold, (train_idx, test_idx) in enumerate(cv_splits):
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(np.log1p(np.maximum(0, X[train_idx])))
        X_te = scaler.transform(np.log1p(np.maximum(0, X[test_idx])))
        clf = LogisticRegression(C=1.0, max_iter=1000, random_state=seed + fold)
        clf.fit(X_tr, y[train_idx])
        oof_preds[test_idx] = clf.predict(X_te)
    return float(balanced_accuracy_score(y, oof_preds))


def main():
    t0 = time.time()
    nwb_files = sorted(list(Path("D:/nwb/omission").glob("*.nwb")))
    rep_sessions = ["sub-C31o_ses-230816", "sub-C31o_ses-230823", "sub-V182o_ses-260710", "sub-V198o_ses-230719"]
    target_files = [p for p in nwb_files if any(s in p.name for s in rep_sessions)]

    print(f"Computing content (X|A vs X|B) decoding on {len(target_files)} sessions, matched to context grid...")

    content_results = []
    for nwb_path in target_files:
        sess_name = nwb_path.stem.replace("_rec", "")
        subj = sess_name.split("_")[0].replace("sub-", "")
        session = oa.read(nwb_path)
        onto = build_trial_ontology(session, slot_keys=("p2", "p3", "p4"), families=("A", "B", "R"))
        onto_corr = onto[onto["correct_trial"]].copy().reset_index(drop=True)
        df_pred = onto_corr[onto_corr["sequence_family"].isin(["A", "B"])].copy()

        for slot in ["p2", "p3", "p4", "ALL_SLOTS"]:
            sub = df_pred if slot == "ALL_SLOTS" else df_pred[df_pred["slot_key"] == slot].copy()
            n_a = int((sub["sequence_family"] == "A").sum())
            n_b = int((sub["sequence_family"] == "B").sum())
            if n_a < 6 or n_b < 6:
                continue

            for area in ["V1", "MT", "ALL"]:
                u_test = session.get_units(area=area) if area != "ALL" else session.get_units()
                if len(u_test) < 4:
                    continue
                X_spk = extract_spk_features(session, area, sub, n_bins=10)
                if X_spk.shape[1] < 4:
                    continue

                y = (sub["sequence_family"] == "A").to_numpy().astype(int)
                skf = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
                cv_splits = list(skf.split(X_spk, y))

                acc_obs = evaluate_cv_direct(X_spk, y, cv_splits)

                rng = np.random.default_rng(42)
                p_nulls = []
                for _ in range(N_PERM):
                    y_p = rng.permutation(y)
                    p_nulls.append(evaluate_cv_direct(X_spk, y_p, cv_splits))
                p_perm = float((1 + np.sum(np.array(p_nulls) >= acc_obs)) / (N_PERM + 1))

                content_results.append({
                    "session": sess_name, "subject": subj, "area": area, "slot": slot,
                    "n_A": n_a, "n_B": n_b,
                    "content_acc": acc_obs, "content_p_perm": p_perm,
                })

    df_content = pd.DataFrame(content_results)
    df_content.to_csv(OUT_DIR / "context_vs_content_content_results.csv", index=False)
    print(f"\nContent decoding: {len(df_content)} session x area x slot cells")
    print(df_content.to_string(index=False))

    # Load context results -- must already be the corrected (999-perm, +1-correction) rerun.
    context_path = OUT_DIR / "predictable_vs_random_omission_results.csv"
    df_context = pd.read_csv(context_path)
    df_context = df_context.rename(columns={"spk_direct_acc": "context_acc", "p_perm": "context_p_perm"})

    matched = pd.merge(
        df_context[["session", "subject", "area", "slot", "context_acc", "context_p_perm", "n_predictable", "n_random"]],
        df_content[["session", "subject", "area", "slot", "content_acc", "content_p_perm", "n_A", "n_B"]],
        on=["session", "subject", "area", "slot"], how="inner",
    )
    matched["D_c"] = matched["context_acc"] - matched["content_acc"]
    matched.to_csv(OUT_DIR / "context_vs_content_matched_contrast.csv", index=False)
    print(f"\nMatched cells: {len(matched)} (of {len(df_context)} context, {len(df_content)} content)")
    print(matched[["session", "area", "slot", "context_acc", "content_acc", "D_c"]].to_string(index=False))

    # Session-clustered one-sample test: D_c ~ 1, cluster-robust SE by session.
    m = smf.ols("D_c ~ 1", data=matched).fit(cov_type="cluster", cov_kwds={"groups": matched["session"]})
    beta0 = float(m.params["Intercept"])
    p0 = float(m.pvalues["Intercept"])
    ci_lo, ci_hi = [float(v) for v in m.conf_int().loc["Intercept"]]

    # Session-level means, for an honest small-N summary (N_session clusters only).
    session_means = matched.groupby("session")["D_c"].mean()

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "H0: E[P_context - P_content] = 0  vs  H1: E[P_context - P_content] > 0",
        "method": "OLS D_c ~ 1 on matched session x area x slot cells, cluster-robust SE by session (session is the true biological replication unit; areas/slots within a session are not independent).",
        "why_this_is_matched": "content_acc and context_acc use identical feature extraction (extract_spk_features, n_bins=10), identical 4-fold StratifiedKFold CV construction, identical N_PERM=999 permutation null with the (1+k)/(N+1) finite-sample correction. Both are balanced_accuracy_score (chance=0.5 regardless of class imbalance) so raw accuracy differencing is valid without extra chance-adjustment, per the binary-balanced-task case.",
        "n_matched_cells": int(len(matched)),
        "n_sessions": int(matched["session"].nunique()),
        "n_subjects": int(matched["subject"].nunique()),
        "mean_D": beta0,
        "median_D": float(matched["D_c"].median()),
        "ci95_cluster_robust": [ci_lo, ci_hi],
        "p_one_sided_gt0": p0 / 2 if beta0 > 0 else 1 - p0 / 2,
        "p_two_sided": p0,
        "prop_cells_D_positive": float((matched["D_c"] > 0).mean()),
        "session_level_mean_D": session_means.round(4).to_dict(),
        "caveat_small_n": f"Only {matched['session'].nunique()} session clusters -- cluster-robust SE is a large-sample approximation and is only indicative at this N. Session-level means are reported directly above so this isn't hidden behind a single p-value.",
        "runtime_seconds": round(time.time() - t0, 2),
    }
    with open(OUT_DIR / "context_vs_content_contrast_receipt.json", "w") as f:
        json.dump(receipt, f, indent=2)
    print("\n=== Context vs Content matched contrast ===")
    print(json.dumps(receipt, indent=2))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 5))
    for area, sub in matched.groupby("area"):
        ax.scatter(sub["content_acc"], sub["context_acc"], label=area, s=40, alpha=0.8, edgecolor="black", lw=0.5)
    lims = [0.4, 0.85]
    ax.plot(lims, lims, "k--", lw=1, label="y = x")
    ax.axvline(0.5, color="gray", ls=":", lw=0.8)
    ax.axhline(0.5, color="gray", ls=":", lw=0.8)
    ax.set_xlim(lims); ax.set_ylim(lims)
    ax.set_xlabel("Content decoding accuracy (X|A vs X|B)")
    ax.set_ylabel("Context decoding accuracy (X|Structured vs X|R)")
    ax.set_title(f"Context vs content, matched cells (n={len(matched)})\nmean D={beta0:.3f}, p={p0:.4f} (cluster-robust)")
    ax.legend(fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "context_vs_content_scatter.png", dpi=200)
    plt.close(fig)
    print(f"\nSaved scatter to {OUT_DIR / 'context_vs_content_scatter.png'}")


if __name__ == "__main__":
    main()
