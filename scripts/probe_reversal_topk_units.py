"""
Follow-up probe for the FEF / V3a-d reversal-generalization result (decode_identity_sliding_window.py
analysis="reversal_generalization"): does restricting the population to a subset of units improve
decodability, and which units carry the effect?

Two things, FEF and V3a/d only (the only two areas that passed the group-level cluster test),
using the SAME sessions/instances/window/bin/fold/C-selection/permutation-null machinery as the
main decode -- only the feature set changes:

1. Per-unit contribution ranking. At the bin nearest each area's reported significant cluster,
   average the REAL (non-permuted) fold-fit ridge coefficient magnitude (on standardized features,
   so units are on a common scale) across folds and sessions. This is descriptive, not a repeated
   test -- it answers "which units carry the effect" for a result that was already found
   significant at the population level, not a new significance claim.

2. Top-K unit-subset re-decode. For k_frac in {1.0, 0.75, 0.5, 0.25, 0.1}, at EACH outer fold,
   rank units by |Pearson r| between that fold's TRAINING window-mean rate and the training
   label only (never using test-fold data -- this is nested inside the same CV the main decode
   already uses, the same principle as _select_c's C-grid search), keep the top ceil(k_frac*n)
   units, and rerun the exact same per-bin primal-ridge decode restricted to that fold-specific
   unit subset. Reports whether restricting the population improves peak signed-decodability or
   cluster mass relative to k_frac=1.0 (the original, already-reported result).

N_PERMUTATIONS reduced to 200 here (vs 500 in the main decode) -- this is an exploratory
follow-up probe across 5 k_fracs x ~15 (session, area) cells, not a claim-bearing headline; stated
explicitly rather than silently under-powering the same nominal test.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from jnwb.permutation import permute_labels
from jnwb.structured_identity_m2a import build_outer_folds, _select_c, C_GRID
import scripts.decode_identity_sliding_window as dw

OUT_DIR = REPO_ROOT / "outputs/classification/identity_reversal_topk_probe"
CONTRIB_CSV = OUT_DIR / "unit_contributions.csv"
TOPK_CSV = OUT_DIR / "topk_results.csv"

TARGET_AREAS = ("FEF", "V3a/d")
AREA_MERGE = {"MST": "MST+FST", "FST": "MST+FST", "V3a": "V3a/d", "V3d": "V3a/d"}
K_FRACS = (1.0, 0.75, 0.5, 0.25, 0.1)
N_PERMUTATIONS = 200
SEED = 91000
CLUSTER_BIN_MS = {"FEF": 112.5, "V3a/d": 175.0}  # centers of the reported significant clusters


def _topk_mask(X_mean: np.ndarray, labels: np.ndarray, train_idx: np.ndarray, k_frac: float) -> np.ndarray:
    n_units = X_mean.shape[1]
    if k_frac >= 1.0:
        return np.ones(n_units, dtype=bool)
    Xt = X_mean[train_idx]
    yt = labels[train_idx].astype(float)
    yt_c = yt - yt.mean()
    Xt_c = Xt - Xt.mean(axis=0, keepdims=True)
    num = Xt_c.T @ yt_c
    den = np.sqrt((Xt_c ** 2).sum(axis=0) * (yt_c ** 2).sum())
    r = np.divide(num, den, out=np.zeros(n_units), where=den > 0)
    k = max(1, int(np.ceil(k_frac * n_units)))
    keep = np.argsort(-np.abs(r))[:k]
    mask = np.zeros(n_units, dtype=bool)
    mask[keep] = True
    return mask


def decode_topk(X, labels, groups, seed, k_frac, train_mask=None, test_mask=None, want_coeffs_bin=None):
    """Same structure as decode_identity_sliding_window.decode_cell_signed, plus nested per-fold
    top-K unit restriction and (optionally) real-fit coefficient extraction at one bin."""
    n, n_units, n_bins = X.shape
    folds = build_outer_folds(groups, labels, train_mask=train_mask, test_mask=test_mask, min_train_groups=2)
    if len(folds) < 2:
        return None

    X_mean = X.mean(axis=2)
    selected_C = {}
    fold_unit_mask = {}
    for fs in folds:
        mask = _topk_mask(X_mean, labels, fs.train_idx, k_frac)
        fold_unit_mask[fs.fold] = mask
        Xm_sub = X_mean[:, mask]
        try:
            C, _, n_inner = _select_c(
                Xm_sub, labels, groups, fs.train_idx, fs.inner_groups, seed=seed + fs.fold * 1000, c_grid=C_GRID
            )
        except ValueError:
            return None
        if n_inner == 0:
            return None
        selected_C[fs.fold] = C

    rng = np.random.default_rng(seed + 777)
    perm_labels = np.stack(
        [permute_labels(labels, groups=groups, scheme="within_group", rng=rng) for _ in range(N_PERMUTATIONS)],
        axis=1,
    )
    mask1_p = perm_labels == 1
    mask0_p = perm_labels == 0

    obs_a = np.full(n_bins, np.nan)
    obs_b = np.full(n_bins, np.nan)
    null_a = np.full((N_PERMUTATIONS, n_bins), np.nan)
    null_b = np.full((N_PERMUTATIONS, n_bins), np.nan)
    coeff_records = []  # (fold, unit_indices, |coeff|) at want_coeffs_bin only

    for b in range(n_bins):
        Xb = X[:, :, b]
        real_sign = np.full(n, np.nan)
        perm_sign = np.full((n, N_PERMUTATIONS), np.nan)
        for fs in folds:
            unit_mask = fold_unit_mask[fs.fold]
            unit_idx = np.flatnonzero(unit_mask)
            train_idx, test_idx = fs.train_idx, fs.test_idx
            X_train = Xb[train_idx][:, unit_mask]
            mean = X_train.mean(axis=0)
            scale = X_train.std(axis=0)
            scale[scale == 0.0] = 1.0
            Xtr = (X_train - mean) / scale
            Xte = (Xb[test_idx][:, unit_mask] - mean) / scale

            train_base = labels[train_idx]
            counts = np.bincount(train_base, minlength=2).astype(float)
            weights = np.sqrt(len(train_base) / (2.0 * counts[train_base]))
            weighted_train = Xtr * weights[:, None]

            A = weighted_train.T @ weighted_train
            A.flat[:: len(A) + 1] += 1.0 / float(selected_C[fs.fold])

            y_real = 2.0 * labels[train_idx] - 1.0
            y_perm = 2.0 * perm_labels[train_idx][:, :] - 1.0
            rhs_y = np.concatenate([y_real[:, None], y_perm], axis=1) * weights[:, None]
            rhs = weighted_train.T @ rhs_y
            coeffs = np.linalg.solve(A, rhs)
            scores = Xte @ coeffs
            sgn = np.sign(scores)
            sgn[sgn == 0.0] = 1.0
            real_sign[test_idx] = sgn[:, 0]
            perm_sign[test_idx] = sgn[:, 1:]

            if want_coeffs_bin is not None and b == want_coeffs_bin:
                coeff_records.append((unit_idx, np.abs(coeffs[:, 0])))

        cov = ~np.isnan(real_sign)
        m1, m0 = labels == 1, labels == 0
        if (cov & m1).any():
            obs_a[b] = np.nanmean(real_sign[cov & m1])
        if (cov & m0).any():
            obs_b[b] = np.nanmean(real_sign[cov & m0])

        covp = ~np.isnan(perm_sign[:, 0])
        sel1 = mask1_p & covp[:, None]
        sel0 = mask0_p & covp[:, None]
        cnt1 = sel1.sum(axis=0)
        cnt0 = sel0.sum(axis=0)
        sum1 = np.where(sel1, perm_sign, 0.0).sum(axis=0)
        sum0 = np.where(sel0, perm_sign, 0.0).sum(axis=0)
        null_a[:, b] = np.divide(sum1, cnt1, out=np.full(N_PERMUTATIONS, np.nan), where=cnt1 > 0)
        null_b[:, b] = np.divide(sum0, cnt0, out=np.full(N_PERMUTATIONS, np.nan), where=cnt0 > 0)

    return obs_a, obs_b, null_a, null_b, len(folds), coeff_records


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    readiness = pd.read_csv(dw.READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()
    _, ctr = dw._edges()

    topk_rows = []
    contrib_rows = []
    t0 = time.time()

    for _, row in ready.iterrows():
        prefix = row["session_prefix"]
        try:
            sess = dw.load_session(prefix)
        except Exception as e:
            print(f"[{prefix}] load failed: {e}")
            continue
        tables = dw.build_instance_tables(sess)
        if "reversal_generalization" not in tables:
            continue
        inst = tables["reversal_generalization"]
        labels = inst["label"].to_numpy()
        groups = inst["group"].to_numpy()
        test_mask = inst["is_test"].to_numpy()
        train_mask = ~test_mask
        if min(len(np.unique(groups[train_mask])), len(np.unique(groups[test_mask]))) < dw.MIN_GROUPS_WITH_BOTH_CLASSES:
            continue
        onsets_s = inst["onset_s"].to_numpy()
        session_areas = sorted(sess.get_units()["area"].dropna().unique().tolist())
        for raw_area in session_areas:
            area_m = AREA_MERGE.get(raw_area, raw_area)
            if area_m not in TARGET_AREAS:
                continue
            try:
                X, row_indices = dw.build_raster_from_onsets(sess, raw_area, onsets_s, dw.BIN_MS, dw.WIN_MS)
                if X is None:
                    continue
                want_bin = int(np.argmin(np.abs(ctr - CLUSTER_BIN_MS[area_m])))
                for k_frac in K_FRACS:
                    result = decode_topk(
                        X, labels, groups, seed=SEED, k_frac=k_frac,
                        train_mask=train_mask, test_mask=test_mask,
                        want_coeffs_bin=want_bin if k_frac == 1.0 else None,
                    )
                    if result is None:
                        continue
                    obs_a, obs_b, null_a, null_b, n_folds, coeff_records = result
                    peak_a = float(np.nanmax(obs_a))
                    thr_a = float(np.nanpercentile(null_a, 95, axis=0)[want_bin])
                    topk_rows.append({
                        "session": prefix, "area": area_m, "raw_area": raw_area, "k_frac": k_frac,
                        "n_units_total": len(row_indices), "n_folds": n_folds,
                        "peak_A": peak_a, "trough_B": float(np.nanmin(obs_b)),
                        "val_at_cluster_bin_A": float(obs_a[want_bin]),
                        "null95_at_cluster_bin_A": thr_a,
                        "above_null95_at_cluster_bin": bool(obs_a[want_bin] > thr_a),
                    })
                    if coeff_records:
                        agg = {}
                        for unit_idx, absc in coeff_records:
                            for ui, c in zip(unit_idx, absc):
                                agg.setdefault(int(ui), []).append(float(c))
                        for ui, vals in agg.items():
                            contrib_rows.append({
                                "session": prefix, "area": area_m, "raw_area": raw_area,
                                "unit_row": row_indices[ui], "mean_abs_coeff": float(np.mean(vals)),
                                "n_folds_covering": len(vals),
                            })
                print(f"[{prefix}/{raw_area}] done, elapsed={time.time()-t0:.0f}s")
                pd.DataFrame(topk_rows).to_csv(TOPK_CSV, index=False)
                if contrib_rows:
                    pd.DataFrame(contrib_rows).to_csv(CONTRIB_CSV, index=False)
            except Exception:
                print(f"[{prefix}/{raw_area}] FAILED:\n{traceback.format_exc()}")
                continue

    print("DONE.", len(topk_rows), "topk rows,", len(contrib_rows), "contribution rows")


if __name__ == "__main__":
    main()
