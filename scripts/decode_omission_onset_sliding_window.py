"""
Population sliding-window decoder for omission ONSET latency -- location- and identity-agnostic.

Question: at what time (relative to a slot's onset) does population spiking first let a linear
decoder tell "this slot was omitted" apart from "this slot had a real stimulus," pooling across
slot position (p2, p3, p4) and stimulus identity (A, B)? This is deliberately NOT the identity
decode (jnwb/structured_identity_m2a.py, A vs B) -- it is a binary detection question, and the
two "present" instances are drawn from the SAME single-omission trial as the omitted instance
(RXRR's own p3/p4, not a different condition's trials), so the comparison is matched within-trial
and cannot be explained by a trial-type or identity confound.

Design, in order:
  1. Instances. For every correct single-omission trial (RXRR/RRXR/RRRX and their A/B-specific
     equivalents AXAB/AAXB/AAAX/BXBA/BBXA/BBBX), the omitted slot contributes one label=1
     ("omitted") instance and the trial's other two real slots (always drawn from {p2,p3,p4},
     never p1 -- p1 is never omitted in this task) contribute label=0 ("present") instances.
  2. Feature. Population raster (unit x time-bin) in a window (WIN_MS) around each instance's
     own slot onset, BIN_MS bins, for every unit recorded in that session x area.
  3. Grouping / CV. Trials are chronologically split into BLOCKS_PER_SESSION contiguous blocks
     per session (own convention, not the Milestone-1 reversal ontology's `cycle` field, which is
     scoped to a narrower 5-session design). Leave-one-block-out outer CV; groups.py's
     `permute_labels(..., scheme="within_group")` respects the same blocking for the null, so no
     permutation draw can produce a label pattern the real block structure could not have.
  4. Regularization. C is selected ONCE per fold on the window-averaged feature (frozen for every
     bin's decode) -- same "observed-fold-selected_C_frozen" convention this repo's own null
     machinery (jnwb/structured_identity_m2a.py) already uses, to keep a 28-bin sliding decode
     from re-running a C grid search at every single bin.
  5. Per-bin statistic. Balanced accuracy on pooled out-of-fold predictions, one curve per
     session x area cell.
  6. Null. For each of N_PERMUTATIONS draws, labels are permuted ONCE (within-block) and the
     FULL 28-bin curve is recomputed under that one permutation (not an independent permutation
     per bin) -- this is what lets a downstream cluster-mass statistic see the null's own
     bin-to-bin correlation, which is the entire point of a cluster-based permutation test over a
     correlated time axis (BH/per-bin correction would treat neighbouring, highly-dependent bins
     as independent tests and is the wrong family here).

Output: one .npz per successful session x area cell (observed curve + null curve array) under
OUT_DIR, plus a running manifest CSV -- both written incrementally so a partial/interrupted run
leaves usable results. A second script (aggregate_omission_onset_clusters.py) combines cells
within an area into the actual cluster-based onset test.
"""
from __future__ import annotations

import sys
import os
import time
import traceback
from pathlib import Path

# Must be set before numpy/OpenBLAS initializes its thread pool. On this machine, OpenBLAS's
# default multithreaded dispatch has catastrophic per-call overhead for the matrix sizes this
# script solves (measured: an 800x800 solve, 501 RHS columns, took 19.8s multithreaded vs 0.058s
# single-threaded -- a 340x difference), almost certainly a thread-pool spin/teardown cost paid
# on every one of the many small solves this sliding-window decoder issues. Single-threaded BLAS
# is not a fallback here, it is strictly faster for this workload on this hardware.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa
from jnwb import paths as _P
from jnwb.sequence_layout import EPOCH_ONSETS_MS
from jnwb.permutation import permute_labels
from jnwb.structured_identity_m2a import (
    OuterFold, build_outer_folds, _ridge_scores, _select_c, _has_both_classes, C_GRID,
)

NWB_DIR = _P.nwb_dir()
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_DIR = REPO_ROOT / "outputs/classification/omission_onset_sliding_window"
MANIFEST_CSV = OUT_DIR / "cell_manifest.csv"

WIN_MS = (-100.0, 600.0)
BIN_MS = 25.0
BLOCKS_PER_SESSION = 8
MIN_UNITS = 3
MIN_BLOCKS_WITH_BOTH_CLASSES = 3  # need >=1 held-out + >=2 train groups (build_outer_folds default)
N_PERMUTATIONS = 500
SEED = 42

SLOT_TO_CONDITIONS = {
    2: ["RXRR", "AXAB", "BXBA"],
    3: ["RRXR", "AAXB", "BBXA"],
    4: ["RRRX", "AAAX", "BBBX"],
}
ALL_SLOTS = (2, 3, 4)


def _edges():
    edges = np.arange(WIN_MS[0], WIN_MS[1] + BIN_MS, BIN_MS)
    ctr = (edges[:-1] + edges[1:]) / 2.0
    return edges, ctr


def load_session(prefix: str):
    return oa.read(str(_P.resolve_nwb_path(prefix)))


def build_instances(sess) -> pd.DataFrame:
    """One row per (trial, slot) instance: label 1=omitted, 0=present (same trial's other slots)."""
    rows = []
    trial_counter = 0
    for omit_slot, conds in SLOT_TO_CONDITIONS.items():
        for cond in conds:
            epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
            if epochs is None or len(epochs) == 0:
                continue
            starts = np.asarray(epochs["start_time"].values, dtype=float)
            for t0 in starts:
                trial_counter += 1
                for slot in ALL_SLOTS:
                    rows.append({
                        "trial_ordinal": trial_counter,
                        "start_time": t0,
                        "slot": slot,
                        "label": 1 if slot == omit_slot else 0,
                        "condition": cond,
                    })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # chronological blocks by TRIAL start_time (all of a trial's instances share one block)
    trial_order = df.drop_duplicates("trial_ordinal").sort_values("start_time")
    trial_order = trial_order.reset_index(drop=True)
    trial_order["block"] = (
        np.floor(np.arange(len(trial_order)) / len(trial_order) * BLOCKS_PER_SESSION)
        .astype(int).clip(max=BLOCKS_PER_SESSION - 1)
    )
    df = df.merge(trial_order[["trial_ordinal", "block"]], on="trial_ordinal", how="left")
    return df.sort_values("start_time").reset_index(drop=True)


def build_raster(sess, area: str, instances: pd.DataFrame, bin_ms: float, win_ms: tuple):
    units = sess.get_units(area=area)
    row_indices = list(units.index)
    if len(row_indices) < MIN_UNITS:
        return None, row_indices
    edges, ctr = _edges()
    n_bins = len(ctr)
    n = len(instances)
    X = np.zeros((n, len(row_indices), n_bins), dtype=np.float64)
    slot_ms = {s: EPOCH_ONSETS_MS[f"p{s}"] for s in ALL_SLOTS}
    onsets_s = (instances["start_time"].to_numpy() + np.array([slot_ms[s] for s in instances["slot"]]) / 1000.0)
    lo_s, hi_s = win_ms[0] / 1000.0, win_ms[1] / 1000.0
    edges_s = edges / 1000.0
    for col, row_index in enumerate(row_indices):
        spikes = sess.get_spike_times(row_index)
        if spikes is None or len(spikes) == 0:
            continue
        spikes = np.sort(np.asarray(spikes, dtype=float))
        for r, onset in enumerate(onsets_s):
            X[r, col], _ = np.histogram(spikes[(spikes >= onset + lo_s) & (spikes < onset + hi_s)] - onset,
                                        bins=edges_s)
    X = X / (bin_ms / 1000.0)  # Hz
    return X, row_indices


def _balanced_acc_matrix(labels_matrix: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    """labels_matrix: (n_test, n_cols) int in {0,1}; prediction: (n_test, n_cols). -> (n_cols,)."""
    n_cols = labels_matrix.shape[1]
    result = np.zeros(n_cols, dtype=float)
    for value in (0, 1):
        mask = labels_matrix == value
        denom = mask.sum(axis=0)
        numer = ((prediction == value) & mask).sum(axis=0)
        result += np.divide(numer, denom, out=np.zeros(n_cols, dtype=float), where=denom > 0)
    return result / 2.0


def decode_cell(X: np.ndarray, labels: np.ndarray, blocks: np.ndarray, seed: int):
    """Returns (observed_curve[n_bins], null_curve[N_PERMUTATIONS, n_bins], n_folds_used) or None.

    Vectorized across permutations: for each (bin, fold) the dual-ridge gram matrix depends only
    on the TRAINING FEATURES (fixed) and the per-sample class weights (frozen from the observed
    labels, same convention as jnwb.structured_identity_m2a.null_metric_distribution -- weights
    are not recomputed per permutation draw). Only the labels vector varies across permutations,
    so it is one extra column of the solve's right-hand side, not a separate O(n^3) refit -- one
    matrix factorization per (bin, fold) serves the real fit AND all N_PERMUTATIONS null draws.
    """
    n, n_units, n_bins = X.shape
    folds = build_outer_folds(blocks, labels, min_train_groups=2)
    if len(folds) < 2:
        return None

    # 1) freeze C per fold on the window-mean feature (R0-style), once.
    X_mean = X.mean(axis=2)
    selected_C = {}
    for fs in folds:
        try:
            C, _, n_inner = _select_c(X_mean, labels, blocks, fs.train_idx, fs.inner_groups,
                                      seed=seed + fs.fold * 1000, c_grid=C_GRID)
        except ValueError:
            return None
        if n_inner == 0:
            return None
        selected_C[fs.fold] = C

    # 2) precompute all permuted label vectors ONCE (bin-independent).
    rng = np.random.default_rng(seed + 777)
    perm_labels = np.stack(
        [permute_labels(labels, groups=blocks, scheme="within_group", rng=rng)
         for _ in range(N_PERMUTATIONS)], axis=1
    )  # (n, N_PERMUTATIONS)

    observed = np.full(n_bins, np.nan)
    null_curves = np.full((N_PERMUTATIONS, n_bins), np.nan)

    for b in range(n_bins):
        Xb = X[:, :, b]
        real_pred = np.full(n, -1, dtype=int)
        perm_pred = np.full((n, N_PERMUTATIONS), -1, dtype=int)
        for fs in folds:
            train_idx, test_idx = fs.train_idx, fs.test_idx
            X_train = Xb[train_idx]
            mean = X_train.mean(axis=0)
            scale = X_train.std(axis=0)
            scale[scale == 0.0] = 1.0
            Xtr = (X_train - mean) / scale
            Xte = (Xb[test_idx] - mean) / scale

            train_base = labels[train_idx]  # observed labels fix the sample weights (see docstring)
            counts = np.bincount(train_base, minlength=2).astype(float)
            weights = np.sqrt(len(train_base) / (2.0 * counts[train_base]))
            weighted_train = Xtr * weights[:, None]

            # Primal-form normal equations (n_units x n_units), not the dual gram (n_train x
            # n_train) _ridge_scores uses -- mathematically identical ridge solution, but here
            # n_units (a few hundred at most) is always << n_train (~700-900), so primal is the
            # cheap side of the kernel trick. Milestone 2A's R1 flattens unit*time into a much
            # higher-dimensional feature, where the dual form is the correct choice instead --
            # this per-bin decoder's feature is unit-only, so the tradeoff flips.
            A = weighted_train.T @ weighted_train
            A.flat[:: len(A) + 1] += 1.0 / float(selected_C[fs.fold])

            y_real = 2.0 * labels[train_idx] - 1.0
            y_perm = 2.0 * perm_labels[train_idx][:, :] - 1.0
            rhs_y = np.concatenate([y_real[:, None], y_perm], axis=1) * weights[:, None]
            rhs = weighted_train.T @ rhs_y  # (n_units, 1+N_PERM)
            coeffs = np.linalg.solve(A, rhs)  # (n_units, 1+N_PERM)
            scores = Xte @ coeffs  # (n_test, 1+N_PERM)
            preds = (scores >= 0.0).astype(int)
            real_pred[test_idx] = preds[:, 0]
            perm_pred[test_idx] = preds[:, 1:]

        covered = real_pred >= 0
        if covered.any():
            y_c, p_c = labels[covered], real_pred[covered]
            observed[b] = _balanced_acc_matrix(y_c[:, None], p_c[:, None])[0]

        covered_p = perm_pred[:, 0] >= 0  # same fold coverage for every permutation column
        if covered_p.any():
            null_curves[:, b] = _balanced_acc_matrix(perm_labels[covered_p], perm_pred[covered_p])

    return observed, null_curves, len(folds)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()
    _, ctr = _edges()

    manifest_rows = []
    if MANIFEST_CSV.exists():
        manifest_rows = pd.read_csv(MANIFEST_CSV).to_dict("records")
    done_cells = {(r["session"], r["area"]) for r in manifest_rows}

    t_start = time.time()
    for _, row in ready.iterrows():
        prefix = row["session_prefix"]
        try:
            sess = load_session(prefix)
        except Exception as e:
            print(f"[{prefix}] load failed: {e}")
            continue
        instances = build_instances(sess)
        if instances.empty:
            print(f"[{prefix}] no single-omission instances")
            continue
        areas = sorted(sess.get_units()["area"].dropna().unique().tolist())
        labels = instances["label"].to_numpy()
        blocks = instances["block"].to_numpy()
        n_blocks_ok = sum(
            _has_both_classes(labels, np.flatnonzero(blocks == b)) for b in np.unique(blocks)
        )
        for area in areas:
            key = (prefix, area)
            if key in done_cells:
                continue
            if n_blocks_ok < MIN_BLOCKS_WITH_BOTH_CLASSES:
                continue
            try:
                X, row_indices = build_raster(sess, area, instances, BIN_MS, WIN_MS)
                if X is None:
                    continue
                result = decode_cell(X, labels, blocks, seed=SEED)
                if result is None:
                    continue
                observed, null_curves, n_folds = result
            except Exception:
                print(f"[{prefix}/{area}] FAILED:\n{traceback.format_exc()}")
                continue

            npz_path = OUT_DIR / f"{prefix}__{area}.npz"
            np.savez(npz_path, observed=observed, null=null_curves, bin_centers_ms=ctr)
            manifest_rows.append({
                "session": prefix, "subject": prefix.split("sub-")[1].split("_ses-")[0],
                "area": area, "n_units": len(row_indices), "n_instances": len(instances),
                "n_omitted": int(labels.sum()), "n_present": int((labels == 0).sum()),
                "n_folds": n_folds, "npz": str(npz_path),
            })
            pd.DataFrame(manifest_rows).to_csv(MANIFEST_CSV, index=False)
            print(f"[{prefix}/{area}] units={len(row_indices)} instances={len(instances)} "
                  f"folds={n_folds} peak_acc={np.nanmax(observed):.3f} "
                  f"elapsed={time.time()-t_start:.0f}s")

    print("DONE. cells:", len(manifest_rows))


if __name__ == "__main__":
    main()
